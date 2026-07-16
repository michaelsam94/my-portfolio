---
title: "Rate-Limiting Algorithms Compared"
slug: "api-rate-limiting-algorithms"
description: "Compare rate-limiting algorithms — token bucket, sliding window, fixed window, leaky bucket — with implementation patterns for APIs and when to use each."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Backend", "API", "Architecture", "DevOps"]
keywords: "rate limiting algorithms, token bucket, sliding window rate limit, fixed window rate limiter, API rate limiting implementation"
faq:
  - q: "What is the best rate-limiting algorithm for APIs?"
    a: "Token bucket is the most common choice for APIs — it allows controlled bursts while maintaining an average rate over time. Sliding window log provides the most accurate rate limiting but uses more memory. Fixed window is simplest but allows burst at window boundaries. Choose based on whether you need burst tolerance and how precise your limits must be."
  - q: "Where should rate limiting happen in the architecture?"
    a: "Rate limit at both the API gateway (coarse per-client limits) and the service level (fine-grained per-resource limits). The gateway stops abuse before it reaches services; service-level limits protect expensive operations individually. Never rely on only one layer."
  - q: "How do I implement distributed rate limiting?"
    a: "Use a shared store (Redis) for rate limit counters across multiple service instances. Atomic increment operations (INCR + EXPIRE in Redis) ensure consistent limits regardless of which instance handles the request. Local in-memory limiters are fine for single-instance deployments but break with horizontal scaling."
---

Rate limiting is how your API survives the traffic spike from a Product Hunt launch, a misconfigured cron job, or a competitor scraping your endpoints. Without it, one aggressive client degrades service for everyone. The algorithm you pick determines whether legitimate burst traffic gets through, whether users hit limits at predictable times, and whether your limiter stays accurate under load. I've implemented all four major algorithms in production; token bucket handles 90% of cases, and the rest exist for specific edge cases.

## Algorithm comparison

| Algorithm | Burst allowed | Accuracy | Memory | Complexity |
|-----------|--------------|----------|--------|------------|
| Fixed window | At window edge | Low (2x burst at boundary) | O(1) | Trivial |
| Sliding window log | No | Highest | O(n) per client | High |
| Sliding window counter | Small | High | O(1) | Moderate |
| Token bucket | Yes (controlled) | Good | O(1) | Moderate |
| Leaky bucket | No (smooth output) | Good | O(1) | Moderate |

## Fixed window

Count requests per time window. Simplest, but allows 2x burst at boundaries:

```
Window 1 (00:00-00:59): 100 requests allowed
Window 2 (01:00-01:59): 100 requests allowed

User sends 100 requests at 00:59 and 100 at 01:00 = 200 in 2 seconds
```

```python
# Redis fixed window
def is_allowed_fixed(user_id: str, limit: int = 100, window: int = 60) -> bool:
    key = f"rate:{user_id}:{int(time.time()) // window}"
    current = redis.incr(key)
    if current == 1:
        redis.expire(key, window)
    return current <= limit
```

Use when: approximate limits are fine, simplicity matters, burst at boundaries is acceptable.

## Token bucket

Tokens accumulate at a fixed rate up to a maximum (bucket capacity). Each request consumes one token:

```python
def is_allowed_token_bucket(user_id: str, rate: float = 1.0, capacity: int = 10) -> bool:
    key = f"bucket:{user_id}"
    now = time.time()

    data = redis.hgetall(key)
    if not data:
        tokens = capacity
        last_refill = now
    else:
        tokens = float(data[b"tokens"])
        last_refill = float(data[b"last_refill"])
        elapsed = now - last_refill
        tokens = min(capacity, tokens + elapsed * rate)

    if tokens >= 1:
        tokens -= 1
        redis.hset(key, mapping={"tokens": tokens, "last_refill": now})
        redis.expire(key, int(capacity / rate) + 1)
        return True
    return False
```

`rate=1.0, capacity=10`: average 1 req/sec, burst up to 10. Best general-purpose choice for APIs.

## Sliding window counter

Hybrid of fixed window and sliding window — weighted average of current and previous window:

```python
def is_allowed_sliding(user_id: str, limit: int = 100, window: int = 60) -> bool:
    now = time.time()
    current_window = int(now) // window
    previous_window = current_window - 1
    elapsed_in_window = now - (current_window * window)

    current_count = int(redis.get(f"rate:{user_id}:{current_window}") or 0)
    previous_count = int(redis.get(f"rate:{user_id}:{previous_window}") or 0)

    weighted = previous_count * (1 - elapsed_in_window / window) + current_count
    if weighted >= limit:
        return False

    redis.incr(f"rate:{user_id}:{current_window}")
    redis.expire(f"rate:{user_id}:{current_window}", window * 2)
    return True
```

Smooth limit enforcement without boundary burst. Good accuracy with O(1) memory.

## Response headers

Tell clients their limit status:

```
HTTP/1.1 200 OK
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 42
X-RateLimit-Reset: 1704067200
Retry-After: 30  (only on 429)
```

```python
@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    allowed, remaining, reset = check_rate_limit(request.user.id)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"error": "Rate limit exceeded"},
            headers={
                "Retry-After": str(reset - int(time.time())),
                "X-RateLimit-Limit": "100",
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset),
            }
        )
    response = await call_next(request)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    return response
```

Return 429 Too Many Requests with `Retry-After` header. Clients (and [agent cost control systems](https://blog.michaelsam94.com/agent-cost-control-budgets/)) can back off intelligently.

## Layered rate limiting

```
Layer 1: Gateway — 1000 req/min per API key (token bucket)
Layer 2: Service — 100 req/min per user (sliding window)
Layer 3: Endpoint — 5 req/min for /export (fixed window)
```

Each layer protects against different abuse patterns. Gateway stops DDoS; service stops individual abuse; endpoint protects expensive operations.

Implement at the [API gateway](https://blog.michaelsam94.com/api-gateway-patterns/) for layers 1 and optionally layer 3 for public endpoints.

Return Retry-After header on 429 responses — clients without backoff hammer harder when rate limited without guidance.

## Token bucket implementation sketch

```python
def allow(key: str, rate: float, burst: int) -> bool:
    bucket = redis.hgetall(f"rl:{key}")
    tokens = float(bucket.get("tokens", burst))
    last = float(bucket.get("last", time.time()))
    tokens = min(burst, tokens + (time.time() - last) * rate)
    if tokens >= 1:
        redis.hset(f"rl:{key}", mapping={"tokens": tokens - 1, "last": time.time()})
        return True
    return False
```

Return `Retry-After` header on 429 — clients without backoff hammer harder.

## Common production mistakes

Teams get rate limiting algorithms wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

API design for rate limiting algorithms frustrates clients when pagination cursors expire silently, error bodies lack stable machine-readable codes, and rate limits return 429 without `Retry-After` headers.

## Debugging and triage workflow

When rate limiting algorithms misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Token bucket algorithm (Wikipedia)](https://en.wikipedia.org/wiki/Token_bucket)
- [Redis rate limiting patterns](https://redis.io/docs/latest/develop/use/patterns/rate-limiting/)
- [IETF RateLimit header fields draft](https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-ratelimit-headers)
- [Rate limiting and backpressure](https://blog.michaelsam94.com/rate-limiting-backpressure/)
- [API gateway patterns](https://blog.michaelsam94.com/api-gateway-patterns/)
