---
title: "RAG: Edge Middleware Geolocation"
slug: "rag-edge-middleware-geolocation"
description: "Edge middleware geolocation for RAG — routing queries by data residency, locale-aware retrieval, compliance gates, and CF-IPCountry patterns."
datePublished: "2026-05-24"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Edge"]
keywords: "rag, edge, middleware, geolocation, ai, production, engineering, architecture"
faq:
  - q: "How does edge geolocation improve RAG responses?"
    a: "Geo signals route requests to region-appropriate vector indexes (EU corpus for EU users), select locale-specific embedding and generation models, apply jurisdiction-specific compliance filters, and prepend retrieved chunks relevant to local regulations—without exposing raw IP geolocation logic to application servers behind the edge."
  - q: "Which geolocation headers do edge platforms provide?"
    a: "Cloudflare exposes cf.ipcountry, cf.region, cf.city, and cf.timezone on requests. Fastly provides geo.country_code via VCL. AWS CloudFront offers CloudFront-Viewer-Country. Middleware should treat these as hints validated against tenant configuration, not sole legal basis for data residency decisions."
  - q: "Can users bypass geo routing with VPNs?"
    a: "Yes. Edge geo is best-effort for UX and default routing. Contractual data residency requires tenant identity, account home region, and document ACLs—not IP alone. VPN detection signals can flag mismatches between claimed account region and edge country for audit logging."
---
A German enterprise customer discovered their support RAG assistant occasionally cited US-only policy documents because requests from Munich engineers hit the default US vector index during a misconfigured failover. Legal had approved EU-isolated infrastructure; product assumed "we have an EU index" was sufficient without edge routing enforcing it. IP geolocation was available at Cloudflare but never read—middleware passed every request to `origin-us` for simplicity.

**Edge middleware geolocation** reads client geography from the CDN/proxy layer—before traffic reaches your RAG API—and uses it to route, filter, and personalize retrieval within compliance bounds. Combined with tenant metadata, it implements data residency and locale-aware answers at the lowest-latency hop.

## Geo signals available at the edge

Typical request headers (Cloudflare example):

| Header | Use in RAG |
|--------|------------|
| `CF-IPCountry` | Route to regional index pool |
| `CF-Region` | US state / EU region for regulatory nuance |
| `CF-Timezone` | Time-aware retrieval (business hours policies) |
| `Accept-Language` | Locale ranking for multilingual corpora |

Edge middleware normalizes into a **`GeoContext`** object attached to downstream requests:

```typescript
interface GeoContext {
  country: string;       // ISO 3166-1 alpha-2
  region?: string;
  timezone?: string;
  locale: string;        // derived from Accept-Language + tenant default
  residencyBucket: "eu" | "us" | "apac" | "unknown";
}
```

Map country → residency bucket via config table updated by legal—not hard-coded in Worker source without review process.

## Middleware routing architecture

```typescript
// middleware.ts (Next.js edge / Cloudflare Worker pattern)
export async function middleware(request: NextRequest) {
  const country = request.headers.get("cf-ipcountry") ?? "XX";
  const locale = negotiateLocale(request.headers.get("accept-language"));
  const tenant = await resolveTenant(request); // JWT or subdomain

  const residency = resolveResidency(tenant.homeRegion, country);
  const origin = ORIGIN_MAP[residency]; // eu-rag.internal, us-rag.internal

  const headers = new Headers(request.headers);
  headers.set("X-Geo-Country", country);
  headers.set("X-Geo-Residency", residency);
  headers.set("X-Geo-Locale", locale);

  if (isBlockedJurisdiction(country, tenant)) {
    return new Response("Service unavailable in your region", { status: 451 });
  }

  return NextResponse.rewrite(new URL(request.nextUrl.pathname, origin), { request: { headers } });
}
```

**Rewrite** vs redirect: internal rewrite keeps URL bar clean; user does not see cross-region redirects.

## Locale-aware retrieval

Geolocation complements language—not substitute. A user in Belgium may prefer French or Dutch; `Accept-Language` leads, geo suggests default when header missing.

Retrieval filter augmentation:

```json
{
  "vector_query": "...",
  "metadata_filter": {
    "allowed_locales": ["fr", "nl", "en"],
    "jurisdiction": "EU",
    "effective_region": "BE"
  },
  "boost": { "locale_match": 1.2, "region_specific_policy": 1.5 }
}
```

Index chunks with metadata at ingest: `locale`, `jurisdiction`, `effective_countries[]`. Missing metadata means chunk excluded from geo-filtered queries—fail closed for regulated tenants.

## Compliance gates

Geo middleware enforces policies before expensive retrieval:

- **Geo-block**: sanctioned countries (OFAC list synced weekly)
- **Data residency**: EU tenant + non-EU POP → force EU origin even if latency higher
- **Logging restriction**: disable query logging headers for CA users with CPRA opt-out flag on account

```typescript
function resolveResidency(tenantHome: string, edgeCountry: string): string {
  if (tenantHome === "EU") return "eu"; // contractual: never US origin
  // Non-regulated: optimize latency
  if (EU_COUNTRIES.has(edgeCountry)) return "eu";
  if (APAC_COUNTRIES.has(edgeCountry)) return "apac";
  return "us";
}
```

