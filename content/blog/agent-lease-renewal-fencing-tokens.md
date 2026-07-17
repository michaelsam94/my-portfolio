---
title: "AI Agents: Lease Renewal Fencing Tokens"
slug: "agent-lease-renewal-fencing-tokens"
description: "Lease renewal loops and fencing tokens for agent workers—TTL math, heartbeat jitter, stale holder detection, and storage-layer enforcement that prevents split-brain side effects."
datePublished: "2026-05-02"
dateModified: "2026-05-02"
tags: ["AI", "Agent", "Lease"]
keywords: "lease renewal, fencing token, distributed lock, agent worker, TTL, split brain, stale holder, etcd lease"
faq:
  - q: "Why are fencing tokens required if lease renewal usually works?"
    a: "Renewal fails silently when processes GC-pause, networks partition, or clock skew misaligns TTL. Two holders can exist briefly—the old one still running after lease expired and a new one started. Fencing tokens monotonically increase per resource; storage rejects writes from stale holders even if they believe they still hold the lease."
  - q: "How often should agent workers renew leases?"
    a: "Renew at one-third of TTL with ±10% jitter. Example: TTL 30s, renew every 10s jittered. If three consecutive renewals fail, stop work and exit—do not finish the LLM batch hoping the lease returns. Heartbeat interval must satisfy TTL ≥ 3× renew interval + max GC pause."
  - q: "Where should fencing tokens be enforced for agent pipelines?"
    a: "At every durable side effect: database job status updates, object store writes, message publish with ordering keys, billing meter increments. In-memory state alone does not need fencing. The token travels with the worker context and must be checked atomically in the same transaction as the mutation."
  - q: "Can Redis INCR serve as a fencing token source?"
    a: "Yes, if INCR runs in the same atomic script as lock acquire and the counter is per resource (job_id, tenant_id). The returned integer is the fence. Downstream stores persist max accepted fence per resource and reject lower values. UUID lock tokens are not fences unless monotonic per resource."
---
Two agent workers processed the same `billing-aggregate-tenant-881` job. The first worker's lease renewal loop stalled during a ninety-second stop-the-world GC; etcd expired the lease and elected a second worker. Both wrote invoice line items—duplicates surfaced in Stripe three days later. The team had lease renewal but no **fencing tokens** on the ledger writes. Lease renewal keeps holders honest most of the time; fencing tokens keep storage honest when renewal fails—the difference between a rare incident and a finance escalation.

## Leases versus locks in agent systems

A **lease** is time-bounded authority to act on a resource. Agent platforms use leases for:

| Resource | Typical TTL | Renewal | Fence required |
|----------|-------------|---------|----------------|
| Cron leader pod | 15–30s | etcd session | On config writes |
| Per-tenant agent run | 60–120s | custom loop | On workspace mutations |
| Tool execution slot | 10s | Redis PX + renew | On external API spend |
| Embedding batch job | 5–15 min | renew or chunk | On vector upserts |

Locks without TTL are dangerous—crashed workers hold forever. Leases without fencing are incomplete—expired workers may still write.

## Acquire, renew, release lifecycle

```python
import asyncio
import time
from dataclasses import dataclass

@dataclass
class Lease:
    resource_id: str
    holder_id: str
    fence: int
    expires_at: float

class LeaseClient:
    async def acquire(self, resource_id: str, ttl_sec: float) -> Lease | None: ...
    async def renew(self, lease: Lease, ttl_sec: float) -> Lease | None: ...
    async def release(self, lease: Lease) -> None: ...

async def run_with_lease(
    client: LeaseClient,
    resource_id: str,
    ttl_sec: float,
    work,
):
    lease = await client.acquire(resource_id, ttl_sec)
    if lease is None:
        raise ResourceBusy(resource_id)

    stop = asyncio.Event()
    renew_task = asyncio.create_task(
        renewal_loop(client, lease, ttl_sec, stop)
    )
    try:
        await work(lease.fence)
    finally:
        stop.set()
        await renew_task
        await client.release(lease)
```

