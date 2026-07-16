---
title: "IVF and Product Quantization Indexes"
slug: "vector-search-ivf-pq-index"
description: "Understand IVF and product quantization for vector search: how they reduce memory, recall trade-offs, when to use them over HNSW, and tuning parameters for large-scale indexes."
datePublished: "2026-03-05"
dateModified: "2026-03-05"
tags: ["AI", "Vector Database", "Search", "Performance"]
keywords: "IVF, product quantization, PQ, vector index, FAISS, approximate nearest neighbor, memory optimization"
faq:
  - q: "What is an IVF index in vector search?"
    a: "IVF (Inverted File Index) partitions the vector space into clusters using k-means, then at query time only searches the clusters nearest to the query vector. Instead of scanning all vectors, the index examines a small subset of clusters (controlled by nprobe), dramatically reducing search time. IVF requires a training step on existing data to compute cluster centroids, and its recall depends on how well the query's nearest neighbors cluster together."
  - q: "How does product quantization reduce vector index memory?"
    a: "Product quantization (PQ) compresses each vector by splitting it into sub-vectors, quantizing each sub-vector to a small codebook of representative values, and storing only the codebook indices. A 1536-dimension float32 vector (6 KB) can be compressed to 96 bytes or less with minimal recall loss. PQ is often combined with IVF (IVF-PQ) to get both fast search and small memory footprint, which is how FAISS serves billion-scale indexes on commodity hardware."
  - q: "When should I use IVF-PQ instead of HNSW?"
    a: "Use IVF-PQ when memory is the primary constraint and your dataset exceeds what HNSW can hold in RAM — typically above 50-100 million vectors. IVF-PQ can serve billion-vector indexes on a single machine with tens of gigabytes of RAM. Choose HNSW when you need the highest recall at low latency on datasets that fit in memory. Many production systems use HNSW for hot data and IVF-PQ for cold or archival vectors."
---

Our FAISS index for 200 million image embeddings needed 1.2 TB of RAM with a flat HNSW index. The server had 256 GB. Switching to IVF-PQ brought memory down to 38 GB with recall@10 dropping from 99% to 91% — acceptable for a "similar images" feature where users scroll through results. IVF and product quantization are the techniques that make billion-scale vector search economically viable, and understanding their trade-offs is essential when HNSW runs out of memory.

## IVF: search fewer vectors

IVF (Inverted File Index) clusters vectors into `nlist` groups using k-means:

```
Cluster 0: [v1, v7, v23, ...]
Cluster 1: [v2, v15, v41, ...]
...
Cluster nlist-1: [v3, v9, v31, ...]
```

At query time, find the `nprobe` nearest centroids and search only those clusters:

```python
import faiss

dimension = 1536
nlist = 4096  # number of clusters

quantizer = faiss.IndexFlatL2(dimension)
index = faiss.IndexIVFFlat(quantizer, dimension, nlist)

# Training requires representative data
index.train(training_vectors)  # at least nlist vectors
index.add(all_vectors)

index.nprobe = 32  # search 32 nearest clusters
distances, indices = index.search(query_vector, k=10)
```

### Key parameters

| Parameter | What it controls | Tuning |
|---|---|---|
| `nlist` | Number of clusters | sqrt(num_vectors), e.g., 4096 for 10M |
| `nprobe` | Clusters searched per query | Higher = better recall, slower. Start at 16-64 |

**nlist too low** — large clusters, slow per-cluster search.
**nlist too high** — small clusters, training needs more data, marginal gains.
**nprobe too low** — misses vectors in adjacent clusters, poor recall.
**nprobe too high** — approaches brute-force within searched clusters.

## Product quantization: compress vectors

PQ splits each vector into `m` sub-vectors and quantizes each to one of `ksub` centroids:

```
1536-dim vector → 48 sub-vectors of 32 dims each
Each sub-vector → nearest of 256 centroids (1 byte index)
Total storage: 48 bytes (vs 6144 bytes for float32)
```

