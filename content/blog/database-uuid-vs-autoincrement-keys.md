---
title: "UUIDs vs Auto-Increment Keys"
slug: "database-uuid-vs-autoincrement-keys"
description: "UUIDs enable distributed ID generation; auto-increment integers are compact and index-friendly. Tradeoffs for primary keys, B-tree fragmentation, and public exposure."
datePublished: "2025-09-18"
dateModified: "2025-09-18"
tags: ["Backend", "Databases", "Architecture"]
keywords: "UUID primary key, auto increment, serial ID, UUIDv7, distributed ID generation, index fragmentation"
faq:
  - q: "When should I use UUIDs as primary keys?"
    a: "Use UUIDs when IDs must be generated offline or across distributed services without a central allocator, when exposing IDs publicly without enumerable guessing, or when merging databases without ID collision. Prefer time-ordered UUIDv7 over random UUIDv4 for better B-tree locality."
  - q: "What are the downsides of UUID primary keys?"
    a: "Random UUIDs cause B-tree index fragmentation and larger indexes compared to sequential integers — inserts hit random pages. Storage overhead is 16 bytes vs 4–8 for bigint. Join and cache performance may suffer at extreme scale unless using sequential UUID variants."
  - q: "Are auto-increment keys bad for security?"
    a: "Sequential IDs are enumerable — /orders/1001 reveals volume and enables scraping neighbors. Never rely on obscurity alone, but public APIs often use opaque UUIDs or encoded IDs while keeping bigint internally for performance."
---

The debate repeats in every greenfield schema review: "UUIDs everywhere for microservices" versus "bigint serial because indexes matter." Both camps are half right. The choice depends on **who generates IDs**, **whether IDs are public**, and **insert volume into clustered indexes**.

## Auto-increment (serial / identity)

```sql
CREATE TABLE orders (
  id BIGSERIAL PRIMARY KEY,
  customer_id BIGINT NOT NULL,
  total_cents INT NOT NULL
);
```

**Pros:**

- Sequential inserts — excellent B-tree locality
- 8-byte keys — smaller indexes, faster joins
- Human-debuggable in logs

**Cons:**

- Single-writer sequence bottleneck (usually negligible until huge QPS)
- Collision merging databases from multiple sources
- Predictable public IDs

