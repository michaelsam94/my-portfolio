---
title: "Preventing Database Deadlocks"
slug: "database-deadlock-detection-prevention"
description: "Deadlocks happen when transactions wait in a cycle. Detection, lock ordering, index design, and application patterns that reduce circular waits."
datePublished: "2025-08-25"
dateModified: "2025-08-25"
tags: ["Backend", "Databases", "Architecture"]
keywords: "database deadlock, lock ordering, transaction isolation, PostgreSQL deadlock, MySQL innodb deadlock"
faq:
  - q: "What causes a database deadlock?"
    a: "A deadlock occurs when two or more transactions each hold locks the others need, forming a wait cycle. Transaction A locks row 1 and waits for row 2 while Transaction B locks row 2 and waits for row 1. The database detects the cycle and aborts one transaction as deadlock victim."
  - q: "How do databases detect deadlocks?"
    a: "Most engines maintain a wait-for graph of transactions and locks. Periodically or on each lock wait, they search for cycles. PostgreSQL's deadlock_timeout (default 1s) bounds detection delay. MySQL InnoDB detects immediately and rolls back one transaction, returning error 1213."
  - q: "What is the best way to prevent deadlocks in application code?"
    a: "Acquire locks in a consistent global order — always update rows sorted by primary key ID. Keep transactions short, avoid user interaction mid-transaction, index foreign keys, and use appropriate isolation levels. Retry deadlock victims with exponential backoff."
---

Deadlocks aren't mysterious database bugs — they're predictable outcomes when two transactions grab locks in opposite order and neither backs down. The engine picks a victim, rolls back, and your API returns 500 unless you planned for it.

## Anatomy of a classic deadlock

```sql
-- Session A
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE id = 1;  -- locks row 1
-- pause
UPDATE accounts SET balance = balance + 100 WHERE id = 2;  -- waits for row 2

-- Session B (concurrent)
BEGIN;
UPDATE accounts SET balance = balance - 50 WHERE id = 2;   -- locks row 2
UPDATE accounts SET balance = balance + 50 WHERE id = 1;   -- waits for row 1 → cycle
```

PostgreSQL returns `ERROR: deadlock detected`. MySQL `1213 Deadlock found`. Application must retry.

## Detection in production

**PostgreSQL:**

```sql
-- Recent deadlocks in logs — enable log_lock_waits, deadlock_timeout
SHOW deadlock_timeout;  -- default 1s

SELECT * FROM pg_stat_database_conflicts;
```

Check logs for `deadlock detected` detail showing both queries.

**MySQL:**

```sql
SHOW ENGINE INNODB STATUS\G
-- LATEST DETECTED DEADLOCK section
```

Enable `innodb_print_all_deadlocks` for continuous logging.

APM traces showing sudden transaction retries often correlate with deadlock spikes under load.

## Prevention: consistent lock ordering

Always lock rows in deterministic order:

```python
def transfer(from_id: int, to_id: int, amount: Decimal):
    first, second = sorted([from_id, to_id])
    with db.transaction():
        db.execute("SELECT id FROM accounts WHERE id IN (%s,%s) FOR UPDATE ORDER BY id",
                   [first, second])
        db.execute("UPDATE accounts SET balance = balance - %s WHERE id = %s",
                   [amount, from_id])
        db.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s",
                   [amount, to_id])
```

Sorting IDs eliminates cycles for pairwise updates. Generalize to lexicographic key ordering for composite entities.

## Keep transactions short

Long transactions hold locks through network calls, human approval steps, and external API requests — multiplying collision windows. Pattern:

1. Read and validate outside transaction
2. Begin transaction
3. Lock + write only
4. Commit
5. Side effects (email, queue) after commit

## Index gaps and lock escalation

Missing indexes cause **gap locks** and full table scans that lock far more than intended:

```sql
-- Bad: scans table, locks many rows
UPDATE orders SET status = 'shipped' WHERE customer_email = 'a@b.com';

-- Good: index on customer_email narrows locks
```

Foreign keys without indexes on referencing columns cause full table locks on parent deletes in some engines.

## Isolation level tradeoffs

`SERIALIZABLE` and `REPEATABLE READ` increase predicate locks and deadlock risk for throughput. Use the **lowest isolation** that correctness allows. Many apps default to `READ COMMITTED` (Postgres default) and implement optimistic concurrency for hot rows.

## Retry with backoff

