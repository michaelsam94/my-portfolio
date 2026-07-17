---
title: "Postgres Parallel Query Tuning"
slug: "postgres-parallel-query-tuning"
description: "Tune parallel query execution — max_parallel_workers, gather nodes, parallel-safe functions, and when parallelism hurts."
datePublished: "2026-02-23"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
keywords: "parallel query postgres, max_parallel_workers_per_gather, gather merge, parallel seq scan, min_parallel_table_scan_size"
faq:
  - q: "Why does my large table scan not use parallel workers?"
    a: "Check min_parallel_table_scan_size (default 8MB) — tables smaller than this won't parallelize. Verify max_parallel_workers_per_gather > 0, the query is not in a transaction with parallel unsafe operations, and no parallel restriction applies (cursor, prepared statement in some modes, or table marked parallel_workers = 0)."
  - q: "Can parallel query make queries slower?"
    a: "Yes. Parallelism adds coordination overhead — Gather node, worker startup, shared memory coordination. On small tables or low-selectivity queries returning few rows, single-worker execution is faster. OLTP point queries rarely benefit; analytical scans on large tables do."
  - q: "How do I limit parallel query impact on OLTP workloads?"
    a: "Set max_parallel_workers_per_gather lower globally (2 instead of 4), use ALTER TABLE ... SET (parallel_workers = 0) on OLTP-hot tables, set max_parallel_workers at cluster level to cap total workers, and assign role-level settings to reserve workers for reporting roles."
---

A sequential scan across 200 million rows on a 32-core server using one CPU while thirty-one cores idle is a tuning failure — or a configuration success, depending on whether parallel query is enabled and the planner judged the scan worth parallelizing. Postgres parallel query splits scan, join, and aggregate work across **background worker processes**, coordinated by a **Gather** node. Misconfiguration either wastes hardware or spawns worker storms that contend with OLTP traffic.

This article covers planner thresholds, configuration parameters, EXPLAIN interpretation, and operational boundaries for parallel query.

## How parallel query works

```
Leader process
  ├── Parallel Seq Scan (partial — workers scan page ranges)
  ├── Parallel Hash Join
  └── Gather / Gather Merge (combine partial results)
        ├── Worker 1
        ├── Worker 2
        └── Worker N
```

The leader participates as a worker (by default) and coordinates collection. Workers are drawn from the **parallel worker pool** — separate from regular backend connections but consuming CPU and shared memory.

EXPLAIN output with parallelism:

```
Gather  (cost=1000..50000 rows=1000000 width=36)
  Workers Planned: 4
  Workers Launched: 4
  ->  Parallel Seq Scan on orders  (cost=0..45000 rows=250000 width=36)
        Filter: (created_at > '2025-01-01')
```

## Key configuration parameters

```sql
-- Cluster-wide cap on parallel workers
max_parallel_workers = 8              -- default 8, max 1024

-- Workers per Gather node
max_parallel_workers_per_gather = 2   -- default 2, 0 disables parallel plans

-- Workers eligible for maintenance (VACUUM, CREATE INDEX)
max_parallel_maintenance_workers = 2

-- Minimum table size before parallel scan considered
min_parallel_table_scan_size = '8MB'

-- Minimum table size for parallel index scan
min_parallel_index_scan_size = '512kB'

-- Cost model — lower = more aggressive parallelism
parallel_setup_cost = 100             -- default 100
parallel_tuple_cost = 0.1             -- default 0.1
```

Session-level overrides for testing:

```sql
SET max_parallel_workers_per_gather = 4;
SET min_parallel_table_scan_size = 0;  -- force consideration (testing only)
```

Permanent per-table control:

```sql
ALTER TABLE orders SET (parallel_workers = 4);  -- hint max workers
ALTER TABLE orders SET (parallel_workers = 0);  -- disable parallel scan
```

Per-role settings for workload isolation:

