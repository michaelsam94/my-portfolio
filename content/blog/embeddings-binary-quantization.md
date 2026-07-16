---
title: "Binary Quantization for Vector Search"
slug: "embeddings-binary-quantization"
description: "Compress embedding vectors with binary quantization: Hamming distance, recall trade-offs, two-stage retrieval, and implementation with FAISS and pgvector."
datePublished: "2025-12-04"
dateModified: "2025-12-04"
tags: ["AI", "Machine Learning", "Embeddings", "Vector Search"]
keywords: "binary quantization embeddings, Hamming distance vector search, FAISS binary vectors, embedding compression, two-stage retrieval, scalar quantization vs binary, pgvector binary"
faq:
  - q: "How much storage does binary quantization save?"
    a: "A float32 embedding of dimension 768 uses 3072 bytes raw. Binary quantization packs one bit per dimension into 96 bytes — roughly 32× compression. With residual or scalar-quantized reranking, you keep most recall while serving coarse search from compact codes."
  - q: "Does binary quantization work with cosine similarity?"
    a: "Binary quantization typically uses sign bits of each dimension (or learned thresholds), and search uses Hamming distance or inner product on ±1 encodings as a proxy. For cosine-heavy pipelines, L2-normalize before binarization and rerank top candidates with full-precision cosine on the shortlist."
  - q: "What recall should I expect from binary-only search?"
    a: "Recall@10 without reranking often lands 60–85% depending on dimensionality and data distribution — unacceptable alone for production. Use binary search as stage one (retrieve 100–500 candidates) and float rerank stage two. Measure recall@k on your held-out query set."
---

Your vector index holds forty million product embeddings at 1536 dimensions float32 — roughly 240 GB of vectors before metadata. Monthly infra bill says shrink or shard aggressively. Binary quantization stores one bit per dimension instead of thirty-two, turning each vector into a compact bitmask where nearest-neighbor search becomes Hamming distance on popcount instructions GPUs and CPUs execute cheaply. The catch: coarse bins lose nuance. Production systems use binary quantization as a first-stage funnel, not the final ranking.

## From float vectors to binary codes

Given L2-normalized vector **x**, a simple sign binarization:

\[
b_i = \begin{cases} 1 & \text{if } x_i \geq 0 \\ 0 & \text{otherwise} \end{cases}
\]

Pack bits into `uint8` arrays:

```python
import numpy as np

def binarize(x: np.ndarray) -> np.ndarray:
    x = x / (np.linalg.norm(x) + 1e-9)
    bits = (x >= 0).astype(np.uint8)
    # pack 8 bits per byte
    return np.packbits(bits)

def hamming(a: bytes, b: bytes) -> int:
    return sum(bin(x ^ y).count('1') for x, y in zip(a, b))
```

Learned thresholds or PCA-rotation before binarization (ScaNN, Matryoshka pipelines) improve recall versus raw sign bits.

## Two-stage retrieval architecture

```
Query float embedding
        │
        ▼
┌───────────────────┐
│ Stage 1: Binary   │  ← scan millions, Hamming top-200
│ index (RAM/GPU)   │
└─────────┬─────────┘
          ▼
┌───────────────────┐
│ Stage 2: Rerank   │  ← float cosine on 200 candidates
│ full precision    │
└─────────┬─────────┘
          ▼
     Top 10 results
```

Stage one minimizes bytes touched per query; stage two restores ranking quality. Tune candidate count `N` until recall@10 plateaus on your eval set.

## FAISS binary indexes

FAISS supports `IndexBinaryFlat` and `IndexBinaryIVF`:

```python
import faiss
import numpy as np

d = 768
nb = 1_000_000
xb = np.random.rand(nb, d).astype('float32')
faiss.normalize_L2(xb)

# Binarize
xb_bin = np.packbits((xb >= 0).astype(np.uint8), axis=1)

index = faiss.IndexBinaryFlat(d)  # d bits
index.add(xb_bin)

xq_bin = np.packbits((query >= 0).astype(np.uint8))
D, I = index.search(xq_bin.reshape(1, -1), k=200)
# rerank I[0] with float vectors
```

`IndexBinaryIVF` clusters for sublinear search on billion-scale with training overhead.

## PostgreSQL pgvector and extensions

Native pgvector stores float vectors; for binary pipelines store `bit(d)` or `bytea` codes in a separate column:

```sql
CREATE TABLE items (
  id bigint PRIMARY KEY,
  embedding vector(768),
  embedding_bin bit(768)
);

-- Hamming via XOR popcount pattern (extension-dependent)
-- Often stage-one in app or specialized extension (pgvector halfvec, vchord)
```

Many teams run stage one in Redis/Valkey with bitmap ops or a dedicated vector engine, stage two in Postgres for transactional consistency.

## Recall measurement

Build eval queries with known relevant documents:

```python
def recall_at_k(ranked_ids, relevant_set, k=10):
    return len(set(ranked_ids[:k]) & relevant_set) / len(relevant_set)
```

Compare:

1. Float HNSW baseline
2. Binary only
3. Binary + rerank N=100, 200, 500

Plot recall vs latency and storage. Binary shines when stage-one latency dominates and you can afford rerank CPU.

## When to skip binary quantization

- Small catalogs (<100k) where HNSW on float32 fits RAM
- Tasks needing precise distance calibration (scientific similarity)
- Dimensions below 64 where compression savings are modest relative to complexity

For billion-scale semantic search with tight p99 latency budgets, binary stage-one plus float rerank is the standard engineering compromise.

## Binary index implementation

FAISS BinaryFlatIndex for exact binary search:

```python
import faiss
import numpy as np

# Convert float embeddings to binary
def float_to_binary(embeddings: np.ndarray) -> np.ndarray:
    return (embeddings > 0).astype(np.uint8)

# Build binary index
d_binary = 128  # 128 bits = 16 bytes per vector
binary_embs = float_to_binary(float_embeddings)  # shape: (N, 128)
index = faiss.IndexBinaryFlat(d_binary)
index.add(binary_embs)

# Search
query_binary = float_to_binary(query_emb.reshape(1, -1))
distances, indices = index.search(query_binary, k=200)
```

Hamming distance via XOR + popcount — SIMD-accelerated on modern CPUs. 10M vectors × 16 bytes = 160MB — fits in RAM on modest hardware.

## Rescoring pipeline

Binary search returns approximate candidates; rescore with float embeddings:

```python
def search_with_rescore(query_float_emb, binary_index, float_store, k=10, candidates=200):
    query_binary = float_to_binary(query_float_emb.reshape(1, -1))
    _, candidate_ids = binary_index.search(query_binary, candidates)

    scores = [
        cosine_similarity(query_float_emb, float_store[id])
        for id in candidate_ids[0]
    ]
    ranked = sorted(zip(candidate_ids[0], scores), key=lambda x: -x[1])
    return ranked[:k]
```

Rescore 200 candidates at float precision adds ~1ms on CPU. Binary search over 10M vectors adds ~5ms. Total: ~6ms vs ~500ms for full float HNSW on 10M.

## Storage comparison at scale

```
10M vectors, 768 dimensions:

Float32 HNSW:  10M × 768 × 4B = 30 GB RAM
Float16 HNSW:  10M × 768 × 2B = 15 GB RAM
Binary + float store:
  Binary index: 10M × 96B  = 960 MB RAM
  Float store:  10M × 768 × 4B = 30 GB disk (not RAM)
  Total RAM: ~1 GB for stage-1
```

Binary index in RAM, float embeddings on SSD — query latency dominated by binary search (~5ms), not float store lookup (~1ms for 200 candidates).

## Failure modes

- **Binary search without rescore** — recall drops 10–20%; unacceptable for precision apps
- **Rescore too few candidates** — recall loss; tune candidates=200–500
- **Float and binary from different models** — dimension mismatch; rebuild both together
- **No eval at each stage** — binary recall unknown; measure separately
- **Binary index without float store** — can't rescore; precision unusable

## Production checklist

- Binary index for stage-1 candidate retrieval
- Float embedding store for stage-2 rescore
- Rescore candidates tuned: 200 minimum, eval recall@K at each level
- Recall@K evaluated: binary only vs binary+rescore vs float baseline
- Binary and float embeddings from same model version
- Index rebuild procedure documented for model updates

## Resources

- [FAISS wiki — binary indexes](https://github.com/facebookresearch/faiss/wiki/Faiss-indexes)
- [Google ScaNN research (quantization)](https://github.com/google-research/google-research/tree/master/scann)
- [pgvector extension documentation](https://github.com/pgvector/pgvector)
- [Hamming distance and SIMD popcount](https://en.wikipedia.org/wiki/Hamming_weight)
- [Efficient and robust approximate nearest neighbor search (Jégou et al.)](https://arxiv.org/abs/1002.4852)
