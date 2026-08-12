---
title: "Authz Scanner"
slug: "authz-scanner"
description: "Authz Scanner: how to avoid the demo-only happy path in production android systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2026-04-29"
dateModified: "2026-08-12"
tags:
  - "Android"
  - "Mobile"
keywords: "authz, scanner, android, production, engineering"
faq:
  - q: "What is Authz Scanner?"
    a: "Authz Scanner is a production approach to avoid the demo-only happy path. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Authz Scanner?"
    a: "Invest when on-call already feels this pain weekly. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Authz Scanner?"
    a: "The usual failure is dual-writing without an outbox. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Authz Scanner** means you avoid the demo-only happy path — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when on-call already feels this pain weekly; that is usually also when shortcuts like dual-writing without an outbox start paging people.

Below is how I implement and operate it in Android systems using Kotlin, CameraX: the contracts, the failure modes, and the checks I want before merge.

## Decision guide for Authz Scanner

If you only remember one thing about Authz Scanner: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can avoid the demo-only happy path.

The anti-pattern is dual-writing without an outbox. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Write the acceptance check in product language: when on-call already feels this pain weekly, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

## When this is the wrong tool

Most write-ups on Authz Scanner stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

Make Authz Scanner error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Scanner — you only deployed it.

Prefer small diffs with a kill switch. Authz Scanner changes that require a hero engineer on-call are not done, even if the feature flag is green.

Practically, being able to avoid the demo-only happy path means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```kotlin
interface KotlinGateway { suspend fun execute(input: Request): Result<Response> }
// Authz Scanner
```

## Minimal viable production setup

Most write-ups on Authz Scanner stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is dual-writing without an outbox. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

I also keep a short 'never again' list beside the code: dual-writing without an outbox; skipping Authz Scanner error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; dual-writing without an outbox |
| Durable path | on-call already feels this pain weekly | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Cost and complexity tradeoffs

If you only remember one thing about Authz Scanner: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can avoid the demo-only happy path.

Make Authz Scanner error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Scanner — you only deployed it.

Prefer small diffs with a kill switch. Authz Scanner changes that require a hero engineer on-call are not done, even if the feature flag is green.

For reviews, I ask: what happens twice? what happens never? what happens partially? Authz Scanner designs that cannot answer those three questions are not production-ready.

## Migration sequence

Most write-ups on Authz Scanner stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

In Android stacks I lean on Kotlin, CameraX for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when dual-writing without an outbox.

Write the acceptance check in product language: when on-call already feels this pain weekly, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Acceptance checks before you call it done

I have watched teams under-specify Authz Scanner and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

Make Authz Scanner error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Scanner — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

## Practical defaults I use for Authz Scanner

Most write-ups on Authz Scanner stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is dual-writing without an outbox. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Prefer small diffs with a kill switch. Authz Scanner changes that require a hero engineer on-call are not done, even if the feature flag is green.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Authz Scanner error rate. Expand only when the metric says you must.

## Review questions before merging Authz Scanner work

I have watched teams under-specify Authz Scanner and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

Make Authz Scanner error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Scanner — you only deployed it.

Prefer small diffs with a kill switch. Authz Scanner changes that require a hero engineer on-call are not done, even if the feature flag is green.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on dual-writing without an outbox. If it is missing, the PR is incomplete.

## Field notes after the first month of Authz Scanner

Most write-ups on Authz Scanner stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

Make Authz Scanner error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Scanner — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Authz Scanner error rate. Expand only when the metric says you must.

## Resources

- https://martinfowler.com/
- https://12factor.net/
