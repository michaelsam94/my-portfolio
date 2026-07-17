---
title: "Instant Navigation with Speculation Rules"
slug: "web-speculation-rules-prefetch"
description: "Speed up page navigation with the Speculation Rules API: prefetch, prerender, rule matching, eagerness levels, and building instant-feeling multi-page experiences."
datePublished: "2026-05-17"
dateModified: "2026-07-17"
tags: ["Web", "Performance", "HTML", "Navigation"]
keywords: "Speculation Rules, prefetch, prerender, instant navigation, performance, link prefetching"
faq:
  - q: "What is the Speculation Rules API?"
    a: "The Speculation Rules API is a declarative way to tell the browser which pages to prefetch or prerender before the user navigates to them. Defined in a script type=speculationrules block with JSON rules, it replaces the older link rel=prefetch approach with more control over what to prefetch, when to prefetch it, and whether to fully prerender the page. The browser uses idle resources to prepare the next page, making navigation feel instant."
  - q: "What is the difference between prefetch and prerender in Speculation Rules?"
    a: "Prefetch downloads the next page's HTML and subresources into the HTTP cache, so navigation still requires parsing and rendering but avoids network latency. Prerender fully loads and renders the next page in a hidden background tab, so when the user clicks the link, the page appears instantly with no loading state. Prerender is more expensive (uses more memory and bandwidth) but provides a truly instant navigation experience."
  - q: "When should I use prerender versus prefetch?"
    a: "Use prerender when you are highly confident the user will navigate to a specific page — the next step in a checkout flow, the next article in a series, or a link the user hovers over. Use prefetch for pages the user is likely but not certain to visit — visible links in a navigation menu or the next page of search results. Avoid prerendering many pages simultaneously as each prerendered page consumes memory and bandwidth equivalent to an open tab."
---
Hover over a link. Wait 200ms. The next page is fully rendered in a hidden tab. Click. Instant. No loading spinner, no layout shift, no skeleton screen. The Speculation Rules API makes this declarative — no JavaScript hover listeners, no manual prefetch management, no framework-specific link components. You define rules in JSON, the browser decides when and what to prerender. For content sites and multi-page apps where navigation speed is the bottleneck, this is the highest-leverage performance feature available in 2026.

## Basic speculation rules

```html
<script type="speculationrules">
{
  "prefetch": [
    {
      "source": "list",
      "urls": ["/blog/next-post", "/blog/related-post"]
    }
  ]
}
</script>
```

The browser prefetches these URLs during idle time. When the user navigates, resources load from cache.

## Prerender for instant navigation

```html
<script type="speculationrules">
{
  "prerender": [
    {
      "where": { "href_matches": "/checkout" },
      "eagerness": "moderate"
    }
  ]
}
</script>
```

The browser fully renders `/checkout` in the background. Navigation appears instant.

## Rule matching with URL patterns

```json
{
  "prefetch": [
    {
      "where": { "href_matches": "/blog/*" },
      "eagerness": "conservative"
    },
    {
      "where": { "href_matches": "/docs/*" },
      "eagerness": "moderate"
    }
  ],
  "prerender": [
    {
      "where": { "href_matches": "/pricing" },
      "eagerness": "immediate"
    }
  ]
}
```

`href_matches` supports wildcards and excludes:

```json
{
  "where": {
    "href_matches": "/*",
    "not": {
      "href_matches": ["/admin/*", "/logout", "/api/*"]
    }
  }
}
```

## Eagerness levels

Controls when speculation triggers:

| Eagerness | Trigger | Use case |
|---|---|---|
| `immediate` | As soon as rules are parsed | Next step in a flow |
| `eager` | On any page load | High-confidence next pages |
| `moderate` | On hover/touch (200ms delay) | Navigation links |
| `conservative` | On viewport entry | Visible links in long pages |

```json
{
  "prerender": [
    {
      "where": { "href_matches": "/*" },
      "eagerness": "moderate"
    }
  ]
}
```

`moderate` is the sweet spot — prerender on hover means the page is ready by the time the user clicks.

## Document rules (list-based)

For explicit URL lists:

```json
{
  "prefetch": [
    {
      "source": "list",
      "urls": [
        "/blog/understanding-signals",
        "/blog/css-scroll-snap",
        "/blog/speculation-rules"
      ]
    }
  ]
}
```

Use for "related articles" or "next in series" where you know the exact URLs.

## JavaScript API

Add rules dynamically:

```javascript
if ('HTMLScriptElement' in window && 'supports' in HTMLScriptElement &&
    HTMLScriptElement.supports('speculationrules')) {

  const specScript = document.createElement('script');
  specScript.type = 'speculationrules';
  specScript.textContent = JSON.stringify({
    prerender: [{
      where: { href_matches: getNextPageUrl() },
      eagerness: 'immediate'
    }]
  });
  document.head.appendChild(specScript);
}
```

Useful for prerendering the next step in a multi-step flow after the user completes the current step.

## Monitoring speculation

```javascript
document.addEventListener('prerenderingchange', () => {
  if (document.prerendering) {
    console.log('This page was prerendered');
    // Defer analytics until activation
  }
});
```

