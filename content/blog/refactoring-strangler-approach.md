---
title: "Refactoring with the Strangler Approach"
slug: "refactoring-strangler-approach"
description: "Replace a legacy system incrementally with the strangler fig pattern: routing seams, parallel runs, and cutover criteria that avoid big-bang rewrites."
datePublished: "2025-04-01"
dateModified: "2025-04-01"
tags: ["Refactoring", "Architecture", "Legacy Systems", "Migration"]
keywords: "strangler fig pattern, incremental migration, legacy modernization, routing facade, parallel run, feature parity, cutover strategy"
faq:
  - q: "When should I use the strangler pattern instead of a rewrite?"
    a: "Use it when the legacy system still earns revenue or carries compliance obligations you cannot pause. A rewrite freezes feature work for months and hides unknown edge cases until launch day. The strangler lets you ship new behavior behind a routing seam while the old code keeps running, so you migrate slice by slice with measurable rollback points."
  - q: "Where do I put the routing seam?"
    a: "Place it at the narrowest stable boundary you control: an API gateway, a message bus topic router, or a facade module inside the monolith. The seam should see every request for the capability you are replacing, yet stay ignorant of business rules on either side. If you cannot intercept 100% of traffic for a feature, that slice is not ready to strangler yet."
  - q: "How do I know a slice is safe to cut over?"
    a: "Define parity metrics before you start: response schema, latency p99, error rate, and a handful of golden-path integration tests replayed against both implementations. Run shadow traffic or parallel writes long enough to catch reconciliation drift. Cut over only when diffs stay within tolerance for a full business cycle, not after a single green CI run."
---

Your checkout service still runs on a Spring monolith from 2016. Product wants subscriptions, finance wants PCI scope reduced, and engineering wants out of the Oracle dependency. A six-month rewrite sounds clean until you realize nobody documented how gift cards interact with tax-exempt B2B orders. The strangler fig pattern—named after vines that gradually replace a host tree—lets you grow a new system around the old one until the legacy piece can be removed without a launch-day cliff.

## Identify a vertical slice, not a layer

The most common strangler mistake is replacing "the database layer" or "all REST endpoints" in one pass. Layers cut horizontally across features; stranglers cut vertically through one user-visible capability. Pick something with clear inputs and outputs: "apply a coupon at checkout," "generate monthly invoices," or "sync inventory to the warehouse API."

For each slice, document the contract the rest of the system expects today—HTTP paths, queue message shapes, batch file formats. That contract becomes your acceptance test harness. Everything else inside the slice is free to change.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Insert a routing seam early

Before you write replacement logic, put a router in front of the legacy code. At the HTTP edge, that might be an API gateway rule; inside a monolith, a thin module that delegates to either `LegacyCheckout` or `CheckoutV2`.

```kotlin
class CheckoutRouter(
    private val legacy: LegacyCheckoutService,
    private val modern: ModernCheckoutService,
    private val flags: FeatureFlags,
) {
    fun applyCoupon(orderId: String, code: String): CouponResult {
        return if (flags.isEnabled("checkout-v2", orderId)) {
            modern.applyCoupon(orderId, code)
        } else {
            legacy.applyCoupon(orderId, code)
        }
    }
}
```

The flag can start at 0% traffic. What matters is that every call path already flows through the seam. Adding the router first prevents the "we'll swap it at the end" rewrite that never finds all the callers.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Run old and new in parallel

For write paths, parallel execution catches subtle divergence. Execute the legacy path as the source of truth while asynchronously invoking the new implementation and comparing results:

```python
def apply_coupon(order_id: str, code: str) -> Result:
    legacy_result = legacy.apply_coupon(order_id, code)
    if shadow_enabled(order_id):
        enqueue_shadow_job(order_id, code, legacy_result)
    return legacy_result
```

Log structured diffs: field name, legacy value, new value. Teams that skip shadow mode discover rounding and timezone bugs in production. Read paths can often skip dual writes but should still replay production traffic in a staging environment weekly.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Migrate data without stopping the world

Stranglers fail when teams treat data migration as a one-night cutover. Prefer incremental sync: change data capture from the legacy database, an outbox table, or nightly reconciliation jobs that backfill the new store. Maintain a correlation ID so you can trace one order through both systems during overlap.

Keep the legacy schema authoritative until parity is proven, then flip a write toggle so new mutations land in the modern store while legacy reads fall through to a compatibility view. Decommission the old table only after you have verified no batch job still queries it.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Define cutover and rollback criteria

Write the decision down before emotions run high. Example criteria: fewer than 0.01% shadow diffs for seven days, p99 latency within 10% of legacy, and sign-off from the team that owns downstream consumers. Rollback must be a flag flip, not a redeploy—if reverting requires a schema rollback, you are not ready.

Schedule cutovers outside peak traffic and keep the legacy code path compiled (even if unreachable) for one release cycle. Teams that delete legacy immediately often redeploy old Git SHAs under pressure.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Retire the host tree

When traffic, data, and operational runbooks all point to the new implementation, remove the legacy branch from the router and delete dead code in the same pull request. Leave the seam interface if other slices still route through it. Document what you learned in an ADR so the next migration starts from a playbook, not from scratch.

Teams that succeed with strangler migrations treat parity dashboards as product features, not test artifacts. Wire shadow diffs to Grafana with alerts when mismatch rate exceeds baseline during business hours. Product owners sign cutover checklists—not only engineering leads—because behavioral differences often surface as revenue impact before they surface as ERROR logs.

Keep a living inventory of remaining legacy slices ranked by risk and customer exposure. Migrate painful integrations early while motivation is high, not after easy UI wins create false confidence. When organizational pressure pushes for premature legacy deletion, point to the rollback drill log: if you have not executed a flag-flip rollback in staging in the last quarter, you are not ready to delete the old branch.

Partner teams consuming your slice need migration notices with timeline, diff examples, and a contact for integration questions. Strangler work is sociotechnical; routing code is the easy half. Document every known parity gap with owner and target date—gaps without owners become production bugs within one release cycle.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Resources

- [Strangler Fig Application (Martin Fowler)](https://martinfowler.com/bliki/StranglerFigApplication.html)
- [Microsoft Azure Architecture Center: Strangler Fig pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/strangler-fig)
- [Working Effectively with Legacy Code (Feathers)](https://www.oreilly.com/library/view/working-effectively-with/9780131177055/)
- [Feature Toggles (Martin Fowler)](https://martinfowler.com/articles/feature-toggles.html)
- [AWS Prescriptive Guidance: Legacy modernization patterns](https://docs.aws.amazon.com/prescriptive-guidance/latest/strategy-migration/introduction.html)
