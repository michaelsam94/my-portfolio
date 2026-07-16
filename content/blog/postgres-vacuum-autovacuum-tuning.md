---
title: "Tuning VACUUM and autovacuum"
slug: "postgres-vacuum-autovacuum-tuning"
description: "Tune PostgreSQL VACUUM and autovacuum: bloat, dead tuples, wraparound prevention, per-table settings, and monitoring vacuum lag before queries slow down."
datePublished: "2026-04-06"
dateModified: "2026-04-06"
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

## Common production mistakes

Teams get vacuum autovacuum tuning wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Postgres work on vacuum autovacuum tuning causes outages when migrations run without `lock_timeout`, connection pools are sized for app servers not PgBouncer modes, and `EXPLAIN` plans from staging are assumed to match production statistics.

## Debugging and triage workflow

When vacuum autovacuum tuning misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [PostgreSQL routine vacuuming](https://www.postgresql.org/docs/current/routine-vacuuming.html)
- [PostgreSQL autovacuum parameters](https://www.postgresql.org/docs/current/runtime-config-autovacuum.html)
- [pg_repack extension](https://reorg.github.io/pg_repack/)
- [PostgreSQL MVCC documentation](https://www.postgresql.org/docs/current/mvcc.html)
- [pgstattuple module](https://www.postgresql.org/docs/current/pgstattuple.html)