Sequences leak business info (`order_id` gap doesn't mean lost orders — rolled-back transactions consume IDs).

## Random UUID v4

```sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ...
);
```

**Pros:**

- Generate anywhere — mobile offline, microservice, client — no coordination
- Non-enumerable in public URLs

**Cons:**

- Random insert order — page splits, index bloat
- 16-byte keys — wider secondary indexes referencing PK

At millions of inserts/day, random UUID PK pain shows in pg_stat_user_tables and buffer cache miss rates.

## UUIDv7 — time-ordered compromise

UUIDv7 (RFC 9562) embeds timestamp in high bits — mostly sequential, still opaque:

```python
import uuid6  # or uuid7 library

order_id = uuid6.uuid7()  # sortable by creation time
```

PostgreSQL 18+ may ship native uuidv7; until then use app-generated or extension.

**Use UUIDv7** when you need distributed generation **and** index locality. Better default than v4 for PKs.

## Surrogate vs natural keys

Often best of both:

```sql
CREATE TABLE orders (
  id BIGSERIAL PRIMARY KEY,           -- internal joins
  public_id UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),  -- API exposure
  ...
);
```

API returns `public_id`; FKs use `id`. Extra column cost buys flexibility.

## Distributed ID alternatives

| Scheme | Properties |
|---|---|
| Snowflake IDs | 64-bit, time-sortable, datacenter-aware |
| ULID | Lexicographically sortable, 128-bit |
| DB sequence per shard | `shard_id << 48 \| local_seq` |
| Identity service | Central HTTP allocator — SPoF unless HA |

Twitter/X Snowflake pattern predates UUIDv7 popularity — still valid at massive scale.

## Secondary index impact

PK choice affects **all** secondary indexes in Postgres clustered index model — secondary indexes store PK values as pointers. UUID PK bloats every index.

If UUID required, consider:

- `uuid` PK with `bigint` clustering key (engine-specific)
- Periodic `REINDEX` monitoring
- Fillfactor tuning on heavily inserted tables

## Public API guidance

Don't expose sequential IDs on user-scoped resources unless authorized checks are bulletproof. UUID/ULID/signed tokens (`id=HMAC`) reduce drive-by enumeration.

Internal admin tools can use bigint for readability.

## Merge and replication

Multi-region active-active favors UUID or Snowflake — no cross-region sequence coordination. Single-region Postgres serial is simpler.

## Decision flowchart (prose)

Single monolith Postgres, IDs internal, OLTP moderate → **bigint serial**.

Microservices, offline creation, public opaque IDs → **UUIDv7** or **ULID**.

Extreme insert rate, internal only → **bigint** with segment allocation per service.

When unsure, **bigint PK + UUID public column** delays the argument without blocking ship.

## Performance benchmarks in practice

The UUID vs bigint debate often lacks numbers. Typical Postgres benchmarks on modern hardware:

| Operation | bigint serial | UUID v4 | UUID v7 |
|---|---|---|---|
| Insert rate (single table) | ~50k/s | ~15k/s | ~40k/s |
| Index size (1M rows) | ~22MB | ~85MB | ~85MB |
| Join on PK (1M × 1M) | baseline | ~2× slower | ~1.2× slower |
| Range scan by PK order | fast | random I/O | mostly sequential |

Numbers vary by hardware, fillfactor, and workload. The point: UUID v4 hurts insert-heavy OLTP; UUID v7 largely closes the gap; bigint still wins on pure performance.

Run your own benchmark with `pgbench` custom scripts before committing to UUID PKs on high-insert tables.

## Sharding and ID generation

In sharded architectures, ID generation strategy interacts with shard routing:

```python
# Shard-aware ID: embed shard ID in high bits
def generate_id(shard_id: int, local_sequence: int) -> int:
    return (shard_id << 48) | local_sequence

# Each shard has its own sequence — no cross-shard coordination
# 16-bit shard ID + 48-bit sequence = 64-bit integer
```

Compare to UUIDv7 (timestamp + random) which doesn't encode shard affinity — routing requires separate lookup. Snowflake IDs encode datacenter + worker + sequence in 64 bits.

For microservices each owning a shard, local sequences with shard prefix work well. For client-generated IDs (mobile offline), UUIDv7 is simpler.

## Migration from serial to UUID

Changing PK type on a live table is painful — expand-contract applies:

1. Add `public_id UUID DEFAULT gen_random_uuid()` column
2. Backfill existing rows
3. Deploy API returning `public_id` instead of `id`
4. Add unique index on `public_id`
5. New code uses `public_id` for lookups; keep `id` for internal joins
6. Never change the PK column itself unless you enjoy pain

Don't migrate bigint PK to UUID PK in place — add a public identifier column instead.

## Failure modes

- **UUID v4 as PK on high-insert table** — index bloat, buffer cache pressure, visible by 6 months
- **Sequential IDs in public API** — enumeration attacks; use public_id column
- **Client-generated UUID without v7** — random v4 fragments indexes; switch to v7
- **Cross-shard sequence coordination** — bottleneck at scale; use embedded shard ID or UUID
- **ORM assuming auto-increment** — Rails/Django default to serial; configure UUID generation explicitly

## Production checklist

- ID strategy documented with rationale (who generates, public exposure, insert rate)
- UUID v7 (not v4) if UUID PK required
- bigint PK + UUID public_id for dual-needs scenarios
- Public APIs never expose sequential IDs on user-scoped resources
- Index bloat monitored on UUID PK tables (pg_stat_user_tables, bloat queries)
- Shard-aware ID generation if horizontally sharded

Use UUIDv7 for time-ordered IDs when index locality matters — random UUIDv4 fragments B-tree indexes on high-insert tables.

## Resources

- [RFC 9562 — UUIDs including UUIDv7](https://www.rfc-editor.org/rfc/rfc9562.html)
- [PostgreSQL — UUID type](https://www.postgresql.org/docs/current/datatype-uuid.html)
- [Instagram engineering — Sharding IDs](https://instagram-engineering.com/sharding-ids-at-instagram-1cf5a71ae5c5)
- [UUID benchmarks (Percona)](https://www.percona.com/blog/store-uuid-optimized-way/)
- [Sonyflake — distributed ID generator](https://github.com/sony/sonyflake)
