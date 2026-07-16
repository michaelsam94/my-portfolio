---
title: "A Layered Caching Strategy"
slug: "performance-caching-layers-strategy"
description: "Design a multi-layer cache: browser, CDN, application, and database caching with TTL policies, invalidation patterns, and stampede prevention."
datePublished: "2026-02-06"
dateModified: "2026-02-06"
tags: ["Performance", "Caching", "Architecture", "Backend"]
keywords: "layered caching strategy, CDN cache, Redis application cache, cache invalidation, cache stampede prevention"
faq:
  - q: "What are the main cache layers in a web application?"
    a: "Browser cache (Cache-Control headers), CDN/edge cache (static assets and cacheable API responses), application cache (Redis/Memcached for computed data), and database cache (query result cache, materialized views, buffer pool). Each layer has different TTL granularity and invalidation complexity."
  - q: "How do you prevent cache stampede on hot keys?"
    a: "Use request coalescing (single-flight lock), stale-while-revalidate, probabilistic early expiration, or pre-warming on deploy. When a popular cache key expires, hundreds of concurrent requests shouldn't all hit the database."
  - q: "When should you not cache?"
    a: "Personalized data with strict freshness requirements, financial balances, auth/session state, and anything where stale reads cause user-visible errors or compliance violations. Cache the stable parts and compose personalized overlays at request time."
---

The product page loaded in 200ms in staging and 4.2 seconds in prod. Staging had 50 products and no CDN. Prod had 50,000 SKUs, a Postgres query joining six tables, and a "temporary" Redis layer someone added without TTLs until memory alarms fired. Fixing it wasn't one cache — it was deciding what belongs at each layer and what invalidates when a merchant updates inventory.

## The cache hierarchy

```
Browser ──► CDN ──► App (Redis) ──► DB (buffer pool / mat views)
  │          │           │                    │
 ~0ms      ~10ms        ~1ms                 ~10–100ms
```

Each layer trades freshness for latency. Push caching down as far as correctness allows.

## Layer 1: Browser and CDN

Static assets — JS, CSS, fonts, product images — get immutable cache keys:

```
Cache-Control: public, max-age=31536000, immutable
```

Filename hashing (`app.a3f2b1.js`) lets you cache forever. HTML gets short TTL or `no-cache` with ETag validation.

CDN cache rules for semi-static API responses:

```
# Product catalog by category — cache 5 min at edge
Cache-Control: public, s-maxage=300, stale-while-revalidate=60
Vary: Accept-Encoding
```

`s-maxage` applies to shared caches (CDN); `max-age` to browser. `stale-while-revalidate` serves stale content while refreshing in background — cuts latency spikes on expiry.

Invalidate CDN on publish events (webhook to CloudFront/Fastly), not arbitrary TTL guessing.

## Layer 2: Application cache (Redis)

Cache expensive aggregations, session-adjacent data, and permission lookups:

```python
def get_category_products(category_id: str) -> list[Product]:
    key = f"cat:{category_id}:products:v3"
    cached = redis.get(key)
    if cached:
        return json.loads(cached)

    products = db.query_products_by_category(category_id)  # slow join
    redis.setex(key, 300, json.dumps(products, default=str))
    return products
```

Version keys (`:v3`) — bump version on schema change instead of scanning `KEYS *` to delete.

**Cache-aside (lazy loading):** app reads cache, on miss loads DB, writes cache. Simple, but stampede-prone.

**Write-through:** update cache on DB write. Higher write latency, consistent reads.

**Write-behind:** queue cache updates async. Fast writes, brief inconsistency window.

We default to cache-aside with single-flight for hot keys:

```python
def get_with_singleflight(key: str, loader: Callable) -> Any:
    if val := redis.get(key):
        return val
    with redis.lock(f"lock:{key}", timeout=5):
        if val := redis.get(key):  # double-check
            return val
        val = loader()
        redis.setex(key, 300, serialize(val))
        return val
```

Only one request rebuilds; others wait on the lock or retry get.

## Layer 3: Database-level caching

Postgres buffer pool caches pages automatically — no app code needed. Help it with proper indexes so hot pages stay warm.

Materialized views for dashboards:

```sql
CREATE MATERIALIZED VIEW daily_revenue AS
SELECT date_trunc('day', created_at) AS day, SUM(amount) AS revenue
FROM orders GROUP BY 1;

-- Refresh on schedule, not on every read
REFRESH MATERIALIZED VIEW CONCURRENTLY daily_revenue;
```

Query result cache (MySQL query cache removed in 8.0; don't rely on it) — prefer explicit app cache with clear invalidation.

## Invalidation strategies

The hard part. Patterns:

**TTL-only.** Accept staleness up to N seconds. Fine for catalog, weather, analytics.

**Event-driven.** Product update → publish `product.updated` → consumer deletes `product:{id}` and `cat:*` keys. Precise but requires reliable event bus.

**Tag-based invalidation.** Store key sets under tags (`tag:category:shoes` → list of keys). Invalidate all keys for a tag on category change. Redis doesn't natively support this — use RedisGears, custom sets, or Memcached with tag emulation.

Document invalidation in the same PR as the write path. Caches without invalidation plans become wrong silently.

## What we cache vs not

| Data | Layer | TTL | Invalidation |
|------|-------|-----|--------------|
| Product detail | Redis + CDN | 5 min | Event on update |
| User cart | None (Redis session only) | Session | N/A |
| Search results | Redis | 60 sec | TTL |
| Static assets | CDN | 1 year | Filename hash |
| Auth tokens | None | — | — |

Never cache per-user financial balances without explicit product approval for staleness.

## Observability

Track hit rate, miss latency, eviction rate, and memory usage per cache namespace. Alert when hit rate drops suddenly — often means key versioning bug or invalidation storm.

Compare p99 API latency with cache bypass header in synthetic checks to measure cache benefit.

## Cache stampede at scale

Beyond single-flight, consider probabilistic early expiration — each request has small chance to refresh cache before TTL expires, spreading recomputation over time. Libraries like Bloom filters help detect hot keys proactively.

For CDN cache poisoning concerns, validate `Vary` headers and cache key includes only intended dimensions. Authenticated pages usually should not be CDN-cached unless segmented by session token in cache key — usually not worth it.

## Common production mistakes

Teams get caching layers strategy wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Performance work on caching layers strategy regresses when optimizations target p50 only, benchmarks run on laptops not production hardware, and flamegraphs are captured once then never compared after refactors.

## Debugging and triage workflow

When caching layers strategy misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [RFC 9111 — HTTP Caching](https://www.rfc-editor.org/rfc/rfc9111.html)
- [Redis caching best practices](https://redis.io/docs/manual/patterns/)
- [CloudFront cache behaviors](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Expiration.html)
- [Facebook memcache paper (scaling cache)](https://www.usenix.org/conference/nsdi13/technical-sessions/presentation/nishtala)
- [AWS ElastiCache best practices](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/BestPractices.html)
