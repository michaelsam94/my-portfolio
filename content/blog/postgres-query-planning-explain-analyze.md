---
title: "Reading EXPLAIN ANALYZE Output"
slug: "postgres-query-planning-explain-analyze"
description: "Interpret PostgreSQL EXPLAIN ANALYZE plans: scan types, cost vs actual rows, buffer hits, join methods, and systematic query optimization workflow."
datePublished: "2026-03-30"
dateModified: "2026-03-30"
tags: ["PostgreSQL", "Backend", "Database", "Performance"]
keywords: "EXPLAIN ANALYZE PostgreSQL, query plan optimization, sequential scan vs index scan, Postgres buffers, query tuning"
faq:
  - q: "What is the difference between EXPLAIN and EXPLAIN ANALYZE?"
    a: "EXPLAIN shows the planner's estimated plan without running the query. EXPLAIN ANALYZE executes the query and shows actual row counts, timing, and loops. Always use ANALYZE for real tuning — estimates wrong mean wrong index choices."
  - q: "Why do estimated rows differ from actual rows in EXPLAIN?"
    a: "Outdated statistics, correlated columns, skewed data distributions, or generic plans. Run ANALYZE on the table, increase statistics targets on filtered columns, or use extended statistics for correlated columns."
  - q: "When is a sequential scan actually fine?"
    a: "When reading a large fraction of the table (often >5–10% depending on width), when the table is small enough to fit in cache, or when index random I/O exceeds sequential scan cost. Not every Seq Scan is a problem."
---

Every slow query ticket attached `EXPLAIN` output without `ANALYZE`. Planned rows: 1. Actual rows: 847,000. The planner chose a nested loop because it expected one row. Production chose pain. Reading EXPLAIN ANALYZE is a skill — scan types, actual vs estimated rows, and buffer reads tell you whether to add an index, update statistics, or rewrite the query.

## Running EXPLAIN properly

```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT o.*, c.name
FROM orders o
JOIN customers c ON c.id = o.customer_id
WHERE o.created_at > now() - interval '7 days'
  AND o.status = 'pending';
```

Options:
- **ANALYZE** — real execution, real timings
- **BUFFERS** — shared/local hit vs read — cache effectiveness
- **VERBOSE** — column names, output expressions
- **SETTINGS** — planner GUCs affecting plan

Run representative queries in staging with production-like data volume. `EXPLAIN` on empty tables lies.

## Node types decoded

| Node | Meaning | Usually good when |
|------|---------|-------------------|
| Seq Scan | Read whole table | Small table or most rows needed |
| Index Scan | Index lookup + heap fetch | Selective filter |
| Index Only Scan | Satisfied from index | INCLUDE/index covers columns |
| Bitmap Index Scan | Build TID bitmap from index | Medium selectivity |
| Nested Loop | For each outer row, scan inner | Small outer set |
| Hash Join | Build hash table on inner | Equi-join, large sets |
| Merge Join | Sorted inputs merged | Pre-sorted or sort cheap |
| Sort | Sort rows | ORDER BY, merge input |

```
Nested Loop  (cost=0.43..892.12 rows=1 width=100) (actual time=0.05..4500.23 rows=89231 loops=1)
  ->  Index Scan using orders_created_idx on orders  (actual rows=89231)
  ->  Index Scan using customers_pkey on customers  (actual rows=1 loops=89231)
```

89231 nested loop iterations — inner index scan ran 89k times. Hash join likely better — planner misestimated `rows=1`.

## Estimated vs actual rows

```
Index Scan ... (cost=... rows=100 width=...) (actual time=... rows=95000 loops=1)
```

Large estimate gap → bad plan. Fixes:

```sql
ANALYZE orders;
ALTER TABLE orders ALTER COLUMN status SET STATISTICS 1000;
CREATE STATISTICS orders_status_created (dependencies) ON status, created_at FROM orders;
ANALYZE orders;
```

Correlated `status` and `created_at` fool independent column statistics.

## BUFFERS: cache vs disk

```
Buffers: shared hit=45000 read=12000
```

`read` = disk I/O (slow). High read count on index scan — working set exceeds `shared_buffers` or cold cache.

`shared hit` dominates — data cached. Still slow? CPU (sort, hash), row width, or lock waits — not I/O.

## Timing interpretation

```
(actual time=0.02..0.05 rows=100 loops=1)   -- startup..total per loop
```

Parent node time includes children. Focus on highest **actual time** nodes — optimization target.

`Planning Time` vs `Execution Time` — plan cache misses show high planning on ORMs generating dynamic SQL.

## Systematic tuning workflow

1. **EXPLAIN (ANALYZE, BUFFERS)** on slow query
2. Find node with highest actual time
3. Seq Scan on large table? — index candidate; verify selectivity
4. Index Scan but huge rows? — statistics or wrong index column order
5. Nested Loop with high loops? — join order or hash join hint investigation
6. Sort/Hash aggregate dominating? — pre-aggregate, materialized view, limit columns
7. Re-run EXPLAIN after change — confirm improvement, watch regressions

Avoid hinting (`/*+ HashJoin */` via pg_hint_plan) until rewrite and index options exhausted.

## Query rewrite examples

**Bad:** function on indexed column
```sql
WHERE date(created_at) = '2026-03-15'  -- Seq Scan
WHERE created_at >= '2026-03-15' AND created_at < '2026-03-16'  -- Index Scan
```

**Bad:** OR preventing index use
```sql
WHERE status = 'pending' OR status = 'processing'
-- Consider IN or UNION ALL per status
```

**Good:** pagination with keyset not OFFSET
```sql
WHERE id > $last_id ORDER BY id LIMIT 50  -- Index Scan
OFFSET 1000000  -- reads and discards million rows
```

## auto_explain for production sampling

Enable `auto_explain` with `log_min_duration_statement` on staging first, then sample in prod for queries exceeding 500ms. Logged plans feed slow query review without manual EXPLAIN reproduction. Redact bind parameters containing PII in log pipeline.

## Operational notes

Compare EXPLAIN plans before and after statistics refresh when upgrading Postgres major versions — planner changes rewrite familiar queries unexpectedly; capture plan baselines in migration test suite.

## Reading EXPLAIN ANALYZE

Red flags in plan output:
- `Seq Scan` on large table with filter — missing index
- `Nested Loop` with high row estimate — stale statistics, run ANALYZE
- `Sort` with `external merge` — work_mem too low
- Actual rows >> estimated rows — planner chose wrong join

Run `EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)` for buffer hit ratio.

## Common production mistakes

Teams get query planning explain analyze wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Postgres work on query planning explain analyze causes outages when migrations run without `lock_timeout`, connection pools are sized for app servers not PgBouncer modes, and `EXPLAIN` plans from staging are assumed to match production statistics.

## Debugging and triage workflow

When query planning explain analyze misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [PostgreSQL EXPLAIN documentation](https://www.postgresql.org/docs/current/sql-explain.html)
- [PostgreSQL Using EXPLAIN guide](https://www.postgresql.org/docs/current/using-explain.html)
- [Depesz EXPLAIN visualizer](https://explain.depesz.com/)
- [PostgreSQL extended statistics](https://www.postgresql.org/docs/current/planner-stats.html#PLANNER-STATS-EXTENDED)
- [PgMustard EXPLAIN analyzer](https://www.pgmustard.com/)
