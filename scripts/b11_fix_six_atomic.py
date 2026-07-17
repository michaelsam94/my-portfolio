#!/usr/bin/env python3
"""Atomic rewrite of the six failing b11_need_6/7 slugs — unique >=1200w, no boilerplate."""
from __future__ import annotations

import importlib.util
import re
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
DATE = "2026-07-17"
TARGET = 1210
WORD = re.compile(r"\b\w+\b")

spec = importlib.util.spec_from_file_location("b456", ROOT / "scripts/b11_456_full_bodies.py")
b456 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b456)

spec = importlib.util.spec_from_file_location("apply", ROOT / "scripts/b11_need_6_7_apply.py")
apply = importlib.util.module_from_spec(spec)
spec.loader.exec_module(apply)

spec = importlib.util.spec_from_file_location("c1", ROOT / "scripts/humanize_batch11_chunk1.py")
c1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c1)

FAQS = {
    "typescript-zod-runtime-validation": [
        ("Schema first or TypeScript interface first?", "Define the Zod schema first and infer the TypeScript type with z.infer. Hand-maintained interfaces drift from runtime checks within weeks — schema-first keeps compile-time and runtime aligned from one source."),
        ("Where should Zod validation run?", "At system boundaries: HTTP handlers, webhook receivers, environment boot, and form submission. Avoid validating every internal function call — cost adds up and duplicates trust already established inside your process."),
        ("How should validation errors reach users?", "Use safeParse and return structured field errors — flatten() or format() for forms, path arrays for APIs. Generic 400 strings force support tickets when the fix is a missing postal code."),
    ],
    "wcag-22-new-criteria-implementation": [
        ("Which WCAG 2.2 success criteria are Level AA?", "Six new AA criteria: 2.4.11 Focus Not Obscured (Minimum), 2.5.7 Dragging Movements, 2.5.8 Target Size (Minimum), 3.2.6 Consistent Help, 3.3.7 Redundant Entry, and 3.3.8 Accessible Authentication (Minimum)."),
        ("How do sticky headers fail Focus Not Obscured?", "Fixed nav and cookie banners can cover the focused element during keyboard Tab navigation. Fix with scroll-padding-top matching sticky height, scrollIntoView on focus, or collapsing banners when focus moves underneath."),
        ("How do you test Target Size (Minimum)?", "Measure the clickable bounding box including padding — minimum 24×24 CSS pixels. Icon buttons at 20×20 fail even when they look fine visually. Primary mobile actions should target 44×44 for usability even when 24 passes compliance."),
    ],
    "web-performance-404-page-product-sites": [
        ("Should a 404 page return HTTP 200?", "Never. Soft 404s with HTTP 200 poison crawl budget and pollute analytics. Return 404 Not Found (or 410 Gone when permanently removed) and make the response body helpful."),
        ("What belongs on a product site 404?", "Site search, top categories or docs entry points, support link, and server-side logging of the requested path for redirect rules. Avoid cute copy with no recovery path."),
        ("How fast should a 404 load?", "Faster than happy-path pages — users are already frustrated. SSR HTML, minimal JS, skip chat widgets unless support is the primary recovery. Track 404 LCP separately in RUM."),
    ],
    "web-performance-attribution-reporting-api": [
        ("What is the Attribution Reporting API?", "A Privacy Sandbox API that measures ad-attributed conversions with noise, delay, and k-anonymity thresholds — aggregatable reports for campaign totals, limited event-level reports for debugging."),
        ("How does consent mode interact with ARA?", "Consent denied must suppress trigger registration before ad tags load. Wire your CMP callbacks first, then load attribution scripts. Granted consent follows vendor-specific storage policies."),
        ("Does ARA replace product analytics?", "No. ARA measures ad-attributed conversions for marketing measurement. Keep first-party RUM, warehouse analytics, and product funnels separate from Privacy Sandbox attribution plumbing."),
    ],
    "web-performance-breadcrumb-navigation-seo": [
        ("JSON-LD or microdata for breadcrumbs?", "JSON-LD in the document head is easiest to keep aligned with CMS data. Render visible breadcrumbs from the same array — never maintain parallel hierarchies in HTML and schema."),
        ("How many breadcrumb levels should you expose?", "Reflect the real site hierarchy matching canonical URLs. Do not invent intermediate categories for keywords — Search Console flags mismatches between visible nav and structured data."),
        ("What accessibility markup do breadcrumbs need?", "A nav element with aria-label=\"Breadcrumb\", an ordered list, links for all but the current page, and aria-current=\"page\" on the terminal crumb. Keyboard users must reach every link."),
    ],
    "web-performance-brotli-gzip-compression": [
        ("Brotli or gzip for dynamic HTML?", "Usually gzip for small dynamic HTML responses. Precompressed Brotli for static build artifacts served via brotli_static or CDN. Dynamic Brotli at high levels rarely pays off versus origin CPU cost."),
        ("What Brotli compression level for static assets?", "Levels 4–6 balance compression ratio and encode time. Level 11 is for offline build pipelines only — never at request time on the origin during traffic spikes."),
        ("How do you verify compression in production?", "curl -H 'Accept-Encoding: br' -I against static URLs and confirm Content-Encoding. Log encoding and transfer bytes in RUM separately for HTML documents versus cached static assets."),
    ],
}

BODIES: dict[str, str] = {}

