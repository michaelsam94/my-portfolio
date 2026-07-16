---
title: "Working with Eventual Consistency"
slug: "distributed-eventual-consistency-patterns"
description: "Eventual consistency trades immediate uniformity for availability and latency. Read repair, CRDTs, sagas, and UX patterns that make stale state livable."
datePublished: "2025-10-15"
dateModified: "2025-10-15"
tags: ["Backend", "Databases", "Architecture"]
keywords: "eventual consistency, read repair, CRDT, conflict resolution, stale reads, Dynamo patterns, AP systems"
faq:
  - q: "What does eventual consistency mean?"
    a: "Eventual consistency guarantees that if no new updates occur, all replicas will converge to the same value given enough time. During convergence, reads may return stale or conflicting versions. Common in geographically distributed AP systems prioritizing availability over immediate strong consistency."
  - q: "How do I build applications on eventually consistent storage?"
    a: "Design for idempotent writes, version vectors or timestamps for conflict detection, user-facing tolerance for brief staleness, read-your-writes routing where needed, and compensating actions for cross-entity invariants. Never assume read-after-write on arbitrary replicas without coordination."
  - q: "What are CRDTs and when should I use them?"
    a: "Conflict-free Replicated Data Types are data structures with merge functions guaranteeing convergence without coordination — counters, sets, registers. Use when concurrent edits to shared state are common and custom merge logic is error-prone — collaborative editing, session carts, presence indicators."
---

Strong consistency is comfortable — read what you just wrote, every time. Most globally distributed systems can't afford the latency, so they ship **eventual consistency** and leave application teams to paper over the gaps. That works when you treat staleness as a design input, not a bug to hide.

## What eventual really promises

After writes stop, replicas **converge**. No promise about **when** or what reads return **during** convergence.

```
t=0: write v2 to Node A
t=1: read from Node B → v1 (stale)
t=5: gossip/replication completes
t=6: read from Node B → v2
```

Users at t=1 see wrong state — product must tolerate or route reads carefully.

## Patterns for tolerable UX

**Read-your-writes** — session sticks to node that took write or waits for replication ack before read.

**Monotonic reads** — user doesn't see time go backward (v2 then v1). Sticky replica or version tokens.

**Causal consistency** — related operations respect cause-effect without full strong consistency (vector clocks, session guarantees).

Communicate uncertainty: "Syncing..." beats silent wrong totals.

## Conflict detection and resolution

Concurrent writes produce siblings:

| Strategy | When |
|---|---|
| Last-write-wins (LWW) | Low stakes, clock sync OK |
| Application merge | Shopping cart union |
| CRDT merge | Counters, sets |
| Human resolution | Legal documents |

```javascript
// LWW with client timestamps — know the risks
function resolve(a, b) {
  return a.timestamp > b.timestamp ? a : b;
}
```

LWW loses data silently — document when acceptable.

## Read repair

On read, if replicas disagree, coordinator or client writes latest version to stale nodes:

```python
def read_with_repair(key, quorum_nodes):
    responses = [node.get(key) for node in quorum_nodes]
    versions = merge_responses(responses)
    latest = max(versions, key=lambda v: v.vector_clock)
    for node, v in zip(quorum_nodes, responses):
        if v != latest:
            node.put(key, latest)  # repair
    return latest
```

Dynamo popularized read repair; adds read latency; keeps entropy from spreading.

## Write path: quorum (W, R)

Choose W replicas acknowledge write, R for read, N total replicas. **R + W > N** gives strong read consistency for that operation without full sync on every write — tunable middle ground.

Cassandra `QUORUM` reads/writes — not fully eventual if configured strictly.

## CRDTs for convergent state

**G-Counter** — grow-only counter per node, sum on merge.

**OR-Set** — add/remove set converges without lost adds.

```javascript
// OR-Set add wins over remove after merge semantics
// Libraries: automerge, yjs for collaborative docs
```

Use when merge semantics are mathematical, not business-policy.

## Sagas for cross-service invariants

Eventual consistency across services — no distributed transaction. **Saga** compensates:

1. Reserve inventory (eventual)
2. Charge payment
3. If charge fails → publish CancelReservation

Each step idempotent; consumers tolerate duplicate events.

## Caching layers amplify staleness

CDN + app cache + replica DB = multi-layer eventual. TTL and cache invalidation on write reduce but don't eliminate lag. **Cache-aside** with version keys detects stale cache entries.

## Testing eventually consistent systems

- Jepsen-style partition tests
- Property tests: merge(merge(a,b), c) == merge(a, merge(b,c))
- Chaos: kill replica mid-write, verify convergence
- User journey tests with forced read from lagging replica

## When to escape eventual

Financial balances, inventory that can't oversell, uniqueness constraints — route to strongly consistent store or shard lock for those operations only. Hybrid beats pure AP dogma.

## Read-your-writes consistency

Users expect to see their own writes immediately — even in eventually consistent systems:

```python
# After write, read from primary (not replica)
def create_order(user_id, items):
    order = db_primary.insert(order)
    cache.set(f"user:{user_id}:latest_order", order.id, ttl=60)
    return order

def get_orders(user_id):
    # Read from replica for list, but check cache for recent writes
    recent = cache.get(f"user:{user_id}:latest_order")
    orders = db_replica.query(user_id)
    if recent and recent not in [o.id for o in orders]:
        orders.insert(0, db_primary.get(recent))
    return orders
```

Route user's own reads to primary or use a short-lived cache of recent writes. Other users' reads can tolerate replica lag.

## Conflict resolution strategies

When concurrent writes converge, choose a resolution strategy explicitly:

| Strategy | Use when | Example |
|---|---|---|
| Last-write-wins (LWW) | Stale data acceptable | User profile nickname |
| Version vectors | Need causal ordering | Collaborative editing |
| CRDT merge | Commutative operations | Shopping cart add/remove |
| Application merge | Domain-specific logic | Wiki page edit conflict UI |
| Strong consistency | Can't lose data | Bank balance |

Document the strategy per entity — don't default everything to LWW.

## CAP theorem in practice

CAP is misunderstood as a binary choice. In practice:

- **Network partitions are rare** — optimize for normal case (low latency, high availability)
- **Consistency is a spectrum** — not just strong vs eventual
- **Most systems are CP or AP per operation** — not globally

```
User profile read  → AP (replica, stale OK for 30s)
Payment capture    → CP (primary, strong consistency)
Search index       → AP (eventual, rebuilt from events)
Inventory count    → CP (pessimistic lock on hot SKU)
```

Design per-operation consistency, not per-system.

## Failure modes

- **Assuming eventual means instant** — replica lag of 30s surprises users who just wrote data
- **LWW on financial data** — concurrent writes lose money
- **No conflict detection** — silent data loss instead of conflict UI
- **Cache without invalidation** — stale cache serves old data after write
- **Saga without compensation** — partial failure leaves inconsistent state

## Production checklist

- Read-your-writes guaranteed for user's own data
- Conflict resolution strategy documented per entity
- Replica lag monitored and alerted (>5s threshold)
- Saga compensations tested for every failure path
- Strong consistency for financial/inventory hot paths
- Jepsen-style partition tests for critical paths

## Resources

- [Dynamo paper](https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf)
- [CRDTs — Shapiro et al. comprehensive survey](https://crdt.tech/papers/shapiro-corrected.pdf)
- [Jepsen consistency analyses](https://jepsen.io/)
- [AWS — Eventually consistent data stores](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadConsistency.html)
- [Martin Kleppmann — Designing Data-Intensive Applications](https://dataintensive.net/)
