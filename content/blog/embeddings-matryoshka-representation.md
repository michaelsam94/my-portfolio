---
title: "Matryoshka Embeddings for Flexible Dims"
slug: "embeddings-matryoshka-representation"
description: "Use Matryoshka representation learning to truncate embedding dimensions at runtime: train once, deploy multiple index tiers, and balance recall vs storage."
datePublished: "2025-12-13"
dateModified: "2025-12-13"
tags: ["AI", "Machine Learning", "Embeddings", "Optimization"]
keywords: "Matryoshka embeddings, flexible dimension embeddings, MRL truncation, OpenAI text-embedding-3, nested representation learning, embedding dimension tradeoff"
faq:
  - q: "What are Matryoshka embeddings?"
    a: "Matryoshka Representation Learning (MRL) trains embeddings so the first d dimensions of a larger vector form a useful sub-vector for retrieval — like nested dolls. You can truncate to 256, 512, or 768 dimensions at query time without retraining separate models, trading recall for storage and speed."
  - q: "How much recall do I lose when truncating dimensions?"
    a: "On well-trained MRL models, truncating to 50% of dimensions often retains 95%+ of full-dimension recall@10 on standard benchmarks. Gains are model- and domain-specific — always benchmark on your query set. Non-MRL models degrade sharply when you simply slice prefix dimensions."
  - q: "Which models support Matryoshka embeddings out of the box?"
    a: "OpenAI text-embedding-3-small and text-embedding-3-large expose dimensions parameter at API call time. Open-source models like nomic-embed-text-v1.5 and some BGE checkpoints advertise MRL training. Verify with your eval harness before assuming prefix truncation works."
---

You shipped vector search at 3072 dimensions and the index fits — until the catalog triples. Re-embedding with a smaller model means dual indexes, migration downtime, and inconsistent scores across old and new vectors. Matryoshka embeddings fix the dimensionality trade-off at training time: the model learns that the first 256 components already encode most semantic signal, with each additional prefix dimension refining distance estimates. One trained model, multiple deployment profiles — 256-dim for mobile edge cache, 1536-dim for server rerank — without maintaining separate encoders.

## How MRL training works

Standard contrastive loss on full-dimension vectors plus auxiliary losses on truncated prefixes:

\[
\mathcal{L} = \sum_{d \in \{64,128,256,...,D\}} w_d \cdot \mathcal{L}_{\text contrastive}(x_{1:d}, y_{1:d})
\]

Each prefix must be independently useful for matching — not just padding that only makes sense at full D.

OpenAI exposes this via API:

```python
from openai import OpenAI
client = OpenAI()

response = client.embeddings.create(
    model="text-embedding-3-large",
    input="reset password for SSO tenant",
    dimensions=256,  # truncate Matryoshka-trained vector
)
vec = response.data[0].embedding  # length 256
```

Open-source with Sentence Transformers — use checkpoints trained with MRL loss (nomic, some BGE variants).

## Storage and latency math

For N vectors, float32 storage ≈ `N × d × 4` bytes.

| Dimensions | Bytes/vector | 10M vectors |
|------------|--------------|-------------|
| 3072 | 12,288 | ~115 GB |
| 768 | 3,072 | ~29 GB |
| 256 | 1,024 | ~9.6 GB |

HNSW search latency scales sublinearly with d but constant factors matter at scale. Truncation reduces RAM and improves cache locality.

## Tiered retrieval pattern

```
Query ──► embed @ 256d ──► coarse HNSW (full catalog)
                │
                ▼ top 500 ids
         re-fetch stored 1536d vectors (or re-embed docs)
                │
                ▼
         cosine rerank ──► top 20
```

Store full-dimension vectors on disk/object storage; keep short prefixes in RAM index. Alternatively store both prefixes in one record with offset layout.

Do not truncate non-MRL models and expect this to work — arbitrary prefix slicing on legacy embeddings scrambles ranking.

## Evaluating truncation on your data

```python
import numpy as np

def recall_at_k(full_embs, trunc_dim, queries, relevant, k=10):
    q = queries[:, :trunc_dim]
    d = full_embs[:, :trunc_dim]
    q = q / np.linalg.norm(q, axis=1, keepdims=True)
    d = d / np.linalg.norm(d, axis=1, keepdims=True)
    sims = q @ d.T
    # argsort, compute recall...
```

