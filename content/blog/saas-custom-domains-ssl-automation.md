---
title: "Custom Domains and Automated Certificates"
slug: "saas-custom-domains-ssl-automation"
description: "Custom Domains and Automated Certificates: how to HTTP-01/DNS-01 at tenant scale in production saas systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2025-08-31"
dateModified: "2026-08-12"
tags:
  - "SaaS"
  - "Backend"
  - "Billing"
keywords: "saas, custom, domains, ssl, automation, production, engineering"
faq:
  - q: "What is Custom Domains and Automated Certificates?"
    a: "Custom Domains and Automated Certificates is a production approach to HTTP-01/DNS-01 at tenant scale. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Custom Domains and Automated Certificates?"
    a: "Invest when white-label portals. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Custom Domains and Automated Certificates?"
    a: "The usual failure is storing private keys in the app DB. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Custom Domains and Automated Certificates** means you HTTP-01/DNS-01 at tenant scale — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when you hit white-label portals; that is usually also when shortcuts like storing private keys in the app DB start paging people.

Below is how I implement and operate it in SaaS systems using Postgres, Stripe, Redis: the contracts, the failure modes, and the checks I want before merge.

## Where Custom Domains and Automated Certificates actually shows up

Most write-ups on Custom Domains and Automated Certificates stop at the demo. This one starts from situations where white-label portals, because that is when the abstraction either pays rent or becomes toil.

Make Custom Domains and Automated Certificates error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Custom Domains and Automated Certificates — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

## A design that makes it routine to HTTP-01/DNS-01 at tenant scale

I have watched teams under-specify Custom Domains and Automated Certificates and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to HTTP-01/DNS-01 at tenant scale.

In SaaS stacks I lean on Postgres, Stripe, Redis for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when storing private keys in the app DB.

Prefer small diffs with a kill switch. Custom Domains and Automated Certificates changes that require a hero engineer on-call are not done, even if the feature flag is green.

Practically, being able to HTTP-01/DNS-01 at tenant scale means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```typescript
export async function handle(input: unknown): Promise<Result> {
  const parsed = schema.safeParse(input);
  if (!parsed.success) throw new ValidationError(parsed.error);
  // Custom Domains and Automated Certificates
  return repo.execute(parsed.data);
}
```

## The failure mode I see in reviews

If you only remember one thing about Custom Domains and Automated Certificates: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can HTTP-01/DNS-01 at tenant scale.

Make Custom Domains and Automated Certificates error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Custom Domains and Automated Certificates — you only deployed it.

Write the acceptance check in product language: when white-label portals, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

I also keep a short 'never again' list beside the code: storing private keys in the app DB; skipping Custom Domains and Automated Certificates error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; storing private keys in the app DB |
| Durable path | white-label portals | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Instrumentation that answers the on-call question

Most write-ups on Custom Domains and Automated Certificates stop at the demo. This one starts from situations where white-label portals, because that is when the abstraction either pays rent or becomes toil.

Make Custom Domains and Automated Certificates error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Custom Domains and Automated Certificates — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

For reviews, I ask: what happens twice? what happens never? what happens partially? Custom Domains and Automated Certificates designs that cannot answer those three questions are not production-ready.

## Rollout checklist

Most write-ups on Custom Domains and Automated Certificates stop at the demo. This one starts from situations where white-label portals, because that is when the abstraction either pays rent or becomes toil.

Make Custom Domains and Automated Certificates error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Custom Domains and Automated Certificates — you only deployed it.

Prefer small diffs with a kill switch. Custom Domains and Automated Certificates changes that require a hero engineer on-call are not done, even if the feature flag is green.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## What I would not do again

If you only remember one thing about Custom Domains and Automated Certificates: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can HTTP-01/DNS-01 at tenant scale.

Make Custom Domains and Automated Certificates error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Custom Domains and Automated Certificates — you only deployed it.

Prefer small diffs with a kill switch. Custom Domains and Automated Certificates changes that require a hero engineer on-call are not done, even if the feature flag is green.

## Practical defaults I use for Custom Domains and Automated Certificates

I have watched teams under-specify Custom Domains and Automated Certificates and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to HTTP-01/DNS-01 at tenant scale.

The anti-pattern is storing private keys in the app DB. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on storing private keys in the app DB. If it is missing, the PR is incomplete.

## Review questions before merging Custom Domains and Automated Certificates work

Most write-ups on Custom Domains and Automated Certificates stop at the demo. This one starts from situations where white-label portals, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is storing private keys in the app DB. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Write the acceptance check in product language: when white-label portals, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Custom Domains and Automated Certificates error rate. Expand only when the metric says you must.

## Field notes after the first month of Custom Domains and Automated Certificates

I have watched teams under-specify Custom Domains and Automated Certificates and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to HTTP-01/DNS-01 at tenant scale.

Make Custom Domains and Automated Certificates error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Custom Domains and Automated Certificates — you only deployed it.

Write the acceptance check in product language: when white-label portals, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Custom Domains and Automated Certificates error rate. Expand only when the metric says you must.

## Resources

- https://martinfowler.com/
- https://12factor.net/
