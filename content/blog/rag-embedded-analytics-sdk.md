---
title: "RAG: Embedded Analytics Sdk"
slug: "rag-embedded-analytics-sdk"
description: "Embedded analytics SDKs for product teams — iframe vs JS SDK, row-level security, theming, and measuring RAG feature adoption in customer dashboards."
datePublished: "2025-03-19"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Embedded"]
keywords: "rag, embedded, analytics, sdk, ai, production, engineering, architecture"
faq:
  - q: "When should a RAG product expose analytics via embedded SDK versus building dashboards in-app?"
    a: "Embed when customers want RAG usage metrics inside their existing BI workflows—query volume, citation rates, thumbs feedback, cost per tenant—without you rebuilding charting for every CRM. Build in-app when analytics are tightly coupled to product actions (reindex triggers, eval failures) requiring write-back beyond read-only embed."
  - q: "How do embedded analytics SDKs enforce multi-tenant row-level security?"
    a: "Generate short-lived signed tokens (JWT or vendor embed secret) mapping embed session to tenant_id filter injected server-side in the BI layer. Never trust client-supplied tenant IDs. RLS policies in Looker, Metabase, or Cube.js filter every query regardless of chart configuration."
  - q: "What RAG metrics belong in customer-facing embedded dashboards?"
    a: "Queries per day, retrieval latency p95, answer feedback ratio, top unanswered question clusters, corpus coverage by locale, and token cost attribution—aggregated and anonymized per tenant policy. Avoid exposing raw prompts if contracts prohibit; offer aggregated topic buckets instead."
---
Customers asked where to see "how our team uses the AI search we pay for"—and the account team exported CSVs from internal Grafana weekly. Product had rich RAG telemetry internally but no **embedded analytics** path. Competitors shipped Looker embeds in settings pages; your dashboard remained a Zendesk article linking to a PDF metrics definition. Adoption conversations stalled because buyers could not self-serve proof of value.

**Embedded analytics SDKs** (Looker Embed SDK, Metabase static embedding, ThoughtSpot Everywhere, Cube.js client, Superset embedded) let SaaS products render governed dashboards inside their UI—iframes or JS components authenticated via signed tokens. For RAG platforms, embedding turns usage, quality, and cost data into a retention feature instead of an ops secret.

## Embed models: iframe vs JS SDK

| Approach | Pros | Cons |
|----------|------|------|
| Signed iframe URL | Simple, strong sandbox | Limited UX integration, cookie/third-party issues |
| JS Embed SDK | Theming, events, navigation hooks | More integration work, CSP configuration |
| React component wrappers | Native feel | Vendor lock-in, version coupling |

RAG settings pages often use **JS SDK** for seamless sidebar navigation; executive summary emails link **static iframe** snapshots.

Looker pattern:

```javascript
import { LookerEmbedSDK } from "@looker/embed-sdk";

LookerEmbedSDK.init("https://analytics.yourcompany.com", { url: "/api/embed/auth" });

const dashboard = LookerEmbedSDK.createDashboardWithId("rag-tenant-overview");
dashboard
  .appendTo("#analytics-root")
  .withParams({ tenant_id: session.tenantId }) // server validates, not client-only
  .build()
  .connect();
```

Server `/api/embed/auth` exchanges session cookie for signed embed URL—client never sees long-lived secrets.

## Row-level security for multi-tenant RAG

Every RAG metric table carries `tenant_id`. BI layer enforces:

```sql
-- Looker access filter example concept
-- sql_always_where: ${rag_events.tenant_id} = {% parameter embed_tenant_id %}
```

Token generation server-side:

```python
def embed_token(user, tenant):
    assert user.tenant_id == tenant.id or user.is_admin
    return jwt.encode({
        "tenant_id": tenant.id,
        "exp": utcnow() + timedelta(minutes= 15),
        "scopes": ["read:dashboard:rag-overview"],
    }, EMBED_SECRET, algorithm="HS256")
```

**Never** embed admin dashboards with cross-tenant data using same secret without scoped filters—classic CVE in SaaS analytics.

Test RLS: attempt token for tenant A, verify SQL logs show filter on A only.

## Metrics catalog for RAG embeds

Curate dashboards customers actually need:

**Usage**
- Queries/day, unique users, peak hour heatmap
- Channel split (API vs UI vs Slack bot)

**Quality**
- Thumbs up/down rate, override/edited answer rate
- "No result" rate and top failure queries (clustered, PII-scrubbed)

**Performance**
- End-to-end latency p50/p95, retrieval vs generation breakdown
- Error rate by error class

**Cost**
- Embedding tokens, generation tokens, $ estimate per tenant tier
- Cost per successful answer (normalized metric for finance buyers)

**Corpus health** (if customer manages corpus)
- Documents indexed, stale document count, last sync status

Avoid 40-chart kitchen sink—three dashboards max at launch.

## Theming and white-label

Embed SDKs accept theme objects matching host app:

```javascript
dashboard.withTheme({
  key_color: "#0066CC",
  background_color: "#FFFFFF",
  font_family: "Inter, sans-serif",
});
```

