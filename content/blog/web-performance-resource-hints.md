---
title: "Resource Hints: preload and prefetch"
slug: "web-performance-resource-hints"
description: "Use preload, prefetch, preconnect, and dns-prefetch to optimize page load: when to use each hint, priority control, and common mistakes."
datePublished: "2026-05-13"
dateModified: "2026-07-17"
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

## Operational checklist (1)

Before promoting Web Performance Resource Hints changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (2)

Re-baseline Web Performance Resource Hints after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (3)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Web Performance Resource Hints touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (4)

Before promoting Web Performance Resource Hints changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (5)

Re-baseline Web Performance Resource Hints after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (6)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Web Performance Resource Hints touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Incident patterns around web performance resource hints

Most incidents involving web performance resource hints start as a silent drift: a secondary path skips the control, a retry amplifies load, or a config default from a tutorial ships to production. Write the failure story before the happy path.

| Check | Expected for web performance resource hints |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 1: inject the failure mode you fear for web performance resource hints in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Invariants to enforce for web performance resource hints

Name three invariants that must hold after every deploy of web performance resource hints. Encode at least one in an automated test that fails when the invariant is disabled. Reviewers should reject PRs that only cover the primary UI path.

Concrete probe 2: inject the failure mode you fear for web performance resource hints in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Telemetry and ownership for web performance resource hints

Pair a leading operational signal with a lagging user or risk outcome. Page on burn related to web performance resource hints, not vanity counters. Keep a named owner and a dashboard link in the service catalog entry.

| Check | Expected for web performance resource hints |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 3: inject the failure mode you fear for web performance resource hints in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Rollout sequence for web performance resource hints

Prefer flags, weighted routes, or dual-running configs. Rehearse rollback once in staging. The on-call note for web performance resource hints should include the revert command and the expected user-visible effect within five minutes.

Concrete probe 4: inject the failure mode you fear for web performance resource hints in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Cross-team contracts for web performance resource hints

Document producers, consumers, timeouts, and idempotency keys. Silent schema or policy changes are how web performance resource hints breaks without a clear owner in the incident channel.

| Check | Expected for web performance resource hints |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 5: inject the failure mode you fear for web performance resource hints in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Capacity and cost notes for web performance resource hints

Estimate QPS, payload size, cardinality, and downstream saturation. Functionally correct web performance resource hints changes still cause outages through pool exhaustion, crawl waste, or CPU amplification.

Concrete probe 6: inject the failure mode you fear for web performance resource hints in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Reviewer checklist for web performance resource hints

Ask what happens when the dependency is slow, when authz is skipped on batch jobs, and when clients retry. Those three questions catch most web performance resource hints regressions before production.

| Check | Expected for web performance resource hints |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 7: inject the failure mode you fear for web performance resource hints in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.
