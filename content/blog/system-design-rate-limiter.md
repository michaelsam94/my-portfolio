---
title: "System Design: Distributed Rate Limiter"
slug: "system-design-rate-limiter"
description: "Design a distributed rate limiter using token bucket and sliding window algorithms, with Redis-backed counters that enforce limits across multiple API gateway instances."
datePublished: "2025-11-09"
dateModified: "2025-11-09"
tags: ["System Design", "Rate Limiting", "Architecture", "Backend"]
keywords: "distributed rate limiter design, token bucket algorithm, sliding window counter, Redis rate limiting, API rate limit architecture"
faq:
  - q: "What is the difference between token bucket and sliding window rate limiting?"
    a: "Token bucket allows bursts up to bucket capacity while maintaining an average rate — a bucket of 100 tokens refilling at 10/sec permits 100 immediate requests then throttles to 10/sec. Sliding window counts requests in a rolling time window — exactly 100 requests in any 60-second period, no burst above 100. Token bucket is smoother for user experience; sliding window is stricter for hard limits like API quotas."
  - q: "How do you implement rate limiting across multiple servers?"
    a: "Centralize counter state in a shared store (Redis) that all API gateway instances read and write. Each request atomically increments a counter and checks against the limit. Redis INCR with EXPIRE or Lua scripts for atomic check-and-increment prevent race conditions. Local in-memory counters work for approximate limiting but fail when requests hit different instances."
  - q: "What HTTP status code should rate-limited requests return?"
    a: "429 Too Many Requests with Retry-After header indicating seconds until the client can retry. Include X-RateLimit-Limit, X-RateLimit-Remaining, and X-RateLimit-Reset headers so clients can self-throttle. For API products, return rate limit info on successful responses too — clients shouldn't have to hit the limit to discover their quota."
---

Our public API had no rate limiting. A misconfigured integration script sent 50,000 requests per minute from a single API key, starving database connections for every other customer. We added rate limiting in an afternoon with Redis — token bucket per API key, 1000 requests per minute default. The script got 429 responses. Everyone else kept working. The fix cost one Redis instance and fifty lines of Lua.

A distributed rate limiter protects your API from abuse, ensures fair usage across tenants, and prevents cascading failures when one client overwhelms shared resources. The challenge is enforcing limits consistently when requests arrive at any of dozens of stateless API gateway instances.

## Rate limiting algorithms

**Fixed window:**

Count requests in fixed time buckets (e.g., minute 0:00-0:59). Simple but allows 2x burst at window boundaries — 100 requests at 0:59 and 100 at 1:00.

**Sliding window log:**

Store timestamp of each request. Count requests in the last N seconds. Accurate but memory-heavy — stores one entry per request.

**Sliding window counter (recommended):**

Hybrid of fixed window and sliding window. Weighted count from current and previous window:

```
count = prev_window_count * (1 - elapsed/window_size) + curr_window_count
```

**Token bucket:**

Bucket holds N tokens, refilling at rate R per second. Each request consumes one token. Allows bursts up to bucket size while maintaining average rate.

## Redis-backed token bucket

```lua
-- token_bucket.lua
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1]) or capacity
local last_refill = tonumber(bucket[2]) or now

local elapsed = now - last_refill
tokens = math.min(capacity, tokens + elapsed * refill_rate)

if tokens >= requested then
    tokens = tokens - requested
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, math.ceil(capacity / refill_rate) + 1)
    return {1, tokens}  -- allowed, remaining tokens
else
    return {0, tokens}  -- denied, current tokens
end
```

```python
async def is_allowed(key: str, capacity: int = 100, refill_rate: float = 1.0) -> tuple[bool, float]:
    result = await redis.evalsha(
        TOKEN_BUCKET_SHA,
        keys=[f"ratelimit:{key}"],
        args=[capacity, refill_rate, time.time(), 1]
    )
    allowed, remaining = result
    return bool(allowed), remaining
```

