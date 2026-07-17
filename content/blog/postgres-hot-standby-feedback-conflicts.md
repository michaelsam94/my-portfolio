---
title: "Postgres Hot Standby Feedback Conflicts"
slug: "postgres-hot-standby-feedback-conflicts"
description: "Understand and resolve hot standby query conflicts — canceling queries, vacuum blocking, and hot_standby_feedback tuning."
datePublished: "2026-02-23"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
keywords: "hot standby conflicts, hot_standby_feedback, max_standby_streaming_delay, vacuum replica, pg_stat_database_conflicts"
faq:
  - q: "Why does my long-running report on a replica get canceled?"
    a: "The primary issued VACUUM or HOT UPDATE that removed row versions your replica query still needs. Postgres cancels the standby query to apply WAL — configured by max_standby_streaming_delay (default 30s waits, then cancels) or immediately depending on conflict type. Shorten queries, use hot_standby_feedback, or run long reports against a delayed replica."
  - q: "What does hot_standby_feedback actually do?"
    a: "The standby tells the primary which rows its open transactions still need via replication feedback. The primary's VACUUM retains dead tuples those queries reference, preventing conflict cancellations. Tradeoff: increased table bloat on the primary if replica queries run for hours."
  - q: "Should I route all read traffic to hot standbys?"
    a: "Route latency-tolerant reads to standbys. Avoid standbys for long analytical queries unless hot_standby_feedback is enabled and bloat is monitored, or use a logical replica / dedicated reporting instance with snapshot isolation that tolerates lag."
---

Read replicas offload analytics, reporting, and read-heavy API paths from the primary. Postgres hot standby replay applies WAL on the replica while simultaneously serving SELECT queries — a concurrency model that creates **conflicts** when primary maintenance needs to remove row versions that standby queries still reference. The result: mysteriously canceled reports, replication lag spikes, and vacuum paralysis.

This article explains conflict types, the parameters that control resolution, and operational strategies to keep replicas useful without harming primary health.

## How hot standby serves queries during replay

A standby continuously replays WAL from the primary. While replaying, it holds **access exclusive** locks briefly for DDL and **row-level exclusivity** for vacuum cleanup. Long-running SELECT on the standby may hold snapshots referencing dead tuples that WAL replay needs to prune.

When replay cannot proceed without conflicting with an active query:

1. Wait up to `max_standby_streaming_delay` (streaming replication)
2. Cancel the conflicting standby query
3. Apply WAL and continue replay

Canceled queries surface to applications as:

```
ERROR: canceling statement due to conflict with recovery
DETAIL: User query might have needed to see row versions that must be removed.
```

## Conflict types tracked in pg_stat_database_conflicts

```sql
SELECT datname,
       confl_tablespace,
       confl_lock,
       confl_snapshot,
       confl_bufferpin,
       confl_deadlock
FROM pg_stat_database_conflicts
WHERE datname = current_database();
```

| Conflict | Cause |
| --- | --- |
| **confl_snapshot** | VACUUM removed rows visible to standby query snapshot |
| **confl_lock** | AccessExclusiveLock on primary (DDL) blocks replay |
| **confl_bufferpin** | Standby holds buffer pin preventing WAL apply |
| **confl_tablespace** | DROP TABLESPACE while standby accesses files |
| **confl_deadlock** | Deadlock between recovery and standby query |

Snapshot conflicts (`confl_snapshot`) are the most common in OLTP + reporting workloads.

## Key configuration parameters

On the **standby** (postgresql.conf):

```sql
-- Max delay before canceling queries (streaming replication)
max_standby_streaming_delay = '30s'   -- default; 0 = cancel immediately

-- Same for archive recovery (crash recovery mode)
max_standby_archive_delay = '30s'

-- Send xmin feedback to primary
hot_standby_feedback = off   -- default; set on for long queries
```

On the **primary**:

```sql
-- Primary respects standby feedback for vacuum decisions
-- (no separate setting — controlled by standby sending feedback)

vacuum_defer_cleanup_age = 0  -- default; increase delays vacuum on primary
```

### max_standby_streaming_delay

Controls how long replay waits before canceling a conflicting query:

```
max_standby_streaming_delay = '30s'
  → Replay pauses up to 30 seconds hoping query finishes
  → After 30s, cancel query and apply WAL
  → Replication lag may grow by up to 30s during wait
```

Set to `-1` to wait indefinitely (replay stalls, lag grows unbounded — rarely correct).

Set to `0` to cancel immediately (minimum lag, maximum query disruption).

Tuning guidance:

- **OLTP read replica**: `'5s'` — fail fast, retry at application layer
- **Mixed workload**: `'30s'` default — reasonable balance
- **Analytics replica with hot_standby_feedback**: `'300s'` — allow long queries time to finish before cancel

### hot_standby_feedback

When `on`, standby sends oldest xmin (active transaction horizon) to primary:

```
Standby long query started at xmin 1000
  → Feedback to primary: "don't vacuum rows needed by xmin 1000"
  → Primary VACUUM skips those dead tuples
  → No snapshot conflict on standby
  → Primary accumulates bloat until standby query completes
```

Enable when:

- Long-running reports (minutes+) on standby
- Conflict cancellation rate is unacceptable
- Primary bloat is monitored and autovacuum tuned

Disable when:

- Standby serves only short OLTP reads
- Primary bloat became problematic after enabling feedback
- Using pglogical or separate reporting replica instead

## Monitoring conflicts

Reset and watch counters:

```sql
SELECT pg_stat_reset();  -- careful in production — resets all stats

-- After interval, check:
SELECT confl_snapshot, confl_lock
FROM pg_stat_database_conflicts
WHERE datname = 'mydb';
```

Log conflicts (standby postgresql.conf):

```
log_recovery_conflict_waits = on   -- log when waiting for query cancel
```

Application metrics: track `SQLSTATE 40001` or error message pattern `conflict with recovery` on replica connection pool.

Replication lag during conflict waits:

```sql
SELECT pg_wal_lsn_diff(
  pg_last_wal_receive_lsn(),
  pg_last_wal_replay_lsn()
) AS replay_lag_bytes;
```

Lag spikes correlate with conflict wait periods.

## Strategies by workload

### Short OLTP reads on replica

```sql
-- Standby config
hot_standby_feedback = off
max_standby_streaming_delay = '5s'
```

Application retries canceled queries. Accept occasional retry.

### Long analytical queries

Option A — feedback + monitoring:

```sql
hot_standby_feedback = on
max_standby_streaming_delay = '600s'
```

Monitor primary bloat:

```sql
-- On primary
SELECT schemaname, relname, n_dead_tup, last_autovacuum
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC
LIMIT 20;
```

Option B — delayed replica:

```
Use pg_receivewal delay or dedicated replica with intentional lag
Analytics query against 1-hour delayed snapshot — no conflict with current primary vacuum
```

Option C — separate reporting database:

Logical replication or ETL to dedicated instance. No hot standby conflicts because it is not WAL replay.

### DDL during business hours

DDL takes AccessExclusiveLock — conflicts with standby replay immediately:

```sql
-- Primary: schedule DDL in maintenance window
-- Or use pg_replication_slots with logical decoding for zero-downtime migrations
```

For unavoidable DDL, expect standby query cancellations during lock replay.

## vacuum_defer_cleanup_age on primary

Legacy alternative to hot_standby_feedback on primary side:

```sql
vacuum_defer_cleanup_age = 1000  -- defer vacuum by 1000 transactions
```

Defers dead tuple cleanup on primary, giving standbys time to finish queries without feedback. Less precise than hot_standby_feedback — defers for all standbys uniformly. Rarely preferred in modern setups.

## Query design for replica safety

Reduce conflict surface:

```sql
-- Bad: 45-minute full table scan holding snapshot
SELECT * FROM orders o JOIN line_items li ON ... WHERE o.created_at > '2020-01-01';

-- Better: chunked reads with commits between chunks (application-level)
SELECT * FROM orders WHERE created_at BETWEEN '2026-01-01' AND '2026-01-07';
-- commit; next chunk
```

Use `SET statement_timeout` on replica role:

```sql
ALTER ROLE reporting_user SET statement_timeout = '120s';
```

Cancels long queries before they cause extended bloat feedback.

## Patroni / HA framework considerations

Failover promotion pauses standby queries entirely. After promotion, former primary rewinds — conflicts irrelevant during transition.

Read replica routing in connection poolers (PgPool-II, HAProxy):

```
Primary: writes + short reads
Replica: read-only with statement_timeout
Analytics replica: hot_standby_feedback=on, separate pool
```

## Troubleshooting runbook

**Spike in canceled queries on replica**:

1. Check `pg_stat_database_conflicts` — identify conflict type
2. Check primary for aggressive VACUUM or recent DDL
3. Identify long queries: `SELECT pid, now()-query_start, query FROM pg_stat_activity WHERE state='active'`
4. Enable hot_standby_feedback if reports must survive vacuum
5. Monitor primary bloat after enabling feedback

**Replication lag growing on replica**:

1. Check if replay is waiting: `log_recovery_conflict_waits`
2. Long conflict wait → increase max_standby_streaming_delay or kill long standby queries
3. If not conflict-related, check WAL generation rate and network

**Primary bloat after enabling hot_standby_feedback**:

1. Find long standby queries holding xmin
2. Reduce query duration or move to separate reporting instance
3. Consider disabling feedback and accepting query cancellations instead

## Measuring conflict rate over time

Track conflict counters in your monitoring system with a periodic scrape:

```sql
SELECT confl_snapshot, confl_lock, confl_bufferpin
FROM pg_stat_database_conflicts
WHERE datname = current_database();
```

Store deltas between scrapes — absolute counters are cumulative since stats reset. Alert when hourly `confl_snapshot` delta exceeds baseline by 3×, which usually correlates with a new long-running report or a schema migration introducing aggressive autovacuum on the primary.

Correlate conflict spikes with primary vacuum activity:

```sql
-- On primary during replica conflict spike
SELECT relname, last_autovacuum, n_dead_tup
FROM pg_stat_user_tables
WHERE n_dead_tup > 10000
ORDER BY n_dead_tup DESC LIMIT 10;
```

Heavy dead tuple accumulation on the primary often precedes replica query cancellations — the vacuum that cleans them triggers the conflict.

## Summary

Hot standby conflicts arise because WAL replay on replicas competes with long-running SELECT snapshots for row version visibility. Configure max_standby_streaming_delay to balance replication lag against query cancellation tolerance. Enable hot_standby_feedback when long replica queries are essential — but monitor primary bloat as the cost. For heavy analytics, a dedicated reporting replica or logical copy eliminates the conflict class entirely. Measure confl_snapshot counters, set statement timeouts on replica roles, and route workloads to the appropriate node rather than treating all replicas as interchangeable.


Never set max_standby_streaming_delay to -1 on a promote-eligible standby; unbounded wait trades query comfort for unsafe lag.
