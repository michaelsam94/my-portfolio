---
title: "CORS Preflight Caching for Faster Cross-Origin Requests"
slug: "rag-cors-preflight-caching"
description: "Cache CORS preflight OPTIONS responses to cut agent dashboard latency — Access-Control-Max-Age, Vary headers, CDN pitfalls, and when preflight caching breaks after deploys."
datePublished: "2025-10-02"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Cors"]
keywords: "CORS preflight caching, Access-Control-Max-Age, OPTIONS request, agent API gateway, Vary header, browser preflight"
faq:
  - q: "How long should Access-Control-Max-Age be for agent APIs?"
    a: "Browsers cap Max-Age at 86400 seconds (24 hours) in Chromium and Firefox; Safari historically ignored or capped lower. For agent backends that rotate auth headers or CORS allowlists weekly, use 300–3600 seconds so policy changes propagate without users hard-refreshing. Pair short TTLs with versioned API paths when you must cache longer."
  - q: "Why do agent dashboards still send OPTIONS on every tool call?"
    a: "Preflight triggers on non-simple methods (PUT, PATCH, DELETE), custom headers (Authorization, X-Request-Id, X-Agent-Session), or Content-Type beyond application/x-www-form-urlencoded, multipart/form-data, or text/plain. Agent UIs often send application/json with Bearer tokens — every distinct origin+path+header combo may preflight unless Max-Age caches the prior approval."
  - q: "Does caching preflight at the CDN help agent latency?"
    a: "Only if the CDN forwards OPTIONS to origin or you configure edge rules that echo correct CORS response headers. Blindly caching 204/200 OPTIONS without Vary on Origin and Access-Control-Request-Headers causes cross-tenant leakage — one customer's allowed origin served to another. Prefer origin caching at the API gateway with explicit Vary."
---
The agent console felt fast in staging and sluggish in production. Chrome DevTools showed the pattern immediately: every tool invocation fired **two** round trips — an OPTIONS preflight, then the POST — and preflight never hit disk cache. The API team had configured CORS correctly on the gateway; they had simply omitted **Access-Control-Max-Age**, so the browser treated every cross-origin agent call as a fresh permission check. For a dashboard that chains twenty tool calls per workflow, that is forty HTTP requests where twenty would suffice.

CORS preflight caching is not exotic optimization. It is baseline latency hygiene for any agent UI hosted on a different origin than its API — `app.example.com` calling `api.example.com`, or a Vercel preview hitting a staging gateway. This post covers how browsers cache preflight, what headers must align, where CDNs lie, and how to verify caching survives deploys.

## When the browser preflights

Simple requests skip preflight. Agent stacks rarely qualify:

| Trigger | Agent example |
|---------|---------------|
| Method not GET/HEAD/POST | `PATCH /sessions/{id}/tools` |
| Custom request header | `Authorization`, `X-Trace-Id`, `X-Agent-Version` |
| Content-Type not "simple" | `application/json` bodies on POST |

Each unique combination of **URL**, **method**, **header set**, and **Origin** produces a distinct preflight cache entry. Adding a new telemetry header to the SDK invalidates prior cache keys for every endpoint until Max-Age expires.

```
Browser                    API Gateway
   │                            │
   │── OPTIONS /v1/tools ──────►│  Access-Control-Request-Method: POST
   │   Origin: https://app...   │  Access-Control-Request-Headers: authorization, content-type
   │                            │
   │◄── 204 No Content ─────────│  Access-Control-Allow-Origin: https://app...
   │    Access-Control-Max-Age: 3600
   │    Access-Control-Allow-Headers: authorization, content-type
   │                            │
   │  (cache 3600s for this key)
   │                            │
   │── POST /v1/tools ─────────►│  actual request — no second OPTIONS
```

Without `Access-Control-Max-Age`, the cache entry TTL is zero — browsers may still memoize briefly in memory during a single page session, but navigation or tab discard clears it.

## Server-side OPTIONS handler

Implement OPTIONS explicitly at the gateway; do not rely on frameworks to infer CORS from POST handlers alone.

```typescript
// gateway/cors.ts
const ALLOWED_ORIGINS = new Set([
  "https://app.example.com",
  "https://staging-app.example.com",
]);

const ALLOWED_HEADERS = [
  "authorization",
  "content-type",
  "x-request-id",
  "x-agent-session",
];

const MAX_AGE_SECONDS = 3600;

export function handleOptions(req: Request): Response {
  const origin = req.headers.get("Origin");
  if (!origin || !ALLOWED_ORIGINS.has(origin)) {
    return new Response(null, { status: 403 });
  }

  const requestMethod = req.headers.get("Access-Control-Request-Method");
  const requestHeaders = req.headers.get("Access-Control-Request-Headers");

  if (!requestMethod) {
    return new Response(null, { status: 400 });
  }

  // Echo requested headers if subset of allowlist (case-insensitive)
  const requested = (requestHeaders ?? "")
    .split(",")
    .map((h) => h.trim().toLowerCase())
    .filter(Boolean);

  const allowedSet = new Set(ALLOWED_HEADERS.map((h) => h.toLowerCase()));
  if (!requested.every((h) => allowedSet.has(h))) {
    return new Response(null, { status: 403 });
  }

  return new Response(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": origin,
      "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
      "Access-Control-Allow-Headers": ALLOWED_HEADERS.join(", "),
      "Access-Control-Max-Age": String(MAX_AGE_SECONDS),
      Vary: "Origin, Access-Control-Request-Method, Access-Control-Request-Headers",
    },
  });
}
```

**Vary** is non-negotiable when responses differ by Origin. CDNs and shared caches that ignore Vary serve Customer A's CORS headers to Customer B — a subtle cross-tenant bug in multi-tenant agent platforms.

