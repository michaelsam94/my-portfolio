---
title: "Complex Layouts with Subgrid"
slug: "css-subgrid-layouts"
description: "Align nested grid items across rows and columns with CSS subgrid: grid-template-columns subgrid and practical card list patterns."
datePublished: "2025-06-02"
dateModified: "2025-06-02"
tags: ["Web", "CSS"]
keywords: "CSS subgrid, grid subgrid, nested grid alignment, card grid layout, CSS Grid"
faq:
  - q: "What is CSS subgrid?"
    a: "Subgrid lets a nested grid item inherit the track lines of its parent grid, so child elements align across sibling containers. A list of cards can share column tracks—titles align, prices align—without hardcoding column widths on each card."
  - q: "Which browsers support subgrid?"
    a: "Firefox 71+, Safari 16+, Chrome 117+ support grid-template-columns: subgrid and subgrid rows. Subgrid is baseline for modern evergreen browsers in 2025."
  - q: "When should I use subgrid vs nested independent grids?"
    a: "Use subgrid when visual alignment must continue through nested components—product grids, form field groups, dashboard widgets sharing column structure. Use independent nested grids when inner layout is self-contained and does not need to align with siblings."
---

Nested CSS Grid without subgrid forces a choice: duplicate parent column definitions on every child (breaks when parent changes) or accept misaligned card titles across rows. Subgrid passes parent track lines through—the inner grid uses `subgrid` and its rows/columns snap to the outer grid's geometry. Card lists finally align like tables without table markup.

## Parent grid setup

```css
.product-list {
  display: grid;
  grid-template-columns: 80px 1fr auto;
  gap: 1rem 1.5rem;
}
```

Each product card spans full row but internal layout subgrids to those three columns:

```css
.product-card {
  display: grid;
  grid-column: 1 / -1;
  grid-template-columns: subgrid;
  align-items: center;
}
```

```html
<ul class="product-list">
  <li class="product-card">
    <img src="thumb.jpg" alt="" />
    <h2>Product name</h2>
    <span class="price">$29</span>
  </li>
  <!-- more cards — prices column-align automatically -->
</ul>
```

## Subgrid rows for vertical alignment

```css
.dashboard {
  display: grid;
  grid-template-rows: auto auto 1fr;
  gap: 1rem;
}

.widget {
  display: grid;
  grid-row: span 1;
  grid-template-rows: subgrid;
}
```

Widget header, body, footer align across adjacent widgets sharing row structure.

## Combining subgrid axes

```css
.card {
  grid-template-columns: subgrid;
  grid-template-rows: subgrid;
}
```

Both axes inherit—use when nested content fills two-dimensional parent cells.

## Fallback without subgrid

```css
@supports not (grid-template-columns: subgrid) {
  .product-card {
    display: grid;
    grid-template-columns: 80px 1fr auto;
  }
}
```

Duplicate track definitions—acceptable degradation until subgrid universal.

## Gap inheritance

Subgrid inherits gap from parent in supporting browsers—verify visually; spec behavior on gap propagation evolved—test Firefox and Chrome.

## Common patterns

**Form field rows** — label, input, error message columns align across stacked field groups.

**Media object lists** — thumbnail column consistent width without fixed px on each item.

**Comparison tables built with grid** — feature rows align without `<table>` when semantic table inappropriate.

## Pitfalls

Subgrid only works when parent is grid and child spans multiple tracks or explicit subgrid range.

Anonymous grid items (direct text nodes) do not subgrid cleanly—wrap in elements.

Deep subgrid nesting stacks complexity—prefer one subgrid level per component boundary.

## Why subgrid exists — the alignment problem

Before subgrid, nested grids were independent coordinate systems. A product list with parent columns `[thumb | title | price]` forced each card to re-declare those columns:

```css
/* Without subgrid — duplicated, drifts when parent changes */
.product-card {
  display: grid;
  grid-template-columns: 80px 1fr auto; /* copy-paste from parent */
}
```