```sql
ALTER ROLE reporting SET max_parallel_workers_per_gather = 4;
ALTER ROLE app_oltp SET max_parallel_workers_per_gather = 0;
```

## When the planner chooses parallelism

Requirements for parallel plans:

1. Query is parallel-safe (no volatile functions blocking parallel mode in unsupported nodes)
2. Table exceeds `min_parallel_table_scan_size`
3. `max_parallel_workers_per_gather > 0`
4. Sufficient `max_parallel_workers` pool available
5. No conflicting settings (transaction isolation, cursor WITH HOLD in some cases)

Parallel-safe operations:

- Seq Scan, Index Scan (with parallel bitmap)
- Hash Join, Nested Loop (limited)
- Aggregate (partial aggregate + finalize)
- Sort (partial sort + merge)

Parallel-unsafe blockers:

- Volatile functions in scan filter: `WHERE random() < 0.1`
- CTEs marked MATERIALIZED with unsafe contents
- Subqueries with locking clauses in some paths
- Writable CTEs

Check function parallel safety:

```sql
SELECT proname, proparallel
FROM pg_proc
WHERE proname = 'my_function';
-- 's' = safe, 'r' = restricted, 'u' = unsafe
```

Mark custom functions safe when appropriate:

```sql
ALTER FUNCTION my_immutable_func() PARALLEL SAFE;
```

## Tuning for analytical workloads

Large reporting queries on dedicated replica:

```sql
-- postgresql.conf on reporting replica
max_parallel_workers = 16
max_parallel_workers_per_gather = 4
min_parallel_table_scan_size = '4MB'
work_mem = '256MB'  -- per worker — total = work_mem × (workers + 1)
```

Monitor work_mem multiplication: 4 workers + leader = 5 × 256 MB = 1.25 GB per query for hash operations. Multiple concurrent parallel queries multiply further.

Adjust parallel cost constants to encourage parallelism on beefy hardware:

```sql
SET parallel_setup_cost = 10;    -- lower startup penalty
SET parallel_tuple_cost = 0.01;  -- lower per-row transfer penalty
```

Use sparingly — defaults are conservative for mixed workloads.

## Tuning for mixed OLTP + analytics

Problem: ad-hoc analytical query spawns 4 workers, starves OLTP CPU cache and I/O.

Mitigations:

```sql
-- Global conservative default
max_parallel_workers_per_gather = 2
max_parallel_workers = 4

-- Hot OLTP tables: disable
ALTER TABLE users SET (parallel_workers = 0);
ALTER TABLE sessions SET (parallel_workers = 0);

-- Large cold tables: enable
ALTER TABLE events SET (parallel_workers = 4);
```

Resource groups (PG extension or external cgroups): cap reporting role CPU.

Statement timeout on OLTP role prevents runaway parallel scans:

```sql
ALTER ROLE app_oltp SET statement_timeout = '30s';
ALTER ROLE reporting SET statement_timeout = '600s';
ALTER ROLE reporting SET max_parallel_workers_per_gather = 4;
```

## EXPLAIN ANALYZE interpretation

```sql
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT count(*), customer_id FROM orders GROUP BY customer_id;
```

Look for:

- **Workers Planned vs Launched**: Launched < Planned means worker pool exhaustion
- **Actual time** on Gather vs Parallel children: Gather overhead = parent time - max child time
- **BUFFERS**: shared hit/read per worker — cache efficiency
- **Rows**: partial rows per worker should roughly equal total/workers

Bad sign — parallelism overhead exceeds benefit:

```
Gather  (actual time=500..520 rows=100 width=4)
  Workers Launched: 4
  ->  Parallel Seq Scan  (actual time=0.1..510 rows=25 width=4)
        Rows Removed by Filter: 999999
```

Full parallel scan discarded almost all rows — index would beat parallelism. Add index on filter column.

## Parallel aggregate

Two-stage aggregation:

```
Finalize Aggregate
  ->  Gather
        ->  Partial Aggregate  (each worker computes partial count/sum)
              ->  Parallel Seq Scan
```

