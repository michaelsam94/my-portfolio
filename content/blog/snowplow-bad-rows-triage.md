---
title: "Snowplow Bad Rows Triage"
slug: "snowplow-bad-rows-triage"
description: "Snowplow Bad Rows Triage: how to avoid the demo-only happy path in production dataeng systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2025-12-10"
dateModified: "2026-08-12"
tags:
  - "Data"
  - "Engineering"
keywords: "snowplow, bad, rows, triage, dataeng, production, engineering"
faq:
  - q: "What is Snowplow Bad Rows Triage?"
    a: "Snowplow Bad Rows Triage is a production approach to avoid the demo-only happy path. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Snowplow Bad Rows Triage?"
    a: "Invest when on-call already feels this pain weekly. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Snowplow Bad Rows Triage?"
    a: "The usual failure is dual-writing without an outbox. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Snowplow Bad Rows Triage** means you avoid the demo-only happy path — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when on-call already feels this pain weekly; that is usually also when shortcuts like dual-writing without an outbox start paging people.

Below is how I implement and operate it in DataEng systems using Spark, Airflow: the contracts, the failure modes, and the checks I want before merge.

## The short answer on Snowplow Bad Rows Triage

Most write-ups on Snowplow Bad Rows Triage stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is dual-writing without an outbox. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Write the acceptance check in product language: when on-call already feels this pain weekly, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

## Constraints before abstractions

Most write-ups on Snowplow Bad Rows Triage stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is dual-writing without an outbox. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Practically, being able to avoid the demo-only happy path means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```sql
-- Snowplow Bad Rows Triage
INSERT INTO example_events (tenant_id, event_id, payload)
VALUES ($1, $2, $3)
ON CONFLICT (tenant_id, event_id) DO NOTHING;
```

## Reference shape using Spark

Most write-ups on Snowplow Bad Rows Triage stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

In DataEng stacks I lean on Spark, Airflow for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when dual-writing without an outbox.

Prefer small diffs with a kill switch. Snowplow Bad Rows Triage changes that require a hero engineer on-call are not done, even if the feature flag is green.

I also keep a short 'never again' list beside the code: dual-writing without an outbox; skipping Snowplow Bad Rows Triage error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; dual-writing without an outbox |
| Durable path | on-call already feels this pain weekly | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Comparison: quick path vs durable path

If you only remember one thing about Snowplow Bad Rows Triage: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can avoid the demo-only happy path.

In DataEng stacks I lean on Spark, Airflow for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when dual-writing without an outbox.

Prefer small diffs with a kill switch. Snowplow Bad Rows Triage changes that require a hero engineer on-call are not done, even if the feature flag is green.

For reviews, I ask: what happens twice? what happens never? what happens partially? Snowplow Bad Rows Triage designs that cannot answer those three questions are not production-ready.

## Edge cases that break demos

I have watched teams under-specify Snowplow Bad Rows Triage and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

Make Snowplow Bad Rows Triage error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Snowplow Bad Rows Triage — you only deployed it.

Prefer small diffs with a kill switch. Snowplow Bad Rows Triage changes that require a hero engineer on-call are not done, even if the feature flag is green.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Shipping without painting into a corner

Most write-ups on Snowplow Bad Rows Triage stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is dual-writing without an outbox. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

## Practical defaults I use for Snowplow Bad Rows Triage

If you only remember one thing about Snowplow Bad Rows Triage: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can avoid the demo-only happy path.

Make Snowplow Bad Rows Triage error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Snowplow Bad Rows Triage — you only deployed it.

Write the acceptance check in product language: when on-call already feels this pain weekly, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on dual-writing without an outbox. If it is missing, the PR is incomplete.

## Review questions before merging Snowplow Bad Rows Triage work

Most write-ups on Snowplow Bad Rows Triage stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

In DataEng stacks I lean on Spark, Airflow for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when dual-writing without an outbox.

Prefer small diffs with a kill switch. Snowplow Bad Rows Triage changes that require a hero engineer on-call are not done, even if the feature flag is green.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Snowplow Bad Rows Triage error rate. Expand only when the metric says you must.

## Field notes after the first month of Snowplow Bad Rows Triage

If you only remember one thing about Snowplow Bad Rows Triage: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can avoid the demo-only happy path.

In DataEng stacks I lean on Spark, Airflow for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when dual-writing without an outbox.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Snowplow Bad Rows Triage error rate. Expand only when the metric says you must.

## Resources

- https://martinfowler.com/
- https://12factor.net/
