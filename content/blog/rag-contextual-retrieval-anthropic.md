---
title: "Contextual Retrieval for Better RAG"
slug: "rag-contextual-retrieval-anthropic"
description: "Implement Anthropic's contextual retrieval: prepend chunk-specific context before embedding to fix out-of-context chunks and improve retrieval recall."
datePublished: "2024-12-03"
dateModified: "2024-12-03"
tags: ["AI", "RAG", "Embeddings", "Anthropic"]
keywords: "contextual retrieval, Anthropic RAG, chunk context, contextual embeddings, retrieval recall, document chunking"
faq:
  - q: "What problem does contextual retrieval solve?"
    a: "Standard RAG embeds chunks in isolation, so a chunk saying 'the threshold is 500ms' loses the information that it refers to API latency limits in the payments service. Contextual retrieval prepends a generated summary of the parent document and section to each chunk before embedding, giving the vector a much richer semantic signal. Anthropic reported up to 49% fewer failed retrievals when combining contextual embeddings with BM25."
  - q: "Does contextual retrieval require an LLM call per chunk?"
    a: "Yes, at index time you generate a short context blurb for each chunk using an LLM — typically 50 to 100 tokens describing what document and section the chunk belongs to. For large corpora this adds indexing cost, but it is a one-time expense per document version. Cache context by document and reuse when only small sections change."
  - q: "Can I use contextual retrieval with any embedding model?"
    a: "Contextual retrieval is model-agnostic — it changes what you embed, not how embeddings work. Apply the same prepend step before sending text to OpenAI, Cohere, Voyage, or open-source embedding models. Re-evaluate retrieval quality after switching models because optimal context blurb length may shift."
---

A chunk containing only `"Retry after 30 seconds with exponential backoff"` scored poorly for the query "How should payment webhook handlers deal with rate limits?" — because stripped of its surroundings, those words could describe anything from database connections to UI debouncing. The chunk was correct; the embedding was lost. Anthropic's contextual retrieval fixes this by giving every chunk a prose frame before it hits the vector index.

## The out-of-context chunk problem

Document splitters produce chunks optimized for size, not self-containment. A chunk from the middle of a 40-page runbook might say "set `TIMEOUT_MS` to 5000" with no mention of which service, which environment, or which version introduced that variable. The embedding captures "timeout configuration" but not "payment webhook handler in production."

Users query with domain vocabulary. Chunks without context create a semantic gap between query embeddings and chunk embeddings, even when the answer is technically in your index.

## How contextual retrieval works

At index time, for each chunk:

1. Send the full document (or a large window) plus the chunk to an LLM.
2. Ask the model to generate a short contextual description — typically 50–100 tokens — situating the chunk within the document.
3. Prepend that context to the chunk text.
4. Embed the combined `context + chunk` string.

```python
CONTEXT_PROMPT = """
<document>
{whole_document}
</document>

Here is the chunk we want to situate within the whole document:
<chunk>
{chunk_text}
</chunk>

Give a short succinct context to situate this chunk within the
overall document for the purposes of improving search retrieval
of the chunk. Answer only with the succinct context and nothing else.
"""

def contextualize_chunk(document: str, chunk: str) -> str:
    context = llm.generate(CONTEXT_PROMPT.format(
        whole_document=document, chunk_text=chunk
    ))
    return f"{context}\n\n{chunk}"
```

The generated context might read: *"This chunk is from the Payments Webhook Runbook, section on rate limit handling for production environments, describing retry timing after HTTP 429 responses."* That framing dramatically improves embedding alignment with user queries.

## Cost management at index time

LLM calls per chunk add up on large corpora. Mitigations:

- **Document-level caching** — if a document has 50 chunks, the full document stays in the prompt context; only the chunk portion changes. Batch multiple chunks per API call where the model supports it.
- **Incremental re-indexing** — regenerate context only for changed sections, not the entire corpus on every deploy.
- **Cheaper models for context generation** — Haiku, GPT-4o-mini, or similar handle this task well. You do not need your generation model for indexing.
- **Template fallback for structured docs** — if metadata already provides document title, section heading, and product name, a template like `"{title} > {section}: {chunk}"` captures 80% of the benefit at zero LLM cost.

## Pairing with BM25 hybrid search

Anthropic's results showed contextual embeddings alone reduce failed retrievals by roughly 35%. Adding BM25 keyword search on the same contextualized chunks — reciprocal rank fusion to merge results — pushes reduction to roughly 49%.

Keyword search catches exact matches — error codes, variable names, product IDs — that embeddings miss. Contextual framing helps BM25 too because the prepended text includes terms the raw chunk omitted.

```python
def hybrid_search(query: str, top_k: int = 10):
    dense_results = vector_search(query, top_k=top_k)
    sparse_results = bm25_search(query, top_k=top_k)
    return reciprocal_rank_fusion(dense_results, sparse_results)
```

## Evaluating contextual retrieval on your corpus

Run A/B retrieval evals:

- **Baseline** — embed raw chunks.
- **Template context** — prepend title + section from metadata.
- **LLM context** — full contextual retrieval.

Measure recall@10 on questions where you know the correct chunk. Contextual retrieval helps most on mid-document chunks from long files — exactly where standard chunking fails hardest. It helps least on self-contained chunks like FAQ entries where the question and answer live in the same paragraph.

## When to skip it

Skip LLM-generated context when:

- Chunks are already self-contained (short FAQs, glossary entries).
- Rich metadata provides equivalent framing at index time.
- Indexing budget is zero and template context is sufficient.

Do not skip evaluation — measure before assuming your metadata is good enough.

## Contextual retrieval prepended chunks

At index time, LLM generates context for each chunk:

```
"Document: Employee handbook. Section: PTO policy. {chunk_text}"
```

25–30% recall improvement on Anthropic benchmarks — costs one LLM call per chunk at index time.

## Common production mistakes

Teams get contextual retrieval anthropic wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

RAG pipelines for contextual retrieval anthropic degrade when chunk boundaries split tables, embeddings go stale after doc updates, and retrieval metrics are measured offline only. Re-index incrementally and monitor answer faithfulness on live traffic samples.

## Debugging and triage workflow

When contextual retrieval anthropic misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Anthropic — contextual retrieval announcement](https://www.anthropic.com/news/contextual-retrieval)
- [Anthropic contextual retrieval cookbook](https://github.com/anthropics/anthropic-cookbook)
- [Voyage AI embedding models](https://docs.voyageai.com/)
- [BM25 and hybrid search in LlamaIndex](https://docs.llamaindex.ai/en/stable/examples/retrievers/bm25_retriever/)
- [Reciprocal rank fusion explained](https://www.elastic.co/guide/en/elasticsearch/reference/current/rrf.html)
