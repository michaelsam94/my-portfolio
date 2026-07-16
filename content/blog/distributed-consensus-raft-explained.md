---
title: "Consensus with Raft, Explained"
slug: "distributed-consensus-raft-explained"
description: "Raft elects a leader and replicates logs for fault-tolerant consensus. Terms, elections, log matching, and why it's easier to teach than Paxos."
datePublished: "2025-10-09"
dateModified: "2025-10-09"
tags: ["Backend", "Databases", "Architecture"]
keywords: "Raft consensus, distributed consensus, leader election, replicated log, etcd, Consul, Paxos alternative"
faq:
  - q: "What problem does Raft solve?"
    a: "Raft solves distributed consensus — getting multiple nodes to agree on a sequence of values (log entries) despite failures. A elected leader accepts client writes, replicates entries to followers, and commits once a majority acknowledges. Committed entries are durable and applied in order on all servers."
  - q: "How is Raft different from Paxos?"
    a: "Raft decomposes consensus into leader election, log replication, and safety with explicit rules designed for understandability. Paxos is equivalently powerful but notoriously difficult to implement completely. etcd, Consul, and TiKV use Raft; many production systems prefer Raft for implementability."
  - q: "What happens when the Raft leader fails?"
    a: "Followers timeout if they hear no heartbeat, start an election, and vote for a candidate with a log at least as up-to-date as their own. Majority votes elect a new leader for the current term. Clients retry writes during election; uncommitted entries from the old leader may be discarded if not replicated to majority."
---

Consensus is the boring foundation beneath exciting things — service discovery, config stores, distributed locks, metadata for CockroachDB. Raft made consensus teachable enough that undergrads implement it in a semester, and production systems bet real infrastructure on it.

## The replicated state machine model

All nodes run identical state machine. **Log** of commands is replicated; once committed, each node applies commands in order — same inputs, same outputs.

```
Client → Leader → append to log → replicate to followers → commit on majority → apply
```

Committed entries survive as long as majority of nodes survive.

## Roles: leader, follower, candidate

- **Leader** — sole writer; handles client requests; sends heartbeats
- **Follower** — passive; responds to RPCs; becomes candidate on election timeout
- **Candidate** — requests votes during election

At most one leader per **term** (monotonic epoch number).

## Leader election

Follower election timeout (random 150–300ms) fires without leader heartbeat:

1. Increment term, become candidate, vote self
2. RequestVotes RPC to peers
3. Majority grants vote → become leader
4. Split vote → new election next timeout

Vote granted only if candidate's log is **at least as up-to-date** (compare last term, then index).

```go
// Simplified election timeout concept
if time.Since(lastHeartbeat) > randomTimeout() {
    startElection()
}
```

Randomization reduces split-vote livelock.

## Log replication

Client sends command to leader:

1. Leader appends entry to local log (uncommitted)
2. AppendEntries RPC to followers with `prevLogIndex/Term` consistency check
3. Followers append if prefix matches; else reject — leader decrements nextIndex and retries
4. Leader commits entry once replicated on **majority**; applies to state machine
5. Commits propagate via next AppendEntries

**Log matching property:** if two entries same index and term, they store same command; all prior entries match.

## Safety guarantees

- **Election restriction** — only candidates with complete committed logs win
- **Leader completeness** — committed entry appears in all future leader logs
- **State machine safety** — same index applied same command

Old leader partition scenario: stale leader can't commit new entries without majority; rejoins as follower, overwrites uncommitted tail.

## Client interaction

Writes go to leader (or redirect). Linearizable reads from leader require additional constraints (`ReadIndex`/`LeaseRead`) — naive follower reads are stale.

etcd exposes linearizable reads via `quorum read` or leader confirmation.

## Typical deployment

3 or 5 nodes — tolerate 1 or 2 failures. Odd count avoids ties. **Don't run even counts** without reason — 4 nodes tolerates same 1 failure as 3 with extra cost.

Place nodes across failure domains (AZs). Majority must be reachable — 2 of 3 AZs if one AZ holds 2 nodes carefully.

## Where Raft lives

