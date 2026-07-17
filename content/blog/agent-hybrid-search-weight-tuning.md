---
title: "Hybrid Search Weight Tuning for RAG Agents"
slug: "agent-hybrid-search-weight-tuning"
description: "Tune BM25 and vector fusion weights for agent retrieval—Reciprocal Rank Fusion, normalized score blending, offline eval harnesses, and per-tenant calibration without overfitting your golden set."
datePublished: "2025-04-12"
dateModified: "2025-04-12"
tags: ["AI Agents", "RAG", "Search", "Retrieval"]
keywords: "hybrid search weight tuning, BM25 vector fusion, reciprocal rank fusion, RAG retrieval, Elasticsearch hybrid query, agent search ranking"
faq:
  - q: "When should agent stacks use hybrid search instead of vectors alone?"
    a: "Use hybrid when queries contain exact identifiers (SKUs, error codes, API method names), rare proper nouns, or version strings that embeddings smear. Pure vector search excels at paraphrase; BM25 excels at lexical precision. Agent tool-selection and code search almost always need both."
  - q: "Is Reciprocal Rank Fusion better than weighted score sum?"
    a: "RRF is more robust when BM25 and cosine scores live on incomparable scales—common across Elasticsearch, pgvector, and Pinecone backends. Weighted sum works when you calibrate scores to [0,1] on representative traffic and renormalize after index changes. Start with RRF; move to weighted sum only if eval shows consistent gains."
  - q: "How many labeled queries do you need to tune fusion weights?"
    a: "A minimum of 200–500 diverse queries with graded relevance (0/1/2) per domain slice—support docs, internal wiki, code. Split train/validation/test by query cluster, not random rows, to avoid leakage. Tune on validation; report once on held-out test. Fewer than 100 queries and you are memorizing noise."
  - q: "Should fusion weights differ per tenant or agent persona?"
    a: "Yes, when corpora differ materially—legal tenants weight exact citation matching higher; coding agents weight symbol overlap. Store weights in tenant config with a global default. Re-evaluate quarterly or after major index migrations. Never tune per user session; that overfits and is not reproducible."
---

Our support agent retrieved the wrong runbook three times in a row for the same ticket. The query was `ERR_CONN_POOL_EXHAUSTED v2.14` — exact error string, exact version. Pure vector search ranked a generic "connection troubleshooting" doc first because the embedding captured semantic neighborhood. BM25 alone missed a paraphrased fix in a newer doc that never indexed the literal token. **Hybrid search** returned both signals; the failure was the **fusion weight**: we had `alpha=0.9` toward vectors because "semantic search feels smarter." Lexical precision was starved.

Hybrid retrieval is default for production RAG agents now. The engineering work is not wiring two indexes — it is **tuning how scores combine** so identifier-heavy queries and conceptual queries both win, without hand-tuning per query type forever.

## Hybrid retrieval architecture

A typical agent retrieval path:

```
User query ──► Query rewriter (optional)
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
    BM25 index            Vector index
    (inverted)            (HNSW / IVF)
         │                     │
         └──────────┬──────────┘
                    ▼
              Fusion layer
                    ▼
            Reranker (optional)
                    ▼
              Top-k chunks → LLM context
```

Fusion happens **before** the cross-encoder reranker in most stacks. Rerankers are expensive; fusion cheaply filters the candidate pool from thousands to dozens.

## Fusion strategies compared

| Method | Formula intuition | Pros | Cons |
|--------|-------------------|------|------|
| Linear blend | `w * vec + (1-w) * bm25` | Simple, one knob | Needs score normalization |
| Reciprocal Rank Fusion | `Σ 1/(k + rank_i)` | Scale-free, robust | Less control per signal |
| CombSUM (normalized) | Sum of min-max normalized scores | Interpretable weights | Sensitive to outlier scores |
| Learned LTR | GBDT on features | Best ceiling | Needs labels, ops burden |

For most agent teams, start with **RRF** or **linear blend on normalized scores**. Graduate to learning-to-rank only when you have labeled data pipelines and an owner for model refresh.

## Reciprocal Rank Fusion implementation

RRF ignores raw scores and uses ranks only — ideal when Elasticsearch `_score` and pgvector cosine distance are incomparable:

```python
from dataclasses import dataclass
from collections import defaultdict

@dataclass
class ScoredDoc:
    doc_id: str
    score: float

def reciprocal_rank_fusion(
    bm25_results: list[ScoredDoc],
    vector_results: list[ScoredDoc],
    k: int = 60,
    weights: tuple[float, float] = (1.0, 1.0),
) -> list[tuple[str, float]]:
    """RRF with optional per-list weight multipliers."""
    fused: dict[str, float] = defaultdict(float)

    for rank, doc in enumerate(bm25_results, start=1):
        fused[doc.doc_id] += weights[0] * (1.0 / (k + rank))

    for rank, doc in enumerate(vector_results, start=1):
        fused[doc.doc_id] += weights[1] * (1.0 / (k + rank))

    return sorted(fused.items(), key=lambda x: x[1], reverse=True)
```

