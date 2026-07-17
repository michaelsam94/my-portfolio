---
title: "Postgres work_mem Sort and Hash Tuning"
slug: "postgres-work-mem-sort-hash-tuning"
description: "Size work_mem for sorts and hashes without OOM — understand per-operation allocation and log_temp_files signals."
datePublished: "2026-03-12"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
keywords: "postgres work_mem, sort hash aggregate, log_temp_files, query memory tuning"
faq:
  - q: "Is work_mem a per-query or per-connection limit?"
    a: "work_mem applies per sort or hash operation within a query, not per query total. A query with five hash joins can allocate up to 5 × work_mem before spilling. Multiply by concurrent active queries when estimating RAM — 100 connections × 64 MB work_mem can theoretically demand gigabytes if every query runs parallel sorts."
  - q: "How do I know if raising work_mem will help a slow query?"
    a: "Run EXPLAIN (ANALYZE, BUFFERS). Look for Sort Method: external merge Disk or Hash Buckets with Batches > 1. If nodes already say in-memory sort with low spill, increasing work_mem may not help. If external sort or multi-batch hash appears, a targeted session-level bump often removes disk I/O."
  - q: "Should I set work_mem globally high for OLTP?"
    a: "No. A high global work_mem risks OOM when many simple queries each trigger small sorts, and it encourages the planner to choose memory-heavy plans. Keep global work_mem conservative (4–16 MB), raise per-session or per-role for reporting workloads, and use pg_stat_statements to find queries that spill."
---

The dashboard query worked fine with ten concurrent users. At Black Friday traffic, the same SQL drove `temp_file` creation to four hundred gigabytes per hour and pushed p95 latency past twelve seconds. The global `work_mem` was 256 MB — generous for one sort, catastrophic when two hundred connections each opened three hash aggregates. Tuning `work_mem` is not picking a magic number; it is understanding per-operation accounting and spill signals.

## What work_mem funds

Postgres allocates `work_mem` for:

- **Sort nodes** — ORDER BY, merge joins, CREATE INDEX (maintenance uses `maintenance_work_mem`, separate knob)
- **Hash tables** — hash joins, hash aggregates, hash-based subplans
- **Materialize nodes** — some CTE materializations

It does **not** cap shared buffers, tuple storage in result sets, or parallel worker aggregate of work_mem (each worker gets its own allocation up to work_mem for parallel sorts/hashes).

```sql
SHOW work_mem;
SET work_mem = '128MB';
ALTER ROLE analyst SET work_mem = '256MB';
```

## Per-operation multiplication

Consider a query with two hash joins, one hash aggregate, and one sort — worst-case concurrent RAM from this one query ≈ 4 × `work_mem` (not counting parallel workers). Now multiply by active connections running similar analytics.

Rule: **effective sort/hash budget ≈ active_queries × ops_per_query × work_mem × (1 + parallel_workers)**. Size RAM headroom accordingly or cap analyst concurrency.

## Reading EXPLAIN for spill

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT o.customer_id, SUM(li.amount)
FROM orders o
JOIN line_items li ON li.order_id = o.id
WHERE o.created_at >= '2025-01-01'
GROUP BY o.customer_id
ORDER BY 2 DESC
LIMIT 100;
```

Healthy hash aggregate:

```
HashAggregate  Batches: 1  Memory Usage: 8423kB
```

Spilling hash:

```
HashAggregate  Batches: 32  Memory Usage: 65536kB  Disk Usage: 204800kB
```

External sort:

```
Sort Method: external merge  Disk: 458912kB
```

When `Batches > 1` or `external merge Disk` appears, the operation exceeded `work_mem` and wrote temp files.

## log_temp_files: fleet-wide spill radar

```ini
log_temp_files = 0    # log any temp file creation
```

Log line example:

```
LOG: temporary file: path "base/pgsql_tmp/pgf_xxx.1", size 104857600
```

Correlate with `log_line_prefix` including query id when using pg_stat_statements.

```sql
SELECT datname, temp_files, temp_bytes,
       temp_bytes / NULLIF(temp_files, 0) AS avg_temp_file_bytes
