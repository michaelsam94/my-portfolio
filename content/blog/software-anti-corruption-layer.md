---
title: "The Anti-Corruption Layer"
slug: "software-anti-corruption-layer"
description: "Isolate legacy and third-party models with an anti-corruption layer: translation boundaries, adapter design, and when ACL beats shared DTOs."
datePublished: "2025-08-03"
dateModified: "2025-08-03"
tags: ["Architecture", "DDD", "Integration", "Legacy"]
keywords: "anti-corruption layer, ACL pattern, bounded context integration, legacy system adapter, domain model translation, Eric Evans DDD"
faq:
  - q: "When do I need an anti-corruption layer?"
    a: "Use an ACL when an upstream system—legacy monolith, vendor API, or partner feed—uses a model that would pollute your domain if imported verbatim. If terminology, invariants, and lifecycles differ, direct mapping spreads their confusion into your codebase. ACL translates at the boundary so inner layers speak only your ubiquitous language."
  - q: "Is an ACL the same as an adapter?"
    a: "Adapters connect technical interfaces—HTTP to gRPC. ACL adds semantic translation: their OrderStatus SHIPPED becomes your FulfillmentCompleted domain event with validated transitions. An ACL often contains adapters internally, but the distinguishing work is model transformation and rejection of foreign concepts at the gate."
  - q: "Does an ACL justify duplicate data structures?"
    a: "Yes—duplicating DTOs and domain types at the boundary is intentional. Shared all-purpose Order class spanning legacy and modern contexts couples you to their schema changes. ACL types are cheaper than corrupting core aggregates with nullable fields for concepts you do not recognize."
---

The ERP represents customers as `CUST_NBR` strings with credit holds encoded as single-character flags. Your checkout bounded context models `Customer` with value objects and explicit credit policies. Importing their structs into domain services let `hold_code == 'X'` leak into pricing rules within a sprint. The anti-corruption layer (ACL)—from Domain-Driven Design—sits between contexts and translates, validates, and rejects inbound concepts so your model stays coherent even when the upstream system is neither owned nor fixable.


## Boundary placement

```
[ Legacy ERP API ] → [ ACL module ] → [ Your domain services ]
                           ↓
                    rejects / maps
```

Only ACL imports legacy SDK types. Domain layer sees `InboundShipmentNotice`, not `ErpAsnXml`.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

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

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Validate at the gate

ACL validates foreign payloads before translation: required fields, numeric ranges, enum subsets. Fail fast with structured errors to integration monitoring. Do not pass partially parsed legacy objects inward hoping domain catches issues.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Outbound translation

Publishing to legacy requires ACL too—your `CancelOrder` command becomes their `VOID_SO` XML with reason codes they accept. Bidirectional ACL prevents domain from learning their verb names.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Testing ACL

Contract tests against legacy sandbox fixtures. Golden files for sample payloads → expected domain objects. When vendor changes schema, tests fail in ACL PR—not in checkout math.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## ACL vs shared kernel

Shared kernel suits closely aligned teams with joint model ownership. ACL suits vendor and legacy boundaries you do not control. Choosing wrong pattern creates either duplication angst (ACL) or coupling pain (shared kernel).

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


ACL enables strangler migrations: start read-only sync, expand translated commands, shrink legacy surface. When legacy retires, delete ACL module—not refactor domain.

Contract tests against legacy sandbox fixtures—golden files for payload to domain mapping. Vendor schema changes fail ACL PR, not pricing math.

Bidirectional ACL on outbound—domain never learns VOID_SO verb names. Unsupported inbound statuses route to manual review queue, not silent null.

Delete ACL module when legacy retires—do not refactor domain to absorb their fields at last minute.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

Document the decision, owner, and rollback path in your team wiki the same week you ship. Future you will not remember which environment variable toggled the behavior unless it is written next to the runbook entry and linked from the alert. That habit costs ten minutes per change and saves hours when pagination or auth misbehaves under a single large tenant.



Run the change through your standard PR checklist: tests, observability, and a two-minute rollback drill in staging. Small operational habits accumulate into systems that survive on-call nights without heroics.


Share a short write-up in your engineering channel after rollout: what shipped, what metric you watch, and who owns follow-up. That closes the loop for teammates who were not in the PR and surfaces gaps in docs before the next person repeats the same investigation.

## Resources

- [Domain-Driven Design (Eric Evans)](https://www.domainlanguage.com/ddd/)
- [Microsoft Azure: Anti-Corruption Layer pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/anti-corruption-layer)
- [Implementing Domain-Driven Design (Vaughn Vernon)](https://vaughnvernon.com/)
- [Martin Fowler: Bounded Context](https://martinfowler.com/bliki/BoundedContext.html)
- [Strangler Fig pattern](https://martinfowler.com/bliki/StranglerFigApplication.html)
