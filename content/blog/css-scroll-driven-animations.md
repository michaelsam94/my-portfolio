---
title: "Scroll-Driven Animations in CSS"
slug: "css-scroll-driven-animations"
description: "Animate elements with scroll progress using CSS scroll-driven animations: animation-timeline, view(), and scroll() without JavaScript listeners."
datePublished: "2025-05-30"
dateModified: "2025-05-30"
tags: ["Web", "CSS"]
keywords: "scroll-driven animations, animation-timeline, view timeline, scroll progress CSS, parallax CSS"
faq:
  - q: "What are CSS scroll-driven animations?"
    a: "Scroll-driven animations tie animation progress to scroll position instead of time. animation-timeline: scroll() tracks scroll container progress; animation-timeline: view() tracks element visibility in scrollport. Keyframes advance as user scrolls—progress bars, fade-ins, parallax without scroll event listeners."
  - q: "Do scroll-driven animations work without JavaScript?"
    a: "Yes in supporting browsers—Chrome 115+, Edge, Safari 26+. No requestAnimationFrame, no IntersectionObserver for basic reveal effects. JS still helps for complex orchestration and fallbacks on unsupported browsers."
  - q: "What is the difference between scroll() and view() timelines?"
    a: "scroll() binds to scroll container progress—0% at top, 100% at bottom of scrollable area. view() binds to element intersection with scrollport—animation runs as element enters, crosses, or exits view. Use view() for reveal-on-scroll; scroll() for page-wide progress indicators."
---

Scroll-jacking with JavaScript scroll listeners caused jank for a decade—main thread blocked, passive listener debates, libraries fighting each other. Scroll-driven animations move scroll coupling into the compositor: declare `animation-timeline: view()` and keyframes run from scroll geometry, not `setTimeout`. Parallax headers and reading progress bars become CSS problems.

## View timeline: reveal on scroll

```css
.reveal {
  animation: fade-slide linear both;
  animation-timeline: view();
  animation-range: entry 0% cover 40%;
}

@keyframes fade-slide {
  from {
    opacity: 0;
    transform: translateY(2rem);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
```

`animation-range: entry 0% cover 40%` runs animation from element entering viewport until 40% covered.

## Named scroll timeline

```css
.scroller {
  overflow-y: auto;
  height: 100vh;
  scroll-timeline: --section-scroll block;
}

.progress-bar {
  animation: grow-width linear;
  animation-timeline: --section-scroll;
}

@keyframes grow-width {
  from { width: 0%; }
  to { width: 100%; }
}
```

Progress bar tracks `.scroller` vertical scroll.

## scroll() shorthand

```css
.header {
  animation: shrink-header linear both;
  animation-timeline: scroll(root block);
}
```

Animates based on document root scroll block axis.

## Parallax-like effect

```css
.hero-image {
  animation: parallax linear;
  animation-timeline: view();
  animation-range: cover 0% cover 100%;
}

@keyframes parallax {
  from { transform: translateY(-10%); }
  to { transform: translateY(10%); }
}
```

Subtle Y shift as image crosses viewport—lighter than multi-layer JS parallax.

## Sticky header shrink

```css
.site-header {
  position: sticky;
  top: 0;
  animation: compact linear both;
  animation-timeline: scroll(root block);
  animation-range: 0 200px;
}

@keyframes compact {
  from { padding-block: 1.5rem; font-size: 1.5rem; }
  to { padding-block: 0.5rem; font-size: 1rem; }
}
```

Header compacts over first 200px of document scroll.

## Reduced motion

```css
@media (prefers-reduced-motion: reduce) {
  .reveal {
    animation: none;
    opacity: 1;
    transform: none;
  }
}
```

Respect user preference—scroll animations can disorient vestibular-sensitive users.

## Fallback strategy

```javascript
if (!CSS.supports('animation-timeline: view()')) {
  // IntersectionObserver adds .visible class
}
```

```css
.reveal { opacity: 0; }
.reveal.visible { opacity: 1; transition: opacity 0.5s; }
```

## Performance notes

Compositor-driven when properties are transform/opacity only—avoid animating width/height on scroll. Test on low-end mobile; many simultaneous view timelines add cost.

## How scroll timelines work under the hood

