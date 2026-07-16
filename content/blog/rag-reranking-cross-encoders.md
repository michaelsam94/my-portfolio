---
title: "Reranking with Cross-Encoders"
slug: "rag-reranking-cross-encoders"
description: "Add cross-encoder reranking to RAG pipelines: joint query-document scoring for higher precision after bi-encoder retrieval."
datePublished: "2025-01-20"
dateModified: "2025-01-20"
tags: ["AI", "RAG", "Reranking", "Cross-Encoders"]
keywords: "cross-encoder reranking, RAG reranker, Cohere rerank, sentence transformers, retrieval precision, two-stage retrieval"
faq:
  - q: "What is a cross-encoder and how does it differ from a bi-encoder?"
    a: "A bi-encoder embeds query and document independently, then compares vectors with cosine similarity — fast but imprecise. A cross-encoder feeds query and document together through a transformer and outputs a single relevance score — slow but precise because attention layers can model interactions between every query and document token. Cross-encoders are rerankers, not primary search engines."
  - q: "How many candidates should I rerank?"
    a: "Rerank 50–100 candidates from bi-encoder or hybrid search, then pass the top 5–10 to the LLM. Reranking 500 candidates with a cross-encoder adds seconds of latency with diminishing returns. Start with top-100 rerank to top-10 and tune based on your precision-latency tradeoff measured on the eval set."
  - q: "Should I use Cohere Rerank or a self-hosted cross-encoder?"
    a: "Cohere Rerank offers strong out-of-box quality with no infrastructure to manage — good for fast deployment and moderate volume. Self-hosted models like ms-marco-MiniLM give you data privacy, no per-call API cost, and customization at the cost of GPU infrastructure. Evaluate both on your domain; generic rerankers sometimes underperform on specialized terminology."
---

Bi-encoder retrieval returned 20 chunks about "authentication" when the user asked about "OAuth token refresh for service accounts." Chunk 14 was the right answer — buried because its single-vector embedding averaged over an entire auth guide. Cross-encoder reranking scores each query-document pair jointly, catching that chunk 14's text specifically discusses service account token refresh even though its bi-encoder vector looked generically auth-related.

## Two-stage retrieval architecture

Production RAG uses two stages:

1. **First stage (retrieval)** — fast bi-encoder, BM25, or hybrid search over the full corpus. High recall, moderate precision. Returns 50–100 candidates.
2. **Second stage (reranking)** — cross-encoder scores each candidate against the query. High precision. Returns top 5–10.

```python
def two_stage_retrieve(query: str, top_k: int = 5) -> list[Document]:
    candidates = hybrid_search(query, top_k=100)
    pairs = [(query, doc.text) for doc in candidates]
    scores = cross_encoder.predict(pairs)
    ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
    return [doc for doc, _ in ranked[:top_k]]
```

Never run cross-encoders over your entire corpus at query time. At 50ms per pair, 100,000 documents would take 83 minutes.

## Cross-encoder models

**Self-hosted options:**

```python
from sentence_transformers import CrossEncoder

model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
scores = model.predict([
    ("OAuth token refresh service accounts", doc.text)
    for doc in candidates
])
```

Popular models:
- `cross-encoder/ms-marco-MiniLM-L-6-v2` — fast, good general quality.
- `cross-encoder/ms-marco-MiniLM-L-12-v2` — slower, higher quality.
- Domain-fine-tuned models for legal, medical, or code search.

**API-based options:**

```python
import cohere

response = cohere_client.rerank(
    model="rerank-english-v3.0",
    query="OAuth token refresh for service accounts",
    documents=[doc.text for doc in candidates],
    top_n=5,
)
```

Cohere Rerank, Jina Reranker, and Voyage Rerank offer managed APIs with strong quality and no GPU management.

## Integrating reranking into the full pipeline

```python
def rag_pipeline(query: str) -> str:
    # Stage 1: Hybrid retrieval (cast wide net)
    bm25_results = bm25_search(query, top_k=50)
    vector_results = vector_search(embed(query), top_k=50)
    candidates = reciprocal_rank_fusion([bm25_results, vector_results])

    # Stage 2: Cross-encoder rerank (precision filter)
    top_chunks = cross_encoder_rerank(query, candidates[:100], top_k=5)

    # Stage 3: Generate
    return llm_generate(query, top_chunks)
```

Each stage has a distinct job. Removing any stage shifts the failure mode — no hybrid search means missed recall; no reranking means noisy context.

## Latency optimization

Cross-encoder reranking is the slowest retrieval stage. Optimize:

- **Batch scoring** — cross-encoders batch pairs efficiently on GPU. Score all 100 candidates in one call, not 100 sequential calls.
- **Truncate documents** — most cross-encoders have input limits (512 tokens typical). Truncate candidate text to the limit; the most relevant content usually appears early in chunks.
- **Cascade reranking** — use a fast cross-encoder (MiniLM-6) to cut 100 → 20, then a stronger model (MiniLM-12 or Cohere) to cut 20 → 5.
- **Cache** — cache reranker scores for identical query-document pairs in high-traffic scenarios.

