---
title: "Priority and Fairness in Job Queues"
slug: "background-jobs-priority-fairness"
description: "Naive FIFO job queues starve low-priority work and let one tenant monopolize workers. Implement priority queues, weighted fair queuing, and per-tenant rate limits for background job systems."
datePublished: "2024-12-09"
dateModified: "2024-12-09"
tags: ["Backend", "Architecture", "Job Queues"]
keywords: "job queue priority, weighted fair queuing, tenant fairness job queue, priority queue workers, background job starvation"
faq:
  - q: "What is job queue starvation?"
    a: "Starvation happens when high-volume low-priority jobs fill the queue and urgent jobs wait indefinitely. Pure FIFO processing has no concept of urgency. Priority queues solve this by processing higher-priority jobs first, but naive priority queues can starve low-priority jobs forever."
  - q: "What is weighted fair queuing for job queues?"
    a: "Weighted fair queuing (WFQ) assigns each tenant or job class a weight and guarantees each gets a proportional share of worker capacity. A tenant with weight 2 gets twice the throughput of weight 1, but no tenant gets zero — preventing monopolization while respecting priority differences."
  - q: "How many priority levels should I use?"
    a: "Three to five levels is practical: critical (payment processing), high (user-triggered), normal (default), low (analytics), bulk (reports/exports). More levels increase complexity without proportional benefit. Map levels to queue names or score fields, not separate worker pools unless isolation is required."
---

One tenant submits 50,000 export jobs. Another tenant's password reset email sits in the queue for twenty minutes. Your FIFO job queue treats a bulk CSV export the same as a payment capture — first in, first out, whoever shouts loudest wins. Priority and fairness aren't luxuries for large platforms; they're what keeps your queue from becoming a denial-of-service vector against your own users.

## Priority levels

```typescript
enum JobPriority {
  CRITICAL = 1,   // payments, auth
  HIGH = 3,       // user-triggered actions
  NORMAL = 5,     // default
  LOW = 7,        // analytics, indexing
  BULK = 10,      // exports, reports
}
```

Store priority on the job record:

```sql
CREATE TABLE jobs (
    id          UUID PRIMARY KEY,
    queue       VARCHAR(50) NOT NULL DEFAULT 'default',
    priority    INT NOT NULL DEFAULT 5,
    tenant_id   UUID NOT NULL,
    payload     JSONB NOT NULL,
    status      VARCHAR(20) DEFAULT 'pending',
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_jobs_dequeue ON jobs(priority, created_at)
    WHERE status = 'pending';
```

Dequeue with priority ordering:

```sql
SELECT * FROM jobs
WHERE status = 'pending'
ORDER BY priority ASC, created_at ASC
LIMIT 1
FOR UPDATE SKIP LOCKED;
```

Lower number = higher priority. `SKIP LOCKED` enables concurrent workers.

## Starvation prevention with aging

Pure priority starves BULK forever. Increase effective priority as jobs wait:

```typescript
function effectivePriority(job: Job): number {
  const waitMinutes = (Date.now() - job.createdAt.getTime()) / 60_000;
  const agingBonus = Math.floor(waitMinutes / 10); // +1 priority level per 10 min wait
  return job.priority - agingBonus;
}
```

Or promote jobs after a max wait threshold:

```typescript
if (waitMinutes > 60 && job.priority > JobPriority.NORMAL) {
  await db.update(jobs).set({ priority: JobPriority.NORMAL }).where(eq(jobs.id, job.id));
}
```

## Weighted fair queuing per tenant

Track per-tenant in-flight count and enforce share:

```typescript
const TENANT_WEIGHTS: Record<string, number> = {
  enterprise: 3,
  pro: 2,
  free: 1,
};

async function dequeueWithFairness(): Promise<Job | null> {
  const tenants = await db
    .select({ tenantId: jobs.tenantId, count: count() })
    .from(jobs)
    .where(eq(jobs.status, 'running'))
    .groupBy(jobs.tenantId);

  const runningByTenant = new Map(tenants.map(t => [t.tenantId, t.count]));

  const pending = await db
    .select()
    .from(jobs)
    .where(eq(jobs.status, 'pending'))
    .orderBy(jobs.priority, jobs.createdAt)
    .limit(100);

  for (const job of pending) {
    const weight = TENANT_WEIGHTS[job.tenantTier] ?? 1;
    const running = runningByTenant.get(job.tenantId) ?? 0;
    const maxConcurrent = weight * 5; // 5, 10, or 15 concurrent per tier

    if (running < maxConcurrent) {
      return job;
    }
  }
  return null;
}
```

Enterprise tenants get more concurrent slots but can't consume 100% of workers.

## Separate queues for isolation

Critical jobs get dedicated workers:

```
critical-queue  → 4 dedicated workers (always reserved)
default-queue   → 8 shared workers
bulk-queue      → 2 workers (low CPU instances)
```

