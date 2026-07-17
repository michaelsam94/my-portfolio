---
title: "AI Agents: Cache Aside Vs Read Through"
slug: "agent-cache-aside-vs-read-through"
description: "Cache-aside vs read-through patterns for AI agent systems — embedding caches, session context, tool result memoization, stampede prevention, and TTL strategies that balance cost with freshness."
datePublished: "2026-05-09"
dateModified: "2026-05-09"
tags: ["AI", "Agent", "Cache"]
keywords: "cache-aside, read-through, write-through, agent caching, Redis, embedding cache, cache stampede, LLM cost optimization"
faq:
  - q: "When should agent systems use cache-aside instead of read-through?"
    a: "Use cache-aside when application code already orchestrates complex agent logic and you want explicit control over cache keys, invalidation, and failure fallback — typical for RAG retrieval results and tool outputs. Read-through fits when a cache library or ORM should hide database fetches behind a simple get API, common for session metadata and user preference blobs."
  - q: "What agent data is safe to cache and what is not?"
    a: "Safe: embedding vectors for immutable document chunks, idempotent tool read responses, compiled system prompt templates, public knowledge base snippets. Unsafe or short-TTL only: personalized account data, authorization decisions, rate-limit counters, anything whose staleness causes wrong tool writes or cross-tenant leakage."
  - q: "How do you prevent cache stampedes on hot agent prompts?"
    a: "Use per-key locks (Redis SETNX), request coalescing (single-flight), jittered TTLs, and stale-while-revalidate for read-heavy embedding lookups. Never let 500 concurrent agent workers miss the same key simultaneously and hammer your vector DB."
  - q: "Does caching LLM completions violate data retention policies?"
    a: "It can. Cache keys derived from user PII, and storing completions beyond approved retention, triggers GDPR and enterprise DPA issues. Hash or tokenize keys, encrypt cache values at rest, set TTL aligned with data classification, and exclude regulated payloads from shared caches entirely."
---
At 9 a.m. every Monday, three thousand agents asked variations of the same question: "What is our PTO policy?" Each variation triggered a full RAG pipeline — embed query, vector search, rerank, LLM summarize — because the team cached nothing, afraid stale HR policy would create liability. Token spend spiked 4×; p95 latency hit eight seconds. The fix was not "cache everything." It was choosing **cache-aside** for retrieval bundles and **read-through** for session context, with TTL and invalidation rules matched to each data type.

Agent workloads are read-heavy, bursty, and expensive. Wrong caching loses money; wrong freshness loses trust. This deep dive compares cache-aside and read-through in agent architectures, with implementation patterns for embeddings, tool results, and conversation state.

## Pattern comparison

| Aspect | Cache-aside (lazy loading) | Read-through |
|--------|---------------------------|--------------|
| Who loads cache on miss? | Application | Cache layer / library |
| Write path | App writes DB, app invalidates or updates cache | Often write-through or write-behind paired |
| Control | Explicit in agent code | Encapsulated behind cache API |
| Miss behavior | App fetches origin, then populates cache | Cache module fetches origin transparently |
| Best for | RAG results, tool memoization | Session profiles, config blobs |

**Write-through** (sync write to cache and DB) and **write-behind** (async DB write) appear alongside read-through in full-stack caches. Agents mostly care about read patterns because tool **writes** must stay authoritative at the origin.

## Cache-aside for agent retrieval and tools

The application checks cache first; on miss, runs retrieval or tool call, then sets cache:

```typescript
import { createHash } from "crypto";
import Redis from "ioredis";

const redis = new Redis(process.env.REDIS_URL);
const RETRIEVAL_TTL_SEC = 3600;

function retrievalCacheKey(
  tenantId: string,
  corpusVersion: string,
  query: string,
): string {
  const hash = createHash("sha256")
    .update(`${tenantId}:${corpusVersion}:${query.toLowerCase().trim()}`)
    .digest("hex")
    .slice(0, 32);
  return `rag:v1:${tenantId}:${hash}`;
}

export async function getRetrievalBundle(
  tenantId: string,
  corpusVersion: string,
  query: string,
  fetchFromOrigin: () => Promise<RetrievalBundle>,
): Promise<RetrievalBundle> {
  const key = retrievalCacheKey(tenantId, corpusVersion, query);
  const cached = await redis.get(key);
  if (cached) return JSON.parse(cached) as RetrievalBundle;

  const lockKey = `${key}:lock`;
  const acquired = await redis.set(lockKey, "1", "EX", 10, "NX");

  if (!acquired) {
    // another worker populates — brief wait and retry
    await sleep(50);
    const retry = await redis.get(key);
    if (retry) return JSON.parse(retry) as RetrievalBundle;
  }

  try {
    const bundle = await fetchFromOrigin();
    await redis.set(key, JSON.stringify(bundle), "EX", RETRIEVAL_TTL_SEC);
    return bundle;
  } finally {
    if (acquired) await redis.del(lockKey);
  }
}
```

**Include `corpusVersion` in keys** — publishing new documents without bumping version serves stale chunks to agents answering compliance questions.

For **tool memoization**, cache only idempotent reads (`get_order_status`, not `cancel_order`). Key by `(tenant, tool, argsHash, toolVersion)`.

## Read-through for session and profile data

Read-through hides origin fetches behind a cache service interface — useful when many agent microservices need consistent session access:

```python
from dataclasses import dataclass
from typing import Callable, Optional
import json
import redis

@dataclass
class SessionContext:
    user_id: str
    tenant_id: str
    locale: str
    permissions: list[str]

class ReadThroughSessionCache:
    def __init__(
        self,
        redis_client: redis.Redis,
        load_from_db: Callable[[str], Optional[SessionContext]],
        ttl_seconds: int = 900,
    ):
        self.r = redis_client
        self.load_from_db = load_from_db
        self.ttl = ttl_seconds

    def get(self, session_id: str) -> Optional[SessionContext]:
        key = f"session:ctx:{session_id}"
        raw = self.r.get(key)
        if raw:
            data = json.loads(raw)
            return SessionContext(**data)

        ctx = self.load_from_db(session_id)
        if ctx is None:
            return None

        self.r.setex(key, self.ttl, json.dumps(ctx.__dict__))
        return ctx

    def invalidate(self, session_id: str) -> None:
        self.r.delete(f"session:ctx:{session_id}")
```

On permission change events, pub/sub invalidation prevents agents acting on stale RBAC for fifteen minutes.

## Embedding caches: a hybrid reality

Embedding inference is costly. Two-tier strategy:

1. **Cache-aside for query embeddings** — same question within TTL skips embed API.
2. **Read-through catalog for document embeddings** — ingestion pipeline writes DB + vector index; serving layer read-throughs chunk vectors keyed by `chunk_id` (immutable until re-ingest).

Document embeddings rarely use naive TTL expiry; **version-based invalidation** when chunk content hash changes.

## Consistency models agents can tolerate

| Data type | Staleness budget | Pattern |
|-----------|------------------|---------|
| Public FAQ chunks | 1–24 hours | Cache-aside + corpus version |
| User account tier | 0–60 seconds | Read-through + event invalidation |
| Exchange rates | 5 minutes | Cache-aside with jitter TTL |
| LLM completion | Usually none | Do not cache personalized outputs |

Agents chaining multiple tools amplify stale reads — cache retrieval only after confirming authorization context matches cached tenant scope.

## Stampede and thundering herd

Hot keys (`system_prompt:global`, viral FAQ) trigger stampedes on expiry. Mitigations:

- **Jitter:** `TTL = base + random(0, base * 0.1)`
- **Single-flight:** one origin fetch per key (see lock example above)
- **Stale-while-revalidate:** return expired value immediately, async refresh
- **Probabilistic early expiration:** refresh before hard expiry under load

Monitor `cache_miss_rate`, `origin_qps_during_miss`, and `lock_wait_ms` — stampede signatures show lock waits spiking with miss rate.

## Security: tenant isolation in shared Redis

Never use `query text alone` as cache key in multi-tenant agents. Always prefix `tenant_id`. For defense in depth:

- Logical DB separation per tier (enterprise vs. shared)
- Encrypt values containing metadata at rest (Redis ACL + KMS)
- Disable `KEYS *` in production; use structured key namespaces

Cross-tenant cache poisoning is a critical finding in pen tests — one tenant's retrieved chunks must not appear under another's key namespace.

## Observability

Export metrics:

```
agent_cache_hits_total{layer="retrieval|session|embed"}
agent_cache_misses_total{layer="..."}
agent_cache_latency_seconds{operation="get|set"}
agent_cache_stampede_lock_waits_total
```

Correlate cache hit ratio with token spend and origin DB QPS. A rising hit ratio with flat token spend suggests caching wrong layer; flat hit ratio with high spend suggests key churn or TTL too short.

## Choosing between patterns in greenfield agent stacks

**Default recommendation:**

- **Cache-aside** — RAG bundles, tool read memoization, query embeddings, prompt template compilation
- **Read-through** — session context, user prefs, feature flags consumed by every turn
- **No cache** — authorization decisions, write tool paths, personalized LLM outputs in regulated flows

Migrate incrementally: add cache-aside to retrieval first (largest cost win), instrument hits, then session read-through if DB session reads exceed 20% of turn latency.

## Failure modes

- **Cache aside without invalidation on write** — HR updates policy; agents cite old PTO for a week
- **Read-through without circuit breaker** — Redis down blocks all session reads unless bypass exists
- **Caching error responses** — transient 503 from tool poisons cache; use negative caching with short TTL only
- **Giant serialized objects** — caching full conversation history in Redis; cache summaries or pointers instead

Always implement **cache bypass** flag for incident debugging.

## Write path interactions: invalidation beats hope

Cache-aside puts invalidation on the application. When an agent tool updates authoritative data — closing a ticket, changing account tier — the write path must delete or version-bump cache keys synchronously before returning success to the user. Miss this once and read-through staleness looks like an model hallucination: the agent confidently cites old state.

For read-through session caches, prefer **event-driven invalidation** over TTL alone. Publish `permissions.changed` events to a fan-out channel; every agent worker subscribed to that tenant drops affected session keys. TTL remains a safety net, not the primary consistency mechanism.

## The takeaway

Cache-aside gives agent engineers explicit control over what gets memoized — ideal for retrieval and idempotent tools. Read-through simplifies session and profile access across services. Match TTL and invalidation to staleness tolerance, isolate tenants in key design, and prevent stampedes on Monday-morning query storms. Done right, caching cuts token and infra cost without turning agents into enthusiastic repeaters of outdated policy.

## Resources

- [Redis caching patterns documentation](https://redis.io/docs/manual/patterns/)
- [AWS ElastiCache best practices](https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/BestPractices.html)
- [Google SRE — addressing cache stampede](https://sre.google/sre-book/caching/)
- [CNCF TAG Storage — cache consistency models](https://github.com/cncf/tag-storage)
- [OpenTelemetry semantic conventions for caches](https://opentelemetry.io/docs/specs/semconv/general/metrics/#cache)
