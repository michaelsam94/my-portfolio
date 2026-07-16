---
title: "Reliable Scheduled Jobs"
slug: "background-jobs-cron-scheduling"
description: "Cron jobs fail silently, double-run on failover, and miss executions during downtime. Build reliable scheduled jobs with leader election, execution tracking, and missed-run catch-up."
datePublished: "2024-12-04"
dateModified: "2024-12-04"
tags: ["Backend", "DevOps", "Cron", "Architecture"]
keywords: "reliable cron jobs, scheduled job execution, leader election cron, missed job catch-up, cron double execution, distributed cron"
faq:
  - q: "Why do plain cron jobs fail in production?"
    a: "Cron assumes one machine, always on, with correct timezone. In distributed systems, every instance runs the same cron entry (double execution), jobs overlap if previous run is slow, and downtime during scheduled time means missed runs with no catch-up. Cron has no built-in tracking, retry, or deduplication."
  - q: "How do I prevent duplicate cron execution across replicas?"
    a: "Use leader election — only the elected leader runs scheduled jobs. Implement with Postgres advisory locks, Redis SET NX with TTL, or Kubernetes Lease objects. Non-leaders skip execution. Combine with an execution log table that rejects duplicate run IDs."
  - q: "Should missed cron runs be executed on recovery?"
    a: "Depends on the job. Daily report generation should catch up once. Hourly metrics aggregation can skip missed windows. Idempotent jobs with a 'last processed timestamp' naturally catch up; destructive or notification jobs should skip missed runs and log the gap."
---

`0 2 * * * /app/nightly-reconcile.sh` works on your laptop. In production you have three Kubernetes pods, a deploy at 2:01 AM, and a pod that restarted mid-run. Now reconciliation ran twice, or not at all, and finance finds a $40k discrepancy on Monday. Reliable scheduled jobs need execution tracking, leader election, overlap protection, and explicit policies for missed runs — not crontab entries on every instance.

## Failure modes of naive cron

| Problem | Cause | Fix |
|---------|-------|-----|
| Double execution | Cron on every replica | Leader election |
| Overlapping runs | Job slower than interval | Mutex / skip-if-running |
| Missed run | Downtime during schedule | Catch-up policy |
| Silent failure | No exit code monitoring | Execution log + alerts |
| Timezone bugs | UTC vs local | Always UTC internally |

## Execution tracking table

```sql
CREATE TABLE job_executions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_name     VARCHAR(100) NOT NULL,
    scheduled_at TIMESTAMPTZ NOT NULL,
    started_at   TIMESTAMPTZ,
    finished_at  TIMESTAMPTZ,
    status       VARCHAR(20) DEFAULT 'pending',
    error        TEXT,
    UNIQUE (job_name, scheduled_at)
);
```

The unique constraint on `(job_name, scheduled_at)` prevents duplicate runs for the same scheduled window.

## Leader election with Postgres

```typescript
async function tryAcquireLeadership(jobName: string, lockDurationSec: number): Promise<boolean> {
  const result = await db.execute(sql`
    SELECT pg_try_advisory_lock(hashtext(${jobName}))
  `);
  return result.rows[0].pg_try_advisory_lock === true;
}

async function runScheduledJob(jobName: string, scheduledAt: Date, fn: () => Promise<void>) {
  if (!await tryAcquireLeadership(jobName, 300)) return;

  try {
    const inserted = await db
      .insert(jobExecutions)
      .values({ jobName, scheduledAt, status: 'running', startedAt: new Date() })
      .onConflictDoNothing()
      .returning();

    if (inserted.length === 0) return; // already ran

    await fn();

    await db.update(jobExecutions)
      .set({ status: 'completed', finishedAt: new Date() })
      .where(eq(jobExecutions.jobName, jobName));
  } catch (error) {
    await db.update(jobExecutions)
      .set({ status: 'failed', error: String(error), finishedAt: new Date() })
      .where(eq(jobExecutions.jobName, jobName));
    throw error;
  } finally {
    await db.execute(sql`SELECT pg_advisory_unlock(hashtext(${jobName}))`);
  }
}
```

## Skip-if-running (overlap protection)

```typescript
async function runWithOverlapGuard(jobName: string, fn: () => Promise<void>) {
  const running = await db
    .select()
    .from(jobExecutions)
    .where(and(
      eq(jobExecutions.jobName, jobName),
      eq(jobExecutions.status, 'running'),
      gt(jobExecutions.startedAt, new Date(Date.now() - 3600_000))
    ));

  if (running.length > 0) {
    logger.warn(`${jobName} still running, skipping`);
    return;
  }

  await runScheduledJob(jobName, truncateToHour(new Date()), fn);
}
```

## Missed run catch-up