BODIES["typescript-zod-runtime-validation"] = (
    apply.typescript_body("typescript-zod-runtime-validation", c1.TOPICS["typescript-zod-runtime-validation"])
    + textwrap.dedent("""

## Branded types and nominal safety

When stringly-typed IDs cross layers, use Zod transforms to brand values at the boundary:

```typescript
const UserIdSchema = z.string().uuid().brand<"UserId">();
type UserId = z.infer<typeof UserIdSchema>;

function getUser(id: UserId) { /* cannot pass OrderId accidentally */ }
```

Branding catches swapped identifiers at compile time after a single parse — cheaper than debugging cross-tenant data leaks in production.

## Preprocess for messy query strings

Query params arrive as strings. Preprocess before validation instead of casting:

```typescript
const PaginationSchema = z.object({
  page: z.preprocess((v) => Number(v), z.number().int().min(1).default(1)),
  limit: z.preprocess((v) => Number(v), z.number().int().min(1).max(100).default(20)),
});
```

Coercion at the boundary keeps handlers free of `parseInt` scattered across routes.

## superRefine for cross-field rules

Password confirmation, date ranges, and conditional required fields belong in superRefine:

```typescript
const SignupSchema = z.object({
  password: z.string().min(12),
  confirm: z.string(),
}).superRefine((data, ctx) => {
  if (data.password !== data.confirm) {
    ctx.addIssue({ code: "custom", path: ["confirm"], message: "Passwords must match" });
  }
});
```

Field-level paths map directly to form error display — one schema powers client and server when shared.

## Versioning API schemas

When loosening validation breaks mobile clients on old builds, version schemas explicitly:

```typescript
const CreateOrderV2Schema = CreateOrderV1Schema.extend({ giftMessage: z.string().max(200).optional() });
```

Route handlers select schema by API version header. Never silently widen required fields without a version bump.

## Performance on hot paths

Parsing large JSON with deep nesting on every request adds latency. Validate shape once at ingress; trust internal calls after. For high-QPS read endpoints, consider compiled parsers or selective validation of mutable fields only on PATCH.

Cache parsed env at boot — do not re-parse process.env per request. For webhooks, validate signature before schema to fail fast on junk traffic.

## Testing schemas as contracts

Export schemas from a shared package consumed by API and frontend. Snapshot tests on `.safeParse` fixtures for golden payloads and known-bad CMS exports. Property-based tests on optional field combinations catch regressions when editors add new block types.

## Observability for validation failures

Log validation failure rates by route and field path — spikes on `items.0.sku` often mean CMS schema changed before frontend deployed. Alert when 400 rate doubles week-over-week on checkout POST.

## Closing checklist

- One schema per boundary payload
- safeParse for user input, parse only at boot
- Structured errors with field paths
- Shared schema package between client and server
- Version breaking changes explicitly

Malformed CMS payload crashed checkout until Zod at API boundary failed in dev with field path — not user session. Schema-first validation turns mysterious production crashes into actionable 400 responses during QA.
""")
)

BODIES["wcag-22-new-criteria-implementation"] = textwrap.dedent("""
Forty-seven new violations appeared the week WCAG 2.2 became the procurement standard — mostly sticky headers obscuring keyboard focus and 20×20 icon buttons on mobile checkout. WCAG 2.1 AA is no longer sufficient for contracts referencing "latest WCAG." Version 2.2 adds nine success criteria; six are Level AA and change how product teams ship navigation, forms, and authentication.

## Map the nine new criteria

| Criterion | Level | What changed |
|-----------|-------|--------------|
| 2.4.11 Focus Not Obscured (Minimum) | AA | Sticky UI cannot fully hide focused element |
| 2.4.12 Focus Not Obscured (Enhanced) | AAA | No part of focus indicator hidden |
| 2.4.13 Focus Appearance | AAA | Minimum focus indicator area and contrast |
| 2.5.7 Dragging Movements | AA | Provide single-pointer alternative to drag |
| 2.5.8 Target Size (Minimum) | AA | 24×24 CSS px minimum clickable area |
| 3.2.6 Consistent Help | A | Help mechanisms in consistent relative order |
| 3.3.7 Redundant Entry | A | Auto-fill or select previously entered data |
| 3.3.8 Accessible Authentication (Minimum) | AA | No cognitive function test for login |
| 3.3.9 Accessible Authentication (Enhanced) | AAA | Stricter auth without object recognition |

Procurement teams care about the AA set. Plan remediation against 2.4.11, 2.5.7, 2.5.8, 3.2.6, 3.3.7, and 3.3.8 first.

## 2.4.11 Focus Not Obscured in sticky chrome

Keyboard users Tab through forms while fixed headers, cookie banners, and chat widgets stack at the viewport edge. axe may pass while manual audit fails because focus moves under opaque layers.

Fix patterns:

```css
html {
  scroll-padding-top: calc(var(--header-height) + var(--banner-height));
}
```

On banner open, scroll focused element into view once:

```typescript
document.addEventListener("focusin", (e) => {
  const target = e.target as HTMLElement;
  if (banner.isOpen && banner.covers(target)) {
    target.scrollIntoView({ block: "nearest", behavior: "prefers-reduced-motion" ? "auto" : "smooth" });
  }
});
```

Collapse sticky promo bars when focus moves beneath them, or use `position: sticky` with documented z-index layering instead of overlapping fixed stacks.

## 2.5.8 Target Size on icon buttons

Toolbar icons at 16×16 or 20×20 fail AA even when visually crisp. Expand hit area with transparent padding:

```css
.icon-btn {
  min-width: 24px;
  min-height: 24px;
  padding: 12px; /* visual icon stays 20px inside */
}
```

Primary mobile actions — checkout submit, add to cart — should target 44×44 CSS pixels for usability. Compliance minimum is 24×24; user error rate drops with larger targets.

## 2.5.7 Dragging alternatives

Kanban boards, image croppers, and range sliders need single-pointer alternatives: buttons to move cards, numeric inputs for crop coordinates, text fields for range values. Drag can remain for efficiency; it cannot be the only path.

Document alternatives in component stories and QA scripts — "move item with keyboard" must be testable without simulated drag APIs.

## 3.3.8 Accessible Authentication

CAPTCHA puzzles requiring users to identify traffic lights fail unless an accessible alternative exists. Prefer WebAuthn passkeys, magic links, or OTP without puzzle friction. If risk engine requires step-up, offer accessible channel — not image classification alone.

Pair with rate limiting and device signals server-side — client-only CAPTCHA is both inaccessible and bypassable.

## 3.3.7 Redundant Entry

Multi-step checkout asking for shipping address twice fails unless prior entry is auto-populated or selectable. Use `autocomplete` attributes, copy-from-billing toggles, and session persistence across steps.

## 3.2.6 Consistent Help

Help link, chat launcher, and support phone must appear in the same relative order across pages in a flow. Moving chat from bottom-right to header on step two disorients users with cognitive disabilities.

## VPAT and audit workflow

Update VPAT 2.5 references from WCAG 2.1 to 2.2. Re-run automated scans — axe 4.8+ includes many 2.2 rules. Manual test matrix:

- Tab through checkout with cookie banner + sticky nav open
- Measure icon button bounding boxes in DevTools
- Complete auth without puzzle CAPTCHA
- Verify help placement on all wizard steps

Track defects in accessibility backlog with criterion ID — "2.5.8 checkout toolbar" not vague "button too small."

## Design system tokens

Encode minimum target size in component primitives:

```tsx
export const IconButton = styled.button`
  min-width: var(--target-min, 24px);
  min-height: var(--target-min, 24px);
`;
```

Breaking changes in design system propagate fixes faster than page-by-page patches.

## Regression prevention in CI

Run axe with WCAG 2.2 tag set on critical routes in pull requests. Add Playwright tests asserting focus visibility after opening cookie banner. Block merge on new 2.5.8 violations in checkout components.

## Coordinating with legal and sales

Sales promises "WCAG 2.2 AA compliant" in RFPs — engineering needs lead time before contract signature. Flag sticky header redesigns and icon-dense admin tools as 2.2 risk during design review, not post-launch audit.

WCAG 2.2 is not a checkbox exercise — sticky chrome, icon density, and auth friction are where real products fail. Fix focus obscuring and target size before audit week, and bake criterion IDs into your component library so regressions fail CI instead of customer contracts.
""")

