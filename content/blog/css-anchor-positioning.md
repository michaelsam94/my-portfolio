---
title: "Anchor Positioning in CSS"
slug: "css-anchor-positioning"
description: "Position popovers, tooltips, and menus relative to anchor elements with CSS anchor positioning—position-anchor, anchor(), and fallback behavior."
datePublished: "2025-05-15"
dateModified: "2025-05-15"
tags: ["Web", "CSS"]
keywords: "CSS anchor positioning, position-anchor, anchor function, popover positioning, tooltip CSS"
faq:
  - q: "What is CSS anchor positioning?"
    a: "CSS anchor positioning lets an element position itself relative to another element (the anchor) without JavaScript measurements. The positioned element uses position-anchor to bind to an anchor-name on the target, then inset properties with anchor() functions place it above, below, or aligned to anchor edges—similar to Popper.js but declarative."
  - q: "Which browsers support CSS anchor positioning?"
    a: "Chrome 125+ and Chromium-based browsers ship anchor positioning; Safari Technology Preview and Firefox are implementing. Use @supports (anchor-name: --x) for progressive enhancement and keep JavaScript fallback for older browsers in production until support broadens."
  - q: "How do I position a tooltip above a button?"
    a: "Set anchor-name on the button, position-anchor on the tooltip, position: absolute, and bottom: anchor(top) with translate to offset. position-try-fallbacks can flip the tooltip below when insufficient viewport space exists above."
---

JavaScript tooltip libraries exist because CSS never had a native way to say "put this box above that button, aligned to its center, flip if clipped." Anchor positioning adds that vocabulary: name an anchor, bind a floating element, use `anchor()` in inset properties. Popovers, dropdowns, and combobox lists become layout problems instead of resize-observer scripts—when browser support catches up.

## Basic setup

```html
<button class="trigger" style="anchor-name: --menu-trigger">Options</button>
<ul class="menu" popover>
  <li>Edit</li>
  <li>Delete</li>
</ul>
```

```css
.trigger {
  anchor-name: --menu-trigger;
}

.menu {
  position: absolute;
  position-anchor: --menu-trigger;
  position-area: bottom center;
  margin-top: 8px;
  position-try-fallbacks: flip-block;
}
```

`position-area` replaces manual `top`/`left` math with semantic placement keywords.

## anchor() function

Fine-grained control:

```css
.tooltip {
  position: absolute;
  position-anchor: --btn;
  bottom: anchor(top);
  left: anchor(center);
  translate: -50% -8px;
  width: anchor-size(width); /* optional: match anchor width */
}
```

`anchor(top)`, `anchor(right)`, `anchor(center)` reference edges and center of anchor box.

## Multiple anchors

Elements can expose names; positioned item picks one:

```css
.card { anchor-name: --card; }
.card-action { anchor-name: --card-action; }

.context-menu {
  position-anchor: --card-action;
  top: anchor(bottom);
  left: anchor(left);
}
```

## Fallback with position-try

When viewport clips placement, try alternatives:

```css
.dropdown {
  position-try-fallbacks:
    flip-block,
    flip-inline,
    --custom-fallback;
}

@position-try --custom-fallback {
  top: anchor(bottom);
  left: anchor(left);
}
```

Browser evaluates fallbacks until one fits visible area.

## Popover API integration

HTML `popover` attribute pairs naturally:

```html
<button popovertarget="tip">Help</button>
<div id="tip" popover class="tooltip">Explanation text</div>
```

```css
#tip {
  position: absolute;
  position-anchor: --help-btn;
  position-area: top center;
  margin: 8px;
}
```

Popover top layer handles z-index; anchor positioning handles geometry.

## Progressive enhancement

```css
@supports (anchor-name: --a) {
  .menu {
    position-anchor: --trigger;
    position-area: bottom span-right;
  }
}

/* Fallback: static placement or JS-enhanced */
@supports not (anchor-name: --a) {
  .menu {
    position: fixed;
    inset: auto 1rem 1rem auto;
  }
}
```

Feature detect before removing Popper/Floating UI from production.

## Accessibility considerations

Anchor positioning does not manage focus trap or aria-expanded—that stays in JS or invoker attributes. Ensure popover has `role` and keyboard dismiss (`Escape`).

## The positioning problem anchor positioning solves

Before anchor positioning, every dropdown library followed the same pattern: measure anchor `getBoundingClientRect()`, measure floating element, compute position, attach scroll/resize listeners, flip if near viewport edge. Floating UI and Popper abstracted this, but the fundamental issue remained — positioning lived in JavaScript because CSS had no way to express "place this element relative to that element."