Log `edgeCountry`, `tenantHome`, `chosenResidency`, `mismatch` boolean for audit dashboards.

## VPN and geo spoofing

Treat IP geo as hint:

- Account `home_region` from signup/KYC overrides latency optimization
- Mismatch alerts: EU account from US IP daily—fraud or traveling user; do not block automatically
- Optional VPN/datacenter IP lists downgrade trust for free-tier abuse

Never store raw IP in RAG query logs if policy forbids; store country code and ASN category only.

## Multi-corpus routing by geography

Global products often maintain:

- `support-kb-global-en` (baseline)
- `support-kb-eu-regulatory` (GDPR-specific addendum)
- `support-kb-us-state` (CCPA, state laws)

Middleware selects corpus list:

```typescript
const corpora = ["support-kb-global-en"];
if (residency === "eu") corpora.push("support-kb-eu-regulatory");
if (country === "DE") corpora.push("support-kb-de-locale");
```

Pass `X-RAG-Corpora` header to origin router; edge does not embed—only routes.

## Testing geo middleware

Unit tests with mocked headers insufficient. CI jobs:

- Request from synthetic `CF-IPCountry=DE` → assert rewrite to EU origin
- EU tenant from `CF-IPCountry=US` → still EU origin
- Blocked country → 451

Staging uses Workers preview with header injection; periodic production synthetic checks from external geo proxy services.

## Performance considerations

Middleware runs under tight CPU limits. Avoid:

- External geo API calls per request—use CDN-provided headers
- Heavy JWT parsing without cache—validate once, short-lived edge session cookie

Precompute tenant → residency map in KV with TTL; JWT carries tenant_id only.

## Observability

Metrics by `country`, `residency`, `corpus_set`, `blocked_reason`. Product analytics: "queries without locale-appropriate results" segmented by geo—surfaces indexing gaps (missing `de` chunks for German users).

Edge middleware geolocation is how RAG respects borders and languages without pushing IP databases into every microservice. Read country and locale at the edge, rewrite to the right regional origin, filter retrieval metadata before embedding spend, and log residency decisions for auditors who ask why a US document appeared in a EU session—it shouldn't, and middleware is where you enforce that.

## Fallback when geo headers missing

Local development and misconfigured proxies omit `CF-IPCountry`. Middleware should **default to tenant home region**, not US-East, when geo unknown—log `geo_fallback=true` for monitoring. Staging must inject geo headers in integration tests; developers use documented header overrides rather than disabling middleware.

## Edge middleware and CDN cache interaction

Geo-routed responses may vary by country—`Cache-Control: private` or `Vary: CF-IPCountry` prevents serving DE retrieval results to FR users from shared cache keys. Misconfigured CDN caching of personalized RAG responses is a common post-launch bug caught only by cross-border QA.

Document cache key formula including residency bucket and corpus version—never cache solely on URL path for authenticated RAG endpoints.

## Testing residency enforcement

Automated compliance tests: EU tenant JWT + `CF-IPCountry=US` must still route EU origin; log `residency_override=tenant_home` metric. US tenant from DE routes US unless data residency product tier purchased—product flag in middleware config table, not hard-coded country lists only.

Pen testers attempt VPN bypass; expect audit log entries, not silent wrong-region routing. Compliance report monthly: count of cross-region requests blocked vs allowed with exception ticket ID.

## Latency impact of middleware rewrites

Extra hop through edge rewrite adds milliseconds—profile end-to-end. If rewrite adds >20ms p95, consider **anycast origin** in region instead of cross-region rewrite for latency-sensitive RAG SLAs while keeping geo headers for metadata filters only.

Middleware CPU limits: heavy JWT validation or tenant DB lookups at edge may exceed Worker limits—cache tenant→residency map in KV with 5-minute TTL to avoid origin DB call per request at edge.

## Wrapping up geo middleware

Geolocation middleware encodes policy at the lowest-latency hop: where data may flow, which corpora apply, and which origin serves the request. Keep policy tables in git-reviewed config synced to edge KV; emergency geo blocks for sanctions updates should not require full application deploy. Audit monthly: sample 10k requests comparing edge country header, tenant home region, and actual origin served—discrepancy rate should stay below 0.01% excluding documented VPN mismatches logged for fraud review.

Geo middleware changes require coordinated updates to customer-facing data processing agreements when residency routing logic affects where prompts and retrieved chunks persist—legal review is part of deploy checklist, not post-incident cleanup.

## Field checklist for edge middleware geolocation

Before calling this done in production, confirm you can measure success and failure independently: a positive metric (throughput, conversion, recall) and a negative one (abuse rate, false accepts, lag). Add one alert that pages on the negative metric and one dashboard panel for the positive. Run a staging drill that forces the failure mode — timeout, poison input, or partial outage — and capture the exact commands in the runbook next to the config. If the drill takes longer than fifteen minutes to execute, simplify the recovery path before you need it at 2am.