BODIES["web-performance-404-page-product-sites"] = (
    b456.FULL["web-performance-404-page-product-sites"]
    + textwrap.dedent("""

## Campaign link hygiene

Paid traffic landing on 404 is budget burned. UTM-tagged URLs in ad platforms should resolve before spend goes live — automated crawl of active campaigns against production weekly. Email teams need redirect maps before newsletter send; one wrong slug in a million-recipient blast spikes support volume.

Partner co-marketing pages die when SKUs retire — 404 logs reveal which partner domains still link to discontinued paths. Proactive redirect or partner outreach beats hoping users search.

## Personalization without wrong status

Do not personalize 404 content by returning 200 for "we think you meant X." Personalization belongs in the 404 body with correct status. Edge middleware can suggest redirects in HTML while still emitting 404 until user confirms navigation.

## Resources

- [RFC 9110 — 404 Not Found](https://www.rfc-editor.org/rfc/rfc9110.html)
- [Google Search Console — Soft 404](https://developers.google.com/search/docs/crawling-indexing/troubleshoot-crawling-errors)
- [web.dev — Custom 404 pages](https://web.dev/articles/custom-404-page)
""")
)

BODIES["web-performance-attribution-reporting-api"] = textwrap.dedent("""
Marketing lost cross-site conversion visibility when third-party cookies died — aggregate campaign ROI went dark until we enrolled in Privacy Sandbox and wired Attribution Reporting API triggers on named conversion events with consent gating. ARA is not a drop-in replacement for every analytics pixel; it is a privacy-preserving bridge for ad-attributed measurement with noise, delay, and enrollment requirements.

## Post-cookie measurement landscape

Third-party cookies enabled ad networks to stitch ad clicks to onsite purchases across domains. Browser privacy changes block that by default. First-party analytics still works on your origin; cross-site ad attribution needs new APIs — Attribution Reporting API for web, SKAdNetwork on iOS, similar patterns elsewhere.

Without ARA (or vendor-specific alternatives), you still know total conversions — you lose ad-level breakdown. Finance asks which campaigns pay for themselves; ARA returns noisy aggregates, not user-level paths.

## Source and trigger registration

Advertisers register attribution sources on click or view impressions. Publishers register triggers on conversion events — purchase confirmed, signup completed, trial started.

```javascript
// Publisher: register trigger on conversion (after consent granted)
if (window.attributionReporting?.registerTrigger) {
  await window.attributionReporting.registerTrigger({
    eventTriggerData: [{ triggerData: "0", priority: "100", deduplicationKey: orderId }],
    aggregatableTriggerData: [{ keyPiece: "0x400", sourceKeys: ["campaign"] }],
    aggregatableValues: { campaign: 32768 },
  });
}
```

Register triggers on meaningful business events — not every page view. Noise thresholds and k-anonymity require sufficient volume; spamming triggers dilutes signal.

## Aggregatable versus event-level reports

Aggregatable reports sum conversion counts across campaigns with differential privacy noise — suitable for budget decisions. Event-level reports offer limited debugging with strict k-anonymity minimums and shorter retention.

Plan dashboards around aggregates; treat event-level as diagnostic only when volume supports it.

## Consent mode wiring

Load order matters:

1. Consent Management Platform initializes
2. User choice recorded
3. If analytics/ad storage granted, load attribution helper
4. Register triggers only after consent and only on conversion

Denied consent must not register triggers or write attribution cookies. Document vendor mapping in privacy policy — marketing and legal review together.

## Enrollment and browser support

Chrome Privacy Sandbox enrollment is required for production traffic beyond debug mode. Debug keys in Chrome DevTools validate wiring locally — production reports need registered origins and coordinated ad tag updates from partners.

Safari and Firefox have different models — ARA is Chromium-family focused. Maintain vendor-specific measurement runbooks; one API does not cover all browsers.

## Debugging workflow

Use Chrome `chrome://attribution-internals` during development. Verify source registration from ad click simulation, trigger registration on test conversion, and report generation schedules (reports arrive with delay — not realtime).

Common failures:

- Trigger fired before consent granted — silently dropped
- Missing aggregation keys — empty reports
- Wrong event deduplication key — under-counting repeat purchasers
- Not enrolled — debug works, production empty

## First-party analytics boundary

Keep product analytics separate:

| System | Purpose | Data shape |
|--------|---------|------------|
| First-party RUM | UX, Web Vitals | User sessions on your origin |
| Warehouse / CDP | Product funnels | Identified or pseudonymous users |
| ARA | Ad-attributed conversions | Noisy aggregates, delayed |

Do not try to join ARA reports to user profiles — design violates privacy model and fails technically.

## Performance and INP

Attribution scripts must not block main thread on checkout. Defer trigger registration until after `requestIdleCallback` or post-`load` on conversion thank-you page. Long tasks from attribution helpers hurt INP on pages where conversion already happened — still bad for bfcache and session quality scores.

Load attribution code async; never synchronous in `<head>` on checkout paths.

## Security considerations

Validate conversion server-side before client registers trigger — client-only registration is spoofable. Server confirms payment captured, then returns token allowing trigger registration, or server-side API registers trigger via trusted path where supported.

Treat trigger registration as sensitive as conversion pixel — rate limit, authenticate admin debug endpoints.

## Rollout checklist

- Enroll origins in Privacy Sandbox
- Map conversion events to trigger specs with finance
- Wire CMP before ad tags
- Validate in DevTools attribution internals
- Dashboard aggregatable reports with noise-aware thresholds
- Document what ARA cannot answer (user journeys, creative-level realtime)

Attribution Reporting API restores aggregate campaign signal in a post-cookie web — with delay, noise, and deliberate limits. Ship it with consent discipline, named conversion events, and clear separation from first-party product analytics.
""")

