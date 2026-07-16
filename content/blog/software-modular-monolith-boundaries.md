---
title: "Drawing Modular Monolith Boundaries"
slug: "software-modular-monolith-boundaries"
description: "Structure modular monoliths: module boundaries, package privacy, API surfaces, and extraction paths without premature microservices."
datePublished: "2025-08-31"
dateModified: "2025-08-31"
tags: ["Architecture", "Modular Monolith", "Monolith", "Microservices"]
keywords: "modular monolith boundaries, monolith modules, package by feature, extract microservice, Spring Modulith, monolith first architecture"
faq:
  - q: "What is a modular monolith?"
    a: "A single deployable application composed of well-bounded modules with explicit public APIs and enforced private internals—like microservices without network partitions. Teams gain clear ownership and test isolation while avoiding operational overhead of distributed systems until scale or org structure truly requires extraction."
  - q: "How do I enforce module boundaries in code?"
    a: "Use package-private visibility, Java modules (module-info), Gradle module tests, ArchUnit rules, or Spring Modulith @ApplicationModuleListener constraints. CI fails when billing imports inventory.internal. Public entry points are facades or application services in api packages; everything else is internal."
  - q: "When should a module become a microservice?"
    a: "Extract when independent scaling, deployment cadence, or failure isolation requirements exceed the cost of network calls, distributed tracing, and data consistency complexity—not when the monolith feels large emotionally. Successful extraction usually follows months of stable modular APIs inside the monolith first."
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

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


## Public API surface

```kotlin
// billing/api/BillingFacade.kt
interface BillingFacade {
    fun issueInvoice(orderId: OrderId): InvoiceId
}
```

Other modules depend only on `billing.api`. Internal persistence, entities, and mappers stay in `billing.internal`.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


## Enforcement in CI

```java
@ArchTest
static final ArchRule noInternalImports = noClasses()
    .that().resideInAPackage("..catalog..")
    .should().dependOnClassesThat().resideInAPackage("..billing.internal..");
```

Spring Modulith verifies module graph on test startup.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


## Communication between modules

Prefer synchronous facade calls in-process for strong consistency needs. Use internal application events for loose coupling:

```kotlin
@ApplicationModuleListener
fun on(orderPlaced: OrderPlacedEvent) { ... }
```

Events stay in-process until extraction replaces with message bus—same handler signature, different adapter.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


## Data ownership

One module owns each table; others access via facade or read replica API—not direct SQL joins across modules in application code. Cross-module queries suggest merged module or explicit reporting read model.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


## Testing strategy

Module integration tests boot subset context. Contract tests on public facades simulate future RPC boundaries.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.



Before splitting module to service:

- [ ] No illegal cross-module imports for 2+ releases
- [ ] Facade API stable and documented
- [ ] Data owned by single module; migration plan for shared tables
- [ ] Observability tags include module name already

Extract with strangler: deploy service, route facade calls over HTTP behind interface.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


Packages named `controllers`, `services`, `repositories` horizontally slice every feature together—no module boundaries, all coupling. Package by feature/module vertically.

billing.api facade only public surface—ArchUnit fails catalog importing billing.internal. In-process events until extraction replaces with bus using same handler signatures.

One module owns each table—cross-module SQL join in app code signals merged module or reporting read model.

Extraction checklist: stable facade, no illegal imports two releases, data migration plan, observability tags already include module name.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

Document the decision, owner, and rollback path in your team wiki the same week you ship. Future you will not remember which environment variable toggled the behavior unless it is written next to the runbook entry and linked from the alert. That habit costs ten minutes per change and saves hours when pagination or auth misbehaves under a single large tenant.



## Resources

- [Modular Monolith (Kamil Grzybek)](https://www.kamilgrzybek.com/blog/posts/modular-monolith-primer)
- [MonolithFirst (Martin Fowler)](https://martinfowler.com/bliki/MonolithFirst.html)
- [Spring Modulith reference](https://docs.spring.io/spring-modulith/reference/)
- [ArchUnit user guide](https://www.archunit.org/userguide/html/000_Index.html)
- [Team Topologies: evolutionary architecture](https://teamtopologies.com/key-concepts-content/evolutionary-architecture)
