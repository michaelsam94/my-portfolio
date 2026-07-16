---
title: "View Transitions for SPAs"
slug: "css-view-transitions-spa"
description: "Add native cross-document and SPA view transitions with document.startViewTransition, CSS view-transition-name, and React Router integration patterns."
datePublished: "2025-06-05"
dateModified: "2025-06-05"
tags: ["Web", "CSS"]
keywords: "View Transitions API, SPA transitions, startViewTransition, view-transition-name, page transitions CSS"
faq:
  - q: "What is the View Transitions API?"
    a: "The View Transitions API captures screenshots of old and new DOM states and animates between them with compositor-controlled crossfades and morphs. document.startViewTransition(callback) wraps DOM updates; CSS ::view-transition-old and ::view-transition-new pseudo-elements style the animation. Works in SPAs and cross-document navigations in supporting browsers."
  - q: "How do shared element transitions work?"
    a: "Assign matching view-transition-name to elements in old and new views—hero image, product title. The browser morphs between their positions and sizes during transition. Names must be unique per frame; remove or rename after transition completes."
  - q: "Does View Transitions work with React and client routing?"
    a: "Yes—wrap state updates that change routes inside startViewTransition. React 19 experimental ViewTransition component integrates; manual pattern uses flushSync to apply DOM update inside callback. Pair with React Router navigation in useEffect or loader after data ready."
---

SPA route changes swap DOM instantly—functional but visually abrupt. View Transitions API gives browsers a first-class hook: capture old state, mutate, capture new state, animate between snapshots. Shared element transitions morph the clicked thumbnail into the detail hero. The API landed in Chrome; Safari and Firefox followed—time to replace some Framer Motion page fades with less JS.

## Basic SPA transition

```javascript
function navigate(url) {
  if (!document.startViewTransition) {
    updateDOM(url);
    return;
  }
  document.startViewTransition(async () => {
    await updateDOM(url);
  });
}
```

```css
::view-transition-old(root),
::view-transition-new(root) {
  animation-duration: 0.25s;
}

::view-transition-old(root) {
  animation-name: fade-out;
}
::view-transition-new(root) {
  animation-name: fade-in;
}

@keyframes fade-out { to { opacity: 0; } }
@keyframes fade-in { from { opacity: 0; } }
```

Default crossfade on root snapshot.

## Shared element transition

List page:

```html
<img src="a.jpg" style="view-transition-name: product-hero;" />
```

Detail page after navigation:

```html
<img src="a.jpg" style="view-transition-name: product-hero;" />
```

Same `view-transition-name`—browser morphs position/size. Remove name from other elements to avoid conflicts.

```css
::view-transition-group(product-hero) {
  animation-duration: 0.4s;
}
```

## React integration

```jsx
import { flushSync } from 'react-dom';

function navigateWithTransition(setRoute, route) {
  if (!document.startViewTransition) {
    setRoute(route);
    return;
  }
  document.startViewTransition(() => {
    flushSync(() => {
      setRoute(route);
    });
  });
}
```

`flushSync` ensures React commits DOM before new snapshot—critical for correct animation.

React 19 (experimental):

```jsx
import { ViewTransition } from 'react';

<ViewTransition>
  <Page key={route} />
</ViewTransition>
```

## Cross-document (MPA) transitions

Chrome supports `@view-transition` at-rule for multi-page navigations between same-origin documents:

```css
@view-transition {
  navigation: auto;
}
```

Both pages opt in—link clicks animate without SPA architecture. Requires deployment on both sides.

## Accessibility

```css
@media (prefers-reduced-motion: reduce) {
  ::view-transition-group(*),
  ::view-transition-old(*),
  ::view-transition-new(*) {
    animation: none !important;
  }
}
```

Provide instant navigation when reduced motion preferred.

Announce route changes to screen readers independently—view transitions are visual only.

## Performance

Large DOM snapshots cost memory—test on mobile. Prefer animating transform/opacity on named groups over full-page snapshots on heavy pages.

Avoid starting transition before async content loads—wait for images or show skeleton with matching transition name.

## Pitfalls

Duplicate `view-transition-name` values in same view break transition—use dynamic names keyed by id:

```javascript
style={{ viewTransitionName: `item-${product.id}` }}
```

Z-index stacking during transition uses pseudo tree—custom z-index on elements may not apply during animation.

## What the browser actually captures

`startViewTransition` doesn't diff the DOM — it screenshots the old state, lets your callback mutate, screenshots the new state, then crossfades between the two snapshots. Named elements (with matching `view-transition-name`) get individual snapshot groups that morph independently from the root crossfade.

