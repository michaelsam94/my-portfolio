---
title: "Authz Rewriter"
slug: "authz-rewriter"
description: "Authz Rewriter: how to avoid the demo-only happy path in production saas systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2026-04-25"
dateModified: "2026-08-12"
tags:
  - "SaaS"
  - "Backend"
keywords: "authz, rewriter, saas, production, engineering"
faq:
  - q: "What is Authz Rewriter?"
    a: "Authz Rewriter is a production approach to avoid the demo-only happy path. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Authz Rewriter?"
    a: "Invest when on-call already feels this pain weekly. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Authz Rewriter?"
    a: "The usual failure is dual-writing without an outbox. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Authz Rewriter** means you avoid the demo-only happy path — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when on-call already feels this pain weekly; that is usually also when shortcuts like dual-writing without an outbox start paging people.

Below is how I implement and operate it in SaaS systems using Postgres, Stripe: the contracts, the failure modes, and the checks I want before merge.

## How I explain Authz Rewriter to a skeptical teammate

If you only remember one thing about Authz Rewriter: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can avoid the demo-only happy path.

Make Authz Rewriter error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Rewriter — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

## Doing work to avoid the demo-only happy path

If you only remember one thing about Authz Rewriter: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can avoid the demo-only happy path.

In SaaS stacks I lean on Postgres, Stripe for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when dual-writing without an outbox.

Write the acceptance check in product language: when on-call already feels this pain weekly, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Practically, being able to avoid the demo-only happy path means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```typescript
export async function handle(input: unknown): Promise<Result> {
  const parsed = schema.safeParse(input);
  if (!parsed.success) throw new ValidationError(parsed.error);
  // Authz Rewriter
  return repo.execute(parsed.data);
}
```

## Code boundaries that keep refactors cheap

If you only remember one thing about Authz Rewriter: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can avoid the demo-only happy path.

Make Authz Rewriter error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Rewriter — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

I also keep a short 'never again' list beside the code: dual-writing without an outbox; skipping Authz Rewriter error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; dual-writing without an outbox |
| Durable path | on-call already feels this pain weekly | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Table stakes vs nice-to-haves

Most write-ups on Authz Rewriter stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

Make Authz Rewriter error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Rewriter — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

For reviews, I ask: what happens twice? what happens never? what happens partially? Authz Rewriter designs that cannot answer those three questions are not production-ready.

## Common regressions after launch

Most write-ups on Authz Rewriter stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

In SaaS stacks I lean on Postgres, Stripe for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when dual-writing without an outbox.

Write the acceptance check in product language: when on-call already feels this pain weekly, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Maintenance burden over 12 months

I have watched teams under-specify Authz Rewriter and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

Make Authz Rewriter error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Rewriter — you only deployed it.

Prefer small diffs with a kill switch. Authz Rewriter changes that require a hero engineer on-call are not done, even if the feature flag is green.

## Practical defaults I use for Authz Rewriter

If you only remember one thing about Authz Rewriter: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can avoid the demo-only happy path.

In SaaS stacks I lean on Postgres, Stripe for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when dual-writing without an outbox.

Write the acceptance check in product language: when on-call already feels this pain weekly, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on dual-writing without an outbox. If it is missing, the PR is incomplete.

## Review questions before merging Authz Rewriter work

Most write-ups on Authz Rewriter stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is dual-writing without an outbox. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Write the acceptance check in product language: when on-call already feels this pain weekly, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Authz Rewriter error rate. Expand only when the metric says you must.

## Field notes after the first month of Authz Rewriter

I have watched teams under-specify Authz Rewriter and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

The anti-pattern is dual-writing without an outbox. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Write the acceptance check in product language: when on-call already feels this pain weekly, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Authz Rewriter error rate. Expand only when the metric says you must.

## Resources

- https://martinfowler.com/
- https://12factor.net/
