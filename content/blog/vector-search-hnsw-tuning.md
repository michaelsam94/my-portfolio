---
title: "Tuning HNSW for Vector Search"
slug: "vector-search-hnsw-tuning"
description: "Tune HNSW index parameters for vector search: m, ef_construction, ef_search, recall-latency trade-offs, and practical benchmarks for production workloads."
datePublished: "2026-03-03"
dateModified: "2026-03-03"
tags: ["AI", "Vector Database", "Search", "Performance"]
keywords: "HNSW tuning, ef_search, ef_construction, vector index, recall, latency, approximate nearest neighbor"
faq:
  - q: "What is HNSW and why is it the default vector index?"
    a: "HNSW (Hierarchical Navigable Small World) is a graph-based approximate nearest neighbor index that builds a multi-layer structure where each vector is connected to its nearest neighbors. Search starts at the top layer and navigates down, following the closest connections at each level. It offers the best recall-latency trade-off among practical ANN algorithms and supports incremental inserts without full rebuilds, which is why pgvector, Qdrant, Weaviate, and most vector databases use it as their default index type."
  - q: "What do the HNSW parameters m and ef_construction control?"
    a: "The m parameter sets how many bidirectional connections each new vector creates in the graph. Higher m means denser graphs, better recall, and more memory. ef_construction controls how many candidate neighbors are considered during index build — higher values produce better graph quality at the cost of slower builds. These are build-time parameters: once set, they define the index structure until you rebuild."
  - q: "How do I tune ef_search for the right recall-latency balance?"
    a: "ef_search is a query-time parameter that controls how many candidates HNSW examines during a search. Higher ef_search means the algorithm explores more of the graph, improving recall but increasing latency. Start at 40 (the default in most implementations), measure recall against a ground-truth test set, and increase until recall plateaus. Typical production values range from 64 to 200. Unlike m and ef_construction, ef_search can be changed per query or per session without rebuilding the index."
---

We deployed pgvector with default HNSW settings and celebrated when queries returned in 8ms. Then someone ran an evaluation against ground-truth nearest neighbors and found recall@10 was 72%. Nearly a third of the true nearest neighbors weren't in the results. Bumping `ef_search` from 40 to 128 pushed recall to 96% with latency still under 20ms. The index was fast because it was lazy, not because it was well-tuned. HNSW has three knobs that control the recall-latency-memory triangle, and the defaults are conservative starting points — not production targets.

## How HNSW works (briefly)

HNSW builds a hierarchy of graphs. The top layer is sparse with long-range connections. Each layer below is denser. Search starts at the top, greedily follows the nearest neighbor, and descends layer by layer until it reaches the bottom layer, which contains all vectors.

```
Layer 2:  A -------- D
Layer 1:  A -- B -- D -- E
Layer 0:  A-B-C-D-E-F-G-H  (all vectors)
```

The quality of connections and the thoroughness of search at each layer determine recall.

## The three parameters

### m (connections per node)

Set at index build time. Controls graph density.

| m value | Memory | Build time | Recall | Use case |
|---|---|---|---|---|
| 8 | Low | Fast | Moderate | Memory-constrained, large datasets |
| 16 | Medium | Medium | Good | Default for most workloads |
| 32 | High | Slow | Excellent | High-recall requirements, smaller datasets |
| 48+ | Very high | Very slow | Marginal gains | Rarely worth it |

```sql
-- pgvector
CREATE INDEX ON documents
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

Rule of thumb: start with m=16. Increase to 32 only if recall is insufficient after tuning ef_search.

### ef_construction (build-time search depth)

How many candidates HNSW evaluates when inserting each vector. Higher = better graph quality.

```sql
CREATE INDEX ON documents
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 128);
```

| ef_construction | Build time | Index quality |
|---|---|---|
| 64 | Fast | Adequate |
| 128 | 2x | Good |
| 256 | 4x | Excellent |
| 512 | 8x | Diminishing returns |

Set ef_construction ≥ 2 × m. For production indexes, 128-256 is the sweet spot. Rebuilding with higher ef_construction on an existing dataset is the cheapest way to improve recall without changing query-time latency.

### ef_search (query-time search depth)

The parameter you tune most often. Controls how many candidates are explored during each query.

```sql
-- pgvector: per-session
SET hnsw.ef_search = 100;

