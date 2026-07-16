---
title: "Distributed Locks with Redis"
slug: "redis-distributed-locks-redlock"
description: "Implement distributed locks with Redis: SET NX patterns, Redlock algorithm, fencing tokens, and pitfalls that cause split-brain lock failures."
datePublished: "2026-01-16"
dateModified: "2026-01-16"
tags: ["Backend", "Redis", "Distributed Systems", "Locks"]
keywords: "Redis distributed locks, Redlock, SET NX EX, fencing tokens, distributed mutex, Redis lock pitfalls"
faq:
  - q: "How do I implement a basic Redis distributed lock?"
    a: "Use SET with NX (set if not exists) and EX (expiry) options: SET lock:resource unique_token NX EX 30. Only one client acquires the lock. Release with a Lua script that checks the token before deleting — never DEL unconditionally, or you may delete another client's lock after yours expired. The token must be unique per acquisition attempt."
  - q: "What is the Redlock algorithm?"
    a: "Redlock acquires locks on N independent Redis instances (typically 5) with a quorum requirement — a majority must agree the lock was acquired. It adds clock-drift-aware validity calculations and retry with jitter. Redlock targets higher reliability than single-instance locks but is debated — Martin Kleppmann's analysis argues it can fail under certain clock and network assumptions."
  - q: "What are fencing tokens and why do I need them?"
    a: "A fencing token is a monotonically increasing number included with every request to the protected resource. Even if a stale lock holder believes it still holds the lock, the resource rejects requests with outdated tokens. This prevents the scenario where Lock A expires, Lock B acquires, and then A's delayed operation corrupts data B is processing."
---

Two cron instances ran the same nightly billing job because both acquired a "lock" using GET-then-SET — a race window of milliseconds that both instances won during a network blip. The invoices were duplicated. A correct Redis distributed lock uses atomic SET NX with expiry and a unique token verified on release. Even then, without fencing tokens, an expired lock holder can still corrupt data. Distributed locks are harder than they look.

## Single-instance lock with SET NX

The minimum correct implementation:

```python
import uuid
import redis

r = redis.Redis(host="redis.internal")
LOCK_TTL = 30  # seconds

def acquire_lock(resource: str) -> str | None:
    token = str(uuid.uuid4())
    acquired = r.set(
        f"lock:{resource}", token,
        nx=True,   # only if key does not exist
        ex=LOCK_TTL,  # auto-expire
    )
    return token if acquired else None

RELEASE_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""

def release_lock(resource: str, token: str) -> bool:
    result = r.eval(RELEASE_SCRIPT, 1, f"lock:{resource}", token)
    return result == 1
```

**Why the Lua script:** Between your GET (checking the token) and DEL (deleting the key), the lock can expire and another client can acquire it. The Lua script executes atomically — check and delete in one operation.

**Why a unique token:** If you DEL without checking, you might delete another client's lock:

```
1. Client A acquires lock
2. Lock expires (A was slow)
3. Client B acquires lock
4. Client A finishes, DEL the key — deletes B's lock
5. Client C acquires lock — now B and C both think they hold it
```

## Lock usage pattern

```python
def run_billing_job():
    token = acquire_lock("billing:nightly")
    if token is None:
        logger.info("Another instance is running billing")
        return

    try:
        process_billing()
    finally:
        release_lock("billing:nightly", token)
```

Always release in `finally`. Set TTL long enough for the job but short enough to recover from crashed holders.

## Lock renewal for long-running jobs

If the job exceeds LOCK_TTL, extend the lock:

```python
RENEW_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("expire", KEYS[1], ARGV[2])
else
    return 0
end
"""

def renew_lock(resource: str, token: str, ttl: int = 30) -> bool:
    return r.eval(RENEW_SCRIPT, 1, f"lock:{resource}", token, ttl) == 1

# Background renewal thread
def hold_lock(resource, token, ttl):
    while job_running:
        time.sleep(ttl / 3)
        if not renew_lock(resource, token, ttl):
            raise LockLostError("Lock expired or stolen")
```

Renew at one-third TTL intervals. If renewal fails, stop the job — you no longer hold the lock.

## Redlock for multi-instance

For higher reliability across independent Redis nodes:

```python
from redlock import Redlock

dlm = Redlock([
    {"host": "redis1.internal"},
    {"host": "redis2.internal"},
    {"host": "redis3.internal"},
    {"host": "redis4.internal"},
    {"host": "redis5.internal"},
])

lock = dlm.lock("billing:nightly", 30000)  # 30s TTL in ms
if lock:
    try:
        process_billing()
    finally:
        dlm.unlock(lock)
```

Redlock requires a quorum (N/2 + 1) of instances to confirm acquisition. It handles individual node failures but not all failure modes — see the debate below.

## Fencing tokens

The subtle failure mode single-instance and Redlock locks share:

```
1. Client A acquires lock, starts slow operation
2. Lock expires
3. Client B acquires lock, starts operation
4. Client A's operation completes, writes to storage
5. Client B's operation completes, overwrites A's stale write
```

Fencing tokens prevent step 4:

```python
# Lock server provides monotonically increasing token
token, fence_id = acquire_lock_with_fence("resource")

# Storage rejects requests with outdated fence IDs
storage.write(data, min_fence_id=fence_id)
```

The storage layer (database, file system, API) must validate fencing tokens. A lock alone does not protect the resource — the resource must reject stale writers.

## When NOT to use distributed locks

Locks add complexity and failure modes. Alternatives:

- **Database unique constraints** — `INSERT ... ON CONFLICT` for idempotent job claiming.
- **Message queue consumer groups** — Redis Streams, SQS, Kafka partition assignment.
- **Leader election** — Kubernetes lease, etcd, ZooKeeper for coarse-grained coordination.
- **Idempotent operations** — design the job so running twice is safe.

```sql
-- Database-based job claiming (no lock needed)
INSERT INTO job_claims (job_name, instance_id, claimed_at)
VALUES ('billing', 'instance-2', NOW())
ON CONFLICT (job_name) DO NOTHING
RETURNING *;
```

If the INSERT returns a row, you claimed the job. If not, another instance has it.

## The Redlock debate

Martin Kleppmann argued Redlock can fail when:
- Clock skew causes premature lock expiry.
- GC pauses delay lock renewal beyond TTL.
- Network partitions isolate lock holders from lock stores.

Salvatore Sanfilippo (Redis creator) defended Redlock with clock drift margins and retry logic. Practical takeaway: Redlock is better than a single instance for many scenarios, but neither replaces fencing tokens for protecting shared resources.

## Common production mistakes

Teams get distributed locks redlock wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Redis usage for distributed locks redlock loses data when persistence mode is misunderstood, hot keys saturate single shards, and TTL strategy is applied after memory pressure already triggered evictions.

## Debugging and triage workflow

When distributed locks redlock misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Redis distributed locks documentation](https://redis.io/docs/latest/develop/use/patterns/distributed-locks/)
- [Redlock algorithm specification](https://redis.io/docs/latest/develop/use/patterns/fault-tolerance/)
- [Martin Kleppmann — How to do distributed locking](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html)
- [Redis antirez Redlock response](http://antirez.com/news/101)
- [python-redlock library](https://github.com/SPSCommerce/redlock-py)
