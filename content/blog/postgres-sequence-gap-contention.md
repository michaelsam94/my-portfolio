---
title: "Postgres Sequence Gaps and Contention"
slug: "postgres-sequence-gap-contention"
description: "Understand why SERIAL gaps are normal, when sequence contention hurts throughput, and patterns for high-insert ID generation."
datePublished: "2026-03-03"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
keywords: "postgres sequences, sequence gaps, IDENTITY column, nextval contention, serial primary key"
faq:
  - q: "Are gaps in Postgres SERIAL or IDENTITY columns a bug?"
    a: "No. Sequences allocate values in blocks for performance; rolled-back transactions, crashed sessions after nextval, and CACHE settings all create gaps. Uniqueness and monotonicity for new rows are guaranteed; consecutive IDs without holes are not."
  - q: "What causes sequence contention on high-insert tables?"
    a: "Every INSERT calls nextval, which updates the sequence row in pg_catalog with row-level lock. At extreme insert rates on a single sequence, sessions queue on that lock. Mitigations include CACHE, per-partition sequences, UUID/ULID keys, or batch allocation."
  - q: "How does CACHE affect gaps and performance?"
    a: "CACHE n pre-allocates n values in session memory; crash loses unused cached values (more gaps) but reduces catalog updates. Default CACHE 1 minimizes gaps but slowest under contention. Production high-throughput often uses CACHE 50–100 accepting gap tradeoff."
  - q: "Should I switch from bigint sequences to UUIDs to fix contention?"
    a: "UUIDs remove single-sequence hot spot but widen indexes and change locality. UUIDv7 or ULID restore roughly monotonic insert order. Choose based on global uniqueness needs and index size, not only contention."
---

Support tickets about "missing" order numbers almost always mean someone expected **`SERIAL`** to behave like a paper invoice ledger: consecutive, gapless, never reused. Postgres sequences deliberately do none of that beyond **unique next value**. Understanding why gaps happen—and when the single-row **`nextval`** lock becomes a throughput ceiling—saves wrong fixes like nightly renumber scripts.

## How sequences work internally

```sql
CREATE TABLE orders (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ...
);
```

**`nextval`** is atomic: increments and returns. With **`CACHE 1`**, every **`nextval`** updates catalog row—concurrent inserters serialize on sequence lock.

## Normal gap sources (not bugs)

| Event | Gap? |
| --- | --- |
| INSERT then ROLLBACK | Yes—value consumed |
| INSERT success, row deleted | Number not reused |
| nextval then crash before INSERT | Yes |
| CACHE 50, restart after 10 used | Up to 40 lost |
| Manual setval | Jump forward |

**Numbers are not reused** after delete—that preserves referential integrity.

## Measuring sequence contention

```sql
SELECT wait_event_type, wait_event, count(*)
FROM pg_stat_activity WHERE state = 'active'
GROUP BY 1, 2 ORDER BY 3 DESC;
```

**`wait_event = 'Lock'`** on sequence relation suggests hot sequence.

```sql
ALTER SEQUENCE order_id_seq CACHE 100;
```

Throughput often improves dramatically; gaps increase—document for finance if they read sequence as invoice number.

## CACHE tuning guide

- **CACHE 1:** minimal gaps, maximum contention
- **CACHE 10–100:** sweet spot for many OLTP systems
- **Very large CACHE:** failover loses bigger blocks

## Alternatives when one sequence saturates

**Partitioned sequences:** each monthly partition has own IDENTITY—spreads locks.

**Application batch allocation:** reserve 1000 values with one nextval burst; crash loses unused range.

**UUID/ULID keys:** no sequence hot spot; 16-byte keys vs 8-byte bigint; UUIDv7 improves B-tree locality.

**Snowflake-style IDs:** application service generates 64-bit IDs; zero Postgres sequence contention.

## Display numbers vs primary keys

Best pattern: **`id bigint`** internal PK + **`order_number text`** human-facing from separate counter table per day with **`INSERT ON CONFLICT DO UPDATE`**.

## Replication and failover

After bulk import with explicit IDs:

```sql
SELECT setval(
  pg_get_serial_sequence('orders', 'id'),
  COALESCE((SELECT MAX(id) FROM orders), 1)
);
```

Automate post-promote hook on orchestration tool (Patroni callback).

Monitor sequences:

```sql
SELECT seq.relname, last_value,
       (SELECT MAX(id) FROM orders) AS max_id
FROM pg_sequences seq WHERE schemaname = 'public';
```

Alert when **`last_value + 1000 < MAX(id)`**.

## COPY and sequence behavior

**COPY** with explicit **`id`** bypasses **`nextval`**—always **`setval`** after. **COPY** without **`id`** uses default per row—same contention as inserts in one transaction.

## pgBouncer and IDENTITY

**`IDENTITY`** wraps sequences—same contention physics as **`SERIAL`**. Migration between them is cosmetic; **`CACHE`** tuning matters for both.

## Sequences vs hash sharding

Sharding by hash across databases removes single-sequence contention but adds routing complexity. Sequences remain default until profiling proves sequence lock as bottleneck at your insert rate.

## Decision matrix

| Requirement | Recommendation |
| --- | --- |
| Max insert rate, gaps OK | CACHE 50–100 |
| Minimal gaps, moderate rate | CACHE 1, accept rollback gaps |
| Human consecutive numbers | Separate display column |
| Global distributed writers | UUIDv7, ULID, or Snowflake |