-- Qdrant: per-query
client.search(
    collection_name="docs",
    query_vector=embedding,
    search_params={"hnsw_ef": 100}
)
```

| ef_search | Recall@10 (typical) | Latency (typical) |
|---|---|---|
| 20 | ~80% | ~5ms |
| 40 | ~90% | ~8ms |
| 64 | ~94% | ~12ms |
| 100 | ~96% | ~18ms |
| 200 | ~98% | ~35ms |

These numbers vary by dataset size, dimension, and m. Measure on your data.

## Benchmarking methodology

Don't guess — measure recall and latency on your actual data:

```python
import numpy as np
from sklearn.neighbors import NearestNeighbors

def evaluate_recall(index, queries, ground_truth, k=10, ef_values=[40, 64, 100, 128, 200]):
    results = {}
    for ef in ef_values:
        hits = 0
        latencies = []
        for q, gt in zip(queries, ground_truth):
            start = time.perf_counter()
            found = index.search(q, k=k, ef_search=ef)
            latencies.append(time.perf_counter() - start)
            found_ids = {r.id for r in found}
            hits += len(found_ids & set(gt[:k])) / k
        results[ef] = {
            "recall": hits / len(queries),
            "p50_ms": np.percentile(latencies, 50) * 1000,
            "p99_ms": np.percentile(latencies, 99) * 1000,
        }
    return results
```

Generate ground truth with brute-force exact search on a sample of queries. Compare ANN results against it at different ef_search values. Plot recall vs. latency and pick the knee of the curve.

## Tuning workflow

1. **Build index** with m=16, ef_construction=128
2. **Set ef_search=40** (default), measure recall@10 and p99 latency
3. **If recall < 95%**, increase ef_search to 64, 100, 128 until recall plateaus
4. **If recall still insufficient**, rebuild with m=32 or ef_construction=256
5. **If latency too high** at target recall, consider reducing dimension (PCA/matryoshka) or sharding

## Dimension reduction as a tuning lever

If HNSW tuning can't hit your latency target, reduce dimensions:

```python
from sklearn.decomposition import PCA

pca = PCA(n_components=512)
reduced_embeddings = pca.fit_transform(embeddings_1536d)
# 1536 → 512 dimensions: ~3x less memory, ~3x faster search
# Measure recall impact — typically 1-3% drop for text embeddings
```

Matryoshka embeddings (trained at multiple dimensions) let you truncate without PCA:

```python
# OpenAI text-embedding-3-large supports dimension reduction
embedding = client.embeddings.create(
    input=text, model="text-embedding-3-large", dimensions=512
).data[0].embedding
```

## Insert performance

HNSW insert throughput decreases as the index grows. Mitigations:

- **Batch inserts** — insert 1000-10000 vectors at a time, not one at a time
- **Build index after bulk load** — insert without index, create index after
- **Lower m during bulk load** — rebuild with higher m after if needed
- **Parallel inserts** — Qdrant and Milvus support concurrent writes to different segments

## Monitoring in production

Track these metrics:
- **recall@K** — weekly evaluation against ground-truth sample
- **p50/p99 query latency** — alert on p99 > SLA
- **index memory usage** — alert at 80% of node RAM
- **insert throughput** — alert on degradation

Recall can degrade as data grows if the graph becomes sparse relative to dataset size. Rebuild or re-tune when recall drops below threshold.

## Common production mistakes

Teams get vector search hnsw tuning wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of vector search hnsw tuning fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [HNSW paper (Malkov & Yashunin, 2018)](https://arxiv.org/abs/1603.09320)
- [pgvector HNSW parameters](https://github.com/pgvector/pgvector#hnsw)
- [Qdrant HNSW configuration](https://qdrant.tech/documentation/concepts/indexing/#vector-index)
- [ANN benchmarks](https://ann-benchmarks.com/)
- [Pinecone HNSW guide](https://www.pinecone.io/learn/series/faiss/hnsw/)
