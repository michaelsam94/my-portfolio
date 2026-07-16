---
title: "Optimizing Core Web Vitals"
slug: "web-performance-core-web-vitals"
description: "Improve LCP, INP, and CLS with targeted Core Web Vitals optimization: measurement, field data, common bottlenecks, and a prioritized fix checklist."
datePublished: "2026-05-08"
dateModified: "2026-05-08"
tags: ["Web", "Performance", "Core Web Vitals", "Frontend"]
keywords: "Core Web Vitals, LCP, INP, CLS, web performance, CrUX, PageSpeed Insights, field data"
faq:
  - q: "What are the three Core Web Vitals metrics?"
    a: "Largest Contentful Paint (LCP) measures loading — how long until the largest visible element renders. Interaction to Next Paint (INP) measures responsiveness — latency between user input and the next visual update. Cumulative Layout Shift (CLS) measures visual stability — how much unexpected layout movement occurs during the page lifecycle. Google uses these as ranking signals."
  - q: "Should I optimize using lab data or field data?"
    a: "Prioritize field data from real users via Chrome User Experience Report (CrUX) or your RUM provider. Lab data from Lighthouse runs in controlled conditions and may not reflect real device and network diversity. Use lab data for debugging specific issues; use field data to measure whether fixes help actual users. A page can pass Lighthouse and fail CrUX."
  - q: "What are the threshold values for passing Core Web Vitals?"
    a: "At the 75th percentile of page loads: LCP under 2.5 seconds (good), INP under 200 milliseconds (good), CLS under 0.1 (good). Values between good and poor thresholds need improvement. Google Search Console reports pass/fail at the URL group level based on 28-day CrUX aggregation."
---

Search Console flagged 40% of our product pages as "Needs Improvement" on LCP. The hero image loaded from a third-party CDN with no priority hint, the web font blocked rendering for 800ms, and a cookie banner injected above the fold pushed content down after paint. Three targeted fixes — preload, font-display swap, and reserved banner space — moved 85% of URLs to "Good" within two weeks.

## The three metrics

| Metric | Measures | Good | Poor |
|---|---|---|---|
| LCP | Loading speed | ≤ 2.5s | > 4.0s |
| INP | Interactivity | ≤ 200ms | > 500ms |
| CLS | Visual stability | ≤ 0.1 | > 0.25 |

Each metric captures a distinct user experience dimension. Optimizing one doesn't automatically fix the others.

## Measuring field data

**CrUX via PageSpeed Insights:**

```
https://pagespeed.web.dev/analysis?url=https://yoursite.com
```

**Search Console → Experience → Core Web Vitals** shows URL groups by status.

**Real User Monitoring (RUM):**

```javascript
import { onLCP, onINP, onCLS } from 'web-vitals';

function sendToAnalytics({ name, value, rating }) {
  analytics.track('web_vital', { metric: name, value, rating });
}

onLCP(sendToAnalytics);
onINP(sendToAnalytics);
onCLS(sendToAnalytics);
```

Deploy RUM to catch regressions before CrUX reflects them (28-day lag).

## Fixing LCP

Common LCP elements: hero images, heading text, video posters.

**Preload the LCP resource:**

```html
<link rel="preload" as="image" href="/hero.webp"
      imagesrcset="/hero-800.webp 800w, /hero-1200.webp 1200w"
      imagesizes="100vw" />
```

**Eliminate render-blocking resources:**

```html
<!-- Defer non-critical CSS -->
<link rel="stylesheet" href="/styles.css" media="print" onload="this.media='all'" />

<!-- Async/defer scripts -->
<script src="/analytics.js" defer></script>
```

**Optimize the LCP element directly:**

- Serve images in AVIF/WebP with responsive srcset
- Inline critical CSS for above-the-fold content
- Use a CDN with HTTP/2 or HTTP/3
- Reduce server response time (TTFB) — LCP can't start until HTML arrives

## Fixing INP

INP replaced First Input Delay (FID) in 2024. It measures all interactions, not just the first.

**Break up long tasks:**

```javascript
// Bad: blocks main thread for 200ms
processLargeDataset(data);

// Good: yield to browser between chunks
async function processInChunks(data, chunkSize = 100) {
  for (let i = 0; i < data.length; i += chunkSize) {
    processChunk(data.slice(i, i + chunkSize));
    await new Promise(r => setTimeout(r, 0));
  }
}
```