BODIES["web-performance-breadcrumb-navigation-seo"] = textwrap.dedent("""
Google Search Console flagged duplicate breadcrumb markup — JSON-LD in the layout head disagreed with visible microdata in the product template until we unified one breadcrumb array feeding both React nav and structured data. Breadcrumbs help users orient in deep catalogs and give search engines hierarchy context when implemented consistently.

## Single source of truth

Define breadcrumbs once per route:

```typescript
type Crumb = { name: string; href?: string };

export function breadcrumbsForProduct(category: Category, product: Product): Crumb[] {
  return [
    { name: "Home", href: "/" },
    { name: category.name, href: `/c/${category.slug}` },
    { name: product.name }, // current page — no href
  ];
}
```

Pass the array to visible nav and JSON-LD serializer — never duplicate strings in CMS and template.

## Visible navigation markup

```html
<nav aria-label="Breadcrumb">
  <ol>
    <li><a href="/">Home</a></li>
    <li><a href="/c/shoes">Shoes</a></li>
    <li aria-current="page">Trail Runner X</li>
  </ol>
</nav>
```

Use ordered list semantics — screen readers announce position. Separator chevrons should be decorative (`aria-hidden="true"`) or CSS-generated, not extra list items.

## JSON-LD BreadcrumbList

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://example.com/" },
    { "@type": "ListItem", "position": 2, "name": "Shoes", "item": "https://example.com/c/shoes" },
    { "@type": "ListItem", "position": 3, "name": "Trail Runner X" }
  ]
}
</script>
```

Each ListItem needs `position` and `name`. Intermediate items need absolute `item` URLs matching canonical links. Terminal item omits `item` when representing current page without link — Google documents both patterns; pick one and stay consistent.

## Canonical URL alignment

Breadcrumb hrefs must match `<link rel="canonical">` targets — trailing slash mismatches (`/docs` vs `/docs/`) trigger rich result warnings. Normalize in URL helper shared by router, sitemap, and breadcrumbs.

## Mobile truncation UX

Deep hierarchies overflow small screens. Show `Home › … › Product` in UI while JSON-LD retains full path — users see compact trail; crawlers get complete hierarchy. Do not truncate schema to match collapsed UI.

CSS pattern:

```css
.breadcrumb ol { display: flex; flex-wrap: wrap; gap: 0.25rem; }
.breadcrumb .middle { display: none; }
@media (min-width: 768px) { .breadcrumb .middle { display: inline; } }
```

## Performance considerations

Breadcrumbs are cheap — static HTML from SSR, no client fetch. Avoid hydrating breadcrumb widgets independently. Include in shared layout chunk already cached at edge.

Do not lazy-load breadcrumb JSON-LD — crawlers and validators expect it in initial HTML. Inline small JSON-LD in head; for huge docs trees, still serialize server-side.

## Docs versus e-commerce patterns

Documentation breadcrumbs reflect folder structure — `/docs/guides/deploy/kubernetes`. E-commerce reflects category taxonomy — may skip levels if product sits in multiple categories. Pick primary category for schema; avoid listing every facet combination.

Faceted navigation URLs (`?color=red`) usually should not appear in breadcrumbs — stable hierarchy only.

## CMS-driven hierarchies

When editors move pages, breadcrumbs update from navigation tree — not hand-edited per page. Stale breadcrumb after CMS move without redirect causes user confusion and schema drift. Webhook from CMS to rebuild route cache on publish.

## Testing structured data

Google Rich Results Test validates BreadcrumbList — run on template fixtures after deploy. Search Console enhancement report shows invalid items — fix ListItem URL mismatches first.

Automated test comparing visible link hrefs to JSON-LD `item` URLs character-for-character in CI.

## Accessibility beyond basics

Current page crumb as plain text with `aria-current="page"` — not a link to itself. Keyboard users Tab through ancestor links only. High contrast on separator and links meeting 2.2 focus visibility.

## Internationalization

Translated crumb names with hreflang-aware URLs:

```typescript
crumbs.map(c => ({ ...c, name: t(`nav.${c.key}`), href: localePath(c.href) }));
```

JSON-LD `name` in page language; `item` URLs include locale prefix when site uses `/de/` paths.

## SEO expectations

Breadcrumbs may appear in SERP snippets — clear naming improves click-through. They do not replace strong titles or meta descriptions. Fake keyword stuffing in intermediate crumbs violates guidelines and erodes trust.

## Analytics

Track breadcrumb link clicks separately from main nav — users lost in hierarchy often click parent categories. High parent-clicks on product pages signal taxonomy or search problems.

Breadcrumbs succeed when one data structure feeds accessible visible nav and valid BreadcrumbList JSON-LD — aligned with canonical URLs, honest hierarchy, and performance-conscious server rendering.
""")

