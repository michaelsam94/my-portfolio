---
title: "Cross-Encoder Reranking for Retrieval Pipelines"
slug: "rag-cross-encoder-reranking"
description: "Cross-encoder reranking for agent RAG — bi-encoder recall, pairwise scoring, batching, model selection, and latency budgets that keep retrieval quality without blocking tool loops."
datePublished: "2025-06-25"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Cross"]
keywords: "cross-encoder reranking, RAG retrieval, ms-marco MiniLM, Cohere rerank, agent tool latency, bi-encoder recall"
faq:
  - q: "When should RAG pipelines add a cross-encoder reranker?"
    a: "Add reranking when bi-encoder or BM25 recall@20 is acceptable but precision@5 is not — users see irrelevant chunks in agent context. Skip reranking for sub-200ms tool loops or corpora where lexical search already returns tight sets. Measure nDCG@5 offline before adding 80–150ms latency."
  - q: "How many candidates should you rerank?"
    a: "Rerank top-50 to top-100 from retrieval, return top-5 to top-10 to the LLM. Reranking 200+ pairs rarely improves quality enough to justify cost; reranking fewer than 20 leaves recall gains on the table. Adaptive top-k based on bi-encoder score spread saves budget on easy queries."
  - q: "Self-hosted cross-encoder vs Cohere Rerank API?"
    a: "Self-host ms-marco-MiniLM-L-6-v2 on CPU for 30–80ms on 50 pairs at moderate QPS. Cohere Rerank v3 wins on quality and ops simplicity at $1–3 per 1k searches — good for spiky retrieval traffic without GPU fleet. Hybrid: API fallback when local queue depth exceeds threshold."
---
Retrieval returned twenty chunks about "refund policy." Only one answered the user's actual question — whether partial refunds apply after 30 days for subscription downgrades. Bi-encoder embeddings ranked a generic FAQ highest because "refund" matched strongly; the specific downgrade clause sat at rank fourteen. A **cross-encoder reranker** rescored all twenty pairs with full query-document attention and promoted the correct paragraph to rank two. The generated answer changed from confidently wrong to precisely cited.

Cross-encoders are the standard second stage in production RAG: expensive per pair, accurate per pair. RAG stacks need them configured with explicit candidate counts, batching, timeouts, and fallback — not bolted on as an unbounded loop over the entire vector index.

## Bi-encoder vs cross-encoder architecture

| Stage | Model interaction | Indexable | Latency per 50 docs |
|-------|-------------------|-----------|---------------------|
| Bi-encoder | Separate encodings, dot product | Yes | 5–20ms retrieval |
| Cross-encoder | Joint transformer forward pass | No | 50–200ms |

```
User query ──► bi-encoder / BM25 ──► top-100 chunk IDs
                                         │
                                         ▼
              query + each chunk text ──► cross-encoder ──► relevance scores
                                         │
                                         ▼
                              top-10 chunks ──► agent context window
```

Bi-encoders compress meaning into fixed vectors — fast, lossy. Cross-encoders read query and document together — slow, precise. Agents live in the two-stage middle ground.

## Self-hosted reranker with sentence-transformers

`cross-encoder/ms-marco-MiniLM-L-6-v2` is the usual starting point — 80MB, CPU-viable, trained on MS MARCO passage ranking.

```python
# retrieval/rerank.py
from sentence_transformers import CrossEncoder
import numpy as np

class AgentReranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model = CrossEncoder(model_name, max_length=512)

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 10,
        batch_size: int = 32,
    ) -> list[tuple[int, float]]:
        if not documents:
            return []

        pairs = [[query, doc] for doc in documents]
        scores = self.model.predict(
            pairs,
            batch_size=batch_size,
            show_progress_bar=False,
        )
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]

# Usage in retrieval tool
def retrieve_and_rerank(query: str, vector_hits: list[dict]) -> list[dict]:
    texts = [h["text"] for h in vector_hits]
    ranked = reranker.rerank(query, texts, top_k=10)
    return [vector_hits[idx] | {"rerank_score": float(score)} for idx, score in ranked]
```

Truncate documents to 512 tokens **before** pairing — tail truncation loses concluding sentences in long runbooks. Prefer head+tail concat or parent-chunk retrieval.

## Batching, ONNX, and GPU placement

Throughput scales with batch size until memory bound:

```python
# Export ONNX for CPU inference servers (optional)
# optimum-cli export onnx --model cross-encoder/ms-marco-MiniLM-L-6-v2 onnx-reranker/

import onnxruntime as ort

session = ort.InferenceSession("onnx-reranker/model.onnx")

def predict_batch(pairs: list[list[str]], batch_size: int = 16) -> np.ndarray:
    all_scores = []
    for i in range(0, len(pairs), batch_size):
        batch = pairs[i : i + batch_size]
        # tokenize batch → run session → collect logits
        scores = run_onnx_batch(session, batch)
        all_scores.extend(scores)
    return np.array(all_scores)
```

For agent platforms above 100 QPS sustained, dedicate a reranker pod pool with HPA on queue depth — do not share GPU with LLM inference unless workload is batch-heavy overnight.

## API-based reranking (Cohere, Jina, Voyage)

Managed rerank removes model ops:

```typescript
async function cohereRerank(
  query: string,
  documents: string[],
  topN: number,
  apiKey: string,
): Promise<{ index: number; relevanceScore: number }[]> {
  const resp = await fetch("https://api.cohere.com/v1/rerank", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "rerank-v3.5",
      query,
      documents,
      top_n: topN,
      return_documents: false,
    }),
  });
  if (!resp.ok) throw new Error(`rerank failed: ${resp.status}`);
  const data = await resp.json();
  return data.results.map((r: { index: number; relevance_score: number }) => ({
    index: r.index,
    relevanceScore: r.relevance_score,
  }));
}
```

