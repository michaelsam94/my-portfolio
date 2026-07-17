---
title: "404 Page Design for Product Sites"
slug: "web-performance-404-page-product-sites"
description: "404 pages recover lost users — search, popular links, report broken link, and correct HTTP status."
datePublished: "2027-03-10"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "404 page design product, helpful 404 UX, broken link recovery"
faq:
  - q: "Should a 404 page return HTTP 200?"
    a: "Never. Soft 404s with HTTP 200 poison crawl budget and pollute analytics. Return 404 Not Found (or 410 Gone when permanently removed) and make the response body helpful."
  - q: "What belongs on a product site 404?"
    a: "Site search, top categories or docs entry points, support link, and server-side logging of the requested path for redirect rules. Avoid cute copy with no recovery path."
  - q: "How fast should a 404 load?"
    a: "Faster than happy-path pages — users are already frustrated. SSR HTML, minimal JS, skip chat widgets unless support is the primary recovery. Track 404 LCP separately in RUM."
---

Marketing shipped a gorgeous illustrated 404 that returned HTTP 200 — Search Console indexed twelve thousand error URLs and organic traffic dipped for six weeks. A product 404 is not a brand moment alone; it is recovery infrastructure. Return the correct status code, help the user find what they wanted, and measure whether they leave or re-engage.

## HTTP status and SEO fundamentals

Always respond with **404 Not Found** (or **410 Gone** when permanently removed). Soft 404s — pretty pages with 200 OK — poison crawl budget and pollute analytics. Configure your edge or framework explicitly:

```typescript
// Next.js App Router
export default function NotFound() {
  return <NotFoundPage />;
}
// not-found.tsx automatically sets 404 status
```

For static hosts, ensure missing paths hit a real 404 document, not SPA fallback to index.html with client-side routing unless you implement prerendered 404 HTML at the edge.

Log 404 paths server-side with referrer and user agent — aggregate weekly. Spikes from one partner domain mean broken inbound links worth fixing at source, not only on your page.

## Content that actually helps users

Effective product 404 pages include:

- **Site search** pre-focused in the header — user already typed a URL; give them search immediately
- **Top destinations** — docs getting started, pricing, support, status page (not random blog posts)
- **Report broken link** form capturing attempted URL and optional email for follow-up
- **Clear language** — "This page moved or never existed" beats cute copy without navigation

Avoid auto-redirecting to homepage — users lose context and bounce confused. Optional smart redirect only when you have high-confidence URL mapping from migrations (`/old-path` → `/new-path` with 301 at server, not JavaScript).

## Performance budget for error routes

404s should load **faster** than happy-path pages — users are already frustrated. Inline critical CSS for the error layout; skip heavy hero video and third-party widgets. Do not load chat widget on 404 unless support is the primary recovery path.

Target LCP under 1.5s on 404 template. Monitor separately in RUM:

```javascript
if (document.body.dataset.pageType === "404") {
  reportMetric("404_lcp", lcpValue, { path: location.pathname });
}
```

Track **404 recovery rate** — users who click search, popular link, or navigate to another page within 60 seconds versus immediate bounce.

## Accessibility on error pages

404 is still a full page — heading hierarchy starts with h1 ("Page not found"), skip link to main content, focus moves to h1 on render for screen reader users. Search input needs `<label>` or `aria-label`. Color contrast on muted illustration text must pass WCAG AA.

Do not rely on illustration alone — always include text explanation. `prefers-reduced-motion` disables animated "lost in space" loops.

## Internationalization and localization

404 copy must translate — `/de/docs/missing` shows German recovery options. hreflang pages that 404 need consistent language in error UI. RTL layouts mirror search and link order.

## Analytics without polluting funnels

Exclude 404 from conversion funnels in analytics config. Segment 404 views by:

- Referrer (external broken link vs internal typo)
- Attempted path patterns (deprecated API docs `/v1/` vs random scans)
- Device class

Alert when 404 rate spikes 3× week-over-week on `/docs/*` — often signals broken release or renamed routes without redirects.

## Migration and redirect discipline

When renaming routes, ship **301 redirects** for six months minimum alongside updated sitemap. Keep redirect map in git:

```yaml
# redirects.yml
- from: /blog/old-slug
  to: /blog/new-slug
  status: 301
```

404 page links to search cannot fix missing redirects — fix server redirects first, polish 404 second.

