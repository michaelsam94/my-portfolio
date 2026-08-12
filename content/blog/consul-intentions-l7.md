---
title: "Consul Intentions L7"
slug: "consul-intentions-l7"
description: "Consul Intentions L7: how to keep failure modes explicit and tested in production payments systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2026-01-15"
dateModified: "2026-08-12"
tags:
  - "Payments"
  - "Fintech"
keywords: "consul, intentions, l7, payments, production, engineering"
faq:
  - q: "What is Consul Intentions L7?"
    a: "Consul Intentions L7 is a production approach to keep failure modes explicit and tested. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Consul Intentions L7?"
    a: "Invest when traffic or tenants are about to scale. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Consul Intentions L7?"
    a: "The usual failure is skipping metrics until after launch. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Consul Intentions L7** means you keep failure modes explicit and tested — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when traffic or tenants are about to scale; that is usually also when shortcuts like skipping metrics until after launch start paging people.

Below is how I implement and operate it in Payments systems using Stripe, ledger: the contracts, the failure modes, and the checks I want before merge.

## How I explain Consul Intentions L7 to a skeptical teammate

I have watched teams under-specify Consul Intentions L7 and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to keep failure modes explicit and tested.

The anti-pattern is skipping metrics until after launch. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

## Doing work to keep failure modes explicit and tested

Most write-ups on Consul Intentions L7 stop at the demo. This one starts from situations where traffic or tenants are about to scale, because that is when the abstraction either pays rent or becomes toil.

Make Consul Intentions L7 error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Consul Intentions L7 — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Practically, being able to keep failure modes explicit and tested means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```typescript
export async function handle(input: unknown): Promise<Result> {
  const parsed = schema.safeParse(input);
  if (!parsed.success) throw new ValidationError(parsed.error);
  // Consul Intentions L7
  return repo.execute(parsed.data);
}
```

## Code boundaries that keep refactors cheap

Most write-ups on Consul Intentions L7 stop at the demo. This one starts from situations where traffic or tenants are about to scale, because that is when the abstraction either pays rent or becomes toil.

Make Consul Intentions L7 error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Consul Intentions L7 — you only deployed it.

Write the acceptance check in product language: when traffic or tenants are about to scale, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

I also keep a short 'never again' list beside the code: skipping metrics until after launch; skipping Consul Intentions L7 error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; skipping metrics until after launch |
| Durable path | traffic or tenants are about to scale | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Table stakes vs nice-to-haves

I have watched teams under-specify Consul Intentions L7 and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to keep failure modes explicit and tested.

Make Consul Intentions L7 error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Consul Intentions L7 — you only deployed it.

Prefer small diffs with a kill switch. Consul Intentions L7 changes that require a hero engineer on-call are not done, even if the feature flag is green.

For reviews, I ask: what happens twice? what happens never? what happens partially? Consul Intentions L7 designs that cannot answer those three questions are not production-ready.

## Common regressions after launch

If you only remember one thing about Consul Intentions L7: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can keep failure modes explicit and tested.

In Payments stacks I lean on Stripe, ledger for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when skipping metrics until after launch.

Prefer small diffs with a kill switch. Consul Intentions L7 changes that require a hero engineer on-call are not done, even if the feature flag is green.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Maintenance burden over 12 months

I have watched teams under-specify Consul Intentions L7 and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to keep failure modes explicit and tested.

The anti-pattern is skipping metrics until after launch. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Prefer small diffs with a kill switch. Consul Intentions L7 changes that require a hero engineer on-call are not done, even if the feature flag is green.

## Practical defaults I use for Consul Intentions L7

If you only remember one thing about Consul Intentions L7: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can keep failure modes explicit and tested.

In Payments stacks I lean on Stripe, ledger for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when skipping metrics until after launch.

Write the acceptance check in product language: when traffic or tenants are about to scale, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

A month in, prune unused paths. Consul Intentions L7 accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Review questions before merging Consul Intentions L7 work

If you only remember one thing about Consul Intentions L7: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can keep failure modes explicit and tested.

The anti-pattern is skipping metrics until after launch. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

A month in, prune unused paths. Consul Intentions L7 accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Field notes after the first month of Consul Intentions L7

If you only remember one thing about Consul Intentions L7: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can keep failure modes explicit and tested.

In Payments stacks I lean on Stripe, ledger for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when skipping metrics until after launch.

Prefer small diffs with a kill switch. Consul Intentions L7 changes that require a hero engineer on-call are not done, even if the feature flag is green.

A month in, prune unused paths. Consul Intentions L7 accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Resources

- https://martinfowler.com/
- https://12factor.net/
