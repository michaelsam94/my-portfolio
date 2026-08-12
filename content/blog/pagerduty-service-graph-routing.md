---
title: "Pagerduty Service Graph Routing"
slug: "pagerduty-service-graph-routing"
description: "Pagerduty Service Graph Routing: how to keep failure modes explicit and tested in production rust systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2025-09-14"
dateModified: "2026-08-12"
tags:
  - "Rust"
  - "Systems"
keywords: "pagerduty, service, graph, routing, rust, production, engineering"
faq:
  - q: "What is Pagerduty Service Graph Routing?"
    a: "Pagerduty Service Graph Routing is a production approach to keep failure modes explicit and tested. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Pagerduty Service Graph Routing?"
    a: "Invest when traffic or tenants are about to scale. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Pagerduty Service Graph Routing?"
    a: "The usual failure is skipping metrics until after launch. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Pagerduty Service Graph Routing** means you keep failure modes explicit and tested — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when traffic or tenants are about to scale; that is usually also when shortcuts like skipping metrics until after launch start paging people.

Below is how I implement and operate it in Rust systems using Axum, Tokio: the contracts, the failure modes, and the checks I want before merge.

## Where Pagerduty Service Graph Routing actually shows up

If you only remember one thing about Pagerduty Service Graph Routing: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can keep failure modes explicit and tested.

The anti-pattern is skipping metrics until after launch. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

## A design that makes it routine to keep failure modes explicit and tested

Most write-ups on Pagerduty Service Graph Routing stop at the demo. This one starts from situations where traffic or tenants are about to scale, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is skipping metrics until after launch. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Practically, being able to keep failure modes explicit and tested means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```rust
pub async fn handle(state: &State, input: Input) -> Result<Output, AppError> {
  // Pagerduty Service Graph Routing
  state.repo.execute(input.validate()?).await.map_err(AppError::from)
}
```

## The failure mode I see in reviews

I have watched teams under-specify Pagerduty Service Graph Routing and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to keep failure modes explicit and tested.

The anti-pattern is skipping metrics until after launch. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

I also keep a short 'never again' list beside the code: skipping metrics until after launch; skipping Pagerduty Service Graph Routing error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; skipping metrics until after launch |
| Durable path | traffic or tenants are about to scale | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Instrumentation that answers the on-call question

Most write-ups on Pagerduty Service Graph Routing stop at the demo. This one starts from situations where traffic or tenants are about to scale, because that is when the abstraction either pays rent or becomes toil.

In Rust stacks I lean on Axum, Tokio for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when skipping metrics until after launch.

Prefer small diffs with a kill switch. Pagerduty Service Graph Routing changes that require a hero engineer on-call are not done, even if the feature flag is green.

For reviews, I ask: what happens twice? what happens never? what happens partially? Pagerduty Service Graph Routing designs that cannot answer those three questions are not production-ready.

## Rollout checklist

Most write-ups on Pagerduty Service Graph Routing stop at the demo. This one starts from situations where traffic or tenants are about to scale, because that is when the abstraction either pays rent or becomes toil.

Make Pagerduty Service Graph Routing error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Pagerduty Service Graph Routing — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## What I would not do again

I have watched teams under-specify Pagerduty Service Graph Routing and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to keep failure modes explicit and tested.

Make Pagerduty Service Graph Routing error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Pagerduty Service Graph Routing — you only deployed it.

Prefer small diffs with a kill switch. Pagerduty Service Graph Routing changes that require a hero engineer on-call are not done, even if the feature flag is green.

## Practical defaults I use for Pagerduty Service Graph Routing

Most write-ups on Pagerduty Service Graph Routing stop at the demo. This one starts from situations where traffic or tenants are about to scale, because that is when the abstraction either pays rent or becomes toil.

Make Pagerduty Service Graph Routing error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Pagerduty Service Graph Routing — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

A month in, prune unused paths. Pagerduty Service Graph Routing accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Review questions before merging Pagerduty Service Graph Routing work

I have watched teams under-specify Pagerduty Service Graph Routing and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to keep failure modes explicit and tested.

Make Pagerduty Service Graph Routing error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Pagerduty Service Graph Routing — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on skipping metrics until after launch. If it is missing, the PR is incomplete.

## Field notes after the first month of Pagerduty Service Graph Routing

I have watched teams under-specify Pagerduty Service Graph Routing and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to keep failure modes explicit and tested.

The anti-pattern is skipping metrics until after launch. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Prefer small diffs with a kill switch. Pagerduty Service Graph Routing changes that require a hero engineer on-call are not done, even if the feature flag is green.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on skipping metrics until after launch. If it is missing, the PR is incomplete.

## Resources

- https://martinfowler.com/
- https://12factor.net/
