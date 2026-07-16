---
title: "The View Transitions API for Smooth SPAs"
slug: "view-transitions-api"
description: "The View Transitions API explained: animate DOM and page changes with startViewTransition, cross-document transitions, and shared-element morphs — without a heavy animation library."
datePublished: "2026-02-08"
dateModified: "2026-02-08"
tags: ["Web", "Frontend", "Animation", "UX"]
keywords: "View Transitions API, cross-document transitions, SPA animations, page transitions web, smooth navigation"
faq:
  - q: "What is the View Transitions API?"
    a: "The View Transitions API is a browser API that animates between two states of the DOM with a single call to document.startViewTransition(). The browser snapshots the old state, lets you update the DOM, snapshots the new state, and cross-fades or morphs between them automatically. It handles both same-document (SPA) transitions and cross-document (multi-page) navigations, giving native-app-like page transitions without a JavaScript animation framework."
  - q: "How do shared element transitions work?"
    a: "You assign a matching view-transition-name to an element in both the old and new states. The browser recognizes the shared identity and animates that element from its old position and size to its new one — for example, a thumbnail growing into a full image on a detail page. Everything with a matching name morphs, while the rest of the page cross-fades by default."
  - q: "Is the View Transitions API supported across browsers?"
    a: "Same-document view transitions are widely supported in Chromium-based browsers and have been rolling out to Safari and Firefox, while cross-document transitions are newer. Because the API is designed to degrade gracefully — an unsupported browser simply performs the DOM update with no animation — you can adopt it as progressive enhancement without breaking anything."
---

For years, animating a page transition on the web meant one of two bad options: hand-roll a fragile system that clones nodes, measures positions, and juggles CSS, or pull in a heavyweight animation library and accept the bundle cost. The View Transitions API replaces both. You call `document.startViewTransition()`, update the DOM inside the callback, and the browser handles snapshotting the before and after states and animating between them. The result is the kind of smooth, native-feeling transition — cross-fades, shared-element morphs, slide-ins — that used to be the exclusive domain of native apps.

I've shipped enough janky manual page transitions to genuinely enjoy this API. It moves the hard parts — measuring layout, coordinating two states, cleaning up — into the browser, and it fails safe: where it's unsupported, you just get an instant update.

## The one function that does the work

The API's surface is deceptively small. You give the browser a callback that mutates the DOM; it does the rest:

```javascript
function updateView(newContent) {
  if (!document.startViewTransition) {
    applyDomUpdate(newContent); // graceful fallback: no animation
    return;
  }
  document.startViewTransition(() => {
    applyDomUpdate(newContent); // your normal DOM update
  });
}
```

Under the hood the browser does four things: captures a snapshot of the current page, runs your callback to update the DOM, captures the new state, then animates from old to new. By default that animation is a smooth cross-fade of the whole page. The feature-detection guard (`if (!document.startViewTransition)`) is what makes this safe to ship today — unsupported browsers take the branch that just updates instantly.

## Customizing with CSS pseudo-elements

The animation is driven entirely by CSS, through a tree of pseudo-elements the browser generates during the transition. The root cross-fade lives on `::view-transition-old(root)` and `::view-transition-new(root)`, and you style them like any animation:

```css
::view-transition-old(root) {
  animation: 200ms ease-out both fade-out;
}
::view-transition-new(root) {
  animation: 300ms ease-in both slide-from-right;
}

@keyframes slide-from-right {
  from { transform: translateX(30px); opacity: 0; }
  to   { transform: translateX(0);    opacity: 1; }
}
```

This is the part I appreciate as an engineer: the *behavior* is one JavaScript call, and the *look* is plain CSS you can tweak, theme, and reason about with normal tooling. There's no imperative animation timeline to babysit.

## Shared-element transitions, the real magic

Cross-fades are nice; shared-element morphs are what make people say "wait, that's the web?" You tag an element with a `view-transition-name`, and if an element with the same name exists in both the old and new states, the browser animates it from its old geometry to its new geometry.

