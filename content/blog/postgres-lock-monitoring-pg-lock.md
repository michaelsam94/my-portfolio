---
title: "Postgres Lock Monitoring pg_locks"
slug: "postgres-lock-monitoring-pg-lock"
description: "Diagnose blocking and deadlocks with pg_locks, pg_stat_activity, and lock wait graphs — lock modes, escalation, and remediation."
datePublished: "2026-02-23"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
keywords: "pg_locks, postgres lock monitoring, blocking query, deadlock, lock wait, pg_blocking_pids"
faq:
  - q: "How do I find which query is blocking others?"
    a: "Join pg_stat_activity with pg_locks on the blocked and blocking PIDs. In PG 14+, pg_blocking_pids(pid) returns blocking backend PIDs directly. Look for blocked sessions in wait_event_type = 'Lock' and trace to the holder's query in pg_stat_activity."
  - q: "What is the difference between RowExclusiveLock and AccessExclusiveLock?"
    a: "RowExclusiveLock (INSERT/UPDATE/DELETE) conflicts with Share, ShareRowExclusive, Exclusive, and AccessExclusive. AccessExclusiveLock (ALTER TABLE, DROP, VACUUM FULL) conflicts with everything — blocks all reads and writes. DDL during peak traffic causes AccessExclusiveLock queues that cascade."
  - q: "Should I kill blocking sessions with pg_terminate_backend?"
    a: "Terminate only after confirming the blocking query is safe to interrupt — long-running analytics, forgotten idle-in-transaction, or runaway migration. Use pg_cancel_backend first for graceful query cancel; pg_terminate_backend for stuck idle-in-transaction. Document the blocking query before termination for post-incident review."
---

A single uncommitted transaction holding a row lock can stall an entire checkout pipeline. A migration grabbing AccessExclusiveLock during peak hours queues every query behind it. Postgres exposes lock state through **pg_locks** and session state through **pg_stat_activity** — but raw output is overwhelming without knowing which lock modes conflict, how to build a blocking tree, and when termination is justified.

This article provides diagnostic queries, lock mode reference, and remediation workflows used during real incidents.

## Lock mode hierarchy

Postgres lock modes from least to most restrictive:

| Mode | Typical operations | Blocks |
| --- | --- | --- |
| AccessShareLock | SELECT | AccessExclusive only |
| RowShareLock | SELECT FOR UPDATE/SHARE | Exclusive, AccessExclusive |
| RowExclusiveLock | INSERT, UPDATE, DELETE | Share, ShareRowExclusive, Exclusive, AccessExclusive |
| ShareUpdateExclusiveLock | VACUUM, CREATE INDEX CONCURRENTLY | ShareUpdateExclusive, Share, ShareRowExclusive, Exclusive, AccessExclusive |
| ShareLock | CREATE INDEX (non-concurrent) | RowExclusive and above |
| ShareRowExclusiveLock | -- rare | RowExclusive and above |
| ExclusiveLock | REFRESH MATERIALIZED VIEW CONCURRENTLY | RowShare and above |
| AccessExclusiveLock | ALTER TABLE, DROP, TRUNCUM FULL | Everything |

Most OLTP blocking involves **RowExclusiveLock** contention on hot rows or **AccessExclusiveLock** from DDL.

## Core diagnostic query

Blocking sessions with queries (PG 14+):

```sql
SELECT
  blocked.pid          AS blocked_pid,
  blocked.usename,
  blocked.application_name,
  now() - blocked.query_start AS blocked_duration,
  left(blocked.query, 100)    AS blocked_query,
  blocking.pid         AS blocking_pid,
  blocking.usename     AS blocking_user,
  now() - blocking.query_start AS blocking_duration,
  left(blocking.query, 100)   AS blocking_query,
  blocked.wait_event_type,
  blocked.wait_event
FROM pg_stat_activity blocked
CROSS JOIN LATERAL unnest(pg_blocking_pids(blocked.pid)) AS blocking_pid
JOIN pg_stat_activity blocking ON blocking.pid = blocking_pid
WHERE blocked.wait_event_type = 'Lock'
ORDER BY blocked_duration DESC;
```

