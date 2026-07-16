---
title: "Designing a Background Job System"
slug: "background-jobs-queue-workers"
description: "Build a production background job system from queue schema to worker pools. Cover enqueue semantics, at-least-once delivery, dead letter queues, observability, and when to buy vs build."
datePublished: "2024-12-14"
dateModified: "2024-12-14"
tags: ["Backend", "Architecture", "Job Queues", "DevOps"]
keywords: "background job system design, job queue workers, dead letter queue, at-least-once jobs, job queue schema, worker pool architecture"
faq:
  - q: "Should I build a custom job queue or use an existing one?"
    a: "Use Sidekiq, BullMQ, Celery, or SQS unless you have unusual requirements (multi-tenant fairness, custom scheduling semantics, embedded in a specific database). Building from scratch makes sense at scale when existing tools can't meet isolation or compliance needs, but expect 6+ months to reach production parity."
  - q: "What is a dead letter queue?"
    a: "A DLQ holds jobs that failed all retry attempts. Instead of silently dropping failed work, move the job payload, error, and stack trace to the DLQ for manual inspection and replay. Alert when DLQ depth increases — it signals systemic failures or bad payloads."
  - q: "How many workers should I run?"
    a: "Start with workers = 2 × CPU cores for CPU-bound jobs, or 10–50 for I/O-bound (API calls, email). Scale on queue depth: if pending jobs grow over 5 minutes, add workers. Set max concurrency per worker to avoid memory exhaustion from large payloads."
---

Every app eventually needs background jobs — send email, process uploads, sync data, generate reports. The first version is a `setTimeout` or a cron script. The tenth version is a queue with workers, retries, dead letter handling, dashboards, and on-call runbooks. Whether you adopt Sidekiq or build on Postgres, the design decisions are the same: delivery semantics, failure handling, and observability.

## Core components

```
Producer → Queue (persistent) → Worker pool → Handler
                ↓ (failures)
            Retry queue → DLQ
                ↓
            Metrics + alerts
```

**Producer:** Application code enqueuing work.  
**Queue:** Durable storage (Redis, Postgres, SQS).  
**Worker:** Long-running process polling and executing jobs.  
**Handler:** Business logic for one job type.

## Job schema

```sql
CREATE TYPE job_status AS ENUM ('pending', 'running', 'completed', 'failed', 'dead');

CREATE TABLE jobs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type          VARCHAR(100) NOT NULL,
    payload       JSONB NOT NULL,
    status        job_status DEFAULT 'pending',
    priority      INT DEFAULT 5,
    attempts      INT DEFAULT 0,
    max_attempts  INT DEFAULT 5,
    run_at        TIMESTAMPTZ DEFAULT now(),
    started_at    TIMESTAMPTZ,
    completed_at  TIMESTAMPTZ,
    last_error    TEXT,
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_jobs_poll ON jobs(run_at, priority)
    WHERE status = 'pending';
```

`run_at` enables delayed/scheduled jobs.

## Worker loop

```typescript
async function workerLoop(workerId: string): Promise<void> {
  while (true) {
    const job = await claimNextJob();
    if (!job) {
      await sleep(1000);
      continue;
    }

    const startTime = Date.now();
    try {
      await handlers[job.type](job.payload);
      await markCompleted(job.id);
      metrics.recordSuccess(job.type, Date.now() - startTime);
    } catch (error) {
      await handleFailure(job, error);
      metrics.recordFailure(job.type, Date.now() - startTime);
    }
  }
}

async function claimNextJob(): Promise<Job | null> {
  return db.transaction(async (tx) => {
    const [job] = await tx
      .select()
      .from(jobs)
      .where(and(
        eq(jobs.status, 'pending'),
        lte(jobs.runAt, new Date())
      ))
      .orderBy(jobs.priority, jobs.runAt)
      .limit(1)
      .for('update', { skipLocked: true });

    if (!job) return null;

    await tx.update(jobs)
      .set({ status: 'running', startedAt: new Date(), attempts: job.attempts + 1 })
      .where(eq(jobs.id, job.id));

    return job;
  });
}
```

## Failure and retry

```typescript
async function handleFailure(job: Job, error: unknown): Promise<void> {
  const errorMsg = error instanceof Error ? error.stack : String(error);

  if (job.attempts >= job.maxAttempts) {
    await db.update(jobs)
      .set({ status: 'dead', lastError: errorMsg })
      .where(eq(jobs.id, job.id));
    await deadLetterQueue.push({ ...job, error: errorMsg });
    alert(`Job ${job.id} (${job.type}) moved to DLQ after ${job.attempts} attempts`);
    return;
  }

  const delayMs = fullJitterDelay(job.attempts, 1000, 300_000);
  await db.update(jobs)
    .set({
      status: 'pending',
      lastError: errorMsg,
      runAt: new Date(Date.now() + delayMs),
    })
    .where(eq(jobs.id, job.id));
}
```

