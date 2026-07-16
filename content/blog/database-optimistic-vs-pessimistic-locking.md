---
title: "Optimistic vs Pessimistic Locking"
slug: "database-optimistic-vs-pessimistic-locking"
description: "Pessimistic locks hold rows upfront; optimistic locks detect conflicts at commit. When each fits, version columns, SELECT FOR UPDATE, and lost update prevention."
datePublished: "2025-09-03"
dateModified: "2025-09-03"
tags: ["Backend", "Databases", "Architecture"]
keywords: "optimistic locking, pessimistic locking, SELECT FOR UPDATE, version column, lost update problem, concurrency control"
faq:
  - q: "What is pessimistic locking?"
    a: "Pessimistic locking acquires row or table locks before modifying data — typically SELECT FOR UPDATE — preventing other transactions from changing those rows until commit. Use when contention is high and conflicts are expensive to retry, such as inventory deduction or seat reservation."
  - q: "What is optimistic locking?"
    a: "Optimistic locking assumes conflicts are rare. Reads proceed without locks; updates include a version or timestamp check so the database rejects writes if another transaction modified the row first. The application retries or returns a conflict error to the user."
  - q: "When should I choose optimistic over pessimistic locking?"
    a: "Choose optimistic for read-heavy entities with low write collision rates — user profile edits, document updates. Choose pessimistic for scarce resources with high collision — ticket inventory, wallet balances, sequential ID generation under load."
---

Two users edit the same record. One saves. The other's changes silently overwrite the first — the classic lost update. Locking strategy decides whether you prevent collisions upfront or detect them at commit time.

## Lost update demonstrated

```sql
-- Both read balance = 100
-- Tx A: SET balance = 100 - 30 → 70
-- Tx B: SET balance = 100 - 20 → 80  (based on stale read)
-- Final balance 80; A's withdrawal vanished
```

Fix requires either locking during read-modify-write or conditional update on version.

## Pessimistic locking

Lock rows before update:

```sql
BEGIN;
SELECT id, balance FROM accounts WHERE id = 42 FOR UPDATE;
-- row locked until commit
UPDATE accounts SET balance = balance - 30 WHERE id = 42;
COMMIT;
```

`FOR UPDATE` blocks other writers (and other `FOR UPDATE` readers) on those rows. `FOR UPDATE SKIP LOCKED` processes first available rows — useful for job queues:

```sql
SELECT * FROM jobs
WHERE status = 'pending'
ORDER BY created_at
FOR UPDATE SKIP LOCKED
LIMIT 1;
```

**Pros:** deterministic serialization on hot rows.

**Cons:** holds connections and locks during slow logic; deadlock risk if lock order inconsistent; reduced throughput under contention.

## Optimistic locking

Add version column:

```sql
CREATE TABLE documents (
  id UUID PRIMARY KEY,
  title TEXT,
  body TEXT,
  version INT NOT NULL DEFAULT 1
);
```

Update with version check:

```sql
UPDATE documents
SET title = $1, body = $2, version = version + 1
WHERE id = $3 AND version = $4;
-- rowcount 0 → conflict, reload and retry
```

ORMs expose this (`@Version` in JPA, Ecto optimistic locking). No locks during read — better concurrency when collisions are rare.

**Pros:** no long-held locks, scales read-heavy workloads.

**Cons:** retries under write storms; user-facing conflict UX needed.

## Hybrid patterns

**Short pessimistic + optimistic fallback** — try optimistic once, escalate to lock on repeated conflict.

**Compare-and-set on single column:**

```sql
UPDATE inventory SET qty = qty - 1 WHERE sku = 'X' AND qty > 0;
```

No version column; atomic decrement prevents oversell if check and update are one statement.

## Choosing for your domain

| Scenario | Strategy |
|---|---|
| Seat booking, limited tickets | Pessimistic or atomic conditional update |
| Wiki page edit | Optimistic with merge UI |
| Bank transfer between accounts | Pessimistic with ordered locks |
| Analytics flag on user | Optimistic or last-write-wins if acceptable |
| Distributed system across services | Saga + idempotency, not DB lock alone |

## ORM pitfalls

Long `@Transactional` service methods holding pessimistic locks through HTTP calls to payment gateways — move external I/O outside transaction.

Optimistic locking disabled by default in some ORMs — lost updates return unless you enable version fields.

Read-modify-write in application without either strategy still races.

## User experience on conflict

Optimistic failure should surface clearly:

```json
HTTP 409 Conflict
{ "error": "document_modified", "current_version": 5, "reload": true }
```

Pessimistic timeout → queue or "try again" rather than infinite wait.

## Testing

Concurrent integration tests spawning threads/processes updating same row. Assert invariants (inventory never negative, version monotonic). Chaos tests with random delays expose lock ordering bugs.

## Distributed systems: neither works alone

Database locks don't span microservices. Cross-service inventory deduction needs:

- **Saga with reservation** — optimistic hold, confirm or release
- **Idempotency keys** — retry-safe operations
- **Outbox pattern** — reliable event delivery between services

```python
# Cross-service: optimistic reservation pattern
def reserve_inventory(order_id, sku, qty):
    result = db.execute("""
        UPDATE inventory SET reserved = reserved + :qty
        WHERE sku = :sku AND available - reserved >= :qty
    """, {"sku": sku, "qty": qty})
    if result.rowcount == 0:
        raise InsufficientStock()
    outbox.publish(InventoryReserved(order_id, sku, qty))
```

Local optimistic update + outbox event — no distributed lock required.

## Performance characteristics

| Scenario | Optimistic | Pessimistic |
|---|---|---|
| Low contention | Fast (no lock wait) | Lock acquisition overhead |
| High contention | Many retries/failures | Queue at lock |
| Long transactions | Version conflicts | Blocks other readers/writers |
| Read-heavy | No impact on reads | SELECT FOR UPDATE blocks reads |

Measure conflict rate on optimistic paths — if >10% of transactions fail with version conflict, consider pessimistic for that hot row.

## Failure modes

- **Optimistic without version column** — lost updates silently
- **Pessimistic lock held during HTTP call** — blocks all other transactions for seconds
- **Deadlock from unordered lock acquisition** — always lock rows in consistent order (by ID)
- **Distributed transaction assumed** — 2PC across services; use saga instead
- **No conflict UX** — optimistic failure returns generic 500 instead of 409 with reload

## Production checklist

- Locking strategy documented per entity (optimistic vs pessimistic)
- Version column on optimistically locked tables
- Partial unique indexes for soft-deleted entities
- Lock ordering convention for multi-row pessimistic locks
- External I/O outside pessimistic transaction boundaries
- 409 Conflict response with current version on optimistic failure
- Concurrent integration tests for hot-row contention

## Common production mistakes

Teams get optimistic vs pessimistic locking wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Data pipelines for optimistic vs pessimistic locking silently corrupt when schema evolution is backward-incompatible, late-arriving events are dropped, and warehouse costs spike because nobody partitions by query pattern.

## Debugging and triage workflow

When optimistic vs pessimistic locking misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [PostgreSQL — Row Locking](https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-ROWS)
- [Hibernate — Optimistic locking](https://docs.jboss.org/hibernate/orm/current/userguide/html_single/Hibernate_User_Guide.html#locking-optimistic)
- [MySQL — InnoDB locking reads](https://dev.mysql.com/doc/refman/8.0/en/innodb-locking-reads.html)
- [Microsoft — Concurrency control patterns](https://learn.microsoft.com/en-us/azure/architecture/patterns/category/concurrency)
- [Use The Index, Luke — Optimistic Concurrency](https://use-the-index-luke.com/)