Plot recall@10 vs dimension {64, 128, 256, 512, full}. Pick the knee where marginal recall per megabyte drops.

## Training your own MRL head

Fine-tuning existing encoders with nested losses (simplified sketch):

```python
# pseudo: sum losses over truncations
for d in [64, 128, 256, 512]:
    z_q = F.normalize(q_emb[:, :d], dim=-1)
    z_d = F.normalize(d_emb[:, :d], dim=-1)
    loss += weighted_contrastive(z_q, z_d)
```

Weights often increase with d — full dimension dominates but small prefixes must still pull their weight.

## Operational notes

- **Index versioning** — document which truncation level each index uses.
- **Score calibration** — cosine scores at 256d are not comparable to 1536d; do not merge ranked lists naively.
- **Consistency** — query and document must use same truncation at each stage.

Matryoshka embeddings turn dimensionality from a one-way door into a runtime knob — valuable when catalog growth and infra cost share the roadmap with search quality.

## Open-source MRL models

Several open models support Matryoshka truncation without retraining:

| Model | Full dim | Truncation dims | License |
|---|---|---|---|
| nomic-embed-text-v1.5 | 768 | 64, 128, 256, 512, 768 | Apache 2.0 |
| OpenAI text-embedding-3-large | 3072 | 256, 1024, 3072 | API |
| jina-embeddings-v3 | 1024 | 32, 64, 128, 256, 512, 1024 | CC-BY-NC |

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("nomic-ai/nomic-embed-text-v1.5")
full_emb = model.encode("query text")           # 768d
fast_emb = model.encode("query text", truncate_dim=128)  # 128d
```

Use `truncate_dim` at query time — same model, different index granularity per use case.

## Two-stage retrieval with MRL

Stage 1: fast coarse search at low dimension. Stage 2: rerank top-K at full dimension:

```python
def search(query, catalog, k=10):
    # Stage 1: 128d index — fast, approximate
    coarse_emb = model.encode(query, truncate_dim=128)
    candidates = index_128d.search(coarse_emb, k=200)

    # Stage 2: full 768d rerank — precise
    full_emb = model.encode(query)  # 768d
    candidate_embs = [catalog[id].full_emb for id in candidates]
    scores = [cosine(full_emb, c) for c in candidate_embs]
    return sorted(zip(candidates, scores), key=lambda x: -x[1])[:k]
```

128d index is 6× smaller than 768d — fits in L3 cache. Rerank 200 candidates at full dimension adds ~2ms vs 50ms for full-dimension search over entire catalog.

## Index sizing with MRL

```
Catalog: 10M documents

768d float32 index: 10M × 768 × 4 bytes = 30 GB
128d float32 index: 10M × 128 × 4 bytes =  5 GB
128d int8 index:    10M × 128 × 1 byte  =  1.3 GB
```

MRL lets you choose the memory/latency tradeoff at deployment time — not at model selection time. Start with 128d index; upgrade to 256d if recall insufficient.

## Failure modes

- **Query at 128d, index at 768d** — dimension mismatch; silent garbage results
- **Score comparison across dimensions** — cosine at 128d ≠ cosine at 768d; don't merge ranked lists
- **Truncation without MRL-trained model** — arbitrary truncation destroys semantic quality
- **No rerank stage** — low-dimension recall loss unacceptable for precision-critical apps
- **Index version mismatch** — query uses v2 model, index built with v1

## Production checklist

- Query and index use same truncation dimension per stage
- MRL-trained model used (not arbitrary truncation)
- Two-stage retrieval: coarse (low-d) + rerank (full-d)
- Index dimension documented in index metadata
- Recall@K evaluated at each truncation level before deployment
- Model version tagged on all index entries

## Resources

- [Matryoshka Representation Learning paper](https://arxiv.org/abs/2205.13147)
- [OpenAI embedding models guide](https://platform.openai.com/docs/guides/embeddings)
- [Nomic embed — open MRL model](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5)
- [Sentence Transformers documentation](https://www.sbert.net/)
- [FAISS index types and memory trade-offs](https://github.com/facebookresearch/faiss/wiki/Faiss-indexes)
