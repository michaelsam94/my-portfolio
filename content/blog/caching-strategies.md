---
title: "Caching Strategies That Don't Bite Back"
seoTitle: "Production Caching Strategies: Cache-Aside, TTL, Invalidation"
slug: "caching-strategies"
description: "Caching cuts latency and database load until stale data, thundering herds, or mystery invalidation cause an outage. Here's how to cache without the regret."
datePublished: "2026-05-03"
dateModified: "2026-05-06"
tags: ["Caching", "Performance", "Backend", "Architecture"]
keywords: "caching strategies, cache-aside, write-through cache, Redis caching, cache invalidation, thundering herd, TTL, CDN caching, cache stampede"
faq:
  - q: "What is the cache-aside pattern?"
    a: "The application checks the cache first. On a miss, it reads from the database, stores the result in cache, and returns it. The app owns cache logic — the database knows nothing about caching."
  - q: "How do I avoid serving stale data?"
    a: "Set TTLs based on how stale the data can be, invalidate on writes for data that must be fresh, and use versioned cache keys when schema changes. There is no universal invalidation strategy — it depends on read/write ratio and freshness requirements."
  - q: "What is a cache stampede (thundering herd)?"
    a: "When a popular cache key expires and hundreds of concurrent requests all miss at once, each hitting the database. Mitigate with request coalescing (single-flight), jittered TTLs, or stale-while-revalidate."
---

Caching is easy to add and hard to get right. A Redis layer in front of Postgres cuts p99 latency from 80ms to 2ms — until a popular key expires and 500 concurrent requests stampede the database, or a charger status update sits in cache for 60 seconds while the driver wonders why the app says "Available" and the hardware says "Charging." I've seen both on real-time systems. The fix isn't "don't cache" — it's choosing the right pattern for each data type and knowing when stale is acceptable.

## The four caching patterns

| Pattern | Who writes to cache | When to use |
|---|---|---|
| Cache-aside | Application (on read miss) | General purpose, most common |
| Read-through | Cache layer (transparent to app) | When cache library supports it (e.g., Hazelcast) |
| Write-through | Application (on every write) | Data that must always be in cache |
| Write-behind | Cache layer (async to DB) | High write throughput, eventual consistency OK |

**Cache-aside** is the default for a reason. The application controls what gets cached and when:

```python
def get_charger(charger_id: str) -> Charger:
    cache_key = f"charger:{charger_id}"

    cached = redis.get(cache_key)
    if cached:
        return Charger.from_json(cached)

    charger = db.query("SELECT * FROM chargers WHERE id = %s", charger_id)
    if charger:
        redis.setex(cache_key, ttl=300, value=charger.to_json())
    return charger
```

On a miss, one request hits the database and populates the cache. Subsequent requests hit Redis. Simple, debuggable, and the database is never unaware of the cache.

## TTL: your first and best invalidation strategy

Time-to-live is the simplest invalidation — let the cache entry expire and the next read refreshes it. Choose TTL based on **how stale the data can be**, not on how often it changes:

| Data type | Staleness tolerance | TTL |
|---|---|---|
| Charger static info (name, location) | Hours | 3600s |
| Charger live status | Seconds | 5–15s |
| User profile | Minutes | 300s |
| Tariff/pricing rules | Until next publish | 86400s or event-driven invalidation |
| Session list (active) | None — don't cache | — |

