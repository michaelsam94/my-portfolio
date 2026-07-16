---
title: "Native CSS Nesting"
slug: "css-nesting-native"
description: "Write maintainable CSS with native nesting: ampersand rules, nested media queries, and how native nesting differs from Sass."
datePublished: "2025-05-27"
dateModified: "2025-05-27"
tags: ["Web", "CSS"]
keywords: "CSS nesting, native CSS nest, & selector, nested media queries, CSS without Sass"
faq:
  - q: "Is native CSS nesting the same as Sass nesting?"
    a: "Similar syntax but different parsing rules. Native nesting requires & for compound selectors in some cases—button { &:hover {} } not button { :hover {} } which would parse as descendant. Native nesting integrates with cascade layers and is valid CSS without compilation—though build tools may still bundle it."
  - q: "Do I need PostCSS for CSS nesting?"
    a: "Evergreen browsers (Chrome 112+, Safari 16.5+, Firefox 117+) support native nesting. PostCSS nesting plugin remains useful for older browser targets or spec-divergent edge cases during transition."
  - q: "Can I nest media queries inside selectors?"
    a: "Yes—one of nesting's best ergonomics wins. .card { @media (min-width: 768px) { padding: 2rem; } } keeps responsive rules colocated with component styles instead of scattered in global media blocks."
---

Sass trained a generation to nest `.card { .title {} .body {} }`. Native CSS nesting ships that ergonomics in the browser—no `$variables` required, no build step strictly necessary. The syntax looks familiar but the spec adds guardrails around `&` and specificity that bite migrators who copy-paste SCSS literally.

## Basic nesting

```css
.card {
  padding: 1rem;
  border-radius: 8px;

  & .title {
    font-size: 1.25rem;
    font-weight: 600;
  }

  & .body {
    color: var(--text-muted);
  }
}
```

`&` represents the parent selector `.card`. Compiled equivalent: `.card .title`, `.card .body`.

## Pseudo-classes and modifiers

```css
.button {
  background: var(--primary);

  &:hover {
    background: var(--primary-dark);
  }

  &:focus-visible {
    outline: 2px solid var(--focus);
  }

  &.is-loading {
    opacity: 0.6;
    pointer-events: none;
  }
}
```

`&.is-loading` compiles to `.button.is-loading`—not `.button .is-loading`.

## Nested media queries

```css
.sidebar {
  display: none;

  @media (min-width: 1024px) {
    display: block;
    width: 280px;
  }
}
```

Colocate breakpoints with component—matches container query philosophy for viewport-driven rules.

## Nesting with cascade layers

```css
@layer components {
  .alert {
    padding: 1rem;

    &--error {
      background: var(--error-bg);
    }

    &--success {
      background: var(--success-bg);
    }
  }
}
```

BEM-style `--modifiers` work with `&--error` → `.alert--error`.

## When & is required

Invalid without `&`—parser treats inner selector as descendant:

```css
/* Wrong in native CSS — parses as .list li descendant .active */
.list li {
  .active { color: red; }
}

/* Correct */
.list li {
  &.active { color: red; }
}
```

Sass allowed implicit `&` compounding; native CSS is stricter.

## Specificity

Nested rules add specificity same as flat CSS—nesting does not reduce weight. Deep nesting still creates heavy selectors:

```css
/* Avoid */
.page {
  .section {
    .card {
      .title { color: blue; } /* 0,4,0 specificity */
    }
  }
}
```

Prefer flat BEM or single-level nesting for maintainability.

## @nest vs implicit nesting

Older spec used `@nest` rule—deprecated in favor of implicit nesting shown above.

## Migration from Sass

| Sass | Native CSS |
|------|------------|
| `$var` | CSS custom properties `--var` |
| `@mixin` | Not available—use classes or @layer |
| `#{}` interpolation | Limited—no selector interpolation |
| Nested `@include` | Copy or use @layer |

Run `sass-to-css` migration with manual `&` audit on compound selectors.

## The Sass-to-native migration path

Teams dropping Sass for native nesting should treat it as a linting exercise, not a find-replace. Start with leaf components — buttons, cards, form fields — where nesting depth is one level. Run both pipelines in parallel during transition:

