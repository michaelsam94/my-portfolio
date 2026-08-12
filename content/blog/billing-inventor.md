---
title: "Billing Inventor"
slug: "billing-inventor"
description: "Billing Inventor: how to keep failure modes explicit and tested in production platform systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2026-08-03"
dateModified: "2026-08-12"
tags:
  - "Platform"
  - "DX"
keywords: "billing, inventor, platform, production, engineering"
faq:
  - q: "What is Billing Inventor?"
    a: "Billing Inventor is a production approach to keep failure modes explicit and tested. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Billing Inventor?"
    a: "Invest when traffic or tenants are about to scale. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Billing Inventor?"
    a: "The usual failure is skipping metrics until after launch. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Billing Inventor** means you keep failure modes explicit and tested — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when traffic or tenants are about to scale; that is usually also when shortcuts like skipping metrics until after launch start paging people.

Below is how I implement and operate it in Platform systems using GitHub Actions, Docker: the contracts, the failure modes, and the checks I want before merge.

## Incident story: when Billing Inventor bit us

If you only remember one thing about Billing Inventor: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can keep failure modes explicit and tested.

The anti-pattern is skipping metrics until after launch. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Write the acceptance check in product language: when traffic or tenants are about to scale, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

## Root cause in one paragraph

Most write-ups on Billing Inventor stop at the demo. This one starts from situations where traffic or tenants are about to scale, because that is when the abstraction either pays rent or becomes toil.

Make Billing Inventor error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Billing Inventor — you only deployed it.

Write the acceptance check in product language: when traffic or tenants are about to scale, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Practically, being able to keep failure modes explicit and tested means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```typescript
export async function handle(input: unknown): Promise<Result> {
  const parsed = schema.safeParse(input);
  if (!parsed.success) throw new ValidationError(parsed.error);
  // Billing Inventor
  return repo.execute(parsed.data);
}
```

## Fix that survived the next traffic spike

Most write-ups on Billing Inventor stop at the demo. This one starts from situations where traffic or tenants are about to scale, because that is when the abstraction either pays rent or becomes toil.

Make Billing Inventor error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Billing Inventor — you only deployed it.

Prefer small diffs with a kill switch. Billing Inventor changes that require a hero engineer on-call are not done, even if the feature flag is green.

I also keep a short 'never again' list beside the code: skipping metrics until after launch; skipping Billing Inventor error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; skipping metrics until after launch |
| Durable path | traffic or tenants are about to scale | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Tests that would have caught it

If you only remember one thing about Billing Inventor: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can keep failure modes explicit and tested.

In Platform stacks I lean on GitHub Actions, Docker for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when skipping metrics until after launch.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

For reviews, I ask: what happens twice? what happens never? what happens partially? Billing Inventor designs that cannot answer those three questions are not production-ready.

## Runbook additions worth keeping

I have watched teams under-specify Billing Inventor and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to keep failure modes explicit and tested.

In Platform stacks I lean on GitHub Actions, Docker for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when skipping metrics until after launch.

Write the acceptance check in product language: when traffic or tenants are about to scale, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Prevention in the platform

I have watched teams under-specify Billing Inventor and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to keep failure modes explicit and tested.

In Platform stacks I lean on GitHub Actions, Docker for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when skipping metrics until after launch.

Prefer small diffs with a kill switch. Billing Inventor changes that require a hero engineer on-call are not done, even if the feature flag is green.

## Practical defaults I use for Billing Inventor

If you only remember one thing about Billing Inventor: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can keep failure modes explicit and tested.

The anti-pattern is skipping metrics until after launch. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

A month in, prune unused paths. Billing Inventor accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Review questions before merging Billing Inventor work

If you only remember one thing about Billing Inventor: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can keep failure modes explicit and tested.

In Platform stacks I lean on GitHub Actions, Docker for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when skipping metrics until after launch.

Write the acceptance check in product language: when traffic or tenants are about to scale, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Billing Inventor error rate. Expand only when the metric says you must.

## Field notes after the first month of Billing Inventor

If you only remember one thing about Billing Inventor: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can keep failure modes explicit and tested.

The anti-pattern is skipping metrics until after launch. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Write the acceptance check in product language: when traffic or tenants are about to scale, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on skipping metrics until after launch. If it is missing, the PR is incomplete.

## Resources

- https://martinfowler.com/
- https://12factor.net/
