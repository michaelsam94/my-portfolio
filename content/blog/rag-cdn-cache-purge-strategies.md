---
title: "RAG: Cdn Cache Purge Strategies"
slug: "rag-cdn-cache-purge-strategies"
description: "Purging CDN caches for RAG-served content—API-driven invalidation vs surrogate keys, soft purge for embedding manifests, and blast-radius control when corpus versions change."
datePublished: "2026-04-11"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Cdn"]
keywords: "CDN cache purge, cache invalidation, surrogate keys, CloudFront invalidation, Fastly purge, RAG static assets, API cache busting"
faq:
  - q: "When should RAG pipelines purge CDN caches?"
    a: "Purge when static retrieval artifacts change—precomputed embedding manifests, cached API response bundles served at edge, or public documentation pages that feed the RAG corpus UI. Do not purge on every document edit; use versioned URLs or surrogate keys for granular invalidation."
  - q: "What is the difference between hard purge and soft purge?"
    a: "Hard purge removes content immediately; the next request fetches from origin. Soft purge (Fastly, Cloudflare) marks content stale but serves it while revalidating in background—lower origin spike, slight staleness window. Use soft purge for large corpus updates; hard purge for security-sensitive retraction."
  - q: "How do surrogate keys reduce purge blast radius?"
    a: "Tag each cached response with surrogate keys (e.g., corpus-v3, tenant-acme, doc-uuid-123). Purge by key invalidates only matching responses instead of entire URL prefixes. A single document update purges one key, not the whole /api/retrieval/* path."
---
A corpus republication pushed 40,000 updated chunks to the vector index. The ops runbook said "purge CDN after reindex." Someone ran `/*` invalidation on CloudFront. Every edge node cold-missed simultaneously. Origin RAG API p95 spiked from 80 ms to 2.4 seconds for forty minutes. The reindex was fine—the purge strategy was not.

RAG systems increasingly serve cached artifacts at CDN edge: precomputed retrieval bundles for popular queries, static embedding manifest files, public knowledge base HTML, and API responses for unauthenticated documentation search. Purge strategy determines whether a content update causes a blip or an outage.

## What RAG teams cache at CDN edge

Not every RAG component belongs on a CDN, but these commonly do:

| Asset | Cache location | Purge trigger |
|-------|---------------|---------------|
| Public KB HTML pages | CDN → origin web | Page content change |
| `/api/v1/search?q=...` public endpoints | CDN → RAG API | Corpus version bump |
| Embedding manifest JSON | CDN → object storage | Model or corpus version |
| Static chunk preview pages | CDN → CMS | Document update |
| OpenAPI spec for RAG API | CDN → origin | API schema change |

Internal authenticated retrieval typically bypasses CDN or uses private cache with tenant-scoped keys.

## Purge mechanisms compared

**URL-based invalidation.** CloudFront, Akamai, and most CDNs accept explicit URL lists or path patterns. Simple but dangerous at scale—wildcard purges have unbounded blast radius.

```bash
# CloudFront — expensive, slow propagation (minutes to 15+)
aws cloudfront create-invalidation \
  --distribution-id E1234567890 \
  --paths "/api/v1/search/*" "/manifests/corpus-v3.json"
```

CloudFront allows 3,000 free invalidation paths per month; excess costs add up. Path wildcards count as one path but invalidate everything matching.

**Surrogate key purge.** Fastly and Cloudflare support tagging responses with cache tags, then purging by tag:

```http
# Origin response headers
Surrogate-Key: corpus-v3 tenant-acme doc-abc123
Cache-Control: public, max-age=3600, stale-while-revalidate=300
```

```bash
# Purge single document's cached responses
curl -X POST "https://api.fastly.com/service/{id}/purge/doc-abc123" \
  -H "Fastly-Key: ${FASTLY_API_KEY}"
```

One document update → one key purge → minimal origin load.

**Cache busting via versioned URLs.** Avoid purge entirely by embedding version in URL:

```
/manifests/corpus-v3.json     → after update, publish as corpus-v4.json
/api/v1/search?corpus=v3&q=... → corpus param bumps on reindex
```

Old URLs expire naturally via TTL. Purge needed only if forced retraction before TTL.

## Designing surrogate keys for RAG responses

Tag responses at multiple granularities:

```python
# middleware/cdn_surrogate_keys.py
def build_surrogate_keys(
    corpus_version: str,
    tenant_id: str,
    doc_ids: list[str],
    query_hash: str | None = None,
) -> str:
    keys = [
        f"corpus-{corpus_version}",
        f"tenant-{tenant_id}",
    ]
    # Cap doc-level keys to prevent header bloat
    for doc_id in doc_ids[:10]:
        keys.append(f"doc-{doc_id}")
    if query_hash:
        keys.append(f"query-{query_hash}")
    return " ".join(keys)
```

Purge hierarchy:

- Single doc edit → purge `doc-{id}`
- Tenant corpus rebuild → purge `tenant-{id}`
- Global model change → purge `corpus-{version}`

## Soft purge vs hard purge for corpus updates

**Hard purge** — content gone immediately. Next request hits origin cold. Thousands of simultaneous cold misses = stampede.

**Soft purge** — content marked stale, served while background revalidation fetches fresh copy. Origin load spreads over minutes.

