---
title: "Authz Strainer"
slug: "authz-strainer"
description: "Authz Strainer: how to avoid the demo-only happy path in production go systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2026-05-15"
dateModified: "2026-08-12"
tags:
  - "Go"
  - "Backend"
keywords: "authz, strainer, go, production, engineering"
faq:
  - q: "What is Authz Strainer?"
    a: "Authz Strainer is a production approach to avoid the demo-only happy path. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Authz Strainer?"
    a: "Invest when on-call already feels this pain weekly. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Authz Strainer?"
    a: "The usual failure is dual-writing without an outbox. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Authz Strainer** means you avoid the demo-only happy path — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when on-call already feels this pain weekly; that is usually also when shortcuts like dual-writing without an outbox start paging people.

Below is how I implement and operate it in Go systems using Go, pgx: the contracts, the failure modes, and the checks I want before merge.

## Decision guide for Authz Strainer

Most write-ups on Authz Strainer stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

Make Authz Strainer error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Strainer — you only deployed it.

Write the acceptance check in product language: when on-call already feels this pain weekly, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

## When this is the wrong tool

Most write-ups on Authz Strainer stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is dual-writing without an outbox. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Practically, being able to avoid the demo-only happy path means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```go
func (s *Service) Handle(ctx context.Context, req Request) error {
  ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
  defer cancel()
  // Authz Strainer
  return s.repo.Save(ctx, req)
}
```

## Minimal viable production setup

I have watched teams under-specify Authz Strainer and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

The anti-pattern is dual-writing without an outbox. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

I also keep a short 'never again' list beside the code: dual-writing without an outbox; skipping Authz Strainer error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; dual-writing without an outbox |
| Durable path | on-call already feels this pain weekly | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Cost and complexity tradeoffs

I have watched teams under-specify Authz Strainer and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

Make Authz Strainer error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Strainer — you only deployed it.

Prefer small diffs with a kill switch. Authz Strainer changes that require a hero engineer on-call are not done, even if the feature flag is green.

For reviews, I ask: what happens twice? what happens never? what happens partially? Authz Strainer designs that cannot answer those three questions are not production-ready.

## Migration sequence

I have watched teams under-specify Authz Strainer and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

The anti-pattern is dual-writing without an outbox. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Acceptance checks before you call it done

Most write-ups on Authz Strainer stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

Make Authz Strainer error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Strainer — you only deployed it.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

## Practical defaults I use for Authz Strainer

If you only remember one thing about Authz Strainer: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can avoid the demo-only happy path.

Make Authz Strainer error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Strainer — you only deployed it.

Prefer small diffs with a kill switch. Authz Strainer changes that require a hero engineer on-call are not done, even if the feature flag is green.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Authz Strainer error rate. Expand only when the metric says you must.

## Review questions before merging Authz Strainer work

Most write-ups on Authz Strainer stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

Make Authz Strainer error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Strainer — you only deployed it.

Prefer small diffs with a kill switch. Authz Strainer changes that require a hero engineer on-call are not done, even if the feature flag is green.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Authz Strainer error rate. Expand only when the metric says you must.

## Field notes after the first month of Authz Strainer

If you only remember one thing about Authz Strainer: optimize for the failure you will actually hit at 2am, not the happy path in a design doc. That usually means designing so you can avoid the demo-only happy path.

Make Authz Strainer error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Authz Strainer — you only deployed it.

Write the acceptance check in product language: when on-call already feels this pain weekly, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on dual-writing without an outbox. If it is missing, the PR is incomplete.

## Resources

- https://martinfowler.com/
- https://12factor.net/
