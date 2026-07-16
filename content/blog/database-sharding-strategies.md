---
title: "Database Sharding Strategies"
slug: "database-sharding-strategies"
description: "Sharding splits data across nodes by partition key. Hash vs range vs directory sharding, resharding, cross-shard queries, and when to shard versus scale up."
datePublished: "2025-09-09"
dateModified: "2025-09-09"
tags: ["Backend", "Databases", "Architecture"]
keywords: "database sharding, partition key, hash sharding, range sharding, resharding, Vitess, Citus"
faq:
  - q: "What is database sharding?"
    a: "Sharding horizontally partitions data across multiple database instances by a shard key. Each shard holds a subset of rows; the application or middleware routes queries to the correct shard. Sharding scales write throughput and storage beyond single-node limits."
  - q: "How do I choose a shard key?"
    a: "Pick a key with high cardinality, even distribution, and alignment with query patterns — most queries filter by shard key to avoid scatter-gather. user_id and tenant_id are common. Avoid monotonic keys alone (hot last shard) unless combined with hashing."
  - q: "When should I shard versus scale vertically?"
    a: "Scale up while a single node handles load with acceptable cost and ops simplicity. Shard when write throughput, storage, or connection limits exceed single-node capacity, or when blast radius isolation per tenant requires physical separation."
---

Nobody shards on day one — and nobody should. Sharding is what you do when vertical scaling, read replicas, and connection pooling stopped being enough, and you're willing to pay the tax on every join that crosses a partition boundary.

## Sharding models

**Hash sharding** — `shard = hash(key) mod N`:

Even spread; range queries across keys require all shards. Resharding when N changes moves most data.

**Range sharding** — keys A-M on shard 1, N-Z on shard 2:

Range scans local; risk hot spots (all new users in one range).

**Directory sharding** — lookup table maps key → shard:

Flexible migration; directory is bottleneck and SPOF without HA.

**Geographic sharding** — EU tenants on EU shards for data residency.

Often hybrid: hash(tenant_id) within region.

## Application-level routing

```python
def shard_for_user(user_id: int) -> str:
    return f"shard_{user_id % 16}"

def get_connection(user_id: int):
    return pools[shard_for_user(user_id)]
```

Every query includes shard key in WHERE clause:

```sql
-- Routed to one shard
SELECT * FROM orders WHERE user_id = 12345 AND order_id = 99;

-- Scatter-gather — expensive
SELECT count(*) FROM orders WHERE status = 'pending';
```

Cross-shard aggregates need map-reduce, CQRS read models, or accept latency.

## Schema per shard

Same schema everywhere — ops simplicity. Migrations run on all shards (tooling: gh-ost per shard, Flyway orchestration).

Global tables (reference data) replicate to each shard or live on separate small DB with cache.

## Hot spots and skew

Celebrity user problem — one `tenant_id` dominates traffic. Mitigations:

- Sub-shard hot tenants to dedicated shard
- Rate limit at application layer
- Split entity further (user messages by conversation_id hash)

Monitor per-shard QPS, storage, replication lag — rebalance before crisis.

## Resharding

Growing from 16 to 32 shards:

1. **Consistent hashing** — minimal key movement (see consistent hashing article)
2. **Dual-write** new and old mapping during migration
3. **Vitess, Citus, MongoDB** automate shard split

Plan resharding before you need emergency weekend cutover.

## Managed and middleware options

| Tool | Model |
|---|---|
| Vitess | MySQL sharding middleware |
| Citus | Postgres extension, distribute by column |
| MongoDB sharded cluster | Native |
| AWS DynamoDB | Managed partition keys |
| Spanner | Transparent sharding |

Middleware hides routing; you still design keys correctly.

## Multi-tenant SaaS pattern

Shard by `tenant_id` — small tenants cohabit shards, enterprise tenants get dedicated shard for isolation and noisy-neighbor control. Directory maps tenant → shard for migrations.

## Queries that hurt

