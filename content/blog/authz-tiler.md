---
title: "Authz Tiler"
slug: "authz-tiler"
description: "Authz Tiler: how to make retries and timeouts intentional in production dataeng systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2026-05-27"
dateModified: "2026-08-12"
tags:
  - "Data"
  - "Engineering"
keywords: "authz, tiler, dataeng, production, engineering"
faq:
  - q: "What is Authz Tiler?"
    a: "Authz Tiler is a production approach to make retries and timeouts intentional. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Authz Tiler?"
    a: "Invest when you are replacing a fragile legacy path. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Authz Tiler?"
    a: "The usual failure is unlimited retries on non-idempotent calls. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Authz Tiler** means you make retries and timeouts intentional — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when you are replacing a fragile legacy path; that is usually also when shortcuts like unlimited retries on non-idempotent calls start paging people.

Below is how I implement and operate it in DataEng systems using Spark, Airflow: the contracts, the failure modes, and the checks I want before merge.

## Decision guide for Authz Tiler

If you only remember one thing about Authz Tiler: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can make retries and timeouts intentional.

The anti-pattern is unlimited retries on non-idempotent calls. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Write the acceptance check in product language: when you are replacing a fragile legacy path, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

## When this is the wrong tool

I have watched teams under-specify Authz Tiler and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to make retries and timeouts intentional.

In DataEng stacks I lean on Spark, Airflow for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when unlimited retries on non-idempotent calls.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Practically, being able to make retries and timeouts intentional means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```sql
-- Authz Tiler
INSERT INTO example_events (tenant_id, event_id, payload)
VALUES ($1, $2, $3)
ON CONFLICT (tenant_id, event_id) DO NOTHING;
```

## Minimal viable production setup

I have watched teams under-specify Authz Tiler and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to make retries and timeouts intentional.

In DataEng stacks I lean on Spark, Airflow for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when unlimited retries on non-idempotent calls.

Write the acceptance check in product language: when you are replacing a fragile legacy path, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

I also keep a short 'never again' list beside the code: unlimited retries on non-idempotent calls; skipping Authz Tiler error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; unlimited retries on non-idempotent calls |
| Durable path | you are replacing a fragile legacy path | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Cost and complexity tradeoffs

Most write-ups on Authz Tiler stop at the demo. This one starts from situations where you are replacing a fragile legacy path, because that is when the abstraction either pays rent or becomes toil.

In DataEng stacks I lean on Spark, Airflow for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when unlimited retries on non-idempotent calls.

Prefer small diffs with a kill switch. Authz Tiler changes that require a hero engineer on-call are not done, even if the feature flag is green.

For reviews, I ask: what happens twice? what happens never? what happens partially? Authz Tiler designs that cannot answer those three questions are not production-ready.

## Migration sequence

If you only remember one thing about Authz Tiler: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can make retries and timeouts intentional.

The anti-pattern is unlimited retries on non-idempotent calls. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Acceptance checks before you call it done

Most write-ups on Authz Tiler stop at the demo. This one starts from situations where you are replacing a fragile legacy path, because that is when the abstraction either pays rent or becomes toil.

In DataEng stacks I lean on Spark, Airflow for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when unlimited retries on non-idempotent calls.

Write the acceptance check in product language: when you are replacing a fragile legacy path, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

## Practical defaults I use for Authz Tiler

I have watched teams under-specify Authz Tiler and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to make retries and timeouts intentional.

Make Authz Tiler error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Tiler — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

A month in, prune unused paths. Authz Tiler accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Review questions before merging Authz Tiler work

Most write-ups on Authz Tiler stop at the demo. This one starts from situations where you are replacing a fragile legacy path, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is unlimited retries on non-idempotent calls. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Prefer small diffs with a kill switch. Authz Tiler changes that require a hero engineer on-call are not done, even if the feature flag is green.

A month in, prune unused paths. Authz Tiler accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Field notes after the first month of Authz Tiler

I have watched teams under-specify Authz Tiler and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to make retries and timeouts intentional.

Make Authz Tiler error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Tiler — you only deployed it.

Write the acceptance check in product language: when you are replacing a fragile legacy path, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

A month in, prune unused paths. Authz Tiler accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Resources

- https://martinfowler.com/
- https://12factor.net/
