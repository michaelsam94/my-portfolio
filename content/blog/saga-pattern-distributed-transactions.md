---
title: "The Saga Pattern for Distributed Transactions"
slug: "saga-pattern-distributed-transactions"
description: "The saga pattern for distributed transactions: choreography vs orchestration, compensating actions, and keeping microservices consistent without 2PC."
datePublished: "2026-01-19"
dateModified: "2026-01-19"
tags: ["Backend", "Architecture", "Distributed Systems"]
keywords: "saga pattern, distributed transactions, choreography, orchestration saga, compensating transactions, eventual consistency"
faq:
  - q: "What is the saga pattern?"
    a: "The saga pattern is a way to manage a business transaction that spans multiple services, where a single ACID transaction is impossible. It models the transaction as a sequence of local transactions, each in one service, and defines a compensating action for each step that semantically undoes it if a later step fails. Instead of atomic all-or-nothing behavior, a saga guarantees that the system either completes every step or compensates the ones that already ran, reaching a consistent end state through eventual consistency."
  - q: "What is the difference between choreography and orchestration sagas?"
    a: "In a choreography saga, each service reacts to events published by other services and emits its own events, with no central coordinator — the workflow is emergent from the event choreography. In an orchestration saga, a central orchestrator explicitly tells each service what to do and tracks the saga's state. Choreography is decoupled and simple for short flows but hard to follow as it grows; orchestration centralizes the logic, making complex flows visible and debuggable at the cost of a coordinator component."
  - q: "Why not just use two-phase commit for distributed transactions?"
    a: "Two-phase commit (2PC) provides atomicity across services but requires all participants to hold locks while waiting for the coordinator, which blocks resources, scales poorly, and fails badly if the coordinator dies mid-commit. It also assumes all participants support distributed transactions, which most modern services and databases don't. Sagas trade 2PC's strong atomicity for availability and loose coupling, accepting eventual consistency and compensations instead of locks and blocking."
---

Once a business operation touches more than one service, the database transaction you relied on for correctness disappears. You can't wrap "reserve inventory, charge the card, create the shipment" in a single `BEGIN`/`COMMIT` when those three things live in three services with three databases. The saga pattern is the standard answer: model the operation as a sequence of local transactions, and for each step define a **compensating action** that semantically undoes it, so that if step three fails you can walk back steps two and one. You give up atomic all-or-nothing in exchange for a system that either finishes or cleans up after itself.

I've built these for order flows and payment pipelines, and the pattern is genuinely good — but it's also where I've seen teams underestimate the work, because "compensation" is a design problem, not a library you install. Here's how sagas actually work and the decisions that determine whether yours stays maintainable.

## Why the ACID transaction is gone

In a monolith with one database, consistency is nearly free — the database gives you atomicity, and a failed step rolls back everything automatically. Split the operation across services and that guarantee evaporates. The textbook fix, **two-phase commit (2PC)**, coordinates a distributed atomic commit, but it's a poor fit for microservices: participants hold locks while awaiting the coordinator's decision, throughput craters under contention, and a coordinator crash between "prepare" and "commit" can leave participants blocked indefinitely. On top of that, most modern datastores and third-party APIs don't even support enlisting in a distributed transaction.

So the industry largely abandoned 2PC for service-to-service work and embraced **eventual consistency**: accept that the system passes through inconsistent intermediate states and guarantee it converges to a consistent end state. The saga is the concrete mechanism for that guarantee.

## Compensations are the hard part

The core primitive is the compensating transaction. For every forward step `Tn`, you write a `Cn` that undoes its effect. Crucially, compensation is **semantic, not literal** — you rarely "roll back," you take a new action that corrects the world.

Consider an order saga:

| Forward step | Compensating action |
| --- | --- |
| Reserve inventory | Release inventory reservation |
| Charge payment | Refund payment |
| Create shipment | Cancel shipment |

