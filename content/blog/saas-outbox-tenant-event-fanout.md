---
title: "Per-Tenant Event Fan-Out with Outbox"
slug: "saas-outbox-tenant-event-fanout"
description: "Per-Tenant Event Fan-Out with Outbox: how to avoid dual writes for integrations in production saas systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2025-09-02"
dateModified: "2026-08-12"
tags:
  - "SaaS"
  - "Backend"
  - "Billing"
keywords: "saas, outbox, tenant, event, fanout, production, engineering"
faq:
  - q: "What is Per-Tenant Event Fan-Out with Outbox?"
    a: "Per-Tenant Event Fan-Out with Outbox is a production approach to avoid dual writes for integrations. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Per-Tenant Event Fan-Out with Outbox?"
    a: "Invest when integration-heavy SaaS. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Per-Tenant Event Fan-Out with Outbox?"
    a: "The usual failure is publishing before commit. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Per-Tenant Event Fan-Out with Outbox** means you avoid dual writes for integrations — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when you hit integration-heavy SaaS; that is usually also when shortcuts like publishing before commit start paging people.

Below is how I implement and operate it in SaaS systems using Postgres, Stripe, Redis: the contracts, the failure modes, and the checks I want before merge.

## How I explain Per-Tenant Event Fan-Out with Outbox to a skeptical teammate

Most write-ups on Per-Tenant Event Fan-Out with Outbox stop at the demo. This one starts from situations where integration-heavy SaaS, because that is when the abstraction either pays rent or becomes toil.

In SaaS stacks I lean on Postgres, Stripe, Redis for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when publishing before commit.

Write the acceptance check in product language: when integration-heavy SaaS, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

## Doing work to avoid dual writes for integrations

If you only remember one thing about Per-Tenant Event Fan-Out with Outbox: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can avoid dual writes for integrations.

Make Per-Tenant Event Fan-Out with Outbox error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Per-Tenant Event Fan-Out with Outbox — you only deployed it.

Prefer small diffs with a kill switch. Per-Tenant Event Fan-Out with Outbox changes that require a hero engineer on-call are not done, even if the feature flag is green.

Practically, being able to avoid dual writes for integrations means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```typescript
export async function handle(input: unknown): Promise<Result> {
  const parsed = schema.safeParse(input);
  if (!parsed.success) throw new ValidationError(parsed.error);
  // Per-Tenant Event Fan-Out with Outbox
  return repo.execute(parsed.data);
}
```

## Code boundaries that keep refactors cheap

If you only remember one thing about Per-Tenant Event Fan-Out with Outbox: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can avoid dual writes for integrations.

In SaaS stacks I lean on Postgres, Stripe, Redis for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when publishing before commit.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

I also keep a short 'never again' list beside the code: publishing before commit; skipping Per-Tenant Event Fan-Out with Outbox error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; publishing before commit |
| Durable path | integration-heavy SaaS | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Table stakes vs nice-to-haves

If you only remember one thing about Per-Tenant Event Fan-Out with Outbox: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can avoid dual writes for integrations.

Make Per-Tenant Event Fan-Out with Outbox error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Per-Tenant Event Fan-Out with Outbox — you only deployed it.

Prefer small diffs with a kill switch. Per-Tenant Event Fan-Out with Outbox changes that require a hero engineer on-call are not done, even if the feature flag is green.

For reviews, I ask: what happens twice? what happens never? what happens partially? Per-Tenant Event Fan-Out with Outbox designs that cannot answer those three questions are not production-ready.

## Common regressions after launch

Most write-ups on Per-Tenant Event Fan-Out with Outbox stop at the demo. This one starts from situations where integration-heavy SaaS, because that is when the abstraction either pays rent or becomes toil.

Make Per-Tenant Event Fan-Out with Outbox error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Per-Tenant Event Fan-Out with Outbox — you only deployed it.

Write the acceptance check in product language: when integration-heavy SaaS, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Maintenance burden over 12 months

I have watched teams under-specify Per-Tenant Event Fan-Out with Outbox and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid dual writes for integrations.

Make Per-Tenant Event Fan-Out with Outbox error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Per-Tenant Event Fan-Out with Outbox — you only deployed it.

Write the acceptance check in product language: when integration-heavy SaaS, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

## Practical defaults I use for Per-Tenant Event Fan-Out with Outbox

I have watched teams under-specify Per-Tenant Event Fan-Out with Outbox and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid dual writes for integrations.

Make Per-Tenant Event Fan-Out with Outbox error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Per-Tenant Event Fan-Out with Outbox — you only deployed it.

Prefer small diffs with a kill switch. Per-Tenant Event Fan-Out with Outbox changes that require a hero engineer on-call are not done, even if the feature flag is green.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on publishing before commit. If it is missing, the PR is incomplete.

## Review questions before merging Per-Tenant Event Fan-Out with Outbox work

Most write-ups on Per-Tenant Event Fan-Out with Outbox stop at the demo. This one starts from situations where integration-heavy SaaS, because that is when the abstraction either pays rent or becomes toil.

In SaaS stacks I lean on Postgres, Stripe, Redis for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when publishing before commit.

Prefer small diffs with a kill switch. Per-Tenant Event Fan-Out with Outbox changes that require a hero engineer on-call are not done, even if the feature flag is green.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Per-Tenant Event Fan-Out with Outbox error rate. Expand only when the metric says you must.

## Field notes after the first month of Per-Tenant Event Fan-Out with Outbox

Most write-ups on Per-Tenant Event Fan-Out with Outbox stop at the demo. This one starts from situations where integration-heavy SaaS, because that is when the abstraction either pays rent or becomes toil.

In SaaS stacks I lean on Postgres, Stripe, Redis for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when publishing before commit.

Prefer small diffs with a kill switch. Per-Tenant Event Fan-Out with Outbox changes that require a hero engineer on-call are not done, even if the feature flag is green.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Per-Tenant Event Fan-Out with Outbox error rate. Expand only when the metric says you must.

## Resources

- https://martinfowler.com/
- https://12factor.net/
