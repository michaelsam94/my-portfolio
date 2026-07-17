---
title: "Coordinating Work with Advisory Locks"
slug: "postgres-advisory-locks-patterns"
description: "Use PostgreSQL advisory locks for distributed coordination: session vs transaction locks, lock IDs, cron deduplication, and avoiding deadlocks with application-level patterns."
datePublished: "2026-03-06"
dateModified: "2026-07-17"
tags: ["PostgreSQL", "Backend", "Database", "Distributed Systems"]
keywords: "PostgreSQL advisory locks, pg_advisory_lock, distributed lock Postgres, cron deduplication, advisory lock patterns"
faq:
  - q: "When should you use PostgreSQL advisory locks instead of Redis locks?"
    a: "When you already depend on Postgres for the operation being coordinated — migrations, batch jobs writing to the same tables, or single-leader cron in small deployments. Advisory locks avoid adding Redis infrastructure but tie lock availability to database connectivity and don't work across unrelated databases."
  - q: "What is the difference between session and transaction advisory locks?"
    a: "Session locks (`pg_advisory_lock`) persist until explicitly released or the connection closes — dangerous with connection pooling. Transaction locks (`pg_advisory_xact_lock`) release automatically at COMMIT or ROLLBACK — preferred for most application patterns."
  - q: "Can advisory locks deadlock?"
    a: "Yes, if different sessions acquire multiple lock IDs in inconsistent order. Use a single lock ID per resource, consistent ordering across code paths, and `pg_try_advisory_xact_lock` with timeout fallback for non-blocking attempts."
---

Three Kubernetes cron pods fired the same nightly aggregation job. Without coordination, they triple-wrote reports and corrupted summary tables. Redis wasn't in this cluster — just Postgres. Advisory locks solved it in twenty lines: one lock ID, `pg_advisory_xact_lock`, first pod wins, others exit cleanly.

Postgres advisory locks are application-defined mutexes stored in the database engine. No table, no row lock on business data — just integer keys the app agrees on.

## Lock types

| Function | Scope | Release |
|----------|-------|---------|
| `pg_advisory_lock(key)` | Session | Manual unlock or disconnect |
| `pg_advisory_xact_lock(key)` | Transaction | COMMIT/ROLLBACK |
| `pg_try_advisory_xact_lock(key)` | Transaction | Returns false if busy |

Prefer **transaction-scoped** locks — connection pool return won't accidentally hold locks across requests.

Two-key variant maps string names to 64-bit IDs:

```sql
SELECT pg_advisory_xact_lock(hashtext('nightly_aggregation'));
-- or two-int key for lower collision risk
SELECT pg_advisory_xact_lock(42, 1);
```

`hashtext()` is convenient; for high-stakes locks use explicit namespace integers (`(service_id, job_id)`).

## Cron deduplication pattern

```python
def run_nightly_aggregation():
    with db.transaction():
        acquired = db.execute(
            "SELECT pg_try_advisory_xact_lock(%s, %s)",
            (NAMESPACE_JOBS, JOB_AGGREGATION)
        ).scalar()
        if not acquired:
            logger.info("Another worker running aggregation, skipping")
            return

        aggregate_daily_metrics()  # long job inside same transaction? NO — see below
```

**Don't run long jobs inside the lock transaction.** The lock transaction should only acquire the lock and insert a "job started" row; commit; do work; start new transaction to mark complete. Or use session lock with careful pool handling.

Better pattern:

```python
with db.transaction():
    if not try_xact_lock(NAMESPACE, JOB_ID):
        return
    db.execute("INSERT INTO job_runs (job, started_at) VALUES (%s, now())", (JOB_ID,))

# lock released on commit — use job_runs uniqueness for dedup
do_long_work()
```

Combine advisory lock ( thundering herd prevention) with unique constraint on `job_runs(job, date)` ( correctness backstop).

## Migration coordination

Multiple deploy pods running Flyway simultaneously — advisory lock as migration mutex:

```sql
-- Flyway supports PostgreSQL advisory lock out of the box via pg_advisory_lock
-- Custom scripts:
SELECT pg_advisory_lock(72707369);  -- Flyway's chosen lock key
-- run migrations
SELECT pg_advisory_unlock(72707369);
```

Flyway handles this internally; raw SQL migration tools should copy the pattern.

## Session locks with connection pooling caution

PgBouncer transaction pooling breaks session locks — connection returns to pool while lock held by ghost session. Use:

- PgBouncer **session mode** for lock-holding connections, or
- Transaction locks only, or
- Locks in direct-to-Postgres connections bypassing pooler

We hit production deadlock from session lock + PgBouncer transaction mode — on-call classic.

## Avoiding deadlocks

Two jobs acquiring locks `(1,2)` then `(2,1)` — Postgres detects and aborts one transaction. Prevention:

```python
LOCK_ORDER = sorted([resource_a, resource_b])
for key in LOCK_ORDER:
    pg_advisory_xact_lock(key)
```

Single lock per logical resource is simplest — namespace by job type, not per shard, unless shards truly independent.

## Monitoring

