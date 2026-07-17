---
title: "Partitioning Large Postgres Tables"
slug: "postgres-partitioning-large-tables"
description: "Partition large PostgreSQL tables by range, list, or hash: declarative partitioning, partition pruning, maintenance, and migration strategies without downtime."
datePublished: "2026-03-26"
dateModified: "2026-07-17"
tags: ["PostgreSQL", "Backend", "Database", "Performance"]
keywords: "PostgreSQL table partitioning, declarative partitioning, partition pruning, range partition Postgres, partition large table"
faq:
  - q: "When should you partition a Postgres table?"
    a: "When a single table exceeds manageable size for vacuum, index rebuilds, and backups — often 50–100 GB+ depending on SLA — and queries consistently filter on the partition key (date, tenant region, status). Partitioning without prune-friendly queries adds complexity without benefit."
  - q: "What is the difference between range and list partitioning?"
    a: "Range partitions split on intervals — dates, numeric ranges. List partitions split on explicit values — country codes, tenant tiers. Hash partitioning spreads rows evenly when no natural range exists but maintenance benefits are limited."
  - q: "Can you add partitions without locking the table?"
    a: "CREATE TABLE ... PARTITION OF attaches a new partition with minimal lock on Postgres 11+. Dropping old partitions (DROP TABLE partition_name) is instant compared to DELETE millions of rows. Plan partition boundaries ahead to avoid runtime CREATE during peak."
---

The `events` table hit 180 GB. Vacuum ran six hours. Index rebuild required a maintenance window. Queries filtered by `created_at` last 7 days but Postgres scanned indexes built for all time. Declarative partitioning by month cut typical query time 40× and let us drop September data with `DROP TABLE events_2025_09` instead of `DELETE` that locked the table for hours.

## Declarative partitioning (Postgres 10+)

```sql
CREATE TABLE events (
  id BIGSERIAL,
  created_at TIMESTAMPTZ NOT NULL,
  user_id UUID NOT NULL,
  payload JSONB
) PARTITION BY RANGE (created_at);

CREATE TABLE events_2026_03 PARTITION OF events
  FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');

CREATE TABLE events_2026_04 PARTITION OF events
  FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
```

Inserts route automatically by `created_at`. Parent table holds schema; data lives in partitions.

## Partition key selection

Must appear in WHERE for **partition pruning**:

```sql
EXPLAIN SELECT * FROM events WHERE created_at >= '2026-03-15';
-- Append -> Seq Scan on events_2026_03 only
```

Without partition key in query — scans all partitions (defeats purpose).

**Range (time-series):** monthly or weekly partitions for logs, events, metrics.

**List (multi-tenant):** 
```sql
PARTITION BY LIST (region)
-- partitions: us, eu, apac
```

**Hash:**
```sql
PARTITION BY HASH (user_id);
-- 8 partitions for even spread — rarely pruned, helps parallel vacuum/maintenance
```

## Indexes on partitioned tables

Create index on parent — propagates to all partitions:

```sql
CREATE INDEX ON events (user_id, created_at);
```

Each partition gets own index — smaller, faster to rebuild per partition.

Unique constraints require partition key inclusion:

```sql
UNIQUE (id, created_at)  -- OK
UNIQUE (id)              -- ERROR unless id globally unique with constraint on each partition
```

Use `BIGSERIAL` per partition carefully — global uniqueness needs UUID or composite.

## Maintenance wins

**Retention:**
```sql
DROP TABLE events_2025_01;  -- instant vs DELETE millions of rows
```

**Vacuum:** autovacuum per partition — recent hot partition vacuums frequently; old partitions frozen.

**Archival:** detach partition, move to cheap storage:

```sql
ALTER TABLE events DETACH PARTITION events_2024_01;
-- export, attach to archive DB
```

## Creating future partitions

Automate with pg_partman extension or cron job:

```sql
SELECT partman.create_parent(
  p_parent_table => 'public.events',
  p_control => 'created_at',
  p_type => 'native',
  p_interval => 'monthly'
);
```

Alert if next month's partition missing — INSERT fails hard if no matching partition.

## Migration from non-partitioned table

Low-downtime approach:

1. Create partitioned table `events_new` with partitions
2. Copy data in batches or logical replication
3. Rename swap in maintenance window:

```sql
BEGIN;
ALTER TABLE events RENAME TO events_old;
ALTER TABLE events_new RENAME TO events;
COMMIT;
```

Or use `pg_rewrite` / dual-write period for stricter SLAs.

Test query plans on staging — ORMs may need partition key hints in queries.

## Common mistakes

- Partitioning by day when queries ask for months — too many partitions (metadata overhead)
- No default partition — inserts fail on boundary gaps; `DEFAULT` partition catches overflow (Postgres 11+)
- Forgetting partition key in ORM scopes — ORM generates full table scan across all children
- Updating partition key column — row must move between partitions (DELETE+INSERT cost)

## Query planner and partitionwise operations