The Lua script executes atomically — no race condition between read and write even with concurrent requests from multiple gateway instances.

## Sliding window counter implementation

```python
async def sliding_window_count(key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    now = time.time()
    current_window = int(now // window_seconds)
    previous_window = current_window - 1
    elapsed_in_window = now % window_seconds

    current_key = f"ratelimit:{key}:{current_window}"
    previous_key = f"ratelimit:{key}:{previous_window}"

    current_count = int(await redis.get(current_key) or 0)
    previous_count = int(await redis.get(previous_key) or 0)

    weight = 1 - (elapsed_in_window / window_seconds)
    estimated_count = previous_count * weight + current_count

    if estimated_count >= limit:
        return False, max(0, limit - int(estimated_count))

    pipe = redis.pipeline()
    pipe.incr(current_key)
    pipe.expire(current_key, window_seconds * 2)
    await pipe.execute()

    return True, max(0, limit - int(estimated_count) - 1)
```

Memory efficient — two counters per key regardless of request volume.

## Integration with API gateway

Rate limiting runs as middleware before request processing:

```python
async def rate_limit_middleware(request, call_next):
    api_key = request.headers.get("X-API-Key")
    tier = await get_tier(api_key)  # free: 100/min, pro: 1000/min, enterprise: 10000/min

    allowed, remaining = await is_allowed(
        key=f"api:{api_key}",
        capacity=tier.limit,
        refill_rate=tier.limit / 60
    )

    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"error": "Rate limit exceeded"},
            headers={
                "Retry-After": str(tier.window_seconds),
                "X-RateLimit-Limit": str(tier.limit),
                "X-RateLimit-Remaining": "0",
            }
        )

    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(tier.limit)
    response.headers["X-RateLimit-Remaining"] = str(int(remaining))
    return response
```

## Multi-dimensional rate limiting

Production APIs limit on multiple dimensions simultaneously:

```python
limits = [
    ("api_key", api_key, 1000, 60),       # 1000/min per API key
    ("ip", client_ip, 100, 60),            # 100/min per IP
    ("endpoint", f"{api_key}:{path}", 100, 60),  # 100/min per endpoint
    ("global", "api", 100000, 60),         # 100K/min global
]

for dimension, key, limit, window in limits:
    allowed, _ = await sliding_window_count(key, limit, window)
    if not allowed:
        return rate_limit_response(dimension)
```

A request must pass all dimensions. Global limits protect shared infrastructure; per-key limits ensure fair usage; per-IP limits catch key-less abuse.

## Handling Redis failures

Rate limiter Redis downtime shouldn't take down your API:

- **Fail open:** Allow requests when Redis is unreachable. Log the failure. Accept temporary over-admission over total outage.
- **Local fallback:** Maintain an approximate in-memory counter as backup. Less accurate but prevents complete bypass.
- **Circuit breaker:** After N Redis failures, stop trying for M seconds and use local fallback.

```python
async def is_allowed_with_fallback(key, capacity, refill_rate):
    try:
        return await is_allowed(key, capacity, refill_rate)
    except RedisConnectionError:
        logger.warning("Redis unavailable, using local fallback")
        return local_limiter.check(key, capacity, refill_rate)
```

## Common production mistakes

Teams get rate limiter wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

System design for rate limiter breaks at scale when hot keys, thundering herds, and cache stampedes are discovered during launch week instead of load test week.

## Resources

- [Redis rate limiting patterns](https://redis.io/docs/reference/patterns/rate-limiter/)
- [Token bucket algorithm — Wikipedia](https://en.wikipedia.org/wiki/Token_bucket)
- [Stripe rate limiter blog post](https://stripe.com/blog/rate-limiters)
- [Cloudflare rate limiting architecture](https://blog.cloudflare.com/counting-things-a-lot-of-different-things/)
- [IETF draft: RateLimit header fields for HTTP](https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-ratelimit-headers)