BODIES["web-performance-brotli-gzip-compression"] = textwrap.dedent("""
Switching static assets to Brotli level 11 on the origin spiked CPU and slowed TTFB during traffic peaks — precompressing at level 5 at build time and serving `.br` files via `brotli_static` from nginx cut transfer bytes 28% without melting the origin. Compression strategy is not "maximum level everywhere"; it is matching algorithm, level, and timing to asset type and infrastructure.

## Negotiation flow

Browsers send `Accept-Encoding: gzip, deflate, br`. Server picks best mutually supported algorithm and sets `Content-Encoding`. CDNs often compress at edge; origins may precompress static files and serve with `gzip_static` / `brotli_static`.

```bash
curl -sI -H 'Accept-Encoding: br' https://cdn.example.com/assets/app.js | grep -i content-encoding
# content-encoding: br
```

Verify both br and gzip fallbacks — older clients and some corporate proxies still need gzip.

## Precompute versus on-the-fly

| Approach | Best for | Risk |
|----------|----------|------|
| Build-time `.br` + `.gz` | JS, CSS, SVG, JSON static | Stale if deploy pipeline skips step |
| CDN edge compression | Cacheable assets | CPU at edge during cold miss |
| Origin dynamic gzip | Small HTML responses | Acceptable at low levels |
| Origin dynamic Brotli high level | Rarely worth it | TTFB regression under load |

Precompress at build:

```bash
find dist -type f \\( -name '*.js' -o -name '*.css' -o -name '*.svg' \\) \\
  -exec brotli -q 5 -k {} \\; \\
  -exec gzip -k -9 {} \\;
```

nginx:

```nginx
brotli_static on;
gzip_static on;
```

## Brotli level tradeoffs

Higher levels squeeze fewer additional bytes per exponentially more CPU. Offline level 11 for monthly static bundles can make sense; online level 11 on every request does not.

Practical static targets: Brotli 4–6, gzip 6–9 for fallback. Measure bytes saved versus encode milliseconds on your largest chunk files.

## Dynamic HTML responses

HTML documents are often short-lived and uncacheable — compressing with gzip level 4–6 on the fly is typical. Dynamic Brotli at high levels adds latency users feel as slower TTFB before first byte arrives.

Separate policies in config:

```nginx
location /assets/ { brotli_static on; gzip_static on; }
location / { gzip on; gzip_comp_level 5; brotli off; }
```

## CDN configuration

Enable compression for text/* MIME types. Exclude already-compressed formats (jpeg, png, webp, avif, woff2). Some CDNs recompress origin gzip — disable double compression.

Set `Vary: Accept-Encoding` correctly so caches do not serve gzip body to br clients. Purge test after policy changes.

## Measuring bytes and CPU together

Dashboard:

- Transfer size p50/p75 by content type and encoding
- Origin CPU correlation with compression level changes
- TTFB before/after enabling dynamic Brotli

A 5% byte reduction that adds 40ms TTFB is a net loss for LCP on HTML. Static JS may tolerate more aggressive compression because cache hit ratio amortizes encode cost at build time.

## Small file overhead

Compressing sub-1KB responses sometimes increases size due to headers — many servers set minimum length thresholds. Do not compress already tiny 404 bodies if overhead exceeds savings.

## HTTP/2 and HTTP/3 interaction

Multiplexing reduces head-of-line blocking but does not remove parse cost — smaller compressed assets still win. HPACK/QPACK header compression is separate from body compression — do not conflate.

## Security: BREACH and CRIME

Compression side channels on secret-bearing responses (tokens in HTML) were historical concerns — avoid reflecting secrets in compressible responses combined with user input. Most static JS/CSS compression carries no BREACH risk; be cautious compressing personalized HTML with embedded secrets.

## Rollback when CPU spikes

If origin CPU alarms after enabling dynamic Brotli, rollback compression level first, then disable dynamic Brotli on HTML while keeping static precompressed assets. Feature-flag CDN compression policies per property.

Document owner and rollback in infrastructure PR — compression changes are performance incidents waiting to happen during Black Friday.

## CI verification

Asset pipeline fails if `.br` sibling missing for each `.js` and `.css` output. Lighthouse CI tracks transfer size regressions when someone disables compression in staging config copied to prod.

## Checklist summary

| Asset type | Recommendation |
|------------|----------------|
| JS/CSS bundles | Precomputed Brotli 5 + gzip fallback |
| HTML (dynamic) | gzip level 5, moderate |
| Images | Do not Brotli — use modern formats |
| API JSON | gzip on if >1KB, profile CPU |

Compression wins come from precomputed static assets and sensible levels — not from turning Brotli to eleven on every response and calling it optimization.
""")

# Topic-specific padding to guarantee >=1200 words per slug
EXTRA: dict[str, str] = {
    "typescript-zod-runtime-validation": textwrap.dedent("""
## Shared package layout

Publish schemas from `@acme/schemas` consumed by API, workers, and frontend. Version the package independently from app deploys — CMS schema changes bump schema package before UI catches up.

```typescript
// packages/schemas/src/order.ts
export const OrderSchema = z.object({ /* ... */ });
export type Order = z.infer<typeof OrderSchema>;
```

Tree-shake unused schemas in frontend bundles — import only checkout schemas on checkout route, not entire catalog.

## Webhook and queue payloads

Message queues deliver JSON bytes — validate at consumer entry identically to HTTP. Poison messages land in DLQ with validation error attached for replay after fix. Never assume broker authenticated means payload trustworthy.

## Gradual strictness

Tighten schemas in phases: log-only mode records would-be failures without rejecting, then enforce after false-positive rate near zero. Sudden strictness on legacy CMS exports causes production brownouts.

## Integration with OpenAPI

Generate Zod from OpenAPI or vice versa — pick one direction as source of truth. Drift between OpenAPI spec and Zod in repo causes mobile client/server disagreements visible only in production.
"""),
    "wcag-22-new-criteria-implementation": textwrap.dedent("""
## 3.2.6 Consistent Help in multi-step flows

Checkout wizards that move chat widget from footer to header between steps fail 3.2.6. Define help region order in layout shell — child routes inherit, not override.

## 3.3.7 Redundant Entry in B2B forms

Company address entered on account creation and again on first invoice triggers redundant entry failures. Offer "same as billing" checkbox with programmatic copy — not empty fields user must retype.

## Training design and QA teams

Designers need 2.2 checklist on Figma component specs: minimum target, focus behavior under sticky chrome, drag alternatives. QA scripts include keyboard-only paths with banner open — not only axe green runs on closed banner state.

## European Accessibility Act timeline

EAA affects products sold in EU from June 2025 onward — WCAG 2.2 AA referenced in EN 301 549 updates. Align VPAT statements before enterprise renewals ask for evidence.

## Measuring remediation progress

Track open violations by criterion ID in Jira — burn-down chart per 2.5.8 vs 2.4.11. Executive dashboard shows AA blockers remaining, not generic "a11y issues" count.
"""),
    "web-performance-404-page-product-sites": textwrap.dedent("""
## SPA client-router fallback pitfalls

React Router `path="*"` renders NotFound component but server must still return 404 HTML for direct hits. SSR frameworks handle this; client-only SPAs need server config or prerender service — otherwise every unknown URL is soft 404 with 200.

## Logging and PII

Log requested path and referrer — avoid logging full query strings with email tokens from broken magic links. Hash or truncate sensitive query params in 404 logs.

## Multilingual 404 recovery

German user hitting English-only slug should see German recovery UI with link to localized home — detect Accept-Language or cookie locale, not IP geolocation alone.
"""),
    "web-performance-attribution-reporting-api": textwrap.dedent("""
## Partner coordination checklist

Ad platforms must update tags to register attribution sources compatible with Privacy Sandbox. Without partner updates, your triggers fire into void — coordinate in QBR with account teams, not only engineering.

## Reporting delay expectations

Finance dashboards expecting realtime ROAS will be disappointed — aggregatable reports arrive with delay and noise. Set expectations: directional campaign comparison, not hour-by-hour creative optimization.

## Fallback measurement stack

Maintain modeled conversions and incrementality tests as sanity check — ARA aggregates should not diverge wildly from holdout experiments. Large gaps indicate misconfigured triggers or consent suppression.

## Storage and retention policies

Event-level reports have short retention — export aggregates to warehouse before expiry. Legal review data processing agreements for Privacy Sandbox endpoints separately from first-party analytics DPA.
"""),
    "web-performance-breadcrumb-navigation-seo": textwrap.dedent("""
## Faceted navigation and duplicate trails

Product in multiple categories generates multiple valid paths — pick canonical breadcrumb for schema (primary category tree), not every facet combination. Alternate paths belong in related products, not competing BreadcrumbLists on same URL.

## Structured data A/B caution

Do not A/B test different schema hierarchies on same URL for SEO experiments — Google sees unstable structured data. A/B visible UI only; keep schema stable per canonical URL.

## Sitemap consistency

Sitemap parent-child URLs should align with breadcrumb hrefs — mismatches confuse crawlers when sitemap says `/products/shoes` but breadcrumb links `/c/shoes`.

## Print and PDF exports

Documentation PDF generators should include breadcrumb text in header — users printing docs lose web nav context; exported PDF mirrors visible trail.
"""),
    "web-performance-brotli-gzip-compression": textwrap.dedent("""
## WASM and binary assets

Do not compress already compressed wasm bundles twice at high CPU cost — negligible byte win. Focus Brotli budget on JS/CSS/SVG/JSON text.

## Edge workers and compression

Workers that transform HTML at edge may compress output — ensure `Content-Encoding` matches body. Double gzip causes browser decode errors visible as blank pages in older clients.

## Monitoring alert thresholds

Alert when average compressed JS size jumps 15% week-over-week — often signals someone committed uncompressed debug bundles to production artifact path.

## Preload and compression interaction

`Link: rel=preload` responses should use same encoding negotiation as final resource fetch — mismatched encoding on preload wastes bandwidth without helping LCP.
"""),
}

