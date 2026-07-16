---
title: "System Design: Distributed Cache"
slug: "system-design-distributed-cache"
description: "Design a distributed caching layer with consistent hashing, cache-aside patterns, eviction policies, and cache stampede prevention for high-throughput backend systems."
datePublished: "2025-10-13"
dateModified: "2025-10-13"
tags: ["System Design", "Caching", "Architecture", "Backend"]
keywords: "distributed cache design, consistent hashing, cache-aside pattern, Redis cluster, cache stampede, LRU eviction, memcached vs Redis"
faq:
  - q: "When should I use a distributed cache vs a local in-process cache?"
    a: "Use a distributed cache (Redis, Memcached) when multiple application instances need to share cached data — session state, rate limit counters, feature flags. Use in-process caches (Caffeine, Guava) for read-heavy, instance-local data where stale reads across instances are acceptable — parsed configs, compiled regex, static lookup tables. Many systems use both: local L1 cache in front of distributed L2."
  - q: "How do I prevent cache stampede on hot keys?"
    a: "Cache stampede happens when a popular key expires and hundreds of concurrent requests all miss cache and hit the database simultaneously. Mitigations: probabilistic early expiration (refresh before TTL), request coalescing (only one request rebuilds, others wait), locking with a short mutex per key, or never expiring hot keys — update them proactively via write-through. For extremely hot keys, consider local caching with short TTL as a buffer."
  - q: "What eviction policy should I use?"
    a: "LRU (Least Recently Used) is the default and works well for most workloads — recently accessed items stay cached. LFU (Least Frequently Used) is better when access patterns have heavy tail popularity (a few keys accessed thousands of times, many keys accessed once). Redis supports both via maxmemory-policy settings. Monitor hit rate and memory usage to tune — aim for 90%+ hit rate on cached endpoints."
---

The product page for our best-selling item received 50,000 requests per minute. PostgreSQL handled it fine at 500 RPM. At 50,000, query latency went from 12ms to 800ms and connection pools exhausted. Adding Redis as a cache-aside layer dropped p99 latency back to 4ms and database load by 95%. The product data hadn't changed — we were just re-reading the same row 50,000 times per minute.

A distributed cache sits between your application and your database, storing frequently accessed data in memory across a cluster of cache nodes. Getting the design right means choosing the right caching pattern, partitioning data across nodes, handling failures gracefully, and preventing the thundering herd when hot keys expire.

## Cache-aside (lazy loading)

The most common pattern — application manages cache explicitly:

```python
async def get_product(product_id: str) -> Product:
    cache_key = f"product:{product_id}"

    cached = await redis.get(cache_key)
    if cached:
        return Product.parse(cached)

    product = await db.fetch_product(product_id)
    if product:
        await redis.setex(cache_key, ttl=3600, value=product.serialize())
    return product
```

On cache miss, read from database, populate cache, return. On write, update database and invalidate (or update) cache:

```python
async def update_product(product_id: str, data: dict):
    await db.update_product(product_id, data)
    await redis.delete(f"product:{product_id}")
```

Cache-aside gives the application full control over what's cached and when. The downside: cache and DB can temporarily diverge if invalidation fails.

## Consistent hashing for distribution

With multiple cache nodes, you need to partition keys across them. Simple modulo hashing (`hash(key) % N`) breaks when nodes are added or removed — most keys remap to different nodes, causing a mass cache miss event.

Consistent hashing maps keys and nodes to a ring. Each key belongs to the next node clockwise on the ring. Adding or removing a node only affects keys on its immediate arc:

```
         Node A
        /        \
   Key1          Key3
      |              |
   Node C -------- Node B
              Key2
```

Redis Cluster and Memcached clients implement consistent hashing with virtual nodes (each physical node maps to multiple points on the ring) for better balance.

When a node fails, its keys redistribute to the next node — some cache misses occur, but the majority of keys remain on their original nodes.

## Eviction and TTL strategy

Caches have finite memory. Eviction policies decide what to remove:

| Policy | Behavior | Best for |
|--------|----------|----------|
| LRU | Evict least recently accessed | General purpose |
| LFU | Evict least frequently accessed | Heavy-tail popularity |
| TTL | Expire after fixed time | Data with known freshness needs |
| Random | Evict random key | Simple, surprisingly effective |

Combine TTL with eviction: set TTL based on data freshness requirements, and let LRU handle memory pressure for keys that haven't expired yet.

```python
# Tiered TTL based on data volatility
TTL_CONFIG = {
    "product": 3600,       # 1 hour — changes infrequently
    "inventory": 60,       # 1 minute — changes often
    "user_session": 1800,  # 30 minutes
    "search_results": 300, # 5 minutes
}
```

## Preventing cache stampede

When a hot key expires, every concurrent request misses cache and hits the database:

```python
import asyncio

_locks: dict[str, asyncio.Lock] = {}

async def get_product_with_lock(product_id: str) -> Product:
    cache_key = f"product:{product_id}"

    cached = await redis.get(cache_key)
    if cached:
        return Product.parse(cached)

    if cache_key not in _locks:
        _locks[cache_key] = asyncio.Lock()

    async with _locks[cache_key]:
        # Double-check after acquiring lock
        cached = await redis.get(cache_key)
        if cached:
            return Product.parse(cached)

        product = await db.fetch_product(product_id)
        await redis.setex(cache_key, 3600, product.serialize())
        return product
```

Only one request rebuilds the cache entry; others wait and read the freshly populated value. For extremely hot keys, add a local in-process cache (1-5 second TTL) as an L1 buffer.

**Probabilistic early expiration:** Refresh cache entries before they expire with probability increasing as TTL approaches zero. This spreads rebuild load over time instead of a single expiry spike.

## Write-through and write-behind

Alternative patterns for write-heavy workloads:

**Write-through:** Update cache and database synchronously on every write. Cache is always fresh but writes are slower.

**Write-behind:** Update cache immediately, batch database writes asynchronously. Faster writes but risk of data loss if cache node fails before DB flush.

Most read-heavy systems stick with cache-aside because it's simpler and the application already handles DB reads.

## Redis Cluster vs Memcached

| Feature | Redis Cluster | Memcached |
|---------|--------------|-----------|
| Data structures | Strings, hashes, lists, sets, sorted sets | Strings only |
| Persistence | Optional (RDB, AOF) | None (pure cache) |
| Replication | Built-in | None (client-side sharding) |
| Pub/Sub | Yes | No |
| Memory efficiency | Higher overhead per key | Lower overhead |
| Best for | Shared state, complex data, pub/sub | Simple key-value caching |

Choose Redis when you need data structures beyond strings, persistence for warm restarts, or pub/sub. Choose Memcached for pure caching with maximum memory efficiency and simplicity.

## Monitoring cache health

Track these metrics:

- **Hit rate:** `hits / (hits + misses)` — target 90%+ for cached endpoints.
- **Memory usage:** Per-node memory and eviction rate.
- **Latency:** p50/p99 for cache operations — should be sub-millisecond.
- **Hot keys:** Identify keys with disproportionate access — may need dedicated handling.
- **Connection count:** Monitor client connections per node.

Alert on hit rate drops below threshold — often indicates invalidation bugs, TTL misconfiguration, or capacity issues.

## Common production mistakes

Teams get distributed cache wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

System design for distributed cache breaks at scale when hot keys, thundering herds, and cache stampedes are discovered during launch week instead of load test week.

## Resources

- [Redis Cluster specification](https://redis.io/docs/reference/cluster-spec/)
- [Consistent hashing explained — Martin Kleppmann](https://www.toptal.com/big-data/consistent-hashing)
- [Cache-aside pattern — AWS Architecture Blog](https://docs.aws.amazon.com/whitepapers/latest/database-caching-on-aws/cache-aside.html)
- [Facebook Memcached paper](https://www.usenix.org/conference/nsdi-13/proceedings/presentation/nishtala)
- [Google Guava CacheBuilder (local cache reference)](https://github.com/google/guava/wiki/CachesExplained)
