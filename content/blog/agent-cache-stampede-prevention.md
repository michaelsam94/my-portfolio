---
title: "AI Agents: Cache Stampede Prevention"
slug: "agent-cache-stampede-prevention"
description: "When a hot cache key expires, hundreds of agent sessions can hammer the same embedding query or LLM call at once—singleflight, probabilistic early expiration, and stale-while-revalidate keep p95 flat."
datePublished: "2026-05-04"
dateModified: "2026-05-04"
tags: ["AI", "Agent", "Cache"]
keywords: "cache stampede, thundering herd, singleflight, stale-while-revalidate, probabilistic early expiration, agent cache, LLM cache, Redis lock, embedding cache"
faq:
  - q: "What triggers a cache stampede in an agent pipeline?"
    a: "A stampede happens when many concurrent requests miss the same cache key at once—usually after TTL expiry, a deploy that clears the cache, or a viral prompt that every session retrieves. Each miss fans out to the slow path: vector search, embedding API, or LLM completion. Without coordination, N concurrent misses become N identical expensive calls."
  - q: "Is singleflight enough for agent workloads?"
    a: "Singleflight (request coalescing) is necessary but not sufficient. It deduplicates in-flight misses for one process, but multi-pod deployments need a distributed lock or lease around the recompute path. Pair singleflight with stale-while-revalidate so callers get slightly old data while one worker refreshes."
  - q: "Should agent response caches use fixed TTL or jitter?"
    a: "Never use identical TTL for hot keys across replicas. Add per-key jitter (±10–20%) so expiry times spread across a window. For retrieval caches keyed by query hash, consider probabilistic early expiration: each read has a small chance of triggering background refresh before hard expiry."
  - q: "How do I detect stampede conditions before users notice?"
    a: "Alert on miss-rate spikes correlated with single-key QPS, lock wait time p95, and downstream duplicate-call ratio. A healthy cache shows smooth miss curves; a stampede shows a vertical wall of misses on one key followed by LLM latency p95 blowing past SLO."
---
The pager fired at 09:01—not because error rates climbed, but because embedding latency p95 crossed 8 seconds. Traffic was normal. The culprit was a single cache key: a rewritten system prompt hash shared by every tenant using the default agent template. At 09:00:00 the Redis key expired. Four hundred pods each saw a miss. Four hundred identical embedding batches hit the GPU cluster in the same 200 ms window. Nothing was "wrong" with the model server; the architecture had simply allowed a thundering herd.

Cache stampede prevention is load-bearing infrastructure for agent systems because agent pipelines cache at every layer—prompt templates, retrieval results, tool outputs, and final completions. A miss is never cheap. This post covers the patterns that keep one expiry event from becoming a regional incident.

## Why agent caches stampede harder than web caches

Traditional HTTP caches serve mostly static or slowly changing content. Agent caches are different in three ways that amplify herd behavior.

**Shared hot keys.** A popular prompt template, a default RAG chunk set, or a feature-flag-gated model route creates keys hit by every session. One expiry affects all tenants at once unless you partition keys by tenant or add entropy.

**Expensive miss paths.** A web cache miss might cost 50 ms to origin. An agent miss might chain embedding (200 ms), vector search (100 ms), rerank (150 ms), and LLM first-token (800 ms). The amplification factor is 10–50× per concurrent miss.

**TTL-driven invalidation.** Deploys that flush cache namespaces, schema migrations that bump key versions, and "helpful" ops scripts that `FLUSHDB` on Redis turn predictable expiry into unpredictable stampedes. Agent teams invalidate aggressively because stale retrieval poisons answers—but blunt invalidation trades correctness for availability cliffs.

The design goal is not zero misses. It is **bounded concurrent recomputes** per key and **graceful degradation** when the slow path is saturated.

## Singleflight: coalesce in-flight misses

Singleflight ensures that when ten goroutines (or Node promises) miss the same key simultaneously, only one executes the loader; the other nine await its result.

```typescript
// cache/singleflight.ts
import { createHash } from "crypto";

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

const sf = new SingleflightGroup<string>();

export async function getCachedCompletion(
  redis: RedisClient,
  promptHash: string,
  compute: () => Promise<string>,
): Promise<string> {
  const cacheKey = `completion:v3:${promptHash}`;

  const cached = await redis.get(cacheKey);
  if (cached) return cached;

  return sf.do(cacheKey, async () => {
    // Double-check after acquiring coalescing slot
    const again = await redis.get(cacheKey);
    if (again) return again;

    const result = await compute();
    await redis.set(cacheKey, result, { EX: 3600 });
    return result;
  });
}
```

Singleflight works within one process. In Kubernetes with 50 replicas, you still get 50 parallel loads unless you add a distributed layer.

## Distributed locks and lease-based refresh

For multi-pod deployments, wrap the recompute path in a short-lived lock. Only the lock holder refreshes; others serve stale data or wait briefly.

