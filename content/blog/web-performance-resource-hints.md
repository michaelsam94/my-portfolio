---
title: "Resource Hints: preload and prefetch"
slug: "web-performance-resource-hints"
description: "Use preload, prefetch, preconnect, and dns-prefetch to optimize page load: when to use each hint, priority control, and common mistakes."
datePublished: "2026-05-13"
dateModified: "2026-05-13"
tags: ["Web", "Performance", "HTML", "Frontend"]
keywords: "preload, prefetch, preconnect, dns-prefetch, resource hints, fetchpriority, link rel"
faq:
  - q: "What is the difference between preload and prefetch?"
    a: "Preload fetches a resource needed for the current page with high priority — the LCP image, critical font, or above-the-fold CSS. Prefetch fetches a resource likely needed for a future navigation with low priority — the next page's JavaScript bundle or HTML document. Preload is for now; prefetch is for later."
  - q: "When should I use preconnect versus dns-prefetch?"
    a: "Preconnect performs DNS lookup, TCP handshake, and TLS negotiation upfront — use it for origins you'll fetch multiple resources from on the current page. dns-prefetch only resolves DNS — use it as a lighter hint for origins that may or may not be needed. Preconnect is strictly better when you know the origin will be used."
  - q: "Can too many resource hints hurt performance?"
    a: "Yes. Each preload competes for bandwidth with other critical resources. Over-preloading dilutes priority and can delay LCP. Limit preloads to two or three critical resources per page. Prefetch is low priority and less harmful, but prefetching resources the user never needs wastes bandwidth on mobile."
---

We added preload for every script and stylesheet on the page — twelve preload tags in the head. LCP got worse. The browser prioritized all twelve resources equally, starving the hero image that actually mattered. Removing nine unnecessary preloads and keeping three targeted ones — hero image, primary font, critical CSS — recovered 600ms on LCP.

## The four resource hints

| Hint | Priority | Purpose |
|---|---|---|
| `preload` | High | Current page, needed soon |
| `prefetch` | Low | Future navigation, maybe needed |
| `preconnect` | — | Establish connection early |
| `dns-prefetch` | — | Resolve DNS early |

## Preload

```html
<link rel="preload" as="image" href="/hero.avif" type="image/avif" fetchpriority="high" />
<link rel="preload" as="font" href="/fonts/inter.woff2" type="font/woff2" crossorigin />
<link rel="modulepreload" href="/app-core.js" />
```

Preload must include the correct `as` value — the browser uses it to set fetch priority and CSP checks.

## Prefetch

```html
<link rel="prefetch" href="/pricing.html" as="document" />
<link rel="prefetch" href="/assets/dashboard-chunk.js" as="script" />
```

Dynamic prefetch on link hover:

```javascript
link.addEventListener('mouseenter', () => {
  const hint = document.createElement('link');
  hint.rel = 'prefetch';
  hint.href = link.href;
  document.head.appendChild(hint);
}, { once: true });
```

## Preconnect and dns-prefetch

```html
<link rel="preconnect" href="https://cdn.example.com" />
<link rel="dns-prefetch" href="https://analytics.example.com" />
```

Use `crossorigin` on preconnect when fetching CORS resources like fonts.

## fetchpriority

```html
<img src="/hero.avif" fetchpriority="high" alt="Hero" />
<img src="/footer-logo.png" fetchpriority="low" alt="Logo" loading="lazy" />
```

Don't set `high` on more than one or two resources.

## Decision guide

Is the resource needed for the CURRENT page?
- LCP element or critical font → preload + fetchpriority="high"
- Not immediately critical → preload (normal priority)
- For a likely NEXT page → prefetch

Is the resource on a different origin?
- Multiple resources from same origin → preconnect
- Maybe one resource → dns-prefetch

## Common mistakes

**Preloading everything.** Each preload competes for bandwidth. Preload only what blocks rendering.

**Preloading lazy-loaded images.** Contradictory signals — pick one.

**Missing crossorigin on font preload.** Font preload silently fails without it.

**Preconnect to unused origins.** Wasted connection setup.

## 103 Early Hints

Some CDNs send 103 Early Hints with Link headers before the full response:

```
Link: </hero.avif>; rel=preload; as=image
```

Browsers start fetching before HTML arrives. Cloudflare and Fastly support this — configure preload hints at the edge for dynamic pages where HTML preload tags aren't practical.

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

## Integration with your stack

Every technique in this guide adapts to your framework and hosting environment. Next.js, Nuxt, Rails, and Django each have conventions for where static assets live, how SSR works, and where to inject resource hints. Map the concepts here to your stack's documentation rather than copying snippets verbatim.

Staging environments should mirror production CDN configuration, HTTP/2 settings, and compression. A fix validated locally over HTTP/1.1 without compression may behave differently behind Cloudflare or Fastly. Deploy performance changes to a canary percentage before full rollout when your platform supports it.

Train the team on these patterns during code review. Performance regressions usually arrive as small PRs — one unoptimized image, one synchronous script, one missing width attribute. Reviewers who recognize LCP and CLS anti-patterns catch issues before they reach production.

## Resources

- [web.dev: Resource hints](https://web.dev/articles/preconnect-and-dns-prefetch)
- [MDN: rel=preload](https://developer.mozilla.org/en-US/docs/Web/HTML/Attributes/rel/preload)
- [MDN: rel=prefetch](https://developer.mozilla.org/en-US/docs/Web/HTML/Attributes/rel/prefetch)
- [fetchpriority (web.dev)](https://web.dev/articles/fetch-priority)
- [Preload responsive images](https://web.dev/articles/preload-responsive-images)
