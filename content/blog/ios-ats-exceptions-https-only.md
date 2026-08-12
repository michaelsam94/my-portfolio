---
title: "App Transport Security Exceptions Done Right"
slug: "ios-ats-exceptions-https-only"
description: "App Transport Security Exceptions Done Right: how to narrow ATS exceptions in production ios systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2025-08-16"
dateModified: "2026-08-12"
tags:
  - "iOS"
  - "SwiftUI"
  - "Mobile"
keywords: "ios, ats, exceptions, https, only, production, engineering"
faq:
  - q: "What is App Transport Security Exceptions Done Right?"
    a: "App Transport Security Exceptions Done Right is a production approach to narrow ATS exceptions. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in App Transport Security Exceptions Done Right?"
    a: "Invest when legacy device endpoints. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with App Transport Security Exceptions Done Right?"
    a: "The usual failure is NSAllowsArbitraryLoads in production. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**App Transport Security Exceptions Done Right** means you narrow ATS exceptions — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when you hit legacy device endpoints; that is usually also when shortcuts like NSAllowsArbitraryLoads in production start paging people.

Below is how I implement and operate it in iOS systems using SwiftUI, Swift, UIKit: the contracts, the failure modes, and the checks I want before merge.

## How I explain App Transport Security Exceptions Done Right to a skeptical teammate

Most write-ups on App Transport Security Exceptions Done Right stop at the demo. This one starts from situations where legacy device endpoints, because that is when the abstraction either pays rent or becomes toil.

Make App Transport Security Exceptions Done Right error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate App Transport Security Exceptions Done Right — you only deployed it.

Prefer small diffs with a kill switch. App Transport Security Exceptions Done Right changes that require a hero engineer on-call are not done, even if the feature flag is green.

## Doing work to narrow ATS exceptions

Most write-ups on App Transport Security Exceptions Done Right stop at the demo. This one starts from situations where legacy device endpoints, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is NSAllowsArbitraryLoads in production. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Prefer small diffs with a kill switch. App Transport Security Exceptions Done Right changes that require a hero engineer on-call are not done, even if the feature flag is green.

Practically, being able to narrow ATS exceptions means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```swift
actor SwiftUIClient {
  func run() async throws {
    try Task.checkCancellation()
    // App Transport Security Exceptions Done Right
  }
}
```

## Code boundaries that keep refactors cheap

If you only remember one thing about App Transport Security Exceptions Done Right: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can narrow ATS exceptions.

The anti-pattern is NSAllowsArbitraryLoads in production. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

I also keep a short 'never again' list beside the code: NSAllowsArbitraryLoads in production; skipping App Transport Security Exceptions Done Right error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; NSAllowsArbitraryLoads in production |
| Durable path | legacy device endpoints | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Table stakes vs nice-to-haves

Most write-ups on App Transport Security Exceptions Done Right stop at the demo. This one starts from situations where legacy device endpoints, because that is when the abstraction either pays rent or becomes toil.

Make App Transport Security Exceptions Done Right error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate App Transport Security Exceptions Done Right — you only deployed it.

Prefer small diffs with a kill switch. App Transport Security Exceptions Done Right changes that require a hero engineer on-call are not done, even if the feature flag is green.

For reviews, I ask: what happens twice? what happens never? what happens partially? App Transport Security Exceptions Done Right designs that cannot answer those three questions are not production-ready.

## Common regressions after launch

Most write-ups on App Transport Security Exceptions Done Right stop at the demo. This one starts from situations where legacy device endpoints, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is NSAllowsArbitraryLoads in production. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Prefer small diffs with a kill switch. App Transport Security Exceptions Done Right changes that require a hero engineer on-call are not done, even if the feature flag is green.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Maintenance burden over 12 months

Most write-ups on App Transport Security Exceptions Done Right stop at the demo. This one starts from situations where legacy device endpoints, because that is when the abstraction either pays rent or becomes toil.

In iOS stacks I lean on SwiftUI, Swift, UIKit for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when NSAllowsArbitraryLoads in production.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

## Practical defaults I use for App Transport Security Exceptions Done Right

Most write-ups on App Transport Security Exceptions Done Right stop at the demo. This one starts from situations where legacy device endpoints, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is NSAllowsArbitraryLoads in production. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on NSAllowsArbitraryLoads in production. If it is missing, the PR is incomplete.

## Review questions before merging App Transport Security Exceptions Done Right work

I have watched teams under-specify App Transport Security Exceptions Done Right and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to narrow ATS exceptions.

In iOS stacks I lean on SwiftUI, Swift, UIKit for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when NSAllowsArbitraryLoads in production.

Prefer small diffs with a kill switch. App Transport Security Exceptions Done Right changes that require a hero engineer on-call are not done, even if the feature flag is green.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on NSAllowsArbitraryLoads in production. If it is missing, the PR is incomplete.

## Field notes after the first month of App Transport Security Exceptions Done Right

I have watched teams under-specify App Transport Security Exceptions Done Right and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to narrow ATS exceptions.

In iOS stacks I lean on SwiftUI, Swift, UIKit for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when NSAllowsArbitraryLoads in production.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on NSAllowsArbitraryLoads in production. If it is missing, the PR is incomplete.

## Resources

- https://martinfowler.com/
- https://12factor.net/
