---
title: "Improving Largest Contentful Paint"
slug: "web-performance-lcp-optimization"
description: "Speed up Largest Contentful Paint: identify the LCP element, preload critical resources, optimize TTFB, and fix the most common LCP bottlenecks."
datePublished: "2026-05-12"
dateModified: "2026-05-12"
tags: ["Web", "Performance", "Core Web Vitals", "Frontend"]
keywords: "LCP, Largest Contentful Paint, preload, TTFB, hero image, render blocking, Core Web Vitals"
faq:
  - q: "What elements can be the LCP element?"
    a: "The LCP element is the largest visible content element in the viewport during page load. It's usually a hero image, a large heading block, a video poster, or a background image loaded via CSS. It excludes content below the fold, iframes, and SVG images. The LCP element can change as content loads — the metric reports the final largest element."
  - q: "Why does preloading the LCP image help so much?"
    a: "Without preload, the browser must download HTML, parse it, discover the CSS, parse CSS, discover the image URL, then start downloading the image. Preload tells the browser to fetch the image immediately during HTML parsing, parallel with CSS and JavaScript. This can shave 500ms to 2 seconds off LCP on image-heavy pages."
  - q: "How does server response time (TTFB) affect LCP?"
    a: "LCP cannot begin until the browser receives HTML. TTFB is the time from request to first byte of the response. If TTFB is 800ms, every subsequent optimization starts 800ms late. LCP equals TTFB plus resource load time plus render time. Fix TTFB first with caching, CDN edge delivery, and server-side rendering optimization."
---

The product page LCP was 4.8 seconds. The LCP element was a hero image — but it wasn't in the HTML. JavaScript fetched product data, created an img element, and set the src three seconds after page load. Moving the image URL into the server-rendered HTML with a preload hint and fetchpriority="high" brought LCP to 1.6 seconds.

## Identifying the LCP element

Chrome DevTools → Performance → record page load → look for the "LCP" marker. Or use the Console:

```javascript
new PerformanceObserver((list) => {
  const entries = list.getEntries();
  const last = entries[entries.length - 1];
  console.log('LCP element:', last.element);
  console.log('LCP time:', last.startTime, 'ms');
}).observe({ type: 'largest-contentful-paint', buffered: true });
```

Know your LCP element before optimizing. Different elements need different fixes.

## Preload the LCP resource

For image LCP:

```html
<head>
  <link rel="preload" as="image" href="/hero-1200.avif"
        imagesrcset="/hero-800.avif 800w, /hero-1200.avif 1200w"
        imagesizes="100vw" fetchpriority="high" />
</head>
<body>
  <img src="/hero-1200.avif" srcset="/hero-800.avif 800w, /hero-1200.avif 1200w"
       sizes="100vw" width="1200" height="675" alt="Hero" fetchpriority="high" />
</body>
```

For text LCP (large heading), preload the web font with `crossorigin`.

## Reduce TTFB

LCP starts when HTML arrives. Target TTFB under 800ms:

| Strategy | Impact |
|---|---|
| CDN edge caching | Eliminates origin round-trip |
| Full-page cache | Serves HTML from edge |
| SSR optimization | Reduce render time |
| Database query optimization | Faster dynamic pages |

Measure TTFB in DevTools Network tab — the green "Waiting" segment of the HTML request.

## Eliminate render-blocking resources

```html
<link rel="stylesheet" href="/styles.css" media="print" onload="this.media='all'" />
<script src="/app.js" defer></script>
```

Render-blocking CSS and synchronous JavaScript delay LCP because the browser can't paint until they're processed.

## Optimize the LCP image itself

- Format: AVIF or WebP (30-50% smaller than JPEG)
- Size: responsive srcset — don't send 1200px image to mobile
- Compression: tune quality for visual acceptability
- CDN: serve from edge closest to user
- Dimensions: set explicit width and height to prevent layout recalculation

## Avoid common LCP anti-patterns

**Client-rendered LCP element:** Server-render the LCP element in HTML. Hydrate after.

**Lazy-loaded LCP image:** Never lazy-load above-the-fold content. Use `fetchpriority="high"` instead.

**CSS background-image as LCP:** Background images loaded via CSS are discovered late. Use `<img>` tags for LCP candidates.

**Third-party widgets competing for bandwidth:** Defer chat widgets, analytics, and A/B testing scripts that compete with the LCP resource for network priority.

## LCP optimization priority

1. Fix TTFB — caching, CDN, server optimization
2. Server-render the LCP element — no client-side creation
3. Preload the LCP resource — image or font
4. Use modern image formats — AVIF/WebP with srcset
5. Eliminate render-blocking CSS/JS — inline critical, defer rest
6. Set fetchpriority="high" on the LCP img element

## Soft navigations and SPAs

In SPAs, route changes don't trigger traditional LCP. Use PerformanceObserver with `type: 'largest-contentful-paint'` and reset on navigation. Consider the Element Timing API for custom LCP candidates in app shells.

## Resource load delay breakdown

LCP element timing splits into: time to first byte, resource load delay (discovery), resource load duration, and element render delay. Use the LCP attribution API to see which subpart dominates before guessing at fixes.

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

## Debugging checklist

When something doesn't work as documented, verify browser support with Can I use before assuming a polyfill bug. Check the Network tab for failed resource loads, incorrect MIME types, and missing CORS headers. Use the Console for CSP violations and Trusted Types errors that silently block operations.

Compare behavior in incognito mode to rule out extension interference. Test with cache disabled during development but validate with realistic caching in staging. Read the specification for edge cases the tutorial skipped — MDN examples cover happy paths, not every boundary condition.

If performance regresses after deployment, roll back first and investigate second. Keep a changelog of performance-related changes linked to metric dashboards. Future you will need to know why that preload tag exists before removing it during a refactor.

## Resources

- [web.dev: Optimize LCP](https://web.dev/articles/optimize-lcp)
- [web.dev: LCP metric definition](https://web.dev/articles/lcp)
- [fetchpriority attribute (MDN)](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/img#fetchpriority)
- [Preload responsive images](https://web.dev/articles/preload-responsive-images)
- [CrUX LCP dashboard](https://developer.chrome.com/docs/crux)