Efficient for `count(*)`, `sum()`, `avg()` on large tables. Less benefit for `count(distinct ...)` — often requires single-threaded deduplication unless approximate acceptable.

## Parallel join

Hash join parallelizes build and probe sides:

```
Gather
  ->  Parallel Hash Join
        ->  Parallel Seq Scan on orders
        ->  Parallel Seq Scan on customers
```

Both sides must be large enough to justify parallelism. Nested loop parallelization is limited — OLTP join patterns rarely parallelize.

## Worker pool exhaustion

```
Workers Planned: 4
Workers Launched: 0
```

Causes:

- `max_parallel_workers` already consumed by other queries
- `max_worker_processes` too low (includes logical replication, autovacuum workers)
- System resource limits

Check:

```sql
SHOW max_worker_processes;  -- must exceed max_parallel_workers + maintenance + logical workers
SHOW max_parallel_workers;
SELECT count(*) FROM pg_stat_activity WHERE backend_type = 'parallel worker';
```

Increase carefully:

```
max_worker_processes = 32
max_parallel_workers = 16
```

Each worker is an OS process — memory and scheduler overhead applies.

## Disabling parallelism entirely

Per session (debugging plan choice):

```sql
SET max_parallel_workers_per_gather = 0;
```

Per database for OLTP-only:

```sql
ALTER DATABASE mydb SET max_parallel_workers_per_gather = 0;
```

Table-level for specific hot tables without affecting global settings.

## Parallel maintenance

```sql
-- VACUUM with parallel workers (PG 13+)
VACUUM (PARALLEL 4) large_table;

-- CREATE INDEX (parallel build since PG 11)
CREATE INDEX CONCURRENTLY ... -- uses max_parallel_maintenance_workers
```

Separate pool from query parallelism — tune `max_parallel_maintenance_workers` independently.

## Cloud and container CPU limits

Kubernetes CPU limits throttle parallel workers — 4 workers on 2 CPU limit fight each other and the cgroup scheduler. Match `max_parallel_workers_per_gather` to actual available CPUs:

```
CPU limit: 4 cores → max_parallel_workers_per_gather = 2 (leave headroom for leader + OS)
```

Cloud instances with burstable CPU (T-series) may throttle during sustained parallel scans — monitor CPU credits.

## Monitoring

```sql
SELECT query, parallel_workers
FROM pg_stat_activity
WHERE parallel_workers > 0;
```

pg_stat_statements — compare mean time with and without parallel plans for same query pattern.

System metrics: CPU utilization per core during parallel query vs single-threaded baseline.

## Version-specific parallel query improvements

Postgres parallel query capabilities expanded across recent releases — verify your version before tuning:

- **PG 13**: Parallel INSERT into tables (limited scenarios)
- **PG 14**: Improved parallel sequential scan cost estimates
- **PG 15**: Parallel RIGHT and FULL OUTER JOIN
- **PG 16**: Parallel hash join memory improvements

Upgrade release notes often include planner fixes that change parallel plan selection without configuration changes. After major version upgrades, re-benchmark top 10 analytical queries — a query that was faster without parallelism on PG 13 may benefit from parallelism on PG 16.

Document baseline EXPLAIN ANALYZE output before upgrades for regression comparison.

## Summary

Parallel query accelerates large scans, joins, and aggregates by distributing work across background workers coordinated by Gather nodes. Tune max_parallel_workers_per_gather and min_parallel_table_scan_size for your hardware and workload mix, disable parallelism on OLTP-hot tables, and verify benefit with EXPLAIN ANALYZE rather than assuming more workers always help. Account for work_mem multiplication across workers, watch for worker pool exhaustion, and reserve aggressive parallelism settings for reporting roles and replicas rather than primary OLTP traffic.


Disable parallel gather for API roles and enable it for analysts so OLTP point lookups do not steal workers from useful reports.