- **etcd** — Kubernetes control plane
- **Consul** — service mesh and KV
- **TiKV** — TiDB storage layer
- **CockroachDB** — range replicas (Multi-Raft)
- **Hashicorp Nomad** — scheduling state

Application devs rarely implement Raft — embed battle-tested library (`raft` in Hashicorp, etcd's pkg).

## Operational concerns

- **Snapshotting** — compact log when it grows; transfer state to slow followers
- **Membership changes** — joint consensus protocol; don't cold-add/remove nodes naively
- **Clock not required** — unlike Spanner; timeouts are relative
- **Write latency** — majority RTT per commit; cross-region Raft is slow — design accordingly

## Raft vs alternatives

| Approach | Notes |
|---|---|
| Raft | Understandable, leader bottleneck |
| Paxos / Multi-Paxos | Proven, harder to implement |
| Zab (ZooKeeper) | Similar role to Raft |
| Spanner TrueTime | Global consistency with GPS clocks |

Pick embedded Raft for control plane metadata — small records, strong consistency, moderate QPS.

## Raft log compaction and snapshots

Raft logs grow unbounded — snapshot to compact:

```
Log: [entry1, entry2, ..., entry1000, entry1001, ...]
      ↑ snapshot at entry1000 (state machine state frozen)
      New followers receive snapshot + entries after 1000
```

```go
// Hashicorp Raft snapshot configuration
config := raft.DefaultConfig()
config.SnapshotInterval = 2 * time.Minute
config.SnapshotThreshold = 8192  // snapshot after 8192 log entries
config.TrailingLogs = 10240      // keep 10240 entries after snapshot
```

Followers far behind leader receive snapshot instead of replaying entire log — critical for slow nodes rejoining cluster.

## Leader election and timeouts

Raft uses randomized election timeouts to prevent split votes:

```
Election timeout: 150–300ms (randomized per node)
Heartbeat interval: 50ms (leader sends to followers)
```

If follower doesn't receive heartbeat within election timeout → starts election. Randomization prevents simultaneous elections from all followers.

Cross-region Raft: election timeout must exceed RTT between regions:

```
Same region: 150–300ms election timeout
Cross-region (50ms RTT): 500–1000ms election timeout
Cross-continent (200ms RTT): 1000–2000ms election timeout
```

## When NOT to use Raft

| Scenario | Better alternative |
|---|---|
| High write throughput (>10k ops/sec) | Sharded databases, event logs |
| Global low-latency writes | CRDTs, eventual consistency |
| Simple leader election only | K8s Lease, advisory lock |
| Read-heavy workloads | Read replicas with eventual consistency |
| Large values (>1MB) | Object store; Raft for metadata only |

Raft commits require majority acknowledgment — cross-region majority adds 100–200ms per write. Use for configuration, service discovery, and coordination metadata only.

## Failure modes

- **Split brain after network partition** — two leaders if quorum misconfigured
- **Unbounded log growth** — disk full; snapshot not configured
- **Cold node addition** — joint consensus not used; cluster split
- **Cross-region Raft for hot path** — write latency unacceptable
- **Even number of nodes** — tie in elections; always use odd count (3, 5, 7)

## Production checklist

- Odd number of nodes (3 minimum for production)
- Snapshot interval and threshold configured
- Election timeout tuned to network RTT
- Joint consensus protocol for membership changes
- Raft used for metadata/coordination only, not hot data path
- Monitoring: leader changes, log size, replication lag per follower

Never run Raft with even number of nodes without understanding quorum edge cases — split votes during network partitions need explicit operator procedure.

## Resources

- [Raft paper — In Search of an Understandable Consensus Algorithm](https://raft.github.io/raft.pdf)
- [Raft visualizations (thesecretlivesofdata)](http://thesecretlivesofdata.com/raft/)
- [etcd Raft documentation](https://etcd.io/docs/v3.5/learning/learner/)
- [Hashicorp Raft library](https://github.com/hashicorp/raft)
- [Diego Ongaro PhD thesis on Raft](https://web.stanford.edu/~ouster/cgi-bin/papers/OngaroPhD.pdf)
