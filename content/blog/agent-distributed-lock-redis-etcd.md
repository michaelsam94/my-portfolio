---
title: "AI Agents: Distributed Lock Redis Etcd"
slug: "agent-distributed-lock-redis-etcd"
description: "Compare Redis Redlock and etcd lease-based locks for agent orchestration—fencing tokens, TTL math, split-brain behavior, and when each store fits."
datePublished: "2026-04-30"
dateModified: "2026-04-30"
tags: ["AI", "Agent", "Distributed"]
keywords: "distributed lock, Redis Redlock, etcd concurrency, fencing token, agent leader election, split brain"
faq:
  - q: "When should agent orchestrators use Redis versus etcd for distributed locks?"
    a: "Use Redis when you already run it for caching/queues, lock hold times are short (seconds), and you can tolerate rare edge cases with fencing tokens on downstream writes. Use etcd when correctness under partition matters more than raw latency—leader election for schedulers, workflow engines, and anything that must survive coordinated failover without double-execution."
  - q: "Is Redlock safe for agent job deduplication?"
    a: "Only if every side effect is guarded by a monotonic fencing token written to your database or object store. Redlock alone does not guarantee mutual exclusion across clock skew and GC pauses. Treat the lock as optimization; make job execution idempotent and store the fencing token with the lease record."
  - q: "What TTL should agent worker locks use?"
    a: "Set TTL to at least 3× your p99 heartbeat interval plus expected critical section duration. If work can exceed TTL, use lease renewal loops with jitter and abort work if renewal fails—never assume infinite extension. For LLM tool batches running 2–10 minutes, prefer workflow-level leases in etcd over Redis locks without renewal."
  - q: "How do you test distributed lock correctness before production?"
    a: "Run Jepsen-style partition tests: isolate lock holder from Redis/etcd majority, verify at most one writer receives a valid fencing token. Chaos-inject process pauses longer than TTL while holding lock—downstream must reject stale tokens. Measure double-execution rate in staging; anything above zero without idempotency is a release blocker."
---
Two agent scheduler pods both believed they held the lock for `reindex-tenant-4421`. Each spawned embedding jobs against the same document corpus; vector store size doubled, invoice line items duplicated, and neither pod crashed—so alerts stayed green until finance noticed. The team had copied a Redis `SET NX EX` snippet from a blog post without **fencing tokens**, without lease renewal, and without asking whether Redis or etcd matched their failure model. Distributed locks are not mutexes; they are probabilistic coordination primitives whose sharp edges only appear under partitions and long GC pauses.

## What agents need locks for

Typical agent platform lock scopes:

| Use case | Hold duration | Correctness bar | Store bias |
|----------|---------------|-----------------|------------|
| Cron leader election | Until pod healthy | High | etcd |
| Per-tenant ingestion | Minutes | High | etcd or Redis + fence |
| Tool rate budget | Sub-second | Medium | Redis |
| Singleton migration | Seconds–minutes | High | etcd |
| Deduplicate webhook | Seconds | Medium | Redis + idempotency key |

Locks coordinate **who may start** work; they do not replace idempotent execution. Always design so duplicate starters cause at worst duplicate effort detectable downstream, never duplicate spend.

## Redis: single-instance vs Redlock

Single Redis primary with `SET key token NX PX ttl` is fast and widely understood:

```python
import uuid
import redis

class RedisLock:
    def __init__(self, client: redis.Redis, key: str, ttl_ms: int):
        self.client = client
        self.key = key
        self.ttl_ms = ttl_ms
        self.token = uuid.uuid4().hex

    def acquire(self) -> bool:
        return bool(
            self.client.set(self.key, self.token, nx=True, px=self.ttl_ms)
        )

    def release(self) -> bool:
        # Lua: delete only if token matches
        script = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('del', KEYS[1])
        else
            return 0
        end
        """
        return bool(self.client.eval(script, 1, self.key, self.token))
```

If primary fails over asynchronously, two clients can both believe they hold the lock. Mitigate with **fencing tokens**: monotonic counters stored in your source of truth.

Redlock (multiple independent Redis nodes) reduces but does not eliminate split-brain risk under real-world clock skew. If you use it, keep quorum math explicit and still fence downstream writes.

## Fencing tokens: the non-optional half