**Reduce JavaScript execution:**

- Code-split and lazy-load non-critical JS
- Defer third-party scripts (chat widgets, analytics)
- Use web workers for heavy computation

**Optimize event handlers:**

```javascript
// Debounce expensive handlers
searchInput.addEventListener('input', debounce(handleSearch, 150));
```

## Fixing CLS

Layout shifts happen when elements load or resize without reserved space.

**Size images and embeds:**

```html
<img src="/photo.webp" width="800" height="600" alt="Product" />
```

**Reserve space for dynamic content:**

```css
.ad-slot {
  min-height: 250px; /* matches ad unit size */
}

.cookie-banner {
  height: 60px; /* fixed height, no content push */
}
```

**Avoid inserting content above existing content:**

- Don't inject banners or notifications above the viewport fold after load
- Use `font-display: swap` with size-adjust fallback fonts
- Load web fonts with preload to reduce FOIT/FOUT duration

## Prioritized fix checklist

1. **Measure field data** — identify worst-performing URL groups
2. **Fix TTFB** — server caching, CDN, edge rendering
3. **Preload LCP image** — single highest-impact LCP fix
4. **Eliminate layout shifts** — explicit dimensions on media and ad slots
5. **Reduce JS payload** — code splitting, defer third parties
6. **Break up long tasks** — improve INP on interactive pages
7. **Monitor continuously** — RUM alerts on metric regressions

## Attribution debugging

The web-vitals library reports element attribution for LCP and INP:

```javascript
onINP((metric) => {
  const { interactionTarget, interactionType } = metric.attribution;
  console.log(`Slow ${interactionType} on`, interactionTarget);
});
```

Ship attribution to your analytics platform to prioritize fixes by impact — which pages, which elements, which interaction types hurt most users.

## CrUX vs. Lighthouse gaps

A page scoring 95 in Lighthouse can fail CrUX if real users hit it on slow devices, with extensions installed, or from distant geographies. Always validate fixes against field data after deployment — CrUX updates on a 28-day rolling window.

## Measuring success in production

Deploy changes behind feature flags when possible so you can compare metrics between control and treatment groups. Use Real User Monitoring to capture performance data from actual devices and network conditions — lab tools alone miss the long tail of user experiences. Set up alerts for regressions: a 10% LCP increase week-over-week warrants investigation before it hits CrUX.

Document your baseline metrics before making changes. Performance work without measurement is guesswork. Share results with the team — concrete numbers ("LCP improved 800ms on mobile") build support for continued investment in web performance and reliability.

Review changes quarterly. Browser updates, new API support, and traffic pattern shifts can obsolete previous optimizations or create new opportunities. What worked in 2024 may not be the best approach in 2026.

## Additional production considerations

Teams often underestimate the maintenance cost of performance optimizations. Automate what you can: CI bundle budgets, Lighthouse CI on PRs, and RUM dashboards that alert on regressions. Manual audits don't scale past a handful of pages.

Security and performance intersect more than teams expect. Third-party scripts that hurt INP also expand your attack surface. Self-hosting fonts and critical assets reduces both latency and supply-chain risk. Review every external dependency quarterly — remove what you no longer need.

Accessibility and performance share goals: semantic HTML helps screen readers and gives the browser better rendering hints. Native elements like dialog, popover, and details reduce JavaScript while improving accessibility. Prefer platform features over custom implementations when they meet your requirements.

Mobile users dominate traffic for most sites. Test on real mid-tier Android hardware, not just desktop Chrome. Simulated throttling in DevTools approximates network conditions but not CPU constraints. A fix that helps desktop may be invisible on mobile if the bottleneck is JavaScript execution, not network.

Collaborate with backend teams on TTFB and API response times. Frontend optimizations can't fix a 2-second server response. Set SLAs for API endpoints that feed critical pages and measure them in the same RUM pipeline as Core Web Vitals.

## Resources

- [web.dev Core Web Vitals](https://web.dev/articles/vitals)
- [Chrome User Experience Report](https://developer.chrome.com/docs/crux)
- [web-vitals library](https://github.com/GoogleChrome/web-vitals)
- [Search Console Core Web Vitals report](https://support.google.com/webmasters/answer/9205520)
- [INP optimization guide](https://web.dev/articles/optimize-inp)