## Handler registration

```typescript
const handlers: Record<string, (payload: unknown) => Promise<void>> = {
  'email.send': async (payload) => {
    const { to, subject, body } = payload as EmailPayload;
    await emailService.send(to, subject, body);
  },
  'image.process': async (payload) => {
    const { s3Key, transforms } = payload as ImagePayload;
    await imageProcessor.process(s3Key, transforms);
  },
};

// Validate payload at enqueue time with Zod
function enqueue(type: string, payload: unknown, opts?: EnqueueOptions) {
  const schema = payloadSchemas[type];
  schema.parse(payload); // fail fast on bad payload
  return db.insert(jobs).values({ type, payload, ...opts });
}
```

## Observability essentials

| Metric | Alert threshold |
|--------|----------------|
| Queue depth (pending) | > 1000 for 10 min |
| Processing latency p95 | > 2× baseline |
| Failure rate | > 5% over 15 min |
| DLQ depth | > 0 (any new entry) |
| Worker heartbeat | Missing > 60s |

Structured logs on every job: `{ jobId, type, attempt, durationMs, status }`.

## Graceful shutdown

```typescript
process.on('SIGTERM', async () => {
  shuttingDown = true;
  await waitForInFlightJobs(30_000);
  process.exit(0);
});
```

Kubernetes sends SIGTERM before killing pods — finish in-flight jobs or they'll retry.

## Build vs buy

| Requirement | Recommendation |
|-------------|---------------|
| Standard web app | BullMQ / Sidekiq |
| AWS-native | SQS + Lambda |
| Complex workflows | Temporal |
| Multi-tenant fairness | Custom on Postgres |
| < 100 jobs/day | Cron + execution table |

Pair with [priority and fairness](https://blog.michaelsam94.com/background-jobs-priority-fairness/) and [reliable cron](https://blog.michaelsam94.com/background-jobs-cron-scheduling/) for the full picture.

## Idempotency patterns

Jobs retry on failure — handlers must be idempotent:

```typescript
async function processPayment(job: Job<{ orderId: string }>) {
  const existing = await db.payment.findUnique({ where: { orderId: job.data.orderId } });
  if (existing?.status === "completed") return; // already processed

  await stripe.charges.create({ idempotencyKey: job.id, ... });
  await db.payment.update({ where: { orderId: job.data.orderId }, data: { status: "completed" } });
}
```

Use job ID or business key as idempotency token. Stripe, Square, and most payment APIs support idempotency keys — pass them through from queue job ID.

## Dead letter queue operations

DLQ is not a graveyard — define a process:

1. Alert on any new DLQ entry (PagerDuty, not weekly digest)
2. Inspect `{ jobId, error, payload, attempts }` within SLA
3. Fix root cause, replay job manually or via admin UI
4. Track DLQ rate as team metric — rising DLQ means systemic failure

```typescript
await deadLetterQueue.process(async (job) => {
  await slack.notify(`DLQ: ${job.name} failed after ${job.attemptsMade} attempts: ${job.failedReason}`);
});
```

## Multi-tenant job isolation

Shared queues need tenant fairness:

```typescript
const queue = new Queue("tasks", {
  defaultJobOptions: { priority: 10 },
});

// Enterprise tenant gets higher priority
await queue.add("report", data, { priority: tenant.tier === "enterprise" ? 1 : 10 });
```

Without priority, one tenant's bulk import blocks another's real-time notifications. Consider per-tenant queues for enterprise isolation.

Pair with [backend idempotent consumer pattern](https://blog.michaelsam94.com/backend-idempotent-consumer-pattern/) for event-driven job triggers.

## Common production mistakes

Teams get queue workers wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of queue workers fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [BullMQ documentation](https://docs.bullmq.io/)
- [Sidekiq wiki](https://github.com/sidekiq/sidekiq/wiki)
- [AWS SQS visibility timeout guide](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html)
- [Celery architecture overview](https://docs.celeryq.dev/en/stable/getting-started/introduction.html)
- [PostgreSQL SKIP LOCKED pattern](https://www.postgresql.org/docs/current/sql-select.html#SQL-FOR-UPDATE-SHARE)
