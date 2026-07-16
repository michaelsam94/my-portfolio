---
title: "Sharding and Scaling Vector Databases"
slug: "vector-db-sharding-scaling"
description: "Scale vector databases beyond a single node: sharding strategies, multi-tenancy, replication, load balancing, and capacity planning for embedding workloads."
datePublished: "2026-03-01"
dateModified: "2026-03-01"
tags: ["AI", "Vector Database", "Architecture", "Scaling"]
keywords: "vector database sharding, scaling, multi-tenancy, distributed vector search, capacity planning, HNSW scaling"
faq:
  - q: "When do I need to shard a vector database?"
    a: "Shard when a single node's memory cannot hold the HNSW index for your full dataset, when query latency exceeds your SLA at current data volume, or when insert throughput saturates a single node's CPU or I/O. A rough threshold is 10-50 million vectors per node depending on dimension count and hardware. If your 1536-dimension index exceeds available RAM and queries fall back to disk, or p99 latency climbs above your target, it is time to distribute."
  - q: "What are the main sharding strategies for vector databases?"
    a: "The three common strategies are: sharding by tenant or namespace (each shard holds one customer's data), sharding by document ID hash (distribute evenly across shards), and sharding by vector clustering (group similar vectors on the same shard for locality). Tenant-based sharding is simplest for multi-tenant SaaS and provides natural isolation. Hash sharding gives even distribution but requires querying all shards. Cluster-based sharding improves per-shard recall but complicates rebalancing."
  - q: "How do I query across multiple vector database shards?"
    a: "The standard approach is scatter-gather: send the query to all shards in parallel, each returns its local top-K results, and a coordinator merges the results and returns the global top-K. This adds latency proportional to the slowest shard plus merge time. Reduce cross-shard queries by routing to the correct shard when a filter (like tenant_id) determines the target, so most queries hit a single shard."
---

At 30 million vectors, our single-node Qdrant instance started swapping. HNSW indexes are memory-hungry — a 1536-dimension index with 30M vectors and m=16 needs roughly 90 GB of RAM for the graph alone, before payloads and OS overhead. We had 64 GB. Query latency went from 15ms p99 to 400ms, then the OOM killer arrived. Sharding wasn't an optimization — it was survival. Vector databases don't scale vertically forever, and the sharding model you choose determines your latency, isolation, and operational complexity for years.

## Why vector databases hit scaling walls

Unlike relational databases where disk-backed B-trees handle datasets larger than RAM, HNSW indexes are predominantly in-memory. Key scaling bottlenecks:

- **Memory** — HNSW graph + vector data must fit in RAM for target latency
- **Insert rate** — each insert updates graph connections; throughput drops as the index grows
- **Graph quality** — very large single-node graphs can degrade recall if parameters aren't retuned
- **Rebuild time** — reindexing 50M vectors takes hours

## Sharding strategies

### By tenant (namespace)

Each tenant gets a dedicated shard or collection:

```
tenant_acme  → shard_1
tenant_globex → shard_2
tenant_initech → shard_3
```

**Pros:** Natural isolation, queries route to one shard, easy per-tenant retention and deletion.
**Cons:** Uneven distribution if tenants vary wildly in size. Hot tenants saturate a single shard.

Best for: Multi-tenant SaaS where queries always include a tenant filter.

### By hash

Distribute vectors by `hash(document_id) % num_shards`:

```
hash(doc_123) % 4 = 2  → shard_2
hash(doc_456) % 4 = 0  → shard_0
```

**Pros:** Even distribution regardless of tenant size.
**Cons:** Every query must scatter-gather across all shards. No natural isolation.

Best for: Single-tenant deployments or research datasets with uniform access patterns.

### By category or metadata

Group related vectors on the same shard:

```
category=legal    → shard_0
category=medical  → shard_1
category=finance  → shard_2
```

**Pros:** Queries with category filters hit one shard. Related vectors cluster for better per-shard recall.
**Cons:** Rebalancing when categories grow unevenly. Cross-category queries need scatter-gather.