Martin Kleppmann's critique of Redlock lands on one fix: the lock service must hand the winner a **fencing token** that storage layers enforce:

```sql
-- PostgreSQL: reject stale lock holders
CREATE TABLE agent_job_leases (
  job_id TEXT PRIMARY KEY,
  holder TEXT NOT NULL,
  fence BIGINT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL
);

-- Worker must pass fence on mutation
UPDATE agent_runs
SET status = 'running', lease_fence = $fence
WHERE job_id = $job_id
  AND (lease_fence IS NULL OR lease_fence < $fence);
```

Redis lock token UUIDs are not fencing tokens unless they monotonically increase per resource. Use a dedicated `INCR lock:fence:{job_id}` inside the acquire Lua script:

```lua
-- KEYS[1] = lock key, KEYS[2] = fence key
if redis.call('set', KEYS[1], ARGV[1], 'NX', 'PX', ARGV[2]) then
  local fence = redis.call('incr', KEYS[2])
  return fence
end
return 0
```

Return fence to Python; pass it on every DB write the lock protects.

## etcd: leases, sessions, and native correctness

etcd builds locks on **leases** with keep-alive streams—better fit for agent leaders and longer workflows:

```go
import (
  clientv3 "go.etcd.io/etcd/client/v3"
  concurrency "go.etcd.io/etcd/client/v3/concurrency"
)

func runAsLeader(cli *clientv3.Client, lockKey string, work func(ctx context.Context) error) error {
  session, err := concurrency.NewSession(cli, concurrency.WithTTL(15))
  if err != nil {
    return err
  }
  defer session.Close()

  mutex := concurrency.NewMutex(session, lockKey)
  ctx := context.Background()
  if err := mutex.Lock(ctx); err != nil {
    return err
  }
  defer mutex.Unlock(ctx)

  return work(ctx)
}
```

Session TTL defines survival without renewal; the etcd client renews automatically while the process runs. If the agent pod freezes longer than TTL, the lease expires and another pod can lead—exactly what you want if the frozen pod cannot make progress anyway.

For **compare-and-swap** style guards, use native transactions:

```go
txn := cli.Txn(ctx).
  If(clientv3.Compare(clientv3.CreateRevision(lockKey), "=", 0)).
  Then(clientv3.OpPut(lockKey, holderID, clientv3.WithLease(leaseID))).
  Else(clientv3.OpGet(lockKey))
resp, err := txn.Commit()
```

## Redis vs etcd decision matrix

| Dimension | Redis lock | etcd lock |
|-----------|------------|-----------|
| Latency | Sub-ms typical | Low ms, gRPC overhead |
| Durability | Memory-first; AOF helps | Raft persisted |
| Partition behavior | Risk of dual holders | Quorum-enforced single leader |
| Operational load | Often already present | Dedicated cluster care |
| Lease renewal | Manual heartbeats | Built into session |
| Watch notifications | Keyspace notifications (fragile) | Native watches for leader loss |

Choose etcd when the lock guards **financially meaningful** or **hard-to-rollback** agent side effects—billing aggregation, destructive migrations, global rate limiter configuration. Choose Redis for **best-effort deduplication** where duplicate work is cheap and idempotency keys catch stragglers.

## Agent orchestration patterns

**Leader election for schedulers** — One pod ticks cron; followers idle. On etcd watch firing `DELETE` for leader key, followers campaign. Expose `/healthz/leader` for load balancers that should not route user traffic to followers.

**Per-tenant serialization** — Prevent concurrent agent runs mutating the same tenant workspace:

```python
def tenant_lock_key(tenant_id: str) -> str:
    return f"agent:lock:tenant:{tenant_id}"

async def with_tenant_lock(redis, tenant_id: str, ttl_ms: int, coro):
    lock = RedisLock(redis, tenant_lock_key(tenant_id), ttl_ms)
    if not lock.acquire():
        raise TenantBusyError(tenant_id)
    try:
        fence = await get_fence(redis, tenant_id)  # from INCR
        return await coro(fence)
    finally:
        lock.release()
```

**Lock-free alternative** — For many agent workloads, **optimistic concurrency** with version columns outperforms distributed locks. Locks make sense when retry cost is high (LLM batch re-embed) or external APIs lack idempotency.

## TTL and renewal math

Define variables:

