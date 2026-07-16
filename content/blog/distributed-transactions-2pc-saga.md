---
title: "Two-Phase Commit vs Saga"
slug: "distributed-transactions-2pc-saga"
description: "2PC coordinates atomic commits across services; sagas use compensating steps. Compare protocols, failure modes, and when each fits microservices."
datePublished: "2025-10-21"
dateModified: "2025-10-21"
tags: ["Backend", "Databases", "Architecture"]
keywords: "two-phase commit, saga pattern, distributed transactions, compensating transaction, XA transactions, microservices consistency"
faq:
  - q: "What is two-phase commit (2PC)?"
    a: "Two-phase commit is a coordination protocol where a coordinator asks all participants to prepare (vote commit or abort), then sends commit or abort based on unanimous prepare votes. All participants must ack before commit completes — atomic all-or-nothing across nodes, blocking on coordinator failure."
  - q: "What is the saga pattern?"
    a: "A saga is a sequence of local transactions with compensating actions for rollback. Each service commits independently; if a later step fails, prior steps run compensating transactions (cancel reservation, refund payment). Sagas provide eventual consistency without distributed locks."
  - q: "When should I use saga instead of 2PC?"
    a: "Use sagas for long-running microservice workflows across heterogeneous stores where 2PC blocking and XA support are impractical. Use 2PC (or single-database transactions) when all participants support XA, transaction duration is short, and true atomicity is mandatory — rare across typical REST microservices."
---

"Make it atomic across three microservices" sounds like one transaction. In practice you choose between **blocking consensus** (2PC) that everyone hates operating, or **compensating workflows** (saga) that require careful idempotency design. Neither gives you free lunch.

## Two-phase commit walkthrough

**Phase 1 — Prepare:** Coordinator asks participants "can you commit?"

```
Coordinator → OrderSvc: PREPARE
Coordinator → PaymentSvc: PREPARE
Coordinator → InventorySvc: PREPARE
```

Participants write undo logs, lock resources, vote YES/NO.

**Phase 2 — Commit/Abort:** Unanimous YES → COMMIT all; any NO → ABORT all.

```
Coordinator → ALL: COMMIT
```

```sql
-- XA-style pseudo
XA START 'x1';
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
XA END 'x1';
XA PREPARE 'x1';  -- vote phase
-- coordinator decides
XA COMMIT 'x1';
```

## 2PC failure modes

- **Coordinator crash after prepare** — participants hold locks, blocked until coordinator recovers (in-doubt state)
- **Slow participants** — locks held, throughput dies
- **Mixed availability** — one NO aborts entire transaction

2PC is **consistent** but **not partition tolerant** — CP during blocking.

Modern microservices rarely expose XA across HTTP APIs.

## Saga: choreography vs orchestration

**Choreography** — events chain between services:

```
OrderCreated → PaymentRequested → PaymentCompleted → InventoryReserved
                      ↓ fail
               PaymentFailed → OrderCancelled
```

Each service knows reactions. Decentralized; hard to trace globally.

**Orchestration** — central saga coordinator:

```python
def place_order_saga(order):
    try:
        payment_id = payment.charge(order.total)
        inventory.reserve(order.items)
        order.mark_confirmed()
    except InventoryError:
        payment.refund(payment_id)
        order.mark_failed()
    except PaymentError:
        order.mark_failed()
```

Explicit flow; easier debugging; orchestrator becomes component to scale and HA.

## Compensating transactions

Forward action ≠ database rollback after commit visible externally:

| Forward | Compensate |
|---|---|
| Charge card | Refund |
| Reserve seat | Release seat |
| Ship package | Initiate return (maybe manual) |

Compensations must be **idempotent** — retry-safe:

```python
def refund(payment_id):
    if already_refunded(payment_id):
        return
    gateway.refund(payment_id)
    mark_refunded(payment_id)
```

## Comparison table

| | 2PC | Saga |
|---|---|---|
| Atomicity | Immediate all-or-nothing | Eventual via compensate |
| Isolation | Locks during prepare | No global lock |
| Duration | Short transactions | Long-running OK |
| Failure handling | Block until recovery | Forward/recover compensating |
| Cross-HTTP | Impractical | Natural |

## Outbox + saga

Reliable event publishing pairs with sagas:

```sql
BEGIN;
UPDATE orders SET status = 'pending';
INSERT INTO outbox (event_type, payload) VALUES ('OrderCreated', ...);
COMMIT;
-- relay publishes to message bus
```

Avoids "DB committed, event lost" race.

## When 2PC still appears

- Single distributed database (Spanner, Cockroach cross-region transactions)
- Legacy enterprise ESB with XA datasources
- Short-lived same-VPC database participants

Not typical greenfield REST mesh.

## Designing sagas well

- Define **happy path + every failure branch** upfront
- Unique saga ID propagated through calls
- Timeout each step; trigger compensate on timeout
- Store saga state machine (tables: saga_id, step, status)
- Monitor stuck sagas — manual intervention queue

