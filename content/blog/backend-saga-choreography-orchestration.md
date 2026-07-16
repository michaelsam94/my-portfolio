---
title: "Saga: Choreography vs Orchestration"
slug: "backend-saga-choreography-orchestration"
description: "Implement distributed sagas with choreography or orchestration: compensation, failure modes, and how to choose between event-driven and Temporal-style coordinators."
datePublished: "2024-12-01"
dateModified: "2024-12-01"
tags: ["Backend", "Architecture", "Distributed Systems"]
keywords: "saga pattern, choreography vs orchestration, compensating transactions, distributed transaction, microservices saga"
faq:
  - q: "What is a saga in microservices?"
    a: "A saga breaks a business transaction across services into a sequence of local transactions, each with a compensating action if a later step fails. There's no 2PC lock across services — you accept eventual consistency and design explicit undo paths (refund, release inventory, cancel reservation)."
  - q: "Choreography or orchestration — which should I pick?"
    a: "Choreography (services emit events, peers react) fits simple, stable flows with few steps. Orchestration (a coordinator tells each step what to do) fits complex branching, human waits, and visibility needs. When the flow diagram needs a whiteboard every sprint, orchestrate."
  - q: "What's the hardest part of sagas?"
    a: "Compensations that aren't perfect mirrors — partial shipping, non-idempotent refunds, and timeouts where you don't know if the remote call succeeded. Pair sagas with idempotent APIs and clear state machines; never assume compensation always restores the prior world."
---

Distributed systems don't get ACID across services. Sagas are how you still book a trip: reserve flight, reserve hotel, charge card — and unwind cleanly if the hotel is full. The fork in the road is whether services react to each other's events (choreography) or a conductor drives the steps (orchestration).

## Choreography

```
OrderService: OrderCreated
  → InventoryService: reserves stock → StockReserved
    → PaymentService: charges → PaymentCaptured
      → OrderService: marks confirmed
```

On failure, services emit failure events and others compensate. Pros: loose coupling, no central bottleneck. Cons: the flow lives only in a distributed mental model — debugging "why didn't payment run?" means tracing a scavenger hunt of topics.

Use choreography when steps are few, the happy path is stable, and each team owns clear reactions.

## Orchestration

```typescript
// Pseudocode coordinator
async function placeOrder(cmd: PlaceOrder) {
  const reservation = await inventory.reserve(cmd.items);
  try {
    await payments.charge(cmd.payment);
    await orders.markConfirmed(cmd.orderId);
  } catch (e) {
    await inventory.release(reservation.id);
    await orders.markFailed(cmd.orderId);
    throw e;
  }
}
```

Or use [Temporal](https://blog.michaelsam94.com/backend-job-scheduling-temporal/) / Step Functions so the orchestrator itself is durable. Pros: the flow is readable in one place; easier timeouts and branching. Cons: coordinator can become a god service if you put business logic that belongs in domains inside it — keep it thin.

## Compensation design

| Step | Action | Compensation |
|---|---|---|
| Reserve inventory | Hold SKUs | Release hold |
| Charge payment | Capture / auth | Refund / void |
| Create shipment | Book carrier | Cancel label |

Compensations must be **idempotent** and tolerant of "already compensated." Timeouts need a policy: if charge status is unknown, query before compensating — don't double-refund.

## Mixing both

A common compromise: orchestrate the critical path (checkout), choreograph side effects (analytics, email). Don't choreograph seven-step money movement without a state machine you can show an auditor.

Sagas trade locking for explicit recovery design. Pick choreography for simple event webs; pick orchestration when you need a single story of what the business transaction *is*.

## The saga state machine you actually need

Whether choreographed or orchestrated, every saga needs a durable record of where it is. Without it, a crash mid-compensation leaves you guessing whether inventory was released or payment was captured:

```sql
CREATE TABLE saga_instances (
  id UUID PRIMARY KEY,
  saga_type TEXT NOT NULL,
  state TEXT NOT NULL,  -- pending, compensating, completed, failed
  current_step INT NOT NULL DEFAULT 0,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE saga_step_log (
  saga_id UUID REFERENCES saga_instances(id),
  step_name TEXT NOT NULL,
  status TEXT NOT NULL,  -- started, succeeded, failed, compensated
  idempotency_key TEXT NOT NULL,
  UNIQUE (saga_id, step_name, idempotency_key)
);
```

Choreography spreads this across services (each owns its slice); orchestration centralizes it in the coordinator. Either way, support teams need one query to answer "what happened to order 48291?"

## When compensation is not a mirror

Real compensations are messy. You authorized a card but didn't capture — void, not refund. You reserved inventory but partially picked — release hold on unpicked SKUs only. You sent a confirmation email — you can't unsend it; compensation is a follow-up correction email, not a rollback. Document these as explicit policies in your saga design doc, not assumptions in code comments.

**Timeout ambiguity** is the classic saga killer. Payment service returns 504 after 30 seconds. Did the charge go through? Policy: query payment status by idempotency key before compensating. Never issue a refund for a charge that never happened — and never mark an order confirmed when the charge is still `pending`.

## Event ordering and duplicate delivery

Choreographed sagas assume events arrive in meaningful order. Kafka partitions keyed by `orderId` help, but consumers still see duplicates. Every handler must be idempotent: processing `PaymentCaptured` twice must not double-ship. Use the [idempotent consumer pattern](https://blog.michaelsam94.com/backend-idempotent-consumer-pattern/) with processed-event deduplication tables.

Out-of-order events happen when clocks skew or retries reorder. A `PaymentFailed` arriving after `PaymentCaptured` needs a version or timestamp guard — ignore stale failure events when the saga already advanced.

## Decision matrix

| Signal | Prefer choreography | Prefer orchestration |
|---|---|---|
| Steps ≤ 3, stable | ✓ | |
| Branching on business rules | | ✓ |
| Human approval gates | | ✓ |
| Cross-team ownership, loose coupling | ✓ | |
| Audit requires single execution trace | | ✓ |
| Regulatory need to show transaction flow | | ✓ |
| High fan-out side effects (analytics) | ✓ (async) | |

Hybrid is normal: orchestrate money movement, choreograph notifications and search index updates. Side effects that can lag and tolerate duplicates belong on the event bus; steps that must happen exactly once belong in the coordinator.

## Testing sagas

Unit tests aren't enough. Build scenario tests that simulate failure at each step:

1. Happy path completes all steps
2. Failure at step N triggers compensations for N-1…1 in reverse order
3. Duplicate events don't double-execute
4. Timeout at step N leaves saga in recoverable state after status query
5. Partial compensation failure escalates to manual review queue

Use test containers or in-memory brokers for choreography; Temporal's test environment replays orchestrated workflows deterministically.

## Production checklist

- Every step has a defined compensation or explicit "non-compensatable" note
- Idempotency keys on all remote calls and event handlers
- Saga state queryable by business id (order id, not internal UUID only)
- Timeouts with query-before-compensate policy on ambiguous steps
- Dead-letter queue for sagas stuck in compensating state
- Dashboards: sagas in-flight, compensation rate, mean completion time

Document the happy path and every failure branch in a single diagram pinned in the repo — future you will not reconstruct choreography from scattered event handlers at 2am.

## Resources

- [Microservices.io — Saga](https://microservices.io/patterns/data/saga.html)
- [Microsoft — Saga pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/saga)
- [Temporal — Saga example](https://docs.temporal.io/evaluating-temporal/understanding-temporal#sagas)
---
