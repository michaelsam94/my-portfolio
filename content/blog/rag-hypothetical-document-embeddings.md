---
title: "HyDE: Hypothetical Document Embeddings"
slug: "rag-hypothetical-document-embeddings"
description: "Use HyDE (Hypothetical Document Embeddings) to improve RAG retrieval: generate a hypothetical answer, embed it, and search with query-document alignment."
datePublished: "2024-12-23"
dateModified: "2024-12-23"
tags: ["AI", "RAG", "HyDE", "Embeddings"]
keywords: "HyDE hypothetical document embeddings, query expansion RAG, zero-shot retrieval, embedding alignment, hypothetical answer retrieval"
faq:
  - q: "What is HyDE and how does it improve retrieval?"
    a: "HyDE generates a hypothetical document that would answer the user's query, embeds that fabricated passage instead of the raw query, and uses the embedding for vector search. The hypothetical text reads like corpus content, so its embedding aligns better with actual document chunks than a short question embedding does. This is especially effective when user queries are short or phrased differently from your documentation."
  - q: "Does HyDE introduce hallucination risk?"
    a: "The hypothetical document is never shown to users — it exists only as a search intermediary. Retrieval quality can improve even when the hypothetical contains inaccuracies, because the embedding captures topic and vocabulary rather than exact facts. Still, monitor retrieval quality: wildly wrong hypotheticals can pull irrelevant chunks and degrade generation downstream."
  - q: "When should I avoid HyDE?"
    a: "Skip HyDE for queries targeting exact identifiers — error codes, SKUs, legal citations — where BM25 keyword search outperforms semantic tricks. Skip it when latency budgets are extremely tight, since it adds an LLM call before every retrieval. HyDE adds most value on conceptual and how-to questions where query-document vocabulary mismatch is the main retrieval failure mode."
---

Users ask "why is my webhook failing silently?" but your runbook chunks say "diagnosing HTTP 2xx responses with empty payload bodies." The query embedding and the answer embedding live in different neighborhoods of vector space — not because the docs are missing, but because users and authors use different words. HyDE (Hypothetical Document Embeddings) closes that gap by asking the LLM to write the answer first, then searching with that fabricated passage.

## The query-document asymmetry problem

Embedding models are trained to map similar texts nearby. A user query is short, interrogative, and informal. Corpus chunks are declarative, technical, and formal. Their embeddings are systematically misaligned even when semantically related.

Traditional fixes:

- **Query expansion** — append synonyms or related terms. Helps somewhat.
- **Fine-tuned embeddings** — train on query-document pairs from your domain. Expensive.
- **HyDE** — generate a passage that looks like a corpus chunk, embed that instead.

## The HyDE pipeline

```python
HYDE_PROMPT = """
Write a short passage that would appear in technical documentation
and directly answer the following question. Use formal technical
language. Do not include disclaimers or say you are unsure.

Question: {query}
"""

def hyde_retrieve(query: str, top_k: int = 10) -> list[Document]:
    # Step 1: Generate hypothetical document
    hypothetical = llm.generate(HYDE_PROMPT.format(query=query))

    # Step 2: Embed the hypothetical (not the query)
    query_embedding = embed(hypothetical)

    # Step 3: Vector search as usual
    return vector_store.search(query_embedding, top_k=top_k)
```

The hypothetical for "why is my webhook failing silently?" might read: *"Webhook delivery failures without error responses typically indicate the endpoint returned HTTP 200 with an empty body. Verify the endpoint acknowledges receipt by returning a non-empty JSON payload within the 5-second timeout window."* That text embeds much closer to actual runbook chunks.

## Multi-HyDE for robustness

Generate multiple hypothetical documents with different phrasings and average their embeddings:

```python
def multi_hyde_embed(query: str, n: int = 3) -> list[float]:
    hypotheticals = [
        llm.generate(HYDE_PROMPT.format(query=query), temperature=0.7)
        for _ in range(n)
    ]
    embeddings = [embed(h) for h in hypotheticals]
    return average_embeddings(embeddings)
```

Averaging reduces sensitivity to any single hallucinated detail. Cost scales linearly with `n`, so 3 is a practical default.

## Combining HyDE with hybrid search

HyDE improves dense retrieval. Pair it with BM25 for exact-match coverage:

```python
def hyde_hybrid_retrieve(query: str, top_k: int = 10):
    hyde_embedding = embed(generate_hypothetical(query))
    vector_results = vector_store.search(hyde_embedding, top_k=20)
    bm25_results = bm25_index.search(query, top_k=20)  # raw query for BM25
    return reciprocal_rank_fusion([vector_results, bm25_results])[:top_k]
```

Use the raw query for BM25 (keywords matter) and the hypothetical for vector search (semantics matter).

## Latency and cost considerations

HyDE adds one LLM generation call per query before retrieval. Mitigations:

- **Cache hypotheticals** for frequent queries — embedding cache keyed on normalized query text.
- **Use a fast model** — Haiku, GPT-4o-mini, or a fine-tuned small model for hypothetical generation.
- **Route selectively** — apply HyDE only when a query classifier detects conceptual questions, not lookups.

```python
def retrieve(query: str):
    if is_exact_lookup(query):  # contains error codes, IDs, etc.
        return bm25_search(query)
    return hyde_retrieve(query)
```

## Evaluating HyDE on your corpus

Compare recall@10 on your eval set:

1. Embed raw query → search (baseline).
2. HyDE hypothetical → search.
3. HyDE + BM25 hybrid.

HyDE typically improves recall most on:

- Short queries (under 10 words).
- How-to and troubleshooting questions.
- Queries phrased in lay language against technical docs.

Gains are minimal on queries that already share vocabulary with corpus chunks.

## Limitations

- **Domain drift** — hypotheticals reflect the LLM's general knowledge, which may not match your product's terminology. Customize the HyDE prompt with domain context.
- **Not a replacement for good chunking** — if chunks are poorly split, HyDE cannot fix retrieval of fragmented context.
- **Added failure mode** — if hypothetical generation fails or times out, have a fallback to raw query embedding.

HyDE adds latency and cost per query — cache hypothetical documents for repeated question patterns before enabling in production.

## HyDE cost control

Generate hypothetical document once per unique query pattern:

```python
@lru_cache(maxsize=1000)
def hyde_embed(query: str) -> list[float]:
    hypothetical = llm.generate(f"Write a passage answering: {query}")
    return embed(hypothetical)
```

Cache by normalized query hash. Skip HyDE when bi-encoder confidence on direct embed exceeds threshold.

## Common production mistakes

Teams get hypothetical document embeddings wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

RAG pipelines for hypothetical document embeddings degrade when chunk boundaries split tables, embeddings go stale after doc updates, and retrieval metrics are measured offline only. Re-index incrementally and monitor answer faithfulness on live traffic samples.

## Debugging and triage workflow

When hypothetical document embeddings misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [HyDE paper — Gao et al. (2022)](https://arxiv.org/abs/2212.10496)
- [LangChain HyDE retriever](https://python.langchain.com/docs/how_to/hypothetical_prompts/)
- [LlamaIndex HyDE query transform](https://docs.llamaindex.ai/en/stable/examples/query_transformations/HyDE_query_transform/)
- [OpenAI embeddings guide](https://platform.openai.com/docs/guides/embeddings)
- [Anthropic contextual retrieval (complementary technique)](https://www.anthropic.com/news/contextual-retrieval)
