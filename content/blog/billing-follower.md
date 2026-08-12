---
title: "Billing Follower"
slug: "billing-follower"
description: "Billing Follower: how to ship it with clear ownership and rollback in production saas systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2026-07-23"
dateModified: "2026-08-12"
tags:
  - "SaaS"
  - "Backend"
keywords: "billing, follower, saas, production, engineering"
faq:
  - q: "What is Billing Follower?"
    a: "Billing Follower is a production approach to ship it with clear ownership and rollback. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Billing Follower?"
    a: "Invest when the feature is on a critical user journey. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Billing Follower?"
    a: "The usual failure is copying a tutorial without matching constraints. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Billing Follower** means you ship it with clear ownership and rollback — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when the feature is on a critical user journey; that is usually also when shortcuts like copying a tutorial without matching constraints start paging people.

Below is how I implement and operate it in SaaS systems using Postgres, Stripe: the contracts, the failure modes, and the checks I want before merge.

## The short answer on Billing Follower

I have watched teams under-specify Billing Follower and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to ship it with clear ownership and rollback.

In SaaS stacks I lean on Postgres, Stripe for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when copying a tutorial without matching constraints.

Write the acceptance check in product language: when the feature is on a critical user journey, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

## Constraints before abstractions

If you only remember one thing about Billing Follower: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can ship it with clear ownership and rollback.

The anti-pattern is copying a tutorial without matching constraints. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Practically, being able to ship it with clear ownership and rollback means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```typescript
export async function handle(input: unknown): Promise<Result> {
  const parsed = schema.safeParse(input);
  if (!parsed.success) throw new ValidationError(parsed.error);
  // Billing Follower
  return repo.execute(parsed.data);
}
```

## Reference shape using Postgres

I have watched teams under-specify Billing Follower and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to ship it with clear ownership and rollback.

The anti-pattern is copying a tutorial without matching constraints. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Prefer small diffs with a kill switch. Billing Follower changes that require a hero engineer on-call are not done, even if the feature flag is green.

I also keep a short 'never again' list beside the code: copying a tutorial without matching constraints; skipping Billing Follower error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; copying a tutorial without matching constraints |
| Durable path | the feature is on a critical user journey | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Comparison: quick path vs durable path

If you only remember one thing about Billing Follower: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can ship it with clear ownership and rollback.

The anti-pattern is copying a tutorial without matching constraints. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Write the acceptance check in product language: when the feature is on a critical user journey, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

For reviews, I ask: what happens twice? what happens never? what happens partially? Billing Follower designs that cannot answer those three questions are not production-ready.

## Edge cases that break demos

If you only remember one thing about Billing Follower: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can ship it with clear ownership and rollback.

The anti-pattern is copying a tutorial without matching constraints. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Prefer small diffs with a kill switch. Billing Follower changes that require a hero engineer on-call are not done, even if the feature flag is green.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Shipping without painting into a corner

Most write-ups on Billing Follower stop at the demo. This one starts from situations where the feature is on a critical user journey, because that is when the abstraction either pays rent or becomes toil.

In SaaS stacks I lean on Postgres, Stripe for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when copying a tutorial without matching constraints.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

## Practical defaults I use for Billing Follower

If you only remember one thing about Billing Follower: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can ship it with clear ownership and rollback.

The anti-pattern is copying a tutorial without matching constraints. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Prefer small diffs with a kill switch. Billing Follower changes that require a hero engineer on-call are not done, even if the feature flag is green.

A month in, prune unused paths. Billing Follower accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Review questions before merging Billing Follower work

I have watched teams under-specify Billing Follower and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to ship it with clear ownership and rollback.

Make Billing Follower error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Billing Follower — you only deployed it.

Prefer small diffs with a kill switch. Billing Follower changes that require a hero engineer on-call are not done, even if the feature flag is green.

A month in, prune unused paths. Billing Follower accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Field notes after the first month of Billing Follower

Most write-ups on Billing Follower stop at the demo. This one starts from situations where the feature is on a critical user journey, because that is when the abstraction either pays rent or becomes toil.

In SaaS stacks I lean on Postgres, Stripe for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when copying a tutorial without matching constraints.

Write the acceptance check in product language: when the feature is on a critical user journey, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Billing Follower error rate. Expand only when the metric says you must.

## Resources

- https://martinfowler.com/
- https://12factor.net/
