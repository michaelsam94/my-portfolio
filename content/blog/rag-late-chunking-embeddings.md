---
title: "Late Chunking for Long Documents"
slug: "rag-late-chunking-embeddings"
description: "Apply late chunking to long-document RAG: embed full documents first, then pool token embeddings into chunks for context-aware vectors without oversized inputs."
datePublished: "2024-12-31"
dateModified: "2024-12-31"
tags: ["AI", "RAG", "Embeddings", "Chunking"]
keywords: "late chunking, long document RAG, contextual embeddings, token pooling, Jina embeddings, document chunking"
faq:
  - q: "What is late chunking?"
    a: "Late chunking reverses the usual order: instead of splitting text into chunks and embedding each independently, you pass the full document (or a large section) through the embedding model first, then pool token-level embeddings into chunk-level vectors. Each chunk's embedding encodes awareness of the surrounding document context, fixing the out-of-context problem without generating separate context blurbs per chunk."
  - q: "How is late chunking different from contextual retrieval?"
    a: "Contextual retrieval prepends an LLM-generated description to each chunk before embedding — adding indexing cost and latency. Late chunking achieves similar context awareness by leveraging the embedding model's attention over the full document during the forward pass. Late chunking requires a model that exposes token-level embeddings and supports long inputs; contextual retrieval works with any embedding model."
  - q: "What embedding models support late chunking?"
    a: "Jina AI's late chunking implementation works with their jina-embeddings-v3 model and open models like nomic-embed and others that expose per-token hidden states. Standard API-only embedding endpoints that return a single vector per input text do not support late chunking unless they offer a token-level mode. Check your model's documentation for token embedding access before adopting this approach."
---

Early chunking embeds `"set TIMEOUT_MS to 5000"` in isolation and hopes the vector somehow encodes that it belongs to the payment webhook handler section of a 30-page runbook. It does not. Late chunking runs the entire section through the embedding model first — letting attention layers see every surrounding sentence — then slices the token embeddings into chunk-sized pools. The resulting vectors know their neighborhood because the model read the neighborhood.

## Early vs late chunking

**Early chunking (standard):**

```
Document → Split into chunks → Embed each chunk independently
```

Each chunk embedding sees only its own tokens. Context from adjacent paragraphs is lost.

**Late chunking:**

```
Document → Pass full text through embedding model →
Extract per-token embeddings → Pool tokens into chunk vectors
```

Each chunk embedding is derived from a forward pass that attended to the full document (up to model context limit).

```python
# Conceptual late chunking flow
def late_chunk_embed(document: str, chunk_boundaries: list[tuple[int, int]]):
    # Full document through model — returns per-token embeddings
    token_embeddings = model.encode_tokens(document)

    chunk_embeddings = []
    for start, end in chunk_boundaries:
        # Mean-pool token embeddings for this chunk's token range
        chunk_emb = token_embeddings[start:end].mean(dim=0)
        chunk_embeddings.append(chunk_emb)

    return chunk_embeddings
```

Chunk boundaries are determined upfront by a text splitter, but embedding happens after the model has processed the complete context.

## Why this matters for long documents

Standard chunking breaks contextual dependencies:

- Pronouns and references ("this setting", "the above service") lose their antecedents.
- Technical parameters lose their scope (which service, which environment).
- Numbered procedures split across chunks lose sequential context.

Contextual retrieval (Anthropic's approach) fixes this by generating a text preamble per chunk. Late chunking fixes it at the embedding level — no extra LLM calls, no generated context text to store.

## Model requirements

Late chunking needs:

1. **Token-level embedding access** — the model returns hidden states per token, not just a pooled sentence embedding.
2. **Long context support** — the document (or section) must fit within the model's context window.
3. **Consistent tokenizer** — chunk boundaries are defined in token offsets, not character offsets.

Jina AI's `jina-embeddings-v3` explicitly supports this via their late chunking API. Open-source models with accessible hidden states work with custom pooling code.

## Handling documents exceeding context limits

When a document exceeds the embedding model's context window:

1. **Section-level late chunking** — split on headings first, late-chunk within each section. Sections under the limit get full context; megasections still need further splitting.
2. **Sliding window with overlap** — process overlapping windows, assign token embeddings to chunks by majority overlap.
3. **Hierarchical** — late-chunk at section level, then early-chunk (standard) only for sections that still exceed limits.

```python
def late_chunk_document(document: str, max_tokens: int = 8192):
    sections = split_on_headings(document)
    all_chunks = []

    for section in sections:
        if token_count(section) <= max_tokens:
            boundaries = recursive_split_boundaries(section)
            embeddings = late_chunk_embed(section, boundaries)
            all_chunks.extend(zip(boundaries, embeddings))
        else:
            # Fall back to early chunking for oversized sections
            all_chunks.extend(early_chunk_embed(section))

    return all_chunks
```

## Evaluating late chunking vs alternatives

On your eval set, compare:

1. Early chunking (baseline).
2. Contextual retrieval (LLM-generated context prepended).
3. Late chunking.

Measure recall@10, especially on questions targeting mid-document chunks from long files. Late chunking and contextual retrieval often perform similarly on this subset, but late chunking avoids per-chunk LLM generation cost.

Late chunking may underperform on very short self-contained chunks where context adds noise — FAQ entries, glossary definitions.

## Production considerations

- **Indexing throughput** — processing full documents through the model is slower than embedding small chunks. Batch by document and parallelize across workers.
- **Re-indexing** — any edit to a document requires re-embedding the affected section, not just the changed chunk. Track section-level hashes for incremental updates.
- **Storage** — chunk vectors are the same dimensionality as early chunking. No additional storage for context text.

Late chunking requires same embedding model at index and query time — model swap invalidates entire index without re-embedding.

## Comparison with contextual retrieval

| Approach | Index cost | Query cost | Context quality |
|----------|------------|------------|-----------------|
| Early chunking | Low | Low | Poor for mid-doc chunks |
| Contextual retrieval (Anthropic) | High (LLM per chunk) | Low | High |
| Late chunking (Jina) | Medium (full doc embed) | Low | High |

Contextual retrieval prepends LLM-generated context to each chunk at index time. Late chunking achieves similar boundary awareness without per-chunk LLM calls — choose based on indexing budget.

## Query-side late chunking

Some implementations apply late chunking at query time too — embed full query, extract token-level representations, match against chunk token embeddings. Symmetric index/query processing improves retrieval for multi-part questions spanning chunk boundaries.

## When to skip late chunking

- Documents under 512 tokens — early chunking is equivalent
- Real-time indexing requirements — late chunking adds latency per document
- Embedding models without long-context support (< 8K tokens)

Pair with [RAG metadata filtering hybrid](https://blog.michaelsam94.com/rag-metadata-filtering-hybrid/) when combining late-chunked embeddings with metadata pre-filters.

## Common production mistakes

Teams get late chunking embeddings wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

RAG pipelines for late chunking embeddings degrade when chunk boundaries split tables, embeddings go stale after doc updates, and retrieval metrics are measured offline only. Re-index incrementally and monitor answer faithfulness on live traffic samples.

## Resources

- [Jina AI late chunking blog post](https://jina.ai/news/late-chunking-in-long-context-embedding-models/)
- [Jina embeddings v3 documentation](https://jina.ai/embeddings/)
- [Anthropic contextual retrieval (alternative approach)](https://www.anthropic.com/news/contextual-retrieval)
- [Nomic embed — open embedding models](https://www.nomic.ai/blog/posts/nomic-embed-text-v1)
- [Hugging Face — mean pooling for sentence embeddings](https://huggingface.co/blog/getting-started-with-embeddings)