- Joins across shard keys without colocation
- Global unique constraints (use UUID or central ID service)
- Transactions spanning shards — 2PC rare; prefer sagas per aggregate

Colocate related entities sharing shard key: `user_id` on users, orders, sessions tables.

## Before you shard checklist

- [ ] Exhausted vertical scale and read replicas
- [ ] >95% queries include candidate shard key
- [ ] Ops ready for N-database monitoring and migrations
- [ ] Cross-shard reporting moved to warehouse/analytics path

If checklist fails, wait.

## Real-world sharding war stories

**The celebrity tenant problem:** A SaaS platform sharded by `tenant_id` hash. One enterprise customer generated 40% of all writes. Their shard ran hot — replication lag spiked, queries slowed for co-located small tenants. Fix: migrate the enterprise tenant to a dedicated shard via directory sharding override. Monitor per-shard write QPS, not just aggregate.

**The cross-shard join that killed reporting:** Engineering ran `SELECT u.name, o.total FROM users u JOIN orders o ON u.id = o.user_id` without realizing users and orders were on different shards. Query fanned out to all 32 shards, aggregated in application memory, and OOM'd the API server. Fix: colocate users and orders on same shard key; move cross-shard analytics to the warehouse.

**The resharding weekend:** Team went from 8 to 16 shards with naive hash mod change. Every key moved. Required 48-hour dual-write migration with consistency checks. Fix: use consistent hashing (see [consistent hashing guide](https://blog.michaelsam94.com/distributed-consistent-hashing/)) or managed tooling (Vitess resharding) that minimizes data movement.

## Vitess and Citus operational notes

**Vitess (MySQL):** Vtgate routes queries; vttablet per shard. Application connects to Vtgate, not individual shards. Resharding is a first-class workflow — plan shard count upfront but know Vitess supports live resharding. Used by Slack, GitHub, Square.

**Citus (Postgres):** Extension that distributes tables by column. `SELECT create_distributed_table('orders', 'tenant_id')`. Cross-shard queries use parallel query execution. Simpler than Vitess for Postgres shops — no separate routing layer, just SQL.

Both require the same design discipline: choose shard key before schema design, not after.

## Connection pooling across shards

Each shard needs its own connection pool. With 32 shards and 20 connections per pool, that's 640 database connections from one service:

```
Total connections = num_shards × pool_size × num_service_instances
```

Mitigate with:
- PgBouncer or RDS Proxy per shard
- Smaller pools per shard (5–10 connections)
- Read replicas for read-heavy shards
- Connection pooler at the Vitess/Citus routing layer

## Observability per shard

Dashboard metrics per shard, not aggregate:

- Write QPS and read QPS
- Storage utilization
- Replication lag (critical — lag on one shard = stale reads for those users)
- Connection pool utilization
- Slow query count

Alert when any single shard exceeds 2× the median shard load — that's your next hot spot.

## Failure modes

- **Shard key not in WHERE clause** — scatter-gather query hits all shards; latency × N
- **Global unique constraint** — auto-increment IDs collide across shards; use UUIDs or central ID service
- **Cross-shard transaction** — 2PC across shards is fragile; design aggregates to single shard
- **Resharding under load** — dual-write period creates consistency windows; plan maintenance
- **Skewed hash distribution** — low-cardinality shard key clusters on few shards

## Production checklist

- Shard key chosen before schema design with >95% query coverage
- Related entities colocated on same shard key
- Per-shard monitoring and alerting configured
- Cross-shard queries routed to warehouse/analytics, not OLTP
- Resharding procedure documented and tested in staging
- Connection pool sizing accounts for shard count × instances
- Hot tenant detection and dedicated shard migration path

## Resources

- [Vitess documentation](https://vitess.io/docs/)
- [Citus — Distributed PostgreSQL](https://docs.citusdata.com/)
- [MongoDB sharding guide](https://www.mongodb.com/docs/manual/sharding/)
- [AWS — DynamoDB partition keys](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-partition-key-design.html)
- [Instagram's sharding story (Meta engineering)](https://engineering.fb.com/)