Cache rerank results by `(model_version, query_hash, doc_ids_hash)` for idempotent agent replays — eval harnesses hammer the same queries.

## Adaptive candidate count

Not every query needs 100 pairs scored. Use bi-encoder score dispersion:

```python
def adaptive_candidate_count(scores: list[float]) -> int:
    if len(scores) < 20:
        return len(scores)
    spread = scores[4] - scores[19]  # rank 5 vs rank 20
    if spread > 0.15:
        return 15   # clear separation — cheap rerank
    if spread > 0.08:
        return 35
    return 75       # flat scores — need deeper rerank
```

Log `spread` and `candidate_count` — flat distributions often indicate embedding model drift or corpus pollution.

## Latency budget integration

Cap rerank stage at 15–25% of retrieval tool p95 (see companion note on reranker latency budgets). Enforce deadlines:

```typescript
async function rerankWithDeadline(
  query: string,
  docs: string[],
  deadlineMs: number,
): Promise<number[]> {
  const budget = Math.max(deadlineMs - Date.now(), 0);
  if (budget < 20) {
    metrics.increment("rerank.skipped_deadline");
    return docs.map((_, i) => i); // preserve bi-encoder order
  }
  return Promise.race([
    reranker.rerank(query, docs),
    sleep(budget).then(() => {
      throw new TimeoutError("rerank");
    }),
  ]).catch(() => {
    metrics.increment("rerank.timeout");
    return docs.map((_, i) => i);
  });
}
```

Never block the agent silently — emit `rerank_degraded: true` in tool metadata so downstream prompts can widen disclaimers.

## Evaluation offline and online

Offline metrics on labeled query-chunk pairs:

- nDCG@5, MRR@10 before/after rerank
- Latency p50/p95 on production hardware
- Score calibration — cross-encoder logits are not probabilities; do not threshold at 0.5 without calibration

Online:

- Agent task success rate (human or LLM-judge)
- Citation accuracy — does the cited chunk contain the answer span?
- User thumbs-down correlated with rerank rank of cited chunk

A/B reranker model versions with feature flags; quality regressions hide in aggregate latency metrics.

## Multilingual and domain adaptation

ms-marco MiniLM is English-centric. Multilingual agents need `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` or API rerankers with locale headers. Domain-specific corpora (legal, medical) benefit from fine-tuned cross-encoders on in-house query-log pairs — even 5k labeled examples beat general models on tail terminology.

## Failure modes

- **Duplicate chunks** — near-identical passages steal top-k slots; dedupe by MinHash before rerank
- **Query-document length mismatch** — short query, long doc: cross-encoder overweight boilerplate headers
- **Stale index** — reranking 404 content that bi-encoder still returns; validate chunk existence
- **Prompt injection in corpus** — malicious doc text in cross-encoder input; sanitize retrieved HTML

## Hybrid retrieval fusion before rerank

Many RAG stacks merge BM25 and vector hits before reranking. Reciprocal Rank Fusion (RRF) avoids normalizing incompatible scores:

```python
def reciprocal_rank_fusion(rank_lists: list[list[str]], k: int = 60) -> list[str]:
    scores: dict[str, float] = {}
    for ranks in rank_lists:
        for rank, doc_id in enumerate(ranks):
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
    return sorted(scores.keys(), key=lambda d: scores[d], reverse=True)

# BM25 top-100 + bi-encoder top-100 → fused ~120 unique → cross-encoder top-10
fused_ids = reciprocal_rank_fusion([bm25_ids, vector_ids])
fused_docs = [fetch_chunk(i) for i in fused_ids[:75]]
```

Reranking fused candidates captures lexical exact-match wins BM25 finds and semantic neighbors vectors find — cross-encoder then prunes false positives from either channel. Log which channel supplied the winning doc; if rerank always picks BM25-only hits, your embeddings may need retraining.

## Context window budgeting after rerank

Top-10 chunks may exceed context window after rerank promotes longer passages. Apply token budget per chunk post-rerank — trim boilerplate headers, preserve answer-bearing sentences identified by lightweight span classifiers. Agent tool contracts should return `{chunks, rerank_scores, tokens_used}` so orchestrators enforce global context limits.

## The takeaway

Cross-encoder reranking is the highest-leverage retrieval upgrade most RAG pipelines can make after basic chunking — if you cap candidates, batch inference, enforce deadlines, and measure nDCG not vibes. Keep bi-encoders for recall, cross-encoders for precision, and never rerank the whole corpus. The agent that cites the right paragraph earns trust; the one that cites rank-one boilerplate loses it in one turn.

## Field checklist for cross encoder reranking

Before calling this done in production, confirm you can measure success and failure independently: a positive metric (throughput, conversion, recall) and a negative one (abuse rate, false accepts, lag). Add one alert that pages on the negative metric and one dashboard panel for the positive. Run a staging drill that forces the failure mode — timeout, poison input, or partial outage — and capture the exact commands in the runbook next to the config. If the drill takes longer than fifteen minutes to execute, simplify the recovery path before you need it at 2am.

## Resources

- [Sentence-Transformers Cross-Encoder docs](https://www.sbert.net/docs/pretrained_cross-encoders.html)
- [MS MARCO passage ranking dataset](https://microsoft.github.io/msmarco/)
- [Cohere Rerank API reference](https://docs.cohere.com/reference/rerank)
- [BEIR benchmark for retrieval evaluation](https://github.com/beir-cellar/beir)
- [Hugging Face cross-encoder model hub](https://huggingface.co/cross-encoder)
