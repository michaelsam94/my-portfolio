---
title: "AI Agents: Edge Middleware Geolocation"
slug: "agent-edge-middleware-geolocation"
description: "Route agent requests by country, enforce data residency, and pick regional model endpoints using edge middleware—without trusting client-supplied geo headers or breaking cache keys."
datePublished: "2026-05-25"
dateModified: "2026-05-25"
tags: ["AI", "Agent", "Edge"]
keywords: "edge middleware, geolocation, data residency, agent routing, CF-IPCountry, Vercel middleware, regional LLM, GDPR, geo routing"
faq:
  - q: "Should agent apps trust X-Forwarded-For or client geo headers?"
    a: "No. Client-supplied geo headers are trivially spoofed. Edge middleware should derive country and region from the platform's trusted geo IP database (Cloudflare CF-IPCountry, Vercel x-vercel-ip-country, Fastly GeoIP) at the PoP handling the request. Pass derived values as internal headers stripped at the origin boundary."
  - q: "How does geolocation affect agent model routing?"
    a: "Use geo to select regional inference endpoints (EU model deployment vs US), enforce blocked jurisdictions, and attach locale hints to prompts. Never use geo alone for authorization—pair with tenant policy stored server-side. Log geo decisions for audit but avoid storing raw IP in application logs."
  - q: "What breaks when middleware rewrites URLs based on country?"
    a: "Cache keys, CDN variants, and signed URLs. If middleware internally rewrites `/api/agent` to `/api/agent-eu`, ensure cache keys include the routing decision or disable shared cache for authenticated agent routes. Session cookies must stay on one hostname to avoid split-brain sessions."
  - q: "How do I test geo middleware without traveling?"
    a: "Use platform-specific override headers in staging only (never production), VPN egress from target regions, and synthetic checks that assert routing tables map country codes to expected upstream origins. Unit-test pure routing functions with fixture country codes independent of IP libraries."
---
Compliance blocked a launch two days before GA: the agent product streamed conversation context through a US-only LLM endpoint while EU enterprise contracts required inference and retrieval logs to stay in `eu-west-1`. The frontend team had added a `locale` query param; backend ignored it. Edge middleware was the fix—a single choke point that derived country from the connecting IP, selected the regional upstream, and stamped every downstream request with an immutable `X-Data-Region` header origin services could enforce.

Geolocation at the edge is not marketing personalization for agent apps. It is a routing and policy layer that decides which model cluster, vector index replica, and retention bucket a session may touch—before any token leaves the browser. This post covers middleware patterns that survive audits, cache interactions, and multi-tenant policy matrices.

## What edge middleware owns in agent stacks

Framework middleware (Next.js, Nuxt, SvelteKit) and CDN Workers run before your agent API handler. For AI workloads, middleware should own:

**Geo derivation.** Map client IP → ISO country/region using the edge provider's database. Attach `X-Geo-Country`, `X-Geo-Region`, and `X-Data-Region` (your internal residency zone).

**Policy routing.** Redirect or proxy to region-specific origins: `agent-api-eu.internal`, `agent-api-us.internal`.

**Compliance gates.** Block requests from embargoed countries; return 451 with a support link instead of a generic 403.

**Locale hints.** Set `Accept-Language` overrides or `X-Agent-Locale` for downstream prompt assembly—derived from geo defaults plus user preference cookie, with geo as fallback only.

**Bot and abuse signals.** Combine geo with ASN and rate limits; agent endpoints attract scrapers probing free tiers.

Middleware should not call LLMs. Keep it deterministic, fast (<5 ms), and free of network hops except when absolutely necessary for geo IP refresh.

## Trusted geo vs spoofable client input

The failure mode is trusting `X-Country-Code` from the browser or a mobile SDK. Attackers set `DE` and route sensitive exfiltration through EU infrastructure while sitting elsewhere—or the reverse, to reach US-only models.

```typescript
// middleware/geo-trust.ts — Next.js Edge Middleware example
import { NextRequest, NextResponse } from "next/server";

const BLOCKED = new Set(["KP", "SY", "CU"]);
const EU_COUNTRIES = new Set([
  "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
  "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
  "PL", "PT", "RO", "SK", "SI", "ES", "SE",
]);

function dataRegion(country: string): "eu" | "us" | "apac" {
  if (EU_COUNTRIES.has(country)) return "eu";
  if (["AU", "NZ", "JP", "SG", "IN"].includes(country)) return "apac";
  return "us";
}

export function middleware(request: NextRequest) {
  // Platform-provided, not client-supplied
  const country =
    request.headers.get("cf-ipcountry") ??
    request.headers.get("x-vercel-ip-country") ??
    "XX";

  if (BLOCKED.has(country)) {
    return new NextResponse("Unavailable in your region", { status: 451 });
  }

  const region = dataRegion(country);
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-geo-country", country);
  requestHeaders.set("x-data-region", region);
  // Strip any client attempt to set these
  requestHeaders.delete("x-forged-region");

  const url = request.nextUrl.clone();
  if (url.pathname.startsWith("/api/agent")) {
    url.hostname = `agent-${region}.internal.example`;
  }

  return NextResponse.rewrite(url, { request: { headers: requestHeaders } });
}

export const config = { matcher: ["/api/agent/:path*"] };
```

Origin services must reject requests missing `X-Data-Region` or bearing values outside the tenant's allowed set—middleware is the first line, not the only line.

## Multi-tenant residency matrices

Enterprise tenants override default geo routing. Acme Corp may contract for EU-only processing even when executives travel. Store policy server-side:

```typescript
interface TenantGeoPolicy {
  tenantId: string;
  allowedRegions: Array<"eu" | "us" | "apac">;
  defaultRegion: "eu" | "us" | "apac";
  strictMode: boolean; // if true, reject geo/contract mismatch
}

export function resolveRegion(
  policy: TenantGeoPolicy,
  derivedRegion: "eu" | "us" | "apac",
  userPreference?: string,
): "eu" | "us" | "apac" {
  const candidate = (userPreference as typeof derivedRegion) ?? policy.defaultRegion;
  if (!policy.allowedRegions.includes(candidate)) {
    if (policy.strictMode) throw new Error("REGION_POLICY_VIOLATION");
    return policy.defaultRegion;
  }
  if (policy.strictMode && candidate !== derivedRegion) {
    // User pref cannot bypass residency when strict
    return policy.defaultRegion;
  }
  return candidate;
}
```

Middleware loads a cached policy snapshot (KV or edge config) keyed by `tenant_id` from JWT or session cookie. Policy changes propagate within your documented staleness window—usually 60 seconds max for compliance-sensitive tenants.

## Model and retrieval routing tables

Geo middleware selects upstreams; it does not embed vectors. Maintain explicit routing tables versioned in config:

| Data region | LLM endpoint | Vector index | Log sink |
|-------------|--------------|--------------|----------|
| eu | `https://llm-eu.internal/v1` | `pinecone-eu-gcp` | `logs-eu` |
| us | `https://llm-us.internal/v1` | `pinecone-us-aws` | `logs-us` |
| apac | `https://llm-apac.internal/v1` | `pinecone-apac-aws` | `logs-apac` |

```python
# origin/region_router.py
from dataclasses import dataclass

@dataclass(frozen=True)
class RegionTarget:
    llm_base: str
    index_host: str
    log_stream: str

ROUTING = {
    "eu": RegionTarget(
        llm_base="https://llm-eu.internal/v1",
        index_host="pinecone-eu-gcp",
        log_stream="logs-eu",
    ),
    "us": RegionTarget(
        llm_base="https://llm-us.internal/v1",
        index_host="pinecone-us-aws",
        log_stream="logs-us",
    ),
}

def upstream_for_request(headers: dict, tenant_policy: dict) -> RegionTarget:
    region = headers.get("x-data-region")
    if region not in tenant_policy["allowed_regions"]:
        raise PermissionError(f"region {region} not allowed for tenant")
    return ROUTING[region]
```

Agent orchestrators read `X-Data-Region` once per request and thread it through tool calls so a browser session cannot trigger a US webhook from an EU-routed turn.

## Cache, cookies, and CDN interactions

Geo-based rewrites break naive caching. If `/api/agent/stream` proxies to different origins by country, a shared CDN cache may serve a US response to a German client.

Rules:

- Mark authenticated agent routes `Cache-Control: private, no-store`.
- If you must cache public agent demos, use `Vary: CF-IPCountry` or separate URLs (`/demo-eu`, `/demo-us`).
- Keep cookies on one canonical host; middleware rewrites internally only.
- Signed WebSocket URLs for streaming must include region in the signature payload.

Streaming agent responses through middleware adds negligible latency if you pass-through bodies. Avoid buffering SSE chunks for inspection—that introduces jitter users perceive as "slow typing."

## Privacy, logging, and audit

Geo middleware sees IP addresses. Minimize retention:

- Log `country`, `region`, `tenant_id`, `request_id`—not full IP.
- If fraud teams need IP, write to a short-TTL security stream with restricted access.
- Document lawful basis for geo processing in your DPIA; agent chat content plus geo is sensitive combined data.

Audit exports should answer: "Why was this session processed in US?" Capture `{ timestamp, tenant_id, derived_country, selected_region, policy_version }` in an append-only store.

## Testing and rollout

**Pure function tests** for `dataRegion()`, `resolveRegion()`, and blocklists.

**Staging overrides** gated by environment:

```typescript
if (process.env.STAGE === "staging" && request.headers.get("x-test-country")) {
  country = request.headers.get("x-test-country")!;
}
```

Never compile override paths in production bundles.

**Synthetic probes** from EU, US, and APAC vantage every five minutes: assert TLS handshake region, response header `X-Data-Region`, and that LLM audit logs land in the expected bucket.

Roll out policy changes with feature flags per tenant. Canary a single EU enterprise customer before flipping default routing for all EU traffic.

## Failure modes and runbooks

| Incident | Detection | Response |
|----------|-----------|----------|
| Wrong region selected | Audit mismatch alerts | Roll back routing table version |
| Geo DB stale (XX country) | Spike in `country=XX` | Fail closed to default region or deny |
| Origin rewrite loop | 502 from middleware | Fix hostname map; disable rewrite |
| Latency regression | Middleware p95 > 10 ms | Remove sync policy fetch; cache in KV |

When geo provider returns `XX` (unknown), prefer deny for strict tenants and `defaultRegion` for consumer tiers—document the choice per product line.

## Closing

Edge middleware geolocation turns residency from a backend afterthought into a enforced property of every agent request. Derive country from trusted platform headers, never from clients; combine geo with tenant policy matrices; keep routing tables explicit and versioned; and treat cache and cookies as first-class victims of geo splits. Done well, product can launch globally while legal sleeps; done poorly, you discover the mismatch during a customer audit, not a unit test.

## Resources

- [Cloudflare CF-IPCountry header](https://developers.cloudflare.com/fundamentals/reference/http-request-headers/#cf-ipcountry)
- [Vercel geolocation in Edge Middleware](https://vercel.com/docs/functions/edge-middleware/middleware-api#geolocation)
- [Next.js Middleware documentation](https://nextjs.org/docs/app/building-your-application/routing/middleware)
- [ISO 3166-1 country codes reference](https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2)
- [HTTP 451 Unavailable For Legal Reasons (RFC 7725)](https://datatracker.ietf.org/doc/html/rfc7725)
