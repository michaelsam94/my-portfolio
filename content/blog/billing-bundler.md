---
title: "Billing Bundler"
slug: "billing-bundler"
description: "Billing Bundler: how to avoid the demo-only happy path in production datastores systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2026-06-30"
dateModified: "2026-08-12"
tags:
  - "Database"
  - "Backend"
keywords: "billing, bundler, datastores, production, engineering"
faq:
  - q: "What is Billing Bundler?"
    a: "Billing Bundler is a production approach to avoid the demo-only happy path. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Billing Bundler?"
    a: "Invest when on-call already feels this pain weekly. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Billing Bundler?"
    a: "The usual failure is dual-writing without an outbox. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Billing Bundler** means you avoid the demo-only happy path — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when on-call already feels this pain weekly; that is usually also when shortcuts like dual-writing without an outbox start paging people.

Below is how I implement and operate it in DataStores systems using Postgres, Redis: the contracts, the failure modes, and the checks I want before merge.

## Billing Bundler: production checklist

Most write-ups on Billing Bundler stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

Make Billing Bundler error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Billing Bundler — you only deployed it.

Write the acceptance check in product language: when on-call already feels this pain weekly, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

## Inputs, outputs, and invariants

I have watched teams under-specify Billing Bundler and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

Make Billing Bundler error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Billing Bundler — you only deployed it.

Prefer small diffs with a kill switch. Billing Bundler changes that require a hero engineer on-call are not done, even if the feature flag is green.

Practically, being able to avoid the demo-only happy path means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```sql
-- Billing Bundler
INSERT INTO example_events (tenant_id, event_id, payload)
VALUES ($1, $2, $3)
ON CONFLICT (tenant_id, event_id) DO NOTHING;
```

## Concurrency and retry behavior

I have watched teams under-specify Billing Bundler and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

In DataStores stacks I lean on Postgres, Redis for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when dual-writing without an outbox.

Prefer small diffs with a kill switch. Billing Bundler changes that require a hero engineer on-call are not done, even if the feature flag is green.

I also keep a short 'never again' list beside the code: dual-writing without an outbox; skipping Billing Bundler error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; dual-writing without an outbox |
| Durable path | on-call already feels this pain weekly | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Human workflows (support, ops, audit)

Most write-ups on Billing Bundler stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is dual-writing without an outbox. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Write the acceptance check in product language: when on-call already feels this pain weekly, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

For reviews, I ask: what happens twice? what happens never? what happens partially? Billing Bundler designs that cannot answer those three questions are not production-ready.

## Load and capacity notes

Most write-ups on Billing Bundler stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

In DataStores stacks I lean on Postgres, Redis for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when dual-writing without an outbox.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Definition of done

Most write-ups on Billing Bundler stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

Make Billing Bundler error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Billing Bundler — you only deployed it.

Write the acceptance check in product language: when on-call already feels this pain weekly, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

## Practical defaults I use for Billing Bundler

If you only remember one thing about Billing Bundler: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can avoid the demo-only happy path.

The anti-pattern is dual-writing without an outbox. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Prefer small diffs with a kill switch. Billing Bundler changes that require a hero engineer on-call are not done, even if the feature flag is green.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on dual-writing without an outbox. If it is missing, the PR is incomplete.

## Review questions before merging Billing Bundler work

If you only remember one thing about Billing Bundler: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can avoid the demo-only happy path.

In DataStores stacks I lean on Postgres, Redis for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when dual-writing without an outbox.

Prefer small diffs with a kill switch. Billing Bundler changes that require a hero engineer on-call are not done, even if the feature flag is green.

A month in, prune unused paths. Billing Bundler accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Field notes after the first month of Billing Bundler

Most write-ups on Billing Bundler stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

In DataStores stacks I lean on Postgres, Redis for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when dual-writing without an outbox.

Write the acceptance check in product language: when on-call already feels this pain weekly, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Billing Bundler error rate. Expand only when the metric says you must.

## Resources

- https://martinfowler.com/
- https://12factor.net/
