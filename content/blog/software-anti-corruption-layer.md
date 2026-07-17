---
title: "The Anti-Corruption Layer"
slug: "software-anti-corruption-layer"
description: "Isolate legacy and third-party models with an anti-corruption layer: translation boundaries, adapter design, and when ACL beats shared DTOs."
datePublished: "2025-08-03"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "anti-corruption layer, ACL pattern, bounded context integration, legacy system adapter, domain model translation, Eric Evans DDD"
faq:
  - q: "What is an ACL?"
    a: "Translation layer that converts upstream DTOs into your domain language."
  - q: "Where does it live?"
    a: "At integration boundary — inbound from legacy ERP, external API, or partner service."
  - q: " vs shared kernel?"
    a: "Shared kernel is mutual model subset; ACL protects your model from theirs."
---

The ERP represents customers as `CUST_NBR` strings with credit holds encoded as single-character flags. Your checkout bounded context models `Customer` with value objects and explicit credit policies. Importing their structs into domain services let `hold_code == 'X'` leak into pricing rules within a sprint. The anti-corruption layer (ACL)—from Domain-Driven Design—sits between contexts and translates, validates, and rejects inbound concepts so your model stays coherent even when the upstream system is neither owned nor fixable.

## Boundary placement

```
[ Legacy ERP API ] → [ ACL module ] → [ Your domain services ]
                           ↓
                    rejects / maps
```

Only ACL imports legacy SDK types. Domain layer sees `InboundShipmentNotice`, not `ErpAsnXml`.

## Translation example

```kotlin
class ErpOrderAdapter(private val client: ErpClient) {
    fun fetchOrder(erpId: String): Order? {
        val raw = client.getSalesOrder(erpId) ?: return null
        if (raw.status !in SUPPORTED_STATUSES) return null
        return Order(
            id = OrderId.generate(),
            externalRef = ExternalRef("erp", erpId),
            lines = raw.lines.map { it.toOrderLine() },
            status = raw.status.toDomainStatus(),
        )
    }
}
```

Unsupported statuses return null or domain-specific `UnknownExternalState` for manual review—not silent garbage.

## Validate at the gate

ACL validates foreign payloads before translation: required fields, numeric ranges, enum subsets. Fail fast with structured errors to integration monitoring. Do not pass partially parsed legacy objects inward hoping domain catches issues.

## Outbound translation

Publishing to legacy requires ACL too—your `CancelOrder` command becomes their `VOID_SO` XML with reason codes they accept. Bidirectional ACL prevents domain from learning their verb names.

## Testing ACL

Contract tests against legacy sandbox fixtures. Golden files for sample payloads → expected domain objects. When vendor changes schema, tests fail in ACL PR—not in checkout math.

## ACL vs shared kernel

Shared kernel suits closely aligned teams with joint model ownership. ACL suits vendor and legacy boundaries you do not control. Choosing wrong pattern creates either duplication angst (ACL) or coupling pain (shared kernel).

ACL enables strangler migrations: start read-only sync, expand translated commands, shrink legacy surface. When legacy retires, delete ACL module—not refactor domain.

Contract tests against legacy sandbox fixtures—golden files for payload to domain mapping. Vendor schema changes fail ACL PR, not pricing math.

Bidirectional ACL on outbound—domain never learns VOID_SO verb names. Unsupported inbound statuses route to manual review queue, not silent null.

Delete ACL module when legacy retires—do not refactor domain to absorb their fields at last minute.

Run the change through your standard PR checklist: tests, observability, and a two-minute rollback drill in staging. Small operational habits accumulate into systems that survive on-call nights without heroics.

Share a short write-up in your engineering channel after rollout: what shipped, what metric you watch, and who owns follow-up. That closes the loop for teammates who were not in the PR and surfaces gaps in docs before the next person repeats the same investigation.

## Operational notes for software anti corruption layer

ACL mappers unit-tested with golden files from upstream API fixtures. When upstream sends unexpected nulls or enum values, ACL should map to domain errors, not throw stack traces to callers. Version ACL separately from domain when upstream releases monthly.

## Notes on software anti corruption layer

ACL mappers unit-tested with golden files from upstream API fixtures. When upstream sends unexpected nulls or enum values, ACL should map to domain errors, not throw stack traces to callers. Version ACL separately from domain when upstream releases monthly.

## Resources

- [Domain-Driven Design (Eric Evans)](https://www.domainlanguage.com/ddd/)
- [Microsoft Azure: Anti-Corruption Layer pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/anti-corruption-layer)
- [Implementing Domain-Driven Design (Vaughn Vernon)](https://vaughnvernon.com/)
- [Martin Fowler: Bounded Context](https://martinfowler.com/bliki/BoundedContext.html)
- [Strangler Fig pattern](https://martinfowler.com/bliki/StranglerFigApplication.html)

Version upstream DTOs separately; ERP field additions should not break domain entities.

Review software anti corruption layer metrics after the next release train on mid-tier mobile devices — regressions that pass lab Lighthouse often fail CrUX field data.

Ship software anti corruption layer changes with a named owner, dashboard link, and rollback command in the runbook — operational readiness matters as much as the code diff.

Ship software anti corruption layer changes with a named owner, dashboard link, and rollback command in the runbook — operational readiness matters as much as the code diff. Re-baseline metrics after the next traffic doubling affecting software routes.

## Trade-offs I keep revisiting for software anti corruption layer

Architecture work around software anti corruption layer is mostly about boundaries and change cost. Draw the context map before naming folders. If two teams deploy on different cadences, a shared mutable model will become the incident factory.

Practical rules for software anti corruption layer:
- Prefer modular monolith seams you can extract later over premature microservices
- Encode ubiquitous language in types and test names, not slide decks
- Event contracts versioned; consumers tolerate additive changes only
- Feature toggles have owners and burn-down dates — permanent toggles are config debt

Workshop output should include a decision record: context, options, chosen path, and the metric that would force a revisit.

| Signal | Target | Alarm |
|--------|--------|-------|
| Coverage % | Team-defined SLO | Page on burn rate |
| Mean time to detect | Baseline − noise | Ticket if sustained |
| Escapes to prod | Budget cap | Weekly review |

## Load and chaos experiments for software anti corruption layer

Reviewers should challenge assumptions encoded in software anti corruption layer: defaults copied from tutorials, timeouts that exceed upstream SLAs, and authz checks applied only on the primary UI path. Require a short threat or failure note in the PR when the change touches a trust boundary.

Concrete probes:
1. Scenario A for software anti corruption layer: partial dependency outage — prove clients degrade gracefully and retries do not amplify load.
2. Scenario B for software anti corruption layer: bad config shipped — prove rollback within the declared RTO without data corruption.
3. Scenario C for software anti corruption layer: traffic 3× baseline — prove autoscaling or shedding keeps the golden journey healthy.

## Anti-patterns unique to software anti corruption layer

Roll out software anti corruption layer behind a flag or weighted route when possible. Start with internal users or a low-risk geography. Watch the signals in the table for at least one full business cycle before calling the migration done. Keep the previous path warm until error budgets stabilize.

Document the owner, the dashboard, and the single command that reverts the change. If that sentence is hard to write, the design is not ready for production traffic.

## Multi-tenant concerns in software anti corruption layer

Detail 1 (831): for software anti corruption layer, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When multi-tenant concerns in software anti corruption layer becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break software anti corruption layer, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about software anti corruption layer: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Compliance evidence for software anti corruption layer

Detail 2 (823): for software anti corruption layer, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When compliance evidence for software anti corruption layer becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break software anti corruption layer, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about software anti corruption layer: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.