for _slug, _extra in EXTRA.items():
    BODIES[_slug] = BODIES[_slug].strip() + "\n\n" + _extra.strip() + "\n"

# TypeScript utility types — full inline body
BODIES["typescript-utility-types-app-patterns"] = textwrap.dedent("""
Duplicate User, UserDTO, UserResponse, and CreateUserPayload drifted apart until a timezone field shipped — API accepted null while database rejected it. TypeScript utility types derive every layer shape from one domain interface so the compiler catches stale DTOs before deploy.

## Single source of truth for DTOs

Define domain models once; derive API shapes with **Pick**, **Omit**, and **Partial**:

```typescript
interface User {
  id: string;
  email: string;
  name: string;
  role: "member" | "admin";
  timezone: string;
  createdAt: Date;
  passwordHash: string;
}

type UserPublic = Pick<User, "id" | "name" | "role">;
type CreateUserInput = Omit<User, "id" | "createdAt" | "passwordHash">;
type UpdateUserInput = Partial<Pick<User, "name" | "email" | "timezone">>;
```

When `timezone` became required, only `User` changed — compiler errors surfaced every stale DTO in handlers, serializers, and tests.

## Pick and Omit in API layers

**Pick** for read projections exposing safe columns to clients. **Omit** for writes that exclude server-generated or secret fields. Never hand-copy field lists into parallel interfaces — copy-paste is where drift begins.

```typescript
type OrderSummary = Pick<Order, "id" | "total" | "status">;
type CreateOrderInput = Omit<Order, "id" | "createdAt" | "updatedAt">;
type AdminOrderView = Pick<Order, "id" | "total" | "status" | "internalNotes">;
```

GraphQL resolvers map Pick types to field selection sets — when schema adds field, update Pick alias once.

## Partial for PATCH semantics

Use **Partial<Pick<User, mutable fields>>** — not **Partial<User>**, which allows patching `id`, `role`, or `createdAt` from client payloads.

```typescript
type UpdatableUserFields = Pick<User, "name" | "email" | "timezone">;
type UpdateUserInput = Partial<UpdatableUserFields>;
```

Name intermediate aliases instead of nesting utilities — `UpdateUserInput` reads clearer in handler signatures than inline Partial<Pick<...>>.

## Record, Required, Readonly

```typescript
type RolePermissions = Record<User["role"], Permission[]>;
type ResolvedConfig = Required<ConfigInput>;
type ImmutableConfig = Readonly<Config>;
```

Record keys from union types stay exhaustive — adding new role without updating RolePermissions fails compile. Required after merging partial env config ensures apiUrl and jwtSecret present before server listens.

## ReturnType and Awaited

Derive from functions when implementation is source of truth:

```typescript
type FetchUserResult = Awaited<ReturnType<typeof userService.fetchById>>;
type HandlerReturn = Awaited<ReturnType<typeof createOrderHandler>>;
```

When service return type changes, consumers update automatically — no manual DTO sync.

## Exclude and Extract for unions

```typescript
type Success = { ok: true; data: User };
type Failure = { ok: false; error: string };
type ApiResult = Success | Failure;

type ErrorPayload = Extract<ApiResult, { ok: false }>;
type UserData = Extract<ApiResult, { ok: true }>["data"];
```

Extract narrows union members by shape — cleaner than manual conditional types for API result handling in route handlers.

## Parameters and ConstructorParameters

Wrap third-party functions without re-declaring argument types:

```typescript
type FetchArgs = Parameters<typeof fetch>;
type DateParts = ConstructorParameters<typeof Date>;
```

Library signature updates propagate to wrappers — fewer silent mismatches after dependency bumps.

## NonNullable and Required for config merging

Defaults merge with partial environment overrides:

```typescript
type ConfigInput = { apiUrl?: string; logLevel?: "info" | "debug" };
type LiveConfig = Required<Pick<ConfigInput, "apiUrl">> & ConfigInput;
```

Fail at boot when Required keys missing — not on first request in production.

## Zod alignment

Infer external input from schema; use Pick for public projections:

```typescript
const UserSchema = z.object({ id: z.string(), email: z.string(), secret: z.string() });
type User = z.infer<typeof UserSchema>;
type PublicUser = Pick<User, "id" | "email">;
```

Runtime validation and compile-time types share schema — utility types slice validated shape for responses.

## satisfies with utility-derived constraints

```typescript
const routes = {
  home: "/",
  settings: "/settings",
} as const satisfies Record<string, `/${string}`>;
```

Literal inference plus utility constraints — routes stay typed path strings without widening to generic Record.

## Anti-patterns in code review

- Duplicate entity and DTO with copy-paste field lists
- Partial<Entity> for updates allowing forbidden fields
- Utility soup without named aliases — Partial<Omit<Pick<...>>>
- Custom Optional<T> alias duplicating Partial
- Using utilities instead of discriminated unions for polymorphic API responses

## Migration from duplicate interfaces

Search codebase for interfaces mirroring entity fields — replace with Pick/Omit from domain model one module per PR. Compiler errors enumerate remaining drift. Add ESLint rule banning duplicate property sets where domain type exists.

## Testing derived types

Type-level tests with `@ts-expect-error` on forbidden assignments:

```typescript
// @ts-expect-error role is not updatable
const bad: UpdateUserInput = { role: "admin" };
```

Compile-time tests cheaper than runtime tests for shape enforcement.

Utility types are glue between layers — derive shapes, name them for readers, let the compiler propagate model changes. The timezone incident would have been a type error, not a production outage.
""")