Best for: Domain-specific search where queries naturally filter by category.

## Scatter-gather query pattern

When a query must search multiple shards:

```python
async def search_all_shards(query_vector: list[float], k: int = 10) -> list[Result]:
    tasks = [
        shard.query(vector=query_vector, top_k=k)
        for shard in shards
    ]
    shard_results = await asyncio.gather(*tasks)

    merged = heapq.merge(
        *[results for results in shard_results],
        key=lambda r: r.score
    )
    return list(itertools.islice(merged, k))
```

Each shard returns top-K. The coordinator merges by score and takes global top-K. Total latency = slowest shard + merge time. With 4 shards at 20ms each, scatter-gather adds ~25ms versus ~20ms for a single shard.

**Optimization:** Route to a single shard when possible:

```python
def get_shard(tenant_id: str) -> Shard:
    return shards[hash(tenant_id) % len(shards)]

# Most queries hit one shard
results = await get_shard(tenant_id).query(vector, top_k=k)
```

## Replication for read scaling

Shard replicas handle read queries while the primary handles writes:

```
shard_1_primary (writes) → shard_1_replica_a (reads)
                         → shard_1_replica_b (reads)
```

Vector databases differ in replication maturity:
- **Qdrant** — raft-based replication per shard
- **Weaviate** — replication factor per class
- **Milvus** — segment-level replication
- **Pinecone** — managed, opaque replication

For read-heavy RAG workloads (many queries per insert), replicas are high value.

## Capacity planning

Rough memory estimate for HNSW:

```
memory ≈ num_vectors × dimension × 4 bytes × overhead_factor

overhead_factor ≈ 1.5-2.0 (graph connections + metadata)
```

For 10M vectors at 1536 dimensions:
```
10M × 1536 × 4 × 1.5 ≈ 92 GB
```

Plan shards so each holds 50-70% of available RAM, leaving headroom for payloads, query working memory, and OS cache.

| Vectors | Dimension | Estimated RAM | Suggested shards (64GB nodes) |
|---|---|---|---|
| 1M | 1536 | ~9 GB | 1 |
| 10M | 1536 | ~92 GB | 2 |
| 50M | 1536 | ~460 GB | 8 |
| 100M | 1536 | ~920 GB | 16 |

## Rebalancing

Shards become uneven over time as tenants grow or data is deleted. Rebalancing strategies:

- **Consistent hashing** — adding a shard only moves 1/N of data
- **Background migration** — copy vectors to new shard, update routing, delete from old
- **Tiered storage** — move cold vectors to disk-backed indexes, keep hot data in memory

Most managed vector databases (Pinecone, Zilliz Cloud) handle rebalancing transparently. Self-hosted requires planning.

## Multi-tenancy without sharding

If your dataset fits on one node but you need tenant isolation:

- **Separate collections per tenant** — simple, but collection overhead adds up past ~1000 tenants
- **Metadata filtering** — single collection with `tenant_id` filter; works until total data exceeds node capacity
- **Hybrid** — large tenants get dedicated shards, small tenants share a common shard

## What I'd do for a new system

1. Start single-node pgvector or Qdrant until 5M vectors
2. Add read replicas when query latency matters more than insert rate
3. Shard by tenant when memory pressure hits 70% or a single tenant needs isolation
4. Use scatter-gather only as a fallback — route to single shard whenever the query allows
5. Monitor per-shard memory, query latency, and insert rate independently

## Common production mistakes

Teams get vector db sharding scaling wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of vector db sharding scaling fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [Qdrant distributed deployment](https://qdrant.tech/documentation/guides/distributed_deployment/)
- [Milvus architecture overview](https://milvus.io/docs/architecture_overview.md)
- [Pinecone pod-based scaling](https://docs.pinecone.io/guides/indexes/pods/understanding-pod-based-indexes)
- [Weaviate horizontal scaling](https://weaviate.io/developers/weaviate/concepts/cluster)
- [HNSW memory analysis (Pinecone)](https://www.pinecone.io/learn/series/faiss/hnsw/)