```typescript
async function catchUpMissedRuns(jobName: string, intervalMs: number, fn: (scheduledAt: Date) => Promise<void>) {
  const lastRun = await db
    .select({ scheduledAt: jobExecutions.scheduledAt })
    .from(jobExecutions)
    .where(and(eq(jobExecutions.jobName, jobName), eq(jobExecutions.status, 'completed')))
    .orderBy(desc(jobExecutions.scheduledAt))
    .limit(1);

  const lastScheduled = lastRun[0]?.scheduledAt ?? new Date(0);
  const now = new Date();
  let next = new Date(lastScheduled.getTime() + intervalMs);

  while (next <= now) {
    await runScheduledJob(jobName, next, () => fn(next));
    next = new Date(next.getTime() + intervalMs);
  }
}
```

Cap catch-up iterations — if downtime was 7 days and interval is hourly, process the last N windows and alert on the gap.

## Managed alternatives

| Tool | Leader election | UI | Best for |
|------|----------------|-----|----------|
| Cron + custom code | DIY | None | Full control |
| Sidekiq-Cron / BullMQ | Via Redis | Basic | App-embedded |
| Temporal schedules | Built-in | Temporal UI | Complex workflows |
| AWS EventBridge | Managed | CloudWatch | AWS-native |
| Kubernetes CronJob | Single pod | K8s events | Cluster-level |

For simple nightly jobs, Postgres advisory locks + execution table is enough. For jobs with steps, retries, and compensation, use [Temporal](https://blog.michaelsam94.com/backend-job-scheduling-temporal/).

## Monitoring

Alert on:
- Job not completed within expected window (+15 min grace)
- Failed status in execution log
- Catch-up backlog > threshold
- Job duration trending up (early warning)

## Exactly-once cron execution

Prevent duplicate runs when multiple app instances exist:

```python
import hashlib
from datetime import datetime

def acquire_job_lock(job_name: str, db) -> bool:
    window = datetime.utcnow().strftime("%Y-%m-%d-%H")  # hourly window
    lock_key = hashlib.sha256(f"{job_name}:{window}".encode()).hexdigest()

    try:
        db.execute(
            "INSERT INTO job_locks (lock_key, acquired_at) VALUES (%s, NOW())",
            (lock_key,)
        )
        return True  # acquired
    except IntegrityError:
        return False  # another instance holds lock

def run_scheduled_job(job_name: str, fn):
    if not acquire_job_lock(job_name, db):
        logger.info(f"Skipping {job_name} — already running on another instance")
        return
    try:
        fn()
        db.execute(
            "UPDATE job_executions SET status='completed', completed_at=NOW() WHERE job_name=%s",
            (job_name,)
        )
    except Exception as e:
        db.execute(
            "UPDATE job_executions SET status='failed', error=%s WHERE job_name=%s",
            (str(e), job_name)
        )
        raise
```

PostgreSQL advisory lock or unique constraint on `(job_name, window)` — both work. Choose based on existing infrastructure.

## Timezone and DST handling

Cron schedules are timezone-sensitive:

```python
import pytz
from croniter import croniter

TZ = pytz.timezone("America/New_York")

def next_run(cron_expr: str) -> datetime:
    now = datetime.now(TZ)
    return croniter(cron_expr, now).get_next(datetime)

# "0 2 * * *" in America/New_York
# DST spring forward: 2 AM doesn't exist → run at 3 AM
# DST fall back: 2 AM happens twice → run once (lock prevents duplicate)
```

Store cron timezone explicitly in job definition. Never assume UTC without documenting it.

## Missed run catch-up policy

Define behavior when scheduler was down:

```python
CATCHUP_POLICY = {
    "nightly_report": {"max_missed": 1, "action": "run_latest"},      # run once on recovery
    "hourly_sync":    {"max_missed": 3, "action": "run_all"},        # catch up all missed
    "weekly_cleanup": {"max_missed": 0, "action": "skip"},           # skip if missed
}
```

Alert when catch-up queue exceeds threshold — indicates extended downtime or slow job execution.

## Failure modes

- **No distributed lock** — duplicate execution on multi-instance deployment
- **Cron in UTC, team expects local time** — jobs run at wrong hour twice yearly (DST)
- **Unbounded catch-up** — 7 days downtime → 168 hourly runs queued on recovery
- **No execution log** — failed jobs undetected until downstream data missing
- **Long-running job overlaps next schedule** — double execution; skip if previous still running

## Production checklist

- Distributed lock (advisory lock or unique constraint) prevents duplicate execution
- Timezone stored explicitly in job definition
- Catch-up policy defined per job (run_latest vs run_all vs skip)
- Execution log with status, started_at, completed_at, error
- Alert: job not completed within expected window + 15 min grace
- Skip next run if previous execution still in progress

## Resources

- [PostgreSQL advisory locks](https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS)
- [Kubernetes CronJob documentation](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/)
- [AWS EventBridge Scheduler](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-rule-schedule.html)
- [Sidekiq periodic jobs](https://github.com/sidekiq/sidekiq/wiki/Scheduled-Jobs)
- [Temporal schedules API](https://docs.temporal.io/workflows#schedule)