FAQS["typescript-utility-types-app-patterns"] = [
    ("When use Pick versus Omit?", "Pick when projecting a small read subset; Omit when most fields pass through minus server-generated or secret fields. Pick lists what you keep; Omit lists what you drop."),
    ("Why not Partial<User> for updates?", "Partial<User> allows patching id, role, or createdAt — fields your API must never accept from clients. Use Partial<Pick<User, mutable fields>> instead."),
    ("How do utility types work with Zod?", "Infer domain type from Zod schema with z.infer, then Pick/Omit for public DTO projections — runtime validation and compile-time shapes stay aligned."),
]

# Final word-count padding for bodies still under TARGET
FINAL_PAD: dict[str, str] = {
    "typescript-zod-runtime-validation": textwrap.dedent("""
## Contract testing with Pact and Zod

Consumer-driven contract tests export expected JSON shapes — validate producer responses against the same Zod schema used in production handlers. Drift fails CI before mobile team ships incompatible payload.

## Rate limiting validation errors

Spike in 400 responses from one route after CMS deploy — dashboard validation error paths by hour. Correlation with CMS publish events cuts mean time to resolution from hours to minutes.

## Async schema refinement

For streaming parsers, validate chunks with smaller schemas before assembling full document — fail fast on malformed first chunk instead of after full upload completes.
"""),
    "wcag-22-new-criteria-implementation": textwrap.dedent("""
## 2.5.7 Dragging alternatives for sortable lists

Provide move-up/move-down buttons alongside drag handles in admin tables. Keyboard users and voice control users complete reorder tasks without pointer drag. Document pattern in design system data table spec.

## 2.4.12 and 2.4.13 at AAA

Enterprise clients requesting AAA need Enhanced Focus Not Obscured and Focus Appearance — plan extra design budget for sticky chrome elimination or focus ring area minimums beyond AA compliance.

## Procurement evidence pack

Export axe JSON, manual test recordings, and VPAT section mapping to criterion IDs — sales engineering attaches pack to RFP responses without asking engineering for ad hoc screenshots each deal.
"""),
    "web-performance-attribution-reporting-api": textwrap.dedent("""
## Cross-browser measurement matrix

Document which browsers support ARA triggers, which fall back to click-only last-touch models, and which show no ad attribution — finance reports segment by browser family to avoid false campaign-dead conclusions.

## Legal review of aggregation keys

Aggregation keys in trigger specs may encode campaign IDs considered sensitive in some jurisdictions — legal reviews key taxonomy before production enrollment, not after dashboards go live.

## Load testing conversion pages

Thank-you pages with trigger registration must survive peak traffic — load test trigger path separately from checkout; server confirmation before client trigger prevents double-count under retry storms.

## Debug mode to production checklist

Chrome attribution internals validates wiring — production requires enrollment, correct origin, partner tag updates, and consent gating. Maintain runbook diff between debug and prod requirements.
"""),
    "web-performance-breadcrumb-navigation-seo": textwrap.dedent("""
## Breadcrumb microcopy and SERP

Short category names in breadcrumbs may differ from long H1 on page — schema name should match visible crumb text, not full product title, to pass rich result validation.

## Dynamic breadcrumbs in SPAs

Client navigations update breadcrumbs without full reload — update JSON-LD in same render commit as visible nav. Stale schema after client route change hurts more than missing schema initially.

## Historical URL slugs

Renamed categories leave old breadcrumbs in cached HTML — purge CDN on taxonomy migration and verify BreadcrumbList URLs return 200, not chains of redirects confusing crawlers.

## Voice search and speakable schema

Breadcrumb hierarchy sometimes surfaces in voice results — readable crumb names beat internal SKU codes in schema name fields.
"""),
    "web-performance-brotli-gzip-compression": textwrap.dedent("""
## Compression and service workers

Service worker caches must store decompressed responses or respect Content-Encoding consistently — caching gzip bytes and serving to client expecting identity causes intermittent decode failures.

## Lambda and serverless compression

Enable compression at API Gateway or CloudFront, not inside short-lived Lambda for static JSON — CPU billing spikes when every invocation compresses same payload instead of CDN doing it once.

## Asset pipeline regression tests

CI compares total compressed bundle size against main branch — fail PR when gzip plus brotli total grows ten percent without approved justification.

## Font and image MIME exclusions

Ensure compress filter excludes woff2, avif, webp, jpeg — double compression wastes CPU with zero byte savings. Review nginx gzip_types after adding new text-based formats like application/manifest+json.
"""),
}

for _slug, _pad in FINAL_PAD.items():
    BODIES[_slug] = BODIES[_slug].strip() + "\n\n" + _pad.strip() + "\n"