Postgres 11+ partitionwise joins and aggregates help when querying across few partitions — verify `enable_partitionwise_join` and `enable_partitionwise_aggregate` settings. For many partitions, default may still choose suboptimal plans — test EXPLAIN on representative queries.

## Operational notes

Automated partition creation should alert if run fails — missing next month partition causes production INSERT failures at midnight on the first, a classic cron oversight incident.

Include partition key in primary key or unique constraints where global uniqueness required — planner pruning and constraint enforcement both depend on consistent key design.

Test ORM-generated SQL against partitioned parent table in staging — some ORMs generate INSERT without partition key when defaults exist, routing rows to DEFAULT partition and hiding data from expected partition scans.

Document partition attachment procedure in runbook for on-call — midnight INSERT failures from missing partition are fixed in minutes when runbook exists, hours when it does not.

When attaching DEFAULT partition catches overflow rows, monitor its size weekly — a growing DEFAULT partition signals boundary planning drift or application inserts missing partition key values.

## Declarative partitioning

```sql
CREATE TABLE events (
  id BIGSERIAL,
  created_at TIMESTAMPTZ NOT NULL,
  payload JSONB
) PARTITION BY RANGE (created_at);

CREATE TABLE events_2026_01 PARTITION OF events
  FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
```

Partition pruning requires `created_at` in WHERE clause. Drop old partitions instead of DELETE for retention.


## Range vs list vs hash

Time-series events use RANGE on created_at. Multi-tenant isolation use LIST on tenant_id or HASH when evenly distributed. Wrong strategy — cross-partition scans negate benefit.

## Partition pruning verification

EXPLAIN must show Append with subset of partitions — if all partitions scanned, predicate not aligned to partition key or wrong types.

## DEFAULT partition trap

Catch-all DEFAULT partition receives orphan rows — becomes largest over time. Alert when DEFAULT over 5% of total.

## Detach for archival

DETACH PARTITION CONCURRENTLY moves old month to archive without long ACCESS EXCLUSIVE lock. Export to Parquet before drop.

## Automatic partition creation

pg_partman extension creates future monthly partitions — cron maintenance prevents INSERT failure when March arrives and February was last created partition. Without automation, on-call gets paged at midnight UTC on month boundary.

## Foreign key across partitions

Postgres 12+ FK referencing partitioned table supported — verify ON DELETE behavior propagates to all partitions. Legacy design with trigger-maintained child tables may differ — document during migration from manual to declarative partitioning.

## Partition-wise join

PG14+ partition-wise join when two partitioned tables share partition key — join per partition parallelizable. Requires compatible partition bounds — planning benefit lost if one table monthly other daily.

## Global indexes unavailable

Unique constraint must include partition key — no global unique on email alone unless email included in partition key or use unique index on non-partitioned lookup table. Architectural constraint drives email uniqueness table separate from events partition.

## ATTACH PARTITION workflow

CREATE TABLE events_2026_07 PARTITION OF events FOR VALUES FROM ('2026-07-01') TO ('2026-08-01') — pre-create next month partition automated; INSERT failure on first day of month if forgotten is classic ops incident preventable by pg_partman cron.

## Constraint exclusion constraint

CHECK constraint on parent enforcing partition key range matches child bounds — mistake in ATTACH PARTITION caught at attach time not at silent wrong-partition insert. Script automated attach validates bounds against pg_get_partition_constraintdef output.

## Closing notes

Archive detached partitions to S3 via COPY before DROP — compliance retention requires provable export even when partition dropped from primary; lifecycle policy moves cold parquet to glacier.

## Additional guidance

Query planner partition pruning requires explicit partition key in WHERE — ORM lazy query without date filter scans all partitions silently. Add linter on SQL strings in repository layer flagging SELECT on partitioned table missing partition key predicate in code review checklist for data access PRs.

Foreign keys referencing partitioned parent supported PG12+ — migration from non-partitioned to partitioned requires careful FK recreation script tested on staging clone with production FK graph complexity including circular references between orders and shipments tables common in ecommerce schemas.

Automate next-month partition creation with pg_partman — manual CREATE PARTITION forgotten before month boundary causes production INSERT failures.

Include partition key in every ORM default scope — linter flags repository methods querying partitioned events table without created_at predicate preventing accidental full partition scan.

Detach old monthly partitions to cold tablespace before DROP — compliance archive COPY to S3 completes while detached partition still queryable read-only for finance audit window without impacting primary INSERT throughput on current month partition.

## Resources

- [PostgreSQL table partitioning documentation](https://www.postgresql.org/docs/current/ddl-partitioning.html)
- [pg_partman extension](https://github.com/pgpartman/pg_partman)
- [PostgreSQL partition pruning](https://www.postgresql.org/docs/current/ddl-partitioning.html#DDL-PARTITIONING-PRUNING)
- [Citus data partitioning guide](https://www.citusdata.com/blog/2023/03/17/partitioning-in-postgres/)
- [PostgreSQL BRIN on partitioned tables](https://www.postgresql.org/docs/current/brin.html)