Pre-PG 14 alternative using pg_locks:

```sql
SELECT
  blocked_locks.pid     AS blocked_pid,
  blocked_activity.query AS blocked_query,
  blocking_locks.pid    AS blocking_pid,
  blocking_activity.query AS blocking_query,
  blocked_activity.wait_event_type
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity
  ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks
  ON blocking_locks.locktype = blocked_locks.locktype
  AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
  AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
  AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
  AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
  AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
  AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
  AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
  AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
  AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
  AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity
  ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted
  AND blocking_locks.granted;
```

## Understanding pg_locks columns

```sql
SELECT locktype, relation::regclass, mode, granted, pid, transactionid, virtualxid
FROM pg_locks
WHERE pid = 12345;
```

| Column | Meaning |
| --- | --- |
| locktype | relation, tuple, transactionid, virtualxid, advisory |
| relation | Table/index OID (locktype=relation) |
| mode | Lock mode requested or held |
| granted | true = held; false = waiting |
| transactionid | Row-level lock via transaction ID |
| virtualxid | Lock on virtual transaction ID |

`granted = false` rows are waiting. Join to pg_stat_activity for the waiting query.

## Lock wait chains

Multi-level blocking (A blocks B blocks C):

```sql
WITH RECURSIVE lock_chain AS (
  SELECT
    pid,
    pg_blocking_pids(pid) AS blocking_pids,
    1 AS depth
  FROM pg_stat_activity
  WHERE wait_event_type = 'Lock'

  UNION ALL

  SELECT
    lc.pid,
    pg_blocking_pids(blocker),
    lc.depth + 1
  FROM lock_chain lc
  CROSS JOIN unnest(lc.blocking_pids) AS blocker
  WHERE lc.depth < 10
)
SELECT DISTINCT depth, pid FROM lock_chain ORDER BY depth;
```

The root blocker at maximum depth is the session to investigate first.

## Common blocking scenarios

### Idle in transaction

```sql
SELECT pid, state, now() - xact_start AS xact_age, query
FROM pg_stat_activity
WHERE state = 'idle in transaction'
ORDER BY xact_start;
```

Application opened transaction, did SELECT, returned connection to pool without COMMIT. Holds RowShareLock or RowExclusiveLock indefinitely.

Fix: application bug — ensure COMMIT/ROLLBACK in finally blocks. Immediate: `pg_terminate_backend(pid)`.

Prevention:

```sql
ALTER SYSTEM SET idle_in_transaction_session_timeout = '60s';
```

### Hot row updates

Concurrent UPDATE on same row — second transaction waits for first to commit:

```sql
-- Session 1
BEGIN; UPDATE inventory SET qty = qty - 1 WHERE sku = 'ABC123';
-- (no commit)

-- Session 2
UPDATE inventory SET qty = qty - 1 WHERE sku = 'ABC123';  -- waits
```

Fix: keep transactions short, optimistic locking with version column, or queue updates per SKU in application.

### DDL during traffic

```sql
ALTER TABLE orders ADD COLUMN promo_code text;
-- AccessExclusiveLock — blocks all queries on orders
```

Fix: use `ADD COLUMN ... DEFAULT ... NOT NULL` in PG 11+ (fast, minimal lock), or `CREATE INDEX CONCURRENTLY` instead of blocking index creation. Schedule DDL in maintenance windows for operations that require AccessExclusiveLock.

### Foreign key checks

INSERT into child waits for parent row lock held by uncommitted transaction on parent table.

### Advisory locks

Application-level locks:

```sql
SELECT pid, locktype, classid, objid, mode, granted
FROM pg_locks
WHERE locktype = 'advisory';
```

Used by migrations (Rails, Flyway), job schedulers, manual `pg_advisory_lock()`. Stuck advisory lock blocks next deploy.

Release:

```sql
SELECT pg_advisory_unlock_all();  -- current session only
SELECT pg_terminate_backend(pid); -- holder session
```

