---
title: "SQL Isolation Levels, Explained"
slug: "database-isolation-levels-explained"
description: "Read uncommitted through serializable — what each isolation level prevents, what anomalies remain, and how Postgres, MySQL, and SQL Server differ."
datePublished: "2025-08-28"
dateModified: "2025-08-28"
tags: ["Backend", "Databases", "Architecture"]
keywords: "SQL isolation levels, read committed, repeatable read, serializable, dirty read, phantom read, MVCC"
faq:
  - q: "What are SQL transaction isolation levels?"
    a: "Isolation levels define how much one transaction sees of concurrent uncommitted or committed changes from others. Higher isolation reduces anomalies (dirty reads, non-repeatable reads, phantoms) at the cost of more locking, retries, or reduced concurrency."
  - q: "What isolation level should I use by default?"
    a: "Read committed is the default in PostgreSQL and SQL Server and suits most OLTP workloads. Use repeatable read or serializable when financial invariants require stable reads within a transaction. Avoid read uncommitted in production — few engines implement it meaningfully."
  - q: "What is the difference between repeatable read and serializable?"
    a: "Repeatable read prevents other transactions from modifying rows you've read, but phantoms (new rows matching a predicate) may still appear in some databases. Serializable prevents all anomalies including phantoms, often via predicate locking or serializable snapshot isolation with abort-on-conflict."
---

Isolation levels are the dial between "fast and loose" and "correct but contentious." Most application bugs I've traced to "we assumed repeatable meant no surprises" while Postgres repeatable read still allowed certain phantom patterns until serializable — or while MySQL's repeatable read behaved differently than the SQL standard suggests on paper.

## The anomalies

| Anomaly | Description |
|---|---|
| Dirty read | Read uncommitted data another transaction rolled back |
| Non-repeatable read | Same row read twice returns different values |
| Phantom read | Same query twice returns different row sets |
| Serialization anomaly | Interleaved transactions produce impossible history |

SQL standard maps isolation levels to prevented anomalies — **implementations vary**.

## Level by level

### READ UNCOMMITTED

Sees in-flight changes. Almost no production use — Postgres treats it as read committed. SQL Server allows dirty reads with `NOLOCK` hints (dangerous).

### READ COMMITTED (default in Postgres, SQL Server)

Each statement sees committed data as of statement start (Postgres) or row version at read time. Prevents dirty reads; allows non-repeatable reads and phantoms.

```sql
-- Postgres default
BEGIN;
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
SELECT balance FROM accounts WHERE id = 1;  -- 100
-- another session commits UPDATE to 200
SELECT balance FROM accounts WHERE id = 1;  -- 200 (non-repeatable)
COMMIT;
```

Fine for most CRUD. Use explicit locking when you need stability within a transaction.

### REPEATABLE READ (MySQL InnoDB default)

Snapshot established at first read in transaction — same row returns consistent values. **Phantoms:** MySQL InnoDB repeatable read prevents phantoms via next-key locks; Postgres repeatable read may still show phantoms for predicate queries without serializable.

```sql
BEGIN ISOLATION LEVEL REPEATABLE READ;
SELECT sum(amount) FROM orders WHERE status = 'open';  -- 1000
-- concurrent insert of open order
SELECT sum(amount) FROM orders WHERE status = 'open';  -- engine-dependent
COMMIT;
```

### SERIALIZABLE

Strongest guarantee — transactions behave as if executed serially. Postgres uses **Serializable Snapshot Isolation (SSI)** — detects rw-conflicts and aborts one transaction:

```sql
BEGIN ISOLATION LEVEL SERIALIZABLE;
SELECT * FROM seats WHERE flight_id = 1 AND seat = '12A' FOR UPDATE;
INSERT INTO bookings (flight_id, seat) VALUES (1, '12A');
COMMIT;  -- may fail with serialization_failure on conflict
```

Retry on `40001` serialization failure.

## MVCC under the hood

Postgres and InnoDB keep row versions — readers don't block writers. Isolation is about **which snapshot** you see, not always about table locks. `SELECT FOR UPDATE` escalates to explicit row locks when needed.

