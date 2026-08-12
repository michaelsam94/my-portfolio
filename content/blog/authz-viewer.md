---
title: "Authz Viewer"
slug: "authz-viewer"
description: "Authz Viewer: how to ship it with clear ownership and rollback in production saas systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2026-06-13"
dateModified: "2026-08-12"
tags:
  - "SaaS"
  - "Backend"
keywords: "authz, viewer, saas, production, engineering"
faq:
  - q: "What is Authz Viewer?"
    a: "Authz Viewer is a production approach to ship it with clear ownership and rollback. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Authz Viewer?"
    a: "Invest when the feature is on a critical user journey. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Authz Viewer?"
    a: "The usual failure is copying a tutorial without matching constraints. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Authz Viewer** means you ship it with clear ownership and rollback — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when the feature is on a critical user journey; that is usually also when shortcuts like copying a tutorial without matching constraints start paging people.

Below is how I implement and operate it in SaaS systems using Postgres, Stripe: the contracts, the failure modes, and the checks I want before merge.

## The short answer on Authz Viewer

If you only remember one thing about Authz Viewer: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can ship it with clear ownership and rollback.

The anti-pattern is copying a tutorial without matching constraints. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

## Constraints before abstractions

Most write-ups on Authz Viewer stop at the demo. This one starts from situations where the feature is on a critical user journey, because that is when the abstraction either pays rent or becomes toil.

Make Authz Viewer error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Viewer — you only deployed it.

Write the acceptance check in product language: when the feature is on a critical user journey, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Practically, being able to ship it with clear ownership and rollback means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```typescript
export async function handle(input: unknown): Promise<Result> {
  const parsed = schema.safeParse(input);
  if (!parsed.success) throw new ValidationError(parsed.error);
  // Authz Viewer
  return repo.execute(parsed.data);
}
```

## Reference shape using Postgres

I have watched teams under-specify Authz Viewer and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to ship it with clear ownership and rollback.

The anti-pattern is copying a tutorial without matching constraints. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

I also keep a short 'never again' list beside the code: copying a tutorial without matching constraints; skipping Authz Viewer error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; copying a tutorial without matching constraints |
| Durable path | the feature is on a critical user journey | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Comparison: quick path vs durable path

I have watched teams under-specify Authz Viewer and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to ship it with clear ownership and rollback.

In SaaS stacks I lean on Postgres, Stripe for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when copying a tutorial without matching constraints.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

For reviews, I ask: what happens twice? what happens never? what happens partially? Authz Viewer designs that cannot answer those three questions are not production-ready.

## Edge cases that break demos

Most write-ups on Authz Viewer stop at the demo. This one starts from situations where the feature is on a critical user journey, because that is when the abstraction either pays rent or becomes toil.

In SaaS stacks I lean on Postgres, Stripe for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when copying a tutorial without matching constraints.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Shipping without painting into a corner

I have watched teams under-specify Authz Viewer and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to ship it with clear ownership and rollback.

In SaaS stacks I lean on Postgres, Stripe for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when copying a tutorial without matching constraints.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

## Practical defaults I use for Authz Viewer

If you only remember one thing about Authz Viewer: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can ship it with clear ownership and rollback.

Make Authz Viewer error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Viewer — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

A month in, prune unused paths. Authz Viewer accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Review questions before merging Authz Viewer work

If you only remember one thing about Authz Viewer: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can ship it with clear ownership and rollback.

In SaaS stacks I lean on Postgres, Stripe for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when copying a tutorial without matching constraints.

Prefer small diffs with a kill switch. Authz Viewer changes that require a hero engineer on-call are not done, even if the feature flag is green.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on copying a tutorial without matching constraints. If it is missing, the PR is incomplete.

## Field notes after the first month of Authz Viewer

I have watched teams under-specify Authz Viewer and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to ship it with clear ownership and rollback.

The anti-pattern is copying a tutorial without matching constraints. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Prefer small diffs with a kill switch. Authz Viewer changes that require a hero engineer on-call are not done, even if the feature flag is green.

A month in, prune unused paths. Authz Viewer accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Resources

- https://martinfowler.com/
- https://12factor.net/
