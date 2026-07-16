---
title: "The :has() Selector in Practice"
slug: "css-has-selector-patterns"
description: "Use CSS :has() for parent and sibling-aware styling: form validation states, card layouts, navigation highlights, and progressive enhancement patterns."
datePublished: "2025-05-24"
dateModified: "2025-05-24"
tags: ["Web", "CSS"]
keywords: "CSS has selector, parent selector, :has pseudo-class, form validation CSS, relational CSS"
faq:
  - q: "What does the CSS :has() selector do?"
    a: ":has() is a relational pseudo-class that selects an element if it contains (or is followed by, with +/~ combinators) a matching descendant or sibling. It enables parent-selection patterns previously impossible in pure CSS—style a form group when an input inside is invalid, or a card when it contains an image."
  - q: "Is :has() supported in all browsers?"
    a: "Safari 15.4+, Chrome 105+, Firefox 121+ support :has(). It is baseline for modern evergreen browsers in 2025. Provide graceful degradation when styling is enhancement-only; do not rely on :has() for critical accessibility without fallback."
  - q: "Does :has() hurt performance?"
    a: "Browsers optimize :has() with bloom filters and limit relative complexity on heavy pages. Avoid chaining many expensive :has() rules on universal selectors like *:has(...). Scope to components—.form-group:has(:invalid) is fine; div:has(div:has(span)) on every node is not."
---

For decades CSS could style descendants from parents but never parents from descendants—"if this input is invalid, highlight the wrapping field group" required JavaScript class toggles. `:has()` inverts the relationship: the subject element matches when it `:has()` a descendant matching inner selector. Finally, declarative parent styling— with sensible performance caveats.

## Basic parent selection

```css
/* Field group with invalid input */
.form-group:has(:invalid) {
  border-color: var(--error);
}

.form-group:has(:focus-visible) {
  outline: 2px solid var(--focus-ring);
}
```

No JS `oninput` class flipping.

## Card with image gets different layout

```css
.card:has(img) {
  display: grid;
  grid-template-columns: 120px 1fr;
}

.card:not(:has(img)) {
  padding-left: 1.5rem;
}
```

## Sibling-aware patterns

```css
/* Label after required input */
label:has(+ input[required])::after {
  content: " *";
  color: var(--error);
}

/* Hide submit until terms checked */
form:has(#terms:not(:checked)) button[type="submit"] {
  opacity: 0.5;
  pointer-events: none;
}
```

`:has()` subject is the element before the pseudo—`label:has(+ input)` selects label with immediately following input.

## Navigation active section

```html
<nav>
  <a href="#intro">Intro</a>
  <a href="#features">Features</a>
</nav>
<main>
  <section id="intro">...</section>
  <section id="features">...</section>
</main>
```

With `:target` inside sections:

```css
nav a:has(+ a:hover) { /* limited — URL hash patterns vary */ }

/* Practical: section in view via scroll-driven or JS class on body */
body:has(#features:target) nav a[href="#features"] {
  font-weight: 700;
  border-bottom: 2px solid currentColor;
}
```

Hash navigation + `:target` + `:has()` for zero-JS highlight on anchor jumps.

## Empty state styling

```css
.list:has(.list-item) .empty-message {
  display: none;
}

.list:not(:has(.list-item)) .empty-message {
  display: block;
}
```

Show empty placeholder when no items without `:empty` limitations (whitespace text nodes break `:empty`).

## Combining with :not()

```css
.table-row:has(td[data-priority="high"]):not(:has(td[data-resolved])) {
  background: var(--urgent-row);
}
```

Unread high-priority unresolved rows highlighted.

## Form patterns

```css
/* Password strength hint visible when field focused and empty */
.password-field:has(input:focus:placeholder-shown) .hint {
  opacity: 1;
}

/* Select with placeholder option */
.select-wrap:has(select:invalid) {
  color: var(--muted);
}
```

Use `:user-invalid` where supported for post-interaction validation styling.

## Accessibility notes

Color-only invalid states still need text errors—`:has()` styles visuals, not `aria-invalid`. Pair with native constraint validation API.

Do not hide focus outlines on parents that `:has(:focus)` unless replacing with visible alternative.

## Progressive enhancement

```css
@supports selector(:has(*)) {
  .form-group:has(:invalid) { border-color: red; }
}
```

Legacy browsers get unstyled groups—acceptable if errors still show via browser validation UI.

## Why :has() changes component CSS architecture

