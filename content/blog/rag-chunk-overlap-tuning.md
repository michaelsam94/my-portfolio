---
title: "Tuning Chunk Size and Overlap"
slug: "rag-chunk-overlap-tuning"
description: "Tune RAG chunk size and overlap for your corpus: how token windows, stride, and content type affect retrieval recall, precision, and generation quality."
datePublished: "2024-11-21"
dateModified: "2024-11-21"
tags: ["AI", "RAG", "Embeddings", "Retrieval"]
keywords: "chunk size tuning, chunk overlap RAG, text splitting, retrieval recall, token window, RAG optimization"
faq:
  - q: "What is a good starting chunk size for RAG?"
    a: "A common starting point is 512 tokens with 50–100 tokens of overlap for general prose documentation. Code and API references often need smaller chunks around 256 tokens because semantic units are shorter. Legal and policy documents sometimes need 1024 tokens to keep clauses intact. Always validate against your own eval set rather than copying defaults."
  - q: "Does more overlap always improve retrieval?"
    a: "Overlap helps when answers span chunk boundaries, but excessive overlap bloats your index and returns near-duplicate chunks that crowd out diverse results. Beyond 20–25% overlap relative to chunk size, marginal recall gains usually shrink while storage and latency costs keep growing. Measure duplicate chunk rate in your top-k results before increasing overlap further."
  - q: "Should chunk size match the embedding model's max input?"
    a: "Chunks should be at or below the embedding model's context limit, but matching the max exactly is rarely optimal. Smaller chunks produce more precise retrieval; larger chunks preserve surrounding context. The embedding limit is a ceiling, not a target — most production systems chunk well below it."
---

Your RAG pipeline retrieved the second half of a numbered procedure and the model told users to "complete step 5" without mentioning that step 5 only makes sense after the firewall rule from step 4. The chunk boundary fell between steps 4 and 5. Chunk size and overlap are not indexer trivia — they determine whether the right context survives the trip from document to embedding to top-k results.

## What chunk size controls

Chunk size is the maximum number of tokens (or characters) per indexed segment. It trades off two retrieval behaviors:

- **Smaller chunks** — higher precision. The embedding represents a focused idea, so matches are specific. Risk: surrounding context is lost.
- **Larger chunks** — higher context preservation. Definitions stay attached to the terms they define. Risk: embeddings average over multiple topics, diluting relevance scores.

A 256-token chunk might perfectly capture one API parameter description. A 1024-token chunk might capture an entire tutorial section but score poorly when the user asks about one function mentioned in passing.

## What overlap controls

Overlap is the number of tokens shared between consecutive chunks — a stride less than the chunk size. A 512-token window with 64-token overlap means each new chunk starts 448 tokens after the previous one.

Overlap exists to keep sentences and facts that straddle boundaries visible in at least one complete chunk. Without overlap, the embedding for "step 4" and the embedding for "step 5" live in different vectors, and a query about the full procedure might miss both.

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,
    chunk_overlap=64,
    length_function=len,  # swap for tiktoken in production
    separators=["\n\n", "\n", ". ", " ", ""],
)

chunks = splitter.split_documents(documents)
```

`RecursiveCharacterTextSplitter` tries larger separators first — paragraphs, then lines, then sentences — so boundaries land on natural breaks rather than mid-word.

## Tuning methodology that actually works

Do not guess. Build a retrieval eval set with 50–100 question–document pairs where you know which passage contains the answer.

1. **Baseline** — run your eval at chunk sizes 256, 512, 768, 1024 with overlap at 10%, 15%, 20% of chunk size.
2. **Measure recall@k** — does the correct chunk appear in top-5 results?
3. **Measure answer quality** — run generation and score factual correctness separately from retrieval. High recall with bad answers means chunks are too small; low recall with good answers when correct chunks appear means generation is the bottleneck.
4. **Check duplicate rate** — count how many top-5 results are near-identical overlaps. Above 30% duplication, reduce overlap or deduplicate at query time.

| Corpus type | Starting chunk size | Starting overlap |
|-------------|--------------------:|-----------------:|
| Technical docs / prose | 512 tokens | 64–80 tokens |
| API / code reference | 256–384 tokens | 32–48 tokens |
| Legal / policy | 768–1024 tokens | 100–128 tokens |
| Chat logs / tickets | 384 tokens | 48 tokens |
| Tables / structured data | Per-row or per-section | Minimal |

## Content-specific adjustments

**Code:** Split on function and class boundaries when possible. A 512-token chunk spanning two unrelated functions retrieves poorly for either.

**Tables:** Row-based or section-based chunking beats naive character splitting. Half a table is worse than no table.

**Markdown headers:** `MarkdownHeaderTextSplitter` keeps sections under their headings intact up to the size limit. Documentation with clear hierarchy benefits enormously.

**PDFs:** Extraction artifacts — broken lines, header/footer repetition — affect effective chunk size. Clean extraction before splitting matters more than tuning overlap on garbage input.

## Overlap vs parent-document retrieval

Overlap duplicates content in the index. An alternative is small chunks for retrieval with a parent-document pattern: retrieve the small chunk, return the parent section to the LLM. This gives precise search without index bloat.

Choose overlap when storage is cheap and your pipeline is simple. Choose parent-document when index size and duplicate results are already problems.

## Production monitoring

Track these signals after deployment:

- **Empty retrieval rate** — queries returning zero chunks above threshold.
- **Average chunks per query** — sudden drops may indicate index corruption.
- **User thumbs-down correlated with chunk IDs** — identifies systematic boundary failures.

Re-tune when you add new document types or switch embedding models. A new model's optimal chunk size is not guaranteed to match the old one.

## Common production mistakes

Teams get chunk overlap tuning wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

RAG pipelines for chunk overlap tuning degrade when chunk boundaries split tables, embeddings go stale after doc updates, and retrieval metrics are measured offline only. Re-index incrementally and monitor answer faithfulness on live traffic samples.

## Debugging and triage workflow

When chunk overlap tuning misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [LangChain text splitters documentation](https://python.langchain.com/docs/how_to/recursive_text_splitter/)
- [LlamaIndex node parser and chunking guide](https://docs.llamaindex.ai/en/stable/module_guides/indexing/)
- [OpenAI embedding model documentation](https://platform.openai.com/docs/guides/embeddings)
- [Pinecone — chunking strategies for RAG](https://www.pinecone.io/learn/chunking-strategies/)
- [Chroma — embedding tips and chunk size](https://docs.trychroma.com/guides/embeddings)
