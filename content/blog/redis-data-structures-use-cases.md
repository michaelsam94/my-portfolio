---
title: "Choosing the Right Redis Data Structure"
slug: "redis-data-structures-use-cases"
description: "A practical guide to Redis data structures: when to use strings, hashes, lists, sets, sorted sets, streams, and HyperLogLog — with real use cases and anti-patterns."
datePublished: "2026-01-14"
dateModified: "2026-01-14"
tags: ["Backend", "Redis", "Databases", "Architecture"]
keywords: "Redis data structures, Redis strings hashes sets, sorted sets leaderboard, Redis streams, HyperLogLog, choose Redis type"
faq:
  - q: "When should I use a Redis hash instead of a string?"
    a: "Use a hash when you store an object with multiple fields that you read or update independently — user profiles, session metadata, product attributes. Hashes let you HGET/HSET single fields without deserializing the whole object. Use a string when the value is atomic (a counter, a serialized blob you always read whole, or a simple flag)."
  - q: "What are sorted sets best for?"
    a: "Sorted sets (ZSET) store unique members with a numeric score, ordered by score. They power leaderboards, priority queues, rate-limit windows keyed by timestamp, and geospatial indexes (via GEO commands, which are implemented on sorted sets). Range queries by score are O(log N + M)."
  - q: "Should I use Redis Lists or Streams for a job queue?"
    a: "Lists (LPUSH/BRPOP) give a simple FIFO queue with blocking pop — fine for basic worker queues with at-most-once delivery if you accept losing a job when a worker crashes mid-process. Streams add persistence, consumer groups, acknowledgment, and replay — choose Streams when you need at-least-once processing and visibility into pending jobs."
---

Redis is not a key-value store with extras — it is a toolbox of specialized data structures, each with different time complexity and memory layout. Pick wrong and you either waste memory storing JSON strings you parse on every access, or you fight the API trying to simulate a leaderboard with a List. The documentation lists commands; production asks which structure matches your access pattern.

## Strings — counters, flags, and simple cache

The default. Use for:

- **Atomic counters** — `INCR page:views:2026-01-14`
- **SET with TTL** — session tokens, OTP codes
- **Bitmaps** — daily active user flags via `SETBIT`
- **Small serialized blobs** you always read/write whole

```redis
SET session:abc123 "{\"userId\":42}" EX 3600
INCR rate:api:user:42:202601141030
```

Anti-pattern: storing a 50-field user object as one JSON string when you only need `displayName` on most reads — use a hash.

## Hashes — field-level objects

```redis
HSET user:42 name "Ada" email "ada@example.com" plan "pro"
HGET user:42 name
```

Memory-efficient for small objects (Redis encodes small hashes compactly). Ideal for entities updated field-by-field. For very large objects (hundreds of fields), consider whether Postgres is the better home.

## Sets — uniqueness and membership

Unordered unique members. O(1) membership test.

- **Tag systems** — `SADD article:99:tags "redis" "database"`
- **Social graphs** — followers as sets, mutual friends via `SINTER`
- **Dedup** — `SADD processed:events event-id` before handling

```redis
SISMEMBER blocked:users user-7   # instant block check
SINTER user:1:followers user:2:followers  # mutual
```

## Sorted sets — rank and time ordering

Member + score ordering. The structure people underuse until they need a leaderboard.

```redis
ZADD leaderboard:2026 18950 "user:42" 15200 "user:7"
ZREVRANGE leaderboard:2026 0 9 WITHSCORES   # top 10
ZRANK leaderboard:2026 "user:42"             # my rank
```

Scores can be timestamps for time-windowed rankings (update scores on activity, prune old members periodically). Also used internally for **sliding window rate limits** — add request timestamp as score, `ZREMRANGEBYSCORE` to drop outside window, `ZCARD` for count.

## Lists — queues and recent items

Doubly linked lists. O(1) push/pop at ends.

- **Simple job queue** — `LPUSH jobs`, workers `BRPOP jobs`
- **Recent N items** — `LPUSH`, `LTRIM 0 99`

No ack/replay. Worker crash after pop = lost job. For durable processing, use Streams.

## Streams — durable event log

Append-only log with consumer groups. Covered in depth elsewhere, but on the decision tree: if you need replay, pending lists, or horizontal consumer scaling, Streams beat Lists.

```redis
XADD orders * type "created" id "ord-991"
XREADGROUP GROUP fulfillers consumer-1 COUNT 10 STREAMS orders >
```

## HyperLogLog and Bloom filters — approximate counts

**HyperLogLog** (`PFADD`, `PFCOUNT`) — approximate unique counts in ~12KB with ~0.81% error. Perfect for "how many unique visitors today" when exact count is unnecessary.

**Bloom filters** (RedisBloom module) — membership with false positives, no false negatives. "Probably seen this URL before" dedup at ingest.

Do not use either when exact counts matter for billing or inventory.

## Geospatial — sorted sets in disguise

`GEOADD`, `GEORADIUS` store lat/lon on sorted set infrastructure. Fine for store locators and driver proximity at moderate scale. At massive geo query volume, dedicated engines (PostGIS, Elasticsearch geo) may win.

## Decision flowchart (text)

```
Need field-level updates?     → Hash
Need ranking by numeric score? → Sorted Set
Need unique membership?       → Set
Need FIFO queue, loss OK?     → List
Need durable queue/events?    → Stream
Need exact counter?           → String + INCR
Need approximate cardinality? → HyperLogLog
```

## Memory and key design

Structure choice affects memory more than most teams expect. Prefix keys consistently (`user:42`, not `user_42`). Set sensible TTLs. Monitor **eviction** — if `maxmemory-policy` is `allkeys-lru`, your Streams may evict under pressure. Choose `volatile-lru` with TTL on cache keys only, or size Redis appropriately.

When a single structure does not fit, combine them. Store user profile fields in a hash, track online status in a set, and queue notifications in a stream — three structures, one user, each optimized for its access pattern.

## Structure selection guide

| Structure | Use case |
|-----------|----------|
| String | Cache, counters, rate limits |
| Hash | Object fields, session data |
| Sorted set | Leaderboards, priority queues |
| Stream | Event log, consumer groups |
| HyperLogLog | Unique visitor count (approx) |

Don't store large JSON blobs in Hash — use String with compression for documents > 1KB.

## Common production mistakes

Teams get data structures use cases wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Redis usage for data structures use cases loses data when persistence mode is misunderstood, hot keys saturate single shards, and TTL strategy is applied after memory pressure already triggered evictions.

## Debugging and triage workflow

When data structures use cases misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Redis data types overview](https://redis.io/docs/latest/develop/data-types/)
- [Sorted set internals (redis.io)](https://redis.io/docs/latest/develop/data-types/sorted-sets/)
- [Redis memory optimization](https://redis.io/docs/latest/develop/use/optimization/memory-optimization/)
- [HyperLogLog documentation](https://redis.io/docs/latest/develop/data-types/probabilistic/hyperloglogs/)
- [Redis Streams introduction](https://redis.io/docs/latest/develop/data-types/streams/)
