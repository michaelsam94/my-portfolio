---
title: "Caching Prompts and Responses"
slug: "llm-caching-prompt-response"
description: "Exact-match LLM caching: cache key design, TTL strategy, provider prompt caching, invalidation rules, and the hit rates that cut inference bills in half."
datePublished: "2024-10-25"
dateModified: "2024-10-25"
tags: ["AI", "LLM", "Architecture", "Backend"]
keywords: "LLM prompt caching, response cache LLM, exact match cache, OpenAI prompt cache, LLM cost reduction"
faq:
  - q: "What is the difference between prompt caching and response caching?"
    a: "Prompt caching (provider-side) reuses computed KV activations for identical prompt prefixes — you pay reduced rates on cached input tokens. Response caching (your side) stores complete model outputs keyed by the full input hash and skips the API call entirely. Use both: provider caching for shared system prompts, response caching for repeated user queries."
  - q: "How do I build a cache key for LLM requests?"
    a: "Hash the model name, temperature (if non-zero), full message list (roles + content), tool definitions, and response format. Include tenant_id for isolation. Exclude request metadata that doesn't affect output. Normalize whitespace in user input if near-duplicates are common."
  - q: "What TTL should LLM cache entries use?"
    a: "Match your data freshness requirements. FAQ answers: 1–24 hours. User-specific data: don't cache or use minutes. System prompts with provider-side caching: hours to days. Always invalidate on prompt version change, document reindex, or model version bump."
---

The second customer asking "What are your business hours?" shouldn't cost another $0.002 in tokens. Exact-match caching is the lowest-complexity cost optimization in LLM apps — hash the input, return the stored output, skip the API call. Teams that skip it pay double for every FAQ, every repeated eval run, and every integration test in CI.

## Response cache architecture

```python
import hashlib
import json

def cache_key(request: CompletionRequest) -> str:
    payload = {
        "model": request.model,
        "messages": request.messages,
        "temperature": request.temperature,
        "tools": request.tools,
        "response_format": request.response_format,
        "tenant_id": request.tenant_id,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()

async def cached_complete(request: CompletionRequest) -> str:
    key = cache_key(request)
    if cached := await redis.get(f"llm:{key}"):
        metrics.cache_hit(request.feature)
        return cached
    response = await provider.complete(request)
    ttl = ttl_for_feature(request.feature)
    await redis.setex(f"llm:{key}", ttl, response)
    return response
```

Store in Redis for sub-millisecond lookups. For large responses, store in S3 with Redis holding the pointer.

## What to cache (and what not to)

**Good candidates**:

- FAQ and support responses
- Classification labels on stable content
- Structured extraction on documents that don't change
- Embedding vectors (keyed by content hash — never re-embed)

**Bad candidates**:

- Responses including live data (stock prices, inventory)
- Creative generation with temperature > 0 (same input, different output by design)
- Personalized recommendations
- Anything where stale answers create liability

When in doubt, cache with short TTL and stamp entries with `cached_at` so downstream can warn users.

## Provider prompt caching

OpenAI and Anthropic cache identical prompt prefixes automatically:

```
┌─────────────────────────────┐
│ System prompt (10K tokens)  │ ← cached prefix (discounted)
├─────────────────────────────┤
│ RAG context (varies)        │
├─────────────────────────────┤
│ User message                │
└─────────────────────────────┘
```

Structure prompts so static content comes first:

```python
messages = [
    {"role": "system", "content": STATIC_SYSTEM_PROMPT},      # cached
    {"role": "system", "content": f"Context:\n{rag_chunks}"}, # varies
    {"role": "user", "content": user_message},
]
```

A 4K-token system prompt cached at 50% discount on 10K daily requests saves real money. Monitor `cached_tokens` in API responses.

## Invalidation

Cache invalidation events:

| Event | Action |
|-------|--------|
| Prompt version deploy | Flush feature-scoped keys or bump key prefix |
| Document reindex | Flush RAG-dependent keys for affected tenant |
| Model upgrade | Global flush or version in cache key |
| Manual content fix | Targeted delete by content hash |

Use key prefixes for cheap bulk invalidation:

```
llm:v3:support:{hash}   ← bump v3 → v4 on prompt deploy
```

## Hit rate optimization