For bulk corpus updates affecting many keys:

1. Publish new corpus version URL (`corpus-v4`)
2. Update application to request v4
3. Soft purge v3 keys with long stale-while-revalidate
4. Let v3 cache entries expire naturally

For security retraction (leaked document):

1. Hard purge specific `doc-{id}` key immediately
2. Purge vector index chunk in parallel
3. Verify with test request from multiple edge locations

## API-driven purge automation

Wire purge into ingestion pipeline:

```python
# ingestion/post_reindex_purge.py
import httpx

async def purge_document(tenant_id: str, doc_id: str, cdn: CdnClient):
    await cdn.purge_by_surrogate_key(f"doc-{doc_id}")
    await cdn.purge_by_surrogate_key(f"tenant-{tenant_id}")
    # Do NOT purge corpus-wide key for single doc update

async def purge_corpus_version(corpus_version: str, cdn: CdnClient):
    await cdn.soft_purge_by_surrogate_key(f"corpus-{corpus_version}")

async def emergency_hard_purge(doc_id: str, cdn: CdnClient):
    await cdn.hard_purge_by_surrogate_key(f"doc-{doc_id}")
    await audit_log.record("emergency_purge", doc_id=doc_id)
```

Rate-limit purge API calls—CloudFront invalidation has propagation delay; firing 100 invalidations in a minute wastes quota without faster convergence.

## CDN configuration for RAG API responses

Cache only idempotent GET requests with explicit cache headers:

```python
# api/search_endpoint.py
from fastapi import Response

@app.get("/api/v1/public/search")
async def public_search(q: str, corpus: str, response: Response):
    results = await retrieve(q, corpus_version=corpus)
    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=600"
    response.headers["Surrogate-Key"] = build_surrogate_keys(corpus, "public", results.doc_ids)
    response.headers["Vary"] = "Accept-Encoding"
    return results
```

Never cache authenticated responses without `private` directive and tenant-scoped keys. Cross-tenant cache poisoning is a real failure mode.

## Blast radius control checklist

Before any purge operation:

- [ ] Identify surrogate keys affected—not URL wildcards
- [ ] Estimate cached response count (CDN analytics)
- [ ] Choose soft vs hard based on urgency
- [ ] Confirm origin capacity for expected miss rate
- [ ] Run during low-traffic window for corpus-wide purges
- [ ] Monitor origin p95 for 30 minutes post-purge
- [ ] Verify purge propagation from 3+ geographic edge locations

## Provider-specific notes

**CloudFront.** Invalidation paths only—no native surrogate keys. Use `Cache-Control` with short TTL and versioned URLs instead, or put Fastly/Cloudflare in front of API origin.

**Fastly.** Full surrogate key support. Soft purge via `Fastly-Soft-Purge: 1` header on purge API call.

**Cloudflare.** Cache-Tag header (equivalent to surrogate keys). Purge by tag via API. Tiered Cache reduces origin load on purge.

**Akamai.** Tag-based invalidation via `Edge-Cache-Tag` response header.

## Monitoring purge impact

Track before and after purge:

- CDN cache hit rate (expect temporary drop)
- Origin RAG API QPS and p95 latency
- Error rate at origin (5xx from overload)
- Time to cache hit rate recovery

Alert if origin p95 exceeds SLO for >10 minutes post-purge—may need origin scale-up or softer purge strategy.

## When not to use CDN purge

- **Real-time internal retrieval** — bypass CDN entirely
- **Personalized results** — not cacheable at shared edge
- **Every document edit** — too granular; use TTL + versioned URLs
- **Vector index updates** — CDN does not cache vector DB; purge API cache only

Purge is a scalpel when surrogate keys and versioning are in place—a sledgehammer when the only tool is URL wildcard invalidation.

## Coordinating CDN purge with vector index updates

CDN purge and vector index update order matters. Purge API cache before index serves new corpus version and users get inconsistent results—fresh chunks in index but stale cached API responses. Standard sequence: deploy new index version, flip corpus version flag, soft-purge CDN surrogate keys for old corpus version, monitor origin miss rate for 30 minutes.

Document purge runbook in the same repo as ingestion pipeline. Automate purge calls from post-reindex webhook rather than manual CLI during incidents when judgment is impaired.

## Edge case: partial purge during rolling deploy

Rolling deployments mix old and new corpus versions briefly. Partial CDN purge—only keys tagged with old corpus version—prevents purging responses from new pods still warming up. Coordinate purge webhook with deployment pipeline stage: purge triggers only after load balancer confirms 100% new version traffic. Integration test in staging: deploy v48 while v47 cache entries exist, verify no v47 responses served after purge completes, verify v48 responses populate cache within five minutes without origin overload.

## Integration notes for cdn cache purge strategies

This rarely lives alone. Map upstream dependencies (auth, data stores, queues) and downstream consumers before you harden the happy path. Sequence the rollout: observability first, then flags, then the risky behavior change. That order turns rollback into a flag flip instead of a reverse migration under pressure. Keep the integration diagram in the same repo as the code so it cannot rot in a slide deck.

## Resources

- Fastly surrogate keys documentation
- Cloudflare cache tags and purge API
- AWS CloudFront invalidation limits and pricing
- HTTP Cache-Control and stale-while-revalidate spec
