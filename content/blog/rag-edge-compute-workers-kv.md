---
title: "RAG: Edge Compute Workers Kv"
slug: "rag-edge-compute-workers-kv"
description: "Edge Workers and KV for RAG — caching embeddings, geo-routed retrieval, auth at the edge, and latency budgets for global AI search."
datePublished: "2026-04-13"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Edge"]
keywords: "rag, edge, compute, workers, kv, ai, production, engineering, architecture"
faq:
  - q: "What RAG workloads belong at the edge versus origin?"
    a: "Edge suits auth and rate limiting, query embedding cache lookup, routing to nearest vector index replica, serving static corpus metadata, and returning cached retrieval results for hot queries. Heavy re-ranking, large context assembly, and LLM generation usually stay at origin or regional GPU clusters due to compute and memory limits on Workers."
  - q: "How should Workers KV store RAG cache entries?"
    a: "Store serialized retrieval payloads keyed by hash(query_embedding + corpus_version + access_tier) with TTL aligned to corpus refresh cadence. Keep values under 25MB KV limits; store chunk text summaries not full documents. Use cache tags in metadata for invalidation when corpus_version bumps."
  - q: "What are the consistency tradeoffs of KV for vector search?"
    a: "Workers KV is eventually consistent with global propagation delay (seconds to minutes). Do not use KV as source of truth for index state—use it for read-through cache only. Stale cache entries after reindex are acceptable if TTL is short or version key includes corpus generation hash."
---
Users in Singapore waited 800ms before retrieval even started—the request routed to a US-East origin, re-embedded a query identical to one asked four seconds earlier in Tokyo, and hit a vector database with no regional replica. The embedding API added 120ms; cross-Pacific RTT added the rest. Product wanted "instant search" on help docs; architecture treated edge as CDN for static JS only.

**Cloudflare Workers**, **Fastly Compute**, and similar **edge compute** platforms run V8 isolates globally. **Workers KV** (and analogous edge stores) provide low-latency key-value reads for cached data. Together they move RAG latency-sensitive paths—auth, cache, geo-routing—closer to users while keeping heavy inference at regional cores.

## RAG request path split across edge and origin

```
[User query]
    ↓
[Edge Worker]
    ├─ JWT validate, tenant extract
    ├─ Rate limit (Durable Objects / Redis)
    ├─ Query hash → KV: cached embedding?
    ├─ KV: cached retrieval result?
    ├─ Geo route to nearest index region
    ↓ (cache miss)
[Regional origin]
    ├─ Embed query (if needed)
    ├─ Vector search + rerank
    ├─ LLM generate
    ↓
[Edge Worker] → response + async KV write
```

Target: edge handles everything until cache miss or generation required—often 40–60% of help-center queries on repetitive phrasing.

## KV cache key design

Cache keys must include everything that affects answer correctness:

```typescript
async function cacheKey(req: RagRequest): Promise<string> {
  const normalized = normalizeQuery(req.query);
  const parts = [
    "rag-v2",
    req.tenantId,
    req.corpusVersion,      // bump on reindex
    req.accessTier,           // prevent cross-tenant leakage
    await sha256(normalized),
  ];
  return parts.join(":");
}
```

**Embedding cache** separate from **retrieval cache**:

- `emb:{hash(normalized_query)}:{model_version}` → float32 bytes or base64
- `ret:{cacheKey}` → `{ chunk_ids, scores, snippets }`

On corpus reindex, bump `corpusVersion` in keys—old entries orphan and expire via TTL without manual purge storms.

TTL guidance:

| Cache type | TTL | Rationale |
|------------|-----|-----------|
| Query embedding | 24h | Model-stable, query-repeatable |
| Retrieval results | 1–4h | Balance freshness vs hit rate |
| Hot FAQ answers | 15m | Policy docs change more often |

## Worker implementation sketch

```typescript
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const req = await parseAndAuth(request, env);
    if (!req.ok) return req.error;

    const key = await cacheKey(req);
    const cached = await env.RAG_KV.get(key, "json");
    if (cached) {
      return Response.json({ ...cached, cache: "hit" });
    }

    const region = pickRegion(request.cf?.colo, req.tenantRegion);
    const origin = env.ORIGIN_URLS[region];
    const result = await fetch(`${origin}/retrieve`, {
      method: "POST",
      body: JSON.stringify(req),
      headers: { "X-Edge-Request-Id": crypto.randomUUID() },
    });

    const body = await result.json();
    ctx.waitUntil(env.RAG_KV.put(key, JSON.stringify(body), { expirationTtl: 3600 }));
    return Response.json({ ...body, cache: "miss" });
  },
};
```

`waitUntil` writes KV after response—user latency excludes cache populate time.

## Geo-routing vector indexes

Vector DB replicas (Pinecone pods, pgvector read replicas, Weaviate modules) often live in 2–3 regions. Edge Worker selects origin by:

1. **User colo** from Cloudflare `cf.colo` or Fastly POP
2. **Tenant data residency** constraint (EU tenant → EU origin only)
3. **Replica health** from short-TTL health keys in KV updated by origin probes

