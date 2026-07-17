---
title: "RAG: Cache Stampede Prevention"
slug: "rag-cache-stampede-prevention"
description: "When a hot embedding or retrieval cache key expires, hundreds of RAG queries can hammer the vector DB and embedding API at once—singleflight, probabilistic early expiration, and stale-while-revalidate keep p95 flat."
datePublished: "2026-05-04"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Cache"]
keywords: "cache stampede, thundering herd, RAG cache, singleflight, stale-while-revalidate, embedding cache, vector search, Redis lock, probabilistic early expiration"
faq:
  - q: "What triggers a cache stampede in a RAG pipeline?"
    a: "A stampede happens when many concurrent queries miss the same cache key at once—usually after TTL expiry on a popular document chunk, a corpus republication that invalidates a broad key prefix, or a deploy that flushes the embedding cache. Each miss fans out to embedding computation, vector search, and reranking. Without coordination, N concurrent misses become N identical expensive calls."
  - q: "Is singleflight enough for multi-pod RAG deployments?"
    a: "Singleflight coalesces in-flight misses within one process, but Kubernetes with dozens of replicas still produces parallel loads unless you add a distributed lock or lease around the recompute path. Pair in-process singleflight with Redis-based locking and stale-while-revalidate so callers get slightly old retrieval results while one worker refreshes."
  - q: "How do I detect stampede conditions before users notice?"
    a: "Alert on miss-rate spikes correlated with single-key QPS, embedding API duplicate-call ratio, and vector DB connection pool saturation. A healthy RAG cache shows smooth miss curves; a stampede shows a vertical wall of misses on one key followed by retrieval latency p95 blowing past SLO."
---
The incident started quietly: embedding latency p95 crossed six seconds while error rates stayed flat. Traffic was normal. The root cause was a single Redis key holding cached embeddings for a rewritten FAQ page that every tenant's default RAG index referenced. At 09:00:00 the key expired. Eighty pods each saw a miss. Eighty identical embedding batches hit the GPU cluster in the same 150 ms window. The vector database connection pool saturated next. Nothing was wrong with the model server—the architecture had simply allowed a thundering herd through a shared hot key.

Cache stampede prevention is load-bearing infrastructure for RAG because retrieval pipelines cache at every layer: query embeddings, chunk embeddings, hybrid search results, reranker scores, and assembled context bundles. A miss is never cheap. This post covers the patterns that keep one expiry event from becoming a regional incident.

## Why RAG caches stampede harder than generic web caches

Traditional HTTP caches serve mostly static content where a miss costs tens of milliseconds to origin. RAG caches amplify herd behavior in three ways that matter for production design.

**Shared hot keys across tenants.** A popular knowledge base article, a default chunking template, or a shared embedding model route creates keys hit by every query session. One expiry affects all tenants at once unless you partition keys by tenant, corpus version, or add per-key entropy to TTL schedules.

**Expensive miss paths.** A web cache miss might cost 50 ms. A RAG miss might chain query embedding (80 ms), hybrid retrieval (120 ms), cross-encoder rerank (200 ms), and context assembly (40 ms). The amplification factor is 10–50× per concurrent miss, and GPU-backed embedding endpoints have hard concurrency ceilings.

**Aggressive invalidation from corpus updates.** RAG teams invalidate caches when documents change because stale chunks poison answers. Blunt prefix invalidation—`DEL embedding:v2:kb-*` after a bulk reindex—turns a content update into an availability cliff. The design goal is not zero misses; it is bounded concurrent recomputes per key and graceful degradation when the slow path is saturated.

## Singleflight: coalesce in-flight misses

Singleflight ensures that when ten concurrent requests miss the same cache key, only one executes the loader; the other nine await its result.

```typescript
// cache/singleflight.ts
type Loader<T> = () => Promise<T>;

export class SingleflightGroup<T> {
  private inFlight = new Map<string, Promise<T>>();

  async do(key: string, loader: Loader<T>): Promise<T> {
    const existing = this.inFlight.get(key);
    if (existing) return existing;

    const promise = loader().finally(() => this.inFlight.delete(key));
    this.inFlight.set(key, promise);
    return promise;
  }
}

const sf = new SingleflightGroup<number[]>();

export async function getQueryEmbedding(
  redis: RedisClient,
  queryHash: string,
  compute: () => Promise<number[]>,
): Promise<number[]> {
  const cacheKey = `embedding:v3:${queryHash}`;

  const cached = await redis.getBuffer(cacheKey);
  if (cached) return deserialize(cached);

  return sf.do(cacheKey, async () => {
    const again = await redis.getBuffer(cacheKey);
    if (again) return deserialize(again);

    const vector = await compute();
    await redis.set(cacheKey, serialize(vector), { EX: 3600 });
    return vector;
  });
}
```

Singleflight works within one process. In Kubernetes with 50 replicas, you still get 50 parallel loads unless you add a distributed coordination layer on top.

## Distributed locks and lease-based refresh

For multi-pod RAG deployments, wrap the recompute path in a short-lived lock. Only the lock holder refreshes; others serve stale data or wait briefly.

