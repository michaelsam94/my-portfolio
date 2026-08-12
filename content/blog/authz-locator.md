---
title: "Authz Locator"
slug: "authz-locator"
description: "Authz Locator: how to keep failure modes explicit and tested in production dataeng systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2026-03-15"
dateModified: "2026-08-12"
tags:
  - "Data"
  - "Engineering"
keywords: "authz, locator, dataeng, production, engineering"
faq:
  - q: "What is Authz Locator?"
    a: "Authz Locator is a production approach to keep failure modes explicit and tested. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Authz Locator?"
    a: "Invest when traffic or tenants are about to scale. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Authz Locator?"
    a: "The usual failure is skipping metrics until after launch. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Authz Locator** means you keep failure modes explicit and tested — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when traffic or tenants are about to scale; that is usually also when shortcuts like skipping metrics until after launch start paging people.

Below is how I implement and operate it in DataEng systems using Spark, Airflow: the contracts, the failure modes, and the checks I want before merge.

## Authz Locator: production checklist

If you only remember one thing about Authz Locator: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can keep failure modes explicit and tested.

The anti-pattern is skipping metrics until after launch. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Prefer small diffs with a kill switch. Authz Locator changes that require a hero engineer on-call are not done, even if the feature flag is green.

## Inputs, outputs, and invariants

I have watched teams under-specify Authz Locator and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to keep failure modes explicit and tested.

In DataEng stacks I lean on Spark, Airflow for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when skipping metrics until after launch.

Prefer small diffs with a kill switch. Authz Locator changes that require a hero engineer on-call are not done, even if the feature flag is green.

Practically, being able to keep failure modes explicit and tested means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```sql
-- Authz Locator
INSERT INTO example_events (tenant_id, event_id, payload)
VALUES ($1, $2, $3)
ON CONFLICT (tenant_id, event_id) DO NOTHING;
```

## Concurrency and retry behavior

If you only remember one thing about Authz Locator: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can keep failure modes explicit and tested.

In DataEng stacks I lean on Spark, Airflow for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when skipping metrics until after launch.

Prefer small diffs with a kill switch. Authz Locator changes that require a hero engineer on-call are not done, even if the feature flag is green.

I also keep a short 'never again' list beside the code: skipping metrics until after launch; skipping Authz Locator error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; skipping metrics until after launch |
| Durable path | traffic or tenants are about to scale | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Human workflows (support, ops, audit)

If you only remember one thing about Authz Locator: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can keep failure modes explicit and tested.

Make Authz Locator error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Locator — you only deployed it.

Write the acceptance check in product language: when traffic or tenants are about to scale, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

For reviews, I ask: what happens twice? what happens never? what happens partially? Authz Locator designs that cannot answer those three questions are not production-ready.

## Load and capacity notes

If you only remember one thing about Authz Locator: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can keep failure modes explicit and tested.

Make Authz Locator error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Locator — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Definition of done

Most write-ups on Authz Locator stop at the demo. This one starts from situations where traffic or tenants are about to scale, because that is when the abstraction either pays rent or becomes toil.

Make Authz Locator error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Locator — you only deployed it.

Prefer small diffs with a kill switch. Authz Locator changes that require a hero engineer on-call are not done, even if the feature flag is green.

## Practical defaults I use for Authz Locator

I have watched teams under-specify Authz Locator and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to keep failure modes explicit and tested.

The anti-pattern is skipping metrics until after launch. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Authz Locator error rate. Expand only when the metric says you must.

## Review questions before merging Authz Locator work

I have watched teams under-specify Authz Locator and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to keep failure modes explicit and tested.

In DataEng stacks I lean on Spark, Airflow for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when skipping metrics until after launch.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Authz Locator error rate. Expand only when the metric says you must.

## Field notes after the first month of Authz Locator

Most write-ups on Authz Locator stop at the demo. This one starts from situations where traffic or tenants are about to scale, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is skipping metrics until after launch. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on skipping metrics until after launch. If it is missing, the PR is incomplete.

## Resources

- https://martinfowler.com/
- https://12factor.net/