FROM pg_stat_database
WHERE datname = current_database();
```

## Tuning workflow

1. **Baseline** — Identify top spillers via logs or `pg_stat_statements`.
2. **Session bump** — `SET work_mem = '64MB'` in reporting role only; re-run EXPLAIN ANALYZE.
3. **Verify latency and temp_bytes** — Ensure improvement without swapping OS page cache.
4. **Lock role setting** — `ALTER ROLE reporter SET work_mem = '64MB';`
5. **Keep global low** — `work_mem = 8MB` globally, higher for ETL batch user.

## hash_mem_multiplier (PostgreSQL 13+)

```ini
hash_mem_multiplier = 2.0   # hash tables may use up to work_mem × this
```

Effective hash budget = `work_mem × hash_mem_multiplier`. Increase cautiously; sort nodes still cap at plain `work_mem`.

## maintenance_work_mem vs work_mem

DDL and VACUUM use `maintenance_work_mem`:

```ini
maintenance_work_mem = 1GB
work_mem = 16MB
```

Do not conflate them. A huge `maintenance_work_mem` does not help SELECT sorts.

## Sort vs hash join: which spills first?

The planner picks merge join (sort both sides) vs hash join (build hash on inner) based on statistics. When EXPLAIN shows both nodes spilling, raising `work_mem` helps the dominant node first.

```sql
SET enable_hashjoin = off;  -- diagnostic only
EXPLAIN ANALYZE ...;
RESET enable_hashjoin;
```

## Parallel query interaction

Parallel workers execute partial sorts/hashes with independent `work_mem` slices. A parallel hash join with four workers can consume far more memory than a serial plan.

```sql
SET max_parallel_workers_per_gather = 0;  -- diagnostic
```

If spill disappears with parallel off, memory multiplication from workers was the culprit.

## temp_file_limit and hard caps

Postgres 14+ supports per-session temp file limits:

```sql
SET temp_file_limit = '50GB';
```

When exceeded, query cancels — preferable to filling disk.

## When indexes beat work_mem

Spill sometimes means missing index, not low memory:

```sql
SELECT * FROM events ORDER BY created_at DESC LIMIT 10;
```

An index on `(created_at DESC)` avoids sort entirely — cheaper than 512 MB `work_mem`. Always ask: can the planner skip the sort/hash node?

## pg_stat_statements correlation

```sql
SELECT query, calls, mean_exec_time, temp_blks_written
FROM pg_stat_statements
WHERE temp_blks_written > 0
ORDER BY temp_blks_written DESC
LIMIT 20;
```

Reset stats after tuning to measure delta.

## OOM prevention on shared hosts

```ini
work_mem = 16MB
max_connections = 100
shared_buffers = 4GB
```

Use connection pooler (PgBouncer) to reduce concurrent server backends. Use statement timeout on analyst sessions:

```sql
ALTER ROLE analyst SET statement_timeout = '120s';
```

## Practical example: ETL aggregation

Nightly job spilling on hash aggregate over 80 GB fact table:

```sql
BEGIN;
SET LOCAL work_mem = '512MB';
SET LOCAL max_parallel_workers_per_gather = 2;

INSERT INTO daily_rollups
SELECT date_trunc('day', ts), sku, SUM(qty)
FROM facts
WHERE ts >= CURRENT_DATE - INTERVAL '1 day'
GROUP BY 1, 2;
COMMIT;
```

`SET LOCAL` scopes to transaction — OLTP connections on default pool unaffected.

## shared_buffers interaction

High `work_mem` does not come from `shared_buffers`, but both compete for RAM. `work_mem` tuning without pooler math invites swap thrashing — monitor OS `vmstat` during peak.

`work_mem` is per sort/hash operation, not per query or connection. Spill shows up in EXPLAIN as external sort or multi-batch hash, and fleet-wide in `log_temp_files`. Keep global values conservative, override for reporting roles, fix plans with indexes when sorts are unnecessary, and account for parallel worker multiplication before the OOM killer teaches the lesson for you.

## Incremental sort and work_mem

PostgreSQL 13+ incremental sort sorts chunks using already-ordered prefix from index — reduces sort width. `EXPLAIN` shows `Incremental Sort` with memory usage lower than full sort. Incremental sort still respects `work_mem`; partial benefit does not eliminate spill on wide partitions. Combine indexed `ORDER BY` prefix with incremental sort before raising memory.

## Grouping sets and rollup memory

`GROUP BY ROLLUP` and `CUBE` generate multiple aggregation levels — each level may allocate hash or sort state. Heavy BI queries with rollup over 10M rows can multiply work_mem pressure silently. Test rollup reports with `EXPLAIN (ANALYZE)` and consider pre-aggregated matviews instead of ad-hoc rollup during peak hours.

## Prepared statements and custom work_mem

ORM connection pools set session variables once per connection checkout:

```sql
SET work_mem = '64MB';  -- on pool init for reporting role via PgBouncer startup query
```

PgBouncer `startup_query` applies per server connection — verify OLTP pool does not inherit analyst work_mem. Document which pooler user maps to which role settings.

## Cloud-managed Postgres limits

RDS and Cloud SQL cap `work_mem` maximum by parameter group tier. Attempting `SET work_mem = '2GB'` on small instance may clamp silently or reject. Check `SHOW work_mem` after SET in managed environments — effective value may differ from requested.

## Vacuum and analyze sort memory

Autovacuum uses `maintenance_work_mem`, not `work_mem`, for index cleanup and sort phases during CREATE INDEX CONCURRENTLY replay. Spill during user queries and bloat during vacuum are separate tuning tracks — do not raise work_mem hoping to fix bloat latency.

## Real incident: sort node regression after upgrade

After PostgreSQL minor upgrade, one reporting query regressed from 4s to 45s — planner switched from hash join to merge join due to statistics refresh. Merge join sorted 12M rows spilling 8GB temp files per run. Fix was restoring statistics plus adding composite index — not raising work_mem from 16MB to 512MB. Lesson: spill after upgrade may be plan regression; compare EXPLAIN across versions before memory knob turning.

## work_mem in connection string options

libpq and JDBC support options parameter:

```
postgresql://analyst:pass@host/db?options=-c%20work_mem%3D128MB
```

BI tools connecting directly bypass role ALTER — document connection string memory for Tableau/Looker service accounts or they inherit default 4MB and flood support with "slow dashboard" tickets.

## Hash join batch growth dynamics

When hash join batches multiply, each batch writes partition files — disk bandwidth becomes bottleneck before CPU. Raising work_mem to fit single batch removes partition round-trips — nonlinear speedup when crossing batch threshold. Identify threshold by binary search SET work_mem in session during EXPLAIN ANALYZE runs in staging clone.