```python
# cache/distributed_refresh.py
import asyncio
import json
import time
import uuid
from redis.asyncio import Redis

LOCK_TTL_SEC = 30
STALE_GRACE_SEC = 300

async def get_retrieval_bundle(
    redis: Redis,
    cache_key: str,
    loader,
) -> dict:
    raw = await redis.get(cache_key)
    if raw:
        entry = json.loads(raw)
        age = time.time() - entry["stored_at"]
        if age < entry["ttl"]:
            return entry["payload"]
        if age < STALE_GRACE_SEC:
            asyncio.create_task(_refresh_if_lock(redis, cache_key, loader))
            return entry["payload"]

    return await _refresh_if_lock(redis, cache_key, loader)

async def _refresh_if_lock(redis: Redis, cache_key: str, loader) -> dict:
    lock_key = f"lock:{cache_key}"
    token = str(uuid.uuid4())
    acquired = await redis.set(lock_key, token, nx=True, ex=LOCK_TTL_SEC)
    if not acquired:
        await asyncio.sleep(0.05)
        raw = await redis.get(cache_key)
        if raw:
            return json.loads(raw)["payload"]
        raise TimeoutError("refresh lock contention")

    try:
        payload = await loader()
        await redis.set(
            cache_key,
            json.dumps({"payload": payload, "stored_at": time.time(), "ttl": 3600}),
            ex=3600 + STALE_GRACE_SEC,
        )
        return payload
    finally:
        current = await redis.get(lock_key)
        if current == token:
            await redis.delete(lock_key)
```

The stale grace window is the critical product decision. For public documentation with version metadata in chunk headers, serving five-minute-old retrieval is acceptable. For real-time policy documents without version checks, stale-while-revalidate is the wrong trade.

## Probabilistic early expiration

Fixed TTL on hot keys guarantees synchronized expiry. Probabilistic early expiration (PER) spreads refresh load: on each cache read, there is a small probability of triggering background refresh before hard expiry.

```python
import random
import math

def should_refresh_early(age_sec: float, ttl_sec: float, beta: float = 1.0) -> bool:
    """Returns True with increasing probability as expiry approaches."""
    if age_sec >= ttl_sec:
        return True
    remaining = ttl_sec - age_sec
    # Higher beta = more aggressive early refresh spread
    prob = beta * math.log(max(remaining, 1)) / math.log(ttl_sec)
    return random.random() < prob
```

Combine PER with jitter: never set identical TTL for hot keys across replicas. Add per-key jitter of ±10–20% so expiry times spread across a window even without PER.

## Key design and invalidation hygiene

Cache key structure determines blast radius. Bad patterns create stampedes; good patterns contain them.

**Version in the key, not in invalidation scripts.** Use `chunk:{corpus_version}:{doc_id}:{chunk_idx}` so corpus republication naturally misses old keys without mass deletion. Avoid prefix deletes that force every pod to recompute simultaneously.

**Separate query cache from document cache.** Query embedding keys (`qe:{hash}`) and document chunk keys (`dc:{doc_id}:{chunk}`) have different heat profiles. Invalidating document keys should not cascade into query keys unless the embedding model version changed.

**Soft invalidation with tombstones.** Instead of deleting keys, write a tombstone value that triggers refresh on next read but allows stale serve during lock contention. Hard deletes during peak traffic are an ops anti-pattern.

**Namespace deploys from cache flushes.** CI pipelines that `FLUSHDB` on Redis after deploy are a common stampede trigger. Use key versioning (`v4:` prefix bump) and let old keys expire naturally.

## Layer-specific guidance for RAG stacks

Different cache layers need different stampede strategies.

**Query embedding cache.** Highest QPS, moderate cost per miss. Singleflight plus PER works well. TTL 1–4 hours with jitter.

**Document chunk embedding cache.** Lower QPS per key but very large keyspace. Distributed locks essential on bulk reindex. Consider write-through on ingestion rather than lazy load on query.

**Hybrid retrieval result cache.** Key by `(query_hash, corpus_version, filter_set)`. Stale-while-revalidate is usually safe for internal docs. TTL 15–60 minutes.

**Reranker score cache.** Expensive cross-encoder calls. Long TTL (hours) with corpus version in key. Stampede here often follows deploys that bump reranker model version—coordinate model rollouts with cache version bumps.

**Assembled context bundle cache.** Full pipeline output. Short TTL (5–15 min) because upstream layers may refresh independently. Most stampede-prone layer during corpus updates—use soft invalidation.

## Observability and runbooks

Metrics that matter for RAG cache stampedes:

- **Miss rate derivative** — alert on d(miss_rate)/dt, not absolute miss rate. A slow climb is normal; a cliff is a stampede.
- **Single-key QPS during miss spike** — identifies the hot key causing the herd.
- **Lock wait time p95** — distributed lock contention signal.
- **Downstream duplicate-call ratio** — embedding API requests divided by unique query hashes; values above 1.5 during steady state indicate failed coalescing.
- **Vector DB connection pool utilization** — secondary effect of stampede, often the paging trigger.

Runbook steps when a stampede is detected:

1. Identify hot key from Redis `MONITOR` or key-level metrics.
2. Extend TTL manually on the hot key to stop the bleeding (`EXPIRE key 3600`).
3. Enable stale serve if not already configured.
4. Scale embedding endpoint replicas if lock coalescing is working but throughput is insufficient.
5. Post-incident: add PER, fix invalidation script, or partition key by tenant.

## Testing stampedes before production

Unit tests for singleflight and lock logic are necessary but insufficient. Load tests must reproduce synchronized expiry.

**Chaos expiry test.** Pre-warm a hot key with production-shaped traffic, then `DEL` the key while maintaining QPS. Measure p95 latency and downstream call count. Success: downstream calls ≈ 1–3, not N.

**Bulk invalidation drill.** Simulate corpus republication prefix delete and verify stale-while-revalidate keeps p95 under SLO.

**Deploy cache version bump.** CI integration test that bumps key version prefix and confirms gradual miss curve, not vertical wall.

Stampedes are architecture bugs, not traffic spikes. The fix is always coordination—singleflight, locks, PER, jitter, and stale serve—applied at the layer where expensive work happens.

## Resources

- Redis distributed lock patterns (Redlock alternatives for short TTL leases)
- Go `singleflight` package and language equivalents
- Facebook memcached paper on stale-while-revalidate
- Probabilistic early expiration (PER) literature from Vattani et al.