```python
def cascade_rerank(query: str, candidates: list, top_k: int = 5):
    # Fast filter: 100 → 20
    scores_fast = fast_cross_encoder.predict([(query, d.text) for d in candidates])
    top_20 = [c for c, _ in sorted(zip(candidates, scores_fast),
                                    key=lambda x: x[1], reverse=True)[:20]]
    # Precise filter: 20 → 5
    scores_precise = precise_cross_encoder.predict([(query, d.text) for d in top_20])
    return [d for d, _ in sorted(zip(top_20, scores_precise),
                                    key=lambda x: x[1], reverse=True)[:top_k]]
```

## Fine-tuning rerankers on your domain

Generic MS MARCO rerankers handle general web search well. Specialized corpora benefit from fine-tuning:

1. Collect query-document relevance pairs from your eval set and production logs.
2. Fine-tune a cross-encoder with binary or graded relevance labels.
3. Evaluate on held-out queries — domain-tuned rerankers often gain 5–15% precision over generic models on technical corpora.

Even 500–1000 labeled pairs can improve reranking on domain-specific terminology.

## Measuring reranker impact

On your eval set, compare:

1. Hybrid search top-5 (no reranking).
2. Hybrid top-100 → cross-encoder rerank → top-5.
3. Hybrid top-100 → ColBERT rerank → top-5 (alternative).

Measure precision@5 (are the top 5 actually relevant?) and end-to-end answer accuracy. Reranking typically improves precision@5 by 15–30% over bi-encoder alone. Diminishing returns appear beyond top-100 candidate pools. Log reranker latency separately from retrieval latency so you can tune pool size against your p95 budget.

## Two-stage retrieval architecture

Standard production RAG retrieval pipeline:

```
Query
  ↓
Stage 1: Bi-encoder (fast, approximate)
  → top-100 candidates in ~10ms
  ↓
Stage 2: Cross-encoder reranker (slow, precise)
  → top-5 in ~200ms
  ↓
LLM generation with top-5 context
```

```python
async def retrieve_and_rerank(query: str, k: int = 5) -> list[Document]:
    # Stage 1: fast bi-encoder retrieval
    candidates = await bi_encoder_search(query, top_k=100)

    # Stage 2: cross-encoder reranking
    pairs = [(query, doc.text) for doc in candidates]
    scores = cross_encoder.predict(pairs)

    ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
    return [doc for doc, _ in ranked[:k]]
```

Tune candidate pool size against latency budget: 50 candidates ≈ 100ms rerank, 100 candidates ≈ 200ms, 200 candidates ≈ 400ms.

## Managed reranking APIs

Avoid self-hosting cross-encoders at moderate scale:

```python
import cohere

# Cohere Rerank API
results = cohere_client.rerank(
    model="rerank-english-v3.0",
    query=query,
    documents=[doc.text for doc in candidates],
    top_n=5,
)

# Jina Reranker API — similar interface
# Cohere Rerank: ~$1 per 1000 searches at top-100
```

Managed APIs handle model updates, scaling, and batching. Self-host when volume exceeds ~100k reranks/day.

## Reranker-free alternatives

When latency budget is tight (<100ms total):

| Approach | Latency | Quality |
|---|---|---|
| Bi-encoder only | ~10ms | Baseline |
| Hybrid (BM25 + bi-encoder) | ~20ms | +10% precision |
| ColBERT (late interaction) | ~50ms | +15% precision |
| Cross-encoder rerank | ~200ms | +25% precision |

ColBERT stores token-level embeddings — faster than cross-encoder, better than bi-encoder. Good middle ground for latency-sensitive RAG.

## Failure modes

- **Reranking all documents** — cross-encoder on full corpus; use bi-encoder first
- **Pool size too small (<20)** — misses relevant documents bi-encoder ranked low
- **Pool size too large (>200)** — latency exceeds p95 budget
- **Generic reranker on domain corpus** — fine-tune on 500+ domain pairs for 5–15% gain
- **Reranker latency not logged separately** — can't tune pool size against budget

## Production checklist

- Two-stage: bi-encoder top-100 → cross-encoder top-5
- Reranker latency logged separately from retrieval latency
- Pool size tuned against p95 latency budget (typically 100 candidates)
- precision@5 measured on eval set before and after reranker
- Domain fine-tune when generic reranker underperforms on technical corpus
- Managed rerank API (Cohere/Jina) unless volume >100k/day

## Resources

- [Sentence Transformers cross-encoders](https://www.sbert.net/docs/pretrained_cross-encoders.html)
- [Cohere Rerank API documentation](https://docs.cohere.com/reference/rerank)
- [MS MARCO cross-encoder models](https://huggingface.co/cross-encoder)
- [Jina Reranker API](https://jina.ai/reranker/)
- [LlamaIndex reranker modules](https://docs.llamaindex.ai/en/stable/module_guides/querying/reranker/)
