---
title: "Responsive Design with Container Queries"
slug: "css-container-queries"
description: "Build component-responsive layouts with CSS container queries: container-type, cqw units, and @container rules that respond to parent size, not viewport."
datePublished: "2025-05-21"
dateModified: "2025-05-21"
tags: ["Web", "CSS"]
keywords: "CSS container queries, @container, container-type, cqw units, component responsive design"
faq:
  - q: "How are container queries different from media queries?"
    a: "Media queries respond to viewport or device characteristics—screen width, prefers-color-scheme. Container queries respond to the size of a parent container element. A card component can switch from stacked to horizontal layout based on its column width in a grid, not the browser window width."
  - q: "What is container-type: inline-size?"
    a: "container-type: inline-size establishes a query container that tracks width (inline size) for descendant @container rules. container-name optionally labels containers for nested query targeting. container-type: size tracks both width and height but requires explicit dimensions on the container—use inline-size for most layouts."
  - q: "Can I use container query units like cqw?"
    a: "Yes. cqw is 1% of container query width, cqh height, cqi inline, cqb block. They work inside @container contexts for typography and spacing scaled to component size—font-size: clamp(1rem, 2cqw, 1.5rem) on card titles."
---

Viewport media queries broke component reuse. A sidebar card looks fine at 1200px viewport but squashed in a 280px grid column because `@media (min-width: 768px)` knows nothing about the column. Container queries fix the unit of responsiveness: the component's parent box. Design systems finally ship one card implementation that adapts everywhere it renders.

## Establish a query container

```css
.card-wrapper {
  container-type: inline-size;
  container-name: card; /* optional */
}
```

Child rules query this ancestor:

```css
@container card (min-width: 400px) {
  .card {
    display: grid;
    grid-template-columns: 120px 1fr;
    gap: 1rem;
  }
}

@container card (max-width: 399px) {
  .card {
    display: flex;
    flex-direction: column;
  }
}
```

Named container helps when multiple nested containers exist.

## Shorthand container property

```css
.card-wrapper {
  container: card / inline-size;
}
```

## Container query units

```css
@container (min-width: 300px) {
  .card-title {
    font-size: clamp(1rem, 4cqw, 1.75rem);
  }
  .card-body {
    padding: 2cqi;
  }
}
```

`cqw` scales with container width—typography tracks component size, not viewport.

## Style queries (container-type: style)

Experimental/style container queries test custom property values:

```css
.card-wrapper {
  container-type: inline-size;
  --layout: compact;
}

@container (min-width: 500px) {
  .card-wrapper { --layout: wide; }
}

@container style(--layout: wide) {
  .card-actions { flex-direction: row; }
}
```

Check browser support before production use of style queries.

## Nested containers

```html
<aside class="sidebar"> <!-- container A -->
  <article class="card-wrap"> <!-- container B -->
    <div class="card">...</div>
  </article>
</aside>
```

```css
.sidebar { container-type: inline-size; container-name: sidebar; }
.card-wrap { container-type: inline-size; container-name: card; }

@container sidebar (min-width: 250px) {
  .sidebar-nav { display: block; }
}

@container card (min-width: 350px) {
  .card { flex-direction: row; }
}
```

Inner `@container card` responds to card-wrap width, not sidebar.

## Fallback for older browsers

```css
.card {
  display: flex;
  flex-direction: column;
}

@container (min-width: 400px) {
  .card {
    display: grid;
    grid-template-columns: 120px 1fr;
  }
}

@supports not (container-type: inline-size) {
  @media (min-width: 768px) {
    .card { /* viewport fallback */ }
  }
}
```

## DevTools and debugging

Chrome DevTools shows container size and which queries matched. If queries never fire, verify ancestor has `container-type` and descendant is not outside subtree.

## Performance

Container queries add layout containment tracking—negligible for typical UIs. Avoid deep nesting of size containers on huge lists without virtualization.

## Container queries vs media queries in practice

