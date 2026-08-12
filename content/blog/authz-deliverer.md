---
title: "Authz Deliverer"
slug: "authz-deliverer"
description: "Authz Deliverer: how to avoid the demo-only happy path in production payments systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2026-02-15"
dateModified: "2026-08-12"
tags:
  - "Payments"
  - "Fintech"
keywords: "authz, deliverer, payments, production, engineering"
faq:
  - q: "What is Authz Deliverer?"
    a: "Authz Deliverer is a production approach to avoid the demo-only happy path. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Authz Deliverer?"
    a: "Invest when on-call already feels this pain weekly. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Authz Deliverer?"
    a: "The usual failure is dual-writing without an outbox. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Authz Deliverer** means you avoid the demo-only happy path — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when on-call already feels this pain weekly; that is usually also when shortcuts like dual-writing without an outbox start paging people.

Below is how I implement and operate it in Payments systems using Stripe, ledger: the contracts, the failure modes, and the checks I want before merge.

## The short answer on Authz Deliverer

I have watched teams under-specify Authz Deliverer and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

The anti-pattern is dual-writing without an outbox. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Prefer small diffs with a kill switch. Authz Deliverer changes that require a hero engineer on-call are not done, even if the feature flag is green.

## Constraints before abstractions

If you only remember one thing about Authz Deliverer: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can avoid the demo-only happy path.

In Payments stacks I lean on Stripe, ledger for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when dual-writing without an outbox.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Practically, being able to avoid the demo-only happy path means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```typescript
export async function handle(input: unknown): Promise<Result> {
  const parsed = schema.safeParse(input);
  if (!parsed.success) throw new ValidationError(parsed.error);
  // Authz Deliverer
  return repo.execute(parsed.data);
}
```

## Reference shape using Stripe

Most write-ups on Authz Deliverer stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is dual-writing without an outbox. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

I also keep a short 'never again' list beside the code: dual-writing without an outbox; skipping Authz Deliverer error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; dual-writing without an outbox |
| Durable path | on-call already feels this pain weekly | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Comparison: quick path vs durable path

If you only remember one thing about Authz Deliverer: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can avoid the demo-only happy path.

In Payments stacks I lean on Stripe, ledger for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when dual-writing without an outbox.

Write the acceptance check in product language: when on-call already feels this pain weekly, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

For reviews, I ask: what happens twice? what happens never? what happens partially? Authz Deliverer designs that cannot answer those three questions are not production-ready.

## Edge cases that break demos

I have watched teams under-specify Authz Deliverer and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

The anti-pattern is dual-writing without an outbox. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Prefer small diffs with a kill switch. Authz Deliverer changes that require a hero engineer on-call are not done, even if the feature flag is green.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Shipping without painting into a corner

I have watched teams under-specify Authz Deliverer and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

In Payments stacks I lean on Stripe, ledger for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when dual-writing without an outbox.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

## Practical defaults I use for Authz Deliverer

Most write-ups on Authz Deliverer stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

In Payments stacks I lean on Stripe, ledger for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when dual-writing without an outbox.

Prefer small diffs with a kill switch. Authz Deliverer changes that require a hero engineer on-call are not done, even if the feature flag is green.

A month in, prune unused paths. Authz Deliverer accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Review questions before merging Authz Deliverer work

If you only remember one thing about Authz Deliverer: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can avoid the demo-only happy path.

Make Authz Deliverer error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Deliverer — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Authz Deliverer error rate. Expand only when the metric says you must.

## Field notes after the first month of Authz Deliverer

I have watched teams under-specify Authz Deliverer and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

Make Authz Deliverer error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Deliverer — you only deployed it.

Prefer small diffs with a kill switch. Authz Deliverer changes that require a hero engineer on-call are not done, even if the feature flag is green.

A month in, prune unused paths. Authz Deliverer accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Resources

- https://martinfowler.com/
- https://12factor.net/