```python
m = 48       # number of sub-vectors
nbits = 8    # bits per sub-quantizer (256 centroids)

index = faiss.IndexIVFPQ(quantizer, dimension, nlist, m, nbits)
index.train(training_vectors)
index.add(all_vectors)
index.nprobe = 32
```

Compression ratio: 1536 × 4 bytes / 48 bytes ≈ **128x compression**.

### Recall impact of PQ

PQ introduces approximation error because vectors are lossy-compressed. The impact depends on:
- **m** — more sub-vectors = less compression, better recall
- **nbits** — more bits per sub-quantizer = larger codebooks, better recall
- **Dimension** — higher-dimensional vectors compress more lossily

Typical recall@10 drop: 2-8% compared to exact search. Measure on your data.

## IVF-PQ: combining both

The production combination for large-scale search:

```python
index = faiss.IndexIVFPQ(quantizer, 1536, nlist=8192, m=48, nbits=8)
index.train(training_vectors)
index.add(all_vectors)
index.nprobe = 64
```

IVF reduces the number of vectors to compare. PQ reduces the cost of each comparison. Together they enable billion-vector search on a single machine.

## IVF-PQ vs HNSW

| Aspect | HNSW | IVF-PQ |
|---|---|---|
| Memory | High (full vectors + graph) | Low (compressed vectors) |
| Recall | Excellent (95-99%) | Good (85-95%) |
| Latency | Low (5-20ms) | Moderate (10-50ms) |
| Insert | Incremental | Batch-oriented |
| Training | None | Requires training pass |
| Scale | Up to ~50M per node | Billions per node |

## pgvector IVFFlat

pgvector supports IVFFlat (IVF without PQ):

```sql
CREATE INDEX ON documents
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Tune probes at query time
SET ivfflat.probes = 20;
```

No product quantization in pgvector — vectors are stored at full precision. IVFFlat is pgvector's memory-conscious option, but HNSW is generally preferred when data fits in RAM.

## When to use each index type

```
Dataset size?
├── < 1M vectors → Flat (exact search, no index needed)
├── 1M - 50M, fits in RAM → HNSW (best recall-latency)
├── 50M - 500M, memory pressure → IVF-Flat (full vectors, clustered)
└── > 500M or memory-critical → IVF-PQ (compressed, billion-scale)
```

## Training best practices

IVF indexes need training data representative of the full dataset:

- Use at least `nlist` vectors for training (more is better)
- Sample randomly if the full dataset is too large for training
- Retrain when data distribution shifts significantly (new embedding model, new content type)
- In FAISS, `train()` on a random subset of 100K-1M vectors works well for most cases

## Optimized query pipeline

For maximum recall with IVF-PQ, use a two-stage approach:

1. **Coarse search** — IVF-PQ retrieves top-100 candidates cheaply
2. **Rerank** — compute exact distance on the 100 candidates, return top-10

```python
distances, indices = ivfpq_index.search(query, k=100)
candidates = [all_vectors[i] for i in indices[0]]
exact_distances = np.linalg.norm(candidates - query, axis=1)
top_10 = np.argsort(exact_distances)[:10]
```

This recovers most of the recall lost to PQ compression with minimal extra compute.

## Common production mistakes

Teams get vector search ivf pq index wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of vector search ivf pq index fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When vector search ivf pq index misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [FAISS wiki: IVF indexes](https://github.com/facebookresearch/faiss/wiki/Faiss-indexes)
- [FAISS product quantization guide](https://github.com/facebookresearch/faiss/wiki/Vector-codecs)
- [FAISS IndexIVFPQ documentation](https://faiss.ai/cpp_api/struct/structfaiss_1_1IndexIVFPQ.html)
- [pgvector IVFFlat](https://github.com/pgvector/pgvector#ivfflat)
- [Billion-scale similarity search with GPUs (Johnson et al.)](https://arxiv.org/abs/1702.08734)