Sequence gaps are a feature of performant allocation. Sequence **contention** is real—diagnose with wait events, then CACHE, partition, or redesign keys.



## Invoice numbering war stories

Finance mandates "no gaps" for invoice numbers while engineering uses **`SERIAL`**—irreconcilable without a separate **`invoice_number`** column allocated from **`daily_counters`** table under **`SERIALIZABLE`** or row lock. Never **`RESTART`** sequences nightly to "fill gaps"—breaks FK references and audit trails. Educate stakeholders with explicit list of gap sources (rollback, cache, failover) before choosing ID strategy.

## Insert-only tables and BRIN

Time-series insert-only tables rarely contend on sequences unless single **`bigserial`** feeds all partitions—use per-partition identity or time-based UUIDv7 keys when ingest exceeds 20k/sec sustained on single node benchmarks.

## pg_dump and sequence ownership

Logical restores must restore sequences with **`pg_dump --serial`** semantics or post-restore **`setval`** script—automate in restore pipeline. Cloud logical imports often forget **`setval`**, causing duplicate PK on first post-migration insert.

## Testing contention in CI

Load test with pgbench custom script inserting into single-table PK default **`nextval`**; graph **`pg_locks`** wait queue depth vs TPS elbow. Compare **`CACHE 1`** vs **`100`** on same hardware—document decision in ADR for future engineers.




## Advisory locks for human-readable counters

Daily invoice counter pattern:

```sql
SELECT pg_advisory_xact_lock(hashtext('invoice:' || current_date::text));
-- increment counter row
```

Advisory lock scopes to transaction—no orphan locks on rollback. Alternative to **`SELECT FOR UPDATE`** on counter row when single hot row contends—shard counters by **`mod(tenant_id, 16)`** for parallel allocation.

## Sequences in unlogged tables

**`UNLOGGED`** tables with serial still consume sequence—gaps on crash worse due to unlogged table truncate on recovery. Do not use unlogged for anything needing durable invoice numbers.

## Numeric overflow

**`serial`** is **`integer`**—overflow at 2^31-1 surprises decade-old apps. Prefer **`bigint`** identity from day one for public-facing IDs.




## Legal and audit narrative template

Provide stakeholders: "Postgres guarantees unique primary keys, not consecutive business numbers. Gaps indicate rollback, crash, or performance optimization (CACHE). For gapless business numbering, we allocate separate display identifiers." Paste into compliance FAQ to reduce recurring tickets.

## Parallel COPY into partitioned table identities

Each partition **`GENERATED ALWAYS AS IDENTITY`** uses separate sequence—parallel load workers into different partitions scale insert without single-sequence lock. Router must target correct partition; wrong partition insert still unique globally if IDs disjoint by sequence.

## time-based UUID keys and index bloat link

UUIDv7 monotonic reduces but does not eliminate index bloat under heavy updates to indexed non-PK columns—sequence contention and index bloat are orthogonal problems requiring separate diagnostics.




## Mini benchmark script

Use pgbench with **`\set id random(1,100000000)`** disabled—pure insert: **`INSERT INTO bench(id) VALUES (DEFAULT);`** on empty table. Compare TPS **`CACHE 1`** vs **`100`**. Archive results in repo **`docs/perf/sequences.md`** for onboarding.



## ORM and sequence pitfalls

Django auto field and SQLAlchemy sequences both map to Postgres sequences—bulk_create with explicit pk skips sequence advance; bulk_create without pk still hammers single sequence under high QPS. Rails upsert patterns may call nextval in Ruby before insert doubling round trips—prefer database DEFAULT.

## Financial audit questions answered

Auditors ask whether deleted invoice numbers reuse—answer no by design in Postgres sequences. They ask whether gaps prove fraud—answer no, gaps prove rollbacks and operational caching. Provide sample pg_catalog query showing last_value vs max id alignment after migrations.


## Monitoring sequence last_value drift

Daily cron comparing MAX(id) to last_value for all serial tables—pager when drift exceeds threshold after bulk jobs. Include fix setval script in alert runbook template parameterized by table name.




## Linked tables sharing sequence

Anti-pattern: two tables same sequence for "continuity"—contention doubles and gaps confuse both domains. Separate sequences; unify only in display layer if business requires contiguous appearance across entity types.

## pgpool-II sequence handling

Some pooler modes cache sequences at pooler layer—investigate pooler docs before tuning CACHE on Postgres alone. Misaligned pooler sequence cache causes duplicate key errors rare but severe; integration test failover with pooler in path.

## Sequence privileges

Revoke USAGE on sensitive sequences from application roles that should only INSERT via DEFAULT—prevent ad hoc nextval calls in SQL injection from burning number ranges or probing sequence values.

Treat sequence last_value alignment checks as part of post-migration smoke tests alongside row counts and extension versions.

Never reset a production sequence to close gaps; you will collide with existing IDs. Treat gap reports as education opportunities, not data corruption, unless deletes are independently proven.

## Resources

- [CREATE SEQUENCE](https://www.postgresql.org/docs/current/sql-createsequence.html)
- [Identity columns](https://www.postgresql.org/docs/current/sql-createtable.html#SQL-CREATETABLE-PARMS-GENERATED-IDENTITY)
