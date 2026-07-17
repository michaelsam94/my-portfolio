---
title: "AI Agents: Geo Blocking Compliance"
slug: "agent-geo-blocking-compliance"
description: "Enforce jurisdiction blocks, export controls, and data residency for agent APIs—layered geo policy at edge, gateway, and application tiers with audit evidence regulators accept."
datePublished: "2025-12-03"
dateModified: "2025-12-03"
tags: ["AI", "Agent", "Geo"]
keywords: "geo blocking, compliance, data residency, GDPR, export control, agent API, jurisdiction, OFAC, geo fence"
faq:
  - q: "Is IP-based geo blocking sufficient for agent compliance?"
    a: "No. IP geo is necessary but not sufficient. Pair it with tenant contract metadata, payment country, KYC jurisdiction, and model/data residency tags. VPN and satellite egress routinely misclassify users—strict workloads should fail closed when geo confidence is low rather than defaulting to permissive routing."
  - q: "Where should geo blocking run for LLM agent stacks?"
    a: "Use three layers: edge middleware for fast 451 responses and CDN cache isolation, API gateway for authenticated tenant policy, and application services for model routing and vector store selection. Each layer should log the same decision ID so auditors can trace a session from HTTP request to inference region."
  - q: "How do we block countries without breaking legitimate enterprise users?"
    a: "Maintain an allowlist override tied to tenant ID and signed contract metadata—not manual IP exceptions. Executives traveling abroad should inherit their org's residency zone via tenant policy, not personal IP. Document every override with expiry, approver, and legal ticket reference."
  - q: "What audit evidence do regulators expect for geo controls?"
    a: "Immutable logs showing country derived, policy version applied, allow/deny outcome, and downstream region selected. Retain denial events longer than allow events. Run quarterly synthetic probes from blocked jurisdictions and attach results to your compliance evidence pack."
---
A sanctions review flagged our agent product three weeks after launch: inference logs showed sessions from a blocked jurisdiction reaching a US-hosted model cluster because geo blocking lived only in the marketing site, not the `/api/agent/stream` path. Support had been whitelisting individual IPs. Legal wanted proof, not anecdotes.

Geo blocking for agent systems is a compliance control, not a CDN toggle. It governs who may invoke models, which regional endpoints may serve them, and what evidence you can produce when a regulator asks why a conversation was processed in Virginia instead of Frankfurt. This post covers layered enforcement, policy versioning, and the operational patterns that keep geo rules aligned with contracts—not with whoever opened the most recent support ticket.

## Why agent geo compliance differs from static websites

Traditional geo blocking returns 403 for `/pricing` based on `CF-IPCountry`. Agent stacks add moving parts:

**Streaming endpoints** bypass page-level rules when mobile apps call APIs directly.

**Tool execution** may reach third-party SaaS (email, calendar, code runners) outside your residency boundary even when inference stays local.

**RAG retrieval** can fan out to vector replicas in multiple regions unless collection routing is geo-aware.

**Background jobs** replay user context in batch workers that ignore the edge decision made at request time.

Compliance requires a **decision chain**: derive jurisdiction → evaluate policy → stamp downstream context → enforce at every egress. Missing any link creates audit gaps.

## Layered enforcement architecture

```text
Client → Edge (451 / region stamp) → Gateway (tenant policy) → Agent API (model route) → Vector DB (replica select)
                ↓                           ↓                          ↓
           audit: geo_decision_id ──────────────────────────────────────────→ immutable log store
```

**Edge layer.** Fast deny for embargoed countries; attach `X-Geo-Country`, `X-Geo-Confidence`, `X-Data-Region`. Strip client-supplied geo headers.

**Gateway layer.** Merge IP-derived geo with tenant contract (`allowedRegions`, `blockedCountries`, `strictMode`). Issue signed internal JWT carrying `geoDecisionId` and `effectiveRegion`.

**Application layer.** Refuse model calls when requested region ∉ tenant policy. Route embeddings search to regional Pinecone/Weaviate collections.