- `H` = heartbeat interval
- `T` = lock TTL
- `W` = worst-case work duration
- `G` = max GC/STW pause

Rule of thumb: `T >= 3*H + G` and renew at `H` with jitter. If `W > T`, you need renewal loops:

```python
async def renew_loop(redis, key: str, token: str, ttl_ms: int, stop: asyncio.Event):
    while not stop.is_set():
        await asyncio.sleep(ttl_ms / 3000)  # renew at ~1/3 TTL
        ok = await extend_if_owner(redis, key, token, ttl_ms)
        if not ok:
            raise LeaseLostError(key)
```

On `LeaseLostError`, abort agent work and mark job **retryable**—continuing without lock risks split brain.

## Observability and debugging

Emit metrics:

- `lock_acquire_success_total{backend="redis|etcd"}`
- `lock_acquire_contention_seconds` histogram
- `lock_lease_lost_total` — critical alert
- `fence_rejected_writes_total` — should be near zero; spikes mean TTL misconfiguration

Log structured fields: `lock_key`, `holder_id`, `fence`, `ttl_ms`, `backend`. During incidents, compare holder logs with etcd revision history or Redis `GET` values.

## Failure drills

Run quarterly:

1. **Pause holder** — `SIGSTOP` agent worker mid-job; verify lease expires and second worker completes with higher fence.
2. **Network partition** — Isolate holder from etcd quorum; verify no writes without valid fence after partition heals.
3. **Redis failover** — Trigger primary promotion; measure window of dual acquire; confirm fencing blocked duplicate DB writes.

Document observed double-execution rate. If non-zero, tighten idempotency before tightening locks.

## Anti-patterns

- **Long critical sections without renewal** — Embedding ten million chunks under one Redis `EX 30` lock.
- **Lock per message** — Kafka consumer locks each message; use partition assignment instead.
- **Ignoring clock skew** — Redlock with unsynchronized VMs and sub-second TTL.
- **No fence on object storage** — S3 overwrites from stale lock holder corrupt agent artifact directories.

## The takeaway

Redis and etcd both offer distributed locks for agent systems, but they fail differently. Redis wins on speed and simplicity when fencing tokens and idempotency backstop correctness. etcd wins when lease semantics and quorum matter for schedulers and irreversible workflows. Pick the store to match your failure model, then prove it with partition tests—not blog post confidence.

## FAQ

### When should agent orchestrators use Redis versus etcd for distributed locks?

Use Redis when you already run it for caching/queues, lock hold times are short (seconds), and you can tolerate rare edge cases with fencing tokens on downstream writes. Use etcd when correctness under partition matters more than raw latency—leader election for schedulers, workflow engines, and anything that must survive coordinated failover without double-execution.

### Is Redlock safe for agent job deduplication?

Only if every side effect is guarded by a monotonic fencing token written to your database or object store. Redlock alone does not guarantee mutual exclusion across clock skew and GC pauses. Treat the lock as optimization; make job execution idempotent and store the fencing token with the lease record.

### What TTL should agent worker locks use?

Set TTL to at least 3× your p99 heartbeat interval plus expected critical section duration. If work can exceed TTL, use lease renewal loops with jitter and abort work if renewal fails—never assume infinite extension. For LLM tool batches running 2–10 minutes, prefer workflow-level leases in etcd over Redis locks without renewal.

### How do you test distributed lock correctness before production?

Run Jepsen-style partition tests: isolate lock holder from Redis/etcd majority, verify at most one writer receives a valid fencing token. Chaos-inject process pauses longer than TTL while holding lock—downstream must reject stale tokens. Measure double-execution rate in staging; anything above zero without idempotency is a release blocker.

## Resources

- [martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html) — How to do distributed locking
- [etcd.io/docs/latest/learning/why/](https://etcd.io/docs/latest/learning/why/) — Why etcd
- [redis.io/docs/manual/patterns/distributed-locks/](https://redis.io/docs/manual/patterns/distributed-locks/) — Redis distributed locks documentation
- [jepsen.io/analyses](https://jepsen.io/analyses) — Jepsen consistency analyses
- [github.com/etcd-io/etcd/tree/main/client/v3/concurrency](https://github.com/etcd-io/etcd/tree/main/client/v3/concurrency) — etcd concurrency package
