---
title: "Leader Election Patterns"
slug: "distributed-leader-election-patterns"
description: "Leader election picks one coordinator among distributed nodes. Raft elections, ZooKeeper ephemeral nodes, Redis Redlock caveats, and Kubernetes lease patterns."
datePublished: "2025-10-18"
dateModified: "2025-10-18"
tags: ["Backend", "Databases", "Architecture"]
keywords: "leader election, distributed lock, Raft election, ZooKeeper, etcd lease, Redlock, singleton worker"
faq:
  - q: "Why do distributed systems need leader election?"
    a: "Leader election ensures exactly one node performs coordination tasks at a time — writing to shared storage, running cron jobs, assigning partitions, or accepting writes in primary-secondary architectures. Without election, split-brain duplicates work or corrupts shared state."
  - q: "How does leader election work in Kubernetes?"
    a: "Kubernetes uses Lease objects and controller-runtime leader election — candidates acquire a lease resource in etcd via coordination.k8s.io API. Holder runs controllers; others standby. etcd's Raft consensus backs lease atomicity. Built into operators and many controllers."
  - q: "Is Redis Redlock a safe leader election mechanism?"
    a: "Redlock for distributed locking remains debated — clock drift, long GC pauses, and asynchronous replication can violate safety assumptions Martin Kleppmann analyzed. For critical correctness, prefer consensus systems (etcd, ZooKeeper) or database advisory locks with fencing tokens."
---

Someone has to run the nightly aggregation job. In a single-server cron, that's trivial. With three app instances, without coordination you get triple billing reports and angry finance. Leader election picks **one** winner; the rest wait.

## Use cases

- **Singleton background worker** — invoice generation, cache warming
- **Primary writer** — accept writes, replicate to secondaries
- **Partition assignment** — Kafka consumer group coordinator (related concept)
- **Failover trigger** — promote database replica

Common requirement: **safety** (at most one leader) and **liveness** (eventually a leader).

## Raft built-in election

Embedded Raft (etcd, Consul) elects leader automatically for the replicated log — not just app-level singleton:

```
Follower timeout → Candidate → majority votes → Leader → heartbeats
```

Apps using etcd often **watch leader key** or use client library session — leader campaign via `concurrency.Election`:

```go
session, _ := concurrency.NewSession(client)
election := concurrency.NewElection(session, "/my-service/leader/")
election.Campaign(ctx, "node-1-id")
// hold leadership until session expires or resign
```

Session TTL — leader must heartbeat; crash → new election.

## ZooKeeper / Curator leader selector

Create **ephemeral sequential** znodes under `/election`:

```
/election/
  node_0000000001  ← smallest = leader
  node_0000000002
  node_0000000003
```

Ephemeral nodes delete when session dies — next smallest becomes leader. Curator `LeaderSelector` wraps pattern.

Classic, well-understood; ZK ensemble ops overhead.

## Kubernetes Lease API

```yaml
apiVersion: coordination.k8s.io/v1
kind: Lease
metadata:
  name: report-generator-leader
  namespace: prod
spec:
  holderIdentity: pod-abc123
  leaseDurationSeconds: 15
  renewTime: "2025-10-18T12:00:00Z"
```

Controller-runtime:

```go
leaderelection.RunOrDie(ctx, leaderelection.LeaderElectionConfig{
    Lock: lock,
    LeaseDuration: 15 * time.Second,
    RenewDeadline: 10 * time.Second,
    RetryPeriod: 2 * time.Second,
    Callbacks: leaderelection.LeaderCallbacks{
        OnStartedLeading: func(ctx context.Context) { runWorker(ctx) },
        OnStoppedLeading: func() { /* cleanup */ },
    },
})
```

Natural for operators; requires cluster — not bare-metal apps.

## Database advisory locks

Postgres:

```sql
SELECT pg_try_advisory_lock(hashtext('report_generator'));
-- run job
SELECT pg_advisory_unlock(hashtext('report_generator'));
```

Simple for low-frequency jobs co-located with DB. Failure to unlock on crash — lock held until session ends. Use session-level locks tied to connection pool carefully.

## Redis Redlock — caution

Redlock acquires lock on N independent Redis masters with TTL. Debate: process pause longer than TTL can duplicate leaders; async replication loses lock on failover.

