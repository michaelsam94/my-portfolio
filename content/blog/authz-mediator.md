---
title: "Authz Mediator"
slug: "authz-mediator"
description: "Authz Mediator: how to measure the user-visible signal first in production platform systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2026-03-19"
dateModified: "2026-08-12"
tags:
  - "Platform"
  - "DX"
keywords: "authz, mediator, platform, production, engineering"
faq:
  - q: "What is Authz Mediator?"
    a: "Authz Mediator is a production approach to measure the user-visible signal first. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Authz Mediator?"
    a: "Invest when auditors or enterprise buyers ask how you know it works. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Authz Mediator?"
    a: "The usual failure is treating edge cases as follow-ups. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Authz Mediator** means you measure the user-visible signal first — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when auditors or enterprise buyers ask how you know it works; that is usually also when shortcuts like treating edge cases as follow-ups start paging people.

Below is how I implement and operate it in Platform systems using GitHub Actions, Docker: the contracts, the failure modes, and the checks I want before merge.

## A pragmatic path to Authz Mediator

Most write-ups on Authz Mediator stop at the demo. This one starts from situations where auditors or enterprise buyers ask how you know it works, because that is when the abstraction either pays rent or becomes toil.

In Platform stacks I lean on GitHub Actions, Docker for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when treating edge cases as follow-ups.

Write the acceptance check in product language: when auditors or enterprise buyers ask how you know it works, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

## Start with the user-visible symptom

If you only remember one thing about Authz Mediator: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can measure the user-visible signal first.

Make Authz Mediator error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Mediator — you only deployed it.

Write the acceptance check in product language: when auditors or enterprise buyers ask how you know it works, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Practically, being able to measure the user-visible signal first means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```typescript
export async function handle(input: unknown): Promise<Result> {
  const parsed = schema.safeParse(input);
  if (!parsed.success) throw new ValidationError(parsed.error);
  // Authz Mediator
  return repo.execute(parsed.data);
}
```

## Implementing ways to measure the user-visible signal first

I have watched teams under-specify Authz Mediator and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to measure the user-visible signal first.

In Platform stacks I lean on GitHub Actions, Docker for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when treating edge cases as follow-ups.

Prefer small diffs with a kill switch. Authz Mediator changes that require a hero engineer on-call are not done, even if the feature flag is green.

I also keep a short 'never again' list beside the code: treating edge cases as follow-ups; skipping Authz Mediator error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; treating edge cases as follow-ups |
| Durable path | auditors or enterprise buyers ask how you know it works | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Guardrails and feature flags

I have watched teams under-specify Authz Mediator and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to measure the user-visible signal first.

Make Authz Mediator error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Mediator — you only deployed it.

Prefer small diffs with a kill switch. Authz Mediator changes that require a hero engineer on-call are not done, even if the feature flag is green.

For reviews, I ask: what happens twice? what happens never? what happens partially? Authz Mediator designs that cannot answer those three questions are not production-ready.

## Measuring whether it worked

I have watched teams under-specify Authz Mediator and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to measure the user-visible signal first.

Make Authz Mediator error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Mediator — you only deployed it.

Write the acceptance check in product language: when auditors or enterprise buyers ask how you know it works, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Follow-ups that usually get skipped

Most write-ups on Authz Mediator stop at the demo. This one starts from situations where auditors or enterprise buyers ask how you know it works, because that is when the abstraction either pays rent or becomes toil.

In Platform stacks I lean on GitHub Actions, Docker for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when treating edge cases as follow-ups.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

## Practical defaults I use for Authz Mediator

Most write-ups on Authz Mediator stop at the demo. This one starts from situations where auditors or enterprise buyers ask how you know it works, because that is when the abstraction either pays rent or becomes toil.

Make Authz Mediator error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Mediator — you only deployed it.

Write the acceptance check in product language: when auditors or enterprise buyers ask how you know it works, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Authz Mediator error rate. Expand only when the metric says you must.

## Review questions before merging Authz Mediator work

Most write-ups on Authz Mediator stop at the demo. This one starts from situations where auditors or enterprise buyers ask how you know it works, because that is when the abstraction either pays rent or becomes toil.

Make Authz Mediator error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Mediator — you only deployed it.

Write the acceptance check in product language: when auditors or enterprise buyers ask how you know it works, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

A month in, prune unused paths. Authz Mediator accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Field notes after the first month of Authz Mediator

If you only remember one thing about Authz Mediator: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can measure the user-visible signal first.

Make Authz Mediator error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Mediator — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Authz Mediator error rate. Expand only when the metric says you must.

## Resources

- https://martinfowler.com/
- https://12factor.net/
