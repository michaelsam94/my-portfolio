---
title: "Semantic Caching for LLM APIs"
slug: "semantic-caching-llm-apis"
description: "How semantic caching cuts LLM API latency and cost by reusing answers to similar questions. Embeddings, thresholds, invalidation, and the failure modes to avoid."
datePublished: "2026-03-04"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "semantic caching, LLM cache, embeddings cache, reduce LLM latency, cache LLM responses, similarity cache"
faq:
  - q: "Semantic vs exact cache?"
    a: "Semantic uses embeddings to match meaning, not literal strings."
  - q: "Main risk?"
    a: "False hits — wrong answer fast is worse than slow correct answer."
  - q: "Cache scope?"
    a: "Include model version, system prompt hash, and tenant in cache key scope."
---

Exact-match caching does almost nothing for LLM traffic. Users never phrase the same question the same way twice — "how do I cancel my subscription," "cancel subscription," and "I want to stop paying" are three cache misses that all deserve one answer. Semantic caching fixes this by keying on *meaning* instead of the literal string, and when it works it turns a 2-second, few-cents LLM call into a 15-millisecond lookup that costs effectively nothing.

I've built this into a couple of production RAG and support-assistant systems, and it's one of the highest-leverage optimizations available — but it has a sharp edge. A too-eager cache confidently returns the wrong answer, which is far worse than being slow. Here's how it actually works and how to keep it honest.

## The core idea

A semantic cache sits in front of your LLM call. For each incoming prompt you:

1. Embed the prompt into a vector.
2. Search a vector store for the nearest previously-seen prompt.
3. If the nearest neighbor's similarity is above a threshold, return its stored response — a cache hit.
4. Otherwise call the LLM, then store the new prompt embedding + response for next time.

```python
def semantic_cache_lookup(prompt: str, threshold: float = 0.92):
    vec = embed(prompt)                      # e.g. a small embeddings model
    hit = vector_store.query(vec, top_k=1)
    if hit and hit.score >= threshold:
        return hit.metadata["response"], True   # cache hit
    response = call_llm(prompt)
    vector_store.upsert(vec, metadata={
        "prompt": prompt,
        "response": response,
        "ts": time.time(),
    })
    return response, False
```

That's the whole mechanism. The engineering is entirely in the details — the threshold, what you scope the cache to, and when you invalidate.

## The threshold is everything

The single number that decides whether this helps or hurts is the similarity threshold. Set it too high (say 0.99 with cosine similarity) and you get almost no hits — you've reinvented exact matching. Set it too low (0.80) and you start serving the answer for "how do I upgrade my plan" to someone who asked "how do I downgrade my plan," which are semantically close but operationally opposite.

There's no universal right value; it depends on your embeddings model and domain. What worked for me was to log candidate hits *without serving them* for a week — record the prompt, the matched prompt, and the score — then eyeball where false matches start creeping in. In one support system the safe line sat around 0.93 cosine; below that, antonym pairs ("enable"/"disable") started colliding. Measure it against your own traffic; don't copy someone's number.

## Scope the cache, don't make it global

The biggest real-world mistake I see is a single global cache. If your responses depend on the user (their plan, their locale, their permissions) or on time (prices, availability), a global cache leaks one user's answer to another and serves stale data.

The fix is to include those variables in the cache key namespace:

```python
namespace = f"{tenant_id}:{locale}:{plan_tier}"
hit = vector_store.query(vec, top_k=1, namespace=namespace)
```

This is the same instinct as good HTTP cache design: cache keys must include everything that changes the answer. For anything personalized, either partition by user or don't semantically cache it at all. Static, factual, non-personalized queries — product docs, how-tos, definitions — are the ideal candidates.

## Invalidation, the hard part

Caches are only as good as their eviction. LLM answers grounded in a knowledge base go stale the moment that base changes. Strategies I've used, roughly in order of effort:

- **TTL** — expire entries after N hours. Crude but works when your underlying data changes on a known cadence.
- **Version tag** — stamp every cache entry with the version of the knowledge base or prompt template that produced it; bump the version to invalidate everything at once. This is essential, because when you change your system prompt every cached answer is now potentially wrong.
- **Event-driven purge** — when a specific document updates, purge cache entries that were grounded in it. This requires tracking provenance (which chunks fed which answer) but gives the tightest correctness.

Whatever you pick, treat a prompt-template change as a full cache flush. I once spent an afternoon debugging "why is the assistant ignoring the new tone guidelines" — the answer was that 60% of responses were cached from before the change.

## What it actually buys you

On a support assistant with heavily repeated questions, a semantic cache hit rate of 30-40% is realistic, and each hit removes a full generation call. The effect compounds: lower p50 latency (cached responses return in tens of milliseconds), lower cost, and less load on your rate-limited LLM provider during traffic spikes. It stacks cleanly with the other levers in [cutting LLM costs](https://blog.michaelsam94.com/cutting-llm-costs-caching-routing-batching/) — routing and batching handle the misses, semantic caching handles the hits.

The infrastructure is modest: any [vector database in production](https://blog.michaelsam94.com/vector-databases-in-production/) can back it, and your choice of [embeddings model](https://blog.michaelsam94.com/choosing-an-embeddings-model/) mostly affects lookup latency and match quality. Use a small, fast embeddings model here — you're comparing short prompts, and shaving embedding latency matters because it's now on your critical path for every request.

## Failure modes to watch

- **The confident wrong hit.** Always log cache hits and sample them. A rising false-hit rate is invisible until a user complains; instrument it.
- **Embedding the wrong thing.** If your prompts include large injected context (retrieved chunks, chat history), embedding the whole thing dilutes the signal. Embed the *user's actual question*, not the fully-assembled prompt.
- **Cache poisoning.** If you store LLM responses that were themselves wrong or unsafe, you'll serve them fast forever. Only cache responses that passed your [guardrails](https://blog.michaelsam94.com/guardrails-moderation-llm-apps/).

## The short version

Semantic caching is worth building the moment you have repeated, non-personalized queries and care about latency or cost. Start conservative on the threshold, scope keys to everything that changes the answer, treat prompt changes as flushes, and instrument hits so a bad match surfaces before your users find it. Done carefully it's nearly free performance; done carelessly it's a machine for serving wrong answers quickly.

## Operational notes for semantic caching llm apis

Log cache hit rate, false-positive reports, and similarity score distribution. When users flag wrong cached answers, capture prompt pair for threshold tuning. Invalidate cache entries when system prompt or retrieval corpus version changes — scope keys must include those versions or stale policy answers slip through.

## Notes on semantic caching llm apis

Log cache hit rate, false-positive reports, and similarity score distribution. When users flag wrong cached answers, capture prompt pair for threshold tuning. Invalidate cache entries when system prompt or retrieval corpus version changes — scope keys must include those versions or stale policy answers slip through.

## Resources

- [OpenAI embeddings guide](https://platform.openai.com/docs/guides/embeddings)
- [Redis vector search documentation](https://redis.io/docs/latest/develop/interact/search-and-query/advanced-concepts/vectors/)
- [Pinecone: what is a vector database](https://www.pinecone.io/learn/vector-database/)
- [pgvector — vector similarity for Postgres](https://github.com/pgvector/pgvector)
- [MTEB: Massive Text Embedding Benchmark](https://huggingface.co/spaces/mteb/leaderboard)

Review semantic caching llm apis metrics after the next release train on mid-tier mobile devices — regressions that pass lab Lighthouse often fail CrUX field data.

## Cache key scoping

Scope semantic cache by model version, system prompt hash, and tenant ID. A cache hit across tenants or prompt versions returns wrong answers confidently — worse than a cache miss.

Document owner, rollback path, and the metric you expect to move after the next deploy.