Anchor positioning moves the geometry into CSS. The browser's layout engine knows both elements' boxes and can recompute on scroll, resize, and anchor movement without JavaScript listeners. This is especially valuable for scrollable containers where JS positioning often lags a frame behind.

## position-area keywords reference

`position-area` replaces manual inset calculations with semantic placement:

```css
/* Common placements */
.tooltip { position-area: top center; }      /* above, centered */
.menu { position-area: bottom span-right; } /* below, left-aligned to anchor */
.popover { position-area: right center; }   /* to the right, vertically centered */
```

The `span-*` variants align the positioned element's edge to the anchor's edge rather than centering — `bottom span-left` puts the dropdown's left edge at the anchor's left edge.

For fine control beyond keywords, fall back to `anchor()` in individual inset properties:

```css
.dropdown {
  top: anchor(bottom);
  left: anchor(left);
  margin-top: 4px;
}
```

## Implicit vs explicit anchors

The Popover API creates implicit anchor relationships — a `popovertarget` button automatically anchors its popover. For non-popover floating elements, set explicit names:

```css
.trigger { anchor-name: --trigger; }
.floating { position-anchor: --trigger; }
```

Multiple anchors on one page need unique names. Use component-scoped naming conventions: `--menu-trigger-{id}` set via inline style or CSS custom property to avoid collisions.

## Scroll and overflow behavior

Anchored elements inside scrollable containers should track anchor movement during scroll. Anchor positioning handles this natively — unlike `position: fixed` popovers that ignore scroll container boundaries. Test with:

- Scrollable `<div>` ancestors (not just window scroll)
- Anchors near container edges where flip fallbacks activate
- Nested scroll containers (modal with scrollable body + dropdown)

When `position-try-fallbacks` exhausts all options, the element may clip — provide a JS fallback or scroll-into-view behavior for critical UI.

## Comparison with JavaScript positioning

| Concern | CSS anchor positioning | Floating UI / Popper |
|---|---|---|
| Scroll tracking | Native, no listeners | Requires scroll/resize handlers |
| Viewport flip | `position-try-fallbacks` | Built-in flip middleware |
| Browser support | Chrome 125+, growing | Universal |
| Dynamic anchor resize | Automatic | Automatic via observers |
| Focus management | Not included | Not included (same) |
| Virtual reference | Limited | Full support |

Plan on keeping Floating UI as fallback until support covers your analytics baseline. Wrap in `@supports (anchor-name: --a)`.

## Integration with dialog and popover

The Popover API's top layer (`:popover-open`) solves z-index stacking wars. Anchor positioning solves geometry. Together they replace most dropdown libraries:

```html
<button popovertarget="menu" style="anchor-name: --btn">Menu</button>
<div id="menu" popover class="dropdown">...</div>
```

```css
.dropdown {
  position: absolute;
  position-anchor: --btn;
  position-area: bottom span-left;
  position-try-fallbacks: flip-block, flip-inline;
  margin: 0;
  border: 1px solid var(--border);
}
```

For modal dialogs, anchor positioning is less relevant — centered overlays don't need anchors. Use it for menus, tooltips, combobox lists, and context menus.

## Failure modes

- **Anchor name not set** — positioned element renders at static position or viewport origin
- **Name collision** — two elements share `--trigger`; last one wins
- **No fallback in unsupported browsers** — menu appears in wrong place; always feature-detect
- **Confusing anchor-size** — `width: anchor-size(width)` on a tooltip wider than anchor may look wrong; set max-width
- **Missing keyboard support** — CSS positions visually; `aria-expanded`, focus trap, and Escape handling remain JavaScript responsibilities

## Production checklist

- `@supports (anchor-name: --a)` with JS fallback for unsupported browsers
- Unique anchor names per instance (dynamic suffix for lists)
- `position-try-fallbacks` configured for viewport edge cases
- Popover API for top-layer stacking where applicable
- Focus management and ARIA attributes handled in JS
- Tested inside scrollable containers and near viewport edges

## Resources

- [CSS anchor positioning spec (W3C)](https://drafts.csswg.org/css-anchor-1/)
- [MDN position-anchor](https://developer.mozilla.org/en-US/docs/Web/CSS/position-anchor)
- [Chrome developer guide to anchor positioning](https://developer.chrome.com/blog/anchor-positioning-api)
- [Popover API documentation](https://developer.mozilla.org/en-US/docs/Web/API/Popover_API)
