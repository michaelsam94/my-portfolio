---
title: "Parent-Document Retrieval for RAG"
slug: "rag-parent-document-retrieval"
description: "Implement parent-document retrieval in RAG: search small child chunks for precision, return parent sections for generation context."
datePublished: "2025-01-12"
dateModified: "2025-01-12"
tags: ["AI", "RAG", "Chunking", "Retrieval"]
keywords: "parent document retrieval, small-to-big retrieval, child parent chunks, RAG context window, hierarchical chunking"
faq:
  - q: "What is parent-document retrieval?"
    a: "Parent-document retrieval indexes small child chunks for precise search but returns the larger parent section — paragraph, page, or document section — to the LLM for generation. You get the search precision of small embeddings with the context completeness of larger chunks. It is also called small-to-big retrieval or hierarchical retrieval."
  - q: "How is parent-document retrieval different from chunk overlap?"
    a: "Overlap duplicates content across chunks in the index, increasing storage and causing near-duplicate results. Parent-document retrieval stores small chunks for search and maps each to a parent ID without duplicating parent text in the index. At query time, you retrieve children and fetch parents — one copy of each parent, no index bloat from overlap."
  - q: "What size should child and parent chunks be?"
    a: "A common starting point is 200–300 token children and 1000–1500 token parents — roughly a paragraph for search and a section for generation. The child should be small enough that its embedding is specific; the parent should fit the answer context for most questions in that section. Validate both retrieval recall and generation quality on your eval set when tuning sizes."
---

The retrieval step nailed it — chunk 7 of the API reference, the one mentioning `retry_after`, landed in top-3. The generation step failed because chunk 7 was 200 tokens with no mention of which endpoint, which auth header, or what HTTP status triggers the retry. Small chunks retrieve well and generate poorly. Parent-document retrieval searches the small chunk and hands the LLM the full section it came from.

## The precision-context tradeoff

| Chunk size | Retrieval precision | Generation context |
|------------|--------------------|--------------------|
| Small (200 tokens) | High | Insufficient |
| Large (1500 tokens) | Low | Sufficient |
| Parent-document | High (search small) | Sufficient (return large) |

Standard RAG forces you to pick one size. Parent-document retrieval splits the problem: optimize chunk size for search separately from context size for generation.

## Data model

Index two levels with a parent-child relationship:

```json
// Child chunk (indexed for search)
{
  "id": "doc-123:child-07",
  "text": "Set retry_after to the value in the Retry-After header...",
  "parent_id": "doc-123:section-rate-limiting",
  "chunk_type": "child"
}

// Parent section (stored, not directly searched)
{
  "id": "doc-123:section-rate-limiting",
  "text": "## Rate Limiting\n\nThe API returns HTTP 429 when...\n\nSet retry_after to the value in the Retry-After header...\n\nFor batch endpoints, use exponential backoff...",
  "chunk_type": "parent"
}
```

Children are embedded and stored in the vector index. Parents are stored in a document store (or the same database without vector indexing) and fetched by ID at query time.

## Indexing pipeline

```python
def index_with_parents(document: str, metadata: dict):
    # Split into parent sections (by heading or size)
    parents = split_into_sections(document, max_tokens=1500)

    for parent in parents:
        parent_id = f"{metadata['doc_id']}:section-{parent.index}"
        parent_store.save(parent_id, parent.text, metadata)

        # Split each parent into small children
        children = split_text(parent.text, chunk_size=256, overlap=0)

        for i, child in enumerate(children):
            child_id = f"{parent_id}:child-{i}"
            vector_store.upsert(
                id=child_id,
                embedding=embed(child),
                metadata={**metadata, "parent_id": parent_id},
            )
```

No overlap needed on children — the parent provides cross-boundary context at generation time.

## Retrieval and generation

```python
def parent_document_retrieve(query: str, top_k: int = 5) -> list[str]:
    # Search child chunks
    child_results = vector_store.search(embed(query), top_k=top_k * 3)

    # Resolve to unique parents
    parent_ids = list(dict.fromkeys(
        r.metadata["parent_id"] for r in child_results
    ))[:top_k]

    # Fetch parent text for generation
    parents = [parent_store.get(pid) for pid in parent_ids]
    return [p.text for p in parents]
```

Deduplicate parents — multiple children from the same section should not send the parent text twice to the LLM. `dict.fromkeys` preserves rank order from child scores.

## Variations and extensions

**Multi-level hierarchy** — children → sections → full document. Retrieve children, return sections for most queries, escalate to full document for broad questions.

**Summary parents** — store an LLM-generated summary as the parent instead of raw text. Reduces tokens sent to the generation model while preserving broader context.

**Parent with child highlight** — pass the parent text but indicate which child matched, helping the LLM focus:

```text
[Most relevant passage]: "Set retry_after to the value in the Retry-After header..."

[Full section context]:
## Rate Limiting
The API returns HTTP 429 when...
```

## Combining with other retrieval techniques

Parent-document retrieval is orthogonal to hybrid search, reranking, and metadata filtering:

```python
def full_retrieve(query: str, filters: dict) -> list[str]:
    children = hybrid_search(query, filters=filters, top_k=30)
    reranked_children = colbert_rerank(query, children, top_k=15)
    parent_ids = deduplicate_parents(reranked_children)[:5]
    return [parent_store.get(pid).text for pid in parent_ids]
```

Each layer addresses a different failure mode: hybrid search for recall, reranking for precision, parent resolution for context.

## Evaluating parent-document retrieval

Compare on your eval set:

1. Small chunks only (256 tokens) for both search and generation.
2. Large chunks only (1500 tokens) for both.
3. Parent-document (256 child, 1500 parent).

Measure retrieval recall@10 on child IDs and end-to-end answer quality with parent context. Parent-document should match or beat small-chunk recall while matching large-chunk generation quality.

Watch total tokens sent to the LLM — parents are larger, so fewer can fit in the context window. Top-3 parents often outperform top-10 small chunks at similar token cost.

## Small-to-big retrieval

Retrieve small chunks for precision, pass parent document (or section) to LLM for generation:

```python
chunks = retrieve(query, top_k=10)
context = [get_parent_section(c) for c in chunks]
```

Parent deduplication prevents sending same section five times.

## Common production mistakes

Teams get parent document retrieval wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

RAG pipelines for parent document retrieval degrade when chunk boundaries split tables, embeddings go stale after doc updates, and retrieval metrics are measured offline only. Re-index incrementally and monitor answer faithfulness on live traffic samples.

## Debugging and triage workflow

When parent document retrieval misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [LangChain parent document retriever](https://python.langchain.com/docs/how_to/parent_document_retriever/)
- [LlamaIndex auto-merging retriever](https://docs.llamaindex.ai/en/stable/examples/retrievers/auto_merging_retriever/)
- [Pinecone — chunking strategies](https://www.pinecone.io/learn/chunking-strategies/)
- [Azure AI Search parent-child indexing](https://learn.microsoft.com/en-us/azure/search/search-how-to-index-parent-child)
- [Weaviate hierarchical retrieval patterns](https://weaviate.io/developers/weaviate/search/basics)
