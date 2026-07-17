---
title: "Two-Tower Retrieval Models for Agent RAG"
slug: "agent-two-tower-retrieval"
description: "Train and serve dual-encoder retrieval for agents: query tower vs document tower, hard negatives, ANN index refresh, and hybrid fusion with BM25 in production."
datePublished: "2025-04-23"
dateModified: "2026-07-17"
tags: ["AI Agents", "RAG", "Machine Learning", "Search"]
keywords: "two tower retrieval agent, dual encoder RAG, embedding retrieval fine tune, ANN vector search agents"
faq:
  - q: "When does two-tower beat bi-encoder re-ranking or pure BM25 for agents?"
    a: "Two-tower shines at scale (millions of chunks) with fixed corpora where query-document interaction can be precomputed. Use hybrid BM25+vector for lexical anchors (SKUs, error codes). Add cross-encoder re-rank on top-20 when precision matters more than latency."
  - q: "How often should the document tower index rebuild?"
    a: "Incremental embedding for changed docs daily; full HNSW rebuild weekly or when embedding model version changes. Agent tool latency budgets usually allow stale indexes up to 24h for internal docs — not for realtime ticket search."
  - q: "What training data do agent retrieval models need?"
    a: "Query-chunk pairs from agent logs: successful tool calls that cited chunks, thumbs-up retrieval, click-through on cited sources. Mine hard negatives from BM25 top-10 misses. Minimum viable: 50k pairs before fine-tune beats generic embeddings."
  - q: "Same embedding model for query and document towers?"
    a: "Architecturally yes for symmetric dual encoders; asymmetric towers (different encoders or prefixes) often win on agent tasks where queries are short questions and documents are long runbooks. Prefix with 'query:' and 'passage:' if using shared backbone."
---

Bi-encoder retrieval is the workhorse of agent RAG: embed the question once, ANN-search a pre-built index, feed top-k chunks to the LLM. **Two-tower models** formalize this as trainable query and document encoders optimized on your agent's actual success signals — not generic web paragraph similarity. Done well, recall@10 on internal runbooks jumps 15–25 points over off-the-shelf `text-embedding-3-small`; done poorly, you fine-tuned on noise and broke BM25's exact-match wins.

## Architecture overview

```
                    training                          serving
              ┌─────────────────┐              ┌──────────────────┐
  query text  │   Query Tower   │─── q_vec ───►│   ANN index      │
              └─────────────────┘              │  (doc vectors)   │
              ┌─────────────────┐              └────────▲─────────┘
  doc chunks  │  Document Tower │─── d_vec ────────────┘ (offline)
              └─────────────────┘
                     │
              contrastive loss + hard negatives
```

Document vectors are computed offline and indexed; query vectors at request time. No cross-attention until optional re-rank stage.

## Model selection baseline

| Approach | Latency (p95) | Quality ceiling | Ops burden |
|----------|---------------|-----------------|------------|
| Generic embedding API | 50–150ms | Moderate | Low |
| Fine-tuned dual encoder | 30–80ms | High | Medium |
| ColBERT late interaction | 100–300ms | Very high | High |
| Cross-encoder only | 500ms+ | Highest | Low scale |

Agents with 200ms retrieval budget: dual encoder + cross-encoder re-rank on top-20.

## Training data from agent telemetry

Mine positives from production:

```sql
SELECT
  r.query_text,
  c.chunk_id,
  c.content_hash
FROM agent_retrieval_events r
JOIN agent_tool_outcomes o ON o.run_id = r.run_id
JOIN chunks c ON c.chunk_id = ANY(r.retrieved_ids)
WHERE o.task_success = true
  AND o.user_feedback IN ('positive', 'implicit_success')
  AND r.created_at > now() - interval '90 days';
```

Hard negatives — BM25 top-10 that agents did not cite:

```python
def mine_hard_negatives(query: str, positive_id: str, corpus_index) -> list[str]:
    bm25_hits = bm25_search(query, k=10)
    return [h.id for h in bm25_hits if h.id != positive_id][:5]
```

Training loop (PyTorch pseudo):

```python
for batch in loader:
    q = query_tower(batch.queries)      # [B, D]
    d_pos = doc_tower(batch.pos_docs)   # [B, D]
    d_neg = doc_tower(batch.neg_docs)   # [B, N, D]
    loss = info_nce(q, d_pos, d_neg, temperature=0.05)
    loss.backward()
```

## Hybrid fusion at serve time

Pure vector misses exact error codes (`ERR_PAYMENT_8842`). Combine:

```python
def hybrid_retrieve(query: str, k: int = 20) -> list[Chunk]:
    bm25_ids = bm25.top_k(query, k=k)
    vec_ids = ann.search(query_tower.encode(query), k=k)
    fused = reciprocal_rank_fusion([bm25_ids, vec_ids], k=60)
    return rerank_cross_encoder(query, fused[:20])[:8]
```

RRF constant `k=60` is a reasonable default; tune on eval set.

| Signal | Weight tweak when... |
|--------|----------------------|
| BM25 boost | Queries contain codes, IDs, product SKUs |
| Vector boost | Paraphrase-heavy natural language |
| Metadata filter | Agent scope limited to tenant KB |

## ANN index operations

Document tower outputs → HNSW (pgvector, Qdrant, ScaNN):

```sql
-- pgvector HNSW example
CREATE INDEX ON document_embeddings
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

SET hnsw.ef_search = 100;  -- recall/latency tradeoff at query time
```

Rebuild playbook when `embedding_model_version` bumps:

1. Dual-write new embeddings to `embeddings_v2` table.
2. Build parallel index.
3. Shadow-query: compare recall@10 vs v1 on golden queries.
4. Flip alias `active_index → v2`.
5. Drop v1 after 7d rollback window.

## Agent tool contract

Expose retrieval as a typed tool with observability:

```json
{
  "name": "search_knowledge_base",
  "parameters": {
    "query": "string",
    "filters": {"product": "string", "doc_type": "string"}
  },
  "returns": {
    "chunks": [{"id", "title", "text", "score", "source"}]
  }
}
```

Log `query`, `chunk_ids`, `scores`, `model_version`, `index_version` on every call for offline eval and retraining.

## Evaluation metrics

Offline golden set (500+ agent tasks):

- **Recall@k** — correct chunk in top-k
- **MRR** — rank of first relevant
- **Citation accuracy** — agent cites retrieved chunk in answer
- **End-to-end task success** — retrieval change impact

Block deploy if Recall@8 drops >2% vs champion model.

## Common pitfalls

- **Training on click logs without success filter** — optimizes for flashy wrong chunks.
- **Chunk size mismatch** — model trained on 512-token passages, served with 2048-token chunks.
- **Tenant leakage** — index must filter `tenant_id` before ANN, not after.
- **Stale document tower** — agent answers from deprecated API docs; tie index freshness to CMS webhooks.

## Resources

- [Google — Dual Encoder Models for Recommendations (conceptual parallel)](https://developers.google.com/machine-learning/recommendation)
- [Sentence Transformers — training overview](https://www.sbert.net/docs/training/overview.html)
- [Pyserini — BM25 baselines](https://github.com/castorini/pyserini)
- [Qdrant — HNSW configuration guide](https://qdrant.tech/documentation/concepts/indexing/)
- [Reciprocal Rank Fusion paper (Cormack et al.)](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf)

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

