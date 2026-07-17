---
title: "AI Agents: Probabilistic Early Expiration"
slug: "agent-probabilistic-early-expiration"
description: "Prevent cache stampedes on LLM response caches with probabilistic early expiration — the math, Redis implementation, and tuning for embedding and completion caches at scale."
datePublished: "2026-05-07"
dateModified: "2026-05-07"
tags: ["AI", "Agent", "Probabilistic"]
keywords: "probabilistic early expiration, cache stampede, LLM cache, xfetch, Redis TTL, thundering herd, semantic cache invalidation"
faq:
  - q: "What problem does probabilistic early expiration solve?"
    a: "When a popular cache key expires, every concurrent request misses at once and hammers the origin — classic cache stampede. Probabilistic early expiration refreshes keys before hard expiry with probability that rises as TTL runs out, spreading recomputation over time so one unlucky millisecond does not collapse your LLM backend."
  - q: "How is this different from locking or request coalescing?"
    a: "Single-flight locks dedupe within one process cluster but add complexity and failure modes if the lock holder dies. Probabilistic early expiration needs no coordination — each client independently rolls dice. Combine both for highest-traffic keys: prob.expiration spreads load; coalescing caps parallel origin calls."
  - q: "Does probabilistic early expiration work with semantic caches?"
    a: "Yes, applied per embedding bucket or per exact cache key. For vector similarity caches, run prob.expiration on the canonical key for a cluster of paraphrases, or on each exact key independently. Tune beta separately — semantic recomputation is more expensive than byte-identical lookup."
  - q: "What beta value should I start with for LLM completion caches?"
    a: "Start with beta = 1.0 (standard XFetch paper default) and TTL of 300–900 seconds for stable prompts. Increase beta toward 2.0 if you still see latency spikes at expiry; decrease toward 0.5 if origin load from early refresh is too high. Measure p99 origin QPS vs. cache age."
---
Latency tripled at the top of every hour because ten thousand sessions shared one cached system prompt response that expired simultaneously.

Probabilistic early expiration is a small algorithmic change that stops LLM and embedding caches from triggering thundering herds — no distributed lock service required.

## Cache stampedes in agent stacks

Agent products cache aggressively: system prompt prefixes, retrieval results for hot documents, embedding vectors, and full completions for FAQ-style queries. Hit rates of 40–70% on repetitive support flows are common.

Fixed TTL expiry is a synchronized timer bomb. At `T=900s`, the key vanishes. Five hundred in-flight requests miss. Each fires a 4k-token completion. Your GPU queue depth spikes, p99 latency crosses SLA, and circuit breakers start rejecting unrelated traffic.

Classic mitigations:

- **Jitter on TTL** — spreads expiry times at write; helps only at insert, not when one key serves millions of reads.
- **Stale-while-revalidate** — serve stale while one worker refreshes; needs explicit support in cache layer.
- **Probabilistic early expiration (XFetch)** — treat keys as "maybe expired" before hard TTL; recompute early with tunable probability.

For LLM caches where recomputation costs dollars and seconds, prob.expiration is often the best cost-to-complexity ratio.

## The XFetch algorithm in plain language

From Vattani et al. (2015), popularized in production by Facebook's memcached patches:

Each cache read computes whether to treat the item as expired **before** its actual TTL:

```
delta = now - item.created_at
if delta < item.ttl * beta * log(random_uniform(0,1)):
    return cached_value  # still "fresh enough"
else:
    return MISS  # recompute and refresh
```

- `beta` controls aggressiveness. Higher beta → earlier probabilistic expiry → smoother load, more origin calls.
- Randomness per request spreads recomputation across the beta-window before hard expiry.
- Hard TTL still applies as upper bound — keys cannot live forever if beta logic never triggers recompute (use `min(hard_ttl, ...)` semantics).

Intuition: when a key is young, `log(random)` is usually small enough that the inequality holds — cache hit. Near end of life, negative log uniform grows — more requests " opt in" to refresh early.

## Redis implementation for completion cache

Store metadata alongside cached completions:

```python
import math
import random
import time
import json
import redis

r = redis.Redis(host="cache.internal", decode_responses=True)

BETA = 1.0
HARD_TTL_SEC = 600

def cache_get(key: str) -> str | None:
    raw = r.get(key)
    if raw is None:
        return None
    item = json.loads(raw)
    age = time.time() - item["created_at"]
    if age >= HARD_TTL_SEC:
        return None  # hard expiry
    if should_refresh_early(age, HARD_TTL_SEC, BETA):
        return None  # probabilistic miss → caller recomputes
    return item["value"]

def should_refresh_early(age: float, ttl: float, beta: float) -> bool:
    # True means treat as miss and refresh
    u = random.random()
    if u <= 0:
        u = 1e-10
    threshold = ttl * beta * math.log(u)
    return age >= threshold

def cache_set(key: str, value: str) -> None:
    payload = json.dumps({"value": value, "created_at": time.time()})
    r.setex(key, HARD_TTL_SEC + 60, payload)  # Redis TTL slightly above hard TTL
```

Caller pattern with origin fetch:

```python
def get_completion(prompt_hash: str, compute_fn) -> str:
    key = f"llm:completion:{prompt_hash}"
    cached = cache_get(key)
    if cached is not None:
        return cached
    result = compute_fn()
    cache_set(key, result)
    return result
```

