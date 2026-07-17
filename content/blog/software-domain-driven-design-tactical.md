---
title: "Tactical DDD Patterns"
slug: "software-domain-driven-design-tactical"
description: "Implement tactical DDD patterns: entities, value objects, aggregates, domain events, repositories, and invariants that hold under concurrency."
datePublished: "2025-08-19"
dateModified: "2026-07-17"
tags: ["DDD", "Domain Modeling", "Architecture", "Backend"]
keywords: "tactical DDD patterns, aggregate root, value object, domain entity, domain events, repository pattern, invariant enforcement"
faq:
  - q: "What belongs inside an aggregate?"
    a: "Cluster entities and value objects that must stay consistent together in one transaction. The aggregate root is the only entry point for mutations—external code references root ID, not internal child IDs. Keep aggregates small; large aggregates cause contention and wide lock scope. If two clusters update independently, they are separate aggregates linked by ID."
  - q: "Value object or entity?"
    a: "Value objects are defined by attributes and immutable—Money, EmailAddress, DateRange. Replace rather than mutate. Entities have identity persisting across attribute changes—Order, Customer. When in doubt, prefer value objects; they simplify reasoning and thread safety."
  - q: "Should repositories return domain objects or DTOs?"
    a: "Repositories in domain layer return aggregates or None—not ORM rows exposed upward. Mapping happens inside infrastructure implementation. Application services load aggregate, call domain methods, save via repository. Query-heavy screens may bypass repository with read models (CQRS) without polluting write aggregates."
faqAnswers:
  - question: "When is software domain driven design tactical the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for software domain driven design tactical?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back software domain driven design tactical safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
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

## Domain events

```kotlin
data class OrderShipped(val orderId: OrderId, val at: Instant) : DomainEvent
```

Raised in aggregate, collected by application service, persisted to outbox for reliable publish. Handlers live outside aggregate in application or other contexts.

## Repository interface

```kotlin
interface OrderRepository {
    fun find(id: OrderId): Order?
    fun save(order: Order)
}
```

Implementation uses JPA, JDBC, or event store—domain never imports.

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

## Concurrency

Optimistic locking on aggregate version column:

```sql
UPDATE orders SET status = ?, version = version + 1
WHERE id = ? AND version = ?
```

Retry on conflict for idempotent commands.

If entities are data bags with all logic in services, you have structs—not necessarily wrong for simple domains, but tactical patterns earn their keep when rules multiply.

Optimistic locking on aggregate version—retry idempotent commands on conflict. Factory methods and private constructors block invalid entity states.

Anemic entities with all logic in services suits simple CRUD; tactical patterns earn keep when rules multiply and bugs cost money.

Domain events via outbox for reliable publish—handlers outside aggregate.

## Aggregate invariants under concurrency

Two requests adding items to the same `Order` aggregate need optimistic locking on version or serializable isolation — otherwise duplicate line items slip through. Domain services coordinate cross-aggregate rules (transfer between accounts) inside one transaction boundary; do not scatter invariants across application layer if they belong to the model.

## Domain events versus integration events

`OrderPlaced` inside the bounded context carries rich domain objects. `order.placed.v1` on the bus carries IDs and primitives only. Map at the boundary — publishing domain entities couples integrators to your refactorings.

## Ubiquitous language in code review

Reject PRs introducing UserDTO in domain layer when glossary says Member. Rename refactors are cheaper than translating between DTO and domain forever. Link glossary page in PR template for bounded context.

## Factory methods on aggregates

Order.create() factory validates invariants before construction — public constructor allows invalid aggregate existence. Repositories reconstitute via factory reading persisted state, not raw constructor.

## Integration testing notes

Exercise the happy path plus three failure modes specific to software domain driven design tactical: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.

## Documentation and on-call

Link runbook steps from the service catalog entry for software domain driven design tactical. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.

## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.

## Quick reference

Instrument software domain driven design tactical before optimizing. Keep a dashboard per critical user journey and review weekly during the first month after launch.

Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.

## Resources

- [Domain-Driven Design Reference (Eric Evans)](https://www.domainlanguage.com/ddd/reference/)
- [Implementing Domain-Driven Design (Vaughn Vernon)](https://vaughnvernon.com/)
- [Aggregate (Martin Fowler)](https://martinfowler.com/bliki/Aggregate.html)
- [Value Object (Martin Fowler)](https://martinfowler.com/bliki/ValueObject.html)
- [Domain Events (Martin Fowler)](https://martinfowler.com/eaaDev/DomainEvent.html)

## Money and specifications

Model money as immutable value object with currency — never Double. Extract complex rules into Specification objects tested without loading full object graphs.

## CQRS projections

Feed read models from domain events; keep write aggregates small. Reporting bypasses repository when projections suffice.

## Saga coordination

Cross-aggregate rules use domain service in one transaction or saga across services — reference other aggregates by ID only.

## An operator's checklist for software domain driven design tactical

Architecture work around software domain driven design tactical is mostly about boundaries and change cost. Draw the context map before naming folders. If two teams deploy on different cadences, a shared mutable model will become the incident factory.

Practical rules for software domain driven design tactical:
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

## Ownership and on-call for software domain driven design tactical

Reviewers should challenge assumptions encoded in software domain driven design tactical: defaults copied from tutorials, timeouts that exceed upstream SLAs, and authz checks applied only on the primary UI path. Require a short threat or failure note in the PR when the change touches a trust boundary.

Concrete probes:
1. Scenario B for software domain driven design tactical: bad config shipped — prove rollback within the declared RTO without data corruption.
2. Scenario C for software domain driven design tactical: traffic 3× baseline — prove autoscaling or shedding keeps the golden journey healthy.
3. Scenario A for software domain driven design tactical: partial dependency outage — prove clients degrade gracefully and retries do not amplify load.

## Post-incident changes after software domain driven design tactical failures

Roll out software domain driven design tactical behind a flag or weighted route when possible. Start with internal users or a low-risk geography. Watch the signals in the table for at least one full business cycle before calling the migration done. Keep the previous path warm until error budgets stabilize.

Document the owner, the dashboard, and the single command that reverts the change. If that sentence is hard to write, the design is not ready for production traffic.

## Developer experience when changing software domain driven design tactical

Detail 1 (585): for software domain driven design tactical, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When developer experience when changing software domain driven design tactical becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break software domain driven design tactical, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about software domain driven design tactical: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.