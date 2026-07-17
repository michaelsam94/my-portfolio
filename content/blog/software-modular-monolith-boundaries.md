---
title: "Drawing Modular Monolith Boundaries"
slug: "software-modular-monolith-boundaries"
description: "Structure modular monoliths: module boundaries, package privacy, API surfaces, and extraction paths without premature microservices."
datePublished: "2025-08-31"
dateModified: "2026-07-17"
tags: ["Architecture", "Modular Monolith", "Monolith", "Microservices"]
keywords: "modular monolith boundaries, monolith modules, package by feature, extract microservice, Spring Modulith, monolith first architecture"
faq:
  - q: "What is a modular monolith?"
    a: "A single deployable application composed of well-bounded modules with explicit public APIs and enforced private internals—like microservices without network partitions. Teams gain clear ownership and test isolation while avoiding operational overhead of distributed systems until scale or org structure truly requires extraction."
  - q: "How do I enforce module boundaries in code?"
    a: "Use package-private visibility, Java modules (module-info), Gradle module tests, ArchUnit rules, or Spring Modulith @ApplicationModuleListener constraints. CI fails when billing imports inventory.internal. Public entry points are facades or application services in api packages; everything else is internal."
  - q: "When should a module become a microservice?"
    a: "Extract when independent scaling, deployment cadence, or failure isolation requirements exceed the cost of network calls, distributed tracing, and data consistency complexity—not when the monolith feels large emotionally. Successful extraction usually follows months of stable modular APIs inside the monolith first."
faqAnswers:
  - question: "When is software modular monolith boundaries the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for software modular monolith boundaries?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back software modular monolith boundaries safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
The "microservices migration" stalled after twelve services shared one database and deployment train. A modular monolith would have enforced boundaries in the compiler first, extracted only modules with proven isolation needs later. Not every product needs distributed systems on day one; many need one repo, one deploy, and hard walls between billing, catalog, and notifications so those walls become service boundaries when metrics justify the jump.

## Module identification

Align modules to business capabilities or bounded contexts:

```
modules/
  billing/     (api, internal, domain)
  catalog/
  notifications/
  shared-kernel/   (minimal!)
```

`shared-kernel` stays tiny—generic IDs, money type—not business rules dumping ground.

## Public API surface

```kotlin
// billing/api/BillingFacade.kt
interface BillingFacade {
    fun issueInvoice(orderId: OrderId): InvoiceId
}
```

Other modules depend only on `billing.api`. Internal persistence, entities, and mappers stay in `billing.internal`.

## Enforcement in CI

```java
@ArchTest
static final ArchRule noInternalImports = noClasses()
    .that().resideInAPackage("..catalog..")
    .should().dependOnClassesThat().resideInAPackage("..billing.internal..");
```

Spring Modulith verifies module graph on test startup.

## Communication between modules

Prefer synchronous facade calls in-process for strong consistency needs. Use internal application events for loose coupling:

```kotlin
@ApplicationModuleListener
fun on(orderPlaced: OrderPlacedEvent) { ... }
```

Events stay in-process until extraction replaces with message bus—same handler signature, different adapter.

## Data ownership

One module owns each table; others access via facade or read replica API—not direct SQL joins across modules in application code. Cross-module queries suggest merged module or explicit reporting read model.

## Testing strategy

Module integration tests boot subset context. Contract tests on public facades simulate future RPC boundaries.

Before splitting module to service:

- [ ] No illegal cross-module imports for 2+ releases
- [ ] Facade API stable and documented
- [ ] Data owned by single module; migration plan for shared tables
- [ ] Observability tags include module name already

Extract with strangler: deploy service, route facade calls over HTTP behind interface.

Packages named `controllers`, `services`, `repositories` horizontally slice every feature together—no module boundaries, all coupling. Package by feature/module vertically.

billing.api facade only public surface—ArchUnit fails catalog importing billing.internal. In-process events until extraction replaces with bus using same handler signatures.

One module owns each table—cross-module SQL join in app code signals merged module or reporting read model.

Extraction checklist: stable facade, no illegal imports two releases, data migration plan, observability tags already include module name.

## Extraction readiness signals

