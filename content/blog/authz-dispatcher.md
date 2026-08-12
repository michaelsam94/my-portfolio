---
title: "Authz Dispatcher"
slug: "authz-dispatcher"
description: "Authz Dispatcher: how to avoid the demo-only happy path in production comms systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2026-02-17"
dateModified: "2026-08-12"
tags:
  - "Integrations"
  - "Backend"
keywords: "authz, dispatcher, comms, production, engineering"
faq:
  - q: "What is Authz Dispatcher?"
    a: "Authz Dispatcher is a production approach to avoid the demo-only happy path. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Authz Dispatcher?"
    a: "Invest when on-call already feels this pain weekly. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Authz Dispatcher?"
    a: "The usual failure is dual-writing without an outbox. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Authz Dispatcher** means you avoid the demo-only happy path — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when on-call already feels this pain weekly; that is usually also when shortcuts like dual-writing without an outbox start paging people.

Below is how I implement and operate it in Comms systems using SES, Twilio: the contracts, the failure modes, and the checks I want before merge.

## How I explain Authz Dispatcher to a skeptical teammate

I have watched teams under-specify Authz Dispatcher and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

In Comms stacks I lean on SES, Twilio for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when dual-writing without an outbox.

Prefer small diffs with a kill switch. Authz Dispatcher changes that require a hero engineer on-call are not done, even if the feature flag is green.

## Doing work to avoid the demo-only happy path

Most write-ups on Authz Dispatcher stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

In Comms stacks I lean on SES, Twilio for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when dual-writing without an outbox.

Prefer small diffs with a kill switch. Authz Dispatcher changes that require a hero engineer on-call are not done, even if the feature flag is green.

Practically, being able to avoid the demo-only happy path means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```typescript
export async function handle(input: unknown): Promise<Result> {
  const parsed = schema.safeParse(input);
  if (!parsed.success) throw new ValidationError(parsed.error);
  // Authz Dispatcher
  return repo.execute(parsed.data);
}
```

## Code boundaries that keep refactors cheap

Most write-ups on Authz Dispatcher stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

In Comms stacks I lean on SES, Twilio for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when dual-writing without an outbox.

Prefer small diffs with a kill switch. Authz Dispatcher changes that require a hero engineer on-call are not done, even if the feature flag is green.

I also keep a short 'never again' list beside the code: dual-writing without an outbox; skipping Authz Dispatcher error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; dual-writing without an outbox |
| Durable path | on-call already feels this pain weekly | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Table stakes vs nice-to-haves

If you only remember one thing about Authz Dispatcher: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can avoid the demo-only happy path.

Make Authz Dispatcher error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Dispatcher — you only deployed it.

Prefer small diffs with a kill switch. Authz Dispatcher changes that require a hero engineer on-call are not done, even if the feature flag is green.

For reviews, I ask: what happens twice? what happens never? what happens partially? Authz Dispatcher designs that cannot answer those three questions are not production-ready.

## Common regressions after launch

I have watched teams under-specify Authz Dispatcher and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

Make Authz Dispatcher error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Dispatcher — you only deployed it.

Write the acceptance check in product language: when on-call already feels this pain weekly, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Maintenance burden over 12 months

I have watched teams under-specify Authz Dispatcher and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

The anti-pattern is dual-writing without an outbox. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Prefer small diffs with a kill switch. Authz Dispatcher changes that require a hero engineer on-call are not done, even if the feature flag is green.

## Practical defaults I use for Authz Dispatcher

Most write-ups on Authz Dispatcher stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

In Comms stacks I lean on SES, Twilio for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when dual-writing without an outbox.

Write the acceptance check in product language: when on-call already feels this pain weekly, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Authz Dispatcher error rate. Expand only when the metric says you must.

## Review questions before merging Authz Dispatcher work

Most write-ups on Authz Dispatcher stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

Make Authz Dispatcher error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Dispatcher — you only deployed it.

Prefer small diffs with a kill switch. Authz Dispatcher changes that require a hero engineer on-call are not done, even if the feature flag is green.

A month in, prune unused paths. Authz Dispatcher accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Field notes after the first month of Authz Dispatcher

Most write-ups on Authz Dispatcher stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is dual-writing without an outbox. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Prefer small diffs with a kill switch. Authz Dispatcher changes that require a hero engineer on-call are not done, even if the feature flag is green.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Authz Dispatcher error rate. Expand only when the metric says you must.

## Resources

- https://martinfowler.com/
- https://12factor.net/
