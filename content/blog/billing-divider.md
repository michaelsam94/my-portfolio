---
title: "Billing Divider"
slug: "billing-divider"
description: "Billing Divider: how to keep failure modes explicit and tested in production dataeng systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2026-07-14"
dateModified: "2026-08-12"
tags:
  - "Data"
  - "Engineering"
keywords: "billing, divider, dataeng, production, engineering"
faq:
  - q: "What is Billing Divider?"
    a: "Billing Divider is a production approach to keep failure modes explicit and tested. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Billing Divider?"
    a: "Invest when traffic or tenants are about to scale. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Billing Divider?"
    a: "The usual failure is skipping metrics until after launch. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Billing Divider** means you keep failure modes explicit and tested — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when traffic or tenants are about to scale; that is usually also when shortcuts like skipping metrics until after launch start paging people.

Below is how I implement and operate it in DataEng systems using Spark, Airflow: the contracts, the failure modes, and the checks I want before merge.

## How I explain Billing Divider to a skeptical teammate

I have watched teams under-specify Billing Divider and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to keep failure modes explicit and tested.

The anti-pattern is skipping metrics until after launch. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

## Doing work to keep failure modes explicit and tested

If you only remember one thing about Billing Divider: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can keep failure modes explicit and tested.

In DataEng stacks I lean on Spark, Airflow for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when skipping metrics until after launch.

Write the acceptance check in product language: when traffic or tenants are about to scale, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Practically, being able to keep failure modes explicit and tested means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```sql
-- Billing Divider
INSERT INTO example_events (tenant_id, event_id, payload)
VALUES ($1, $2, $3)
ON CONFLICT (tenant_id, event_id) DO NOTHING;
```

## Code boundaries that keep refactors cheap

Most write-ups on Billing Divider stop at the demo. This one starts from situations where traffic or tenants are about to scale, because that is when the abstraction either pays rent or becomes toil.

In DataEng stacks I lean on Spark, Airflow for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when skipping metrics until after launch.

Write the acceptance check in product language: when traffic or tenants are about to scale, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

I also keep a short 'never again' list beside the code: skipping metrics until after launch; skipping Billing Divider error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; skipping metrics until after launch |
| Durable path | traffic or tenants are about to scale | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Table stakes vs nice-to-haves

I have watched teams under-specify Billing Divider and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to keep failure modes explicit and tested.

In DataEng stacks I lean on Spark, Airflow for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when skipping metrics until after launch.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

For reviews, I ask: what happens twice? what happens never? what happens partially? Billing Divider designs that cannot answer those three questions are not production-ready.

## Common regressions after launch

Most write-ups on Billing Divider stop at the demo. This one starts from situations where traffic or tenants are about to scale, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is skipping metrics until after launch. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Prefer small diffs with a kill switch. Billing Divider changes that require a hero engineer on-call are not done, even if the feature flag is green.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Maintenance burden over 12 months

I have watched teams under-specify Billing Divider and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to keep failure modes explicit and tested.

The anti-pattern is skipping metrics until after launch. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Write the acceptance check in product language: when traffic or tenants are about to scale, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

## Practical defaults I use for Billing Divider

I have watched teams under-specify Billing Divider and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to keep failure modes explicit and tested.

In DataEng stacks I lean on Spark, Airflow for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when skipping metrics until after launch.

Prefer small diffs with a kill switch. Billing Divider changes that require a hero engineer on-call are not done, even if the feature flag is green.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Billing Divider error rate. Expand only when the metric says you must.

## Review questions before merging Billing Divider work

I have watched teams under-specify Billing Divider and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to keep failure modes explicit and tested.

Make Billing Divider error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Billing Divider — you only deployed it.

Write the acceptance check in product language: when traffic or tenants are about to scale, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on skipping metrics until after launch. If it is missing, the PR is incomplete.

## Field notes after the first month of Billing Divider

Most write-ups on Billing Divider stop at the demo. This one starts from situations where traffic or tenants are about to scale, because that is when the abstraction either pays rent or becomes toil.

In DataEng stacks I lean on Spark, Airflow for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when skipping metrics until after launch.

Write the acceptance check in product language: when traffic or tenants are about to scale, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Billing Divider error rate. Expand only when the metric says you must.

## Resources

- https://martinfowler.com/
- https://12factor.net/