Failover: if EU origin unhealthy, route to secondary only if contract allows cross-border retrieval.

## Rate limiting and cost control at edge

Embedding and retrieval cost money. Enforce limits before origin:

- **Durable Objects** or **Redis** counters per `tenant_id + minute`
- Stricter limits for anonymous trials
- Block known bot TLS fingerprints (see device fingerprinting) at edge

Return 429 with `Retry-After` before burning GPU at origin.

## Consistency and invalidation

KV is not strongly consistent globally. Two users in different POPs may get different cached answers for seconds after corpus update—acceptable for help docs if `corpusVersion` in key updates atomically at deploy time.

**Invalidation strategies**:

- Version bump in key (preferred)
- Prefix delete via Workers KV list + delete (slow at scale)
- Short TTL for high-stakes corpora (legal, medical)

For must-fresh queries, accept header `Cache-Control: no-cache` bypassing KV—charge premium tier or admin roles only.

## Size limits and payload shaping

Workers KV value limit 25 MiB; CPU time limits per request. Cache retrieval payloads with:

- Chunk IDs + scores + 200-char snippets—not full PDF text
- Let client or origin expand chunks on demand

Compress JSON with gzip before KV put if payloads approach MB scale—decompress in Worker on hit.

## Observability

Log edge decisions: cache hit/miss, colo, chosen origin, latency breakdown. Metrics:

- `edge_rag_cache_hit_ratio`
- `edge_rag_origin_latency_ms` by region
- `edge_rag_kv_errors`

Compare p95 user latency before/after edge cache—target 30–50% reduction for repeat-query workloads.

## When not to use edge KV

- **Personalized retrieval** where every user sees different ACL-filtered chunks—cache keys explode unless ACL encoded in key safely.
- **Sub-second corpus freshness** requirements—KV TTL fight you.
- **Large reranker models**—keep at origin GPU.

Edge Workers plus KV turn RAG from a single-region bottleneck into a geo-distributed cache and routing layer. Auth, rate limits, and hot query results move to the POP; origin handles what requires real compute. Singapore users get answers in 120ms when the embedding and retrieval payload already live in KV— not after a round trip to Virginia.

## Durable Objects for coordination

When multiple edge POPs write KV cache simultaneously, **Durable Objects** (Cloudflare) or equivalent provide single-threaded coordination per cache key—optional for high-churn keys suffering write races. Weigh DO cost vs duplicate origin fetches from race conditions.

For **cache stampede** on hot keys (product launch FAQ), use request coalescing: first miss triggers origin fetch, concurrent misses wait on same promise via Durable Object mutex.

## Cost modeling edge vs origin

Finance asks whether KV egress savings exceed Workers request charges. Model: `(cache_hit_rate * origin_cost_avoided) - (workers_requests * price + kv_reads * price)`. Revisit quarterly as query mix shifts—launch day hit rate spikes change economics. Document assumptions in FinOps dashboard tied to RAG product line.

## Testing edge cache behavior globally

Use **Cloudflare Workers preview** with colo simulation or third-party geo proxy services to verify cache hit from multiple POPs before launch. Staging in single region misses KV eventual consistency races visible only cross-POP.

Load test cache stampede scenario: 10k identical queries in one second from distributed clients—measure origin request count should be ≪ 10k if coalescing works. Document results in performance test report attached to launch ticket.

## Disaster recovery for edge configuration

Workers KV data loss or accidental namespace delete loses hot cache—not source truth. DR runbook: repopulate from origin on cache miss storm; increase origin capacity temporarily during cold cache period. Terraform state backs KV namespace definitions; prevent manual delete without break-glass.

Version Worker scripts alongside KV key schema changes—deploy Worker before changing key format so old keys gracefully miss rather than parse error crash edge isolate.

## Wrapping up edge strategy

Edge KV caching is a latency and cost lever, not a correctness layer. Origin remains authoritative; edge accelerates repeat queries and shields regional indexes from thundering herds during product launches. Success metrics: p95 latency reduction for cached queries, origin QPS reduction ratio, and zero cross-tenant cache key collisions in security audits. Review cache key formula quarterly whenever ACL model or corpus versioning changes—subtle key bugs become isolation incidents at scale.

Document which query classes bypass cache entirely: admin reindex triggers, compliance exports, and eval harness runs must send `Cache-Control: no-store` from clients so edge does not serve stale retrieval during intentional freshness tests before major corpus promotions.

Edge cache hit ratio belongs on the RAG product dashboard next to retrieval latency—when hit rate drops after corpus refresh, that is expected; when it drops without refresh, investigate key schema regressions first.

## Field checklist for edge compute workers kv

Before calling this done in production, confirm you can measure success and failure independently: a positive metric (throughput, conversion, recall) and a negative one (abuse rate, false accepts, lag). Add one alert that pages on the negative metric and one dashboard panel for the positive. Run a staging drill that forces the failure mode — timeout, poison input, or partial outage — and capture the exact commands in the runbook next to the config. If the drill takes longer than fifteen minutes to execute, simplify the recovery path before you need it at 2am.
