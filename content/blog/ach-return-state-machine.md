---
title: "Ach Return State Machine"
slug: "ach-return-state-machine"
description: "Ach Return State Machine: how to make retries and timeouts intentional in production platform systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2025-10-07"
dateModified: "2026-08-12"
tags:
  - "Platform"
  - "DX"
keywords: "ach, return, state, machine, platform, production, engineering"
faq:
  - q: "What is Ach Return State Machine?"
    a: "Ach Return State Machine is a production approach to make retries and timeouts intentional. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Ach Return State Machine?"
    a: "Invest when you are replacing a fragile legacy path. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Ach Return State Machine?"
    a: "The usual failure is unlimited retries on non-idempotent calls. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Ach Return State Machine** means you make retries and timeouts intentional — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when you are replacing a fragile legacy path; that is usually also when shortcuts like unlimited retries on non-idempotent calls start paging people.

Below is how I implement and operate it in Platform systems using GitHub Actions, Docker: the contracts, the failure modes, and the checks I want before merge.

## Incident story: when Ach Return State Machine bit us

I have watched teams under-specify Ach Return State Machine and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to make retries and timeouts intentional.

The anti-pattern is unlimited retries on non-idempotent calls. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

## Root cause in one paragraph

I have watched teams under-specify Ach Return State Machine and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to make retries and timeouts intentional.

The anti-pattern is unlimited retries on non-idempotent calls. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Prefer small diffs with a kill switch. Ach Return State Machine changes that require a hero engineer on-call are not done, even if the feature flag is green.

Practically, being able to make retries and timeouts intentional means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```typescript
export async function handle(input: unknown): Promise<Result> {
  const parsed = schema.safeParse(input);
  if (!parsed.success) throw new ValidationError(parsed.error);
  // Ach Return State Machine
  return repo.execute(parsed.data);
}
```

## Fix that survived the next traffic spike

If you only remember one thing about Ach Return State Machine: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can make retries and timeouts intentional.

In Platform stacks I lean on GitHub Actions, Docker for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when unlimited retries on non-idempotent calls.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

I also keep a short 'never again' list beside the code: unlimited retries on non-idempotent calls; skipping Ach Return State Machine error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; unlimited retries on non-idempotent calls |
| Durable path | you are replacing a fragile legacy path | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Tests that would have caught it

Most write-ups on Ach Return State Machine stop at the demo. This one starts from situations where you are replacing a fragile legacy path, because that is when the abstraction either pays rent or becomes toil.

In Platform stacks I lean on GitHub Actions, Docker for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when unlimited retries on non-idempotent calls.

Prefer small diffs with a kill switch. Ach Return State Machine changes that require a hero engineer on-call are not done, even if the feature flag is green.

For reviews, I ask: what happens twice? what happens never? what happens partially? Ach Return State Machine designs that cannot answer those three questions are not production-ready.

## Runbook additions worth keeping

If you only remember one thing about Ach Return State Machine: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can make retries and timeouts intentional.

The anti-pattern is unlimited retries on non-idempotent calls. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Prevention in the platform

If you only remember one thing about Ach Return State Machine: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can make retries and timeouts intentional.

The anti-pattern is unlimited retries on non-idempotent calls. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

## Practical defaults I use for Ach Return State Machine

If you only remember one thing about Ach Return State Machine: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can make retries and timeouts intentional.

Make Ach Return State Machine error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Ach Return State Machine — you only deployed it.

Write the acceptance check in product language: when you are replacing a fragile legacy path, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on unlimited retries on non-idempotent calls. If it is missing, the PR is incomplete.

## Review questions before merging Ach Return State Machine work

Most write-ups on Ach Return State Machine stop at the demo. This one starts from situations where you are replacing a fragile legacy path, because that is when the abstraction either pays rent or becomes toil.

In Platform stacks I lean on GitHub Actions, Docker for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when unlimited retries on non-idempotent calls.

Write the acceptance check in product language: when you are replacing a fragile legacy path, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Ach Return State Machine error rate. Expand only when the metric says you must.

## Field notes after the first month of Ach Return State Machine

Most write-ups on Ach Return State Machine stop at the demo. This one starts from situations where you are replacing a fragile legacy path, because that is when the abstraction either pays rent or becomes toil.

In Platform stacks I lean on GitHub Actions, Docker for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when unlimited retries on non-idempotent calls.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Ach Return State Machine error rate. Expand only when the metric says you must.

## Resources

- https://martinfowler.com/
- https://12factor.net/