Instrument `cache_get` returns: hit, hard_miss, prob_miss. If prob_miss dominates and origin load is high, lower beta.

## Layering with single-flight for hot keys

Probabilistic expiration spreads traffic; it does not guarantee exactly one recomputation. For keys with extreme fan-out (global system prompt), add brief coalescing:

```python
from redis.lock import Lock

def get_completion_coalesced(key: str, compute_fn) -> str:
    cached = cache_get(key)
    if cached is not None:
        return cached
    lock = Lock(r, f"lock:{key}", timeout=30, blocking_timeout=5)
    if lock.acquire(blocking=False):
        try:
            cached = cache_get(key)  # double-check
            if cached is not None:
                return cached
            result = compute_fn()
            cache_set(key, result)
            return result
        finally:
            lock.release()
    else:
        # Another worker refreshes; wait briefly or serve stale if allowed
        time.sleep(0.05)
        cached = cache_get(key)
        return cached if cached else compute_fn()
```

Use coalescing only on a allowlist of known hot keys — global locks on every request reintroduce contention you wanted to avoid.

## Tuning for embedding vs. completion caches

**Embeddings** — deterministic, cheaper than full completion. Slightly lower beta (0.7–1.0) acceptable; hard TTL 24h+ for stable corpora. Invalidate on document update via version suffix in key (`doc:118:v4`), not TTL alone.

**Completions** — expensive, user-visible latency. Beta 1.0–1.5 with HARD_TTL 300–900s for semi-static answers. Shorter TTL for time-sensitive content (pricing, inventory).

**Semantic caches** — key by `(embedding_bucket, policy_version)`. Prob.expiration on bucket canonical key; when refresh triggers, recompute embedding similarity index entry and stored completion together. Log false-hit rate separately — prob.expiration does not fix wrong-answer caching, only load shape.

## Measuring success

Dashboard four series:

1. Origin QPS vs. wall clock — stampede shows as sharp spike at fixed intervals before prob.exp; should flatten after.
2. Ratio `prob_miss / (hit + prob_miss + hard_miss)` — tuning knob feedback.
3. p99 completion latency during former expiry minutes.
4. Cache hit rate — early refresh lowers hit rate slightly; acceptable if origin p99 and cost improve.

Load test: simulate 500 concurrent clients reading one key approaching TTL. Without prob.exp, origin receives 500 simultaneous computes. With beta=1.0, spread over roughly `beta * ttl * (1 - 1/e)` seconds for exponential-style distribution — empirically verify in staging.

## Pitfalls

**Clock skew** across clients affects age calculation if created_at is writer-local; use server time from Redis `TIME` on write.

**Beta too high** on low-traffic keys causes unnecessary origin calls — prob.exp shines on hot keys; cold keys can use plain TTL.

**Ignoring prompt version in cache key** — prob.exp refreshes stale **wrong** answers faster if version not in key. Always include model ID, prompt template hash, and retrieval corpus version in the key namespace.

**Caching errors** — never prob.exp refresh 429/500 responses; cache only 200 with explicit error TTL separate from success path.

## When to skip probabilistic early expiration

Caches with fewer than ~10 concurrent readers per key at expiry — jitter alone may suffice. Client-side caches with no shared Redis — coalescing in-process is enough.

Real-time agent tool results (live stock prices) should not use long TTL caches at all; prob.expiration does not make stale financial data acceptable.

## Closing the loop

Add prob.expiration to your LLM cache layer before the next marketing push drives ten× FAQ traffic. Tune beta from metrics, not folklore. Pair with versioned keys and selective single-flight on globals.

The algorithm fits in forty lines. The production win is not looking clever — it is removing the hourly latency cliff nobody could explain until they plotted cache TTL against origin QPS.

## Extending to CDN and edge caches

The same prob.expiration logic applies at edge workers serving cached agent widget responses. Edge TTLs are shorter; beta often lands lower (0.5–0.8) because recomputation at origin is rarer than at regional Redis. Pass `Cache-Control` with hard max-age while implementing prob.exp in worker code — browsers and CDNs still need an upper bound.

For multi-region Redis, prob.expiration runs independently per region — acceptable when origin can handle scattered refresh. If origin is single-region, coordinate hot-key coalescing globally via a short-lived lock in the primary region only; edge regions serve stale up to `stale_max_sec` while primary refreshes.

Document beta and HARD_TTL per cache namespace in config management. Prompt teams should not need to ask infra which values apply to their new FAQ cache — defaults live in a YAML file reviewed quarterly against origin load charts.

## Resources

- [Optimal Probabilistic Cache Stampede Prevention (Vattani et al., 2015)](https://arxiv.org/abs/1410.1323)
- [Facebook/memcached: Probabilistic early expiration patch notes](https://github.com/memcached/memcached/wiki/ReleaseNotes1524)
- [AWS Database Blog — Preventing cache stampede with DynamoDB DAX and lazy loading](https://aws.amazon.com/blogs/database/building-a-cache-that-protects-against-stampedes/)
- [Redis expiration documentation](https://redis.io/docs/manual/keyspace-notifications/)
- [Semantic caching for LLM APIs — related patterns](/blog/semantic-caching-llm-apis)
