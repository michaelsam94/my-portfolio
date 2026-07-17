---
title: "Tuning VACUUM and autovacuum"
slug: "postgres-vacuum-autovacuum-tuning"
description: "Tune PostgreSQL VACUUM and autovacuum: bloat, dead tuples, wraparound prevention, per-table settings, and monitoring vacuum lag before queries slow down."
datePublished: "2026-04-06"
dateModified: "2026-07-17"
tags: ["PostgreSQL", "Backend", "Database", "Operations"]
keywords: "PostgreSQL autovacuum tuning, VACUUM bloat, dead tuples Postgres, vacuum wraparound, pg_stat_user_tables vacuum"
faq:
  - q: "What happens if autovacuum doesn't run often enough?"
    a: "Dead tuples accumulate causing table and index bloat, sequential scans and index scans read more pages, queries slow down, and transaction ID wraparound risk increases — which can force shutdown for emergency vacuum. High-churn tables feel this first."
  - q: "Should I disable autovacuum on busy tables and run manual VACUUM?"
    a: "Rarely. Disable only with a rigorous manual schedule that outperforms autovacuum — usually you instead tune autovacuum per-table thresholds lower for hot tables. Disabling without replacement guarantees bloat."
  - q: "What is the difference between VACUUM and VACUUM FULL?"
    a: "VACUUM marks dead space reusable and freezes XIDs — online, non-blocking for normal reads. VACUUM FULL rewrites the entire table to reclaim disk space — exclusive lock, downtime risk. Use pg_repack for online compaction instead of VACUUM FULL in production."
---

Disk usage climbed 40% while row count grew 5%. `pg_stat_user_tables.n_dead_tup` on `events` showed 12 million dead tuples. Autovacuum ran — just not often enough for a table ingesting 50k rows per minute. Tuning autovacuum isn't DBA arcana; it's why your indexed queries got slower six months after launch.

## What VACUUM does

Postgres MVCC leaves dead row versions when UPDATE/DELETE runs. VACUUM:

- Marks dead tuples reusable (space not returned to OS except via FULL/repack)
- Updates visibility map for index-only scans
- Freezes transaction IDs to prevent wraparound
- Updates planner statistics (if `vacuum analyze`)

Autovacuum launcher wakes workers based on thresholds.

## Default thresholds (often too lazy for hot tables)

```
autovacuum_vacuum_threshold = 50
autovacuum_vacuum_scale_factor = 0.2   -- 20% of table
autovacuum_analyze_scale_factor = 0.1
```

On 100M row table: vacuum triggers after 20M dead tuples — catastrophic delay.

## Per-table tuning

```sql
ALTER TABLE events SET (
  autovacuum_vacuum_scale_factor = 0.01,   -- 1%
  autovacuum_vacuum_threshold = 1000,
  autovacuum_analyze_scale_factor = 0.005,
  autovacuum_vacuum_cost_delay = 2        -- ms, more aggressive
);
```

Hot append-mostly tables: lower scale_factor. Small dimension tables: defaults fine.

Global aggressiveness (use carefully):

```sql
-- postgresql.conf
autovacuum_max_workers = 6
autovacuum_naptime = 10s
autovacuum_vacuum_cost_limit = 1000
```

More workers + lower naptime = more frequent vacuum attempts.

## Monitoring

```sql
SELECT relname, n_live_tup, n_dead_tup,
       round(n_dead_tup::numeric / nullif(n_live_tup, 0), 4) AS dead_ratio,
       last_autovacuum, last_autoanalyze
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC
LIMIT 20;
```

Alert when:
- `dead_ratio > 0.1` sustained on large tables
- `last_autovacuum` older than expected for churn rate
- `age(relfrozenxid)` approaching `autovacuum_freeze_max_age` (default 200M)

Wraparound warning:

```sql
SELECT datname, age(datfrozenxid) FROM pg_database;
```

## Long transactions block vacuum

Open transaction holds xmin — vacuum can't remove dead tuples it might still need.

```sql
SELECT pid, xact_start, state, query
FROM pg_stat_activity
WHERE state != 'idle'
  AND xact_start < now() - interval '1 hour';
```

Kill idle-in-transaction connections. ORM session leaks are common culprit.

## Bloat measurement and remediation

```sql
-- pgstattuple extension
SELECT * FROM pgstattuple('events');
-- dead_tuple_percent
```

Remediation ladder:
1. Tune autovacuum, wait for natural cleanup
2. `VACUUM (VERBOSE, ANALYZE) events;` manual nudge
3. `pg_repack` online rewrite
4. `VACUUM FULL` only in maintenance window (locks table)

Index bloat: `REINDEX INDEX CONCURRENTLY` per bloated index.

## Partitioning helps vacuum

Monthly partitions — vacuum hammers recent partition; drop old partitions instead of vacuuming 180 GB monolith.

## Common mistakes

- **`fillfactor 100` on update-heavy tables** — leave headroom: `ALTER TABLE SET (fillfactor = 85)` for HOT updates
- **Too many autovacuum workers on small instance** — I/O saturation
- **Ignoring analyze** — vacuum without analyze leaves stale stats after bulk changes
- **Monitoring disk only** — bloat invisible until queries degrade

## RDS and managed Postgres specifics

On Amazon RDS and Aurora, autovacuum parameters live in parameter groups — changing them requires a pending-reboot apply for static parameters. Watch `FreeStorageSpace` alongside dead tuples: bloat consumes allocated storage even when `SELECT pg_size_pretty(pg_database_size())` looks stable because free space inside the table file is not returned to the filesystem until `VACUUM FULL` or repack.

