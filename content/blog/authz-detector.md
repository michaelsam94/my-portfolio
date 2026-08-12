---
title: "Authz Detector"
slug: "authz-detector"
description: "Authz Detector: how to ship it with clear ownership and rollback in production android systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2026-02-16"
dateModified: "2026-08-12"
tags:
  - "Android"
  - "Mobile"
keywords: "authz, detector, android, production, engineering"
faq:
  - q: "What is Authz Detector?"
    a: "Authz Detector is a production approach to ship it with clear ownership and rollback. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Authz Detector?"
    a: "Invest when the feature is on a critical user journey. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Authz Detector?"
    a: "The usual failure is copying a tutorial without matching constraints. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Authz Detector** means you ship it with clear ownership and rollback — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when the feature is on a critical user journey; that is usually also when shortcuts like copying a tutorial without matching constraints start paging people.

Below is how I implement and operate it in Android systems using Kotlin, CameraX: the contracts, the failure modes, and the checks I want before merge.

## Building Authz Detector into an existing system

I have watched teams under-specify Authz Detector and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to ship it with clear ownership and rollback.

The anti-pattern is copying a tutorial without matching constraints. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Write the acceptance check in product language: when the feature is on a critical user journey, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

## Contracts and ownership

Most write-ups on Authz Detector stop at the demo. This one starts from situations where the feature is on a critical user journey, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is copying a tutorial without matching constraints. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Prefer small diffs with a kill switch. Authz Detector changes that require a hero engineer on-call are not done, even if the feature flag is green.

Practically, being able to ship it with clear ownership and rollback means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```kotlin
interface KotlinGateway { suspend fun execute(input: Request): Result<Response> }
// Authz Detector
```

## Data and state implications

I have watched teams under-specify Authz Detector and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to ship it with clear ownership and rollback.

Make Authz Detector error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Detector — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

I also keep a short 'never again' list beside the code: copying a tutorial without matching constraints; skipping Authz Detector error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; copying a tutorial without matching constraints |
| Durable path | the feature is on a critical user journey | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Security notes that are not optional

I have watched teams under-specify Authz Detector and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to ship it with clear ownership and rollback.

Make Authz Detector error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Detector — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

For reviews, I ask: what happens twice? what happens never? what happens partially? Authz Detector designs that cannot answer those three questions are not production-ready.

## Observability and SLOs

I have watched teams under-specify Authz Detector and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to ship it with clear ownership and rollback.

The anti-pattern is copying a tutorial without matching constraints. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Prefer small diffs with a kill switch. Authz Detector changes that require a hero engineer on-call are not done, even if the feature flag is green.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Week-one validation plan

Most write-ups on Authz Detector stop at the demo. This one starts from situations where the feature is on a critical user journey, because that is when the abstraction either pays rent or becomes toil.

Make Authz Detector error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Detector — you only deployed it.

Write the acceptance check in product language: when the feature is on a critical user journey, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

## Practical defaults I use for Authz Detector

Most write-ups on Authz Detector stop at the demo. This one starts from situations where the feature is on a critical user journey, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is copying a tutorial without matching constraints. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on copying a tutorial without matching constraints. If it is missing, the PR is incomplete.

## Review questions before merging Authz Detector work

I have watched teams under-specify Authz Detector and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to ship it with clear ownership and rollback.

In Android stacks I lean on Kotlin, CameraX for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when copying a tutorial without matching constraints.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on copying a tutorial without matching constraints. If it is missing, the PR is incomplete.

## Field notes after the first month of Authz Detector

I have watched teams under-specify Authz Detector and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to ship it with clear ownership and rollback.

The anti-pattern is copying a tutorial without matching constraints. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Write the acceptance check in product language: when the feature is on a critical user journey, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

A month in, prune unused paths. Authz Detector accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Resources

- https://martinfowler.com/
- https://12factor.net/