## Soft 404 detection in monitoring

Synthetic checks hit known-bad URLs expecting 404 status and key string "not found". CI fails if status becomes 200. Google Search Console "Soft 404" report warrants weekly review — often SPA routing misconfiguration.

## Edge and CDN configuration

Cloudflare, Fastly, and similar platforms need explicit 404 page rules — default error page may ignore your React bundle. Serve lightweight static 404 at edge when origin is down to avoid circular error pages.

Cache 404 responses carefully — short TTL (minutes) if some paths flip between valid and invalid during deploys; longer TTL for truly static missing assets.

## Security considerations

404 pages still execute CSP — do not weaken headers on error routes. Reflected path in error message ("You tried /{{path}}") needs HTML escaping to prevent XSS from maliciously crafted URLs logged into page content.

Rate-limit 404 report form — attackers probe paths via your site; do not amplify into email spam to support.

## When to use 410 Gone

Permanently removed content (discontinued product, deleted account portal) should return **410** — signals crawlers to drop faster than 404. Document 410 list in SEO runbook when deprecating major sections.

## Design system integration

404 should use same header, footer, and tokens as product chrome — user knows they are still on your site. Dark mode and theme tokens apply; do not ship unstyled default server page on production domain.

Storybook story for 404 with visual regression — teams forget error pages until rebrand breaks contrast.

A great 404 page combines correct HTTP semantics, fast load, accessible recovery paths, and instrumentation that turns dead ends into product feedback — broken link reports and search queries reveal where navigation and docs fail before support tickets do.

## Framework-specific 404 implementations

**Next.js:** `not-found.tsx` at segment level for localized 404 within docs section while app shell persists. **Remix:** throw `Response` with status 404 from loader. **Static site generators:** prebuild 404.html copied to output root on deploy.

Ensure client-side routers register server 404 fallback — direct URL hit must not return SPA shell with empty content and 200 status.

## A/B testing recovery paths

Test search-first versus popular-links-first layouts — recovery rate differs by audience (developers search docs; consumers click category links). Run experiment two weeks minimum; segment by referrer type.

## Broken link outreach workflow

Weekly export top 100 404 paths with external referrers — email partner webmasters with corrected URLs. Internal broken links become tickets assigned to team owning source page. Reduces repeat 404 without waiting for users to complain.

## Performance checklist summary

| Check | Target |
|-------|--------|
| HTTP status | 404 or 410, never 200 |
| LCP | < 1.5s mobile p75 |
| JS weight | Minimal — no chat widget unless required |
| Search | Labeled input, keyboard accessible |
| Analytics | Excluded from conversion funnels |

Product 404 pages earn their keep when metrics show users recovering instead of bouncing — treat them as product surface area, not design afterthought.

## Campaign link hygiene

Paid traffic landing on 404 is budget burned. UTM-tagged URLs in ad platforms should resolve before spend goes live — automated crawl of active campaigns against production weekly. Email teams need redirect maps before newsletter send; one wrong slug in a million-recipient blast spikes support volume.

Partner co-marketing pages die when SKUs retire — 404 logs reveal which partner domains still link to discontinued paths. Proactive redirect or partner outreach beats hoping users search.

## Personalization without wrong status

Do not personalize 404 content by returning 200 for "we think you meant X." Personalization belongs in the 404 body with correct status. Edge middleware can suggest redirects in HTML while still emitting 404 until user confirms navigation.

## Resources

- [RFC 9110 — 404 Not Found](https://www.rfc-editor.org/rfc/rfc9110.html)
- [Google Search Console — Soft 404](https://developers.google.com/search/docs/crawling-indexing/troubleshoot-crawling-errors)
- [web.dev — Custom 404 pages](https://web.dev/articles/custom-404-page)

## SPA client-router fallback pitfalls

React Router `path="*"` renders NotFound component but server must still return 404 HTML for direct hits. SSR frameworks handle this; client-only SPAs need server config or prerender service — otherwise every unknown URL is soft 404 with 200.

## Logging and PII

Log requested path and referrer — avoid logging full query strings with email tokens from broken magic links. Hash or truncate sensitive query params in 404 logs.

## Multilingual 404 recovery

German user hitting English-only slug should see German recovery UI with link to localized home — detect Accept-Language or cookie locale, not IP geolocation alone.