**Async layer.** Propagate `geoDecisionId` onto queue messages so summarization workers cannot process EU sessions in US workers.

## Policy model and versioning

Store geo policy as versioned documents, not hardcoded country lists in middleware:

```typescript
interface GeoPolicy {
  policyVersion: string;
  tenantId: string;
  blockedCountries: string[];       // ISO 3166-1 alpha-2
  allowedRegions: Array<"eu" | "us" | "apac">;
  defaultRegion: "eu" | "us" | "apac";
  strictMode: boolean;
  overrides: Array<{
    type: "tenant_contract" | "legal_hold";
    expiresAt: string;
    approvedBy: string;
    ticketRef: string;
  }>;
}

interface GeoDecision {
  decisionId: string;
  policyVersion: string;
  derivedCountry: string;
  confidence: "high" | "medium" | "low";
  effectiveRegion: "eu" | "us" | "apac";
  outcome: "allow" | "deny" | "route";
  reasonCode: string;
}

export function evaluateGeoPolicy(
  policy: GeoPolicy,
  derivedCountry: string,
  confidence: GeoDecision["confidence"],
): GeoDecision {
  const decisionId = crypto.randomUUID();
  const base = {
    decisionId,
    policyVersion: policy.policyVersion,
    derivedCountry,
    confidence,
  };

  if (policy.blockedCountries.includes(derivedCountry)) {
    return { ...base, effectiveRegion: policy.defaultRegion, outcome: "deny", reasonCode: "COUNTRY_BLOCKED" };
  }
  if (confidence === "low" && policy.strictMode) {
    return { ...base, effectiveRegion: policy.defaultRegion, outcome: "deny", reasonCode: "LOW_GEO_CONFIDENCE" };
  }
  const region = countryToRegion(derivedCountry);
  if (!policy.allowedRegions.includes(region)) {
    return { ...base, effectiveRegion: policy.defaultRegion, outcome: "deny", reasonCode: "REGION_NOT_CONTRACTED" };
  }
  return { ...base, effectiveRegion: region, outcome: "allow", reasonCode: "POLICY_MATCH" };
}
```

Bump `policyVersion` on every legal change. Reject in-flight sessions when policy updates mid-stream only if `strictMode` and contract requires immediate cutoff; otherwise log `policyVersion` mismatch for reconciliation.

## Edge middleware implementation

```typescript
// middleware/geo-compliance.ts
import { NextRequest, NextResponse } from "next/server";

const OFAC_BLOCKED = new Set(["KP", "IR", "SY", "CU", "RU"]); // illustrative — legal owns canonical list

export async function middleware(req: NextRequest) {
  const country = req.headers.get("cf-ipcountry") ?? "XX";
  const confidence = country === "XX" ? "low" : "high";

  const tenantId = req.headers.get("x-tenant-id");
  const policy = tenantId ? await fetchPolicy(tenantId) : DEFAULT_POLICY;

  const decision = evaluateGeoPolicy(policy, country, confidence);

  await emitGeoAudit(decision, { path: req.nextUrl.pathname, tenantId });

  if (decision.outcome === "deny") {
    return NextResponse.json(
      { error: "service_unavailable_region", decisionId: decision.decisionId },
      { status: 451, headers: { "X-Geo-Decision-Id": decision.decisionId } },
    );
  }

  const headers = new Headers(req.headers);
  headers.set("x-geo-decision-id", decision.decisionId);
  headers.set("x-data-region", decision.effectiveRegion);
  headers.delete("x-client-country"); // never trust client

  return NextResponse.next({ request: { headers } });
}
```

Return **451 Unavailable For Legal Reasons** with a stable error schema—not opaque 403—so clients and auditors distinguish policy blocks from auth failures.

## Model and data plane routing

Geo compliance fails when inference stays regional but retrieval does not:

```python
# agent_router.py — enforce region at call site
def route_inference(decision: GeoDecision, tenant: Tenant) -> ModelEndpoint:
    endpoint = tenant.endpoints.get(decision.effective_region)
    if not endpoint:
        raise RegionPolicyViolation(decision.decision_id)
    if endpoint.region not in tenant.contract.allowed_regions:
        raise RegionPolicyViolation(decision.decision_id)
    return endpoint

def route_vector_search(decision: GeoDecision, collection: str) -> VectorClient:
    regional_collection = f"{collection}-{decision.effective_region}"
    client = VectorClient.for_collection(regional_collection)
    audit_log.info("vector_route", decision_id=decision.decision_id, collection=regional_collection)
    return client
```

Block tool calls that would egress to US SaaS when `effective_region == "eu"` unless the tool is on an approved regional allowlist.

## VPN, satellite, and low-confidence geo

MaxMind and provider databases misclassify VPN egress, corporate proxies, and Starlink ground stations. Options:

**Fail closed in strictMode** when confidence is low—painful for travelers but defensible in audits.

**Step-up verification** for medium confidence: require SSO session established in contracted region within N days.

**Tenant override** for known enterprise egress IPs registered during onboarding—not per-user support tickets.

Never silently downgrade strict tenants to US routing because geo lookup returned `XX`.

## Testing and synthetic compliance probes

Unit-test `evaluateGeoPolicy` with fixture countries and policy matrices. Integration tests should assert:

- Blocked country → 451 with `decisionId`
- EU tenant + DE IP → EU model endpoint in trace
- Policy version change → new decisions reference updated version

Run scheduled probes from cloud regions simulating blocked jurisdictions. Store pass/fail in your compliance evidence bucket with retention matching SOC2/ISO requirements.

```yaml
# .github/workflows/geo-compliance-probe.yml (excerpt)
jobs:
  probe-blocked-regions:
    strategy:
      matrix:
        region: [eu-west-1, us-east-1, ap-southeast-1]
    runs-on: ubuntu-latest
    steps:
      - name: Assert blocked jurisdiction denied
        run: |
          STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
            -H "X-Test-Country: KP" \
            https://staging-api.example.com/api/agent/health)
          test "$STATUS" = "451"
```

## Operational metrics and alerts

| Metric | Purpose |
|--------|---------|
| `geo_denials_total{reason_code}` | Spike detection vs legal list changes |
| `geo_confidence_low_total` | VPN/proxy misclassification rate |
| `geo_policy_version_mismatch` | Stale gateway cache |
| `geo_routing_violation` | Application bypass—page immediately |

Alert on any `geo_routing_violation`—that indicates enforcement drift, not user error. Review denial dashboards weekly with legal during export-control list updates.

## Common failure modes

**Marketing-only geo.** Blocks on www but not API—classic agent gap.

**IP allowlist sprawl.** Hundreds of `/32` exceptions with no expiry; remove in favor of tenant overrides.

**Cached responses crossing regions.** CDN cache keys must include `X-Data-Region` or disable shared cache for authenticated agent routes.

**Async workers ignoring decision context.** Batch summarization processes EU chats in US—propagate `geoDecisionId` on every queue message.

**Shadow IT tools.** Agent plugins calling global APIs; maintain tool registry with regional eligibility flags.

## The takeaway

Geo blocking compliance for agent products is a cross-layer control with audit-grade logging, not a WAF rule. Derive jurisdiction from trusted sources, evaluate versioned tenant policy at gateway and application boundaries, route models and vectors consistently, and prove it with synthetic probes. Legal teams care about decision IDs in logs more than they care about which CDN you use—give them a chain they can follow.

## Resources

- [Cloudflare IP Geolocation headers](https://developers.cloudflare.com/network/ip-geolocation/)
- [RFC 7231 — 451 Unavailable For Legal Reasons](https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.14)
- [OFAC Sanctions List Search](https://sanctionssearch.ofac.treas.gov/)
- [EU GDPR — International transfers overview](https://commission.europa.eu/law/law-topic/data-protection/international-dimensions-data-protection_en)
- [MaxMind GeoIP2 precision and limitations](https://dev.maxmind.com/geoip/docs/databases)
