---
title: "Metadata Filtering in Hybrid RAG"
slug: "rag-metadata-filtering-hybrid"
description: "Use metadata filtering in hybrid RAG pipelines: pre-filter vector and BM25 search by tenant, version, language, and access control for precise retrieval."
datePublished: "2025-01-04"
dateModified: "2025-01-04"
tags: ["AI", "RAG", "Metadata", "Retrieval"]
keywords: "metadata filtering RAG, hybrid search filters, vector database metadata, pre-filtering retrieval, access control RAG, tenant isolation"
faq:
  - q: "When should I filter by metadata vs including metadata in the query?"
    a: "Filter when metadata represents hard constraints — tenant ID, language, document version, access level — that must never be violated. Include metadata in the query embedding when it is soft context that should influence ranking but not exclude results, like product category or topic tags. Getting this wrong either leaks data across tenants or over-filters useful results."
  - q: "Should metadata filters apply before or after vector search?"
    a: "Apply hard filters before or during search — most vector databases support pre-filtering that restricts the search space before computing similarity. Post-filtering retrieves top-k then discards non-matching results, which silently reduces effective k and drops relevant documents. Pre-filtering is correct for access control; post-filtering is only acceptable for soft preferences with a widened initial k."
  - q: "How do I combine metadata filters with hybrid search?"
    a: "Apply the same metadata filter to both BM25 and vector search paths before fusion. Asymmetric filtering — filtering one retriever but not the other — causes RRF to merge results from different document pools, reintroducing documents that should have been excluded. Treat the filter as a shared gate both retrievers pass through."
---

A user at Tenant A received an answer citing Tenant B's custom integration guide because the vector search returned the highest-scoring chunk globally and nobody attached a `tenant_id` filter to the query. The content was relevant by embedding similarity and catastrophically wrong by access control standards. Metadata filtering is how you tell the retriever which subset of the corpus is even allowed to participate — before similarity scoring, not after.

## What metadata to index

Attach structured fields to every chunk at index time:

```json
{
  "chunk_id": "doc-123:chunk-4",
  "text": "...",
  "tenant_id": "tenant_a",
  "product": "payments-api",
  "language": "en",
  "doc_version": "3.2",
  "status": "current",
  "access_level": "internal",
  "effective_date": "2024-06-01",
  "source_type": "runbook"
}
```

Fields fall into categories:

- **Access control** — `tenant_id`, `user_role`, `access_level`. Hard filters, non-negotiable.
- **Versioning** — `doc_version`, `status`, `effective_date`. Hard filters for correctness.
- **Localization** — `language`, `region`. Hard filters for user-facing apps.
- **Topical** — `product`, `category`, `team`. Soft filters or query-time boosts.

## Pre-filtering in vector databases

Modern vector stores support metadata predicates during search:

```python
results = vector_store.search(
    query_embedding=embed(query),
    top_k=10,
    filter={
        "tenant_id": {"$eq": current_user.tenant_id},
        "status": {"$eq": "current"},
        "language": {"$eq": user.locale},
        "access_level": {"$in": allowed_levels(current_user)},
    },
)
```

Syntax varies by provider — Pinecone, Weaviate, Qdrant, Chroma, and Elasticsearch all support variations of this pattern. The principle is identical: constrain the search space before similarity computation.

## Applying filters to hybrid search

Both retrieval paths must respect the same filters:

```python
def filtered_hybrid_search(query: str, filters: dict, top_k: int = 10):
    bm25_results = bm25_index.search(
        query, top_k=20, filter=filters
    )
    vector_results = vector_store.search(
        embed(query), top_k=20, filter=filters
    )
    return reciprocal_rank_fusion([bm25_results, vector_results])[:top_k]
```

If BM25 is a separate system (Elasticsearch) and vectors live in Pinecone, duplicate filter logic carefully. A filter mismatch between stores is a data leak waiting to happen.

## Extracting filters from queries

Users do not always state filters explicitly. Extract them:

**Rule-based:**

