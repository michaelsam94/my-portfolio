---
title: "Beyond CAP: The PACELC Theorem"
slug: "distributed-cap-theorem-pacelc"
description: "CAP picks consistency or availability during partitions. PACELC extends the tradeoff to normal operation — latency vs consistency when the network is fine."
datePublished: "2025-10-03"
dateModified: "2025-10-03"
tags: ["Backend", "Databases", "Architecture"]
keywords: "PACELC theorem, CAP theorem, consistency availability, distributed systems tradeoffs, eventual consistency, Dynamo"
faq:
  - q: "What is the PACELC theorem?"
    a: "PACELC extends CAP: if there is a Partition (P), choose Availability (A) or Consistency (C); Else (E), even when the network is normal, choose Latency (L) or Consistency (C). Most real-world tradeoffs happen in the EL branch — Dynamo-style systems sacrifice consistency for low latency during normal operation."
  - q: "How is PACELC different from CAP?"
    a: "CAP only addresses behavior during network partitions. PACELC acknowledges that when partitions aren't happening, systems still trade consistency for latency — async replication gives fast writes but stale reads. CAP alone misleads teams into thinking consistency vs availability only matters during rare partition events."
  - q: "Which databases are PA/EL vs PC/EC?"
    a: "PA/EL: Dynamo, Cassandra, Riak — available during partition, low-latency eventually consistent normally. PC/EC: traditional RDBMS with sync replication — consistent but higher latency. Many modern systems offer tunable levels — MongoDB read concerns, Cassandra LOCAL_QUORUM."
---

CAP theorem conversations stall at "pick two of consistency, availability, partition tolerance." That's technically true and practically incomplete — partitions are rare; **every day** your system chooses between low latency and strong consistency on the happy path. PACELC names that everyday tradeoff.

## CAP recap (briefly)

During a **network partition**, distributed nodes can't talk. You must choose:

- **CP** — refuse writes/reads that can't be verified consistent (may be unavailable)
- **AP** — accept requests, risk inconsistent views until healed

Partition tolerance (P) isn't optional in distributed systems — networks fail. The real choice is C vs A **during partition**.

## PACELC fills the gap

Abadi's formulation:

> **If P** → choose **A** or **C**
> **Else (E)** → choose **L** (latency) or **C**

Normal operation (no partition): do you wait for cross-replica agreement (consistent, slower) or return after local write (fast, possibly stale)?

```
         Partition?
        /          \
      Yes           No (Else)
      /              \
  A or C          L or C
```

## PA/EL systems in the wild

Amazon Dynamo and descendants (Cassandra, Vortex-style KV stores):

- **PA** — during partition, stay available, reconcile later
- **EL** — normally, replicate async for low write latency; reads may lag

```python
# Cassandra-style write: ack after local replica
session.execute(
    "INSERT INTO cart ...",
    consistency_level=ConsistencyLevel.ONE  # fast, EL side
)
```

Stronger reads:

```python
session.execute(
    "SELECT * FROM cart WHERE user_id = ?",
    consistency_level=ConsistencyLevel.QUORUM  # moves toward EC
)
```

Tunable — not binary.

## PC/EC systems

Traditional RDBMS with synchronous replication:

- **PC** — during partition, primary may block promotions or refuse writes
- **EC** — normally wait for sync replica ack before commit — higher latency, strong consistency

Spanner/CockroachDB add synchronized clocks for global consistency at latency cost — different axis (TrueTime) but still paying for C.

## Why this matters for design reviews

Teams say "we're AP because we use Cassandra" then wonder why checkout reads stale inventory. They're **EL** on normal path — by design. Fix is tunable consistency on critical reads (QUORUM, SERIAL), not surprise.

Conversely, teams on Postgres primary-replica say "we're consistent" while reads hit 5-second-lag replica — that's **EL** behavior without admitting it.

Map each operation to required C vs L:

| Operation | Typical choice |
|---|---|
| Add to cart display | L — stale OK briefly |
| Payment capture | C — quorum or primary |
| Social feed | L |
| Inventory deduct | C or transactional lock |

## PACELC and microservices

Each service may sit different quadrant. Platform standardizing "everything eventual" breaks payment flows. Document per-endpoint guarantees in API contracts — not blanket AP label.

Saga patterns accept EL across services; 2PC pushes EC at latency cost.

## Latency numbers ground the tradeoff

Cross-region round trip ~50–150ms. Sync cross-region commit per write adds that to user-facing latency. EL async replication returns in local RTT. Product chooses whether user waits.

## Beyond the theorems

PACELC doesn't prescribe answers — it vocabulary for discussions auditors and PMs understand. Pair with explicit SLAs: "inventory reads RPO 0, max staleness 500ms."

Jepsen tests reveal whether system's claimed PC/EC holds under partition — marketing ≠ behavior.