Understanding MVCC explains why long transactions bloat storage (old versions retained) and why vacuum/undo matters.

## Choosing a level

| Use case | Level |
|---|---|
| Typical web API CRUD | Read committed |
| Report within transaction needing stable rows | Repeatable read |
| Financial ledger invariants, seat booking | Serializable + retry |
| Read-only analytics on replica | Read committed or replica lag tolerance |

Don't default entire app to serializable — throughput collapses on hot keys.

## Application patterns

**Optimistic concurrency** — version column instead of serializable:

```sql
UPDATE products
SET stock = stock - 1, version = version + 1
WHERE id = 42 AND version = 7;
-- 0 rows updated → retry or conflict error
```

**Explicit locks** when isolation alone insufficient:

```sql
SELECT * FROM inventory WHERE sku = 'ABC' FOR UPDATE;
```

**Read from replicas** — isolation on primary doesn't apply; account for replication lag.

## Testing concurrency

Stress tests with parallel transactions — property-based tests asserting invariants (balance sum constant, no double booking). Log isolation level in slow query telemetry when debugging anomalies.

## Engine cheat sheet

| Engine | Default | Notes |
|---|---|---|
| PostgreSQL | Read committed | Serializable = SSI |
| MySQL InnoDB | Repeatable read | Next-key locks |
| SQL Server | Read committed | Snapshot isolation optional |
| SQLite | Serializable | Single writer simplifies |

Read your engine's docs — the standard names don't guarantee standard behavior.

## Real-world anomaly examples

**Read committed — non-repeatable read:** Transaction A reads balance $100. Transaction B updates to $80 and commits. Transaction A reads again, sees $80. Expected at READ COMMITTED — problematic if A makes decisions assuming $100 still holds.

**Repeatable read — phantom read (MySQL):** Transaction A counts 5 open orders. Transaction B inserts order #6 and commits. Transaction A counts again — still 5 in InnoDB repeatable read (phantoms prevented for locked rows, not all cases). PostgreSQL repeatable read prevents phantoms differently via snapshot.

**Serializable — serialization failure:** Two concurrent seat bookings pass initial checks, both try to insert — PostgreSQL SSI detects conflict, one transaction aborts with `40001`. Application must retry.

Document which anomalies your product tolerates per table — not per database.

## Connection pool interactions

PgBouncer transaction pooling breaks `SET TRANSACTION ISOLATION LEVEL` if session settings don't stick across transactions. Use session pooling for serializable workloads, or set isolation in every transaction explicitly:

```sql
BEGIN ISOLATION LEVEL SERIALIZABLE;
-- work
COMMIT;
```

ORM defaults often hide isolation level — verify Hibernate `@Transactional(isolation = SERIALIZABLE)` actually propagates to JDBC.

## Debugging production anomalies

When users report "impossible" data states:

1. Check isolation level on connection (`SHOW transaction_isolation` in Postgres)
2. Review ORM flush timing — long transactions hold snapshots
3. Check replica lag if read came from follower
4. Look for application-level race without DB transaction wrapping

Pair with [database deadlock detection](https://blog.michaelsam94.com/database-deadlock-detection-prevention/) — higher isolation increases deadlock frequency.

## Production checklist

- [ ] Isolation level documented per table/use-case
- [ ] Serializable workloads use session pooling, not transaction pooling
- [ ] Optimistic concurrency with version columns on hot rows
- [ ] ORM isolation settings verified against JDBC logs
- [ ] Replica lag accounted for in read-your-writes paths

## Resources

- [PostgreSQL — Transaction Isolation](https://www.postgresql.org/docs/current/transaction-iso.html)
- [MySQL — InnoDB transaction isolation levels](https://dev.mysql.com/doc/refman/8.0/en/innodb-transaction-isolation-levels.html)
- [SQL standard isolation (Berenson et al. paper)](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/tr-95-51.pdf)
- [Martin Kleppmann — isolation anomalies explained](https://martin.kleppmann.com/2015/09/21/isolation.html)
- [Use The Index, Luke — isolation levels](https://use-the-index-luke.com/sql/misc/isolation)
