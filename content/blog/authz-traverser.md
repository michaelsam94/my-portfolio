---
title: "Authz Traverser"
slug: "authz-traverser"
description: "Authz Traverser: how to avoid the demo-only happy path in production flutter systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2026-06-03"
dateModified: "2026-08-12"
tags:
  - "Flutter"
  - "Mobile"
keywords: "authz, traverser, flutter, production, engineering"
faq:
  - q: "What is Authz Traverser?"
    a: "Authz Traverser is a production approach to avoid the demo-only happy path. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Authz Traverser?"
    a: "Invest when on-call already feels this pain weekly. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Authz Traverser?"
    a: "The usual failure is dual-writing without an outbox. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Authz Traverser** means you avoid the demo-only happy path — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when on-call already feels this pain weekly; that is usually also when shortcuts like dual-writing without an outbox start paging people.

Below is how I implement and operate it in Flutter systems using Flutter, Dart: the contracts, the failure modes, and the checks I want before merge.

## Incident story: when Authz Traverser bit us

If you only remember one thing about Authz Traverser: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can avoid the demo-only happy path.

Make Authz Traverser error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Traverser — you only deployed it.

Prefer small diffs with a kill switch. Authz Traverser changes that require a hero engineer on-call are not done, even if the feature flag is green.

## Root cause in one paragraph

I have watched teams under-specify Authz Traverser and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

In Flutter stacks I lean on Flutter, Dart for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when dual-writing without an outbox.

Prefer small diffs with a kill switch. Authz Traverser changes that require a hero engineer on-call are not done, even if the feature flag is green.

Practically, being able to avoid the demo-only happy path means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```dart
class FlutterRepository {
  Future<Result> run(Request req) async {
    // Authz Traverser
    return Result.ok(await _client.post('/v1/action', body: req.toJson()));
  }
}
```

## Fix that survived the next traffic spike

If you only remember one thing about Authz Traverser: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can avoid the demo-only happy path.

In Flutter stacks I lean on Flutter, Dart for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when dual-writing without an outbox.

Prefer small diffs with a kill switch. Authz Traverser changes that require a hero engineer on-call are not done, even if the feature flag is green.

I also keep a short 'never again' list beside the code: dual-writing without an outbox; skipping Authz Traverser error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; dual-writing without an outbox |
| Durable path | on-call already feels this pain weekly | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Tests that would have caught it

I have watched teams under-specify Authz Traverser and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

Make Authz Traverser error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Traverser — you only deployed it.

Prefer small diffs with a kill switch. Authz Traverser changes that require a hero engineer on-call are not done, even if the feature flag is green.

For reviews, I ask: what happens twice? what happens never? what happens partially? Authz Traverser designs that cannot answer those three questions are not production-ready.

## Runbook additions worth keeping

If you only remember one thing about Authz Traverser: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can avoid the demo-only happy path.

Make Authz Traverser error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Traverser — you only deployed it.

Write the acceptance check in product language: when on-call already feels this pain weekly, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Prevention in the platform

I have watched teams under-specify Authz Traverser and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

In Flutter stacks I lean on Flutter, Dart for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when dual-writing without an outbox.

Write the acceptance check in product language: when on-call already feels this pain weekly, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

## Practical defaults I use for Authz Traverser

If you only remember one thing about Authz Traverser: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can avoid the demo-only happy path.

Make Authz Traverser error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Traverser — you only deployed it.

Write the acceptance check in product language: when on-call already feels this pain weekly, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Authz Traverser error rate. Expand only when the metric says you must.

## Review questions before merging Authz Traverser work

I have watched teams under-specify Authz Traverser and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

Make Authz Traverser error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Traverser — you only deployed it.

Prefer small diffs with a kill switch. Authz Traverser changes that require a hero engineer on-call are not done, even if the feature flag is green.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on dual-writing without an outbox. If it is missing, the PR is incomplete.

## Field notes after the first month of Authz Traverser

If you only remember one thing about Authz Traverser: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can avoid the demo-only happy path.

Make Authz Traverser error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Traverser — you only deployed it.

Prefer small diffs with a kill switch. Authz Traverser changes that require a hero engineer on-call are not done, even if the feature flag is green.

A month in, prune unused paths. Authz Traverser accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Resources

- https://martinfowler.com/
- https://12factor.net/
