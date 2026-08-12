---
title: "Authz Switcher"
slug: "authz-switcher"
description: "Authz Switcher: how to keep failure modes explicit and tested in production sre systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2026-05-20"
dateModified: "2026-08-12"
tags:
  - "SRE"
  - "Observability"
keywords: "authz, switcher, sre, production, engineering"
faq:
  - q: "What is Authz Switcher?"
    a: "Authz Switcher is a production approach to keep failure modes explicit and tested. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Authz Switcher?"
    a: "Invest when traffic or tenants are about to scale. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Authz Switcher?"
    a: "The usual failure is skipping metrics until after launch. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Authz Switcher** means you keep failure modes explicit and tested — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when traffic or tenants are about to scale; that is usually also when shortcuts like skipping metrics until after launch start paging people.

Below is how I implement and operate it in SRE systems using Prometheus, Grafana: the contracts, the failure modes, and the checks I want before merge.

## Authz Switcher: production checklist

I have watched teams under-specify Authz Switcher and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to keep failure modes explicit and tested.

In SRE stacks I lean on Prometheus, Grafana for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when skipping metrics until after launch.

Write the acceptance check in product language: when traffic or tenants are about to scale, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

## Inputs, outputs, and invariants

I have watched teams under-specify Authz Switcher and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to keep failure modes explicit and tested.

The anti-pattern is skipping metrics until after launch. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Write the acceptance check in product language: when traffic or tenants are about to scale, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Practically, being able to keep failure modes explicit and tested means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```typescript
export async function handle(input: unknown): Promise<Result> {
  const parsed = schema.safeParse(input);
  if (!parsed.success) throw new ValidationError(parsed.error);
  // Authz Switcher
  return repo.execute(parsed.data);
}
```

## Concurrency and retry behavior

I have watched teams under-specify Authz Switcher and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to keep failure modes explicit and tested.

Make Authz Switcher error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Switcher — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

I also keep a short 'never again' list beside the code: skipping metrics until after launch; skipping Authz Switcher error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; skipping metrics until after launch |
| Durable path | traffic or tenants are about to scale | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Human workflows (support, ops, audit)

I have watched teams under-specify Authz Switcher and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to keep failure modes explicit and tested.

In SRE stacks I lean on Prometheus, Grafana for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when skipping metrics until after launch.

Write the acceptance check in product language: when traffic or tenants are about to scale, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

For reviews, I ask: what happens twice? what happens never? what happens partially? Authz Switcher designs that cannot answer those three questions are not production-ready.

## Load and capacity notes

Most write-ups on Authz Switcher stop at the demo. This one starts from situations where traffic or tenants are about to scale, because that is when the abstraction either pays rent or becomes toil.

In SRE stacks I lean on Prometheus, Grafana for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when skipping metrics until after launch.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Definition of done

Most write-ups on Authz Switcher stop at the demo. This one starts from situations where traffic or tenants are about to scale, because that is when the abstraction either pays rent or becomes toil.

In SRE stacks I lean on Prometheus, Grafana for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when skipping metrics until after launch.

Write the acceptance check in product language: when traffic or tenants are about to scale, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

## Practical defaults I use for Authz Switcher

If you only remember one thing about Authz Switcher: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can keep failure modes explicit and tested.

Make Authz Switcher error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Switcher — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on skipping metrics until after launch. If it is missing, the PR is incomplete.

## Review questions before merging Authz Switcher work

I have watched teams under-specify Authz Switcher and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to keep failure modes explicit and tested.

In SRE stacks I lean on Prometheus, Grafana for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when skipping metrics until after launch.

Write the acceptance check in product language: when traffic or tenants are about to scale, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Authz Switcher error rate. Expand only when the metric says you must.

## Field notes after the first month of Authz Switcher

I have watched teams under-specify Authz Switcher and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to keep failure modes explicit and tested.

Make Authz Switcher error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Switcher — you only deployed it.

Write the acceptance check in product language: when traffic or tenants are about to scale, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Authz Switcher error rate. Expand only when the metric says you must.

## Resources

- https://martinfowler.com/
- https://12factor.net/