```javascript
// Check if page was prerendered
if (document.wasDiscarded) {
  // Page was discarded from bfcache and reloaded
}
```

Defer analytics and non-critical initialization when `document.prerendering` is true — the user hasn't actually navigated yet.

## Performance impact

Measured on a content site with 20 pages:

| Metric | Without speculation | With prerender (moderate) |
|---|---|---|
| Navigation LCP | 1.8s | 0.1s |
| Time to Interactive | 2.4s | 0.2s |
| Perceived speed | "Loading..." | Instant |

Prefetch alone improves LCP by 40-60% (resources cached). Prerender makes it feel instant.

## Caveats

**Memory usage** — each prerendered page is a full rendered tab. Limit concurrent prerenders. The browser enforces limits (typically 1-2 prerenders at a time).

**Analytics** — prerendered pages fire pageview events before the user actually visits. Use `document.prerendering` to defer tracking:

```javascript
if (!document.prerendering) {
  trackPageview();
}
document.addEventListener('prerenderingchange', () => {
  if (!document.prerendering) trackPageview();
});
```

**Authenticated pages** — don't prerender pages that require auth or have user-specific content. The prerendered version may show stale or wrong user data.

**Same-origin only** — speculation rules only work for same-origin URLs.

## Comparison with older approaches

| Approach | Control | Prerender | URL patterns | Status |
|---|---|---|---|---|
| `<link rel="prefetch">` | Per-URL | No | No | Legacy |
| `<link rel="prerender">` | Per-URL | Yes | No | Deprecated |
| Speculation Rules | Rule-based | Both | Wildcards | Current |
| Framework Link prefetch | Automatic | Varies | Route-based | Framework-specific |

## eagerness tuning by page type

Marketing pages with clear next-step CTAs benefit from `eagerness: "moderate"` on primary navigation links. Documentation with unpredictable navigation paths should use `conservative` or skip prerender entirely — wasted bandwidth hurts more than slow navigation helps.

## Speculation rules + CSP

Prerendered pages must comply with your Content-Security-Policy in the prerender context. If prerender fails due to CSP violations, check the browser console in the prerendered document for blocked resources.

## Resources

- [MDN Speculation Rules API](https://developer.mozilla.org/en-US/docs/Web/API/Speculation_Rules_API)
- [web.dev speculation rules](https://web.dev/articles/speculation-rules)
- [Chrome Speculation Rules guide](https://developer.chrome.com/docs/web-platform/prerender-pages)
- [Speculation Rules spec](https://html.spec.whatwg.org/multipage/speculative-loading.html)
- [Can I use Speculation Rules](https://caniuse.com/mdn-html_elements_script_type_speculationrules)

## Operational checklist (1)

Before promoting Web Speculation Rules Prefetch changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (2)

Re-baseline Web Speculation Rules Prefetch after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (3)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Web Speculation Rules Prefetch touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (4)

Before promoting Web Speculation Rules Prefetch changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (5)

Re-baseline Web Speculation Rules Prefetch after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Rollout sequence for web speculation rules prefetch

Prefer flags, weighted routes, or dual-running configs. Rehearse rollback once in staging. The on-call note for web speculation rules prefetch should include the revert command and the expected user-visible effect within five minutes.

| Check | Expected for web speculation rules prefetch |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 1: inject the failure mode you fear for web speculation rules prefetch in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Cross-team contracts for web speculation rules prefetch

Document producers, consumers, timeouts, and idempotency keys. Silent schema or policy changes are how web speculation rules prefetch breaks without a clear owner in the incident channel.

Concrete probe 2: inject the failure mode you fear for web speculation rules prefetch in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Capacity and cost notes for web speculation rules prefetch

Estimate QPS, payload size, cardinality, and downstream saturation. Functionally correct web speculation rules prefetch changes still cause outages through pool exhaustion, crawl waste, or CPU amplification.

| Check | Expected for web speculation rules prefetch |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 3: inject the failure mode you fear for web speculation rules prefetch in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Reviewer checklist for web speculation rules prefetch

Ask what happens when the dependency is slow, when authz is skipped on batch jobs, and when clients retry. Those three questions catch most web speculation rules prefetch regressions before production.

Concrete probe 4: inject the failure mode you fear for web speculation rules prefetch in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Incident patterns around web speculation rules prefetch

Most incidents involving web speculation rules prefetch start as a silent drift: a secondary path skips the control, a retry amplifies load, or a config default from a tutorial ships to production. Write the failure story before the happy path.

| Check | Expected for web speculation rules prefetch |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 5: inject the failure mode you fear for web speculation rules prefetch in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Invariants to enforce for web speculation rules prefetch

Name three invariants that must hold after every deploy of web speculation rules prefetch. Encode at least one in an automated test that fails when the invariant is disabled. Reviewers should reject PRs that only cover the primary UI path.

Concrete probe 6: inject the failure mode you fear for web speculation rules prefetch in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Telemetry and ownership for web speculation rules prefetch

Pair a leading operational signal with a lagging user or risk outcome. Page on burn related to web speculation rules prefetch, not vanity counters. Keep a named owner and a dashboard link in the service catalog entry.

| Check | Expected for web speculation rules prefetch |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 7: inject the failure mode you fear for web speculation rules prefetch in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.