Extract when: (1) ArchUnit clean two releases, (2) facade API semver-stable, (3) module owns tables exclusively, (4) on-call can already filter metrics by module tag. Premature HTTP extraction before in-process events stabilized cost us three months of dual-write bugs — strangler behind same interface worked second time.

## Extraction readiness signals

Extract when: (1) ArchUnit clean two releases, (2) facade API semver-stable, (3) module owns tables exclusively, (4) on-call can already filter metrics by module tag. Premature HTTP extraction before in-process events stabilized cost us three months of dual-write bugs — strangler behind same interface worked second time.

## Field metrics and rollback

Capture baseline p75 error rate and latency on tier-1 routes before merge. Compare seven days post-deploy sliced by mobile and region. Document rollback in PR and runbook.

## Resources

- [Modular Monolith (Kamil Grzybek)](https://www.kamilgrzybek.com/blog/posts/modular-monolith-primer)
- [MonolithFirst (Martin Fowler)](https://martinfowler.com/bliki/MonolithFirst.html)
- [Spring Modulith reference](https://docs.spring.io/spring-modulith/reference/)
- [ArchUnit user guide](https://www.archunit.org/userguide/html/000_Index.html)
- [Team Topologies: evolutionary architecture](https://teamtopologies.com/key-concepts-content/evolutionary-architecture)

## Field notes on software modular monolith boundaries

Architecture work around software modular monolith boundaries is mostly about boundaries and change cost. Draw the context map before naming folders. If two teams deploy on different cadences, a shared mutable model will become the incident factory.

Practical rules for software modular monolith boundaries:
- Prefer modular monolith seams you can extract later over premature microservices
- Encode ubiquitous language in types and test names, not slide decks
- Event contracts versioned; consumers tolerate additive changes only
- Feature toggles have owners and burn-down dates — permanent toggles are config debt

Workshop output should include a decision record: context, options, chosen path, and the metric that would force a revisit.

| Signal | Target | Alarm |
|--------|--------|-------|
| Latency p99 | Team-defined SLO | Page on burn rate |
| Error rate | Baseline − noise | Ticket if sustained |
| Cost per 1k ops | Budget cap | Weekly review |

## What reviewers should challenge in software modular monolith boundaries PRs

Reviewers should challenge assumptions encoded in software modular monolith boundaries: defaults copied from tutorials, timeouts that exceed upstream SLAs, and authz checks applied only on the primary UI path. Require a short threat or failure note in the PR when the change touches a trust boundary.

Concrete probes:
1. Scenario A for software modular monolith boundaries: partial dependency outage — prove clients degrade gracefully and retries do not amplify load.
2. Scenario B for software modular monolith boundaries: bad config shipped — prove rollback within the declared RTO without data corruption.
3. Scenario C for software modular monolith boundaries: traffic 3× baseline — prove autoscaling or shedding keeps the golden journey healthy.

## Rollout sequence that worked for software modular monolith boundaries

Roll out software modular monolith boundaries behind a flag or weighted route when possible. Start with internal users or a low-risk geography. Watch the signals in the table for at least one full business cycle before calling the migration done. Keep the previous path warm until error budgets stabilize.

Document the owner, the dashboard, and the single command that reverts the change. If that sentence is hard to write, the design is not ready for production traffic.

## Caching interactions with software modular monolith boundaries

Detail 1 (974): for software modular monolith boundaries, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When caching interactions with software modular monolith boundaries becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break software modular monolith boundaries, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about software modular monolith boundaries: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Multi-tenant concerns in software modular monolith boundaries

Detail 2 (0): for software modular monolith boundaries, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When multi-tenant concerns in software modular monolith boundaries becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break software modular monolith boundaries, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about software modular monolith boundaries: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Compliance evidence for software modular monolith boundaries

Detail 3 (609): for software modular monolith boundaries, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When compliance evidence for software modular monolith boundaries becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break software modular monolith boundaries, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about software modular monolith boundaries: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Developer experience when changing software modular monolith boundaries

Detail 4 (76): for software modular monolith boundaries, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When developer experience when changing software modular monolith boundaries becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break software modular monolith boundaries, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about software modular monolith boundaries: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.