Understanding the mechanism helps debug "why isn't my animation running?" Scroll-driven animations tie `animation-progress` to a **timeline progress** value between 0 and 1. For `view()`, progress tracks how much of the subject element has crossed the scrollport according to `animation-range`. For `scroll()`, progress tracks scroll offset within the scroll container. The animation runs on the compositor thread when you stick to `transform` and `opacity` — the main thread never sees per-frame scroll events.

This is fundamentally different from `scroll` event listeners that fire dozens of times per second on the main thread. Scroll-driven animations sample scroll position at composite time, similar to how `position: sticky` works — declarative coupling to scroll geometry rather than imperative callbacks.

## Choosing between view() and scroll()

| Use case | Timeline | Why |
|---|---|---|
| Element fade-in on enter | `view()` | Progress tied to element visibility |
| Reading progress bar | `scroll()` | Progress tied to container scroll position |
| Sticky header shrink | `scroll(root block)` | Document scroll, not element visibility |
| Horizontal carousel item highlight | `view(inline)` | Inline axis for horizontal scrollport |
| Parallax on hero image | `view()` with range | Subtle shift as element traverses viewport |

Named timelines (`scroll-timeline: --foo`) decouple the scrolling element from the animated element — useful when the progress bar lives outside the scroll container in the DOM tree but should track its scroll.

## animation-range tuning

The range syntax is the steepest learning curve. Read `entry 0% cover 40%` as: "start when the element begins entering, finish when 40% of the element is covered by the scrollport."

```css
/* Slow reveal — animation spans most of viewport traversal */
.wide-reveal {
  animation-range: entry 0% cover 80%;
}

/* Snappy pop-in — short range near entry edge */
.snappy-reveal {
  animation-range: entry 0% entry 100%;
}

/* Exit animation — runs as element leaves */
.fade-out {
  animation-range: exit 0% exit 100%;
  animation-direction: reverse;
}
```

Test ranges in Chrome DevTools Animation panel — scrub scroll and watch progress. Wrong ranges produce "nothing happens" or "animation already finished on load."

## Stacking multiple scroll animations

Product pages often combine a document-level progress bar, per-section reveals, and a sticky header shrink. Each creates a scroll timeline. On low-end devices, ten simultaneous `view()` animations on a long page can stress the compositor:

- Stagger which elements animate — not every `<p>` needs a reveal
- Use `content-visibility: auto` on below-fold sections to skip layout for off-screen blocks
- Prefer one `scroll()` timeline feeding CSS custom properties if many elements need the same progress value

```css
@keyframes set-progress {
  to { --scroll-progress: 1; }
}

.scroller {
  animation: set-progress linear;
  animation-timeline: scroll(self);
  animation-fill-mode: both;
}

.child {
  opacity: calc(var(--scroll-progress, 0));
}
```

## Debugging checklist

- Animation not running? Verify browser support (`CSS.supports('animation-timeline: view()')`)
- Element visible but no animation? Check `animation-range` — element may already be past range on load
- Jank on scroll? Inspect for non-composited properties (`width`, `margin`, `border-radius`)
- Animation fires once on page load? `view()` on above-fold content may complete immediately — adjust range
- Named timeline not connecting? Confirm `scroll-timeline` is on the scrolling ancestor and name matches

## Accessibility and UX

Scroll-driven animations can trigger vestibular symptoms when large elements move horizontally or zoom during scroll. Always wrap in `prefers-reduced-motion: reduce` and provide static fallbacks. Screen readers ignore scroll animations entirely — don't hide content behind animation completion; elements should be readable at full opacity regardless.

For infinite scroll feeds, `view()` re-triggers when elements re-enter — may cause flicker. Use `animation-fill-mode: both` and consider one-shot IntersectionObserver fallback for feeds where re-entry animation is undesirable.

## Production checklist

- Feature-detect and provide IntersectionObserver fallback
- Animate only `transform` and `opacity` for compositor path
- Respect `prefers-reduced-motion`
- Test on iOS Safari and Android Chrome — scroll container differences matter
- Limit simultaneous view timelines on long pages
- Verify animation-range on above-fold and below-fold content
- Avoid scroll animations on critical navigation elements

## Resources

- [MDN scroll-driven animations](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_scroll-driven_animations)
- [web.dev — Scroll-driven animations](https://web.dev/articles/css-scroll-driven-animations)
- [CSS scroll-driven animations spec](https://drafts.csswg.org/scroll-animations-1/)
- [Can I use scroll-driven animations](https://caniuse.com/css-scroll-driven-animations)