The mental model shift: media queries answer "how big is the viewport?" Container queries answer "how big is my slot?" A dashboard with a collapsible sidebar illustrates this — when the sidebar opens, the main content column shrinks but the viewport is unchanged. Media queries fire nothing; container queries reflow cards inside the narrower column.

```css
/* Wrong tool — fires on viewport, not column */
@media (min-width: 600px) {
  .dashboard-card { grid-template-columns: 1fr 1fr; }
}

/* Right tool — fires when card's container is wide enough */
@container (min-width: 600px) {
  .dashboard-card { grid-template-columns: 1fr 1fr; }
}
```

Use media queries for page-level layout (sidebar visibility, navigation mode). Use container queries for component internals (card layout, data table density, form field arrangement).

## Size containment gotchas

`container-type: size` requires the container to have explicit dimensions — width *and* height. Most components only know their width from layout flow, which is why `inline-size` is the default choice:

```css
/* size — needs explicit height, rarely what you want */
.metrics-panel {
  container-type: size;
  height: 400px; /* required or queries never resolve */
}

/* inline-size — tracks width, height flows naturally */
.metrics-panel {
  container-type: inline-size;
}
```

If container queries never fire despite visible width, check that no ancestor has `overflow: hidden` breaking containment in edge cases, and verify the querying element is a descendant of the container element.

## Container query length units in depth

| Unit | Meaning | Typical use |
|---|---|---|
| `cqw` | 1% of container width | Fluid typography |
| `cqh` | 1% of container height | Vertical spacing in sized containers |
| `cqi` | 1% of inline size | Logical property layouts |
| `cqb` | 1% of block size | Block-axis padding |
| `cqmin` / `cqmax` | Min/max of inline and block | Responsive sizing |

```css
@container (min-width: 250px) {
  .stat-value {
    font-size: clamp(1.25rem, 5cqw + 0.5rem, 2.5rem);
  }
}
```

Container units only work inside a container query context — using `cqw` outside `@container` is invalid. Fallback with `rem` in the default (non-query) rule.

## Card grid pattern — the killer app

The pattern that converts most teams:

```html
<div class="card-grid">
  <article class="card-wrap">
    <div class="card">...</div>
  </article>
  <!-- repeat -->
</div>
```

```css
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

.card-wrap {
  container-type: inline-size;
}

@container (min-width: 350px) {
  .card {
    display: grid;
    grid-template-columns: 80px 1fr;
    gap: 1rem;
  }
}

@container (max-width: 349px) {
  .card {
    display: flex;
    flex-direction: column;
  }
}
```

Same card component works in a 320px mobile column, a 400px grid cell, and a 600px featured slot — one implementation, zero breakpoint props passed from JavaScript.

## Style queries and the future

Style containers (`container-type: style`) enable queries on custom property values — `@container style(--theme: dark)`. Support is narrower than size queries; treat as progressive enhancement. When supported, they eliminate JavaScript theme class toggling for component-internal layout switches.

## Failure modes

- **Query never matches** — missing `container-type` on ancestor, or element is outside container subtree
- **Flash of wrong layout** — no default styles outside `@container`; always define a narrow-layout baseline
- **Container in container confusion** — unnamed containers query nearest ancestor; use `container-name` when nesting
- **Performance on long lists** — 500 cards each with `container-type: inline-size` adds containment overhead; virtualize or use container on the list, not each item

## Production checklist

- Default (narrow) layout defined outside `@container` rules
- `container-type: inline-size` unless you explicitly need height queries
- `container-name` when multiple nested containers exist
- Viewport fallback via `@supports not (container-type: inline-size)` for legacy browsers
- Test cards in narrow sidebar, wide main, and full-width contexts
- DevTools container overlay used to verify query breakpoints

When introducing container queries to an existing design system, migrate one component at a time — cards first, then data tables, then navigation shells — and keep viewport media queries for page skeleton until each component is self-contained.

## Resources

- [MDN CSS container queries](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_containment/Container_queries)
- [web.dev — Container queries](https://web.dev/articles/container-queries)
- [CSS containment module spec](https://www.w3.org/TR/css-contain-3/)
- [Can I use container queries](https://caniuse.com/css-container-queries)