Change the thumbnail column to 100px in the parent? Update every child declaration. Miss one? Misaligned rows. Subgrid makes the inner grid inherit parent tracks — one source of truth for column geometry.

## Subgrid line names and ranges

Parent grids can name lines; subgrid children inherit them:

```css
.product-list {
  display: grid;
  grid-template-columns: [thumb-start] 80px [title-start] 1fr [price-start] auto [price-end];
}

.product-card {
  grid-column: 1 / -1;
  grid-template-columns: subgrid;
}

.product-card .badge {
  grid-column: price-start / price-end;
}
```

Named lines pass through subgrid — useful when a badge should span the price column without knowing its pixel width.

## Subgrid with gap and alignment

Subgrid inherits the parent's gap in modern browsers, but test across Firefox, Chrome, and Safari — gap propagation had spec iterations. Alignment properties (`align-items`, `justify-items`) on the subgrid element control how subgrid items sit within inherited tracks.

When items in the same column have different heights (multi-line titles), subgrid row alignment keeps price cells vertically centered across cards in the same row — behavior that flexbox within each card can't replicate across siblings.

## Page-level layout with subgrid

Subgrid isn't only for lists — page layouts benefit:

```css
.page-layout {
  display: grid;
  grid-template-columns: 240px 1fr 300px;
  grid-template-rows: auto 1fr auto;
}

.main-content {
  grid-column: 2;
  grid-row: 2;
  display: grid;
  grid-template-columns: subgrid;
  grid-column: 1 / -1; /* span full page width tracks */
}
```

Article content aligns to the same column grid as the page header and footer — consistent vertical rhythm without magic margin numbers.

## When subgrid is the wrong tool

- **Self-contained card internals** — if the card's inner layout doesn't need to align with sibling cards, a regular nested grid is simpler
- **Single item** — subgrid requires a parent grid with multiple children benefiting from shared tracks
- **Flexbox layouts** — subgrid is grid-only; flex containers don't support it
- **Dynamic column counts** — if each card needs different column counts, shared tracks don't help

## Fallback strategy

```css
.product-card {
  display: grid;
  grid-template-columns: subgrid;
}

@supports not (grid-template-columns: subgrid) {
  .product-card {
    grid-template-columns: 80px 1fr auto;
  }
}
```

Centralize fallback track definitions as custom properties on the parent:

```css
.product-list {
  --col-thumb: 80px;
  --col-price: auto;
  grid-template-columns: var(--col-thumb) 1fr var(--col-price);
}

@supports not (grid-template-columns: subgrid) {
  .product-card {
    grid-template-columns: var(--col-thumb) 1fr var(--col-price);
  }
}
```

One place to update column widths, even in fallback mode.

## Debugging subgrid

Firefox Grid Inspector and Chrome DevTools show subgrid relationships with overlay lines. Common issues:

- Child doesn't span enough parent columns — `grid-column: 1 / -1` required for full-width subgrid
- Direct text nodes as grid items — wrap in `<span>`; anonymous items break alignment
- Parent isn't `display: grid` — subgrid on flex or block children is ignored

## Production checklist

- Parent grid defines canonical track structure
- Subgrid child spans all relevant parent columns/rows
- Fallback track definitions share custom properties with parent
- Tested in Firefox, Chrome, and Safari
- No text nodes as direct subgrid items
- Only one subgrid level per component boundary

Subgrid support is baseline in evergreen browsers — if your fallback duplicates track definitions via custom properties, you can drop the `@supports` block once analytics confirm negligible traffic on unsupported engines.

When presenting subgrid to stakeholders skeptical of "another CSS feature," demo the product card alignment problem live: nested grids with duplicated column widths vs one `subgrid` keyword. The visual before/after sells faster than spec language.

## Resources

- [MDN subgrid](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_grid_layout/Subgrid)
- [CSS Grid Level 2 spec — subgrid](https://www.w3.org/TR/css-grid-2/#subgrid-definition)
- [web.dev — Subgrid](https://web.dev/articles/css-subgrid)
- [Can I use subgrid](https://caniuse.com/css-subgrid)