**Renewal loop** with jitter and failure budget:

```python
async def renewal_loop(client, lease, ttl_sec, stop: asyncio.Event):
    interval = ttl_sec / 3
    failures = 0
    while not stop.is_set():
        jitter = interval * 0.1 * (2 * random.random() - 1)
        await asyncio.sleep(interval + jitter)
        if stop.is_set():
            break
        renewed = await client.renew(lease, ttl_sec)
        if renewed is None:
            failures += 1
            if failures >= 3:
                raise LeaseLost(lease.resource_id)
        else:
            lease = renewed
            failures = 0
```

On `LeaseLost`, cancel in-flight LLM calls and mark job **retryable**—continuing without authority duplicates side effects.

## Fencing token generation

Monotonic per resource, incremented only on successful acquire:

```lua
-- Redis: KEYS[1]=lock, KEYS[2]=fence, ARGV[1]=holder, ARGV[2]=ttl_ms
local ok = redis.call('set', KEYS[1], ARGV[1], 'NX', 'PX', ARGV[2])
if ok then
  local fence = redis.call('incr', KEYS[2])
  return fence
end
return 0
```

```go
// etcd: transactional create with revision as fence proxy
func (c *Client) Acquire(ctx context.Context, key, holder string, ttl int64) (fence int64, err error) {
  lease, err := c.cli.Grant(ctx, ttl)
  if err != nil {
    return 0, err
  }
  txn := c.cli.Txn(ctx).
    If(clientv3.Compare(clientv3.CreateRevision(key), "=", 0)).
    Then(clientv3.OpPut(key, holder, clientv3.WithLease(lease.ID)))
  resp, err := txn.Commit()
  if err != nil || !resp.Succeeded {
    return 0, ErrNotAcquired
  }
  return int64(resp.Header.Revision), nil
}
```

Prefer dedicated fence counters over etcd revision when revisions gap across unrelated keys.

## Storage-layer enforcement

Fencing belongs in the **same transaction** as business mutations:

```sql
CREATE TABLE agent_job_leases (
  job_id TEXT PRIMARY KEY,
  holder TEXT NOT NULL,
  fence BIGINT NOT NULL DEFAULT 0,
  expires_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE agent_job_runs (
  job_id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  accepted_fence BIGINT NOT NULL DEFAULT 0
);

-- Worker mutation: only if fence advances
UPDATE agent_job_runs
SET status = $status, accepted_fence = $fence
WHERE job_id = $job_id
  AND $fence > accepted_fence;
-- check rows affected == 1
```

Object stores lack compare-and-swap on arbitrary keys—use metadata table or conditional writes (S3 If-Match on version id updated with fence).

For **Kafka/Pulsar**, include fence in message key ordering; consumers reject messages with fence lower than stored max for that aggregate.

## TTL and GC pause math

Define:

- `T` = lease TTL
- `R` = renew interval ≈ T/3
- `G` = p99.9 GC pause + stall
- `N` = allowed consecutive renew failures before abort (typically 3)

Constraint: `T >= N * R + G`

Example: G = 90s for a misconfigured JVM agent sidecar → TTL must exceed 90s + 3×10s = 120s minimum, or fix GC. Agent Python workers rarely hit 90s STW—but asyncio blocked on sync CPU work can miss renewals equally.

## Detecting stale holders

Emit metrics when fence rejects writes:

```python
def apply_with_fence(db, job_id: str, fence: int, status: str):
    rowcount = db.execute(
        """
        UPDATE agent_job_runs
        SET status = %s, accepted_fence = %s
        WHERE job_id = %s AND %s > accepted_fence
        """,
        (status, fence, job_id, fence),
    )
    if rowcount == 0:
        metrics.inc("fence_rejected_writes_total", labels={"job_id": job_id})
        raise StaleHolderError(job_id, fence)
```