Deadlock victims are safe to retry — one transaction already aborted:

```python
MAX_RETRIES = 3
for attempt in range(MAX_RETRIES):
    try:
        transfer(from_id, to_id, amount)
        break
    except DeadlockError:
        if attempt == MAX_RETRIES - 1:
            raise
        time.sleep(0.05 * (2 ** attempt) + random.uniform(0, 0.05))
```

Jitter prevents thundering herd re-deadlock.

## Design alternatives

- **Queue per aggregate** — serialize updates to same account through single worker
- **Optimistic locking** — version column, no row locks until commit conflict
- **Advisory locks** — `pg_advisory_xact_lock(hashtext('account:' || id))` for app-level ordering
- **Avoid concurrent multi-row updates** when order can't be controlled

## When deadlocks indicate design problems

Spike after launch often means new code path locks tables in different order than legacy paths. Graph lock acquisition in code review for any multi-statement transaction touching multiple entities.

Chronic deadlocks on one table — consider partitioning hot keys or splitting read/write paths.

## Reading deadlock graphs

PostgreSQL and MySQL expose deadlock victim information:

```sql
-- PostgreSQL: enable deadlock logging
SET log_lock_waits = on;
SET deadlock_timeout = '1s';
-- Check logs for: "deadlock detected" with DETAIL showing blocked queries

-- MySQL: show recent deadlock
SHOW ENGINE INNODB STATUS;
-- Look for LATEST DETECTED DEADLOCK section
```

Deadlock graph shows cycle: Transaction A waits for B's lock, B waits for A's lock. Fix by ensuring both transactions acquire locks in same order.

## Lock ordering convention

Document and enforce lock acquisition order in code review:

```python
# Always lock accounts in ascending ID order
def transfer(from_id: int, to_id: int, amount: Decimal):
    first, second = sorted([from_id, to_id])
    with db.transaction():
        lock_account(first)
        lock_account(second)
        debit(first, amount)
        credit(second, amount)
```

```python
# Enforce via advisory lock ordering
def update_entities(entity_ids: list[int]):
    for eid in sorted(entity_ids):  # always ascending
        db.execute("SELECT pg_advisory_xact_lock(%s)", (eid,))
    # now safe to update all entities
```

Any code path touching multiple rows must acquire locks in consistent order — ascending ID is the simplest convention.

## Monitoring deadlock rate

```sql
-- PostgreSQL: pg_stat_database deadlocks counter
SELECT datname, deadlocks FROM pg_stat_database WHERE datname = current_database();

-- Alert if deadlocks > 10/hour
```

Spike after deploy indicates new code path with wrong lock order. Chronic deadlocks on one table indicate hot key contention — consider queue-per-aggregate pattern.

## ORM deadlock pitfalls

```python
# Django: select_for_update without ordering
Order.objects.select_for_update().filter(id__in=order_ids)  # random order!

# Fix: always order before locking
Order.objects.select_for_update().filter(
    id__in=order_ids
).order_by('id')  # consistent lock order
```

ORMs don't enforce lock ordering — explicit `.order_by('id')` before `select_for_update()` required.

## Failure modes

- **No lock ordering convention** — different code paths deadlock each other
- **ORM select_for_update without order_by** — database returns rows in arbitrary order
- **Long transaction holding locks** — increases deadlock probability; keep transactions short
- **Deadlock rate not monitored** — spike after deploy undetected until user complaints
- **Retry without jitter** — thundering herd re-deadlock after victim abort

## Production checklist

- Lock ordering convention documented (ascending ID standard)
- All multi-row transactions acquire locks in consistent order
- ORM queries use order_by before select_for_update
- Deadlock rate monitored with alert >10/hour
- Retry with exponential backoff and jitter on deadlock victim
- Code review checks lock acquisition order for multi-entity transactions

## Resources

- [PostgreSQL — Explicit Locking](https://www.postgresql.org/docs/current/explicit-locking.html)
- [MySQL — InnoDB deadlocks](https://dev.mysql.com/doc/refman/8.0/en/innodb-deadlocks.html)
- [Microsoft SQL Server — Deadlock detection](https://learn.microsoft.com/en-us/sql/relational-databases/sql-server-deadlocks-guide)
- [Use The Index, Luke — Locking](https://use-the-index-luke.com/sql/misc/locking)
- [Martin Kleppmann — Designing Data-Intensive Applications (transactions chapter)](https://dataintensive.net/)
