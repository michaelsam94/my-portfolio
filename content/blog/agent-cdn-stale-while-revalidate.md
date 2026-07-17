---
title: "AI Agents: Cdn Stale While Revalidate"
slug: "agent-cdn-stale-while-revalidate"
description: "Stale-while-revalidate at the CDN for agent workloads — Cache-Control directives, origin shielding, prompt manifest freshness, and balancing latency with correctness."
datePublished: "2026-05-13"
dateModified: "2026-05-13"
tags: ["AI", "Agent", "Cdn"]
keywords: "stale-while-revalidate, stale-if-error, CDN caching, Cache-Control, agent latency, edge caching, SWR, origin shield"
faq:
  - q: "What does stale-while-revalidate mean for agent-facing HTTP responses?"
    a: "When a cached response passes its max-age freshness window but remains within the stale-while-revalidate window, the CDN can serve the stale copy immediately while fetching a fresh version from origin in the background. Users see low latency; the next request gets updated content. Ideal for agent SDK loaders, tool schema catalogs, and public documentation where brief staleness is acceptable."
  - q: "How is stale-while-revalidate different from stale-if-error?"
    a: "stale-while-revalidate applies during normal operation when origin is healthy but revalidation is needed. stale-if-error allows serving stale content when origin returns errors or times out — a resilience pattern for agent status pages and read-only config during partial outages. Many production setups combine both directives on the same response."
  - q: "Can SWR hide critical prompt or safety-policy updates?"
    a: "Yes — that is the tradeoff. If max-age=300 and stale-while-revalidate=3600, clients may see policy text up to 3900 seconds old. Safety-critical prompts should use short max-age, versioned URLs, or active purge on deploy rather than long SWR windows. Non-critical UI copy can tolerate longer staleness."
  - q: "Do all CDNs honor stale-while-revalidate identically?"
    a: "No. Cloudflare, Fastly, and Akamai support SWR with vendor-specific nuances in how background revalidation is scheduled and whether stale-if-error interacts with origin shield tiers. CloudFront added broader Cache-Control support in recent years but behavior differs from dedicated edge platforms. Test with your provider's cache analyzer before relying on SWR in production."
---
Agent chat widgets fail the latency test in two places: model inference and everything **before** the first token — loading embed scripts, fetching tenant config, downloading tool JSON Schema, warming WebAssembly tokenizers. Those assets are read-heavy, change infrequently relative to chat traffic, and tolerate seconds (sometimes minutes) of staleness. **`Cache-Control: stale-while-revalidate`** lets CDNs serve instantly from edge while refreshing asynchronously — the same pattern that makes news sites feel fast without blocking on origin RTT for every page view.

Used poorly, SWR keeps a recalled safety filter or revoked API schema alive at the edge long after you fixed origin. Used well, it cuts p95 embed load time from 400 ms to 40 ms without running a purge API on every deploy. This piece covers how SWR interacts with agent asset lifecycles, how to tune directives per resource class, and where origin shields fit.

## Freshness model refresher

HTTP caching distinguishes:

- **Fresh** — `Age <= max-age` (or `Expires` in the future). Serve without contacting origin.
- **Stale** — past freshness but potentially still servable under extension directives.
- **Must revalidate** — `no-cache` requires validation but allows stored copy after 304.

`stale-while-revalidate=<seconds>` extends servable stale lifetime **after** max-age expires. During SWR window, edge returns stale body immediately and triggers background revalidation.

```
Timeline (max-age=60, stale-while-revalidate=300)

0s ──────── 60s ──────────────────────────────── 360s
   FRESH         STALE (SWR) — serve + revalidate      TOO STALE — must block or miss
```

`stale-if-error=<seconds>` is orthogonal — serves stale on origin 5xx/timeout within its window, even outside SWR if configured.

## Agent asset tiers and SWR tuning

Not all agent HTTP responses should use SWR.

| Resource | Example path | Suggested policy |
|----------|--------------|------------------|
| Immutable hashed bundles | `/static/agent.a8f3.js` | `max-age=31536000, immutable` — no SWR needed |
| Tenant embed config | `/embed/{id}/config.json` | `max-age=60, stale-while-revalidate=3600, stale-if-error=86400` |
| Tool schema registry | `/schemas/tools/v2/index.json` | `max-age=300, stale-while-revalidate=1800` |
| Public status / model availability | `/status.json` | `max-age=15, stale-while-revalidate=60, stale-if-error=300` |
| Authenticated entitlements | `/v1/me/features` | `private, no-store` — never CDN cache |

Safety policies and content moderation rules belong in **short max-age** tiers or versioned paths, not long SWR. Marketing copy on `/docs/pricing` can SWR aggressively.

