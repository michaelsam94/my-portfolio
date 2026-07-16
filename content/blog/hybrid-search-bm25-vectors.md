---
title: "Hybrid Search: Combining BM25 and Vectors"
slug: "hybrid-search-bm25-vectors"
description: "How hybrid search combines BM25 and vector retrieval with rank fusion to beat either alone: when keyword wins, when semantics wins, and how to merge them."
datePublished: "2026-03-05"
dateModified: "2026-03-05"
tags: ["RAG", "Retrieval", "Search", "LLM"]
keywords: "hybrid search, BM25, vector search, reciprocal rank fusion, keyword vs semantic, dense sparse retrieval"
faq:
  - q: "What is hybrid search?"
    a: "Hybrid search combines a sparse keyword retriever like BM25 with a dense vector retriever, then merges their results into a single ranked list. It exists because the two methods fail in different, complementary ways: keyword search nails exact terms, IDs, and rare words but misses paraphrases, while vector search captures meaning but can miss literal matches. Fusing them recovers relevant documents that either method alone would drop."
  - q: "When does BM25 beat vector search?"
    a: "BM25 wins on exact-match needs: product SKUs, error codes, function names, proper nouns, and any rare token where the literal string matters. It also degrades gracefully on out-of-domain vocabulary because it does not depend on an embedding model having seen the term. For keyword-heavy or technical corpora, a well-tuned BM25 is a surprisingly strong baseline that pure vector systems often underperform."
  - q: "How do you combine BM25 and vector scores?"
    a: "The most robust method is Reciprocal Rank Fusion, which merges results by rank position rather than raw score, sidestepping the problem that BM25 and cosine scores are on incompatible scales. Each document gets a score of the sum over retrievers of 1 divided by (k plus its rank), and you sort by that combined value. It requires no score normalization and works well out of the box."
---

Pick one retrieval method and you inherit its blind spots. Hybrid search is the fix: run BM25 keyword retrieval and dense vector retrieval side by side, then fuse their results into one ranked list that's better than either produces alone. The reason it works is that the two approaches fail in *opposite* directions — keyword search misses paraphrases, vector search misses exact tokens — so combining them patches each other's holes.

I reach for hybrid by default now on any serious RAG system. The number of times a pure-vector setup confidently failed to find a document because the user typed an exact error code the embedding model had smoothed into mush finally convinced me. Here's the mental model and the implementation.

## Two retrievers, two failure modes

**BM25** is sparse, lexical retrieval. It scores documents by term overlap, weighting rare terms higher and long documents lower. It's decades old, runs on an inverted index, needs no GPU, and is shockingly hard to beat on the right query. Its strength is literal matching: `ERR_CONN_4021`, `useEffect`, a specific part number. Its weakness is that it has no idea "car" and "automobile" are related — different tokens, zero overlap.

**Vector search** is dense, semantic retrieval. It embeds query and documents into a shared space and finds nearest neighbors by cosine similarity. Its strength is meaning: it matches "how do I cancel my plan" to a doc titled "subscription termination" with no shared keywords. Its weakness is the mirror image of BM25's — it can miss an exact rare token because the embedding blurs it into a neighborhood of "similar" words, and it degrades on out-of-domain vocabulary the model never really learned.

| Query type | BM25 | Vector |
| --- | --- | --- |
| Exact code / ID / SKU | Excellent | Unreliable |
| Rare technical term | Strong | Weak |
| Paraphrase / synonym | Poor | Excellent |
| Conceptual / fuzzy intent | Weak | Strong |
| Out-of-domain vocabulary | Robust | Fragile |

Look at that table and the case for hybrid is obvious: real query streams contain all of these rows, and no single column wins every one.

## Fusing results without a scale war

The obvious idea — add the BM25 score to the cosine score — fails, because they're on incompatible, unnormalized scales. BM25 might return 14.2; cosine returns 0.81. Summing them lets one method dominate arbitrarily.

**Reciprocal Rank Fusion (RRF)** sidesteps this entirely by ignoring raw scores and fusing on *rank position*. A document's fused score is the sum, across retrievers, of `1 / (k + rank)`, where `k` is a small constant (60 is the common default). No normalization, no tuning of relative weights, works out of the box:

```python
def rrf(result_lists, k=60):
    scores = {}
    for results in result_lists:            # e.g. [bm25_hits, vector_hits]
        for rank, doc_id in enumerate(results):
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
    return sorted(scores, key=scores.get, reverse=True)

fused = rrf([bm25_top50, vector_top50])
top_k = fused[:10]
```

A document that ranks #1 in one retriever and #40 in the other still bubbles up; a document both retrievers rank highly rockets to the top. That "agreement is rewarded" behavior is exactly what you want. If you need to favor one retriever, you can weight the terms, but I'd start with plain RRF and only add weights if evals demand it.

## Where hybrid slots into the stack

Hybrid search is a retrieval-stage decision. Both retrievers pull their top ~50 candidates, RRF fuses them, and you pass the merged top-k downstream. In a serious pipeline that downstream step is usually a cross-encoder reranker that reorders the fused set by true relevance — the two techniques stack, they don't compete. The reranking half of that story, plus how it interacts with chunking and evals, is something I go into in [RAG in production: chunking, reranking, and evals](https://blog.michaelsam94.com/rag-in-production-chunking-reranking-evals/).

The vector half of hybrid also inherits all the operational realities of running an ANN index at scale — recall/latency tradeoffs, filtering, index rebuilds — which I cover separately in [vector databases in production](https://blog.michaelsam94.com/vector-databases-in-production/). Hybrid doesn't remove those concerns; it just adds a sparse index alongside them.

## The honest costs

Hybrid isn't free, and pretending otherwise sets teams up for surprise:

- **Two indexes to maintain.** You now run and keep in sync an inverted index (Elasticsearch/OpenSearch, Lucene, or a vector DB's built-in sparse support) and a vector index. Ingestion writes to both; drift between them causes weird gaps.
- **Higher latency.** You issue two queries and a fusion step. Usually tens of milliseconds, but it's not zero, and the slower retriever gates your response.
- **More tuning surface.** BM25 has its own knobs (`k1`, `b`), the fusion has `k`, and each retriever's top-N affects recall. More levers, more ways to misconfigure.

My rule: if your corpus is heavy on codes, names, or jargon, hybrid pays for itself immediately. If it's pure prose and users ask conceptual questions, pure vector may be enough and simpler. Measure before you assume — which means having a retrieval eval set, the same discipline behind [evaluating retrieval metrics for RAG](https://blog.michaelsam94.com/evaluating-retrieval-metrics-rag/). Decide with recall@k numbers, not vibes.

## Practical defaults that work

If you're standing up hybrid today, here's the configuration I'd start from and only change with evidence:

1. Retrieve top 50 from BM25 and top 50 from vectors.
2. Fuse with RRF, `k = 60`, equal weights.
3. Take the fused top 20 into a cross-encoder reranker.
4. Pass the reranked top 5–8 to the model.
5. Keep a golden query set spanning exact-match, paraphrase, and conceptual queries, and track recall@k on every change.

The single most common mistake I see is teams treating "we added vectors" as automatically better and quietly regressing on exact-match queries their old keyword search handled fine. Hybrid is how you get the semantic upside without paying that tax. It's a little more machinery, but for most real corpora it's the retrieval setup that stops surprising you — and in search, boring and reliable is the whole goal.

## Resources

- [Elasticsearch — reciprocal rank fusion](https://www.elastic.co/guide/en/elasticsearch/reference/current/rrf.html)
- [Original BM25 / Okapi reference (Robertson & Zaragoza)](https://www.staff.city.ac.uk/~sbrp622/papers/foundations_bm25_review.pdf)
- [Weaviate — hybrid search documentation](https://weaviate.io/developers/weaviate/search/hybrid)
- [Pinecone — sparse-dense hybrid search](https://docs.pinecone.io/guides/data/understanding-hybrid-search)
- [OpenSearch — neural and hybrid search](https://opensearch.org/docs/latest/search-plugins/hybrid-search/)