On the [EV charging platform](https://blog.michaelsam94.com/how-i-architected-an-ev-charging-platform/), live charger status was **never cached in Redis**. It flowed through [WebSocket push](https://blog.michaelsam94.com/websocket-architecture-at-scale/) directly from the middleware. Caching real-time state is how you get the "app says Available, charger says Charging" bug. Static charger metadata — name, connector type, location — cached aggressively because it changed once a quarter.

## Invalidation on writes

When TTL-based staleness isn't acceptable, invalidate on write:

```python
def update_charger_status(charger_id: str, status: str):
    db.execute("UPDATE chargers SET status = %s WHERE id = %s", (status, charger_id))
    redis.delete(f"charger:{charger_id}")
    event_bus.publish("ChargerStatusChanged", {"chargerId": charger_id, "status": status})
```

The write path clears the cache key. The next read repopulates it. This works when:

- Writes are infrequent relative to reads.
- You can identify all cache keys affected by a write.
- Event-driven invalidation reaches all cache nodes (see below).

When writes are frequent, invalidation becomes a game of whack-a-mole. If a charger sends meter values every 10 seconds, invalidating on every write means you're barely caching at all. For high-churn data, either accept a short TTL or don't cache — push updates instead.

## Avoiding the thundering herd

The scenario: a popular cache key expires. Five hundred requests arrive simultaneously. All miss. All query Postgres. Database melts.

**Mitigations:**

**Jittered TTLs.** Don't set every key to expire at exactly 300 seconds. Add random jitter: `TTL = 300 + random(0, 30)`. Spreads expirations over a 30-second window.

**Single-flight (request coalescing).** Only one request fetches from the database on a miss; others wait for the result:

```python
import asyncio

_inflight: dict[str, asyncio.Future] = {}

async def get_charger_cached(charger_id: str) -> Charger:
    cache_key = f"charger:{charger_id}"

    cached = await redis.get(cache_key)
    if cached:
        return Charger.from_json(cached)

    if cache_key in _inflight:
        return await _inflight[cache_key]

    future = asyncio.get_event_loop().create_future()
    _inflight[cache_key] = future
    try:
        charger = await db.fetch_charger(charger_id)
        await redis.setex(cache_key, 300 + random.randint(0, 30), charger.to_json())
        future.set_result(charger)
        return charger
    finally:
        del _inflight[cache_key]
```

**Stale-while-revalidate.** Return the stale value immediately while one background request refreshes the cache. The client gets data instantly (possibly a few seconds old); the database gets one query, not five hundred.

## Cache key design

Bad keys cause phantom misses and impossible invalidation:

```
# Bad: no version, no namespace
redis.set("42", data)

# Good: namespaced, versioned
redis.set("v2:charger:42", data)
redis.set("v1:user:9:profile", data)
```

Rules:

- **Namespace by entity type** — `charger:`, `session:`, `tariff:`.
- **Version prefix** — when the cached shape changes, bump the version. Old keys expire via TTL; no mass invalidation needed.
- **Avoid unbounded key cardinality** — caching per-user-per-page-per-filter combinations explodes memory. Cache the underlying data; assemble the response in the app.

## Multi-layer caching

Production systems usually stack two or three layers:

```
Client (HTTP cache / local state)
  ↓ miss
CDN / Edge (static assets, public GET endpoints)
  ↓ miss
Application cache (Redis / Memcached)
  ↓ miss
Database (Postgres)
```

Each layer has different TTL and invalidation semantics. CDN caches `GET /api/v1/tariffs` for 5 minutes with `Cache-Control: public, max-age=300`. Redis caches the database query for 60 seconds. The Flutter app holds the last-known state in memory via Riverpod and updates via WebSocket push.

Don't cache the same data at every layer with the same TTL — you'll serve stale data at every level simultaneously. Higher layers get longer TTLs for stable data; lower layers get shorter TTLs or event-driven invalidation.

## When caching is the wrong tool

- **Real-time state that must be exact** — charger status, active session state, payment confirmation. Push, don't cache.
- **Data that's unique per request** — search results with 100 parameter combinations. Cache hit rate will be near zero.
- **Write-heavy workloads** — if you're invalidating more often than you're hitting, the cache adds latency without benefit.
- **Strong consistency requirements** — if "read your own writes" matters (user updates profile, immediately sees old name), cache-aside with TTL will fail until invalidation catches up.

For the charging platform, the rule was simple: if the data changes because of something a charger or user *just did*, it goes through WebSocket. If it changes because an admin edited a config last Tuesday, it goes in Redis with a long TTL.

## Resources

- [AWS — Caching Best Practices](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/BestPractices.html)
- [Redis documentation — Cache-aside pattern](https://redis.io/docs/latest/develop/use/patterns/cache-aside/)
- [Martin Fowler — Patterns of Enterprise Application Architecture (Cache patterns)](https://martinfowler.com/eaaCatalog/)
- [Google SRE Book — Addressing Cascading Failures](https://sre.google/sre-book/addressing-cascading-failures/)
- [Cloudflare — Cache stampede prevention](https://blog.cloudflare.com/cache-stampede-mitigation/)
- [Phil Karlton — There are only two hard things in CS (cache invalidation)](https://martinfowler.com/bliki/TwoHardThings.html)