```sql
SELECT * FROM pg_locks WHERE locktype = 'advisory';
```

Alert on advisory locks held longer than expected — indicates stuck job or connection leak.

`pg_stat_activity` joined with `pg_locks` shows which application holds lock.

## vs dedicated lock services

| Approach | Pros | Cons |
|----------|------|------|
| Advisory locks | No extra infra, ACID with DB work | DB dependency, pooling pitfalls |
| Redis Redlock | Fast, familiar | Extra system, debated correctness |
| DB row lock (`SELECT FOR UPDATE`) | Visible in business table | Couples lock to schema |

Advisory locks win for small-to-medium systems already on Postgres. At multi-region scale with complex fencing token requirements, evaluate dedicated coordination (etcd, DynamoDB conditional writes).

## Fencing tokens consideration

Advisory locks do not provide fencing — a delayed worker can complete after lock released and corrupt state. For financial correctness, pair lock with version column compare-and-swap or use a system designed for distributed consensus when true exclusion with fencing is required.

## Operational notes

Document lock ID allocation in a central registry spreadsheet or internal wiki table — namespace integer ranges per team prevent two services colliding on lock key 42 without knowing it.

Load test lock contention scenarios — two workers racing for same lock ID should show one winner and clean skip path, not connection pool exhaustion from blocked workers waiting indefinitely.

Include advisory lock acquisition in structured application logs with lock namespace and job ID — debugging production skips without logs reduces to guessing which cron won the race.


## Session vs transaction advisory locks

pg_advisory_lock survives until disconnect — dangerous with PgBouncer transaction mode. Prefer pg_advisory_xact_lock scoped to transaction — auto-releases on commit/rollback.

## Lock key namespace design

Encode domain in high bits, entity id in low bits via hashtext. Document namespace table — two features hashing to same key space deadlock each other.

## Non-blocking try locks for cron

pg_try_advisory_lock — if false, another pod running nightly report. Leader election without ZooKeeper for single-row jobs.

## Debugging lock waits

pg_locks joined with pg_stat_activity shows advisory lock holders. wait_event advisory in activity view — correlate with long-running batch holding lock during business hours.

## Advisory locks vs row-level locks for job queues

SKIP LOCKED on rows competes with advisory locks for job dequeue. Advisory locks lighter when no row exists yet (schedule slot reservation before insert). Combine: advisory lock per resource during booking flow, row lock on confirm — see exclusion constraint post for final persist.

## Timeout handling in application

Wrap pg_advisory_xact_lock in SET LOCAL lock_timeout = '2s' — fail fast to user rather than hang connection pool. Map lock timeout SQLSTATE to HTTP 503 with Retry-After when contention expected (flash sale inventory).

## pg_advisory_lock key generation

Avoid raw integer keys from user input — hash strings to int64 with hashtext or application-side FNV. Collision across namespaces causes mysterious blocking — document namespace prefix in lock key high bits: `(namespace_id << 32) | resource_id`.

## Observability for lock waits

pg_stat_activity wait_event_type Lock with wait_event advisory — export to Prometheus via postgres_exporter. Alert when advisory wait count >10 for 5 minutes during business hours; often cron overlap or stuck transaction holding lock without timeout.

## Comparison with SELECT FOR UPDATE SKIP LOCKED

Job queue dequeue uses SKIP LOCKED on status=pending rows — advisory locks when no row yet exists to lock (hold slot before insert). Choose advisory for reservation phase, row lock for commit phase in two-phase booking flow.

## Benchmark: advisory vs row lock latency

pgbench custom script comparing pg_advisory_xact_lock vs SELECT FOR UPDATE on dummy row — advisory typically lower overhead when no row exists yet. Document benchmark in ADR choosing advisory for pre-insert slot hold pattern in scheduling service before exclusion constraint added on commit.

## Closing notes

Document lock key namespace in service README table: key type, hashtext input, timeout, and SQLSTATE mapping so on-call resolves contention without reading application source during incident.

## Additional guidance

Session-level advisory locks survive PgBouncer only in session pooling mode — document pool mode in runbook next to any feature using pg_advisory_lock without xact scope. Migration from session to transaction pooling requires refactoring session locks to xact locks or row locks to avoid silent lock loss between transactions.

Load test advisory lock hold duration under peak booking — lock held through slow external payment callback blocks other bookers; shorten critical section to database commit only and move payment wait outside lock scope when measuring contention metrics before choosing advisory versus exclusion constraint approach.

Prefer pg_advisory_xact_lock over session lock whenever PgBouncer transaction pooling is enabled — document in database platform standards.

Set lock_timeout on transactions taking advisory xact lock — fail fast with retryable error instead of holding connection pool slot indefinitely during flash sale contention.

## Resources

- [PostgreSQL advisory locks documentation](https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS)
- [PostgreSQL pg_locks view](https://www.postgresql.org/docs/current/view-pg-locks.html)
- [PgBouncer pooling modes](https://www.pgbouncer.org/features.html)
- [Flyway PostgreSQL advisory locking](https://flywaydb.org/documentation/configuration/parameters)
- [Martin Kleppmann on distributed locks](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html)
