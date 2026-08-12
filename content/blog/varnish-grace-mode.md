---
title: "Varnish Grace Mode"
slug: "varnish-grace-mode"
description: "Varnish Grace Mode: how to make retries and timeouts intentional in production privacy systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2026-01-17"
dateModified: "2026-08-12"
tags:
  - "Privacy"
  - "Compliance"
keywords: "varnish, grace, mode, privacy, production, engineering"
faq:
  - q: "What is Varnish Grace Mode?"
    a: "Varnish Grace Mode is a production approach to make retries and timeouts intentional. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Varnish Grace Mode?"
    a: "Invest when you are replacing a fragile legacy path. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Varnish Grace Mode?"
    a: "The usual failure is unlimited retries on non-idempotent calls. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Varnish Grace Mode** means you make retries and timeouts intentional — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when you are replacing a fragile legacy path; that is usually also when shortcuts like unlimited retries on non-idempotent calls start paging people.

Below is how I implement and operate it in Privacy systems using GDPR, KMS: the contracts, the failure modes, and the checks I want before merge.

## Where Varnish Grace Mode actually shows up

If you only remember one thing about Varnish Grace Mode: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can make retries and timeouts intentional.

In Privacy stacks I lean on GDPR, KMS for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when unlimited retries on non-idempotent calls.

Prefer small diffs with a kill switch. Varnish Grace Mode changes that require a hero engineer on-call are not done, even if the feature flag is green.

## A design that makes it routine to make retries and timeouts intentional

If you only remember one thing about Varnish Grace Mode: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can make retries and timeouts intentional.

Make Varnish Grace Mode error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Varnish Grace Mode — you only deployed it.

Write the acceptance check in product language: when you are replacing a fragile legacy path, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Practically, being able to make retries and timeouts intentional means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```typescript
export async function handle(input: unknown): Promise<Result> {
  const parsed = schema.safeParse(input);
  if (!parsed.success) throw new ValidationError(parsed.error);
  // Varnish Grace Mode
  return repo.execute(parsed.data);
}
```

## The failure mode I see in reviews

If you only remember one thing about Varnish Grace Mode: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can make retries and timeouts intentional.

Make Varnish Grace Mode error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Varnish Grace Mode — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

I also keep a short 'never again' list beside the code: unlimited retries on non-idempotent calls; skipping Varnish Grace Mode error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; unlimited retries on non-idempotent calls |
| Durable path | you are replacing a fragile legacy path | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Instrumentation that answers the on-call question

If you only remember one thing about Varnish Grace Mode: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can make retries and timeouts intentional.

In Privacy stacks I lean on GDPR, KMS for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when unlimited retries on non-idempotent calls.

Write the acceptance check in product language: when you are replacing a fragile legacy path, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

For reviews, I ask: what happens twice? what happens never? what happens partially? Varnish Grace Mode designs that cannot answer those three questions are not production-ready.

## Rollout checklist

Most write-ups on Varnish Grace Mode stop at the demo. This one starts from situations where you are replacing a fragile legacy path, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is unlimited retries on non-idempotent calls. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Prefer small diffs with a kill switch. Varnish Grace Mode changes that require a hero engineer on-call are not done, even if the feature flag is green.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## What I would not do again

If you only remember one thing about Varnish Grace Mode: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can make retries and timeouts intentional.

In Privacy stacks I lean on GDPR, KMS for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when unlimited retries on non-idempotent calls.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

## Practical defaults I use for Varnish Grace Mode

If you only remember one thing about Varnish Grace Mode: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can make retries and timeouts intentional.

Make Varnish Grace Mode error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Varnish Grace Mode — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

A month in, prune unused paths. Varnish Grace Mode accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Review questions before merging Varnish Grace Mode work

If you only remember one thing about Varnish Grace Mode: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can make retries and timeouts intentional.

The anti-pattern is unlimited retries on non-idempotent calls. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Write the acceptance check in product language: when you are replacing a fragile legacy path, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Varnish Grace Mode error rate. Expand only when the metric says you must.

## Field notes after the first month of Varnish Grace Mode

If you only remember one thing about Varnish Grace Mode: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can make retries and timeouts intentional.

The anti-pattern is unlimited retries on non-idempotent calls. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Prefer small diffs with a kill switch. Varnish Grace Mode changes that require a hero engineer on-call are not done, even if the feature flag is green.

A month in, prune unused paths. Varnish Grace Mode accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Resources

- https://martinfowler.com/
- https://12factor.net/
