---
title: "Multi-Page View Transitions"
slug: "web-view-transitions-multi-page"
description: "Animate page navigations with the View Transitions API across multi-page apps: cross-document transitions, CSS animations, and progressive enhancement."
datePublished: "2026-05-19"
dateModified: "2026-05-19"
tags: ["Web", "CSS", "Animation", "Frontend"]
keywords: "View Transitions API, cross-document transitions, page transition, MPA, navigation animation, view-transition"
faq:
  - q: "Do View Transitions work in multi-page apps without a JavaScript framework?"
    a: "Yes. Cross-document view transitions (Chrome 126+) animate navigations between separate HTML pages without any JavaScript framework. Opt in with a CSS @view-transition rule. The browser captures screenshots of the old and new pages and animates between them automatically. This brings SPA-like transitions to traditional server-rendered sites."
  - q: "How do cross-document transitions differ from same-document transitions?"
    a: "Same-document transitions (document.startViewTransition) work within a single page — toggling tabs, updating content via JavaScript. Cross-document transitions work across page navigations — clicking a link loads a new HTML document with an animated transition. Same-document requires JavaScript to call the API. Cross-document requires only CSS opt-in on both pages."
  - q: "What happens if the browser doesn't support View Transitions?"
    a: "The navigation works normally — instant page swap with no animation. View Transitions are purely progressive enhancement. No polyfill exists for cross-document transitions because they require browser-level navigation control. Same-document transitions can check for API support before calling startViewTransition."
---

Our documentation site was a multi-page app served by a static generator. Every link click was an abrupt white flash. We added `@view-transition { navigation: auto; }` to the global CSS — two lines — and page navigations cross-faded smoothly. No JavaScript router, no framework migration, no hydration. The browser handled everything.

## Cross-document transitions

Enable on every page:

```css
@view-transition {
  navigation: auto;
}
```

That's the entire setup for basic cross-fade transitions between pages. The browser captures the old page, loads the new page, captures it, and animates between the snapshots.

Customize the animation:

```css
@view-transition {
  navigation: auto;
}

::view-transition-old(root) {
  animation: fade-out 0.25s ease-out;
}

::view-transition-new(root) {
  animation: fade-in 0.25s ease-in;
}

@keyframes fade-out {
  to { opacity: 0; }
}

@keyframes fade-in {
  from { opacity: 0; }
}
```

## Same-document transitions

For SPA-style updates within one page:

```javascript
function updateContent(newHTML) {
  if (!document.startViewTransition) {
    container.innerHTML = newHTML;
    return;
  }

  document.startViewTransition(() => {
    container.innerHTML = newHTML;
  });
}
```

The callback runs the DOM update. The browser animates between old and new states.

## Named transitions for specific elements

Assign view-transition-name to animate specific elements independently:

```css
.hero-image {
  view-transition-name: hero;
}

.page-title {
  view-transition-name: title;
}
```

When both the old and new page have elements with the same `view-transition-name`, the browser morphs between them — the hero image slides from its old position to its new position.

```css
::view-transition-old(hero) {
  animation: slide-out 0.3s ease-in;
}

::view-transition-new(hero) {
  animation: slide-in 0.3s ease-out;
}
```

## Shared element transitions

Product listing to detail page:

```html
<!-- listing.html -->
<img src="/product-1.jpg" style="view-transition-name: product-1" alt="Widget" />

<!-- detail.html -->
<img src="/product-1.jpg" style="view-transition-name: product-1" alt="Widget" />
```

The image morphs from its thumbnail position on the listing page to its full-size position on the detail page.

## Transition types

Specify animation direction with `transition-type`:

```css
@view-transition {
  navigation: auto;
  types: slide-forward;
}

/* On the page being navigated away from */
:root:active-view-transition-type(backwards) {
  /* reverse animation */
}
```

Set types via navigation API or meta tag for forward/back navigation patterns.

## Respecting user preferences

```css
@media (prefers-reduced-motion: reduce) {
  @view-transition {
    navigation: none;
  }
}
```

Disable transitions for users who prefer reduced motion.

## Performance considerations

View transitions capture page snapshots — they add a small overhead to navigation:

- Capture old page: ~16ms
- Load new page: normal navigation time
- Capture new page: ~16ms
- Animate: GPU-composited, no layout cost

Keep transition durations under 300ms. Long animations delay interactivity on the new page.

## MPA vs. SPA transitions

| Approach | Setup | Works without JS | SEO |
|---|---|---|---|
| Cross-document (MPA) | CSS only | Yes | Full |
| Same-document (SPA) | JavaScript API | No | Depends on SSR |
| Framework (Next.js) | Built-in support | No | Full with SSR |

Cross-document transitions are the lowest-effort path to animated navigation for server-rendered sites.

## Transition naming across routes

Use consistent `view-transition-name` values on shared elements (header logo, product image) across pages. The browser morphs matching names during cross-document transitions. Names must be unique per page — duplicate names on the same page cause transitions to break.

## Fallback for unsupported browsers

Navigation works without transitions. No polyfill needed. Optionally detect support:

```javascript
if (!('startViewTransition' in document)) {
  // instant navigation — no special handling needed
}
```

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

## Common production mistakes

Teams get view transitions multi page wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of view transitions multi page fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [MDN: View Transitions API](https://developer.mozilla.org/en-US/docs/Web/API/View_Transitions_API)
- [web.dev: Cross-document view transitions](https://web.dev/articles/view-transitions)
- [Chrome: View Transitions for MPA](https://developer.chrome.com/docs/web-platform/view-transitions/)
- [Can I use View Transitions](https://caniuse.com/view-transitions)
- [View Transition API spec](https://drafts.csswg.org/css-view-transitions-1/)