```css
.thumbnail {
  view-transition-name: hero-image;
}
/* On the detail page, the large image also uses: */
.hero {
  view-transition-name: hero-image;
}
```

Click a thumbnail in a grid, navigate to the detail view, and the image visibly grows and slides into its new position while the rest of the page cross-fades around it. You wrote zero animation code for that. The one rule to internalize: a given `view-transition-name` must be *unique* on the page at any moment — two elements sharing the same name simultaneously breaks the transition. For lists, that usually means setting the name dynamically on just the item being interacted with.

## Same-document versus cross-document

There are two flavors, and the distinction matters for architecture.

| Type | Trigger | Best for |
| --- | --- | --- |
| Same-document | `startViewTransition()` after a client-side route change | SPAs and framework routers |
| Cross-document | Automatic, opt-in via CSS `@view-transition` | Traditional multi-page sites |

Same-document is the SPA case: your router updates the DOM inside the transition callback. Cross-document is the newer, quietly revolutionary one — you opt in with a single CSS rule and get animated transitions between *actual separate HTML pages*, no SPA required:

```css
@view-transition {
  navigation: auto;
}
```

That means a plain server-rendered site, or an [islands-architecture setup with Astro](https://blog.michaelsam94.com/islands-architecture-astro/), can have polished page transitions without adopting a client-side router at all. For me that's the headline: the API erases one of the last real UX advantages SPAs held over multi-page sites.

## Framework and PWA integration

Most routers now expose hooks for this. Astro ships a `<ClientRouter />` that wraps navigations in view transitions; React and Vue router integrations wrap route changes in `startViewTransition`. The pattern is always the same — the framework calls the API around its DOM update, and you supply the CSS. When you're building an installable, app-like experience, view transitions are one of the cheapest ways to close the perceived-quality gap with native, which is why I treat them as standard kit alongside the rest of a [progressive web app in 2026](https://blog.michaelsam94.com/progressive-web-apps-2026/).

## The honest caveats

It's a great API, but I've hit its edges:

- **Transitions block interaction briefly.** While the animation runs, the page is essentially frozen for that duration. Keep transitions short — I aim for 150–300ms — because a beautiful 600ms transition feels sluggish the tenth time a user triggers it.
- **`view-transition-name` uniqueness bites in lists.** Dynamically assigning and clearing names is the fiddly part; plan for it in list-to-detail flows.
- **Accessibility: respect `prefers-reduced-motion`.** Wrap your animation CSS in a media query and drop to instant or minimal fades for users who ask for less motion. This is not optional.
- **Snapshotting has a cost.** Very large or complex DOM states take time to snapshot. It's rarely a problem, but transitions on enormous pages can feel less crisp than on lean ones.

```css
@media (prefers-reduced-motion: reduce) {
  ::view-transition-group(*),
  ::view-transition-old(*),
  ::view-transition-new(*) {
    animation: none !important;
  }
}
```

## Worth adopting now

Because the API degrades to a plain DOM update when unsupported, there's essentially no downside to layering it on as progressive enhancement — you add delight where it works and lose nothing where it doesn't. Start with a global cross-fade for route changes, add one or two shared-element morphs on your highest-traffic flow (grid-to-detail is the classic), and keep durations tight with reduced-motion handled. That's a couple of hours of work for a genuinely native-feeling result, without a single animation library in your bundle. After years of gluing this together by hand, having it be a browser primitive still feels like a small gift.

## Resources

- [MDN — View Transitions API](https://developer.mozilla.org/en-US/docs/Web/API/View_Transitions_API)
- [Chrome for Developers — Smooth transitions with the View Transition API](https://developer.chrome.com/docs/web-platform/view-transitions)
- [W3C — CSS View Transitions Module Level 1](https://www.w3.org/TR/css-view-transitions-1/)
- [W3C — CSS View Transitions Module Level 2 (cross-document)](https://www.w3.org/TR/css-view-transitions-2/)
- [MDN — prefers-reduced-motion](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion)
