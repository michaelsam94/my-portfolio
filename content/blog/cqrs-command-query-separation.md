---
title: "CQRS in Practice"
slug: "cqrs-command-query-separation"
description: "Apply Command Query Responsibility Segregation with separate read and write models, event sourcing options, and pragmatic boundaries in backend services."
datePublished: "2025-05-09"
dateModified: "2025-05-09"
tags: ["Backend", "Architecture"]
keywords: "CQRS, command query separation, read model, write model, event sourcing, backend architecture"
faq:
  - q: "What is CQRS?"
    a: "CQRS separates the model and paths for writes (commands that change state) from reads (queries that return data). Commands enforce business rules and update the write store; queries read from optimized read models that may denormalize data for display. The two sides can use different databases, schemas, and scaling strategies."
  - q: "When is CQRS worth the complexity?"
    a: "CQRS pays off when read and write patterns diverge sharply—high-write event ingestion with complex dashboard queries, collaborative editing with heavy read projections, or systems needing independent scaling of read replicas. Skip it for simple CRUD apps where one normalized schema serves both paths fine."
  - q: "Does CQRS require event sourcing?"
    a: "No. CQRS works with traditional CRUD write stores that update read models synchronously or asynchronously. Event sourcing stores state as event log and is often paired with CQRS because projections rebuild read models from events—but combining both is the heavy form; adopt incrementally."
---

CRUD on one database table works until your product manager wants a dashboard aggregating data from six tables with sub-second load times while writes spike to ten thousand orders per minute. CQRS says stop pretending one model fits both jobs—optimize writes for correctness, optimize reads for queries users actually run. The pattern is often over-applied to todo apps and under-applied to systems drowning in read replica lag. Pragmatic CQRS draws a boundary, not a religion.

## Commands vs queries

**Command** — intent to change state; may fail validation; returns success/failure, not domain data:

```kotlin
data class PlaceOrderCommand(
    val customerId: UUID,
    val items: List<OrderLine>,
)

sealed class CommandResult {
    data object Success : CommandResult()
    data class Rejected(val reason: String) : CommandResult()
}
```

**Query** — no side effects; returns DTOs tailored to UI:

```kotlin
data class OrderSummaryView(
    val orderId: UUID,
    val status: String,
    val totalDisplay: String,
    val lineItems: List<LineItemView>,
)
```

Naming matters: `PlaceOrder` not `CreateOrderAndReturnOrderDto`.

## Simple CQRS without event sourcing

```
POST /orders  → CommandHandler → Write DB (normalized)
                      │
                      ▼ async or sync
                 Read DB (denormalized OrderSummaryView)
GET /orders/:id → QueryHandler → Read DB
```

Write path:

```kotlin
class PlaceOrderHandler(
    private val writeRepo: OrderWriteRepository,
    private val readProjector: OrderReadProjector,
) {
    fun handle(cmd: PlaceOrderCommand): CommandResult {
        val order = Order.create(cmd) ?: return CommandResult.Rejected("Invalid items")
        writeRepo.save(order)
        readProjector.project(order)  // update read table
        return CommandResult.Success
    }
}
```

Read model table:

```sql
CREATE TABLE order_summary_view (
    order_id UUID PRIMARY KEY,
    customer_id UUID,
    status TEXT,
    total_cents BIGINT,
    items_json JSONB,
    updated_at TIMESTAMPTZ
);
CREATE INDEX idx_order_customer ON order_summary_view(customer_id);
```

Dashboard queries hit one table—no joins at read time.

## Async projection

Decouple with message queue when write latency must stay low:

```
CommandHandler → Write DB → publish OrderPlaced event
                                │
                                ▼
                         ProjectionWorker → Read DB
```

Eventual consistency: reads may lag milliseconds to seconds—UI handles with "processing" state or version polling.

Idempotent projections: replay events safely with upsert keyed by order ID.

## Event sourcing + CQRS (advanced)

Write store is append-only event log:

```kotlin
sealed class OrderEvent {
    data class Created(val id: UUID, val lines: List<OrderLine>) : OrderEvent()
    data class Paid(val id: UUID, val paymentId: String) : OrderEvent()
    data class Shipped(val id: UUID, val tracking: String) : OrderEvent()
}
```

Aggregate rebuilds from events; read models project from same stream. Enables audit trail and temporal queries ("order state at time T") at cost of operational complexity—snapshots, schema evolution, replay tooling.

## Separate databases

Read side on Postgres replica, Elasticsearch, or ClickHouse; write side on primary OLTP Postgres. Sync via CDC (Debezium) or application events.

When to split DBs:

- Search needs inverted index
- Analytics needs columnar
- Read QPS >> write QPS

Operational cost rises—monitor replication lag and projection health.

## Validation and invariants

Commands enforce invariants on write model:

```kotlin
fun Order.Companion.create(cmd: PlaceOrderCommand): Order? {
    if (cmd.items.isEmpty()) return null
    if (cmd.items.any { it.qty <= 0 }) return null
    return Order(/* ... */)
}
```

Queries assume read model already valid—no business rule re-validation on GET.

## API surface

```http
POST /commands/place-order
{ "customerId": "...", "items": [...] }
→ 202 Accepted { "commandId": "..." }

GET /views/orders/abc-123
→ 200 { "status": "Shipped", ... }
```

Separate routes signal intent. GraphQL can expose `mutation placeOrder` vs `query orderSummary` with same separation.

## Pitfalls

**CQRS everywhere.** Admin CRUD screens on one entity do not need two models.

**Stale read UX ignored.** Users submit form, redirect to detail, see old data—confusing without refresh strategy.

**Projection bugs.** Read model wrong while write model correct—nightmare debug without event replay tooling.

**Duplicated validation.** Client, command, and query paths diverging—single source of truth for rules on command side only.

## Migration path

1. Identify hot read queries hurting OLTP
2. Add read table + projector from existing writes
3. Route reads to new table
4. Introduce explicit command objects for write path
5. Consider events only if audit/replay need appears

## Read model refresh strategies

Users expect read-your-writes after commands:

| Strategy | Latency | Complexity |
|----------|---------|------------|
| Synchronous projection | Immediate | Blocks command path |
| Async projector + poll | 100ms–2s | Simple, UX polling |
| Async + WebSocket push | Near-immediate | Requires notify pipeline |
| Cache invalidation | Variable | Cache coherency risk |

For user-facing flows, synchronous projection of the affected aggregate is often worth the 20ms — async projection for cross-aggregate dashboards.

## CQRS without event sourcing

CQRS does not require event sourcing:

```sql
-- Command side: normalized write schema
UPDATE orders SET status = 'shipped' WHERE id = $1;

-- Query side: denormalized read table (updated in same transaction or async)
INSERT INTO order_summaries (id, status, customer_name, ...)
SELECT o.id, o.status, c.name, ...
FROM orders o JOIN customers c ON ...
WHERE o.id = $1
ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status;
```

Event sourcing adds audit/replay capability but triples operational complexity — adopt when compliance or debugging requirements justify it.

Pair with [event sourcing projections](https://blog.michaelsam94.com/event-sourcing-projections-read-models/) when you choose the full event-sourced path.

## Common production mistakes

Teams get command query separation wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of command query separation fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [Martin Fowler — CQRS](https://martinfowler.com/bliki/CQRS.html)
- [Greg Young — CQRS Documents](https://cqrs.files.wordpress.com/2010/11/cqrs_documents.pdf)
- [Microsoft Azure Architecture — CQRS pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs)
- [EventStoreDB documentation](https://www.eventstore.com/eventstore)
