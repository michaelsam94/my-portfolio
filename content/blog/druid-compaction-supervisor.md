---
title: "Druid Compaction Supervisor"
slug: "druid-compaction-supervisor"
description: "Druid Compaction Supervisor: how to ship druid compaction behind flags with a rollback — tradeoffs, failure modes, instrumentation, and rollout checks for production systems."
datePublished: "2025-12-05"
dateModified: "2026-08-12"
tags:
  - "Engineering"
  - "Druid"
keywords: "druid, compaction, supervisor, production, engineering"
faq:
  - q: "What is Druid Compaction Supervisor?"
    a: "Druid Compaction Supervisor is the production approach to ship druid compaction behind flags with a rollback. It emphasizes contracts, failure modes, and metrics over slide-deck definitions."
  - q: "When should teams invest in Druid Compaction Supervisor?"
    a: "Invest when enterprise buyers ask how you prove it works. If user-visible errors or cost already move with druid compaction supervisor, prioritize it."
  - q: "What is the most common mistake with Druid Compaction Supervisor?"
    a: "The usual failure is dual writes without an outbox or CDC story. Teams also skip measurement until after launch, which turns a design choice into an incident."
---
**Druid Compaction Supervisor** means you ship druid compaction behind flags with a rollback — with a named owner, a measurable signal, and a rollback a tired on-call can run. I reach for this when enterprise buyers ask how you prove it works; that is also when shortcuts like dual writes without an outbox or CDC story start paging people.

This write-up is specific to `druid-compaction-supervisor` in a product context, using OpenTelemetry, Postgres for the mechanics while keeping ownership human.

## A pragmatic path to Druid Compaction Supervisor

Teams usually discover Druid Compaction Supervisor after a quiet failure — wrong data, slow pages, or a bill spike. Design for enterprise buyers ask how you prove it works.

With OpenTelemetry, Postgres, the mechanics are straightforward; the hard part is invariants. The anti-pattern I still see is dual writes without an outbox or CDC story.

Ship behind a flag, canary by cohort, and write the rollback in the PR description. Druid Compaction Supervisor that needs a hero is not done.

Slug-specific note (druid-compaction-supervisor): prioritize supervisor behavior under load and verify with a fixture named `druid-compaction-supervisor-smoke`.

## Start from the user-visible symptom

I treat Druid Compaction Supervisor as an operations problem first. The goal is to ship druid compaction behind flags with a rollback, not to collect frameworks.

Put a metric on the user-visible effect of druid compaction supervisor before you optimize internals. If enterprise buyers ask how you prove it works, you need that graph on day one.

Acceptance check: an on-call engineer can explain system state for druid compaction supervisor from one dashboard and one runbook page.

Concretely, being able to ship druid compaction behind flags with a rollback forces explicit choices: source of truth, timeout budgets, and which errors users see versus operators.

Slug-specific note (druid-compaction-supervisor): prioritize supervisor behavior under load and verify with a fixture named `druid-compaction-supervisor-smoke`.

```typescript
// Druid Compaction Supervisor
export async function handle_druid_compaction_supervisor(input: unknown): Promise<Result> {
  const parsed = schema.safeParse(input);
  if (!parsed.success) throw new ValidationError(parsed.error);
  const span = tracer.startSpan("druid-compaction-supervisor");
  try {
    if (await repo.seen(parsed.data.idempotencyKey)) return { ok: true, deduped: true };
    const out = await repo.execute(parsed.data);
    await repo.mark(parsed.data.idempotencyKey);
    return out;
  } finally {
    span.end();
  }
}
```

## Implementation details for druid compaction supervisor

I treat Druid Compaction Supervisor as an operations problem first. The goal is to ship druid compaction behind flags with a rollback, not to collect frameworks.

Put a metric on the user-visible effect of druid compaction supervisor before you optimize internals. If enterprise buyers ask how you prove it works, you need that graph on day one.

Ship behind a flag, canary by cohort, and write the rollback in the PR description. Druid Compaction Supervisor that needs a hero is not done.

My never-again list for druid compaction supervisor: dual writes without an outbox or CDC story; shipping without a kill switch; and alerting only on infrastructure CPU.

Slug-specific note (druid-compaction-supervisor): prioritize supervisor behavior under load and verify with a fixture named `druid-compaction-supervisor-smoke`.

