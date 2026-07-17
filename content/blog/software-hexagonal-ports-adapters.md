---
title: "Hexagonal Architecture in Practice"
slug: "software-hexagonal-ports-adapters"
description: "Apply hexagonal (ports and adapters) architecture: domain core, inbound/outbound ports, testability, and mapping to packages or modules."
datePublished: "2025-08-28"
dateModified: "2026-07-17"
tags: ["Architecture", "Hexagonal", "Clean Architecture", "DDD"]
keywords: "hexagonal architecture, ports and adapters, Alistair Cockburn, clean architecture, domain driven design layers, adapter pattern"
faq:
  - q: "What is a port versus an adapter?"
    a: "Ports are interfaces the domain or application defines—needs outward (repository port) or offers inward (REST API port implemented by application service). Adapters are infrastructure implementations: PostgresRepository, HttpOrderController, SmtpEmailSender. Domain depends on port interfaces only; adapters depend on domain, never reverse."
  - q: "Is hexagonal the same as clean architecture?"
    a: "Conceptually aligned—dependency rule pointing inward, domain at center. Hexagonal emphasizes explicit ports for every external system; clean architecture names rings (entities, use cases). Use whichever vocabulary your team shares; the win is testable domain without framework imports."
  - q: "Does hexagonal require many layers of indirection?"
    a: "No. One application service per use case and one adapter per technology is enough for most services. Avoid port-per-method explosion. Introduce ports where substitution, testing, or multiple implementations justify the interface—not for every CRUD call by default."
faqAnswers:
  - question: "When is software hexagonal ports adapters the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for software hexagonal ports adapters?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back software hexagonal ports adapters safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
Spring annotations littered the domain package—`@Entity` on aggregates, `@Autowired` on constructors—so unit tests needed a running container to assert shipping rules. Hexagonal architecture (ports and adapters, Alistair Cockburn) puts business logic in the center with explicit interfaces for everything outside: HTTP, database, message bus, clock. Frameworks live in outer rings as replaceable adapters. The goal is not diagram aesthetics; it is running `Order.ship()` in a test with fake repositories in milliseconds.

## Layer diagram

```
        [ HTTP Adapter ] ──→ [ Inbound Port / Use Case ] ──→ [ Domain ]
                                    ↓
                            [ Outbound Port ] ←── [ DB Adapter ]
```

Dependencies point inward. Domain has zero imports from adapters.

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

## Package structure

```
domain/
application/
adapters/in/web/
adapters/out/persistence/
adapters/out/messaging/
```

Enforce with ArchUnit or module boundaries in Gradle.

## Mapping cost

Entity ↔ domain mapping boilerplate is real. Use mappers or factory methods; do not skip mapping by leaking JPA entities into use cases—that recouples silently.

CLI script with fifty lines—skip. System growing past three integrations and needing framework swap or heavy unit testing—ports pay rent.

ArchUnit enforces domain does not import adapters. Mapping entity to domain in adapter—never leak JPA into use cases.

Ports where substitution and testing justify interface—not port-per-method explosion. CLI fifty-liner skips hexagonal; three integrations approaching justifies ports.

Prefer boring, repeatable process over one heroic migration weekend.

Treat operational readiness as part of definition-of-done: dashboards, alerts, runbook links, and a named owner. Skipping those steps ships code that works in demo and fails quietly in production until a customer or auditor finds the gap.

## Testing with fake adapters

Replace `PostgresOrderRepository` with in-memory fake implementing the same port in unit tests. HTTP adapters get contract tests against WireMock; domain tests never spin containers. If tests need Spring context, the hexagon leaked inward.

## Package structure that enforces direction

```
domain/       — entities, value objects, domain services
application/  — use cases, port interfaces
adapters/
  in/web/     — controllers
  out/db/     — repositories
  out/email/  — SMTP
```

ArchUnit or import-linter rules: domain imports nothing from adapters. CI fails on `domain.. -> adapters..` dependency.

