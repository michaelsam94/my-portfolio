---
title: "Authz Listener"
slug: "authz-listener"
description: "Authz Listener: how to make retries and timeouts intentional in production typescript systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2026-03-15"
dateModified: "2026-08-12"
tags:
  - "TypeScript"
  - "Web"
keywords: "authz, listener, typescript, production, engineering"
faq:
  - q: "What is Authz Listener?"
    a: "Authz Listener is a production approach to make retries and timeouts intentional. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Authz Listener?"
    a: "Invest when you are replacing a fragile legacy path. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Authz Listener?"
    a: "The usual failure is unlimited retries on non-idempotent calls. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Authz Listener** means you make retries and timeouts intentional — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when you are replacing a fragile legacy path; that is usually also when shortcuts like unlimited retries on non-idempotent calls start paging people.

Below is how I implement and operate it in TypeScript systems using TypeScript, Zod: the contracts, the failure modes, and the checks I want before merge.

## Incident story: when Authz Listener bit us

I have watched teams under-specify Authz Listener and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to make retries and timeouts intentional.

In TypeScript stacks I lean on TypeScript, Zod for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when unlimited retries on non-idempotent calls.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

## Root cause in one paragraph

If you only remember one thing about Authz Listener: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can make retries and timeouts intentional.

In TypeScript stacks I lean on TypeScript, Zod for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when unlimited retries on non-idempotent calls.

Write the acceptance check in product language: when you are replacing a fragile legacy path, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Practically, being able to make retries and timeouts intentional means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```typescript
export async function handle(input: unknown): Promise<Result> {
  const parsed = schema.safeParse(input);
  if (!parsed.success) throw new ValidationError(parsed.error);
  // Authz Listener
  return repo.execute(parsed.data);
}
```

## Fix that survived the next traffic spike

I have watched teams under-specify Authz Listener and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to make retries and timeouts intentional.

Make Authz Listener error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Listener — you only deployed it.

Write the acceptance check in product language: when you are replacing a fragile legacy path, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

I also keep a short 'never again' list beside the code: unlimited retries on non-idempotent calls; skipping Authz Listener error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; unlimited retries on non-idempotent calls |
| Durable path | you are replacing a fragile legacy path | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Tests that would have caught it

I have watched teams under-specify Authz Listener and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to make retries and timeouts intentional.

The anti-pattern is unlimited retries on non-idempotent calls. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

For reviews, I ask: what happens twice? what happens never? what happens partially? Authz Listener designs that cannot answer those three questions are not production-ready.

## Runbook additions worth keeping

Most write-ups on Authz Listener stop at the demo. This one starts from situations where you are replacing a fragile legacy path, because that is when the abstraction either pays rent or becomes toil.

Make Authz Listener error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Listener — you only deployed it.

Write the acceptance check in product language: when you are replacing a fragile legacy path, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Prevention in the platform

If you only remember one thing about Authz Listener: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can make retries and timeouts intentional.

Make Authz Listener error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Listener — you only deployed it.

Prefer small diffs with a kill switch. Authz Listener changes that require a hero engineer on-call are not done, even if the feature flag is green.

## Practical defaults I use for Authz Listener

If you only remember one thing about Authz Listener: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can make retries and timeouts intentional.

Make Authz Listener error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Listener — you only deployed it.

Prefer small diffs with a kill switch. Authz Listener changes that require a hero engineer on-call are not done, even if the feature flag is green.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Authz Listener error rate. Expand only when the metric says you must.

## Review questions before merging Authz Listener work

I have watched teams under-specify Authz Listener and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to make retries and timeouts intentional.

In TypeScript stacks I lean on TypeScript, Zod for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when unlimited retries on non-idempotent calls.

Write the acceptance check in product language: when you are replacing a fragile legacy path, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on unlimited retries on non-idempotent calls. If it is missing, the PR is incomplete.

## Field notes after the first month of Authz Listener

Most write-ups on Authz Listener stop at the demo. This one starts from situations where you are replacing a fragile legacy path, because that is when the abstraction either pays rent or becomes toil.

In TypeScript stacks I lean on TypeScript, Zod for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when unlimited retries on non-idempotent calls.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

A month in, prune unused paths. Authz Listener accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Resources

- https://martinfowler.com/
- https://12factor.net/
