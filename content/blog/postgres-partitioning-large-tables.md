---
title: "Partitioning Large Postgres Tables"
slug: "postgres-partitioning-large-tables"
description: "Partition large PostgreSQL tables by range, list, or hash: declarative partitioning, partition pruning, maintenance, and migration strategies without downtime."
datePublished: "2026-03-26"
dateModified: "2026-03-26"
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

## Common production mistakes

Teams get partitioning large tables wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Postgres work on partitioning large tables causes outages when migrations run without `lock_timeout`, connection pools are sized for app servers not PgBouncer modes, and `EXPLAIN` plans from staging are assumed to match production statistics.

## Debugging and triage workflow

When partitioning large tables misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [PostgreSQL table partitioning documentation](https://www.postgresql.org/docs/current/ddl-partitioning.html)
- [pg_partman extension](https://github.com/pgpartman/pg_partman)
- [PostgreSQL partition pruning](https://www.postgresql.org/docs/current/ddl-partitioning.html#DDL-PARTITIONING-PRUNING)
- [Citus data partitioning guide](https://www.citusdata.com/blog/2023/03/17/partitioning-in-postgres/)
- [PostgreSQL BRIN on partitioned tables](https://www.postgresql.org/docs/current/brin.html)
