---
title: "Hexagonal Architecture in Practice"
slug: "software-hexagonal-ports-adapters"
description: "Apply hexagonal (ports and adapters) architecture: domain core, inbound/outbound ports, testability, and mapping to packages or modules."
datePublished: "2025-08-28"
dateModified: "2025-08-28"
tags: ["Architecture", "Hexagonal", "Clean Architecture", "DDD"]
keywords: "hexagonal architecture, ports and adapters, Alistair Cockburn, clean architecture, domain driven design layers, adapter pattern"
faq:
  - q: "What is a port versus an adapter?"
    a: "Ports are interfaces the domain or application defines—needs outward (repository port) or offers inward (REST API port implemented by application service). Adapters are infrastructure implementations: PostgresRepository, HttpOrderController, SmtpEmailSender. Domain depends on port interfaces only; adapters depend on domain, never reverse."
  - q: "Is hexagonal the same as clean architecture?"
    a: "Conceptually aligned—dependency rule pointing inward, domain at center. Hexagonal emphasizes explicit ports for every external system; clean architecture names rings (entities, use cases). Use whichever vocabulary your team shares; the win is testable domain without framework imports."
  - q: "Does hexagonal require many layers of indirection?"
    a: "No. One application service per use case and one adapter per technology is enough for most services. Avoid port-per-method explosion. Introduce ports where substitution, testing, or multiple implementations justify the interface—not for every CRUD call by default."
---

Spring annotations littered the domain package—`@Entity` on aggregates, `@Autowired` on constructors—so unit tests needed a running container to assert shipping rules. Hexagonal architecture (ports and adapters, Alistair Cockburn) puts business logic in the center with explicit interfaces for everything outside: HTTP, database, message bus, clock. Frameworks live in outer rings as replaceable adapters. The goal is not diagram aesthetics; it is running `Order.ship()` in a test with fake repositories in milliseconds.


## Layer diagram

```
        [ HTTP Adapter ] ──→ [ Inbound Port / Use Case ] ──→ [ Domain ]
                                    ↓
                            [ Outbound Port ] ←── [ DB Adapter ]
```

Dependencies point inward. Domain has zero imports from adapters.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Inbound adapter example

```kotlin
@RestController
class OrderController(private val shipOrder: ShipOrderUseCase) {
    @PostMapping("/orders/{id}/ship")
    fun ship(@PathVariable id: UUID) {
        shipOrder(ShipOrderCommand(OrderId(id)))
    }
}
```

Controller translates HTTP to command DTO; no business rules.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Outbound port and adapter

```kotlin
interface OrderRepository {
    fun find(id: OrderId): Order?
    fun save(order: Order)
}

class JpaOrderRepository(private val em: EntityManager) : OrderRepository {
    override fun find(id: OrderId): Order? =
        em.find(OrderEntity::class.java, id.value)?.toDomain()
}
```

Swap `InMemoryOrderRepository` in tests.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Use case orchestration

```kotlin
class ShipOrderUseCase(
    private val orders: OrderRepository,
    private val clock: Clock,
    private val events: EventPublisher,
) {
    operator fun invoke(cmd: ShipOrderCommand) {
        val order = orders.find(cmd.orderId) ?: throw NotFound
        order.ship(clock.instant())
        orders.save(order)
        events.publish(order.pullEvents())
    }
}
```

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Package structure

```
domain/
application/
adapters/in/web/
adapters/out/persistence/
adapters/out/messaging/
```

Enforce with ArchUnit or module boundaries in Gradle.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Mapping cost

Entity ↔ domain mapping boilerplate is real. Use mappers or factory methods; do not skip mapping by leaking JPA entities into use cases—that recouples silently.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


CLI script with fifty lines—skip. System growing past three integrations and needing framework swap or heavy unit testing—ports pay rent.

ArchUnit enforces domain does not import adapters. Mapping entity to domain in adapter—never leak JPA into use cases.

Ports where substitution and testing justify interface—not port-per-method explosion. CLI fifty-liner skips hexagonal; three integrations approaching justifies ports.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

Document the decision, owner, and rollback path in your team wiki the same week you ship. Future you will not remember which environment variable toggled the behavior unless it is written next to the runbook entry and linked from the alert. That habit costs ten minutes per change and saves hours when pagination or auth misbehaves under a single large tenant.



Run the change through your standard PR checklist: tests, observability, and a two-minute rollback drill in staging. Small operational habits accumulate into systems that survive on-call nights without heroics.


Share a short write-up in your engineering channel after rollout: what shipped, what metric you watch, and who owns follow-up. That closes the loop for teammates who were not in the PR and surfaces gaps in docs before the next person repeats the same investigation.


Prefer boring, repeatable process over one heroic migration weekend.


Treat operational readiness as part of definition-of-done: dashboards, alerts, runbook links, and a named owner. Skipping those steps ships code that works in demo and fails quietly in production until a customer or auditor finds the gap.

## Resources

- [Hexagonal Architecture (Alistair Cockburn)](https://alistair.cockburn.us/hexagonal-architecture/)
- [Ports and Adapters pattern (Java Design Patterns site)](https://java-design-patterns.com/patterns/hexagonal-architecture/)
- [Clean Architecture (Robert C. Martin)](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [ArchUnit library](https://www.archunit.org/)
- [Spring Modulith documentation](https://docs.spring.io/spring-modulith/reference/)
