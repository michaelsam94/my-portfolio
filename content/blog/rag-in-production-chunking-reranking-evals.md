---
title: "RAG in Production: Chunking, Reranking, and Evals That Matter"
slug: "rag-in-production-chunking-reranking-evals"
description: "The RAG techniques that actually move retrieval quality in production: smart chunking, two-stage reranking, hybrid search, and evals that catch regressions early."
datePublished: "2026-01-13"
dateModified: "2026-01-13"
tags: ["RAG", "LLM", "Retrieval", "Evaluation"]
keywords: "RAG, retrieval augmented generation, reranking, chunking strategies, vector search, RAG evaluation"
faq:
  - q: "What is the biggest cause of bad RAG answers?"
    a: "In production, retrieval is the usual culprit — if the right chunk never makes it into context, no amount of prompt tuning saves the answer. Most quality gains come from better chunking, hybrid search, and reranking, not from a bigger generation model."
  - q: "What chunk size should I use for RAG?"
    a: "There's no universal number, but 300-800 tokens with 10-20% overlap is a sound starting point for prose. Chunk on semantic boundaries like headings and paragraphs rather than fixed character counts, and always evaluate a few sizes against your own queries."
  - q: "Do I need a reranker in my RAG pipeline?"
    a: "Usually yes. Retrieve a broad candidate set (say top 50) with vector or hybrid search, then use a cross-encoder reranker to reorder them and keep the top 5-8. Reranking consistently improves precision at the top for a small latency cost."
---

Most RAG systems that ship badly fail in the same place: retrieval, not generation. The model is fine; the right chunk simply never reaches its context. If you're debugging a RAG app that gives confident, wrong, or vague answers, spend your time on chunking, search, and reranking before you touch the prompt or upgrade the model. That's where the wins are.

I'll cover the pipeline the way it actually matters in production: how to chunk so the useful unit of text stays intact, how to combine vector and keyword search, why a reranking stage pays for itself, and — the part teams skip — how to build evals that tell you whether a change helped or quietly regressed retrieval.

## Chunking: the decision that quietly sets your ceiling

Chunking sets the upper bound on retrieval quality, because you can only retrieve what you stored as a unit. Fixed-size character splits are the default in every tutorial and the wrong default for real documents — they cut sentences in half and separate a claim from its qualifier.

Chunk on **semantic boundaries** instead. For structured docs (markdown, HTML, code), split on headings, sections, and paragraphs. For prose, aim for roughly 300–800 tokens per chunk with 10–20% overlap so a fact that straddles a boundary survives in at least one chunk. A few rules I hold to:

- **Keep structure as metadata.** Store the document title, section heading, and source URL alongside each chunk. Prepending the heading to the chunk text at embedding time meaningfully improves recall.
- **Don't strip tables and lists into prose.** They carry meaning in their layout; flatten them carefully or they become noise.
- **One idea per chunk, ideally.** Overstuffed chunks dilute the embedding; tiny chunks lose context. The sweet spot is empirical — test it.

There is no magic chunk size. The only way to know is to evaluate candidates against your real queries, which is why evals come before tuning, not after.

## Hybrid search beats pure vectors

Dense vector search is great at semantic similarity and bad at exact matches — product codes, error strings, names, acronyms. A user searching for `ERR_2043` wants that literal token, and an embedding may not surface it. The fix is **hybrid search**: run dense (vector) and sparse (keyword/BM25) retrieval, then fuse the results, commonly with Reciprocal Rank Fusion.

```python
def hybrid_search(query, k=50):
    dense = vector_index.search(embed(query), k=k)     # semantic
    sparse = bm25_index.search(query, k=k)             # lexical
    return reciprocal_rank_fusion([dense, sparse], k=k)
```

Hybrid retrieval consistently outperforms either method alone on mixed workloads, because real queries mix conceptual and literal intent. Most production [vector databases](https://blog.michaelsam94.com/vector-databases-in-production/) now support both dense and sparse indexes, so this is mostly a configuration and fusion concern rather than a second system.

## Reranking: cheap precision at the top

Retrieval optimizes for recall — cast a wide net, top 50 candidates. But you only feed the model 5–8 chunks, and their *order and relevance* is what matters. This is the job of a **reranker**: a cross-encoder that scores each (query, chunk) pair jointly and reorders the candidates.

The two-stage pattern is standard for a reason:

1. **Retrieve** a broad candidate set (top 50) cheaply with hybrid search.
2. **Rerank** those 50 with a cross-encoder and keep the top 6.

Cross-encoders are more accurate than the bi-encoders used for retrieval because they attend to the query and document together, but they're too slow to run over your whole corpus — hence the two stages. A hosted reranker (Cohere Rerank) or an open one (BGE reranker via [Hugging Face](https://huggingface.co/)) adds tens of milliseconds and routinely lifts top-k precision by double digits. In my experience it's the single highest-ROI addition to a naive RAG pipeline.

## Evals: how you know any of this worked

Here's the discipline most teams lack, and it's the reason they can't tell whether a change helped: **you need retrieval evals separate from answer evals.** If you only judge final answers, you can't tell whether a bad answer came from bad retrieval or bad generation.

Build a labeled set of 50–200 real queries with known relevant chunks, then track retrieval metrics:

| Metric | What it tells you |
| --- | --- |
| Recall@k | Did the right chunk make it into the top k at all? |
| Precision@k | How much of the top k is actually relevant? |
| MRR / nDCG | Is the best chunk near the top, not buried at position 10? |

These metrics let you compare chunk sizes, embedding models, and rerankers objectively. Change one variable, rerun, compare — no vibes. For a deeper treatment of the retrieval side, see [evaluating retrieval metrics for RAG](https://blog.michaelsam94.com/evaluating-retrieval-metrics-rag/).

For end-to-end answer quality, layer an LLM-as-judge eval on top — faithfulness (is the answer grounded in the retrieved chunks?) and relevance (does it answer the question?). The broader practice of building these harnesses is covered in [LLM evals for agent quality](https://blog.michaelsam94.com/llm-evals-measuring-agent-quality/). The key is running both tiers in CI so a "small" chunking tweak can't silently tank recall on your way to production.

## Putting it together

A production RAG pipeline that behaves looks like this, in order of impact:

1. **Chunk on semantic boundaries**, carry structure as metadata, tune size against evals.
2. **Retrieve with hybrid search** so both concepts and literals surface.
3. **Rerank** the candidate set with a cross-encoder; keep the top 6.
4. **Ground the generation** with citations so the model quotes sources, not memory.
5. **Eval retrieval and answers separately, in CI**, so regressions get caught before users do.

The unglamorous truth is that RAG quality is mostly a data and retrieval problem wearing an LLM costume. Get the chunks right, search both ways, rerank, and measure — and the generation step becomes the easy part.

## Resources

- [Cohere — Rerank documentation](https://docs.cohere.com/docs/rerank-overview)
- [Hugging Face — MTEB embedding & reranking leaderboard](https://huggingface.co/spaces/mteb/leaderboard)
- [Pinecone — Learn: RAG and retrieval](https://www.pinecone.io/learn/retrieval-augmented-generation/)
- [Ragas — RAG evaluation framework](https://docs.ragas.io/)
- [OpenAI — Retrieval and RAG guidance](https://platform.openai.com/docs/guides/retrieval)
- [Elastic — Reciprocal Rank Fusion explained](https://www.elastic.co/guide/en/elasticsearch/reference/current/rrf.html)
