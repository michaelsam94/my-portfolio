---
title: "Billing Exporter"
slug: "billing-exporter"
description: "Billing Exporter: how to ship it with clear ownership and rollback in production rust systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2026-07-19"
dateModified: "2026-08-12"
tags:
  - "Rust"
  - "Systems"
keywords: "billing, exporter, rust, production, engineering"
faq:
  - q: "What is Billing Exporter?"
    a: "Billing Exporter is a production approach to ship it with clear ownership and rollback. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Billing Exporter?"
    a: "Invest when the feature is on a critical user journey. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Billing Exporter?"
    a: "The usual failure is copying a tutorial without matching constraints. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Billing Exporter** means you ship it with clear ownership and rollback — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when the feature is on a critical user journey; that is usually also when shortcuts like copying a tutorial without matching constraints start paging people.

Below is how I implement and operate it in Rust systems using Axum, Tokio: the contracts, the failure modes, and the checks I want before merge.

## Incident story: when Billing Exporter bit us

If you only remember one thing about Billing Exporter: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can ship it with clear ownership and rollback.

Make Billing Exporter error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Billing Exporter — you only deployed it.

Write the acceptance check in product language: when the feature is on a critical user journey, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

## Root cause in one paragraph

I have watched teams under-specify Billing Exporter and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to ship it with clear ownership and rollback.

Make Billing Exporter error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Billing Exporter — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Practically, being able to ship it with clear ownership and rollback means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```rust
pub async fn handle(state: &State, input: Input) -> Result<Output, AppError> {
  // Billing Exporter
  state.repo.execute(input.validate()?).await.map_err(AppError::from)
}
```

## Fix that survived the next traffic spike

Most write-ups on Billing Exporter stop at the demo. This one starts from situations where the feature is on a critical user journey, because that is when the abstraction either pays rent or becomes toil.

Make Billing Exporter error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Billing Exporter — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

I also keep a short 'never again' list beside the code: copying a tutorial without matching constraints; skipping Billing Exporter error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; copying a tutorial without matching constraints |
| Durable path | the feature is on a critical user journey | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Tests that would have caught it

Most write-ups on Billing Exporter stop at the demo. This one starts from situations where the feature is on a critical user journey, because that is when the abstraction either pays rent or becomes toil.

In Rust stacks I lean on Axum, Tokio for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when copying a tutorial without matching constraints.

Prefer small diffs with a kill switch. Billing Exporter changes that require a hero engineer on-call are not done, even if the feature flag is green.

For reviews, I ask: what happens twice? what happens never? what happens partially? Billing Exporter designs that cannot answer those three questions are not production-ready.

## Runbook additions worth keeping

If you only remember one thing about Billing Exporter: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can ship it with clear ownership and rollback.

Make Billing Exporter error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Billing Exporter — you only deployed it.

Prefer small diffs with a kill switch. Billing Exporter changes that require a hero engineer on-call are not done, even if the feature flag is green.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Prevention in the platform

Most write-ups on Billing Exporter stop at the demo. This one starts from situations where the feature is on a critical user journey, because that is when the abstraction either pays rent or becomes toil.

In Rust stacks I lean on Axum, Tokio for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when copying a tutorial without matching constraints.

Write the acceptance check in product language: when the feature is on a critical user journey, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

## Practical defaults I use for Billing Exporter

If you only remember one thing about Billing Exporter: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can ship it with clear ownership and rollback.

In Rust stacks I lean on Axum, Tokio for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when copying a tutorial without matching constraints.

Prefer small diffs with a kill switch. Billing Exporter changes that require a hero engineer on-call are not done, even if the feature flag is green.

A month in, prune unused paths. Billing Exporter accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Review questions before merging Billing Exporter work

If you only remember one thing about Billing Exporter: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can ship it with clear ownership and rollback.

Make Billing Exporter error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Billing Exporter — you only deployed it.

Prefer small diffs with a kill switch. Billing Exporter changes that require a hero engineer on-call are not done, even if the feature flag is green.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Billing Exporter error rate. Expand only when the metric says you must.

## Field notes after the first month of Billing Exporter

If you only remember one thing about Billing Exporter: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can ship it with clear ownership and rollback.

In Rust stacks I lean on Axum, Tokio for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when copying a tutorial without matching constraints.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on copying a tutorial without matching constraints. If it is missing, the PR is incomplete.

## Resources

- https://martinfowler.com/
- https://12factor.net/