The pseudo-element tree during animation:

```
::view-transition
  ├── ::view-transition-group(root)
  │     ├── ::view-transition-image-pair(root)
  │     │     ├── ::view-transition-old(root)
  │     │     └── ::view-transition-new(root)
  └── ::view-transition-group(hero-image)
        ├── ::view-transition-image-pair(hero-image)
        │     ├── ::view-transition-old(hero-image)
        │     └── ::view-transition-new(hero-image)
```

Style these pseudo-elements to control timing, easing, and which snapshot is visible. Root group handles the page-level crossfade; named groups handle shared element morphs.

## Data loading and transition timing

The most common production bug: starting a transition before async content loads. User clicks product, transition begins, detail page shows skeleton, hero image pops in mid-animation — jarring.

```javascript
async function navigateToProduct(id) {
  const detail = await fetchProduct(id); // load BEFORE transition

  if (!document.startViewTransition) {
    renderDetail(detail);
    return;
  }

  document.startViewTransition(() => {
    flushSync(() => renderDetail(detail));
  });
}
```

Alternatively, use matching `view-transition-name` on skeleton and final hero so the browser morphs placeholder → image. The name must persist across both states.

## Framework-specific patterns

**React Router v6+:**

```jsx
function ProductDetail() {
  const { id } = useParams();
  const [product, setProduct] = useState(null);

  useEffect(() => {
    fetchProduct(id).then(data => {
      if (document.startViewTransition) {
        document.startViewTransition(() => {
          flushSync(() => setProduct(data));
        });
      } else {
        setProduct(data);
      }
    });
  }, [id]);
}
```

**Next.js App Router:** View transitions work with client-side navigation in the app shell. Cross-document transitions between server-rendered pages require the `@view-transition { navigation: auto; }` opt-in on both pages — experimental and Chrome-specific for now.

**Vue / Svelte:** Same pattern — wrap reactive state update in `startViewTransition` with synchronous DOM flush.

## Cross-document transitions in production

MPA cross-document transitions require both origin and destination pages to opt in:

```css
@view-transition {
  navigation: auto;
}
```

Same-origin only. Both pages must include this rule. Useful for documentation sites and marketing pages without SPA architecture. Not yet universal — provide standard navigation as fallback. Test back/forward navigation; bfcache interaction with view transitions varies by browser.

## Custom animations beyond crossfade

```css
::view-transition-old(root) {
  animation: 300ms ease-out both slide-out;
}
::view-transition-new(root) {
  animation: 300ms ease-in both slide-in;
}

@keyframes slide-out {
  to { transform: translateX(-30px); opacity: 0; }
}
@keyframes slide-in {
  from { transform: translateX(30px); opacity: 0; }
}
```

For shared elements, animate size and position morph:

```css
::view-transition-group(product-hero) {
  animation-duration: 400ms;
  animation-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
}
```

## Performance on mobile

Full-page snapshots of complex DOM trees allocate offscreen buffers. On low-memory devices, large transitions can cause jank or eviction:

- Limit named transitions to 2–3 elements per navigation
- Avoid transitions on pages with heavy canvas, video, or thousands of DOM nodes
- Test on mid-range Android devices, not just desktop Chrome
- Use shorter durations on mobile (200ms vs 400ms)

## Failure modes

- **Duplicate view-transition-name in same frame** — transition breaks or behaves unpredictably; only one element per name
- **Missing flushSync in React** — old snapshot captured after partial render; animation shows intermediate state
- **display:none on transitioning element** — snapshot is empty; ensure element is visible before transition
- **Fixed-position elements** — may animate unexpectedly; exclude with `view-transition-name: none`
- **SEO concern** — transitions are visual only; content is in DOM regardless

## Production checklist

- Feature-detect `document.startViewTransition`
- Async content loaded before transition starts (or skeleton names match)
- `flushSync` used for React state updates inside callback
- `prefers-reduced-motion` disables all transition animations
- Unique `view-transition-name` per shared element (dynamic suffix with id)
- Screen reader route change announcements independent of visual transition
- Tested on mobile with realistic DOM weight

## Resources

- [MDN View Transitions API](https://developer.mozilla.org/en-US/docs/Web/API/View_Transitions_API)
- [web.dev — View Transitions](https://web.dev/articles/view-transitions)
- [Chrome cross-document view transitions](https://developer.chrome.com/docs/web-platform/view-transitions/cross-document)
- [React ViewTransition (canary docs)](https://react.dev/reference/react/ViewTransition)
