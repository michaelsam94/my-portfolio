---
title: "Kong Opa Plugin"
slug: "kong-opa-plugin"
description: "Kong Opa Plugin: how to avoid the demo-only happy path in production android systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2026-01-15"
dateModified: "2026-08-12"
tags:
  - "Android"
  - "Mobile"
keywords: "kong, opa, plugin, android, production, engineering"
faq:
  - q: "What is Kong Opa Plugin?"
    a: "Kong Opa Plugin is a production approach to avoid the demo-only happy path. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Kong Opa Plugin?"
    a: "Invest when on-call already feels this pain weekly. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Kong Opa Plugin?"
    a: "The usual failure is dual-writing without an outbox. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Kong Opa Plugin** means you avoid the demo-only happy path — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when on-call already feels this pain weekly; that is usually also when shortcuts like dual-writing without an outbox start paging people.

Below is how I implement and operate it in Android systems using Kotlin, CameraX: the contracts, the failure modes, and the checks I want before merge.

## Incident story: when Kong Opa Plugin bit us

I have watched teams under-specify Kong Opa Plugin and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

Make Kong Opa Plugin error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Kong Opa Plugin — you only deployed it.

Prefer small diffs with a kill switch. Kong Opa Plugin changes that require a hero engineer on-call are not done, even if the feature flag is green.

## Root cause in one paragraph

I have watched teams under-specify Kong Opa Plugin and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

In Android stacks I lean on Kotlin, CameraX for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when dual-writing without an outbox.

Prefer small diffs with a kill switch. Kong Opa Plugin changes that require a hero engineer on-call are not done, even if the feature flag is green.

Practically, being able to avoid the demo-only happy path means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```kotlin
interface KotlinGateway { suspend fun execute(input: Request): Result<Response> }
// Kong Opa Plugin
```

## Fix that survived the next traffic spike

I have watched teams under-specify Kong Opa Plugin and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

Make Kong Opa Plugin error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Kong Opa Plugin — you only deployed it.

Write the acceptance check in product language: when on-call already feels this pain weekly, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

I also keep a short 'never again' list beside the code: dual-writing without an outbox; skipping Kong Opa Plugin error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; dual-writing without an outbox |
| Durable path | on-call already feels this pain weekly | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Tests that would have caught it

Most write-ups on Kong Opa Plugin stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is dual-writing without an outbox. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

For reviews, I ask: what happens twice? what happens never? what happens partially? Kong Opa Plugin designs that cannot answer those three questions are not production-ready.

## Runbook additions worth keeping

Most write-ups on Kong Opa Plugin stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

Make Kong Opa Plugin error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Kong Opa Plugin — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Prevention in the platform

I have watched teams under-specify Kong Opa Plugin and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

In Android stacks I lean on Kotlin, CameraX for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when dual-writing without an outbox.

Prefer small diffs with a kill switch. Kong Opa Plugin changes that require a hero engineer on-call are not done, even if the feature flag is green.

## Practical defaults I use for Kong Opa Plugin

Most write-ups on Kong Opa Plugin stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

Make Kong Opa Plugin error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Kong Opa Plugin — you only deployed it.

Write the acceptance check in product language: when on-call already feels this pain weekly, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on dual-writing without an outbox. If it is missing, the PR is incomplete.

## Review questions before merging Kong Opa Plugin work

I have watched teams under-specify Kong Opa Plugin and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

Make Kong Opa Plugin error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Kong Opa Plugin — you only deployed it.

Write the acceptance check in product language: when on-call already feels this pain weekly, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on dual-writing without an outbox. If it is missing, the PR is incomplete.

## Field notes after the first month of Kong Opa Plugin

If you only remember one thing about Kong Opa Plugin: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can avoid the demo-only happy path.

The anti-pattern is dual-writing without an outbox. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Write the acceptance check in product language: when on-call already feels this pain weekly, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

A month in, prune unused paths. Kong Opa Plugin accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Resources

- https://martinfowler.com/
- https://12factor.net/