Acceptable for **best-effort** deduplication; not for financial invariants without **fencing tokens** — storage rejects stale leader writes.

## Fencing tokens

Monotonic token from lock service; storage rejects writes with token older than last seen:

```
Lock grant → token=5 → write with token=5 OK
Stale leader → token=4 → storage rejects
```

Essential when lock TTL < max pause time.

## Split-brain prevention

Two leaders worse than none. Require:

- Majority quorum for election
- STONITH / fence old primary on DB failover
- Lease shorter than job duration with renew loop

Monitor `is_leader` metric — dual leader alert pages immediately.

## Graceful leadership transfer

On deploy, **resign** leadership before shutdown so standby starts job without waiting TTL:

```go
election.Resign(context.Background())
```

Avoids 15-second gap in cron during rolling update.

## Choosing a pattern

| Pattern | Fit |
|---|---|
| K8s Lease | Controllers in cluster |
| etcd election | Microservices already using etcd |
| ZK | Legacy Hadoop/Kafka ecosystems |
| Advisory lock | Simple cron, DB-centric |
| Raft embedded | Building replicated state machine |

Don't invent TTL locks in Redis without reading Kleppmann's analysis.

## Split-brain prevention

Leader election prevents split-brain — two nodes both believing they're leader:

```
Node A: acquires lease, becomes leader, processes jobs
Node B: lease expired (A crashed), acquires lease, becomes leader
Node A: recovers, tries to process jobs → must check lease before acting
```

Every leader action must verify lease ownership before executing:

```go
func (l *Leader) RunJob(ctx context.Context) error {
    if !l.election.IsLeader() {
        return ErrNotLeader
    }
    return l.job.Execute(ctx)
}
```

Without lease check on recovery, two leaders process the same job — duplicate emails, double charges, inconsistent state.

## Fencing tokens

For resources accessed by the leader (database writes, file locks), use fencing tokens:

```go
// Leader acquires lease with monotonically increasing token
token := election.Acquire()
// Write to shared resource includes token
db.Execute("UPDATE jobs SET status='running', fence_token=? WHERE id=? AND fence_token < ?",
    token, jobID, token)
// If old leader writes with stale token, update fails
```

Fencing token invalidates stale leader writes even if the old leader resumes after network partition heals.

## Leader election for cron jobs

Simple pattern for single-instance cron in a replicated deployment:

```python
import k8s_leader_election

def on_started_leading():
    scheduler.start()  # only leader runs cron

def on_stopped_leading():
    scheduler.shutdown()

leader_election.run(
    lock_name="cron-leader",
    on_started_leading=on_started_leading,
    on_stopped_leading=on_stopped_leading,
)
```

Non-leader replicas stay healthy (serve HTTP) but don't run scheduled jobs. On leader failure, standby acquires lease within TTL (typically 15s) and starts scheduler.

## Failure modes

- **TTL too short** — leader resigns during GC pause; unnecessary failover churn
- **TTL too long** — 60s gap with no leader after crash
- **No lease check before action** — recovered old leader processes duplicate jobs
- **Redis Redlock without fencing** — split-brain under clock skew (see Kleppmann)
- **No graceful resign on shutdown** — full TTL wait before standby takes over

## Production checklist

- Leader verifies lease before every mutating action
- Fencing tokens on shared resource writes
- Graceful resign on pod shutdown (preStop hook)
- TTL tuned: long enough for GC pauses, short enough for acceptable failover gap
- Avoid Redis Redlock for correctness-critical paths without fencing
- Monitor leader election metrics (lease acquisitions, resigns, failures)

## Common production mistakes

Teams get distributed leader election patterns wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of distributed leader election patterns fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [etcd concurrency election package](https://pkg.go.dev/go.etcd.io/etcd/client/v3/concurrency#Election)
- [Kubernetes leader election guide](https://pkg.go.dev/sigs.k8s.io/controller-runtime/pkg/leader-election)
- [Martin Kleppmann — How to do distributed locking](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html)
- [Apache Curator LeaderSelector](https://curator.apache.org/docs/recipes-leader-election/)
- [Redis Redlock documentation](https://redis.io/docs/manual/patterns/distributed-locks/)
