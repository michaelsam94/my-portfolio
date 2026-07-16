---
title: "Durable Workflows with Temporal"
slug: "backend-job-scheduling-temporal"
description: "Use Temporal for durable workflows: retries, timers, signals, and why it beats cron-plus-queue for long-running business processes."
datePublished: "2024-11-18"
dateModified: "2024-11-18"
tags: ["Backend", "Architecture", "Workflows"]
keywords: "Temporal workflow, durable execution, Temporal.io, workflow engine, saga orchestration, long running process"
faq:
  - q: "What problem does Temporal solve that a queue doesn't?"
    a: "Queues move messages; Temporal runs workflows that survive process restarts, sleep for days, wait for signals, and retry activities with full history. You write ordinary code with await points — the service persists progress so a crash doesn't lose which step you were on."
  - q: "When is Temporal overkill?"
    a: "Fire-and-forget background jobs, simple cron, or single-step async work don't need a workflow engine. Use Temporal when the process spans multiple services, human approvals, timers (dunning, reminders), or must not double-execute side effects across failures."
  - q: "How do activities differ from workflows?"
    a: "Workflows must be deterministic — no random, no direct IO — so history can replay. Activities perform the IO (HTTP, DB, email) and are retried with policies you configure. That split is the core mental model; violate determinism and you'll get non-determinism errors on replay."
---

Cron plus a queue works until the business process has seven steps, two human waits, and a three-day timer. Then you're storing state machines in Postgres by hand and praying your retry logic matches reality. Temporal (and similar durable-execution systems) make that process a function you can read — with the platform owning recovery.

## Workflows vs activities

```typescript
// Workflow — deterministic orchestration
export async function onboardMerchant(input: OnboardInput): Promise<void> {
  await createAccounts(input); // activity
  await sendVerificationEmail(input.email);

  const verified = await condition(() => verifiedFlag, "72 hours");
  if (!verified) {
    await markAbandoned(input.merchantId);
    return;
  }

  await provisionProduction(input.merchantId);
}
```

```typescript
// Activity — real IO, configured retries
export async function sendVerificationEmail(email: string): Promise<void> {
  await emailClient.send({ to: email, template: "verify" });
}
```

If the worker dies mid-`provisionProduction`, another worker replays history, skips completed activities, and continues. You don't rebuild "step = 4" columns.

## Patterns that map well

- **Saga / orchestration** — compensate on failure with explicit activities
- **Dunning and reminders** — `sleep` / timers that survive deploys
- **Human-in-the-loop** — signals or updates when an analyst approves
- **Entity workflows** — one workflow per order/device as a long-lived actor

## What to keep out of workflows

- Large payloads in workflow arguments (store blobs elsewhere, pass IDs)
- Non-deterministic calls (`Date.now()`, random, UUID) without Temporal's side-effect APIs
- Tight loops without timers — you'll flood history

## Operational basics

Run a Temporal cluster (self-hosted or Cloud), workers that poll task queues, and version workflows carefully when you change code (`patched` / versioning APIs). Observe workflow failures separately from activity failures — different dashboards, different on-call meaning.

For simpler needs, [background job queues](https://blog.michaelsam94.com/background-jobs-queue-workers/) remain the right default. Reach for Temporal when the process *is* the product logic and reliability requirements outgrow ad-hoc state machines.

## Temporal vs cron, queues, and Step Functions

The decision tree is simpler than vendor marketing suggests. Cron fires on a schedule with no memory of partial failure — fine for nightly reports, wrong for "charge card, wait three days, retry twice, then escalate." A message queue moves one job at a time with at-least-once delivery, but orchestration across seven steps means you build your own state table, visibility timeouts, and dead-letter handling. AWS Step Functions and Temporal solve overlapping problems; Step Functions fits AWS-native shops with JSON state machines, while Temporal gives you real code (TypeScript, Go, Java) with local testing and open-source portability.

| Need | Cron | Queue worker | Temporal |
|---|---|---|---|
| Single async task | Yes | Yes | Overkill |
| Retry with backoff | Manual | Built-in per message | Built-in per activity |
| Multi-day timer | No | Hacky delayed messages | Native `sleep` |
| Human approval wait | No | Polling or custom | Signals / conditions |
| Full execution history | No | Logs only | Replayable event log |

If your team already maintains a Postgres `workflow_runs` table with step enums and you're spending sprint time on "what happens when step 4 succeeds but step 5 times out," you've reinvented half of Temporal. Migrate the orchestration, keep domain logic in activities.

## Workflow versioning without breaking production

Deploying new workflow code while thousands of in-flight executions run old logic is the operational trap. Temporal's `patched` API and workflow versioning let you branch:

```typescript
import { patched } from '@temporalio/workflow';

export async function onboardMerchant(input: OnboardInput) {
  if (patched('add-kyc-step-2025-03')) {
    await runKycCheck(input); // new activity
  }
  await createAccounts(input);
  // ...
}
```

Old histories replay through the pre-patch path; new starts take the new path. Never change workflow structure without a patch or version bump — non-determinism errors (`NondeterminismError: Activity type mismatch`) mean someone edited a running workflow's code path. Treat workflow definitions like database migrations: deploy-compatible first, then remove old branches after drain.

## Failure modes I've debugged

**Activity succeeds, workflow thinks it failed.** Network partition between worker and Temporal server can leave activity completion unrecorded. Activities must be idempotent; use idempotency keys on external calls. **Workflow stuck in Running forever.** Usually a missing signal or a `condition` with no timeout. Always bound human waits: `await condition(() => approved, '30 days')` then escalate. **History too large.** Workflows that loop thousands of times without `continueAsNew` hit size limits (~50MB). Batch processing should spawn child workflows or call `continueAsNew` every N iterations. **Worker task backlog.** Scale workers horizontally on the same task queue; one slow activity type can starve the queue — split hot activities to dedicated queues.

## Worker deployment and observability

Workers poll task queues — they're stateless processes you scale like API servers. Run at least two replicas per queue in production so deploys don't drain all pollers. Separate task queues by domain (`payments`, `onboarding`) so a poison message in one domain doesn't block another. Temporal UI shows every workflow execution with input, result, pending activities, and stack traces — use it as the primary debug surface, not grep through application logs.

Metrics worth alerting on: `workflow_task_schedule_to_start_latency` (worker capacity), `activity_task_failures` by type (downstream dependency health), and `workflow_endtoend_latency` p99 by workflow type (SLA regressions). Export to Prometheus via Temporal's SDK metrics or Cloud observability.

## Production checklist

- Activities are idempotent; external calls carry idempotency keys
- Workflow code has zero direct I/O — all side effects in activities
- Human waits and external callbacks use signals with documented payloads
- Timers have explicit timeout policies and escalation paths
- Workflow changes ship with `patched` or version identifiers
- Workers run ≥2 replicas; critical queues isolated
- Load tests include worker restart mid-execution
- Runbooks document how to terminate, reset, or signal stuck workflows

Start with one workflow type in staging — onboard a merchant, process a refund, run a provisioning pipeline — and deliberately kill workers mid-execution. If replay completes without duplicate side effects, your activity boundaries are correct.

## Resources

- [Temporal documentation](https://docs.temporal.io/)
- [Temporal — What is durable execution?](https://temporal.io/blog/durable-execution)
- [Cadence/Temporal community patterns](https://community.temporal.io/)
---