## Origin response headers

Express / Node example for embed config:

```typescript
// routes/embedConfig.ts
type CacheProfile = "aggressive" | "balanced" | "strict";

const PROFILES: Record<CacheProfile, string> = {
  aggressive: "public, max-age=120, stale-while-revalidate=7200, stale-if-error=86400",
  balanced:   "public, max-age=60, stale-while-revalidate=3600, stale-if-error=43200",
  strict:     "public, max-age=10, stale-while-revalidate=60, stale-if-error=300",
};

export function embedConfigHandler(profile: CacheProfile = "balanced") {
  return async (req: Request, res: Response) => {
    const tenantId = req.params.tenantId;
    const config = await loadEmbedConfig(tenantId);

    res.setHeader("Content-Type", "application/json");
    res.setHeader("Cache-Control", PROFILES[profile]);
    res.setHeader("Vary", "Accept-Encoding");
    // Surrogate keys for targeted purge when profile is "strict"
    res.setHeader("Surrogate-Key", `tenant-${tenantId} embed-config`);
    res.setHeader("ETag", `"${config.versionHash}"`);

    if (req.headers["if-none-match"] === `"${config.versionHash}"`) {
      return res.status(304).end();
    }
    res.json(config);
  };
}
```

**ETag** and **Last-Modified** enable cheap 304 revalidation during background refresh — origin sends empty body, edge keeps stale until new body arrives.

For Next.js agent dashboards:

```javascript
// app/api/public/tool-schemas/route.ts
export async function GET() {
  const schemas = await getPublicToolSchemas();
  return Response.json(schemas, {
    headers: {
      "Cache-Control": "public, max-age=300, stale-while-revalidate=1800, stale-if-error=3600",
      "CDN-Cache-Control": "max-age=300, stale-while-revalidate=1800", // Cloudflare override
    },
  });
}
```

Some providers honor `CDN-Cache-Control` or `Surrogate-Control` separately from browser `Cache-Control` — set shorter browser max-age and longer edge SWR when appropriate.

## CDN configuration patterns

**Fastly** — VCL or Compute@Edge can enforce SWR even if origin omits it (be explicit in origin instead when possible):

```vcl
# beresp stage — normalize agent config caching
if (req.url ~ "^/embed/" && beresp.status == 200) {
  set beresp.cacheable = true;
  set beresp.ttl = 60s;
  set beresp.stale_while_revalidate = 3600s;
  set beresp.stale_if_error = 86400s;
}
```

**Cloudflare** — Cache Rules transform origin headers; enable "Respect stale" options per tier. Page Rules legacy — prefer Cache Rules with custom cache keys for tenant paths.

**CloudFront** — attach cache policies with min/max/default TTL; ensure origin sends appropriate Cache-Control since policy may cap TTL. Origin shield in front of S3 reduces revalidation load when thousands of edges background-fetch simultaneously.

## Origin shield and thundering herd

SWR without shielding can stampede origin: 500 edge PoPs each background-revalidate the same stale object at once after TTL expiry.

```
Without shield: Edge₁..Edge₅₀₀ ──► Origin (500 concurrent revalidations)

With shield:    Edge₁..Edge₅₀₀ ──► Shield POP ──► Origin (1 revalidation)
```

Place **origin shield** (Fastly shield POP, CloudFront secondary cache, Cloudflare tiered cache) between edge and origin for hot agent config paths. Monitor origin QPS during deploy windows — spikes indicate SWR misconfiguration or missing shield.

## Interaction with agent deploy pipelines

Versioned hashed assets (`agent.v3.f4e2d1.js`) need no SWR — filename change busts cache naturally. SWR matters for **unversioned** endpoints:

1. Deploy new prompt config to origin
2. Without purge, edges serve stale until max-age + SWR expires
3. With SWR, users get old config instantly while edge revalidates

Mitigation stack:

- Bump `versionHash` in config → ETag changes → background revalidation picks up new JSON
- Pair deploy with surrogate-key soft purge for strict tiers
- Reduce max-age during active incident response

Automated check in CI:

```python
# tests/test_cache_headers.py
import httpx

def test_embed_config_swr_headers():
    r = httpx.get("https://staging.cdn.example/embed/demo/config.json")
    cc = r.headers["cache-control"]
    assert "stale-while-revalidate" in cc
    assert "max-age=" in cc
    max_age = int(next(p.split("=")[1] for p in cc.split(",") if "max-age" in p))
    swr = int(next(p.split("=")[1] for p in cc.split(",") if "stale-while-revalidate" in p))
    assert max_age <= 300, "max-age too long for safety-sensitive embed config"
    assert swr >= max_age, "SWR should extend beyond freshness window"
```