Alert on `fence_rejected_writes_total` spike—signals TTL too short, renewal bugs, or split brain in progress.

Log structured: `resource_id`, `holder_id`, `fence`, `lease_expires_at`, `renew_latency_ms`.

## Integration with agent orchestrators

Orchestrators (Temporal, custom DAG) should pass `fence` through activity context:

```typescript
interface AgentActivityContext {
  jobId: string;
  tenantId: string;
  leaseFence: number;
}

export async function embedBatch(ctx: AgentActivityContext, docs: string[]) {
  for (const batch of chunk(docs, 50)) {
    await vectorStore.upsert(batch, {
      jobId: ctx.jobId,
      minFence: ctx.leaseFence,
    });
    // re-check lease between batches for long jobs
    await assertLeaseValid(ctx);
  }
}
```

Long LLM tool chains split into **checkpointed batches** each validating fence—don't hold one lease for a twenty-minute run without renewal proof.

## Testing split-brain scenarios

Quarterly drills:

1. **SIGSTOP holder** during job—verify second acquirer gets higher fence and first worker's writes reject after resume.
2. **Partition holder from etcd/Redis**—verify lease expires and only new holder progresses.
3. **Slow renew path**—inject 2s latency on renew RPC; verify no false LeaseLost with proper TTL math.

Jepsen-style assertions: at most one writer increases `accepted_fence` for a job at any time.

## Anti-patterns

- **Renewal in a thread without crash detection**—main work exits, renewal continues forever.
- **UUID as fence**—not monotonic, cannot compare stale vs current.
- **Fence checked in app memory only**—second process bypasses.
- **Infinite lease extension on success**—crashed workers never release.
- **Ignoring fence rejections**—log and continue duplicates data.

## The takeaway

Lease renewal gives agent workers time-bounded authority; fencing tokens make that authority enforceable when renewal fails. Renew at one-third TTL with jitter, abort after consecutive renew failures, and enforce monotonic fences on every durable side effect. Measure fence rejections—they are the early warning for TTL misconfiguration and split-brain before users see duplicate charges or corrupted workspace state.

## FAQ

### Why are fencing tokens required if lease renewal usually works?

Renewal fails silently when processes GC-pause, networks partition, or clock skew misaligns TTL. Two holders can exist briefly—the old one still running after lease expired and a new one started. Fencing tokens monotonically increase per resource; storage rejects writes from stale holders even if they believe they still hold the lease.

### How often should agent workers renew leases?

Renew at one-third of TTL with ±10% jitter. Example: TTL 30s, renew every 10s jittered. If three consecutive renewals fail, stop work and exit—do not finish the LLM batch hoping the lease returns. Heartbeat interval must satisfy TTL ≥ 3× renew interval + max GC pause.

### Where should fencing tokens be enforced for agent pipelines?

At every durable side effect: database job status updates, object store writes, message publish with ordering keys, billing meter increments. In-memory state alone does not need fencing. The token travels with the worker context and must be checked atomically in the same transaction as the mutation.

### Can Redis INCR serve as a fencing token source?

Yes, if INCR runs in the same atomic script as lock acquire and the counter is per resource (job_id, tenant_id). The returned integer is the fence. Downstream stores persist max accepted fence per resource and reject lower values. UUID lock tokens are not fences unless monotonic per resource.

## Resources

- [martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html) — How to do distributed locking (fencing tokens)
- [etcd.io/docs/latest/learning/api/#lease-api](https://etcd.io/docs/latest/learning/api/#lease-api) — etcd lease API
- [redis.io/docs/manual/patterns/distributed-locks/](https://redis.io/docs/manual/patterns/distributed-locks/) — Redis distributed locks
- [jepsen.io/analyses](https://jepsen.io/analyses) — Jepsen consistency analyses
- [docs.temporal.io/develop/activity-retry-simulator](https://docs.temporal.io/develop/activity-retry-simulator) — Temporal activity reliability patterns