```yaml
saga: place_order
steps:
  - charge_payment:
      compensate: refund_payment
  - reserve_inventory:
      compensate: release_inventory
  - confirm_order:
      compensate: cancel_order
```

## User experience

Saga in progress → show pending state. Compensated → clear failure message, not silent revert. Payment succeeded inventory failed → refund notification required.

## The coordinator failure problem in 2PC

2PC's Achilles heel is the coordinator. If the coordinator crashes between Phase 1 (prepare) and Phase 2 (commit), all participants hold locks in "prepared" state indefinitely:

```
Phase 1: All participants voted YES, hold locks
Coordinator: *crashes*
Participants: waiting for COMMIT or ABORT that never comes
Other transactions: blocked on locked rows
```

Recovery requires coordinator recovery with durable transaction log — participants query coordinator state on restart. This is why 2PC is considered **blocking** and why distributed databases that implement it (Spanner, CockroachDB) invest heavily in coordinator HA and fast failover.

For microservices over HTTP, there is no coordinator recovery protocol — which is why 2PC essentially doesn't exist in REST architectures.

## Saga state persistence

Every saga needs durable state — not just in-memory orchestration:

```sql
CREATE TABLE saga_executions (
  id UUID PRIMARY KEY,
  saga_type VARCHAR(100) NOT NULL,
  status VARCHAR(20) NOT NULL, -- running, completed, compensating, failed
  current_step INT NOT NULL DEFAULT 0,
  context JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE saga_step_log (
  saga_id UUID REFERENCES saga_executions(id),
  step_name VARCHAR(100) NOT NULL,
  status VARCHAR(20) NOT NULL, -- started, completed, failed, compensated
  attempt INT NOT NULL DEFAULT 1,
  started_at TIMESTAMPTZ DEFAULT now(),
  completed_at TIMESTAMPTZ
);
```

On orchestrator crash, a new worker picks up sagas in `running` or `compensating` status and resumes from `current_step`. Without this, crashes lose saga progress entirely.

## Idempotency at every saga step

Both forward actions and compensations must be idempotent:

```python
def charge_payment(saga_id, amount, idempotency_key):
    existing = db.get_payment_by_key(idempotency_key)
    if existing:
        return existing.payment_id
    return payment_gateway.charge(amount, idempotency_key=idempotency_key)

def refund_payment(saga_id, payment_id, idempotency_key):
    if db.is_refunded(idempotency_key):
        return
    payment_gateway.refund(payment_id, idempotency_key=f"refund-{idempotency_key}")
    db.mark_refunded(idempotency_key)
```

Saga retries (from crash recovery or message redelivery) re-execute steps — idempotency keys prevent double-charge and double-refund.

## Choosing between choreography and orchestration

See the detailed [saga choreography vs orchestration guide](https://blog.michaelsam94.com/backend-saga-choreography-orchestration/) for the full decision matrix. Quick summary:

- **Choreography** — few steps, stable flow, teams own their reactions
- **Orchestration** — complex branching, human waits, audit requirements
- **Temporal/Step Functions** — orchestration with durable execution (survives worker crashes)

## Testing distributed workflows

Test matrix for saga implementations:

| Scenario | Expected outcome |
|---|---|
| Happy path | All steps complete, status = completed |
| Failure at step N | Steps 1..N-1 compensated in reverse order |
| Crash mid-step | Recovery resumes from durable state |
| Duplicate event | Idempotent — no double execution |
| Timeout at step N | Compensate or escalate to manual review |
| Partial compensation failure | Saga status = failed, alert ops |

Run these as integration tests with real database transactions, not mocks.

## Failure modes

- **Non-idempotent compensation** — retry creates double refund or duplicate cancellation
- **Missing saga state persistence** — crash loses progress, manual cleanup required
- **Compensation that doesn't mirror forward action** — void vs refund confusion
- **No timeout on steps** — saga stuck in running forever
- **Using 2PC across HTTP services** — no standard protocol; use saga instead

## Production checklist

- Saga state persisted durably with step-level logging
- Every forward action and compensation is idempotent
- Timeouts defined per step with escalation policy
- Outbox pattern for reliable event publishing between steps
- Stuck saga monitoring and manual intervention queue
- Integration tests cover failure at each step
- User-facing pending/compensated states in UI

## Resources

- [microservices.io — Saga pattern](https://microservices.io/patterns/data/saga.html)
- [Google Cloud — Transaction patterns for microservices](https://cloud.google.com/architecture/partners/microservices-architecture-introduction)
- [Martin Kleppmann — Transactions chapter (DDIA)](https://dataintensive.net/)
- [Temporal.io — durable workflow orchestration](https://docs.temporal.io/workflows)
- [XA transactions — PostgreSQL two-phase commit](https://www.postgresql.org/docs/current/sql-prepare-transaction.html)
