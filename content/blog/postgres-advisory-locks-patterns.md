---
title: "Coordinating Work with Advisory Locks"
slug: "postgres-advisory-locks-patterns"
description: "Use PostgreSQL advisory locks for distributed coordination: session vs transaction locks, lock IDs, cron deduplication, and avoiding deadlocks with application-level patterns."
datePublished: "2026-03-06"
dateModified: "2026-03-06"
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

## Common production mistakes

Teams get advisory locks patterns wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Postgres work on advisory locks patterns causes outages when migrations run without `lock_timeout`, connection pools are sized for app servers not PgBouncer modes, and `EXPLAIN` plans from staging are assumed to match production statistics.

## Debugging and triage workflow

When advisory locks patterns misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [PostgreSQL advisory locks documentation](https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS)
- [PostgreSQL pg_locks view](https://www.postgresql.org/docs/current/view-pg-locks.html)
- [PgBouncer pooling modes](https://www.pgbouncer.org/features.html)
- [Flyway PostgreSQL advisory locking](https://flywaydb.org/documentation/configuration/parameters)
- [Martin Kleppmann on distributed locks](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html)
