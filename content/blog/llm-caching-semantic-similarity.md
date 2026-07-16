---
title: "Semantic Caching for LLM APIs"
slug: "llm-caching-semantic-similarity"
description: "Cache LLM responses by meaning, not exact text: embedding similarity thresholds, false-positive controls, TTL for paraphrased queries, and when semantic cache beats exact match."
datePublished: "2024-10-28"
dateModified: "2024-10-28"
tags: ["AI", "LLM", "Machine Learning", "Architecture"]
keywords: "semantic caching LLM, embedding cache similarity, LLM API cache, paraphrase cache, vector cache LLM"
faq:
  - q: "How similar is similar enough for a cache hit?"
    a: "Start at cosine similarity 0.92–0.95 for FAQ-style queries and calibrate on labeled pairs. Lower thresholds increase hit rate but raise false-positive risk — 'cancel subscription' and 'cancel my account' might score 0.93 but need different handlers. Use higher thresholds for action intents, lower for informational ones."
  - q: "Semantic cache vs exact cache — do I need both?"
    a: "Yes, in layers. Check exact hash first (free, zero false positives), then semantic lookup (embedding search against cached query vectors). Exact hits are ~40% of semantic hits in support bots — don't skip the cheap layer."
  - q: "How do I prevent stale answers in semantic cache?"
    a: "TTL by content type, store cache entry metadata (source doc versions, prompt version), and re-validate high-stakes answers even on cache hit. For RAG-backed responses, include chunk IDs in cache metadata and invalidate when any source chunk updates."
---

"What's your return policy?", "How do returns work?", and "Can I send something back?" are three cache keys in an exact-match system and one answer in a semantic cache. That's the promise — and the risk. Semantic caching returns cached responses for paraphrased inputs by comparing embeddings instead of strings. Get the threshold wrong and you return the refund policy when someone asked about returns on a digital product.

## How semantic cache works

```
Query → embed → search cache index (similar queries)
                      ↓
              similarity ≥ threshold?
                 /        \
              yes          no
               ↓            ↓
        return cached    call LLM → store (query_embed, response)
```

Each cache entry stores:

```python
@dataclass
class SemanticCacheEntry:
    query_text: str
    query_embedding: list[float]
    response: str
    tenant_id: str
    metadata: dict  # prompt_version, source_chunks, created_at
    ttl_expires: datetime
```

## Implementation

```python
async def semantic_lookup(
    query: str,
    tenant_id: str,
    threshold: float = 0.93,
) -> str | None:
    embedding = await embed(query)
    hits = await vector_index.search(
        embedding,
        filter={"tenant_id": tenant_id},
        top_k=1,
    )
    if not hits or hits[0].score < threshold:
        return None
    entry = await store.get(hits[0].id)
    if entry.ttl_expires < now():
        return None
    return entry.response
```

Use the same embedding model for cache lookup and retrieval — mixing models breaks similarity scores.

## Two-tier cache

```python
async def get_response(query: str, tenant_id: str) -> str:
    # Tier 1: exact match (Redis)
    exact_key = hash(tenant_id, normalize(query))
    if hit := await redis.get(exact_key):
        return hit

    # Tier 2: semantic (vector index)
    if hit := await semantic_lookup(query, tenant_id):
        metrics.semantic_hit()
        return hit

    # Miss: full LLM call
    response = await llm.complete(query, tenant_id=tenant_id)
    await store_both(exact_key, query, response, tenant_id)
    return response
```

Exact tier catches identical repeats (CI tests, bots). Semantic tier catches human paraphrasing.

## Threshold calibration

Don't guess 0.95. Build a calibration set:

1. Collect 200 query pairs labeled "same intent" / "different intent"
2. Compute embedding similarity for each pair
3. Plot ROC curve — pick threshold at acceptable false-positive rate

| Intent type | Recommended starting threshold |
|-------------|-------------------------------|
| FAQ / informational | 0.90–0.93 |
| Transactional / action | 0.95–0.98 |
| Multi-turn context-dependent | Don't semantic cache |

For action intents, consider semantic cache lookup only to suggest "Did you mean X?" rather than auto-returning.

## False positive controls

Additional guards beyond similarity:

- **Intent tag matching** — cache entry tagged `billing`; query classified as `billing` only
- **Entity overlap** — "refund for order 123" vs "refund for order 456" share structure but different entities; extract entities and require match
- **Time sensitivity check** — if cached entry is older than 1 hour and query contains temporal words ("today", "now"), bypass cache

```python
def safe_to_serve(cached: SemanticCacheEntry, query: str) -> bool:
    if cached.metadata.get("intent") != classify_intent(query):
        return False
    if has_entity_mismatch(cached.query_text, query):
        return False
    return True
```

## Storage and eviction

Semantic caches grow unbounded without eviction:

- **LRU** with max entries per tenant
- **TTL** by category (FAQ: 24h, product info: 4h)
- **Size cap** on response text stored

Use a dedicated vector index (not your RAG index) for cache entries — mixing pollutes retrieval and complicates TTL.

## Measuring value

Track:

- Semantic hit rate vs exact hit rate
- False positive rate (from user thumbs-down after cache hit — tag these)
- Latency saved (cache hit p50 vs LLM p50)
- Cost saved per day

If false positive rate exceeds 1%, raise threshold or restrict to informational intents.

## When semantic cache isn't worth it

- Low query volume (< 1000/day) — exact cache is enough
- Highly personalized responses — every answer is unique
- Rapidly changing content — invalidation complexity exceeds savings
- Regulated domains where wrong cached answers have legal exposure

## Multi-tenant cache isolation

Semantic caches are a cross-tenant leak vector if keys ignore tenant boundaries. Always embed `tenant_id`, `model_version`, and `prompt_template_version` in the cache lookup key and in the vector metadata filter:

```python
def lookup_cache(tenant_id: str, query: str, embedding: list[float]) -> CacheHit | None:
    return vector_index.search(
        embedding,
        filter={"tenant_id": tenant_id, "model": MODEL_VERSION},
        threshold=0.92,
    )
```

A support bot for Tenant A must never return an answer cached from Tenant B's similar question — even if embeddings are nearly identical. Enterprise contracts treat this as a data breach, not a cache miss.

## Invalidation strategies

Semantic caches need explicit invalidation, not just TTL:

| Trigger | Action |
|---------|--------|
| Knowledge base update | Invalidate by `source_doc_id` tag |
| Model upgrade | Bump `model_version` — old entries ignored |
| Policy change | Purge by intent tag (`billing`, `legal`) |
| User correction | Delete entry + log for threshold tuning |

Batch invalidation beats scanning the full index. Tag every cache entry with the document IDs or product SKUs that informed the answer so a CMS publish event can purge affected rows in O(tags) rather than re-embedding everything.

## Production rollout checklist

- [ ] Exact cache layer in front of semantic cache (cheaper, zero false positives)
- [ ] Similarity threshold tuned on held-out query pairs with human labels
- [ ] False positive dashboard: thumbs-down tagged with `cache_hit=true`
- [ ] Per-tenant hit rate and cost savings visible in billing dashboard
- [ ] Bypass cache for authenticated actions (refunds, account changes)
- [ ] Load test: cache at 10× expected QPS without vector index latency regression

Start with informational intents only. Expand to transactional intents only after false positive rate stays below 0.5% for two weeks.

## Quick reference

| Pattern | When to use |
|---------|-------------|
| Exact cache only | < 1K queries/day, zero false-positive tolerance |
| Semantic + exact | Support bots, FAQ-heavy products |
| Semantic with entity guard | Order status, account queries |
| No cache | Personalized generation, regulated advice |

Review cache hit rate weekly alongside support ticket volume — a rising ticket rate with rising hit rate signals false positives, not success.

## Resources

- [GPTCache semantic cache module](https://gptcache.readthedocs.io/en/latest/)
- [Redis vector search for caching](https://redis.io/docs/latest/develop/interact/search-and-query/query/vector-search/)
- [Zilliz semantic cache patterns](https://zilliz.com/blog/semantic-cache-for-llms)
- [LangChain semantic cache integration](https://python.langchain.com/docs/how_to/llm_caching/)
- [Embeddings similarity benchmarks (MTEB)](https://huggingface.co/spaces/mteb/leaderboard)
