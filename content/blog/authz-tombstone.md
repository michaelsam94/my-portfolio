---
title: "Authz Tombstone"
slug: "authz-tombstone"
description: "Authz Tombstone: how to make retries and timeouts intentional in production python systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2026-05-29"
dateModified: "2026-08-12"
tags:
  - "Python"
  - "Backend"
keywords: "authz, tombstone, python, production, engineering"
faq:
  - q: "What is Authz Tombstone?"
    a: "Authz Tombstone is a production approach to make retries and timeouts intentional. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Authz Tombstone?"
    a: "Invest when you are replacing a fragile legacy path. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Authz Tombstone?"
    a: "The usual failure is unlimited retries on non-idempotent calls. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Authz Tombstone** means you make retries and timeouts intentional — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when you are replacing a fragile legacy path; that is usually also when shortcuts like unlimited retries on non-idempotent calls start paging people.

Below is how I implement and operate it in Python systems using FastAPI, Pydantic: the contracts, the failure modes, and the checks I want before merge.

## A pragmatic path to Authz Tombstone

Most write-ups on Authz Tombstone stop at the demo. This one starts from situations where you are replacing a fragile legacy path, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is unlimited retries on non-idempotent calls. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

## Start with the user-visible symptom

If you only remember one thing about Authz Tombstone: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can make retries and timeouts intentional.

In Python stacks I lean on FastAPI, Pydantic for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when unlimited retries on non-idempotent calls.

Prefer small diffs with a kill switch. Authz Tombstone changes that require a hero engineer on-call are not done, even if the feature flag is green.

Practically, being able to make retries and timeouts intentional means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```python
async def handle(req, client, store):
    if await store.seen(req.idempotency_key):
        return
    # Authz Tombstone
    await client.post('/v1/action', timeout=2.0)
    await store.mark(req.idempotency_key)
```

## Implementing ways to make retries and timeouts intentional

If you only remember one thing about Authz Tombstone: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can make retries and timeouts intentional.

In Python stacks I lean on FastAPI, Pydantic for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when unlimited retries on non-idempotent calls.

Prefer small diffs with a kill switch. Authz Tombstone changes that require a hero engineer on-call are not done, even if the feature flag is green.

I also keep a short 'never again' list beside the code: unlimited retries on non-idempotent calls; skipping Authz Tombstone error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; unlimited retries on non-idempotent calls |
| Durable path | you are replacing a fragile legacy path | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Guardrails and feature flags

I have watched teams under-specify Authz Tombstone and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to make retries and timeouts intentional.

In Python stacks I lean on FastAPI, Pydantic for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when unlimited retries on non-idempotent calls.

Write the acceptance check in product language: when you are replacing a fragile legacy path, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

For reviews, I ask: what happens twice? what happens never? what happens partially? Authz Tombstone designs that cannot answer those three questions are not production-ready.

## Measuring whether it worked

If you only remember one thing about Authz Tombstone: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can make retries and timeouts intentional.

In Python stacks I lean on FastAPI, Pydantic for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when unlimited retries on non-idempotent calls.

Write the acceptance check in product language: when you are replacing a fragile legacy path, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Follow-ups that usually get skipped

Most write-ups on Authz Tombstone stop at the demo. This one starts from situations where you are replacing a fragile legacy path, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is unlimited retries on non-idempotent calls. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Prefer small diffs with a kill switch. Authz Tombstone changes that require a hero engineer on-call are not done, even if the feature flag is green.

## Practical defaults I use for Authz Tombstone

Most write-ups on Authz Tombstone stop at the demo. This one starts from situations where you are replacing a fragile legacy path, because that is when the abstraction either pays rent or becomes toil.

In Python stacks I lean on FastAPI, Pydantic for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when unlimited retries on non-idempotent calls.

Write the acceptance check in product language: when you are replacing a fragile legacy path, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on unlimited retries on non-idempotent calls. If it is missing, the PR is incomplete.

## Review questions before merging Authz Tombstone work

I have watched teams under-specify Authz Tombstone and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to make retries and timeouts intentional.

In Python stacks I lean on FastAPI, Pydantic for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when unlimited retries on non-idempotent calls.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on unlimited retries on non-idempotent calls. If it is missing, the PR is incomplete.

## Field notes after the first month of Authz Tombstone

I have watched teams under-specify Authz Tombstone and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to make retries and timeouts intentional.

Make Authz Tombstone error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Tombstone — you only deployed it.

Prefer small diffs with a kill switch. Authz Tombstone changes that require a hero engineer on-call are not done, even if the feature flag is green.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on unlimited retries on non-idempotent calls. If it is missing, the PR is incomplete.

## Resources

- https://martinfowler.com/
- https://12factor.net/
