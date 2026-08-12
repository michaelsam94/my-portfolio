---
title: "Billing Harvester"
slug: "billing-harvester"
description: "Billing Harvester: how to ship it with clear ownership and rollback in production architecture systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2026-07-28"
dateModified: "2026-08-12"
tags:
  - "Architecture"
  - "Backend"
keywords: "billing, harvester, architecture, production, engineering"
faq:
  - q: "What is Billing Harvester?"
    a: "Billing Harvester is a production approach to ship it with clear ownership and rollback. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Billing Harvester?"
    a: "Invest when the feature is on a critical user journey. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Billing Harvester?"
    a: "The usual failure is copying a tutorial without matching constraints. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Billing Harvester** means you ship it with clear ownership and rollback — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when the feature is on a critical user journey; that is usually also when shortcuts like copying a tutorial without matching constraints start paging people.

Below is how I implement and operate it in Architecture systems using Kafka, Postgres: the contracts, the failure modes, and the checks I want before merge.

## Decision guide for Billing Harvester

Most write-ups on Billing Harvester stop at the demo. This one starts from situations where the feature is on a critical user journey, because that is when the abstraction either pays rent or becomes toil.

In Architecture stacks I lean on Kafka, Postgres for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when copying a tutorial without matching constraints.

Prefer small diffs with a kill switch. Billing Harvester changes that require a hero engineer on-call are not done, even if the feature flag is green.

## When this is the wrong tool

I have watched teams under-specify Billing Harvester and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to ship it with clear ownership and rollback.

The anti-pattern is copying a tutorial without matching constraints. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Write the acceptance check in product language: when the feature is on a critical user journey, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Practically, being able to ship it with clear ownership and rollback means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```typescript
export async function handle(input: unknown): Promise<Result> {
  const parsed = schema.safeParse(input);
  if (!parsed.success) throw new ValidationError(parsed.error);
  // Billing Harvester
  return repo.execute(parsed.data);
}
```

## Minimal viable production setup

I have watched teams under-specify Billing Harvester and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to ship it with clear ownership and rollback.

In Architecture stacks I lean on Kafka, Postgres for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when copying a tutorial without matching constraints.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

I also keep a short 'never again' list beside the code: copying a tutorial without matching constraints; skipping Billing Harvester error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; copying a tutorial without matching constraints |
| Durable path | the feature is on a critical user journey | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Cost and complexity tradeoffs

Most write-ups on Billing Harvester stop at the demo. This one starts from situations where the feature is on a critical user journey, because that is when the abstraction either pays rent or becomes toil.

Make Billing Harvester error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Billing Harvester — you only deployed it.

Write the acceptance check in product language: when the feature is on a critical user journey, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

For reviews, I ask: what happens twice? what happens never? what happens partially? Billing Harvester designs that cannot answer those three questions are not production-ready.

## Migration sequence

If you only remember one thing about Billing Harvester: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can ship it with clear ownership and rollback.

Make Billing Harvester error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Billing Harvester — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Acceptance checks before you call it done

Most write-ups on Billing Harvester stop at the demo. This one starts from situations where the feature is on a critical user journey, because that is when the abstraction either pays rent or becomes toil.

Make Billing Harvester error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Billing Harvester — you only deployed it.

Prefer small diffs with a kill switch. Billing Harvester changes that require a hero engineer on-call are not done, even if the feature flag is green.

## Practical defaults I use for Billing Harvester

I have watched teams under-specify Billing Harvester and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to ship it with clear ownership and rollback.

The anti-pattern is copying a tutorial without matching constraints. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on copying a tutorial without matching constraints. If it is missing, the PR is incomplete.

## Review questions before merging Billing Harvester work

I have watched teams under-specify Billing Harvester and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to ship it with clear ownership and rollback.

The anti-pattern is copying a tutorial without matching constraints. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Write the acceptance check in product language: when the feature is on a critical user journey, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Billing Harvester error rate. Expand only when the metric says you must.

## Field notes after the first month of Billing Harvester

Most write-ups on Billing Harvester stop at the demo. This one starts from situations where the feature is on a critical user journey, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is copying a tutorial without matching constraints. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Prefer small diffs with a kill switch. Billing Harvester changes that require a hero engineer on-call are not done, even if the feature flag is green.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Billing Harvester error rate. Expand only when the metric says you must.

## Resources

- https://martinfowler.com/
- https://12factor.net/
