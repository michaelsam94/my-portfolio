---
title: "Authz Director"
slug: "authz-director"
description: "Authz Director: how to measure the user-visible signal first in production rust systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2026-02-16"
dateModified: "2026-08-12"
tags:
  - "Rust"
  - "Systems"
keywords: "authz, director, rust, production, engineering"
faq:
  - q: "What is Authz Director?"
    a: "Authz Director is a production approach to measure the user-visible signal first. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Authz Director?"
    a: "Invest when auditors or enterprise buyers ask how you know it works. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Authz Director?"
    a: "The usual failure is treating edge cases as follow-ups. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Authz Director** means you measure the user-visible signal first — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when auditors or enterprise buyers ask how you know it works; that is usually also when shortcuts like treating edge cases as follow-ups start paging people.

Below is how I implement and operate it in Rust systems using Axum, Tokio: the contracts, the failure modes, and the checks I want before merge.

## Incident story: when Authz Director bit us

I have watched teams under-specify Authz Director and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to measure the user-visible signal first.

Make Authz Director error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Director — you only deployed it.

Write the acceptance check in product language: when auditors or enterprise buyers ask how you know it works, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

## Root cause in one paragraph

Most write-ups on Authz Director stop at the demo. This one starts from situations where auditors or enterprise buyers ask how you know it works, because that is when the abstraction either pays rent or becomes toil.

Make Authz Director error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Director — you only deployed it.

Write the acceptance check in product language: when auditors or enterprise buyers ask how you know it works, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Practically, being able to measure the user-visible signal first means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```rust
pub async fn handle(state: &State, input: Input) -> Result<Output, AppError> {
  // Authz Director
  state.repo.execute(input.validate()?).await.map_err(AppError::from)
}
```

## Fix that survived the next traffic spike

If you only remember one thing about Authz Director: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can measure the user-visible signal first.

In Rust stacks I lean on Axum, Tokio for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when treating edge cases as follow-ups.

Prefer small diffs with a kill switch. Authz Director changes that require a hero engineer on-call are not done, even if the feature flag is green.

I also keep a short 'never again' list beside the code: treating edge cases as follow-ups; skipping Authz Director error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; treating edge cases as follow-ups |
| Durable path | auditors or enterprise buyers ask how you know it works | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Tests that would have caught it

I have watched teams under-specify Authz Director and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to measure the user-visible signal first.

Make Authz Director error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Director — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

For reviews, I ask: what happens twice? what happens never? what happens partially? Authz Director designs that cannot answer those three questions are not production-ready.

## Runbook additions worth keeping

Most write-ups on Authz Director stop at the demo. This one starts from situations where auditors or enterprise buyers ask how you know it works, because that is when the abstraction either pays rent or becomes toil.

Make Authz Director error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Director — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Prevention in the platform

Most write-ups on Authz Director stop at the demo. This one starts from situations where auditors or enterprise buyers ask how you know it works, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is treating edge cases as follow-ups. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

## Practical defaults I use for Authz Director

If you only remember one thing about Authz Director: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can measure the user-visible signal first.

Make Authz Director error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Director — you only deployed it.

Write the acceptance check in product language: when auditors or enterprise buyers ask how you know it works, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Authz Director error rate. Expand only when the metric says you must.

## Review questions before merging Authz Director work

Most write-ups on Authz Director stop at the demo. This one starts from situations where auditors or enterprise buyers ask how you know it works, because that is when the abstraction either pays rent or becomes toil.

Make Authz Director error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Director — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on treating edge cases as follow-ups. If it is missing, the PR is incomplete.

## Field notes after the first month of Authz Director

I have watched teams under-specify Authz Director and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to measure the user-visible signal first.

Make Authz Director error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Director — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Authz Director error rate. Expand only when the metric says you must.

## Resources

- https://martinfowler.com/
- https://12factor.net/