```python
def extract_filters(query: str, user: User) -> dict:
    filters = {
        "tenant_id": user.tenant_id,
        "access_level": {"$in": user.allowed_levels},
    }
    if "payments" in query.lower():
        filters["product"] = "payments-api"
    return filters
```

**LLM-extracted:**

```text
Given the user query, extract metadata filters as JSON.
Available fields: product, language, doc_version, category.
Only include fields explicitly mentioned or strongly implied.
```

LLM extraction handles "show me the French version of the billing docs" but adds latency. Use for complex queries; use rule-based for known filter patterns.

## Soft filters vs hard filters

**Hard filters** — exclude non-matching documents entirely. Required for security and versioning.

**Soft filters** — boost matching documents in ranking without excluding others:

```python
# Elasticsearch example: boost matching product, don't exclude others
{
    "query": {
        "bool": {
            "must": {"match": {"text": query}},
            "should": {"term": {"product": {"value": "payments-api", "boost": 2.0}}}
        }
    }
}
```

Use soft boosts when the metadata is a hint, not a constraint. "Questions about billing" might boost `product: billing` without hiding API docs that also answer the question.

## Multi-tenant isolation patterns

For SaaS RAG applications:

- **Namespace per tenant** — separate vector collections per tenant. Strongest isolation, higher ops overhead.
- **Shared index with tenant filter** — single index, `tenant_id` on every chunk, filter on every query. Simpler ops, requires discipline.
- **Hybrid** — shared index for public docs, per-tenant collections for private content. Query both and merge.

Never rely on the LLM to ignore cross-tenant context in the prompt. If wrong chunks enter the context window, you have already failed regardless of what the prompt says.

## Monitoring filter effectiveness

Track:

- **Zero-result rate per filter combination** — users in Tenant A consistently getting zero results means missing content, not bad queries.
- **Post-filter discard rate** — if using post-filtering, log how many of top-50 were discarded. High discard rates mean you need pre-filtering or larger initial k.
- **Cross-tenant retrieval attempts** — alert if any query returns chunks with a different `tenant_id` than the requester's.

Log filter selectivity in production — metadata filters that match 90% of documents provide no retrieval benefit over no filter.

## Pre-filter vs post-filter tradeoffs

| Approach | Pros | Cons |
|----------|------|------|
| Pre-filter (vector DB) | Efficient, secure | Index must support filter fields |
| Post-filter (app layer) | Flexible | Wastes embedding search on discarded docs |
| Hybrid | Balance | Two code paths to maintain |

Post-filtering top-50 then keeping 5 fails when filter is selective — retrieve top-500 when post-filter discard rate exceeds 50%.

## Filter schema design

Design chunk metadata at ingest time:

```json
{
  "tenant_id": "uuid",
  "doc_type": "policy|faq|api",
  "product": "billing",
  "version": "2026-01",
  "access_level": "internal|customer",
  "language": "en"
}
```

Every filter field in queries must exist on every chunk — missing metadata means documents invisible to filtered queries silently.

Pair with [RAG reranking cross-encoders](https://blog.michaelsam94.com/rag-reranking-cross-encoders/) when metadata filtering narrows candidates for reranking.

## Common production mistakes

Teams get metadata filtering hybrid wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

RAG pipelines for metadata filtering hybrid degrade when chunk boundaries split tables, embeddings go stale after doc updates, and retrieval metrics are measured offline only. Re-index incrementally and monitor answer faithfulness on live traffic samples.

## Debugging and triage workflow

When metadata filtering hybrid misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Pinecone metadata filtering](https://docs.pinecone.io/guides/data/filter-with-metadata)
- [Weaviate filtered vector search](https://weaviate.io/developers/weaviate/search/filters)
- [Qdrant filtering documentation](https://qdrant.tech/documentation/concepts/filtering/)
- [Elasticsearch hybrid search with filters](https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-bool-query.html)
- [LangChain vector store retriever filters](https://python.langchain.com/docs/how_to/vectorstore_retriever/)