Low hit rate usually means:

- **Over-specific keys** — including timestamps or request IDs
- **High temperature** — disable caching for creative endpoints
- **No normalization** — "business hours?" vs "Business hours" are different keys

```python
def normalize_user_text(text: str) -> str:
    return text.strip().lower().rstrip("?.!")
```

Only normalize when semantically safe. Don't lowercase proper nouns in technical support.

Target 30–60% hit rate on FAQ-heavy features. Below 10%, caching isn't worth the complexity.

## Observability

Track per feature:

- Hit rate, miss rate, bypass rate (TTL expired)
- Cost saved estimate: `hits × avg_cost_per_request`
- Stale serve count (if serving expired cache under load)
- Cache size and eviction rate

Alert if hit rate drops suddenly — often means a prompt change invalidated keys or a new traffic pattern emerged.

## Security

- Include `tenant_id` in every key
- Don't cache responses containing PII unless encrypted at rest
- Set max response size for cache (prevent memory exhaustion attacks)
- Rate-limit cache lookups to prevent enumeration

## Semantic caching

Exact-match caching misses paraphrased queries. Semantic cache matches by embedding similarity:

```python
async def semantic_cache_lookup(query: str, threshold: float = 0.95) -> str | None:
    query_emb = embed_model.encode(query)
    # Search cache index for similar queries
    results = cache_index.search(query_emb, k=1)
    if results and results[0].score > threshold:
        return cache_store.get(results[0].id)
    return None

async def cached_generate(query: str) -> str:
    cached = await semantic_cache_lookup(query)
    if cached:
        metrics.increment("cache.semantic_hit")
        return cached
    response = await llm.generate(query)
    await cache_store.set(embed_model.encode(query), response)
    return response
```

Semantic cache hit rate 2–3× higher than exact match on FAQ-style queries. Threshold 0.95 prevents serving wrong answers for similar-but-different queries.

## Cache invalidation strategies

| Strategy | Use when | Tradeoff |
|---|---|---|
| TTL expiry | General content | Stale data until TTL |
| Version key in cache key | Prompt/model changes | Manual version bump |
| Event-driven purge | Knowledge base update | Requires event infrastructure |
| LRU eviction | Memory-bounded cache | Oldest entries evicted |

```python
def cache_key(prompt_version: str, tenant_id: str, query: str) -> str:
    normalized = normalize_user_text(query)
    content_hash = hashlib.sha256(normalized.encode()).hexdigest()[:16]
    return f"{tenant_id}:{prompt_version}:{content_hash}"
```

Include prompt version in key — prompt change automatically invalidates old cache entries without manual purge.

## Provider-native prompt caching

OpenAI and Anthropic cache repeated prompt prefixes automatically:

```python
# OpenAI: system prompt cached after first request
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": LONG_SYSTEM_PROMPT},  # cached
        {"role": "user", "content": user_query},             # not cached
    ],
)
# First request: full cost. Subsequent: system prompt at 50% discount.
```

Place static content (system prompt, RAG context, few-shot examples) at the start of the prompt. Provider caches prefix automatically — no application cache needed for the static portion.

## Failure modes

- **PII in cached responses** — compliance violation; encrypt or exclude PII from cache
- **No tenant isolation in cache key** — cross-tenant data leak
- **Semantic threshold too low** — wrong answer served for similar query
- **Prompt change without version bump** — stale responses served from old prompt cache
- **Unbounded cache size** — memory exhaustion; set max size with LRU eviction

## Production checklist

- Tenant ID in every cache key
- Prompt version in cache key for automatic invalidation on change
- Semantic cache threshold ≥0.95 for FAQ-style queries
- PII excluded from cache or encrypted at rest
- Hit rate, cost saved, and eviction rate monitored
- Provider-native prompt caching used for static prefix content

## Resources

- [OpenAI prompt caching guide](https://platform.openai.com/docs/guides/prompt-caching)
- [Anthropic prompt caching documentation](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)
- [GPTCache open-source library](https://github.com/zilliztech/GPTCache)
- [Redis caching best practices](https://redis.io/docs/latest/develop/use/patterns/)
- [Cloudflare AI Gateway caching](https://developers.cloudflare.com/ai-gateway/configuration/caching/)