## Driving adapter thinness

HTTP controller maps request DTO to command object, calls application service, maps result to response — no business if-statements in controller. Fat controllers signal missing application service extraction.

## Clock and UUID ports

Inject Clock and IdGenerator ports — tests freeze time and deterministic IDs. Hardcoded Instant.now() in domain makes flaky tests and non-reproducible event ordering.

## Integration testing notes

Exercise the happy path plus three failure modes specific to software hexagonal ports adapters: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.

## Documentation and on-call

Link runbook steps from the service catalog entry for software hexagonal ports adapters. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.

## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.

## Quick reference

Instrument software hexagonal ports adapters before optimizing. Keep a dashboard per critical user journey and review weekly during the first month after launch.

Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.

## Resources

- [Hexagonal Architecture (Alistair Cockburn)](https://alistair.cockburn.us/hexagonal-architecture/)
- [Ports and Adapters pattern (Java Design Patterns site)](https://java-design-patterns.com/patterns/hexagonal-architecture/)
- [Clean Architecture (Robert C. Martin)](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [ArchUnit library](https://www.archunit.org/)
- [Spring Modulith documentation](https://docs.spring.io/spring-modulith/reference/)

## CLI inbound adapter

Reuse the same use case port from HTTP, queue listener, and CLI — business rules stay centralized.

## Configuration port

Inject configuration through port interface — domain never reads environment variables directly.

## An operator's checklist for software hexagonal ports adapters

Architecture work around software hexagonal ports adapters is mostly about boundaries and change cost. Draw the context map before naming folders. If two teams deploy on different cadences, a shared mutable model will become the incident factory.

Practical rules for software hexagonal ports adapters:
- Prefer modular monolith seams you can extract later over premature microservices
- Encode ubiquitous language in types and test names, not slide decks
- Event contracts versioned; consumers tolerate additive changes only
- Feature toggles have owners and burn-down dates — permanent toggles are config debt

Workshop output should include a decision record: context, options, chosen path, and the metric that would force a revisit.

| Signal | Target | Alarm |
|--------|--------|-------|
| Crawl / index ratio | Team-defined SLO | Page on burn rate |
| Rich result valid % | Baseline − noise | Ticket if sustained |
| Organic landing LCP | Budget cap | Weekly review |

## Ownership and on-call for software hexagonal ports adapters

Reviewers should challenge assumptions encoded in software hexagonal ports adapters: defaults copied from tutorials, timeouts that exceed upstream SLAs, and authz checks applied only on the primary UI path. Require a short threat or failure note in the PR when the change touches a trust boundary.

Concrete probes:
1. Scenario A for software hexagonal ports adapters: partial dependency outage — prove clients degrade gracefully and retries do not amplify load.
2. Scenario B for software hexagonal ports adapters: bad config shipped — prove rollback within the declared RTO without data corruption.
3. Scenario C for software hexagonal ports adapters: traffic 3× baseline — prove autoscaling or shedding keeps the golden journey healthy.

## Rollout sequence that worked for software hexagonal ports adapters

Roll out software hexagonal ports adapters behind a flag or weighted route when possible. Start with internal users or a low-risk geography. Watch the signals in the table for at least one full business cycle before calling the migration done. Keep the previous path warm until error budgets stabilize.

Document the owner, the dashboard, and the single command that reverts the change. If that sentence is hard to write, the design is not ready for production traffic.

## Developer experience when changing software hexagonal ports adapters

Detail 1 (577): for software hexagonal ports adapters, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When developer experience when changing software hexagonal ports adapters becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break software hexagonal ports adapters, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about software hexagonal ports adapters: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Observability cardinality around software hexagonal ports adapters

Detail 2 (884): for software hexagonal ports adapters, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When observability cardinality around software hexagonal ports adapters becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break software hexagonal ports adapters, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about software hexagonal ports adapters: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.