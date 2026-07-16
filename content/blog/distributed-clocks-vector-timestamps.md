---
title: "Vector Clocks and Causality"
slug: "distributed-clocks-vector-timestamps"
description: "Wall clocks lie in distributed systems. Vector clocks track causal order across nodes for conflict detection and eventual consistency debugging."
datePublished: "2025-10-06"
dateModified: "2025-10-06"
tags: ["Backend", "Databases", "Architecture"]
keywords: "vector clocks, logical clocks, Lamport timestamps, causal consistency, conflict resolution, Dynamo clocks"
faq:
  - q: "What is a vector clock?"
    a: "A vector clock is an array of counters, one per node in the system, included with each message or write. When a node sends or records an event, it increments its own counter. Comparing vectors determines whether events are causally ordered, concurrent, or equal — enabling detection of conflicts in replicated data."
  - q: "How are vector clocks different from Lamport timestamps?"
    a: "Lamport timestamps give a total order consistent with causality but cannot detect concurrent events — different timestamps might still be unrelated. Vector clocks distinguish concurrency: if neither vector is less than the other, events happened in parallel and may conflict."
  - q: "Where are vector clocks used in production?"
    a: "Dynamo-family systems (Riak, early Cassandra versions), CRDT replication metadata, distributed debugging, and version vectors in Riak. Many modern systems use simplified version vectors or hybrid logical clocks (HLC) combining physical and logical time for smaller metadata."
---

When Node A and Node B both update the same shopping cart offline, "last write wins" by wall clock is how you lose items — laptop clocks skew by minutes. Vector clocks don't fix conflicts automatically; they tell you **whether two writes were concurrent** so your merge logic can run instead of guessing.

## Why wall time fails

NTP skew, leap seconds, manual clock adjustment — `timestamp` ordering is not causal ordering. Event B responding to Event A must sort after A regardless of clock drift.

**Causal order:** if A → B (A happened-before B), all nodes should agree B is later. Concurrent events have no happened-before relationship.

## Lamport timestamps (stepping stone)

Each node maintains counter L:

- Local event: L++
- Send message: attach L
- Receive message: L = max(L, message_L) + 1

If L(A) < L(B), A might have caused B — but not guaranteed (concurrent events can get arbitrary order).

## Vector clocks

Vector V with one slot per node `{A:1, B:3, C:2}`.

Rules:

- **Local event** at node i: V[i]++
- **Send**: attach V after increment
- **Receive** from j: V[i] = max(V[i], V_msg[i]) + 1; V[k] = max(V[k], V_msg[k]) for k ≠ i

Compare vectors:

- V dominates W (V > W) if all V[k] ≥ W[k] and at least one strict — V happened-after W
- Neither dominates → **concurrent** — potential conflict

```
Write1: {A:1, B:0}  at A
Write2: {A:1, B:1}  at B  — concurrent with Write1 if no message path
```

## Worked example: cart conflict

1. Client on A sets cart to `[book]` → V={A:1,B:0}
2. Client on B adds `[pen]` concurrently → V={A:0,B:1}
3. Replica merges both — neither dominates → **sibling conflict**
4. Application merge: union items or prompt user

Without vector detection, LWW silently drops `[book]` or `[pen]`.

## Version vectors vs vector clocks

**Version vector** — same structure, tracks data object versions per replica, not global events. Used in Riak `vclock` metadata on objects.

Storage overhead O(nodes) — problematic at thousands of nodes. **Dotted version vectors** and **hybrid logical clocks (HLC)** compress metadata using physical time + logical counter:

```
HLC = (physical_time, logical_counter, node_id)
```

CockroachDB and Cassandra use HLC-style timestamps for ordering with less state.

## CRDTs and causality

Conflict-free replicated data types embed causality in merge semantics — G-Counter, OR-Set use dotted vectors internally. Vector clocks identify when custom merge needed for non-CRDT data.

## Implementation sketch

```python
def increment(vec, node_id, index):
    vec = vec.copy()
    vec[index] += 1
    return vec

def merge_on_receive(local, remote, node_id, index):
    merged = [max(a, b) for a, b in zip(local, remote)]
    merged[index] += 1
    return merged

def concurrent(v1, v2):
    return not dominates(v1, v2) and not dominates(v2, v1) and v1 != v2
```