## Mapping databases to PACELC quadrants

| System | Partition (P→) | Normal (E→) | Notes |
|---|---|---|---|
| Cassandra | A (stay up) | L (ONE writes) | Tunable per query |
| MongoDB | A | L (default) | Read/write concerns adjust |
| Postgres async replica | A (split brain risk) | L (replica lag) | Often mislabeled "consistent" |
| Postgres sync replica | C (blocks on lag) | C (sync commit) | Higher write latency |
| Spanner | C | C (TrueTime) | Global consistency at latency cost |
| DynamoDB | A | L (eventual default) | Strongly consistent reads optional |
| Redis Cluster | A | L | No cross-key transactions by default |
| etcd/Consul | C | C | CP for coordination services |

No system is purely one quadrant — most offer tunable knobs. The question is the default and what your code path actually uses.

## Designing for explicit consistency tiers

Document consistency requirements per operation in your API spec:

```yaml
operations:
  add_to_cart:
    consistency: eventual
    max_staleness_ms: 2000
    rationale: brief cart mismatch acceptable

  checkout_payment:
    consistency: strong
    mechanism: primary-only read + serializable transaction
    rationale: money movement

  product_catalog_browse:
    consistency: eventual
    max_staleness_ms: 300000  # 5 min CDN cache OK
```

This prevents engineers from accidentally routing payment reads to a lagging replica because "we use Postgres which is consistent."

## PACELC in microservice sagas

Cross-service workflows inherit the weakest consistency link:

```
Order service (EL) → Payment service (EC) → Inventory (EL)
```

The saga accepts EL across services but requires EC at payment capture. Design compensations assuming inventory read may be stale — verify with version numbers or reservation locks, not blind deduct.

## Failure modes

- **Labeling system "CP" while reads hit async replica** — EL behavior with CP expectations
- **Using ONE consistency for financial reads** — stale balance displays
- **Ignoring EL during normal operation** — blaming CAP during rare partitions when daily staleness is the real issue
- **No per-operation consistency spec** — engineers guess wrong defaults
- **Cross-region sync commit without latency budget** — user-facing writes take 150ms+ RTT

## Production checklist

- Each read/write path mapped to C vs L requirement
- Default consistency level documented per database
- Replica reads gated by staleness budget per operation
- Critical paths (payment, inventory deduct) use strong consistency
- Monitoring on replica lag with alerts tied to read routing
- PACELC quadrant documented in architecture decision records

## Real-world PACELC examples

| System | Partition behavior | Normal behavior | Rationale |
|---|---|---|---|
| Cassandra | AP (always writable) | PC (low latency reads) | Write availability critical |
| MongoDB default | CP (primary election) | PC (single-node reads) | Consistency on writes |
| CockroachDB | CP (Raft quorum) | PC (local reads) | Strong consistency default |
| DynamoDB | AP (eventual) | PC (single-region) | Configurable per operation |
| Spanner | CP (TrueTime) | LC (global commit latency) | Global consistency |

Document your system's PACELC quadrant in the architecture decision record — not just "we use Cassandra."

## Latency vs consistency tradeoff in practice

Normal-operation latency/consistency tradeoff (the LC in PACELC) affects every read:

```python
# DynamoDB: choose consistency per read
response = dynamodb.get_item(
    TableName="users",
    Key={"user_id": {"S": user_id}},
    ConsistentRead=True,   # LC: higher latency, fresh data
    # ConsistentRead=False  # PC: lower latency, stale up to 1s
)

# Route based on operation type
def get_user(user_id, own_data=False):
    return dynamodb.get_item(
        Key={"user_id": user_id},
        ConsistentRead=own_data,  # strong for own data, eventual for others
    )
```

Same database, different consistency per operation — PACELC in action.

## When to choose each quadrant

**PA (Partition + Availability):** Social feeds, analytics counters, non-critical metadata. Accept stale reads during partition.

**PC (Partition + Consistency):** Financial transactions, inventory deduction. Refuse writes during partition rather than accept divergence.

**LA (Latency + Availability):** Real-time dashboards, recommendation scores. Stale data acceptable for speed.

**LC (Latency + Consistency):** Cross-region user sessions, global config. Pay latency for consistency even in normal operation.

## Resources

- [Daniel Abadi — PACELC post](https://dbmsmusings.blogspot.com/2010/04/problems-with-cap-and-yahoos-little.html)
- [Brewer's CAP FAQ](https://www.infoq.com/articles/cap-twelve-years-later-how-the-rules-have-changed/)
- [Designing Data-Intensive Applications — consistency chapter](https://dataintensive.net/)
- [Jepsen consistency analyses](https://jepsen.io/analyses)
- [Amazon Dynamo paper (2007)](https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf)
