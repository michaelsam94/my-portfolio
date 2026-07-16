---
title: "Choosing an Embeddings Model in 2026"
slug: "choosing-an-embeddings-model"
description: "A practical guide to choosing an embeddings model in 2026: dimensions, MTEB scores, cost, latency, and self-hosted vs API tradeoffs for real retrieval systems."
datePublished: "2026-03-06"
dateModified: "2026-03-06"
tags: ["Embeddings", "RAG", "Machine Learning", "Search"]
keywords: "embeddings model, text embeddings, embedding dimensions, MTEB, choose embeddings, vector embeddings"
faq:
  - q: "How do I choose an embeddings model?"
    a: "Start from your constraints: retrieval quality on your own data, latency, cost, and whether you can self-host. Use MTEB as a shortlist, then benchmark the top two or three on your actual documents and queries — leaderboard rank rarely survives contact with your domain."
  - q: "Do more embedding dimensions mean better results?"
    a: "Not necessarily. Higher dimensions capture more nuance but cost more to store and search, and the retrieval-quality gains often plateau. Many 2026 models support Matryoshka truncation, letting you shorten vectors and trade a little accuracy for big storage and speed savings."
  - q: "Should I use an API embeddings model or self-host?"
    a: "Use an API when volume is moderate and you want zero ops. Self-host an open model when you have high volume, strict data-residency requirements, or need to avoid per-token costs at scale. The break-even is usually about cost and privacy, not quality."
---

The embeddings model is the quietest and most consequential decision in any retrieval system. It sets the ceiling on how good your search or RAG can be — no reranker or clever prompt recovers relevance the embeddings failed to capture — and yet people pick one off a leaderboard and never revisit it. Choosing an embeddings model well in 2026 comes down to four things: retrieval quality *on your data*, dimensions, cost, and whether you self-host.

I'll walk through how I actually make this call, because the honest answer is "it depends," and the interesting part is on what.

## Start with MTEB, but don't stop there

The [MTEB leaderboard](https://huggingface.co/spaces/mteb/leaderboard) is the right place to build a shortlist. It scores models across retrieval, clustering, classification, and reranking on dozens of datasets, and the retrieval tab is what matters for RAG. But the leaderboard measures performance on *its* datasets, not yours. Legal contracts, Arabic support tickets, EV-charging telemetry logs, and React component docs are all "text," and no single ranking predicts all of them.

So MTEB narrows the field to maybe three candidates; then you benchmark those three on your own corpus. This is non-negotiable and cheaper than it sounds:

```python
# Minimal retrieval eval on your own labeled query->doc pairs
def recall_at_k(model, queries, gold, k=5):
    hits = 0
    for q, gold_doc in zip(queries, gold):
        results = search(model.embed(q), top_k=k)
        if gold_doc in [r.id for r in results]:
            hits += 1
    return hits / len(queries)
```

A couple hundred labeled query/answer pairs is enough to see clear separation. I've had a leaderboard #4 beat a #1 by a wide margin on a domain-specific corpus. For a deeper treatment of scoring retrieval, see [evaluating retrieval metrics](https://blog.michaelsam94.com/evaluating-retrieval-metrics-rag/).

## Dimensions: bigger isn't automatically better

Embedding dimension is a direct cost lever. A 3072-dim vector takes twice the storage and roughly twice the search compute of a 1536-dim one, and the retrieval gain is often small. In 2026 the important development is **Matryoshka representation learning** — models trained so you can truncate the vector to a shorter prefix and keep most of the quality.

That means you're no longer stuck with the model's native size. A model that outputs 1024 dims might let you use the first 256 with only a couple points of recall loss, cutting your vector store footprint by 4x. The practical workflow:

| Dimension | Relative storage | Typical recall impact |
|---|---|---|
| Full (e.g. 1024) | 1.0x | baseline |
| Truncated to 512 | 0.5x | ~1-2 pts lower |
| Truncated to 256 | 0.25x | ~3-5 pts lower |

Test the truncated sizes on your eval set and pick the smallest one that clears your quality bar. Storage and query latency in a [production vector database](https://blog.michaelsam94.com/vector-databases-in-production/) scale directly with this number, so it compounds.

## Cost and latency

There are two cost axes: indexing (embed your whole corpus once, plus updates) and querying (embed every incoming query, on the hot path). API models charge per token for both. If you're embedding millions of documents, indexing cost alone can dwarf everything else, and that's where self-hosting an open model starts to pay.

Latency matters more on the query side because it's user-facing. An API round trip adds 100-300ms before you've even searched; a small self-hosted model on a GPU can embed a short query in single-digit milliseconds. If you also run a [semantic cache](https://blog.michaelsam94.com/semantic-caching-llm-apis/), query embedding latency lands on your critical path for every request, which is another argument for a small, fast model there.

## API vs self-hosted

The decision tree I use:

- **Use an API model** (OpenAI, Cohere, Voyage, Google) when volume is moderate, you don't want to run GPUs, and your data can leave your perimeter. Zero ops, strong quality, and you can switch models with a config change.
- **Self-host an open model** (the current strong open families in the BGE / E5 / GTE / Qwen lineages) when you have high volume, strict data residency or privacy needs, or want predictable cost at scale. The tradeoff is you now own inference infra, batching, and model updates.

For anything touching regulated or personal data — which, given [privacy engineering on mobile](https://blog.michaelsam94.com/privacy-engineering-mobile-gdpr/) constraints, is a lot of my work — self-hosting isn't just cheaper, it removes a whole class of data-handling questions.

## Practical gotchas

A few things that have bitten me:

- **Match query and document encoding.** Some models expect an instruction prefix like `"query: "` vs `"passage: "`. Forgetting this silently tanks recall — the vectors land in different regions of the space.
- **Normalize consistently.** If you index with normalized vectors and query without (or mix cosine and dot product), your scores are meaningless. Pick one and enforce it.
- **Model upgrades mean full re-indexing.** Embeddings from two different models are not comparable, so changing models requires re-embedding your entire corpus. Budget for it, and version your index by model name.
- **Multilingual is a real axis.** If your corpus mixes languages (mine often mixes English and Arabic), you need a genuinely multilingual model, not an English one with token coverage. Benchmark cross-lingual retrieval specifically.

## What I'd actually pick

For a new English-heavy RAG system with moderate volume, I default to a strong API model, truncate the dimensions to the smallest size that passes my eval, and add a [reranker](https://blog.michaelsam94.com/rag-in-production-chunking-reranking-evals/) on top — the reranker often matters more than squeezing the last point out of the embeddings. For high-volume or privacy-sensitive systems, I self-host a top open model and eat the ops cost.

The meta-lesson after doing this several times: the model matters less than the discipline. A mid-tier model with a good eval loop and a reranker beats a top-tier model chosen on vibes. Build the eval first, then the choice makes itself.

## Resources

- [MTEB leaderboard on Hugging Face](https://huggingface.co/spaces/mteb/leaderboard)
- [MTEB paper (arXiv)](https://arxiv.org/abs/2210.07316)
- [Matryoshka Representation Learning (arXiv)](https://arxiv.org/abs/2205.13147)
- [OpenAI embeddings guide](https://platform.openai.com/docs/guides/embeddings)
- [Sentence Transformers documentation](https://www.sbert.net/)
- [Cohere embeddings documentation](https://docs.cohere.com/docs/embeddings)