BullMQ / Sidekiq support named queues with per-queue concurrency. A bulk export never blocks a payment job when they share zero workers.

## Rate limiting enqueue

Prevent queue flooding at the source:

```typescript
async function enqueueJob(job: NewJob): Promise<void> {
  const recentCount = await redis.incr(`enqueue:${job.tenantId}:${hourBucket()}`);
  await redis.expire(`enqueue:${job.tenantId}:${hourBucket()}`, 3600);

  const limit = TENANT_RATE_LIMITS[job.tenantTier] ?? 1000;
  if (recentCount > limit) {
    throw new RateLimitError(`Tenant ${job.tenantId} exceeded hourly job limit`);
  }

  await db.insert(jobs).values(job);
}
```

## Monitoring fairness

Track per-tenant:
- Queue depth (pending jobs)
- Wait time p95 by priority level
- Processing rate (jobs/minute)
- Starvation events (jobs waiting > SLA)

Dashboard a "noisy neighbor" panel — the tenant with highest queue depth and lowest priority mix.

## Weighted fair queuing implementation

WFQ ensures each tenant gets proportional bandwidth regardless of queue depth:

```python
import heapq
from dataclasses import dataclass, field

@dataclass(order=True)
class FairJob:
    virtual_finish_time: float
    tenant_id: str = field(compare=False)
    job_id: str = field(compare=False)
    weight: float = field(compare=False)

class WeightedFairQueue:
    def __init__(self):
        self.heap: list[FairJob] = []
        self.virtual_time: dict[str, float] = defaultdict(float)

    def enqueue(self, job, tenant_id: str, weight: float):
        self.virtual_time[tenant_id] += 1.0 / weight
        heapq.heappush(self.heap, FairJob(
            virtual_finish_time=self.virtual_time[tenant_id],
            tenant_id=tenant_id,
            job_id=job.id,
            weight=weight,
        ))

    def dequeue(self) -> FairJob:
        return heapq.heappop(self.heap)
```

Tenant with weight=2 gets twice the processing rate of weight=1 tenant — regardless of how many jobs each has queued.

## Priority levels with SLA guarantees

Define priority tiers with explicit SLA targets:

| Priority | SLA (p95 wait) | Use case | Preemption |
|---|---|---|---|
| Critical | <30 seconds | Payment webhooks | Can preempt lower |
| High | <5 minutes | User-triggered exports | No |
| Normal | <30 minutes | Background sync | No |
| Low | <4 hours | Analytics, cleanup | No |

```python
PRIORITY_QUEUES = {
    "critical": {"sla_seconds": 30, "workers": 4},
    "high":     {"sla_seconds": 300, "workers": 8},
    "normal":   {"sla_seconds": 1800, "workers": 16},
    "low":      {"sla_seconds": 14400, "workers": 4},
}
```

Dedicated worker pools per priority — critical jobs never wait behind low-priority backlog.

## Starvation prevention

Low-priority jobs can starve if high-priority queue always has work:

```python
def select_next_job(queues: dict[str, Queue], starvation_threshold_seconds: int = 3600):
    # Check for starved jobs first
    for priority in ["low", "normal"]:
        oldest = queues[priority].peek_oldest()
        if oldest and oldest.wait_time > starvation_threshold_seconds:
            return oldest  # force process regardless of higher priority backlog

    # Normal priority selection
    for priority in ["critical", "high", "normal", "low"]:
        if not queues[priority].empty():
            return queues[priority].dequeue()
```

Promote jobs waiting beyond starvation threshold — alert ops when promotion happens frequently (indicates under-provisioned workers).

## Failure modes

- **No per-tenant rate limiting** — one tenant floods queue; others starve
- **Single priority queue** — low-priority jobs never processed during high load
- **No starvation detection** — low-priority jobs wait indefinitely
- **Priority inversion** — critical job waits for low-priority job holding resource
- **No noisy neighbor monitoring** — tenant abuse undetected until SLA breach

## Production checklist

- Weighted fair queuing or dedicated worker pools per priority tier
- Per-tenant rate limiting on job enqueue
- Starvation threshold with automatic job promotion
- SLA targets defined per priority level
- Noisy neighbor dashboard (queue depth + priority mix per tenant)
- Alert when any job waits beyond its priority SLA

## Resources

- [BullMQ priority and rate limiting](https://docs.bullmq.io/)
- [Sidekiq queue priorities](https://github.com/sidekiq/sidekiq/wiki/Advanced-Options)
- [Weighted Fair Queuing (original paper)](https://dl.acm.org/doi/10.1145/103236.103247)
- [Google SRE — load balancing](https://sre.google/sre-book/load-balancing-datacenter/)
- [Celery routing and priorities](https://docs.celeryq.dev/en/stable/userguide/routing.html)
