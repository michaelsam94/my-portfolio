---
title: "Rate Limiting with Redis"
slug: "redis-rate-limiting-sliding-window"
description: "Implement rate limiting with Redis: sliding window log, token bucket, and fixed window algorithms with production-ready code and header patterns."
datePublished: "2026-01-20"
dateModified: "2026-01-20"
tags: ["Backend", "Redis", "Rate Limiting", "API"]
keywords: "Redis rate limiting, sliding window log, token bucket Redis, API throttling, fixed window counter, rate limit headers"
faq:
  - q: "Why use Redis for rate limiting?"
    a: "Rate limits must be enforced consistently across all application instances. In-memory per-process counters let clients exceed limits by routing requests to different servers. Redis provides atomic operations and sub-millisecond latency for shared counters that every instance reads and writes. It is the standard backend for distributed rate limiting."
  - q: "Which rate limiting algorithm is most accurate?"
    a: "Sliding window log tracks individual request timestamps and counts within a rolling window — the most accurate approach. Token bucket allows controlled bursts while maintaining an average rate. Fixed window is simplest but allows up to 2x the limit at window boundaries. For API rate limits where precision matters, use sliding window log."
  - q: "How do I return rate limit status to API clients?"
    a: "Include standard headers on every response: X-RateLimit-Limit (max requests), X-RateLimit-Remaining (requests left), X-RateLimit-Reset (window reset timestamp). On 429 responses, add Retry-After with seconds until the client can retry. These headers let clients self-throttle before hitting limits."
---

API key `sk_live_abc` sent 4,000 requests in the minute after a cron job misconfigured its polling interval. Your per-key limit was 1,000 per minute. Without a shared counter, three app servers each counted 1,333 requests locally and saw no problem. Redis-backed rate limiting aggregates counts across every instance so the 1,001st request gets a 429 regardless of which server handles it.

## Fixed window counter

Simplest approach — count requests per clock-aligned window:

```python
import redis
import time

r = redis.Redis(host="redis.internal")

def fixed_window_limit(key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    window_key = f"rl:{key}:{int(time.time()) // window_seconds}"

    pipe = r.pipeline()
    pipe.incr(window_key)
    pipe.expire(window_key, window_seconds)
    count, _ = pipe.execute()

    remaining = max(0, limit - count)
    return count <= limit, remaining
```

**Problem:** A client can send `limit` requests at 00:00:59 and another `limit` at 00:01:00 — 2x the intended rate in a two-second burst.

## Sliding window log

Track individual request timestamps in a sorted set:

```python
def sliding_window_limit(key: str, limit: int, window_ms: int) -> tuple[bool, int]:
    now = time.time() * 1000
    redis_key = f"rl:sw:{key}"

    pipe = r.pipeline()
    # Remove expired entries
    pipe.zremrangebyscore(redis_key, 0, now - window_ms)
    # Add current request
    pipe.zadd(redis_key, {str(now): now})
    # Count requests in window
    pipe.zcard(redis_key)
    # Set TTL for cleanup
    pipe.expire(redis_key, int(window_ms / 1000) + 1)

    _, _, count, _ = pipe.execute()
    remaining = max(0, limit - count)
    return count <= limit, remaining
```

No boundary burst problem. Memory scales with request volume in the window — fine for API limits (hundreds per minute), expensive for millions per second.

## Token bucket

Allow bursts while maintaining average rate:

```python
BUCKET_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local data = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(data[1]) or capacity
local last_refill = tonumber(data[2]) or now

local elapsed = now - last_refill
tokens = math.min(capacity, tokens + elapsed * refill_rate)

if tokens >= 1 then
    tokens = tokens - 1
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, math.ceil(capacity / refill_rate) + 1)
    return {1, math.floor(tokens)}
else
    return {0, 0}
end
"""

def token_bucket_limit(key: str, capacity: int, refill_per_second: float) -> tuple[bool, int]:
    redis_key = f"rl:tb:{key}"
    now = time.time()
    allowed, remaining = r.eval(
        BUCKET_LUA, 1, redis_key, capacity, refill_per_second, now
    )
    return bool(allowed), int(remaining)
```

`capacity=100, refill_per_second=10` allows 100-request bursts, then steady 10/second. Lua ensures atomicity.

## Middleware integration

```python
from functools import wraps

def rate_limit(limit: int = 100, window: int = 60):
    def decorator(fn):
        @wraps(fn)
        def wrapper(request):
            key = f"apikey:{request.api_key}"
            allowed, remaining = sliding_window_limit(key, limit, window * 1000)

            if not allowed:
                return Response(
                    status=429,
                    headers={
                        "Retry-After": str(window),
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": "0",
                    },
                    body="Rate limit exceeded",
                )

            response = fn(request)
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            return response
        return wrapper
    return decorator
```

## Tiered limits

Different limits per plan tier:

```python
TIER_LIMITS = {
    "free":       {"requests": 100,   "window": 3600},
    "pro":        {"requests": 1000,  "window": 3600},
    "enterprise": {"requests": 10000, "window": 3600},
}

def check_tier_limit(api_key: str) -> tuple[bool, int]:
    tier = get_api_key_tier(api_key)
    config = TIER_LIMITS[tier]
    return sliding_window_limit(
        f"tier:{api_key}",
        config["requests"],
        config["window"] * 1000,
    )
```

Store tier in the API key metadata. Limits apply per key, not per IP — preventing circumvention by rotating IPs.

## Redis Cell module

Redis offers the Cell module (formerly Redis-Cell) for native rate limiting:

```bash
CL.THROTTLE user:42 15 30 10 2
# key, max_burst, rate_period, quantity, cost
```

Returns `[limited, total_rate, remaining, retry_in]` in one atomic call. Available in Redis Enterprise and some managed providers.

## Algorithm selection

| Algorithm | Accuracy | Burst handling | Memory | Complexity |
|-----------|----------|---------------|--------|------------|
| Fixed window | Low | Bad (2x at boundary) | Low | Trivial |
| Sliding window log | High | None | Per-request | Moderate |
| Token bucket | Moderate | Controlled bursts | Low | Moderate |
| Sliding window counter | Good | Minimal | Low | Low |

**Sliding window counter** (hybrid) — approximate sliding window by weighting the previous and current fixed windows. Good balance of accuracy and memory for high-traffic APIs.

Treat production rollout as a measured change: ship with observability, validate rollback, and review metrics 24 hours after deploy — patterns that look obvious in docs fail when skipped under release pressure.

## Common production mistakes

Teams get rate limiting sliding window wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Redis usage for rate limiting sliding window loses data when persistence mode is misunderstood, hot keys saturate single shards, and TTL strategy is applied after memory pressure already triggered evictions.

## Debugging and triage workflow

When rate limiting sliding window misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Redis rate limiting patterns](https://redis.io/docs/latest/develop/use/patterns/rate-limiting/)
- [Stripe rate limiter engineering blog](https://stripe.com/blog/rate-limiters)
- [IETF RateLimit header draft](https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-ratelimit-headers)
- [redis-cell module](https://github.com/brandur/redis-cell)
- [Cloudflare rate limiting rules](https://developers.cloudflare.com/waf/rate-limiting-rules/)
