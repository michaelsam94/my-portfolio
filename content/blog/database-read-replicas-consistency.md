---
title: "Read Replicas and Consistency"
slug: "database-read-replicas-consistency"
description: "Read replicas scale reads but lag behind the primary. Replication modes, staleness budgets, read-your-writes routing, and when replicas lie to users."
datePublished: "2025-09-06"
dateModified: "2025-09-06"
tags: ["Backend", "Databases", "Architecture"]
keywords: "read replica, replication lag, read your writes, eventual consistency, PostgreSQL streaming replication, Aurora replicas"
faq:
  - q: "What is a read replica?"
    a: "A read replica is a copy of a primary database that applies changes asynchronously or semi-synchronously from the primary's write-ahead log or binlog. Applications route read queries to replicas to offload the primary, accepting potential replication lag between write on primary and visibility on replica."
  - q: "What is replication lag?"
    a: "Replication lag is the delay between a commit on the primary and when that change appears on a replica. Lag spikes during heavy writes, network issues, or slow replica apply. Users reading from lagging replicas see stale data — missing recent rows or outdated values."
  - q: "How do I implement read-your-writes consistency?"
    a: "Route reads for a session to the primary after a write, use session tracking of last write LSN and wait for replica catch-up, or employ globally consistent read endpoints (Aurora global DB, Spanner). Simplest pattern: writes and immediate subsequent reads hit primary; background analytics hit replicas."
---

Adding read replicas fixed our connection pool exhaustion, then broke the profile page — users updated their name, refreshed, saw the old name for three seconds. Replicas scale reads; they don't copy the consistency model of a single node unless you engineer it.

## Primary-replica topology

```
        ┌──▶ Replica 1 (reads)
App ──▶ Primary (writes)
        └──▶ Replica 2 (reads)
```

Primary accepts writes, streams WAL/binlog to replicas. Replicas apply changes in order — usually asynchronous.

## Consistency spectrum

| Mode | Behavior |
|---|---|
| Strong (single node) | Reads see latest commit |
| Async replica | Reads may be stale |
| Semi-sync | At least one replica acked before commit ack — reduces loss risk, not read staleness |
| Sync quorum | Commit after N replicas — costly, rare in general OLTP |

**Replication lag** measured in bytes, seconds, or transactions behind:

```sql
-- PostgreSQL
SELECT pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS lag_bytes
FROM pg_stat_replication;
```

Alert on lag p99, not just average.

## Staleness budgets

Define acceptable lag per use case:

| Query | Staleness OK? |
|---|---|
| Dashboard analytics | Minutes |
| Product catalog | Seconds |
| User profile after edit | Zero |
| Payment status after checkout | Zero |

Route accordingly — not all reads go to replicas.

## Read-your-writes patterns

**Sticky primary after write** — session flag routes reads to primary for N seconds post-write:

```python
def get_user(user_id, session):
    if session.recently_wrote_user(user_id):
        return db_primary.get_user(user_id)
    return db_replica.get_user(user_id)
```

**Monotonic reads** — same user always hits same replica via consistent hashing to avoid flip-flopping between lag states.

**Wait for catch-up** — Postgres `pg_wait_for_lsn` or proxy logic:

```sql
SELECT pg_wait_for_lsn('0/ABC123');  -- after recording write LSN
```

Adds latency; use sparingly on critical paths.

**Causal consistency tokens** — client sends last seen LSN; proxy routes or waits until replica >= LSN.

## Proxy and driver support

PgBouncer, RDS Proxy, HAProxy, Vitess, Citus — some offer read/write split with lag awareness. ORMs often need explicit `using(:replica)` vs `using(:primary)` — no magic default.

Aurora reader endpoints load-balance replicas; **Aurora MySQL global database** offers cross-region with defined RPO/RTO tradeoffs.

## When replicas mislead

