---
title: "Tactical DDD Patterns"
slug: "software-domain-driven-design-tactical"
description: "Implement tactical DDD patterns: entities, value objects, aggregates, domain events, repositories, and invariants that hold under concurrency."
datePublished: "2025-08-19"
dateModified: "2025-08-19"
tags: ["DDD", "Domain Modeling", "Architecture", "Backend"]
keywords: "tactical DDD patterns, aggregate root, value object, domain entity, domain events, repository pattern, invariant enforcement"
faq:
  - q: "What belongs inside an aggregate?"
    a: "Cluster entities and value objects that must stay consistent together in one transaction. The aggregate root is the only entry point for mutations—external code references root ID, not internal child IDs. Keep aggregates small; large aggregates cause contention and wide lock scope. If two clusters update independently, they are separate aggregates linked by ID."
  - q: "Value object or entity?"
    a: "Value objects are defined by attributes and immutable—Money, EmailAddress, DateRange. Replace rather than mutate. Entities have identity persisting across attribute changes—Order, Customer. When in doubt, prefer value objects; they simplify reasoning and thread safety."
  - q: "Should repositories return domain objects or DTOs?"
    a: "Repositories in domain layer return aggregates or None—not ORM rows exposed upward. Mapping happens inside infrastructure implementation. Application services load aggregate, call domain methods, save via repository. Query-heavy screens may bypass repository with read models (CQRS) without polluting write aggregates."
---

`order.status = "SHIPPED"` in a controller bypassed the rule that cancelled orders cannot ship—because nothing enforced invariants at the domain layer. Tactical DDD patterns put business rules where they survive framework churn: aggregates guard consistency boundaries, value objects encode validated concepts, domain events announce facts other contexts react to. This is not ceremony for CRUD; it is structure for behavior-rich domains where bugs cost money.


## Value objects

```kotlin
@JvmInline
value class Email private constructor(val value: String) {
    companion object {
        fun of(raw: String): Email {
            require(EMAIL_REGEX.matches(raw)) { "Invalid email" }
            return Email(raw.lowercase())
        }
    }
}
```

Invalid emails cannot exist—constructor guarantees.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Entity and aggregate root

```kotlin
class Order private constructor(
    val id: OrderId,
    private val lines: MutableList<OrderLine>,
    private var status: OrderStatus,
) {
    fun ship() {
        check(status == OrderStatus.PAID) { "Cannot ship order in $status" }
        status = OrderStatus.SHIPPED
        registerEvent(OrderShipped(id, Instant.now()))
    }
}
```

Factory methods control creation; private setters block casual mutation.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Domain events

```kotlin
data class OrderShipped(val orderId: OrderId, val at: Instant) : DomainEvent
```

Raised in aggregate, collected by application service, persisted to outbox for reliable publish. Handlers live outside aggregate in application or other contexts.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Repository interface

```kotlin
interface OrderRepository {
    fun find(id: OrderId): Order?
    fun save(order: Order)
}
```

Implementation uses JPA, JDBC, or event store—domain never imports.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Application service orchestration

```kotlin
class ShipOrderHandler(
    private val orders: OrderRepository,
    private val outbox: Outbox,
) {
    fun handle(cmd: ShipOrderCommand) {
        val order = orders.find(cmd.orderId) ?: throw NotFound
        order.ship()
        orders.save(order)
        outbox.publish(order.pullEvents())
    }
}
```

Thin orchestration; no business if-statements here.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Concurrency

Optimistic locking on aggregate version column:

```sql
UPDATE orders SET status = ?, version = version + 1
WHERE id = ? AND version = ?
```

Retry on conflict for idempotent commands.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


If entities are data bags with all logic in services, you have structs—not necessarily wrong for simple domains, but tactical patterns earn their keep when rules multiply.

Optimistic locking on aggregate version—retry idempotent commands on conflict. Factory methods and private constructors block invalid entity states.

Anemic entities with all logic in services suits simple CRUD; tactical patterns earn keep when rules multiply and bugs cost money.

Domain events via outbox for reliable publish—handlers outside aggregate.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

Document the decision, owner, and rollback path in your team wiki the same week you ship. Future you will not remember which environment variable toggled the behavior unless it is written next to the runbook entry and linked from the alert. That habit costs ten minutes per change and saves hours when pagination or auth misbehaves under a single large tenant.



Run the change through your standard PR checklist: tests, observability, and a two-minute rollback drill in staging. Small operational habits accumulate into systems that survive on-call nights without heroics.


Share a short write-up in your engineering channel after rollout: what shipped, what metric you watch, and who owns follow-up. That closes the loop for teammates who were not in the PR and surfaces gaps in docs before the next person repeats the same investigation.

## Resources

- [Domain-Driven Design Reference (Eric Evans)](https://www.domainlanguage.com/ddd/reference/)
- [Implementing Domain-Driven Design (Vaughn Vernon)](https://vaughnvernon.com/)
- [Aggregate (Martin Fowler)](https://martinfowler.com/bliki/Aggregate.html)
- [Value Object (Martin Fowler)](https://martinfowler.com/bliki/ValueObject.html)
- [Domain Events (Martin Fowler)](https://martinfowler.com/eaaDev/DomainEvent.html)