```python
# cache/distributed_refresh.py
import asyncio
import json
import time
import uuid
from redis.asyncio import Redis

LOCK_TTL_SEC = 30
STALE_GRACE_SEC = 300  # serve stale up to 5 min during refresh

async def get_with_lock(
    redis: Redis,
    key: str,
    loader,
    ttl_sec: int = 3600,
) -> dict:
    raw = await redis.get(key)
    if raw:
        envelope = json.loads(raw)
        age = time.time() - envelope["stored_at"]
        if age < ttl_sec:
            return envelope["value"]
        if age < ttl_sec + STALE_GRACE_SEC:
            # Stale-while-revalidate: return old, refresh in background
            asyncio.create_task(_refresh_if_leader(redis, key, loader, ttl_sec))
            return envelope["value"]

    return await _refresh_if_leader(redis, key, loader, ttl_sec)


async def _refresh_if_leader(redis, key, loader, ttl_sec):
    lock_key = f"lock:{key}"
    token = str(uuid.uuid4())
    acquired = await redis.set(lock_key, token, nx=True, ex=LOCK_TTL_SEC)
    if not acquired:
        # Another pod is refreshing; wait and read
        for _ in range(20):
            await asyncio.sleep(0.1)
            raw = await redis.get(key)
            if raw:
                return json.loads(raw)["value"]
        return await loader()  # last resort

    try:
        value = await loader()
        envelope = {"value": value, "stored_at": time.time()}
        await redis.set(key, json.dumps(envelope), ex=ttl_sec + STALE_GRACE_SEC)
        return value
    finally:
        # Release lock only if we still hold it
        current = await redis.get(lock_key)
        if current == token:
            await redis.delete(lock_key)
```

Key details: lock TTL must exceed p99 loader latency but stay short enough that a crashed holder does not block refresh for hours. Always use stale-while-revalidate so lock waiters are not blocked on the slow path.

## Probabilistic early expiration (PER)

Fixed TTL creates synchronized expiry. Probabilistic early expiration spreads refresh across time: on each read, compute a small probability that this read triggers background refresh even though the key is still valid.

```typescript
function shouldEarlyRefresh(storedAt: number, ttlSec: number, beta = 1.0): boolean {
  const age = (Date.now() - storedAt) / 1000;
  const remaining = ttlSec - age;
  if (remaining <= 0) return true;
  // Higher age → higher refresh probability; beta tunes aggressiveness
  const probability = Math.exp(-remaining / (beta * ttlSec));
  return Math.random() < probability;
}
```

PER shines for retrieval caches where keys are read thousands of times per minute but recomputed only once per hour. The first reads after the "soft expiry window" gradually refresh the key so hard expiry rarely coincides with peak traffic.

## Jitter, key design, and invalidation hygiene

**TTL jitter.** When setting expiry, use `TTL + random(-0.15, +0.15) * TTL` so keys created in the same deploy wave do not expire together.

**Key granularity.** Cache at the narrowest stable unit. Caching entire agent sessions is fragile; caching `(tenant_id, query_embedding_hash, index_version)` survives prompt changes without invalidating everything.

**Soft invalidation.** Bump a version suffix in the key (`v14`) instead of deleting keys. Old keys expire naturally; new reads miss to the new namespace without a thundering herd on delete.

**Never flush production Redis during business hours.** If you must invalidate, write the new version prefix and let TTL drain the old namespace over hours.

## Layer-specific guidance for agent stacks

| Cache layer | Stampede risk | Recommended pattern |
|-------------|---------------|---------------------|
| Prompt / system template | Very high (shared key) | PER + distributed lock + versioned keys |
| Embedding vectors | High (batch API limits) | Singleflight + request batching |
| Retrieval results | Medium (query diversity) | SWR with 60s grace, tenant-scoped keys |
| LLM completion | Low–medium | Cache only deterministic paths; skip streaming |
| Tool call results | Medium (idempotency) | Short TTL (30s) + coalescing |

Streaming completions generally should not be cached at the response level—users expect fresh tokens. Cache the retrieval context that feeds the stream instead.

## Observability and runbooks

Dashboards should answer: "Are we stampeding right now?"

- `cache_miss_total` by key prefix (top 10 keys)
- `cache_lock_wait_seconds` histogram
- `loader_in_flight` gauge per key prefix
- Ratio of downstream calls to cache hits for embedding and LLM endpoints

Runbook steps when miss rate spikes on a single key:

1. Confirm whether a deploy or invalidation event preceded the spike.
2. Temporarily extend TTL or enable stale-while-revalidate for the affected prefix.
3. If lock contention is high, increase lock wait timeout or serve stale unconditionally for that key class.
4. Post-incident: add PER or key versioning so the next expiry spreads load.

## Testing stampedes before production

Unit tests prove singleflight coalescing. Integration tests need concurrent load:

```bash
# 100 concurrent requests, key expired 1 second ago
hey -n 100 -c 100 -m POST \
  -H "Content-Type: application/json" \
  -d '{"prompt_hash":"hot-key-abc"}' \
  https://staging.agent.example/v1/completion
```

Assert downstream embedding QPS stays near 1 (or pod count if no distributed lock yet), not 100. Chaos tests: expire a hot key during synthetic peak and verify p95 latency stays within SLO.

## Closing

Cache stampede prevention is not a Redis configuration tweak—it is a concurrency design problem at the boundary between fast memory and slow AI inference. Singleflight stops herds within a process; distributed locks and stale-while-revalidate stop them across a fleet; probabilistic early expiration stops synchronized expiry from forming herds in the first place. Agent teams that nail this pattern ship prompt changes and cache invalidations without fearing the top of the hour.

## Resources

- [Facebook's Scaling Memcache at Facebook (PER origins)](https://www.usenix.org/conference/nsdi13/technical-sessions/presentation/nishtala)
- [Go singleflight package documentation](https://pkg.go.dev/golang.org/x/sync/singleflight)
- [Redis SET NX distributed locking patterns](https://redis.io/docs/manual/patterns/distributed-locks/)
- [RFC 5861: HTTP Stale-While-Revalidate](https://datatracker.ietf.org/doc/html/rfc5861)
- [AWS ElastiCache best practices for TTL and eviction](https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/BestPractices.html)
