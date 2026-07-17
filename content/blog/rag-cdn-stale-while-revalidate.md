---
title: "RAG: Cdn Stale While Revalidate"
slug: "rag-cdn-stale-while-revalidate"
description: "Stale-while-revalidate at the CDN edge keeps RAG API responses fast during corpus updates—serve cached retrieval bundles while background revalidation fetches fresh chunks without user-visible latency spikes."
datePublished: "2026-05-13"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Cdn"]
keywords: "stale-while-revalidate, SWR, CDN caching, RAG API cache, Cache-Control, edge caching, revalidation, stale-if-error"
faq:
  - q: "What does stale-while-revalidate mean for RAG API responses?"
    a: "After Cache-Control max-age expires, the CDN may continue serving the cached response for an additional stale-while-revalidate window while asynchronously fetching a fresh copy from origin. Users see no latency spike during revalidation— they get slightly stale retrieval results instead of waiting for origin."
  - q: "When is stale content acceptable in RAG retrieval?"
    a: "Acceptable for public documentation with version metadata in responses, cached search results for non-critical queries, and static embedding manifests. Unacceptable for real-time policy documents, regulated content without version checks, or personalized authenticated retrieval where staleness could show wrong tenant data."
  - q: "How does stale-while-revalidate differ from stale-if-error?"
    a: "stale-while-revalidate triggers background refresh when content is past max-age but still within the SWR window. stale-if-error serves stale content only when origin returns an error (5xx). Use both: SWR for normal freshness, stale-if-error for origin outage resilience."
---
Corpus v47 went live at 14:00. The CDN served cached retrieval responses for `/api/v1/public/search` with a five-minute max-age. Every cache entry expired at 14:05 simultaneously. Without stale-while-revalidate, those requests would have blocked on origin while the RAG API recomputed hybrid search results—p95 would have jumped from 45 ms at edge to 800 ms at origin. With `stale-while-revalidate=600`, the CDN kept serving v46 results for up to ten additional minutes while background revalidation pulled v47 gradually. Users searching public docs saw no latency cliff; they might have seen slightly outdated snippets until revalidation completed.

Stale-while-revalidate (SWR) is an HTTP Cache-Control extension that decouples user-perceived latency from origin freshness. For RAG systems serving cacheable public retrieval at CDN edge, it is the difference between invisible corpus updates and post-deploy latency incidents.

## How stale-while-revalidate works

Standard caching timeline without SWR:

```
0──────── max-age ────────►| BLOCKING MISS | fresh origin fetch
                           expiry
```

With SWR:

```
0──────── max-age ──── SWR window ────►| must revalidate or miss
                           expiry      (blocking)
                    
During SWR window: serve stale immediately + async background fetch
```

The CDN returns cached content instantly. A background request fetches fresh content and updates the cache for subsequent requests. Only one background fetch per cache key—not one per user request.

## Cache-Control headers for RAG endpoints

Configure origin to emit appropriate headers:

```python
# api/public_retrieval.py
CORPUS_TTL_SEC = 300        # 5 min fresh
SWR_WINDOW_SEC = 600        # 10 min stale serve + background refresh
STALE_IF_ERROR_SEC = 86400  # 24h stale on origin 5xx

def cache_headers(corpus_version: str) -> dict[str, str]:
    return {
        "Cache-Control": (
            f"public, max-age={CORPUS_TTL_SEC}, "
            f"stale-while-revalidate={SWR_WINDOW_SEC}, "
            f"stale-if-error={STALE_IF_ERROR_SEC}"
        ),
        "Surrogate-Key": f"corpus-{corpus_version}",
        "Vary": "Accept-Encoding",
    }
```

CDN must support SWR—Cloudflare, Fastly, and Akamai do. CloudFront supports `stale-while-revalidate` in Cache-Control since 2021.

## Freshness vs correctness tradeoffs for RAG

SWR introduces staleness. Whether that is acceptable depends on content type:

| Content type | max-age | SWR window | Rationale |
|-------------|---------|------------|-----------|
| Public KB search | 300s | 600s | Minor staleness OK with version header |
| Embedding manifest | 3600s | 7200s | Version in URL is primary freshness |
| API OpenAPI spec | 86400s | 3600s | Rarely changes |
| Policy/compliance docs | 60s | 0s | No SWR—freshness critical |
| Authenticated retrieval | private, no-cache | — | Never CDN cache shared responses |

Expose corpus version in response body so clients detect staleness:

```json
{
  "corpus_version": "v47",
  "cached_at": "2026-07-17T14:03:00Z",
  "results": [...]
}
```

Frontend can show "results may not reflect latest updates" if `corpus_version` lags known current.

## CDN configuration examples

**Fastly** — respects Cache-Control SWR natively. Optionally override:

```
# fastly.vcl (usually not needed—origin headers suffice)
if (beresp.http.Cache-Control ~ "stale-while-revalidate") {
  set beresp.stale_while_revalidate = 600s;
}
```

**Cloudflare** — enable "Respect origin Cache-Control" in cache rules. SWR honored automatically.

**CloudFront** — configure origin response headers policy to forward Cache-Control. SWR supported in modern behaviors.

Verify SWR behavior with test:

```bash
# First request — MISS, populates cache
curl -sI "https://cdn.example.com/api/v1/public/search?q=refund&corpus=v47" | grep -i age

# Wait past max-age, request again — should be HIT with Age > max-age
sleep 310
curl -sI "https://cdn.example.com/api/v1/public/search?q=refund&corpus=v47" | grep -E "Age|X-Cache"
# Expect: Age: 310+, X-Cache: HIT (stale served)
```

## Interaction with corpus version bumps

When corpus version increments (v47 → v48):

**Without version in URL.** All cached keys expire on schedule. SWR smooths the transition—stale v47 results serve while v48 revalidates. Users may briefly see v47 snippets. Acceptable for public docs.

**With version in URL** (`corpus=v48` param). New version = new cache keys = cold miss for v48, but v47 keys remain for clients still requesting old version. No stampede on either version. Preferred pattern for major updates.

Combine both: version in URL for major bumps, SWR for within-version freshness.

## Background revalidation load on RAG origin

SWR shifts load from synchronous user requests to asynchronous background fetches. Origin still receives revalidation traffic—just not blocking users.

Estimate background QPS:

```
background_qps ≈ unique_cache_keys / SWR_window_seconds
```

For 10,000 unique search query cache keys with 600s SWR window: ~17 background revalidations/sec at steady state after max-age expiry. Manageable for most RAG APIs.

Spike occurs when many keys expire simultaneously (deploy clears cache metadata). Combine SWR with:
- TTL jitter per key (vary max-age ±10%)
- Surrogate key soft purge instead of hard delete
- Probabilistic early revalidation at CDN (Fastly `stale-while-revalidate-max-age`)

## stale-if-error for origin resilience

Pair SWR with `stale-if-error` for origin outage protection:

```
Cache-Control: public, max-age=300, stale-while-revalidate=600, stale-if-error=86400
```

If RAG origin returns 502 during embedding service outage, CDN serves last known good response for up to 24 hours. Critical for public documentation availability during partial pipeline failures.

Caution: stale-if-error on retrieval can serve very outdated content. Cap the window (3600–86400s) and monitor corpus version in stale responses.

## Anti-patterns

**SWR on authenticated endpoints without Vary.** Shared cache serves tenant A's retrieval to tenant B. Use `private` or tenant-scoped cache keys with `Vary: Authorization`.

**Infinite SWR window.** `stale-while-revalidate=31536000` defeats caching purpose—content never refreshes unless manually purged.

**SWR without corpus version exposure.** Users cannot tell answers are stale; trust erodes silently.

**Blocking revalidation fallback.** Some CDN misconfigurations block on revalidation miss. Test explicitly.

## Monitoring SWR effectiveness

Metrics to track:

- **CDN Age header distribution** — values > max-age indicate SWR serving
- **Origin QPS during corpus deploy** — should be flat with SWR vs spike without
- **User-facing p95 latency** — should not spike at max-age boundary
- **Corpus version mismatch rate** — client-reported vs current version

Dashboard panel: overlay cache hit rate, origin QPS, and p95 latency around deploy times. SWR success shows stable p95 despite origin QPS bump from background fetches.

## Application-level SWR complement

CDN SWR handles HTTP caching. Apply same pattern in application Redis cache:

```python
async def get_with_swr(key: str, loader, ttl: int, swr: int):
    entry = await redis.get(key)
    if entry:
        data = json.loads(entry)
        age = time.time() - data["stored_at"]
        if age < ttl:
            return data["value"]
        if age < ttl + swr:
            asyncio.create_task(_background_refresh(key, loader, ttl))
            return data["value"]
    return await _refresh(key, loader, ttl)
```

Layer CDN SWR (edge) over application SWR (Redis) over vector index (source of truth). Each layer adds latency absorption.

## Client-side freshness hints for RAG applications

Frontend clients should read corpus_version from API responses and compare against a known-current version endpoint. When mismatch detected, show non-blocking banner: "Newer documents available—refresh for latest results." This converts SWR staleness from silent trust erosion into explicit user choice.

Mobile RAG clients with offline cache extend SWR semantics to local storage—stale-while-revalidate applies to on-device cache layers with same TTL discipline as CDN. Sync corpus version on app launch before serving cached retrieval results.

## Measuring SWR effectiveness in production

Add custom CDN headers or origin response headers tracking revalidation outcomes: X-Cache-Status (HIT/STALE/MISS), X-Corpus-Version, X-Revalidated-At. Log these in RAG API access logs for analysis. Weekly report: percentage of requests served stale vs fresh, average staleness duration in seconds, correlation between stale serve rate and user feedback "outdated answer" reports. Tune max-age and SWR window based on evidence—not defaults.

## Acceptance criteria for cdn stale while revalidate

Ship only when staging demonstrates the failure modes you claim to handle. Record the evidence — load test output, chaos result, or screenshot of the alert firing — in the PR. Revisit the settings after the first real incident; production will teach you which timeout or retention value was optimistic. Prefer boring, documented tradeoffs over clever defaults that only exist in one engineer's head.

## Resources

- RFC 5861 — stale-while-revalidate and stale-if-error
- Fastly stale content serving guide
- CloudFront Cache-Control support documentation
- HTTP caching best practices for API responses