`:has()` enables **upstream selection** — styling an ancestor based on descendant state. Before it, every form library toggled `.is-invalid` on the parent via JavaScript on `input` events. Every card grid checked for image children in the template layer. `:has()` moves this to CSS, reducing JavaScript surface area and eliminating flash-of-unstyled-state on hydration.

The selector is forgiving about structure — `.form-group:has(input:invalid)` works regardless of whether the input is a direct child or nested inside a wrapper, as long as it's a descendant.

## Advanced form patterns

Multi-field validation groups:

```css
/* Entire form section highlighted when any field invalid */
.form-section:has(input:invalid, select:invalid, textarea:invalid) {
  border-left: 3px solid var(--error);
}

/* Submit enabled only when all required fields valid */
form:has(input[required]:valid) button[type="submit"] {
  opacity: 1;
  pointer-events: auto;
}

form:has(input[required]:invalid) button[type="submit"] {
  opacity: 0.5;
  pointer-events: none;
}
```

Pair with `:user-invalid` (where supported) to style only after user interaction, avoiding red borders on untouched required fields at page load:

```css
.form-group:has(input:user-invalid) {
  border-color: var(--error);
}
```

## Layout patterns without JavaScript

Responsive card grids that adapt to content:

```css
/* Featured layout when card contains an image */
.card-grid:has(.card img) {
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
}

/* Compact list when no images present */
.card-grid:not(:has(.card img)) {
  grid-template-columns: 1fr;
}

.card:has(img) {
  grid-row: span 2;
}
```

Navigation highlighting based on visible section (combined with scroll-driven animations or `:target`):

```css
nav:has(a[href="#pricing"]:target) a[href="#pricing"],
nav:has(a[aria-current="page"][href="/pricing"]) a[href="/pricing"] {
  font-weight: 700;
  color: var(--primary);
}
```

## Table and data display patterns

```css
/* Highlight row with overdue date */
.table tbody tr:has(td[data-status="overdue"]) {
  background: var(--warning-bg);
}

/* Hide actions column header when no rows have actions */
.table:not(:has(td.actions)) th.actions {
  display: none;
}

/* Expandable row indicator */
.table tr:has(+ tr.expanded-content) td:first-child::before {
  content: "▾";
}
```

## Performance guidance in depth

Browser engines optimize `:has()` using bloom filters — pre-computed sets of elements that *might* match, avoiding full DOM scans on every style recalculation. Still, expensive patterns exist:

```css
/* Bad — scans every div in the document on any DOM change */
div:has(div:has(span:has(a))) { }

/* Good — scoped to component class */
.data-table tbody tr:has(td.priority-high) { }

/* Good — direct child check */
.form-row:has(> input:required) { }
```

Chrome DevTools Performance panel shows style recalculation cost — profile pages with many `:has()` rules during heavy DOM updates (virtual list scrolling, live filtering).

## Limitations to know

- `:has()` cannot traverse up past the subject — it's "does this element contain...", not "find my ancestor that contains..."
- The subject is always the element before `:has()` — `a:has(+ b)` selects `a`, not `b`
- Cannot be used in `::-webkit-scrollbar` or other pseudo-elements that don't accept complex selectors (browser-dependent)
- Inside `@keyframes` — not valid

## Progressive enhancement strategy

When `:has()` styling is cosmetic enhancement:

```css
.form-group { border-color: var(--border); }

@supports selector(:has(*)) {
  .form-group:has(:invalid) { border-color: var(--error); }
}
```

When `:has()` is functional (submit button disabled state), provide JavaScript fallback:

```javascript
if (!CSS.supports('selector(:has(*))')) {
  form.querySelectorAll('input').forEach(input => {
    input.addEventListener('input', () => updateFormState(form));
  });
}
```

## Production checklist

- `:has()` scoped to component classes, not universal selectors
- `:user-invalid` used where supported for post-interaction validation styling
- Accessibility: error messages as text, not color-only; ARIA attributes in HTML/JS
- `@supports selector(:has(*))` for enhancement-only styling
- JavaScript fallback for functional `:has()` patterns
- Performance profiled on pages with dynamic DOM updates

## Resources

- [MDN :has()](https://developer.mozilla.org/en-US/docs/Web/CSS/:has)
- [CSS Selectors Level 4 spec](https://www.w3.org/TR/selectors-4/#relational)
- [web.dev — :has() the parent selector](https://web.dev/articles/css-has)
- [Can I use :has()](https://caniuse.com/css-has)