Host app CSS should not leak into iframe—postMessage height resize handling for responsive layouts.

White-label tier: custom logo, hide "Powered by Looker" per vendor contract.

## Event hooks for product integration

JS SDKs emit events—use for product analytics:

```javascript
dashboard.on("dashboard:run:complete", (event) => {
  productAnalytics.track("embedded_dashboard_viewed", {
    dashboard_id: event.dashboard.id,
    tenant_id: session.tenantId,
  });
});
```

Drill-down from chart → in-app corpus manager: listen `drillmenu:click`, navigate host router to `/corpus?filter=...` when customer clicks "stale docs" bar.

## CSP, cookies, and third-party embed pitfalls

**Content-Security-Policy** must allow frame-src to analytics host. **SameSite** cookies break embed auth if misconfigured—use dedicated embed SSO flow (SAML → short-lived embed token).

Safari ITP may block third-party cookies—prefer first-party subdomain `analytics.customerapp.com` CNAME to vendor.

## Performance and load

Embedded dashboards run heavy queries. Mitigate:

- **Aggregate tables** materialized hourly for tenant metrics—not raw event scans
- **Query cache** in semantic layer (Cube, dbt metrics)
- **Load dashboard on tab activation**, not page load
- Set **row limits** and **query timeout** in BI tool

Show skeleton UI while embed connects—Looker cold start can exceed 2s.

## Governance and contractual constraints

Customer contracts may prohibit showing raw user queries in embeds—aggregate to topic clusters via offline NLP labeling. HIPAA tenants may forbid any PHI in BI warehouse feeding embed—separate pipeline with stricter redaction.

Document in DPA what embedded analytics stores, retention, and subprocessors (Looker Cloud hosted where).

## Build vs buy decision tree

**Buy embed** when: standard charts suffice, speed to market matters, ops team small.

**Build in-app charts** when: deep integration with RAG admin actions, custom eval visualizations, or embed licensing cost prohibitive at scale.

Hybrid: embed executive summary; custom React for corpus debug tools.

Embedded analytics SDKs close the "prove ROI" gap for RAG products. Signed tokens, tenant RLS, and a focused metrics catalog let customers see query volume, quality, and cost inside your app—without weekly CSV exports from Grafana and without leaking one tenant's prompts into another's dashboard.

## Embedding in customer-facing SLAs

Contractual uptime for analytics embed may differ from core RAG API—set expectations in SLA annex: embed availability 99.5% if vendor-hosted BI, with status page subscription. When Looker maintenance windows occur, in-app banner explains analytics temporary unavailability—avoid silent blank iframe.

## Custom metrics API vs embed

Enterprise customers sometimes want raw metrics via API instead of iframe. Offer **read-only metrics API** exporting same aggregates as embed with OAuth client credentials—single semantic layer (Cube/dbt) feeds both embed SDK and REST so numbers never diverge. Sales teams pitch embed for quick time-to-value; API for customers with existing Tableau estates.

## Accessibility of embedded dashboards

Iframe embeds must support keyboard navigation and screen reader labels—vendor accessibility VPAT on file. Host app provides skip link bypassing embed for users who cannot interact with third-party chart canvas.

Color contrast in embedded theme must meet WCAG when displayed inside host app background—not only standalone Looker instance. QA checklist includes embed in light and dark host themes.

## Multi-workspace and embedded admin

Enterprise customers with multiple workspaces need embed tokens scoped to **workspace_id**—RLS filter must match JWT claim exactly. Admin users switching workspaces in host app must refresh embed session token—stale token showing wrong tenant data is critical severity bug tested in QA matrix every release.

Embed SDK version pinning: Renovate updates `@looker/embed-sdk` with visual regression on analytics settings page—vendor SDK breaks iframe height contract occasionally; catch in CI not production.

## Wrapping up embedded analytics

Embedded dashboards turn RAG from black-box AI into accountable software customers can measure. Invest in semantic layer correctness once—embed and API share metrics—rather than rebuilding charts per customer request. Track embed adoption rate in product analytics: accounts viewing embedded dashboard weekly correlate with renewal in enterprise segments; prioritize UX polish on empty states and loading skeletons where first impressions determine whether buyers assign analytics to daily workflows.

Customer success should demo embedded analytics in every enterprise kickoff—accounts that never open the dashboard in first 30 days show measurably lower expansion revenue; in-app nudges after tenth successful RAG query increase embed adoption without support tickets.

Semantic layer ownership should sit with data platform, not embedded in each product squad—central ownership keeps embed metrics and API exports consistent while RAG product teams focus on query experience rather than rebuilding SQL for every customer dashboard request.

## Acceptance criteria for embedded analytics sdk

Ship only when staging demonstrates the failure modes you claim to handle. Record the evidence — load test output, chaos result, or screenshot of the alert firing — in the PR. Revisit the settings after the first real incident; production will teach you which timeout or retention value was optimistic. Prefer boring, documented tradeoffs over clever defaults that only exist in one engineer's head.