## Measuring SWR effectiveness

Metrics to track:

- **Edge hit ratio** — should rise after enabling SWR on config paths
- **Origin revalidation QPS** — 304 rate vs 200 rate
- **Time-to-fresh after deploy** — p95 seconds until sampled PoPs serve new ETag
- **Embed load p95** — client-side RUM for widget initialization

Log CDN debug headers (`Age`, `X-Cache`, `CF-Cache-Status`, `Fastly-Debug`) in synthetic monitors. Alert when post-deploy freshness exceeds SLO (e.g., 90% of PoPs fresh within 5 minutes).

## Failure modes and debugging

**Stale safety policy after emergency fix** — long SWR window + no purge. Response: shorten TTL tier, emergency purge, switch to versioned policy URLs.

**Infinite stale loop** — origin always 500 during revalidation; `stale-if-error` serves ancient content indefinitely. Cap `stale-if-error`, page on prolonged origin errors, fail closed for auth paths.

**Vary header misconfiguration** — `Vary: *` disables cache sharing; agent configs that vary on `Authorization` when they shouldn't destroy hit ratio.

**Compression double-keying** — ensure `Vary: Accept-Encoding` only; brotli vs gzip variants cache separately.

**Private data leakage** — never attach SWR to responses containing session tokens or PII. `Cache-Control: private` or `no-store` for user-specific agent settings.

## Browser vs CDN SWR

Modern browsers implement SWR for subresources fetched with cache API semantics, but agent embeds often load cross-origin from a CDN domain — **browser cache** follows CDN headers on first fetch. Service workers can implement custom SWR for offline agent UIs:

```javascript
// sw.js — stale-while-revalidate for tool schema cache
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (!url.pathname.startsWith("/schemas/")) return;

  event.respondWith(
    caches.open("schemas-v1").then(async (cache) => {
      const cached = await cache.match(event.request);
      const networkFetch = fetch(event.request).then((res) => {
        if (res.ok) cache.put(event.request, res.clone());
        return res;
      });
      return cached || networkFetch;
    })
  );
});
```

Coordinate CDN and service worker TTLs — double caching with divergent policies causes ghost bugs.

## Case study: embed latency before and after SWR

A production agent embed serving 2M daily loads had p95 initialization of 380 ms, dominated by config fetch (`/embed/config.json`) with `Cache-Control: max-age=0, must-revalidate` — every page load blocked on origin RTT. After switching to `max-age=60, stale-while-revalidate=3600` with origin shield:

- Edge hit ratio on config path rose from 12% to 89%
- p95 embed init dropped to 52 ms globally
- Origin config QPS fell from 2,000 to 180 (mostly background 304s)
- Post-deploy freshness: 95% of PoPs served new ETag within 90 seconds without manual purge

The tradeoff surfaced once: an emergency moderation rule change took four minutes to propagate globally — acceptable given parallel Slack alert to enterprise tenants. They added a `strict` cache profile for tenants under regulatory review (`max-age=10, stale-while-revalidate=60`) switchable via feature flag without code deploy.

## Decision matrix: when not to use SWR

| Scenario | Recommendation |
|----------|----------------|
| OAuth JWKS rotation during key compromise | Hard purge + `no-cache` until stable |
| A/B prompt experiment with legal review | Short max-age only; no SWR |
| Global agent SDK with content-hashed filename | `immutable`; SWR irrelevant |
| Rate-limit config affecting abuse prevention | `max-age=5` max; monitor freshness SLO |
| Static marketing blog for agent docs | Aggressive SWR + stale-if-error |

Document the chosen profile in your tenant onboarding runbook so customer success does not promise "instant config updates" when CDN policy says otherwise.

## Closing

Stale-while-revalidate is the right default for **read-heavy, latency-sensitive, eventually-consistent** agent assets: embed configs, public schemas, docs, status endpoints. It is the wrong default for **authorization, safety enforcement, and secrets**. Tune max-age for acceptable staleness bounds, add stale-if-error for resilience, shield origin from revalidation herds, and verify behavior on your specific CDN. SWR buys speed — explicit versioning and purge paths buy correctness when speed would lie.

## Resources

- [RFC 9111 — HTTP Caching (stale-while-revalidate)](https://www.rfc-editor.org/rfc/rfc9111.html#section-4.2.4)
- [web.dev — stale-while-revalidate](https://web.dev/articles/stale-while-revalidate)
- [Fastly — stale content delivery](https://www.fastly.com/documentation/guides/concepts/edge-state/cache/stale/)
- [Cloudflare Cache Rules documentation](https://developers.cloudflare.com/cache/how-to/cache-rules/)
- [Amazon CloudFront cache policies and origin shield](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cache-policies.html)