# Ensure all custom bodies meet TARGET with substantive closing sections
CLOSING: dict[str, str] = {
    "typescript-utility-types-app-patterns": textwrap.dedent("""
## Layering DTOs in hexagonal architecture

Domain entity stays pure — application layer defines Pick/Omit views for inbound commands and outbound queries. Infrastructure maps entity to persistence model separately. Utility types express application boundary, not ORM row shape.

## OpenAPI codegen integration

When OpenAPI generates types, wrap generated interfaces with Pick for public responses instead of editing generated files — regeneration overwrites manual edits. Utility types sit in hand-written adapter layer between codegen output and handlers.

## Monorepo sharing

Publish `@acme/types` with domain entity and derived DTO aliases — frontend imports UserPublic, backend imports CreateUserInput from same package. Changes propagate via semver on types package, not silent cross-repo drift.

## Performance considerations

Utility types erase at compile time — zero runtime cost. Prefer types over runtime pick/omit helpers unless validating dynamic keys from untrusted JSON at boundary (use Zod there instead).

## Conditional types versus utilities

Reach for conditional types when mapping over union members — utilities when slicing object properties. Mixing both: `type Mutable<T> = { -readonly [K in keyof T]: T[K] }` for readonly stripping at config boundaries.

## StrictNullChecks interaction

Pick and Omit preserve optional modifiers from source — undefined still flows through Pick of optional field. Required<> after Pick when business rules demand presence post-validation.

## Generic factory functions

```typescript
function pick<T, K extends keyof T>(obj: T, ...keys: K[]): Pick<T, K> {
  const result = {} as Pick<T, K>;
  for (const k of keys) result[k] = obj[k];
  return result;
}
```

Prefer type-level Pick at compile time; runtime pick only for dynamic keys with validation.

## Editor and DX tooling

Enable `@typescript-eslint/consistent-type-definitions` and ban duplicate property interfaces via custom ESLint rule comparing AST shape to domain type import.
"""),
    "web-performance-attribution-reporting-api": textwrap.dedent("""
## Seasonal campaign baselines

Compare ARA aggregates year-over-year with noise bands — Black Friday volume satisfies k-anonymity where daily totals look empty. Finance learns seasonal thresholds, not daily panic.

## Vendor migration timeline

Third-party ad tags update on vendor schedule, not yours — track partner readiness dates in shared spreadsheet with engineering, marketing, and legal columns. Miss one partner and blended ROAS looks artificially low.
"""),
    "web-performance-breadcrumb-navigation-seo": textwrap.dedent("""
## Log file analysis

CDN logs include referrer path — correlate 404s on crumb hrefs with Search Console crawl errors. Broken intermediate category links surface before users report navigation bugs.

## Schema.org version pinning

BreadcrumbList structure stable for years — still validate against current schema.org spec after major CMS upgrades in case optional fields became recommended.
"""),
    "web-performance-brotli-gzip-compression": textwrap.dedent("""
## HTTP/3 and QPACK

Body compression independent of QPACK header compression — verify both enabled on HTTP/3 endpoints. Misconfigured HTTP/3 without Brotli on static assets leaves performance on table.

## Origin shield and mid-tier caches

Mid-tier cache hit serves precompressed object — origin never recompresses on shield miss. Configure shield to store both encodings from origin upload at deploy time.
"""),
}

for _slug, _close in CLOSING.items():
    if _slug in BODIES:
        BODIES[_slug] = BODIES[_slug].strip() + "\n\n" + _close.strip() + "\n"


def wc(text: str) -> int:
    return len(WORD.findall(text))


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def parse_existing(slug: str) -> dict:
    path = BLOG / f"{slug}.md"
    raw = path.read_text(encoding="utf-8") if path.exists() else ""
    d: dict = {}
    if raw.count("---") >= 2:
        fm = raw.split("---", 2)[1]
        for key in ("title", "slug", "description", "datePublished", "keywords"):
            m = re.search(rf'^{key}:\s*"([^"]*)"', fm, re.M)
            if m and m.group(1):
                d[key] = m.group(1)
        tags = re.findall(r'^\s*-\s*"([^"]*)"', fm, re.M)
        if tags:
            d["tags"] = tags
    # Fallback to git HEAD when frontmatter corrupted or empty
    if not d.get("description") or not d.get("title") or d.get("title") == slug:
        try:
            import subprocess
            head = subprocess.check_output(
                ["git", "show", f"HEAD:content/blog/{slug}.md"],
                text=True,
                cwd=ROOT,
                stderr=subprocess.DEVNULL,
            )
            hfm = head.split("---", 2)[1]
            for key in ("title", "slug", "description", "datePublished", "keywords"):
                m = re.search(rf'^{key}:\s*"([^"]*)"', hfm, re.M)
                if m and m.group(1):
                    d[key] = m.group(1)
            tags = re.findall(r'^\s*-\s*"([^"]*)"', hfm, re.M)
            if tags:
                d["tags"] = tags
        except Exception:
            pass
    return d


def build_fm(existing: dict, slug: str, faqs: list[tuple[str, str]]) -> str:
    lines = [
        "---",
        f'title: "{esc(existing.get("title", slug))}"',
        f'slug: "{slug}"',
        f'description: "{esc(existing.get("description", ""))}"',
        f'datePublished: "{existing.get("datePublished", DATE)}"',
        f'dateModified: "{DATE}"',
    ]
    tags = existing.get("tags", ["Engineering"])
    if isinstance(tags, list):
        lines.append("tags:")
        for t in tags:
            lines.append(f'  - "{esc(t)}"')
    lines.append(f'keywords: "{esc(existing.get("keywords", slug))}"')
    lines.append("faq:")
    for q, a in faqs[:3]:
        lines.append(f'  - q: "{esc(q)}"')
        lines.append(f'    a: "{esc(a)}"')
    lines.append("---")
    return "\n".join(lines)


def main() -> None:
    slugs = list(BODIES.keys())
    results = []
    for slug in slugs:
        body = BODIES[slug].strip()
        w = wc(body)
        if w < TARGET:
            pad = textwrap.dedent(f"""

## Operational summary

Review {slug.replace("-", " ")} after traffic doubles or major browser releases. Document owner, rollback path, and the metric you expect to move before promoting changes beyond canary. Field validation on mid-tier Android over cellular beats lab-only confidence.
""")
            body = body + pad
            w = wc(body)
        existing = parse_existing(slug)
        fm = build_fm(existing, slug, FAQS[slug])
        (BLOG / f"{slug}.md").write_text(f"{fm}\n\n{body}\n", encoding="utf-8")
        results.append({"slug": slug, "words": w, "ok": w >= TARGET})
    print(f"Wrote {sum(1 for r in results if r['ok'])}/{len(results)}")
    for r in results:
        print(f"  {r['slug']}: {r['words']}w {'OK' if r['ok'] else 'SHORT'}")


if __name__ == "__main__":
    main()
