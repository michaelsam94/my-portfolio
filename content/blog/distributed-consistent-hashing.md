---
title: "Consistent Hashing for Sharding"
slug: "distributed-consistent-hashing"
description: "Consistent hashing minimizes key movement when shards are added or removed. Virtual nodes, ring topology, and application to caches and databases."
datePublished: "2025-10-12"
dateModified: "2025-10-12"
tags: ["Backend", "Databases", "Architecture"]
keywords: "consistent hashing, hash ring, virtual nodes, sharding, memcached, distributed cache, ketama"
faq:
  - q: "What is consistent hashing?"
    a: "Consistent hashing maps keys and nodes to a fixed ring using a hash function. Each key belongs to the first node clockwise from its hash position. When nodes join or leave, only keys adjacent to that node on the ring move — unlike modulo hashing where most keys remap."
  - q: "What are virtual nodes in consistent hashing?"
    a: "Virtual nodes (vnodes) place multiple hash points per physical node on the ring, improving load balance when node counts are small. A server might own 100 virtual positions, receiving roughly 1/N of keys with smoother distribution than single-point placement."
  - q: "Where is consistent hashing used?"
    a: "Distributed caches (Memcached clients, Redis Cluster slots), CDNs, Dynamo-style databases, load balancers, and P2P systems. Any system sharding by key that needs elasticity — adding capacity without full reshuffle."
---

Modulo sharding `hash(key) % N` is simple until N changes from 8 to 9 — nearly every key moves, invalidating caches and triggering mass data migration. Consistent hashing limits movement to keys near the changed node on the ring. That's why Memcached clients and Dynamo adopted it.

## The ring

Hash space 0 to 2^32-1 (or SHA space) forms a **ring**:

```
         Node A
           |
    key K -+- Node B
           |
         Node C
```

Hash key and nodes to positions. Key owns to **first node ≥ key hash** (clockwise), wrapping around.

Add node D between B and C — only keys between B and D (formerly on C) move to D. Other keys untouched.

Remove node — its keys transfer to next clockwise node only.

## Modulo vs consistent

| hash(key) % N | Consistent hash |
|---|---|
| N change → ~all keys move | N change → ~1/N keys move |
| Simple | Ring + vnode complexity |
| OK fixed shard count | Elastic clusters |

## Virtual nodes

Three physical nodes with one ring point each — uneven if hashes cluster. **Virtual nodes:** each physical node claims multiple hashes:

```python
import hashlib

def vnode_positions(physical_id, vnode_count=100):
    return [
        int(hashlib.md5(f"{physical_id}#{i}".encode()).hexdigest(), 16) % (2**32)
        for i in range(vnode_count)
    ]
```

100 vnodes per server → tighter balance. AWS Dynamo and Cassandra use vnode concepts.

## Lookup algorithm

```python
def get_node(key, ring_sorted):
    h = hash_key(key)
    for node_hash, node_id in ring_sorted:
        if node_hash >= h:
            return node_id
    return ring_sorted[0][1]  # wrap
```

Binary search on sorted ring — O(log N).

## Replication on ring

Walk clockwise for R replicas — key stored on primary node plus next R-1 distinct nodes. Survives node loss without full reshuffle.

Dynamo: preference list, quorum reads/writes.

## Hot spots

Celebrity key still lands one node — consistent hashing balances **average** load, not **worst** case. Mitigate with:

- Application-level sharding of hot keys (sub-keys)
- Separate hot key cache layer
- Dynamic load migration (Redis Cluster rebalances slots)

## Client vs server-side routing

**Client-side** — library computes node (Ketama for Memcached). Smart clients, dumb servers.

**Server-side** — proxy (Twemproxy, Envoy hash policy) or cluster metadata (Redis Cluster gossip).

Server-side simplifies client upgrades when ring topology changes.

## Redis Cluster variant

16384 **hash slots** assigned to nodes — consistent hashing flavor with fixed slot space. `MOVED`/`ASK` redirects during resharding. Slots migrate incrementally online.

## Resharding operations

1. Add new node with vnodes
2. Identify key ranges to migrate (between old and new positions)
3. Copy data in background
4. Dual-read or brief lock during cutover
5. Remove old node if shrinking