Actual POST responses must repeat `Access-Control-Allow-Origin` (and `Allow-Credentials` if cookies flow). Preflight cache does not substitute for response headers on the real request.

## Gateway and CDN layering

Three common deployment shapes:

1. **API gateway terminates CORS** — OPTIONS never hits application pods. Best for uniform policy and lowest origin load.
2. **CDN edge** — cache OPTIONS only with cache key including Origin and requested headers. Default CloudFront/Fastly behaviors often miss OPTIONS entirely; configure a dedicated behavior.
3. **Service mesh sidecar** — Envoy's CORS filter supports `max_age`; ensure the filter runs on both ingress and internal east-west paths if browser-facing traffic passes through.

```yaml
# envoy cors filter excerpt
typed_config:
  "@type": type.googleapis.com/envoy.extensions.filters.http.cors.v3.Cors
  allow_origin_string_match:
    - exact: https://app.example.com
  allow_methods: GET, POST, PUT, PATCH, DELETE, OPTIONS
  allow_headers: authorization,content-type,x-request-id
  max_age: "3600"
```

Measure OPTIONS QPS separately from business routes. Healthy traffic shows OPTIONS ≪ POST after warm cache; OPTIONS ≈ POST means caching failed or Max-Age is zero.

## Agent-specific pitfalls

**Streaming and WebSockets.** CORS governs fetch and XHR; WebSocket handshakes use a different Origin check. Do not assume fixing REST preflight helps SSE or WS agent channels.

**Multiple SDK versions.** v1 SDK sends `X-Agent-Version: 1`; v2 adds `X-Tenant-Id`. Each header permutation is a new preflight key. Stabilize header sets across minor SDK releases or accept cache churn during rollouts.

**Credentials mode.** `fetch(..., { credentials: 'include' })` forbids `Access-Control-Allow-Origin: *`. Wildcard origins break credentialed sessions; explicit origin echo is required on both OPTIONS and POST.

**Third-party tool embeds.** Agents embedded in customer iframes may run on arbitrary origins. Dynamic origin allowlists (database-backed, cached 60s at gateway) beat static env vars — but shorten Max-Age when allowlist changes are frequent.

## Observability and verification

Instrument at the edge:

```python
# metrics middleware (pseudo)
def record_cors(req, resp):
    if req.method == "OPTIONS":
        metrics.increment("http.options.count", tags={"path": req.path_template})
        max_age = resp.headers.get("Access-Control-Max-Age", "0")
        metrics.histogram("cors.max_age", int(max_age))
```

Client-side verification script for CI:

```javascript
// scripts/verify-preflight-cache.mjs
const origin = "https://staging-app.example.com";
const url = "https://staging-api.example.com/v1/agent/tools";

async function preflight() {
  const t0 = performance.now();
  await fetch(url, {
    method: "OPTIONS",
    headers: {
      Origin: origin,
      "Access-Control-Request-Method": "POST",
      "Access-Control-Request-Headers": "authorization, content-type",
    },
  });
  return performance.now() - t0;
}

const first = await preflight();
const second = await preflight();
console.log({ firstMs: first, secondMs: second, cached: second < first * 0.5 });
```

Run twice in a real browser context; the second OPTIONS should not appear in Network tab if cache hit (Chrome hides cached preflight) or completes in sub-millisecond time.

Alert when OPTIONS p95 exceeds POST p95 × 0.3 sustained — usually a deploy stripped Max-Age or Vary misconfiguration at CDN.

## Security tradeoffs

Long Max-Age means revoked origins stay trusted until TTL expiry. For agent APIs with static allowlists, 24h is fine. For marketplaces that onboard customer subdomains hourly, keep Max-Age under 600s and accept extra OPTIONS cost — cheaper than serving a deprovisioned tenant.

Never cache OPTIONS at shared CDN layers without origin-specific cache keys. `Access-Control-Allow-Origin` must reflect the request Origin, not a constant.

Preflight responses must not leak sensitive bodies — 204 with headers only.

## Rollout checklist

1. Add explicit OPTIONS route before changing Max-Age in production.
2. Set Max-Age to 3600; verify with DevTools — disable cache, load app, reload, confirm OPTIONS count drops.
3. Add `Vary: Origin, Access-Control-Request-Method, Access-Control-Request-Headers`.
4. Dashboard OPTIONS/POST ratio target: < 0.05 after five minutes of active use.
5. Document header additions in SDK changelog — each new header busts preflight cache once per user.

## Service worker interaction

Progressive agent dashboards that register service workers must not intercept OPTIONS incorrectly. If `fetch` handlers rewrite cross-origin tool calls, ensure OPTIONS passes through untouched or implements identical CORS header logic. A service worker that caches POST responses but drops Max-Age on synthetic OPTIONS responses creates Heisenbugs — preflight succeeds in dev without SW, fails intermittently in production PWA mode.

## The takeaway

CORS preflight caching is a one-header fix that agent teams overlook because OPTIONS traffic is invisible in business metrics until dashboards feel heavy. Set `Access-Control-Max-Age`, echo `Vary` correctly, handle OPTIONS at the gateway, and watch OPTIONS QPS as a first-class SLO. Agent UIs that hammer tool APIs dozens of times per session will feel snappier without touching model latency at all.

## Resources

- [MDN: CORS preflight request](https://developer.mozilla.org/en-US/docs/Glossary/Preflight_request)
- [Fetch spec — HTTP-cors-protocol](https://fetch.spec.whatwg.org/#http-cors-protocol)
- [Envoy CORS filter documentation](https://www.envoyproxy.io/docs/envoy/latest/configuration/http/http_filters/cors_filter)
- [Chrome DevTools network panel — understanding preflight](https://developer.chrome.com/docs/devtools/network/)
- [OWASP CORS guidance](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
