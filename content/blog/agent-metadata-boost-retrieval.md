---
title: "Metadata Boost Retrieval for Agent RAG Pipelines"
slug: "agent-metadata-boost-retrieval"
description: "Use structured metadata—recency, tenant tier, doc type, tool affinity—to re-rank vector and BM25 hits so agents retrieve the right playbook, not the most similar paragraph."
datePublished: "2025-06-23"
dateModified: "2025-06-23"
tags: ["AI Agents", "RAG", "Retrieval", "Search Ranking"]
keywords: "metadata boost retrieval, RAG ranking, Elasticsearch function score, recency boost, hybrid search metadata, agent knowledge base"
faq:
  - q: "What metadata fields matter most for agent retrieval?"
    a: "Start with doc_type (runbook vs changelog vs API ref), recency (updated_at), environment (prod vs staging), product surface (billing vs infra), and authority (verified vs draft). For multi-tenant agents add tenant_id and visibility scope. Avoid boosting on fields the LLM could infer wrongly from content alone."
  - q: "Should metadata boost happen before or after vector search?"
    a: "Apply lightweight boosts in the first-stage retrieval (function_score in Elasticsearch, filter + weighted sum in pgvector hybrid) to shape the candidate pool. Run cross-encoder reranking after boosts so semantic relevance still dominates top-k. Boost-only without rerank overfits hand-tuned weights."
  - q: "How do you prevent stale docs from ranking first?"
    a: "Use gaussian decay on updated_at with scale ~30–90 days depending on doc velocity. Cap boost so a ancient but keyword-perfect doc cannot beat a recent moderate match. Surface as-of dates in chunk headers so the model knows freshness."
  - q: "Can metadata boosts leak across tenants?"
    a: "Yes if filters are optional. Always apply hard filters (tenant_id, ACL bitmap) before boosts—boosts are multipliers on an already permission-filtered set. Integration tests with two tenants querying the same string must assert zero cross-tenant doc ids."
---

The agent cited a **deprecated** refund policy because it scored highest on embedding similarity—the 2022 PDF shared vocabulary with the user's question and nobody boosted `status: canonical` or penalized `superseded_by`. Support escalations spiked until we added **metadata-aware retrieval**: not replacing vectors, but reshaping ranks with fields humans already curate in the CMS.

Pure semantic search treats a draft blog post and a verified runbook as peers if the wording aligns. Agent RAG needs **policy-aware ranking**: which doc types can ground answers, how fresh they must be, which environment they apply to. Metadata boost retrieval is the layer between hybrid search and the reranker where those rules live—explicit, testable, and tunable per agent persona.

## Architecture placement

```
Query ──► Query understanding (optional entity extract)
              │
              ▼
     Hard filters (tenant, ACL, language)
              │
              ▼
     Hybrid retrieval (BM25 + vector)
              │
              ▼
     Metadata boost / function_score  ◄── this article
              │
              ▼
     Cross-encoder rerank (top 50 → top 8)
              │
              ▼
     Chunk assembly + citation headers → LLM
```

Boosts adjust **first-stage** scores. If you only boost after fetching top-10 vectors, a doc at rank 400 never enters the pool—**recall** loss. Expand `k` before boost (e.g., 100) then cut to 20 post-boost for reranker.

## Metadata schema for agent corpora

Normalize at index time:

```json
{
  "chunk_id": "doc_refund_policy_v3#sec2",
  "text": "...",
  "embedding": [0.012, -0.034, "..."],
  "metadata": {
    "tenant_id": "ten_acme",
    "doc_type": "runbook",
    "status": "canonical",
    "product": "billing",
    "environment": "production",
    "updated_at": "2025-05-01T00:00:00Z",
    "authority_score": 1.0,
    "superseded_by": null,
    "tool_tags": ["stripe_refund", "billing_api"]
  }
}
```

`authority_score` captures human or workflow verification—0.0 draft, 0.5 team-reviewed, 1.0 legal-approved.

Index mappings should mark filter fields as `keyword` and dates as `date`—not analyzed text.

## Elasticsearch function_score pattern

Combine BM25/vector with boosts:

```json
{
  "query": {
    "function_score": {
      "query": {
        "hybrid": {
          "queries": [
            { "match": { "text": "{{query}}" } },
            { "knn": { "field": "embedding", "query_vector": "{{vec}}", "k": 100, "num_candidates": 500 } }
          ]
        }
      },
      "functions": [
        {
          "filter": { "term": { "metadata.status": "canonical" } },
          "weight": 1.4
        },
        {
          "filter": { "term": { "metadata.doc_type": "runbook" } },
          "weight": 1.2
        },
        {
          "gauss": {
            "metadata.updated_at": {
              "origin": "now",
              "scale": "30d",
              "decay": 0.5
            }
          }
        },
        {
          "filter": { "exists": { "field": "metadata.superseded_by" } },
          "weight": 0.3
        }
      ],
      "score_mode": "multiply",
      "boost_mode": "multiply"
    }
  },
  "size": 50
}
```

`score_mode: multiply` compounds signals—canonical + recent multiplies; superseded crushes score. Alternative `sum` for finer tuning but easier to overweight one function.

## Postgres + pgvector hybrid with metadata

When stack is SQL-first:

```sql
WITH vector_hits AS (
  SELECT chunk_id, 1 - (embedding <=> $1::vector) AS vec_score
  FROM kb_chunks
  WHERE tenant_id = $2
    AND acl_allowed($3, chunk_id)
  ORDER BY embedding <=> $1::vector
  LIMIT 100
),
bm25_hits AS (
  SELECT chunk_id, ts_rank_cd(text_tsv, plainto_tsquery($4)) AS bm25_score
  FROM kb_chunks
  WHERE tenant_id = $2
    AND text_tsv @@ plainto_tsquery($4)
  LIMIT 100
),
combined AS (
  SELECT
    COALESCE(v.chunk_id, b.chunk_id) AS chunk_id,
    COALESCE(v.vec_score, 0) AS vec_score,
    COALESCE(b.bm25_score, 0) AS bm25_score
  FROM vector_hits v
  FULL OUTER JOIN bm25_hits b USING (chunk_id)
)
SELECT
  c.chunk_id,
  (0.6 * c.vec_score + 0.4 * normalize_bm25(c.bm25_score))
    * meta_boost(m) AS final_score
FROM combined c
JOIN kb_chunks m ON m.chunk_id = c.chunk_id
ORDER BY final_score DESC
LIMIT 50;
```

Boost function in SQL or application code:

```python
from datetime import datetime, timezone

def meta_boost(meta: dict, query_tools: set[str]) -> float:
    boost = 1.0
    if meta.get("status") == "canonical":
        boost *= 1.4
    if meta.get("doc_type") == "runbook":
        boost *= 1.15
    if meta.get("superseded_by"):
        boost *= 0.25

    updated = datetime.fromisoformat(meta["updated_at"].replace("Z", "+00:00"))
    age_days = (datetime.now(timezone.utc) - updated).days
    recency = 0.5 ** (age_days / 30)  # half-life 30 days
    boost *= 0.5 + 0.5 * recency  # floor 0.5

    tool_overlap = len(query_tools & set(meta.get("tool_tags", [])))
    if tool_overlap:
        boost *= 1.0 + 0.1 * min(tool_overlap, 3)

    return boost
```

## Agent persona weight profiles

Store boost profiles per agent—not global constants:

```yaml
agents:
  support_l1:
    doc_type_weights:
      runbook: 1.3
      changelog: 0.9
      marketing: 0.4
    recency_half_life_days: 21
  coding_agent:
    doc_type_weights:
      api_reference: 1.5
      runbook: 1.0
    tool_tag_boost: 1.2
```

Load at query time; version profiles; A/B test with retrieval eval harness (nDCG@10 on labeled ticket→doc pairs).

## Query-time metadata inference

Boosts work better when query supplies implicit filters. Lightweight classifier:

```python
INTENT_FILTERS = {
    "refund": {"product": "billing", "doc_type": ["runbook", "policy"]},
    "deploy": {"product": "infra", "doc_type": ["runbook", "changelog"]},
}

def infer_hard_filters(query: str) -> dict:
    intent = intent_model.predict(query)  # small fast model or rules
    return INTENT_FILTERS.get(intent, {})
```

Apply inferred filters as **should** clauses (soft) if confidence < 0.8; **filter** (hard) if high confidence to avoid wrong domain exclusion.

## Chunk headers for the LLM

Metadata helps the model, not just the index:

```markdown
[source: runbook | product: billing | updated: 2025-05-01 | status: canonical]
## Refund eligibility
...
```

The model learns to prefer canonical headers when chunks conflict—retrieval and prompt alignment.

## Evaluation without fooling yourself

Build a eval set of `(query, relevant_chunk_ids, metadata_context)` from support tickets. Metrics:

- nDCG@10 with and without boosts
- **Wrong-version rate** — top-1 has `superseded_by` set
- **Cross-type error** — marketing doc in top-3 for procedural query

Tune boosts on validation; report once on held-out test. Log production retrieval with boost components for offline replay:

```json
{
  "query_id": "q_991",
  "chunk_id": "doc_12",
  "vec_score": 0.82,
  "bm25_score": 0.41,
  "meta_boost": 1.68,
  "final_score": 1.09,
  "boost_factors": {"canonical": 1.4, "recency": 1.0}
}
```

## Failure modes

| Failure | Cause | Mitigation |
|---------|-------|------------|
| Boost explosion | multiply stack | Cap meta_boost at 2.0 |
| Fresh but wrong | recency only | require minimum vec score floor |
| Tenant leak | filter after boost | filter first in SQL/ES |
| Tool tag spam | CMS mis-tags | audit tool_tags on publish |

## Operational concerns

Reindex when metadata schema changes. Boost weights live in config—deploy via feature flag, not index rebuild.

Dashboard: average meta_boost by doc_type, fraction of answers citing non-canonical docs (from citation parser).

## Parent-child chunk linking

Long runbooks split into chunks lose document-level metadata if only leaf chunks carry fields. Propagate parent metadata at index time:

```python
def enrich_chunk_metadata(leaf: dict, parent: dict) -> dict:
    return {
        **leaf["metadata"],
        "doc_type": parent["doc_type"],
        "status": parent["status"],
        "updated_at": parent["updated_at"],
        "superseded_by": parent.get("superseded_by"),
        "parent_doc_id": parent["doc_id"],
    }
```

Boost on parent `status: canonical` even when child chunk text is generic ("See section 3"). Retrieval logs should include `parent_doc_id` for analytics on which source docs drive answers.

## Negative boosts and exclusion rules

Some metadata demands **hard exclusion**, not soft penalty:

- `environment: staging` — filter out for production-facing agents entirely
- `legal_hold: true` — exclude from customer support agents
- `language: ja` — filter when query language detector returns `en`

Soft penalties handle ambiguous cases: `audience: internal` gets weight 0.6 for external tenant agents but remains retrievable for employee-only personas. Document exclusion vs boost in runbooks—on-call should know which rules are filter vs multiplier.

## Combining metadata boost with RRF

When using Reciprocal Rank Fusion for hybrid lists, apply metadata as a **post-fusion rerank** step on the top 100 fused ids:

```python
def post_fusion_meta_rerank(
    fused: list[tuple[str, float]],
    meta_by_id: dict[str, dict],
    cap: float = 2.0,
) -> list[tuple[str, float]]:
    reranked = []
    for doc_id, rrf_score in fused:
        boost = min(cap, meta_boost(meta_by_id[doc_id]))
        reranked.append((doc_id, rrf_score * boost))
    return sorted(reranked, key=lambda x: x[1], reverse=True)
```

This keeps RRF scale-free while still elevating canonical docs. Compare nDCG@10 against pre-fusion function_score—pick whichever wins on your eval set; do not stack both without measurement (double-counting risk).

## The takeaway

Metadata boost retrieval turns CMS structure into ranking signal so agents prefer canonical, fresh, on-domain docs. Hard-filter tenancy and ACL first, expand hybrid recall, apply bounded multiplicative boosts, then rerank semantically. Tune per agent persona with labeled evals and log boost factors so regressions are debuggable—not mysterious "the agent got worse."

## Resources

- [Elasticsearch function_score query](https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dfunction-score-query.html)
- [OpenSearch hybrid search with filters](https://opensearch.org/docs/latest/search-plugins/hybrid-search/)
- [pgvector documentation](https://github.com/pgvector/pgvector)
- [BEIR benchmark — retrieval evaluation mindset](https://github.com/beir-cellar/beir)
- [Reciprocal Rank Fusion paper (Cormack et al.)](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf)
