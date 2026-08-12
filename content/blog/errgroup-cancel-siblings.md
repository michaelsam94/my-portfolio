---
title: "Errgroup Cancel Siblings"
slug: "errgroup-cancel-siblings"
description: "Errgroup Cancel Siblings: how to avoid the demo-only happy path in production go systems — design tradeoffs, failure modes, instrumentation, and rollout checks."
datePublished: "2025-10-16"
dateModified: "2026-08-12"
tags:
  - "Go"
  - "Backend"
keywords: "errgroup, cancel, siblings, go, production, engineering"
faq:
  - q: "What is Errgroup Cancel Siblings?"
    a: "Errgroup Cancel Siblings is a production approach to avoid the demo-only happy path. It focuses on concrete failure modes, contracts, and metrics rather than a slide-deck definition."
  - q: "When should teams invest in Errgroup Cancel Siblings?"
    a: "Invest when on-call already feels this pain weekly. If error rate and latency already hurts users or cost, prioritize it; defer only if the path is unused."
  - q: "What is the most common mistake with Errgroup Cancel Siblings?"
    a: "The usual failure is dual-writing without an outbox. Teams also ship without measuring outcomes, then discover the design only during an incident."
---
**Errgroup Cancel Siblings** means you avoid the demo-only happy path — with an owner, a measurable signal, and a rollback you can execute tired. I reach for this when on-call already feels this pain weekly; that is usually also when shortcuts like dual-writing without an outbox start paging people.

Below is how I implement and operate it in Go systems using Go, pgx: the contracts, the failure modes, and the checks I want before merge.

## How I explain Errgroup Cancel Siblings to a skeptical teammate

I have watched teams under-specify Errgroup Cancel Siblings and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

Make Errgroup Cancel Siblings error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Errgroup Cancel Siblings — you only deployed it.

Prefer small diffs with a kill switch. Errgroup Cancel Siblings changes that require a hero engineer on-call are not done, even if the feature flag is green.

## Doing work to avoid the demo-only happy path

I have watched teams under-specify Errgroup Cancel Siblings and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

The anti-pattern is dual-writing without an outbox. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Prefer small diffs with a kill switch. Errgroup Cancel Siblings changes that require a hero engineer on-call are not done, even if the feature flag is green.

Practically, being able to avoid the demo-only happy path means you choose boundaries on purpose: which process owns the source of truth, which retries are safe, and which errors are user-visible versus operator-only.

```go
func (s *Service) Handle(ctx context.Context, req Request) error {
  ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
  defer cancel()
  // Errgroup Cancel Siblings
  return s.repo.Save(ctx, req)
}
```

## Code boundaries that keep refactors cheap

Most write-ups on Errgroup Cancel Siblings stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is dual-writing without an outbox. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

I also keep a short 'never again' list beside the code: dual-writing without an outbox; skipping Errgroup Cancel Siblings error rate; and shipping without a rollback that a tired on-call can execute.

| Approach | When it fits | Main risk |
| --- | --- | --- |
| Minimal path | Early product, low blast radius | Hidden coupling; dual-writing without an outbox |
| Durable path | on-call already feels this pain weekly | More moving parts; needs ownership |
| Hybrid / staged | Migrating brownfield systems | Dual-running complexity |

## Table stakes vs nice-to-haves

I have watched teams under-specify Errgroup Cancel Siblings and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

Make Errgroup Cancel Siblings error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Errgroup Cancel Siblings — you only deployed it.

Prefer small diffs with a kill switch. Errgroup Cancel Siblings changes that require a hero engineer on-call are not done, even if the feature flag is green.

For reviews, I ask: what happens twice? what happens never? what happens partially? Errgroup Cancel Siblings designs that cannot answer those three questions are not production-ready.

## Common regressions after launch

I have watched teams under-specify Errgroup Cancel Siblings and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

The anti-pattern is dual-writing without an outbox. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

Related reading:

- [idempotency distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/)
- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Maintenance burden over 12 months

Most write-ups on Errgroup Cancel Siblings stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

The anti-pattern is dual-writing without an outbox. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Write the acceptance check in product language: when on-call already feels this pain weekly, operators can explain system state without spelunking five tabs. If they cannot, keep iterating.

## Practical defaults I use for Errgroup Cancel Siblings

I have watched teams under-specify Errgroup Cancel Siblings and then spend a quarter cleaning up production surprises. The work is less about clever APIs and more about making it routine to avoid the demo-only happy path.

The anti-pattern is dual-writing without an outbox. It looks fine in staging with one tenant and tidy data, then collapses under retries, partial deploys, or a noisy neighbor.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

In code review, demand a threat/failure note: what happens on retry, on partial deploy, and on dual-writing without an outbox. If it is missing, the PR is incomplete.

## Review questions before merging Errgroup Cancel Siblings work

Most write-ups on Errgroup Cancel Siblings stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

In Go stacks I lean on Go, pgx for the mechanics, but ownership stays human. Someone has to define invariants, name the dashboard, and decide what happens when dual-writing without an outbox.

Document the semantic meaning of success and compensation. Future you will not remember why a shortcut was safe — and neither will the next team.

A month in, prune unused paths. Errgroup Cancel Siblings accumulates flags and dual-writes faster than teams expect; schedule deletion the same day you ship the new path.

## Field notes after the first month of Errgroup Cancel Siblings

Most write-ups on Errgroup Cancel Siblings stop at the demo. This one starts from situations where on-call already feels this pain weekly, because that is when the abstraction either pays rent or becomes toil.

Make Errgroup Cancel Siblings error rate a first-class signal before you celebrate the launch. If you cannot see regressions within an hour, you do not yet operate Errgroup Cancel Siblings — you only deployed it.

Prefer small diffs with a kill switch. Errgroup Cancel Siblings changes that require a hero engineer on-call are not done, even if the feature flag is green.

Default to deny-by-default configs, explicit timeouts, and a single dashboard row for Errgroup Cancel Siblings error rate. Expand only when the metric says you must.

## Resources

- https://martinfowler.com/
- https://12factor.net/