Notice that "refund payment" is not the inverse of "charge payment" — money moved, was recorded, maybe triggered a receipt email. The compensation is a *new business fact*, not a rollback. This is where sagas get subtle: some actions are hard or impossible to compensate cleanly (you can't un-send a physical package that already left). The senior move is to **order your steps so the hardest-to-undo action comes last**, minimizing the compensation surface. Reserve-then-charge-then-ship is deliberate: shipping is nearly irreversible, so it goes last, and by then everything before it succeeded.

Every step and every compensation must also be **idempotent**, because in a distributed system messages get redelivered and steps get retried. If "release inventory" runs twice it must not release twice. This is the same non-negotiable I keep hammering in [idempotency for distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/) — sagas simply don't work without it.

## Choreography: events, no conductor

There are two ways to coordinate the steps. In a **choreography** saga, there's no central controller. Each service listens for events and emits its own, and the workflow emerges from the chain of reactions:

```text
OrderService   --OrderCreated-->        InventoryService
InventoryService --InventoryReserved-->  PaymentService
PaymentService --PaymentCharged-->       ShippingService
PaymentService --PaymentFailed-->        InventoryService (compensate)
```

Each service reliably publishes its events — almost always via the [event-driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/) so the local transaction and the event publication are atomic. Choreography is beautifully decoupled: no service knows the whole flow, and adding a participant can be as simple as subscribing to an event.

The downside shows up as the saga grows. With six or seven services reacting to each other, **no single place describes the workflow**. Debugging "why didn't the shipment get created?" means tracing events across many services, and cyclic event dependencies can sneak in. Choreography is my default for short flows (2–4 steps); past that, the emergent complexity turns into a liability.

## Orchestration: a central brain

In an **orchestration** saga, a dedicated orchestrator owns the workflow. It calls each service (or sends commands), tracks the saga's state in a durable store, and decides what to do next — including triggering compensations in reverse order on failure:

```python
class OrderSaga:
    def run(self, order):
        try:
            self.inventory.reserve(order.id, order.items)      # T1
            self.payment.charge(order.id, order.total)         # T2
            self.shipping.create(order.id, order.address)      # T3
            self.state.mark_completed(order.id)
        except StepFailed as e:
            self.compensate(order, failed_at=e.step)           # run C(n-1)..C1

    def compensate(self, order, failed_at):
        if failed_at > 2: self.payment.refund(order.id)        # C2
        if failed_at > 1: self.inventory.release(order.id)     # C1
        self.state.mark_compensated(order.id)
```

The orchestrator's state must be persisted at every transition so it can resume after a crash mid-saga — the orchestrator itself has to be crash-recoverable, which is the main new burden this style introduces. In return you get a single, readable definition of the workflow, easy visibility into where any saga is stuck, and a natural home for timeouts and retries. For complex, long-running, or auditable flows, orchestration wins decisively, which is why tools like Temporal, AWS Step Functions, and Camunda exist to be that durable orchestrator.

## Choosing, and living with, a saga

My rule of thumb:

- **Choreography** for short, stable flows where decoupling matters and the step count stays small.
- **Orchestration** for complex flows, anything with more than ~4 steps, long-running processes, or where you need to *see* and audit saga state. Use a purpose-built engine rather than hand-rolling durable state.

And two hard truths regardless of style. First, **the intermediate states are visible.** During the saga, inventory is reserved but not yet paid; a user might see an order that's "processing" for seconds. Your UI and your other reads must tolerate these in-between states — that's the price of dropping ACID. Second, **compensation can itself fail.** What happens when the refund API is down during compensation? You need retries, alerting, and ultimately a human-review dead-letter path for sagas that can neither complete nor compensate. Pretending compensation always succeeds is the most common way I see saga implementations quietly leave money and inventory in wrong states.

Used with eyes open, the saga pattern is the right tool for cross-service consistency — it trades the impossible dream of distributed atomicity for a pragmatic, recoverable, eventually-consistent workflow. The pattern is straightforward; the discipline it demands around idempotency, compensation design, and failure-of-failure handling is what separates a robust implementation from a demo.

## Resources

- [microservices.io — Saga pattern](https://microservices.io/patterns/data/saga.html)
- [Temporal documentation](https://docs.temporal.io/)
- [AWS Step Functions developer guide](https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html)
- ["Sagas" — Garcia-Molina & Salem (1987)](https://www.cs.cornell.edu/andru/cs711/2002fa/reading/sagas.pdf)
- [microservices.io — Transactional outbox](https://microservices.io/patterns/data/transactional-outbox.html)
- [Camunda: orchestration vs choreography](https://camunda.com/blog/2023/02/orchestration-vs-choreography/)