- **Unique constraint checks on replica** — stale read misses recent insert, duplicate key on primary
- **Read-modify-write on replica** — race with primary writes
- **Failover promotion** — replica lag means lost transactions if promoted too early

Never enforce uniqueness or financial invariants on replica reads alone.

## Failover and consistency

Promote lagging replica → data loss window equals lag at promotion time. Use `pg_replication_slot` monitoring, synchronous standbys for zero RPO tiers (write latency cost).

Test failover quarterly — replica promotion changes DNS/connection strings; apps must reconnect.

## Scaling replicas without lies

Add replicas until lag stable under peak write load. If lag unbounded, primary write throughput exceeds apply capacity — shard or upgrade replica hardware.

Connection pool per replica; don't fan one pool to all nodes blindly.

Cache hot reads (Redis) with TTL + invalidation on write — reduces replica load and staleness sensitivity for read-heavy keys.

## Aurora and managed database specifics

Managed databases offer replica features beyond vanilla Postgres:

**Amazon Aurora:**
- Storage layer shared between primary and replicas — replication lag typically sub-100ms
- Reader endpoint load-balances across replicas automatically
- Aurora Global Database: cross-region replicas with ~1 second typical lag
- Custom endpoints: route specific query patterns to specific replica groups

**Google Cloud SQL:**
- Read replicas with automatic failover promotion
- Query Insights shows which queries hit primary vs replica

**Supabase/Neon:**
- Read replicas as separate compute endpoints
- Connection string routing via pooler

Managed offerings reduce ops burden but don't eliminate staleness — application routing logic still required.

## Read replica for analytics

The cleanest pattern: never mix OLTP and analytics queries on the same replica pool.

```
Primary → OLTP reads requiring freshness
Replica pool A → Application reads tolerating seconds of lag
Replica pool B → Analytics/BI queries (can tolerate minutes)
```

Analytics queries (full table scans, complex joins) starve OLTP reads if they share replica pools. Dedicated analytics replica — or better, replicate to warehouse via CDC — keeps OLTP performance stable.

## Connection pool routing

```python
class DatabaseRouter:
    def __init__(self, primary_pool, replica_pool):
        self.primary = primary_pool
        self.replica = replica_pool

    def read(self, session, query):
        if session.needs_fresh_read:
            return self.primary.execute(query)
        return self.replica.execute(query)

    def write(self, query):
        result = self.primary.execute(query)
        session.mark_written()  # subsequent reads go to primary
        return result
```

ORM integration (Django database router, Rails multiple databases, TypeORM replication) provides similar patterns — configure explicitly, don't assume automatic routing.

## Failure modes

- **All reads to replica after write** — user sees stale data; implement sticky primary
- **Uniqueness check on replica** — duplicate key error on primary; always check constraints on primary
- **Analytics on OLTP replica pool** — slow queries degrade app read latency
- **Promoting lagging replica** — data loss equal to lag at promotion time
- **No lag monitoring** — stale reads discovered by users, not alerts

## Production checklist

- Staleness budget defined per query type
- Read-your-writes implemented (sticky primary or LSN wait)
- Replication lag monitored with p99 alerting
- Analytics queries routed to dedicated replica or warehouse
- Uniqueness checks always run against primary
- Failover tested quarterly with lag measurement
- Connection pool configured per endpoint (primary vs replica)

## Common production mistakes

Teams get read replicas consistency wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Data pipelines for read replicas consistency silently corrupt when schema evolution is backward-incompatible, late-arriving events are dropped, and warehouse costs spike because nobody partitions by query pattern.

## Resources

- [PostgreSQL — Streaming Replication](https://www.postgresql.org/docs/current/warm-standby.html)
- [AWS RDS — Read replicas](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ReadRepl.html)
- [Google Cloud SQL — Replication](https://cloud.google.com/sql/docs/postgres/replication)
- [Jepsen — replica consistency analyses](https://jepsen.io/)
- [Amazon Aurora — Endpoints and reader scaling](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Aurora.Overview.html)
