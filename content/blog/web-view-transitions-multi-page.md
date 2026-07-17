---
title: "Multi-Page View Transitions"
slug: "web-view-transitions-multi-page"
description: "Animate page navigations with the View Transitions API across multi-page apps: cross-document transitions, CSS animations, and progressive enhancement."
datePublished: "2026-05-19"
dateModified: "2026-07-17"
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

## Resources

- [MDN: View Transitions API](https://developer.mozilla.org/en-US/docs/Web/API/View_Transitions_API)
- [web.dev: Cross-document view transitions](https://web.dev/articles/view-transitions)
- [Chrome: View Transitions for MPA](https://developer.chrome.com/docs/web-platform/view-transitions/)
- [Can I use View Transitions](https://caniuse.com/view-transitions)
- [View Transition API spec](https://drafts.csswg.org/css-view-transitions-1/)

## Operational checklist (1)

Before promoting Web View Transitions Multi Page changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (2)

Re-baseline Web View Transitions Multi Page after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (3)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Web View Transitions Multi Page touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (4)

Before promoting Web View Transitions Multi Page changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (5)

Re-baseline Web View Transitions Multi Page after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (6)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Web View Transitions Multi Page touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (7)

Before promoting Web View Transitions Multi Page changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Invariants to enforce for web view transitions multi page

Name three invariants that must hold after every deploy of web view transitions multi page. Encode at least one in an automated test that fails when the invariant is disabled. Reviewers should reject PRs that only cover the primary UI path.

| Check | Expected for web view transitions multi page |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 1: inject the failure mode you fear for web view transitions multi page in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Telemetry and ownership for web view transitions multi page

Pair a leading operational signal with a lagging user or risk outcome. Page on burn related to web view transitions multi page, not vanity counters. Keep a named owner and a dashboard link in the service catalog entry.

Concrete probe 2: inject the failure mode you fear for web view transitions multi page in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Rollout sequence for web view transitions multi page

Prefer flags, weighted routes, or dual-running configs. Rehearse rollback once in staging. The on-call note for web view transitions multi page should include the revert command and the expected user-visible effect within five minutes.

| Check | Expected for web view transitions multi page |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 3: inject the failure mode you fear for web view transitions multi page in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Cross-team contracts for web view transitions multi page

Document producers, consumers, timeouts, and idempotency keys. Silent schema or policy changes are how web view transitions multi page breaks without a clear owner in the incident channel.

Concrete probe 4: inject the failure mode you fear for web view transitions multi page in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Capacity and cost notes for web view transitions multi page

Estimate QPS, payload size, cardinality, and downstream saturation. Functionally correct web view transitions multi page changes still cause outages through pool exhaustion, crawl waste, or CPU amplification.

| Check | Expected for web view transitions multi page |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 5: inject the failure mode you fear for web view transitions multi page in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Reviewer checklist for web view transitions multi page

Ask what happens when the dependency is slow, when authz is skipped on batch jobs, and when clients retry. Those three questions catch most web view transitions multi page regressions before production.

Concrete probe 6: inject the failure mode you fear for web view transitions multi page in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Incident patterns around web view transitions multi page

Most incidents involving web view transitions multi page start as a silent drift: a secondary path skips the control, a retry amplifies load, or a config default from a tutorial ships to production. Write the failure story before the happy path.

| Check | Expected for web view transitions multi page |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 7: inject the failure mode you fear for web view transitions multi page in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.
