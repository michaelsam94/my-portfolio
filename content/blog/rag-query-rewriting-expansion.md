---
title: "Query Rewriting and Expansion"
slug: "rag-query-rewriting-expansion"
description: "Improve RAG retrieval with query rewriting and expansion: HyDE, multi-query generation, step-back prompting, and decomposition for better chunk recall."
datePublished: "2025-01-16"
dateModified: "2025-01-16"
tags: ["AI", "RAG", "Query Expansion", "Retrieval"]
keywords: "query rewriting RAG, query expansion, multi-query retrieval, step-back prompting, query decomposition, retrieval optimization"
faq:
  - q: "What is the difference between query rewriting and query expansion?"
    a: "Query rewriting transforms the original query into a better-formed search query — fixing grammar, adding domain terms, or rephrasing for embedding alignment. Query expansion generates additional queries alongside the original to search with multiple phrasings. Rewriting replaces; expansion supplements. Many production pipelines do both: rewrite for the primary search, expand for supplemental searches."
  - q: "Does query rewriting add too much latency?"
    a: "An LLM rewrite call adds 200–800ms depending on model and prompt size. Mitigate with caching for frequent queries, a fast small model for rewriting, and selective routing — only rewrite queries classified as vague or conversational. The retrieval quality improvement on those queries usually justifies the latency cost."
  - q: "Can query rewriting hurt retrieval quality?"
    a: "Yes. Over-aggressive rewriting can replace user-specific terms with generic synonyms, dropping exact identifiers like error codes or product names. Always preserve proper nouns and technical terms from the original query. Run the original query through BM25 in parallel so exact matches are not lost when the rewritten query drifts."
---

"My webhook thing isn't working" retrieved generic webhook overview pages — not the troubleshooting guide for silent HTTP 200 failures. The user's query was vague, informal, and missing the vocabulary your docs use. The docs were indexed correctly; the query never reached them. Query rewriting and expansion transform what the user said into what your retrieval system can match.

## Why raw queries underperform

Users and documentation authors speak differently:

- Users: informal, abbreviated, missing domain terms.
- Docs: formal, complete sentences, product-specific vocabulary.

Short queries embed poorly against long technical chunks. Conversational phrasing embeds far from declarative documentation prose. Query preprocessing closes this gap before the embedding step.

## Query rewriting

Transform the user's query into a search-optimized form:

```python
REWRITE_PROMPT = """
Rewrite the following user question into a precise technical search query
that would match documentation. Preserve all proper nouns, error codes,
and product names exactly. Do not answer the question.

User question: {query}
Search query:
"""

def rewrite_query(query: str) -> str:
    return llm.generate(REWRITE_PROMPT.format(query=query))
```

"My webhook thing isn't working" → "webhook delivery failure troubleshooting silent HTTP 200 response."

Use a fast model — this is preprocessing, not generation. Cache results keyed on normalized query text.

## Multi-query expansion

Generate multiple query variants and search with all of them:

```python
MULTI_QUERY_PROMPT = """
Generate 3 different search queries that would help answer this question.
Use varied vocabulary and angles. One per line.

Question: {query}
"""

def multi_query_search(query: str, top_k: int = 10):
    variants = llm.generate(MULTI_QUERY_PROMPT.format(query=query)).split("\n")
    variants.append(query)  # always include original

    all_results = []
    for variant in variants:
        all_results.append(vector_search(variant.strip(), top_k=top_k))

    return reciprocal_rank_fusion(all_results)[:top_k]
```

RRF fusion merges results from all variants. Documents matching multiple variants rank highest — a strong relevance signal.

## Step-back prompting

Generate a broader question that provides context, then search with both:

```python
STEP_BACK_PROMPT = """
Ask a more general question that would help answer this specific question.
Do not answer either question.

Specific: {query}
General:
"""

def step_back_search(query: str, top_k: int = 10):
    general = llm.generate(STEP_BACK_PROMPT.format(query=query))
    specific_results = vector_search(query, top_k=15)
    general_results = vector_search(general, top_k=15)
    return reciprocal_rank_fusion([specific_results, general_results])[:top_k]
```

"What timeout should I set for payment webhooks?" step-backs to "How does payment webhook configuration work?" — retrieving overview docs that contextualize the specific timeout answer.

## Query decomposition

Break complex questions into sub-queries for multi-hop retrieval:

```python
DECOMPOSE_PROMPT = """
Break this question into independent sub-questions that can each be
answered by searching documentation separately. Return as a JSON array.

Question: {query}
"""

def decomposed_search(query: str, top_k: int = 10):
    sub_queries = json.loads(llm.generate(DECOMPOSE_PROMPT.format(query=query)))
    all_chunks = []
    for sq in sub_queries:
        all_chunks.extend(vector_search(sq, top_k=5))
    return deduplicate(all_chunks)[:top_k]
```

"Can Enterprise customers use SSO with the legacy API after migrating to the new auth service?" decomposes into SSO eligibility, legacy API compatibility, and migration timeline queries.

## Preserving exact terms

Rewriting must not destroy identifiers:

```python
def safe_rewrite(query: str) -> str:
    # Extract and protect exact terms
    protected = extract_identifiers(query)  # error codes, UUIDs, product names
    rewritten = llm_generate_rewrite(query)

    # Ensure protected terms appear in rewrite
    for term in protected:
        if term.lower() not in rewritten.lower():
            rewritten = f"{rewritten} {term}"

    return rewritten
```

Always run the original query through BM25 alongside any rewritten vector search. BM25 preserves exact token matching regardless of how the rewrite paraphrases.

## Routing: when to rewrite

Not every query benefits:

```python
def retrieve(query: str):
    if contains_exact_identifier(query):
        return hybrid_search(query)  # BM25 handles exact terms
    if is_vague_or_conversational(query):
        rewritten = rewrite_query(query)
        return hybrid_search(rewritten)
    return hybrid_search(query)  # clear queries search directly
```

Classify with heuristics (query length, presence of technical terms, question word patterns) or a lightweight classifier. Log rewrite decisions and compare retrieval quality on rewritten vs non-rewritten queries monthly.

## Evaluating query preprocessing

On your eval set, compare:

1. Raw query → search (baseline).
2. Rewrite only.
3. Multi-query expansion.
4. Step-back + specific.
5. Decomposition (for multi-hop questions).

Measure recall@10 per query category. Rewriting helps most on vague and conversational queries. Decomposition helps most on multi-hop questions. Applying all techniques to every query adds cost without benefit.

## Common production mistakes

Teams get query rewriting expansion wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

RAG pipelines for query rewriting expansion degrade when chunk boundaries split tables, embeddings go stale after doc updates, and retrieval metrics are measured offline only. Re-index incrementally and monitor answer faithfulness on live traffic samples.

## Debugging and triage workflow

When query rewriting expansion misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [LangChain multi-query retriever](https://python.langchain.com/docs/how_to/MultiQueryRetriever/)
- [LlamaIndex query transform modules](https://docs.llamaindex.ai/en/stable/module_guides/querying/)
- [Step-back prompting paper](https://arxiv.org/abs/2310.06117)
- [HyDE — hypothetical document embeddings](https://arxiv.org/abs/2212.10496)
- [RAG query preprocessing survey](https://arxiv.org/abs/2409.11227)