The constant `k=60` comes from the original RRF paper; values between 20 and 100 rarely move nDCG@10 more than 0.02 on agent corpora. **Weights** `(w_bm25, w_vec)` skew toward lexical or semantic lists — that is your primary tuning surface under RRF.

## Weighted linear fusion with normalization

When both backends expose scores you can calibrate, linear fusion gives direct control:

```python
import numpy as np

def min_max_normalize(scores: np.ndarray) -> np.ndarray:
    lo, hi = scores.min(), scores.max()
    if hi - lo < 1e-9:
        return np.ones_like(scores)
    return (scores - lo) / (hi - lo)

def fuse_linear(
    bm25: list[ScoredDoc],
    vector: list[ScoredDoc],
    alpha: float,  # weight on vector; BM25 gets (1 - alpha)
) -> list[tuple[str, float]]:
    bm25_map = {d.doc_id: d.score for d in bm25}
    vec_map = {d.doc_id: d.score for d in vector}
    all_ids = set(bm25_map) | set(vec_map)

    bm25_arr = np.array([bm25_map.get(i, 0.0) for i in all_ids])
    vec_arr = np.array([vec_map.get(i, 0.0) for i in all_ids])

    bm25_norm = min_max_normalize(bm25_arr)
    vec_norm = min_max_normalize(vec_arr)

    fused_scores = alpha * vec_norm + (1 - alpha) * bm25_norm
    id_list = list(all_ids)
    ranked = sorted(zip(id_list, fused_scores), key=lambda x: x[1], reverse=True)
    return ranked
```

**Critical detail:** normalize **per query**, not globally across the index. Global min/max from offline stats goes stale after reindexing.

## Elasticsearch hybrid query pattern

If you use Elasticsearch 8.x dense_vector + text:

```json
{
  "size": 50,
  "query": {
    "hybrid": {
      "queries": [
        {
          "match": {
            "content": {
              "query": "{{query}}",
              "boost": 0.4
            }
          }
        },
        {
          "knn": {
            "field": "embedding",
            "query_vector": "{{embedding}}",
            "k": 50,
            "num_candidates": 200,
            "boost": 0.6
          }
        }
      ]
    }
  },
  "rank": {
    "rrf": {
      "window_size": 50,
      "rank_constant": 60
    }
  }
}
```

Map `boost` values to your `(w_bm25, w_vec)` experiments. After index settings change (new analyzer, different HNSW `ef_construction`), re-run validation — boosts are not portable across index versions.

## Offline evaluation harness

Tuning without measurement is guessing. Build a harness that replays labeled queries:

```python
# eval/hybrid_tuning.py
from sklearn.metrics import ndcg_score
import itertools

def evaluate_alpha(
    dataset: list[dict],
    alpha_values: list[float],
) -> dict[float, float]:
    """dataset item: {query, bm25_hits, vector_hits, relevance: {doc_id: 0|1|2}}"""
    results = {}
    for alpha in alpha_values:
        ndcgs = []
        for item in dataset:
            fused = fuse_linear(item["bm25_hits"], item["vector_hits"], alpha)
            ranked_ids = [doc_id for doc_id, _ in fused[:10]]
            rel = [item["relevance"].get(d, 0) for d in ranked_ids]
            ideal = sorted(item["relevance"].values(), reverse=True)[:10]
            if sum(ideal) == 0:
                continue
            ndcgs.append(ndcg_score([ideal], [rel], k=10))
        results[alpha] = sum(ndcgs) / len(ndcgs) if ndcgs else 0.0
    return results

# Grid search — coarse then fine
coarse = evaluate_alpha(val_set, [0.0, 0.25, 0.5, 0.75, 1.0])
best_coarse = max(coarse, key=coarse.get)
fine_grid = [best_coarse - 0.1, best_coarse, best_coarse + 0.1]
fine = evaluate_alpha(val_set, [a for a in fine_grid if 0 <= a <= 1])
```

Log **per-segment** metrics: `identifier_query`, `conceptual_query`, `multi_hop`. A global optimum hides regressions — high alpha helps paraphrase questions but destroys SKU lookup.

## Query-type routing without ML

Hard-coded routing beats a bad global weight when query shapes are obvious:

```typescript
export function fusionWeights(query: string): { alpha: number; rrfWeights: [number, number] } {
  const hasErrorCode = /\b[A-Z]{2,}_[A-Z0-9_]+\b/.test(query);
  const hasVersion = /\bv?\d+\.\d+(\.\d+)?\b/.test(query);
  const hasQuotedExact = /"[^"]+"/.test(query);

  if (hasErrorCode || hasVersion || hasQuotedExact) {
    return { alpha: 0.25, rrfWeights: [1.5, 1.0] }; // favor BM25
  }

  if (query.split(/\s+/).length <= 3) {
    return { alpha: 0.45, rrfWeights: [1.2, 1.0] }; // short keyword-ish
  }

  return { alpha: 0.65, rrfWeights: [1.0, 1.0] }; // default conceptual
}
```

Validate routers on the eval set — regex routing adds maintenance debt if patterns misfire on multilingual queries.

## Production observability

Ship fusion metadata with each retrieval for debugging:

```json
{
  "query_id": "q_8f3a",
  "fusion": {
    "method": "rrf",
    "k": 60,
    "weights": [1.5, 1.0],
    "bm25_top": ["doc_12", "doc_44"],
    "vector_top": ["doc_99", "doc_12"],
    "fused_top": ["doc_12", "doc_99", "doc_44"]
  }
}
```

Dashboards worth building:

- **MRR@k delta** if BM25-only vs vector-only vs hybrid (sampled online with human labels)
- **Click-through on cited chunks** — proxy for retrieval quality in agent answers
- **Abstain / "I don't know" rate** — bad fusion often increases hallucination pressure

Alert when fused results diverge completely from both lists (Jaccard similarity < 0.1 on top-5) — often signals index skew or embedding model drift.

## Per-tenant calibration

Store weights in tenant config:

```yaml
# tenants/acme-corp/retrieval.yaml
fusion:
  method: rrf
  rank_constant: 60
  weights: [1.8, 1.0]   # legal corpus: citation matching matters
  rerank_top_n: 30

# tenants/eng-platform/retrieval.yaml
fusion:
  method: linear
  alpha: 0.35           # code search: symbols and imports are lexical
  rerank_top_n: 50
```

Promotion workflow: tune on tenant validation set → canary 5% of retrieval traffic → compare answer-level eval and latency → full rollout. Rollback is a config flip, not a reindex.

## Common failure modes

**Overfitting the golden set.** Twenty demo queries tuned until the CEO demo works — production regresses. Hold out a test set nobody tuned against.

**Ignoring negative relevance.** nDCG with only positive labels misses "this doc must never appear" constraints. Track precision@k on hard negatives (similar but wrong version docs).

**Stale weights after embedding model swap.** New model changes vector ranking entirely; BM25 weights unchanged. Re-run grid search after any embedding endpoint version bump.

**Double-counting near-duplicate chunks.** Fusion boosts the same passage indexed twice under different IDs. Deduplicate by `parent_chunk_id` before fusion.

**Latency blowup from wide retrieval windows.** Fetching top-200 from each list for RRF is safe offline; online, cap at 50 unless reranker recall suffers measurably.

## Interaction with rerankers

Cross-encoders reorder the fused top-30. If fusion weights are badly skewed, the reranker never sees the right doc in its window — no amount of reranker quality fixes that. Diagnostic: run reranker on the **union** of BM25 and vector top-50 offline; if nDCG jumps massively, fusion is the bottleneck, not reranking.

Typical stack: hybrid top-50 → cross-encoder top-8 → LLM. Tune fusion first; tune reranker threshold second.

## The takeaway

Hybrid search weight tuning is the difference between an agent that finds the exact runbook and one that confidently summarizes the wrong doc. Start with RRF for scale-free fusion, grid-search alpha or RRF weights on a segmented eval set, route obvious query shapes with explicit rules, and store per-tenant configs you can canary and rollback. Measure on held-out queries, log fusion decisions in production, and re-tune after every embedding or analyzer change — weights are not write-once constants.

## Resources

- [Cormack, Clarke, Buettcher — Reciprocal Rank Fusion (2009)](https://plg.uwaterloo.ca/~gvcormac/cormac/recent/)
- [Elasticsearch — Hybrid search and RRF](https://www.elastic.co/guide/en/elasticsearch/reference/current/knn-search.html)
- [OpenSearch — Hybrid query documentation](https://opensearch.org/docs/latest/query-dsl/compound/hybrid/)
- [Pyserini — BM25 baselines for retrieval eval](https://github.com/castorini/pyserini)
- [BEIR benchmark — Heterogeneous retrieval evaluation](https://github.com/beir-cellar/beir)