| Approach | Fits when | Main risk |
| --- | --- | --- |
| Minimal | Early product, small blast radius | Hidden coupling; dual writes without an outbox or CDC story |
| Durable | enterprise buyers ask how you prove it works | More parts; needs a clear owner |
| Staged hybrid | Brownfield migration | Dual-running complexity |

## Flags, canaries, and kill switches

Production systems punish vague ownership and unmeasured happy paths. For druid compaction supervisor, that means making failure visible early.

Keep side effects at the edges and make every write idempotent. Druid Compaction Supervisor without retry semantics is a future incident write-up.

Document what 'success' and 'undo' mean in product language. Future reviewers will not share your context on druid compaction supervisor.

Review prompts I use: what happens twice, what happens never, what happens partially? If Druid Compaction Supervisor cannot answer, it is not production-ready.

Slug-specific note (druid-compaction-supervisor): prioritize supervisor behavior under load and verify with a fixture named `druid-compaction-supervisor-smoke`.

## Proving it worked

I treat Druid Compaction Supervisor as an operations problem first. The goal is to ship druid compaction behind flags with a rollback, not to collect frameworks.

With OpenTelemetry, Postgres, the mechanics are straightforward; the hard part is invariants. The anti-pattern I still see is dual writes without an outbox or CDC story.

Ship behind a flag, canary by cohort, and write the rollback in the PR description. Druid Compaction Supervisor that needs a hero is not done.

Slug-specific note (druid-compaction-supervisor): prioritize supervisor behavior under load and verify with a fixture named `druid-compaction-supervisor-smoke`.

Related reading:

- [event driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/)
- [saga pattern distributed transactions](https://blog.michaelsam94.com/saga-pattern-distributed-transactions/)
- [designing for observability slos](https://blog.michaelsam94.com/designing-for-observability-slos/)

## Follow-ups teams usually skip

Teams usually discover Druid Compaction Supervisor after a quiet failure — wrong data, slow pages, or a bill spike. Design for enterprise buyers ask how you prove it works.

Keep side effects at the edges and make every write idempotent. Druid Compaction Supervisor without retry semantics is a future incident write-up.

Document what 'success' and 'undo' mean in product language. Future reviewers will not share your context on druid compaction supervisor.

Slug-specific note (druid-compaction-supervisor): prioritize supervisor behavior under load and verify with a fixture named `druid-compaction-supervisor-smoke`.

## Practical defaults for Druid Compaction Supervisor

Teams usually discover Druid Compaction Supervisor after a quiet failure — wrong data, slow pages, or a bill spike. Design for enterprise buyers ask how you prove it works.

Put a metric on the user-visible effect of druid compaction supervisor before you optimize internals. If enterprise buyers ask how you prove it works, you need that graph on day one.

Acceptance check: an on-call engineer can explain system state for druid compaction supervisor from one dashboard and one runbook page.

Slug-specific note (druid-compaction-supervisor): prioritize supervisor behavior under load and verify with a fixture named `druid-compaction-supervisor-smoke`.

Default deny, explicit timeouts, and one dashboard row for druid compaction supervisor. Expand only when the metric demands it.

## Review questions before merging druid compaction supervisor work

Production systems punish vague ownership and unmeasured happy paths. For druid compaction supervisor, that means making failure visible early.

Keep side effects at the edges and make every write idempotent. Druid Compaction Supervisor without retry semantics is a future incident write-up.

Acceptance check: an on-call engineer can explain system state for druid compaction supervisor from one dashboard and one runbook page.

Slug-specific note (druid-compaction-supervisor): prioritize supervisor behavior under load and verify with a fixture named `druid-compaction-supervisor-smoke`.

Default deny, explicit timeouts, and one dashboard row for druid compaction supervisor. Expand only when the metric demands it.

## Field notes after thirty days of druid compaction supervisor

Teams usually discover Druid Compaction Supervisor after a quiet failure — wrong data, slow pages, or a bill spike. Design for enterprise buyers ask how you prove it works.

Keep side effects at the edges and make every write idempotent. Druid Compaction Supervisor without retry semantics is a future incident write-up.

Document what 'success' and 'undo' mean in product language. Future reviewers will not share your context on druid compaction supervisor.

Slug-specific note (druid-compaction-supervisor): prioritize supervisor behavior under load and verify with a fixture named `druid-compaction-supervisor-smoke`.

In review, require a short failure note covering retry, partial deploy, and dual writes without an outbox or CDC story. Missing that note blocks merge.

## Resources

- Internal runbook seed: `druid-compaction-supervisor`
- https://12factor.net/
- https://martinfowler.com/