Aurora storage autoscales, but query performance still degrades with heap bloat. Use Performance Insights to correlate `BufferCacheHitRatio` drops with tables showing rising `n_dead_tup`. For logical replication subscribers, vacuum freeze on the publisher remains critical — replicas do not relieve xmin pressure on the primary.

Schedule manual `VACUUM (ANALYZE)` before large bulk loads and immediately after bulk deletes on partitioned tables. Bulk delete without follow-up vacuum leaves partitions in a state where the planner underestimates live rows until analyze catches up.

## HOT updates and fillfactor

When UPDATE keeps rows on same page, Heap-Only Tuple (HOT) updates avoid index maintenance. Lower fillfactor preserves page space for HOT chains on update-heavy tables. Monitor `n_tup_hot_upd` vs `n_tup_upd` in pg_stat_user_tables — low HOT ratio suggests fillfactor tuning opportunity.

## Operational notes

After bulk DELETE migrations, schedule manual vacuum analyze before re-opening traffic — autovacuum may lag hours on large tables while planner statistics still reflect pre-delete row counts.

Correlate autovacuum duration with maintenance window alerts — vacuum exceeding expected duration on large partition often signals need for lower scale_factor on that partition only.

Track table bloat percentage weekly on top ten largest tables — trending bloat above five percent triggers manual vacuum investigate before query plans degrade noticeably to users.

Treat production rollout as a measured change: ship with observability, validate rollback, and review metrics 24 hours after deploy — patterns that look obvious in docs fail when skipped under release pressure.


## autovacuum_vacuum_scale_factor

Default 0.2 means 20% dead tuples trigger vacuum — on 100M row table, 20M dead tuples before vacuum. Lower scale factor on large hot tables to 0.02.

## Index bloat vs heap bloat

n_dead_tup rising with stable n_live_tup — autovacuum not keeping up. Increase autovacuum_max_workers before aggressive VACUUM FULL.

## Transaction id wraparound

Monitor age(datfrozenxid) — emergency vacuum when approaching 2 billion. Long transactions block vacuum freeze — alert on xact_start over 24h.

## VACUUM vs ANALYZE scheduling

Bulk load followed by ANALYZE only — planner wrong until stats refresh. VACUUM after large DELETE before ANALYZE.

## autovacuum_vacuum_cost_delay tuning

On SSD storage, lower cost_delay for hot tables — vacuum completes before wraparound emergency. NVMe can tolerate aggressive autovacuum_vacuum_cost_limit increase per table OPTIONS.

## Monitoring bloat with pgstattuple

SELECT * FROM pgstattuple('events') on largest table monthly — dead_tuple_pct over 20% with autovacuum running suggests autovacuum not keeping up or long transactions blocking. pg_repack online rewrite alternative to VACUUM FULL for heap bloat without long lock.

## aggressive autovacuum for hot tables

```sql
ALTER TABLE events SET (
  autovacuum_vacuum_scale_factor = 0.01,
  autovacuum_analyze_scale_factor = 0.005,
  autovacuum_vacuum_cost_limit = 2000
);
```

Tune per table after measuring n_dead_tup on pg_stat_user_tables — one size fits all leaves hot tables bloated while cold tables over-vacuumed.

## freeze_max_age monitoring

Alert when relfrozenxid age > 75% of autovacuum_freeze_max_age — proactive vacuum freeze before emergency wraparound autovacuum interrupts production IO.

## Manual VACUUM (ANALYZE) after bulk load

COPY 10M rows then immediate ANALYZE — planner chooses seq scan on empty stats underestimating rows. VACUUM ANALYZE after bulk delete too — dead tuples and stats both stale.

## autovacuum worker saturation

pg_stat_progress_vacuum shows multiple workers busy — if all workers occupied, hot table waits — increase autovacuum_max_workers temporarily during bloat incident after verifying IO headroom on storage.

## pgstattuple after vacuum

Run pgstattuple on table after aggressive autovacuum — dead_tuple_pct should near zero. If not, long transaction blocking vacuum visible in pg_stat_activity with xact_start old — pg_cancel_backend or application fix long session.

## Closing notes

Graph autovacuum duration and dead tuple count on dashboard next to API latency — visual correlation convinces product to accept brief autovacuum tuning maintenance when bloat causes seq scan regression.

## Additional guidance

Tables with heavy UPDATE to indexed jsonb columns experience faster dead tuple accumulation — per-table autovacuum aggressive settings on those tables only rather than global autovacuum tuning affecting whole cluster IO profile during peak hours when global aggressive vacuum would compete with checkout query IO on same storage volume.

Monitor autovacuum wraparound protection priority in pg_stat_progress_vacuum — emergency vacuum during wraparound crisis contends IO with production traffic; proactive per-table tuning prevents reaching wraparound forced autovacuum mode that ignores cost delay limits causing latency spike visible to all users simultaneously.

Alert on pg_stat_user_tables n_dead_tup above five percent of n_live_tup for Tier-1 tables — triggers autovacuum tuning review before sequential scan regression hits checkout queries.

Graph dead_tuple_pct next to p95 query latency on checkout tables — visual correlation accelerates approval for autovacuum parameter change affecting IO during business hours maintenance window.

## Resources

- [PostgreSQL routine vacuuming](https://www.postgresql.org/docs/current/routine-vacuuming.html)
- [PostgreSQL autovacuum parameters](https://www.postgresql.org/docs/current/runtime-config-autovacuum.html)
- [pg_repack extension](https://reorg.github.io/pg_repack/)
- [PostgreSQL MVCC documentation](https://www.postgresql.org/docs/current/mvcc.html)
- [pgstattuple module](https://www.postgresql.org/docs/current/pgstattuple.html)
