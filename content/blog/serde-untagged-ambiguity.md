---
title: "Serde Untagged Ambiguity"
slug: "serde-untagged-ambiguity"
description: "Serde Untagged Ambiguity: how to keep failure modes explicit and tested in production sre systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2025-10-20"
dateModified: "2026-08-12"
tags:
  - "SRE"
  - "Observability"
keywords: "serde, untagged, ambiguity, sre, production, engineering"
faq:
  - q: "What is Serde Untagged Ambiguity?"
    a: "Serde Untagged Ambiguity is a production approach to keep failure modes explicit and tested. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Serde Untagged Ambiguity?"
    a: "Invest when traffic or tenants are about to scale. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Serde Untagged Ambiguity?"
    a: "The usual failure is skipping metrics until after launch. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Serde Untagged Ambiguity** means you keep failure modes explicit and tested — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when traffic or tenants are about to scale; that is usually also when shortcuts like skipping metrics until after launch start paging people.

Below is how I implement and operate it in SRE systems using Prometheus, Grafana: the contracts, the failure modes, and the checks I want before merge.

## A pragmatic path to Serde Untagged Ambiguity

I have watched teams under-specify Serde Untagged Ambiguity and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to keep failure modes explicit and tested.

The anti-pattern is skipping metrics until after launch. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

## Start with the user-visible symptom

I have watched teams under-specify Serde Untagged Ambiguity and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to keep failure modes explicit and tested.

The anti-pattern is skipping metrics until after launch. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Practically, being able to keep failure modes explicit and tested means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```typescript
export async function handle(input: unknown): Promise<Result> {
  const parsed = schema.safeParse(input);
  if (!parsed.success) throw new ValidationError(parsed.error);
  // Serde Untagged Ambiguity
  return repo.execute(parsed.data);
}
```

## Implementing ways to keep failure modes explicit and tested

Most write-ups on Serde Untagged Ambiguity stop at the demo. This one starts from situations where traffic or tenants are about to scale, because that is when the abstraction either pays rent or becomes toil.

In SRE stacks I lean on Prometheus, Grafana for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when skipping metrics until after launch.

Write the acceptance check in product language: when traffic or tenants are about to scale, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

I also keep a short 'never again' list beside the code: skipping metrics until after launch; skipping Serde Untagged Ambiguity error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; skipping metrics until after launch |
| Durable path | traffic or tenants are about to scale | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Guardrails and feature flags

I have watched teams under-specify Serde Untagged Ambiguity and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to keep failure modes explicit and tested.

The anti-pattern is skipping metrics until after launch. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

For reviews, I ask: what happens twice? what happens never? what happens partially? Serde Untagged Ambiguity designs that cannot answer those three questions are not production-ready.

## Measuring whether it worked

Most write-ups on Serde Untagged Ambiguity stop at the demo. This one starts from situations where traffic or tenants are about to scale, because that is when the abstraction either pays rent or becomes toil.

Make Serde Untagged Ambiguity error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Serde Untagged Ambiguity — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Follow-ups that usually get skipped

Most write-ups on Serde Untagged Ambiguity stop at the demo. This one starts from situations where traffic or tenants are about to scale, because that is when the abstraction either pays rent or becomes toil.

Make Serde Untagged Ambiguity error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Serde Untagged Ambiguity — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

## Practical defaults I use for Serde Untagged Ambiguity

Most write-ups on Serde Untagged Ambiguity stop at the demo. This one starts from situations where traffic or tenants are about to scale, because that is when the abstraction either pays rent or becomes toil.

Make Serde Untagged Ambiguity error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Serde Untagged Ambiguity — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Serde Untagged Ambiguity error rate. Expand only when the metric says you must.

## Review questions before merging Serde Untagged Ambiguity work

Most write-ups on Serde Untagged Ambiguity stop at the demo. This one starts from situations where traffic or tenants are about to scale, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is skipping metrics until after launch. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

A month in, prune unused paths. Serde Untagged Ambiguity accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Field notes after the first month of Serde Untagged Ambiguity

I have watched teams under-specify Serde Untagged Ambiguity and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to keep failure modes explicit and tested.

In SRE stacks I lean on Prometheus, Grafana for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when skipping metrics until after launch.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

A month in, prune unused paths. Serde Untagged Ambiguity accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Resources

- https://martinfowler.com/
- https://12factor.net/
