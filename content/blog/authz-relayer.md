---
title: "Authz Relayer"
slug: "authz-relayer"
description: "Authz Relayer: how to ship it with clear ownership and rollback in production ios systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2026-04-17"
dateModified: "2026-08-12"
tags:
  - "iOS"
  - "Mobile"
keywords: "authz, relayer, ios, production, engineering"
faq:
  - q: "What is Authz Relayer?"
    a: "Authz Relayer is a production approach to ship it with clear ownership and rollback. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Authz Relayer?"
    a: "Invest when the feature is on a critical user journey. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Authz Relayer?"
    a: "The usual failure is copying a tutorial without matching constraints. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Authz Relayer** means you ship it with clear ownership and rollback — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when the feature is on a critical user journey; that is usually also when shortcuts like copying a tutorial without matching constraints start paging people.

Below is how I implement and operate it in iOS systems using SwiftUI, Swift: the contracts, the failure modes, and the checks I want before merge.

## Authz Relayer: production checklist

If you only remember one thing about Authz Relayer: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can ship it with clear ownership and rollback.

In iOS stacks I lean on SwiftUI, Swift for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when copying a tutorial without matching constraints.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

## Inputs, outputs, and invariants

If you only remember one thing about Authz Relayer: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can ship it with clear ownership and rollback.

In iOS stacks I lean on SwiftUI, Swift for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when copying a tutorial without matching constraints.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Practically, being able to ship it with clear ownership and rollback means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```swift
actor SwiftUIClient {
  func run() async throws {
    try Task.checkCancellation()
    // Authz Relayer
  }
}
```

## Concurrency and retry behavior

I have watched teams under-specify Authz Relayer and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to ship it with clear ownership and rollback.

Make Authz Relayer error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Relayer — you only deployed it.

Write the acceptance check in product language: when the feature is on a critical user journey, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

I also keep a short 'never again' list beside the code: copying a tutorial without matching constraints; skipping Authz Relayer error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; copying a tutorial without matching constraints |
| Durable path | the feature is on a critical user journey | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Human workflows (support, ops, audit)

Most write-ups on Authz Relayer stop at the demo. This one starts from situations where the feature is on a critical user journey, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is copying a tutorial without matching constraints. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

For reviews, I ask: what happens twice? what happens never? what happens partially? Authz Relayer designs that cannot answer those three questions are not production-ready.

## Load and capacity notes

I have watched teams under-specify Authz Relayer and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to ship it with clear ownership and rollback.

In iOS stacks I lean on SwiftUI, Swift for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when copying a tutorial without matching constraints.

Prefer small diffs with a kill switch. Authz Relayer changes that require a hero engineer on-call are not done, even if the feature flag is green.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Definition of done

I have watched teams under-specify Authz Relayer and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to ship it with clear ownership and rollback.

In iOS stacks I lean on SwiftUI, Swift for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when copying a tutorial without matching constraints.

Write the acceptance check in product language: when the feature is on a critical user journey, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

## Practical defaults I use for Authz Relayer

If you only remember one thing about Authz Relayer: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can ship it with clear ownership and rollback.

Make Authz Relayer error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Relayer — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Authz Relayer error rate. Expand only when the metric says you must.

## Review questions before merging Authz Relayer work

Most write-ups on Authz Relayer stop at the demo. This one starts from situations where the feature is on a critical user journey, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is copying a tutorial without matching constraints. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Prefer small diffs with a kill switch. Authz Relayer changes that require a hero engineer on-call are not done, even if the feature flag is green.

A month in, prune unused paths. Authz Relayer accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Field notes after the first month of Authz Relayer

I have watched teams under-specify Authz Relayer and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to ship it with clear ownership and rollback.

Make Authz Relayer error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Relayer — you only deployed it.

Prefer small diffs with a kill switch. Authz Relayer changes that require a hero engineer on-call are not done, even if the feature flag is green.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Authz Relayer error rate. Expand only when the metric says you must.

## Resources

- https://martinfowler.com/
- https://12factor.net/