## Deadlock detection

Postgres automatically detects deadlocks and cancels one transaction:

```
ERROR: deadlock detected
DETAIL: Process 12345 waits for ShareLock on transaction 67890; blocked by process 54321...
```

Log deadlocks:

```
log_lock_waits = on
deadlock_timeout = '1s'
```

Inspect deadlock graph in logs. Application should retry on `40P01` SQLSTATE.

Reduce deadlocks:

- Consistent lock ordering across transactions (always lock rows by ID ascending)
- Shorter transactions
- Lower isolation level where serializable is unnecessary

## Remediation actions

**Cancel query** (graceful — transaction continues):

```sql
SELECT pg_cancel_backend(12345);
```

**Terminate session** (rollback transaction):

```sql
SELECT pg_terminate_backend(12345);
```

**Kill idle in transaction** (batch):

```sql
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND now() - xact_start > interval '5 minutes'
  AND usename NOT IN ('postgres', 'replication');
```

Always record blocking query and application_name before termination for post-incident review.

## Monitoring and alerting

Prometheus postgres_exporter metrics:

- `pg_locks_count` by mode
- `pg_stat_activity_max_tx_duration`
- Custom query for `count(*) WHERE wait_event_type = 'Lock'`

Alert when:

- Lock wait count > 10 for 2 minutes
- Any `idle in transaction` older than 5 minutes
- `AccessExclusiveLock` waiting (granted=false) during business hours

Dashboard query for lock wait rate:

```sql
SELECT count(*) FILTER (WHERE wait_event_type = 'Lock') AS waiting,
       count(*) AS total
FROM pg_stat_activity
WHERE backend_type = 'client backend';
```

## Preventive schema and application design

- **Short transactions**: fetch data, decide, write — no user think time inside TX
- **Skip locked rows** for non-critical updates: `FOR UPDATE SKIP LOCKED`
- **Optimistic concurrency**: `UPDATE ... WHERE id = $1 AND version = $2`
- **Partition hot tables**: reduce lock contention scope
- **CONCURRENTLY** for index creation and rebuilds
- **lock_timeout** on migrations: `SET lock_timeout = '5s'` — fail fast instead of queue

```sql
-- Migration session
SET lock_timeout = '5s';
SET statement_timeout = '300s';
ALTER TABLE ... ;
```

## pg_locks vs pg_stat_progress

For VACUUM and CREATE INDEX progress, use `pg_stat_progress_vacuum` and `pg_stat_progress_create_index` — not pg_locks. Lock monitoring complements progress views during long maintenance.

## On-call lock triage cheat sheet

Keep this sequence visible in your runbook:

| Step | Action | Query |
| --- | --- | --- |
| 1 | Count lock waits | `SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock'` |
| 2 | Find blockers | `SELECT * FROM ... pg_blocking_pids ...` (full query above) |
| 3 | Classify blocker | idle in transaction → terminate; DDL → wait or cancel migration; hot row → app fix |
| 4 | Check duration | `now() - xact_start` on blocker |
| 5 | Terminate if safe | `pg_cancel_backend` first, then `pg_terminate_backend` |
| 6 | Verify recovery | Lock wait count returns to zero |

Post-incident: if idle-in-transaction caused the block, grep application code for missing COMMIT. If DDL caused it, add lock_timeout to migration tooling.

## Summary

pg_locks combined with pg_stat_activity reveals who blocks whom and why. Use pg_blocking_pids on PG 14+ for fast blocking trees, distinguish RowExclusive contention from AccessExclusive DDL disasters, and terminate idle-in-transaction sessions aggressively with timeout configuration. Prevent blocking with short transactions, lock_timeout on migrations, CONCURRENTLY operations, and application-level retry on deadlocks. Lock monitoring is not optional infrastructure — it is the primary diagnostic during database-related incidents.


Set lock_timeout on migration sessions so DDL fails fast instead of becoming the head of an invisible lock queue that 503s the app.