Automate in Vitess, Cassandra, managed DBs — manual ring math error-prone.

## When simpler hashing suffices

Fixed shard count forever, small N, full reshuffle acceptable offline — `% N` OK.

Consistent hashing when **elastic scale** and **cache warmth** matter.

## Implementation walkthrough

Building a minimal consistent hash ring in Python:

```python
import bisect
import hashlib
from dataclasses import dataclass

@dataclass
class RingNode:
    hash_pos: int
    node_id: str

class ConsistentHashRing:
    def __init__(self, nodes: list[str], vnodes_per_node: int = 100):
        self.ring: list[RingNode] = []
        for node_id in nodes:
            for i in range(vnodes_per_node):
                h = self._hash(f"{node_id}#{i}")
                self.ring.append(RingNode(h, node_id))
        self.ring.sort(key=lambda n: n.hash_pos)

    def _hash(self, key: str) -> int:
        return int(hashlib.sha256(key.encode()).hexdigest(), 16) % (2**32)

    def get_node(self, key: str) -> str:
        h = self._hash(key)
        idx = bisect.bisect_left([n.hash_pos for n in self.ring], h)
        if idx == len(self.ring):
            idx = 0
        return self.ring[idx].node_id

    def add_node(self, node_id: str, vnodes: int = 100):
        for i in range(vnodes):
            h = self._hash(f"{node_id}#{i}")
            bisect.insort(self.ring, RingNode(h, node_id), key=lambda n: n.hash_pos)

    def remove_node(self, node_id: str):
        self.ring = [n for n in self.ring if n.node_id != node_id]
```

Adding a node only affects keys that hash between the new node's positions and its predecessor — typically ~1/N of all keys.

## Load balancing and weighted nodes

Not all servers have equal capacity. Assign more vnodes to powerful nodes:

```python
# High-memory node gets 200 vnodes, standard gets 100
ring.add_node("cache-large-1", vnodes=200)
ring.add_node("cache-standard-1", vnodes=100)
ring.add_node("cache-standard-2", vnodes=100)
```

`cache-large-1` receives roughly 2× the keys of each standard node. Adjust vnode counts until per-node memory/CPU utilization is balanced.

## Production deployment patterns

**Memcached client-side routing:** Ketama library computes ring locally; client connects directly to the correct server. Adding a Memcached node requires updating all clients' ring configuration simultaneously — or accept brief cache miss storm during transition.

**Redis Cluster server-side routing:** Fixed 16384 hash slots assigned to nodes. Resharding moves slots incrementally with `MOVED`/`ASK` redirects. Clients don't need ring updates — cluster gossip handles topology changes.

**Database sharding (Vitess/Cassandra):** Consistent hashing with vnodes built into the sharding layer. Resharding is an operational workflow, not application code.

## Failure modes

- **Too few vnodes** — uneven load distribution with small cluster; use 100+ vnodes per physical node
- **Hot key** — consistent hashing doesn't help; one celebrity key still lands on one node
- **Ring not updated on node failure** — clients route to dead node until ring refreshed
- **Modulo used where elasticity needed** — full cache invalidation on every scale event
- **No replication walk** — single node failure loses all keys on that node without clockwise replica

## Production checklist

- Virtual nodes configured (100+ per physical node)
- Weighted vnodes for heterogeneous hardware
- Hot key mitigation strategy (application-level sub-sharding or dedicated cache)
- Ring update protocol defined for add/remove node operations
- Replication factor configured (walk clockwise for R copies)
- Load tested after topology changes to verify balanced distribution

## Resources

- [Karger et al. — Consistent Hashing paper (1997)](https://www.akamai.com/us/en/multimedia/documents/technical-publication/consistent-hashing-and-random-trees-distributed-caching-protocols-for-relieving-hot-spots-on-the-world-wide-web-technical-publication.pdf)
- [Dynamo paper — partitioning section](https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf)
- [Redis Cluster specification](https://redis.io/docs/reference/cluster-spec/)
- [libketama — consistent hashing library](https://github.com/RJ/ketama)
- [Cassandra virtual nodes](https://cassandra.apache.org/doc/latest/cassandra/managing/operating/vnodes.html)
