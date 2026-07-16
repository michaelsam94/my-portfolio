---
title: "Redis Cache-Aside and Write-Through"
slug: "redis-caching-patterns-cache-aside"
description: "Cache-aside, read-through, and write-through patterns with Redis: consistency trade-offs, stampede prevention, TTL strategy, and when caching hurts more than it helps."
datePublished: "2026-01-12"
dateModified: "2026-01-12"
tags: ["Backend", "Redis", "Performance", "Architecture"]
keywords: "Redis cache-aside, write-through cache, read-through, cache stampede, cache invalidation, TTL strategy"
faq:
  - q: "What is the cache-aside pattern?"
    a: "In cache-aside (lazy loading), the application manages the cache explicitly. On read, check Redis first; on miss, load from the database, populate the cache, and return. On write, update the database first, then invalidate or update the cache entry. The cache does not sit transparently in front of the database — application code orchestrates both layers."
  - q: "How does write-through differ from cache-aside?"
    a: "Write-through updates the cache and database synchronously on every write — the cache is always warm for written keys. Cache-aside typically invalidates on write and repopulates on next read. Write-through simplifies read consistency but adds write latency and can cache data that is never read again."
  - q: "How do I prevent cache stampede?"
    a: "When a hot key expires, many concurrent requests may miss simultaneously and hammer the database. Mitigations include probabilistic early expiration, request coalescing (single-flight — only one thread rebuilds, others wait), locking with SETNX, or never expiring hot keys and invalidating explicitly on write."
---

The database was melting at 2,000 queries per second for a product catalog page that changed twice a day. Redis cache-aside dropped read load on Postgres by 94% with forty lines of application code and sensible TTLs. The hard part was not adding Redis — it was choosing invalidation semantics so users never saw stale prices after a promotion went live.

Caching patterns are boring until they are wrong. Wrong means phantom inventory, double-charged wallets, or a thundering herd that takes down the origin during a key expiry.

## Cache-aside — the default pattern

```
Read:
  1. GET cache key
  2. Hit → return
  3. Miss → SELECT from DB → SET cache → return

Write:
  1. UPDATE database
  2. DEL cache key (or SET new value)
```

```python
def get_product(product_id: str) -> Product:
    key = f"product:{product_id}"
    cached = redis.get(key)
    if cached:
        return Product.parse_raw(cached)

    product = db.query(Product).get(product_id)
    if product:
        redis.setex(key, 3600, product.json())
    return product

def update_product(product_id: str, data: dict) -> Product:
    product = db.update(product_id, data)
    redis.delete(f"product:{product_id}")  # invalidate, don't update in place
    return product
```

**Invalidate on write** vs **update on write**: invalidation is safer when the cached object is derived from joins or computed fields. Updating in place risks partial staleness if the cache shape does not match the DB row exactly.

## Read-through and write-through

**Read-through** moves cache population into a cache layer (or library) that calls a loader callback on miss. Application code only talks to the cache API. Same consistency properties as cache-aside; cleaner call sites.

**Write-through** writes to cache and DB together:

```
Write:
  1. SET cache
  2. UPDATE database (same request)
```

Reads always hit warm cache for written keys. Writes pay cache + DB latency every time. Use when read-after-write consistency must be instant and write volume is moderate.

**Write-behind (write-back)** writes to cache immediately and asynchronously flushes to DB. Highest write performance, hardest consistency story. I avoid it unless you have explicit durability requirements and replay infrastructure.

## TTL strategy that matches data shape

| Data type | TTL approach |
| --- | --- |
| Static config | Long TTL + explicit invalidation on admin change |
| User session | Match session lifetime; refresh on activity |
| Aggregates (counts) | Short TTL (30–60s) or invalidate on underlying write |
| Hot product pages | No TTL; invalidate on catalog update |

Blind one-hour TTL on everything is how promotions go live in the database but not on the website for fifty-nine minutes.

## Stampede prevention

Hot key `product:flash-sale-1` expires. Ten thousand requests miss at once. Postgres falls over.

**Single-flight (request coalescing):**

```python
def get_product_coalesced(product_id: str) -> Product:
    key = f"product:{product_id}"
    cached = redis.get(key)
    if cached:
        return Product.parse_raw(cached)

    lock_key = f"lock:{key}"
    if redis.set(lock_key, "1", nx=True, ex=10):
        try:
            product = db.query(Product).get(product_id)
            redis.setex(key, 3600, product.json())
            return product
        finally:
            redis.delete(lock_key)
    else:
        time.sleep(0.05)
        return get_product_coalesced(product_id)  # retry — cache likely warm
```

**Probabilistic early expiration:** refresh before hard expiry with probability increasing as TTL approaches zero — spreads load over time.

**External pre-warming:** background job refreshes hot keys before expiry. Simple and effective for known hot paths.

## Consistency traps

- **Race on invalidate:** Thread A reads miss, loads stale DB. Thread B updates DB and deletes cache. Thread A writes stale value to cache. Fix: use version tags, shorter TTL, or set-after-write ordering with transactional outbox.
- **Caching null:** Cache misses for non-existent IDs should store a sentinel with short TTL to block repeated DB lookups (cache penetration).
- **Caching errors:** Do not cache 500 responses. Cache 404s briefly if appropriate.

## When not to cache

Skip Redis when:

- Data changes on every read (personalized real-time feeds with no shared keys)
- Dataset is smaller than Redis overhead would suggest
- Strong consistency is non-negotiable and invalidation is harder than the query
- The query is already fast (<5ms indexed lookup) and not contended

Measure hit rate. Below 80% on intentional cache keys, you are paying complexity for little gain.

## Common production mistakes

Teams get caching patterns cache aside wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Redis usage for caching patterns cache aside loses data when persistence mode is misunderstood, hot keys saturate single shards, and TTL strategy is applied after memory pressure already triggered evictions.

## Debugging and triage workflow

When caching patterns cache aside misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Redis caching strategies (redis.io)](https://redis.io/docs/latest/develop/use/patterns/)
- [Cache-Aside pattern (Microsoft Azure Architecture)](https://learn.microsoft.com/en-us/azure/architecture/patterns/cache-aside)
- [AWS caching best practices](https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/Strategies.html)
- [Scaling Memcache at Facebook (paper)](https://www.usenix.org/conference/nsdi13/technical-sessions/presentation/nishtala)
- [SETNX command reference](https://redis.io/docs/latest/commands/setnx/)