Persist vector with each object version in KV store.

## Operational use

- Debug "why did my write disappear" — compare vclocks in Riak
- Sync engines detecting edit conflicts (Git, CouchDB MVCC + revision trees related)
- Choosing merge vs reject in collaborative editing

Not every system exposes vectors to app layer — know what's under hood when picking DB.

## Limits

Vector size grows with replica count — shard clocks or use HLC. Doesn't resolve conflicts — only classifies them. Human or domain merge still required.

Global strong consistency (Spanner) sidesteps app-level vectors by serializing writes — different cost model.

## Hybrid Logical Clocks (HLC)

HLC combines physical time with logical counter — no central clock required:

```python
import time

class HybridLogicalClock:
    def __init__(self):
        self.pt = 0  # physical time component
        self.lc = 0  # logical counter

    def now(self) -> tuple:
        physical = int(time.time() * 1_000_000)  # microseconds
        if physical > self.pt:
            self.pt = physical
            self.lc = 0
        else:
            self.lc += 1
        return (self.pt, self.lc)

    def update(self, remote: tuple) -> tuple:
        physical = int(time.time() * 1_000_000)
        self.pt = max(physical, self.pt, remote[0])
        if self.pt == remote[0]:
            self.lc = max(self.lc, remote[1]) + 1
        elif self.pt == physical:
            self.lc += 1
        else:
            self.lc = 0
        return (self.pt, self.lc)
```

HLC timestamps are compact (8 bytes), sortable, and preserve causality. Used in CockroachDB and MongoDB internally.

## Conflict resolution strategies

Vector clocks detect conflicts — resolving them requires domain logic:

```python
def resolve_shopping_cart(local_cart, remote_cart, local_vclock, remote_vclock):
    if dominates(local_vclock, remote_vclock):
        return local_cart  # local is newer, keep it
    if dominates(remote_vclock, local_vclock):
        return remote_cart  # remote is newer
    # Concurrent edit — merge
    merged_items = merge_items(local_cart.items, remote_cart.items)
    return Cart(items=merged_items, vclock=merge_vclock(local_vclock, remote_vclock))
```

| Strategy | Use when |
|---|---|
| Last-write-wins | Stale data acceptable |
| Merge (CRDT) | Commutative operations (sets, counters) |
| Application merge | Domain-specific logic (shopping cart) |
| Human resolution | High-value conflicts (document editing) |

## Dynamo-style version vectors in practice

Amazon Dynamo uses vector clocks for conflict detection at scale:

```
Write: increment node's counter in vector
Read: return all conflicting versions if concurrent writes detected
Resolve: application merges or chooses version
```

Riak exposes this explicitly — `allow_mult=true` returns all concurrent values on read, application resolves. Cassandra uses last-write-wins by default — simpler but loses concurrent writes silently.

## Failure modes

- **Vector size grows with replica count** — use HLC for compact timestamps
- **LWW without vector clock** — concurrent writes silently lost
- **No merge strategy defined** — conflicts detected but unresolved
- **Clock skew in pure Lamport clocks** — HLC handles this better
- **Vector not persisted with object** — can't detect conflicts on read

## Production checklist

- Conflict detection mechanism chosen (vector clock, HLC, or MVCC)
- Merge strategy defined per data type (LWW, CRDT, application merge)
- Concurrent write conflicts surfaced to application, not silently dropped
- HLC used when compact sortable timestamps needed
- Vector clock or HLC persisted with each object version
- Conflict rate monitored — high rate indicates design problem

## Resources

- [Lamport — Time, Clocks, and the Ordering of Events (1978)](https://lamport.azurewebsites.net/pubs/time-clocks.pdf)
- [Fidge-Mattern vector clocks](https://www.cs.rug.nl/~volkov/vector_clocks.pdf)
- [Hybrid Logical Clocks paper (Kulkarni et al.)](https://cse.buffalo.edu/tech-reports/2014-04.pdf)
- [Riak — Version vectors and conflict resolution](https://docs.riak.com/riak/kv/2.2.3/developing/use/conflict-resolution/index.html)
- [Dynamo paper — Section on versioning](https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf)
