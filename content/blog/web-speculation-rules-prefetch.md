---
title: "Instant Navigation with Speculation Rules"
slug: "web-speculation-rules-prefetch"
description: "Speed up page navigation with the Speculation Rules API: prefetch, prerender, rule matching, eagerness levels, and building instant-feeling multi-page experiences."
datePublished: "2026-05-17"
dateModified: "2026-05-17"
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

## Measuring success in production

Deploy changes behind feature flags when possible so you can compare metrics between control and treatment groups. Use Real User Monitoring to capture performance data from actual devices and network conditions — lab tools alone miss the long tail of user experiences. Set up alerts for regressions: a 10% LCP increase week-over-week warrants investigation before it hits CrUX.

Document your baseline metrics before making changes. Performance work without measurement is guesswork. Share results with the team — concrete numbers ("LCP improved 800ms on mobile") build support for continued investment in web performance and reliability.

Review changes quarterly. Browser updates, new API support, and traffic pattern shifts can obsolete previous optimizations or create new opportunities. What worked in 2024 may not be the best approach in 2026.

## Common production mistakes

Teams get speculation rules prefetch wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of speculation rules prefetch fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When speculation rules prefetch misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [MDN Speculation Rules API](https://developer.mozilla.org/en-US/docs/Web/API/Speculation_Rules_API)
- [web.dev speculation rules](https://web.dev/articles/speculation-rules)
- [Chrome Speculation Rules guide](https://developer.chrome.com/docs/web-platform/prerender-pages)
- [Speculation Rules spec](https://html.spec.whatwg.org/multipage/speculative-loading.html)
- [Can I use Speculation Rules](https://caniuse.com/mdn-html_elements_script_type_speculationrules)