```css
/* postcss.config.js — dual support during migration */
{
  "plugins": {
    "postcss-nesting": {}  /* compiles for older browsers; passthrough for modern */
  }
}
```

Audit checklist for each nested file:

1. Every `:hover`, `:focus`, `:active` on a compound selector needs `&` prefix
2. BEM modifiers (`&--error`) and states (`&.is-active`) — verify compiled output
3. Nested `@media` blocks — valid in native nesting, no change needed
4. Nested `@keyframes` — supported; nested `@import` — not inside rules
5. Sass `&-suffix` parent selector suffix — rewrite explicitly

Sass variables become custom properties at the component root:

```css
.card {
  --card-padding: 1rem;
  padding: var(--card-padding);

  @media (min-width: 768px) {
    --card-padding: 2rem;
  }
}
```

Mixins don't port — extract repeated patterns into utility classes in `@layer utilities` or shared component classes.

## Nesting depth guidelines

Deep nesting was a Sass anti-pattern that native nesting doesn't fix — it makes specificity worse:

| Depth | Verdict |
|---|---|
| 1 level (pseudo-classes, modifiers) | Preferred |
| 2 levels (component + element) | Acceptable for small components |
| 3+ levels | Refactor to flat BEM or CSS Modules |

```css
/* Prefer */
.card { }
.card__title { }
.card--featured { }

/* Over nested */
.card {
  .header {
    .title { /* 0,3,0 — hard to override */ }
  }
}
```

CSS Modules and shadow DOM remain valid scoping strategies. Native nesting complements them — you can nest pseudo-classes inside a Module class without reaching for `:global`.

## Interaction with :is(), :where(), and :has()

Nesting combines cleanly with modern selectors:

```css
.form-group {
  &:has(:invalid) {
    border-color: var(--error);
  }

  &:where(:not(.form-group--inline)) {
    margin-bottom: 1rem;
  }
}
```

`:where()` inside nested rules keeps specificity at the parent's level — useful for optional spacing variants without specificity inflation.

## Common failure modes

- **Missing `&` on pseudo-class** — `:hover` without `&` creates a descendant selector `.button :hover` (any hovered descendant) instead of `.button:hover`
- **Specificity wars return** — nesting doesn't reduce weight; `@layer` is the fix for priority, not shallower selectors
- **PostCSS vs native divergence** — PostCSS nesting plugin may accept syntax native browsers reject. Test in target browsers without PostCSS in CI
- **@keyframes name collisions** — nested keyframes are scoped to the stylesheet, not the selector; naming still needs discipline

## Browser support strategy

Target evergreen-only internal tools? Drop PostCSS nesting entirely. Public-facing sites with legacy browser requirements: keep PostCSS as compile step, write native-compatible syntax so you can drop the plugin when analytics show <1% on unsupported browsers.

Feature query for progressive enhancement:

```css
@supports selector(&) {
  /* Native nesting path confirmed */
}
```

## Production checklist

- `&` on all compound pseudo-class and modifier selectors
- Nesting depth ≤ 2 levels in component styles
- Sass mixins replaced with utilities or component classes
- PostCSS output tested against native browser parsing
- Specificity reviewed — pair with `@layer` for priority control
- Custom properties replace Sass variables at component root

Native nesting is one piece of a modern CSS stack — pair it with `@layer` for cascade priority and container queries for component responsiveness. Together they replace most of what teams reached for Sass to solve.

For greenfield projects in 2025, the default stack is native nesting + cascade layers + container queries — no Sass, no PostCSS nesting plugin, no build-step surprises. Keep PostCSS in the pipeline only for autoprefixer and future syntax you opt into deliberately.

Lint with `stylelint` rules that flag descendant selectors missing `&` — catches the most common migration bug before it reaches production. Add a CI step that diffs compiled output against native browser parsing for any file touched in a PR.

## Tooling

```json
// postcss.config.js — fallback only
{
  "plugins": {
    "postcss-nesting": {}
  }
}
```

Vite and modern bundlers pass through native nesting to supported browsers.

## Resources

- [CSS Nesting Module spec](https://www.w3.org/TR/css-nesting-1/)
- [MDN CSS nesting](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_nesting)
- [web.dev — CSS nesting](https://web.dev/articles/css-nesting)
- [Can I use CSS nesting](https://caniuse.com/css-nesting)
