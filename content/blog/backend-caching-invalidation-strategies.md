---
title: "Cache Invalidation Strategies"
slug: "backend-caching-invalidation-strategies"
description: "Cache invalidation strategies that work: TTL, write-through, write-behind, event-driven invalidation, and choosing the right pattern for your data."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Backend", "Architecture", "Databases", "DevOps"]
keywords: "cache invalidation strategies, cache-aside pattern, write-through cache, event-driven cache invalidation, Redis caching patterns"
faq:
  - q: "What is the hardest problem in caching?"
    a: "Cache invalidation — knowing when to remove or update cached data so clients never see stale results after the underlying data changes. There are only two hard things in computer science: cache invalidation, naming things, and off-by-one errors. The right strategy depends on your consistency requirements and write patterns."
  - q: "What is the cache-aside pattern?"
    a: "The application manages the cache explicitly: on read, check cache first — if miss, read from database and populate cache. On write, update the database and invalidate (or update) the cache entry. It's the most common pattern because the cache is optional — if it fails, the app still works by reading from the database."
  - q: "When should I use TTL-based expiration vs event-driven invalidation?"
    a: "Use TTL when slightly stale data is acceptable (product catalogs, user profiles, config). Use event-driven invalidation when freshness matters (account balances, inventory counts, permissions). Most production systems combine both: TTL as a safety net, events for immediate invalidation on writes."
---

There are two hard things in computer science — and cache invalidation is the one that causes production incidents at 2am. Your Redis cache serves user profiles in 2ms instead of 50ms database queries, but when a user updates their email, the cache still shows the old one for 15 minutes. The strategies below aren't theoretical — they're the patterns I deploy based on how stale the data can be and how often it changes.

## Strategy overview

| Strategy | Consistency | Complexity | Best for |
|----------|------------|------------|----------|
| TTL expiration | Eventual (bounded) | Low | Catalogs, configs, profiles |
| Cache-aside + invalidate | Strong (on write) | Medium | User data, settings |
| Write-through | Strong | Medium | Always-fresh reads |
| Write-behind | Eventual | High | Write-heavy workloads |
| Event-driven | Strong (near real-time) | High | Multi-service, shared cache |

## Cache-aside (most common)

Application manages cache lifecycle:

```python
def get_user(user_id: str) -> User:
    cache_key = f"user:{user_id}"

    # Read: cache first
    cached = redis.get(cache_key)
    if cached:
        return User.from_json(cached)

    # Cache miss: read DB, populate cache
    user = db.get_user(user_id)
    if user:
        redis.setex(cache_key, 900, user.to_json())  # 15 min TTL
    return user

def update_user(user_id: str, data: dict) -> User:
    user = db.update_user(user_id, data)

    # Write: update DB, invalidate cache
    redis.delete(f"user:{user_id}")
    return user
```

On write, **invalidate** (delete) rather than update the cache — simpler and avoids race conditions where a concurrent read re-populates with stale data between your DB write and cache update.

## TTL as safety net

Even with invalidation, set TTLs as a backstop:

```python
redis.setex(cache_key, 900, data)  # expires in 15 min regardless
```

If invalidation fails (Redis down, bug in invalidation logic), TTL ensures stale data eventually disappears. Choose TTL based on acceptable staleness:

| Data type | TTL | Rationale |
|-----------|-----|-----------|
| Product catalog | 1 hour | Changes infrequently |
| User profile | 15 min | Moderate change rate |
| Config/settings | 5 min | Needs reasonable freshness |
| Inventory count | 30 sec | High change rate, short tolerance |
| Session data | Match session lifetime | Security |

## Event-driven invalidation

For multi-service architectures where one service writes and another caches:

```python
# Order service publishes event on update
event_bus.publish("order.updated", {"order_id": "4521"})

# Cache service subscribes
@subscribe("order.updated")
def invalidate_order_cache(event):
    redis.delete(f"order:{event['order_id']}")
    redis.delete(f"user_orders:{get_user_for_order(event['order_id'])}")
```

This is the [outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/) applied to cache invalidation — reliable event delivery ensures cache stays consistent.

Invalidate related caches too. Updating an order should invalidate both the order cache and the user's order list cache.

## Write-through

Cache and database updated synchronously on write:

```python
def update_user(user_id: str, data: dict) -> User:
    user = db.update_user(user_id, data)
    redis.setex(f"user:{user_id}", 900, user.to_json())  # update cache immediately
    return user

def get_user(user_id: str) -> User:
    cached = redis.get(f"user:{user_id}")
    if cached:
        return User.from_json(cached)
    user = db.get_user(user_id)
    return user  # don't cache on read — write-through populates on write
```

Reads are always fast (cache hit after first write). Writes are slower (must update both). Good when reads vastly outnumber writes and freshness matters.

## Cache stampede prevention

When a popular cache entry expires, hundreds of concurrent requests hit the database:

```python
def get_with_lock(cache_key: str, fetch_fn, ttl: int = 900):
    cached = redis.get(cache_key)
    if cached:
        return cached

    lock_key = f"lock:{cache_key}"
    if redis.set(lock_key, "1", nx=True, ex=10):  # acquire lock
        try:
            data = fetch_fn()
            redis.setex(cache_key, ttl, data)
            return data
        finally:
            redis.delete(lock_key)
    else:
        time.sleep(0.1)  # wait for lock holder
        return redis.get(cache_key) or fetch_fn()  # retry or fallback
```

Only one request regenerates the cache; others wait or serve slightly stale data.

## What NOT to cache

- **Rapidly changing data** where TTL < 5 seconds (just read the DB)
- **User-specific sensitive data** without encryption (PII in Redis)
- **Large objects** (>1MB — network cost exceeds DB query cost)
- **Aggregations** that are expensive to invalidate (invalidate 50 related keys on one write)

For [semantic caching in LLM APIs](https://blog.michaelsam94.com/semantic-caching-llm-apis/), different rules apply — similar queries hit cached responses with TTL and embedding similarity thresholds.

## Monitoring

Track:
- **Hit rate**: `hits / (hits + misses)` — below 80% means your cache isn't effective
- **Stale serves**: count of reads after invalidation should have fired
- **Memory usage**: evictions under memory pressure
- **Invalidation lag**: time between write and cache delete

Prefer TTL plus event-driven invalidation over pure TTL — stale-while-revalidate masks invalidation bugs until users report wrong data.

## Common production mistakes

Teams get caching invalidation strategies wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Backend services for caching invalidation strategies fall over when retries amplify load, idempotency keys expire before clients retry, and bulkheads are configured in code but not enforced in deployment topology.

## Debugging and triage workflow

When caching invalidation strategies misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Redis caching patterns](https://redis.io/docs/latest/develop/use/patterns/)
- [AWS caching best practices](https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/Strategies.html)
- [Martin Fowler — Cache-Aside pattern](https://martinfowler.com/bliki/CacheAside.html)
- [Event-driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [Connection pooling for serverless](https://blog.michaelsam94.com/connection-pooling-serverless-databases/)
