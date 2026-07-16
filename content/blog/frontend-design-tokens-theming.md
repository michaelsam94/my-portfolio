---
title: "Design Tokens and Theming"
slug: "frontend-design-tokens-theming"
description: "Design tokens are named design decisions as data—color, spacing, typography—consumed by CSS, React, and Figma from one source. Implementation patterns that scale."
datePublished: "2025-04-10"
dateModified: "2025-04-10"
tags: ["Web", "Frontend", "Design Systems", "CSS"]
keywords: "design tokens, CSS custom properties theming, design system tokens, Style Dictionary, semantic tokens"
faq:
  - q: "Design tokens vs CSS variables—what is the difference?"
    a: "Tokens are platform-agnostic names and values (JSON); CSS custom properties are one output format. You might also emit Swift, Kotlin, or Tailwind config from the same token file. Variables implement tokens in the browser."
  - q: "Should I use primitive or semantic token names?"
    a: "Both layers: primitives (blue-500, space-4) and semantics (color-text-primary, spacing-card-padding) referencing primitives. Components consume semantics so re-theming changes mappings, not every button file."
  - q: "How do teams sync Figma and code tokens?"
    a: "Figma Variables/Tokens Studio export JSON; Style Dictionary or Tokens Studio pipeline transforms to CSS/TS. CI fails if Figma export drifts from repo—treat tokens like code."
---

The rebrand changed primary blue once. Without tokens, we grep-replaced `#2563EB` and missed four hex variants in dark mode SCSS. With tokens, `color.action.primary` updated in `tokens.json`; CSS, React, and Storybook picked it up on next build. Design tokens are the API between design and engineering.

## Token layers

```
Primitive:   color.blue.600 = #2563EB
Semantic:    color.text.link = {color.blue.600}
Component:   button.primary.background = {color.text.link}  (optional)
```

Components reference semantics; dark theme swaps semantic mappings:

```json
{
  "color": {
    "surface": {
      "default": { "value": "{color.neutral.0}" }
    },
    "text": {
      "primary": { "value": "{color.neutral.900}" }
    }
  }
}
```

Dark theme file overrides `surface.default` to `{color.neutral.900}`.

## CSS custom properties output

Build step emits:

```css
:root {
  --color-surface-default: #ffffff;
  --color-text-primary: #111827;
  --space-4: 1rem;
  --font-size-body: 1rem;
}

[data-theme="dark"] {
  --color-surface-default: #111827;
  --color-text-primary: #f9fafb;
}
```

Consume in components:

```css
.card {
  background: var(--color-surface-default);
  padding: var(--space-4);
  color: var(--color-text-primary);
}
```

## TypeScript consumption

```typescript
export const tokens = {
  color: {
    textPrimary: 'var(--color-text-primary)',
  },
  space: {
    md: 'var(--space-4)',
  },
} as const;
```

```tsx
<div style={{ color: tokens.color.textPrimary, padding: tokens.space.md }} />
```

Or generate typed constants from JSON with Style Dictionary.

## Style Dictionary pipeline

```json
// tokens/color.json
{
  "color": {
    "brand": {
      "primary": { "value": "#2563EB" }
    }
  }
}
```

```javascript
// style-dictionary.config.js
module.exports = {
  source: ['tokens/**/*.json'],
  platforms: {
    css: {
      transformGroup: 'css',
      buildPath: 'dist/css/',
      files: [{ destination: 'variables.css', format: 'css/variables' }],
    },
  },
};
```

Run in CI on token PRs.

## React theming integration

```tsx
const ThemeProvider = ({ theme, children }) => (
  <div data-theme={theme}>{children}</div>
);
```

With CSS-in-JS (styled-components, Emotion), inject token object into `ThemeProvider` matching CSS variable values for hybrid setups.

Tailwind v4 supports CSS variables as theme extension—map tokens to `@theme` block.

## Spacing and typography scales

Use modular scales—not one-off pixels:

| Token | Value |
|-------|-------|
| space-1 | 0.25rem |
| space-4 | 1rem |
| font-size-sm | 0.875rem |
| font-size-lg | 1.125rem |

Document line-height pairs with font sizes in same token group.

## Governance

- Token PRs require design review
- Deprecate tokens with alias period (`color.old-name` → `color.new-name`)
- Version token package separately if multiple apps consume

## Token naming conventions

Use dot notation in JSON, kebab in CSS:

```json
{ "color": { "text": { "primary": { "value": "{color.neutral.900}" } } } }
```

```css
--color-text-primary: #111827;
```

Document naming in ADR—consistency beats cleverness.

## Multi-brand theming

```html
<html data-brand="acme" data-theme="dark">
```

Switch `data-brand` loads alternate token file or CSS layer—white-label SaaS pattern.

## Accessibility tokens

Define `focus-ring`, `min-touch-target`, and contrast-paired text/surface tokens—audit with axe in Storybook per theme.

## Versioning tokens package

Publish `@company/design-tokens` semver—breaking renames major bump; codemod consumer CSS variable renames in monorepo.


## Toolchain integration

Wire Style Dictionary into CI: PR touching `tokens/**/*.json` runs build and fails if CSS output diff not committed (or auto-commits to artifact branch—pick policy). Designers export from Figma Tokens Studio; engineers review JSON diff like code.

Storybook displays all semantic tokens on Docs page—design QA compares Figma swatch to rendered component side by side each release.

## Dark mode and high contrast

Ship `data-theme="dark"` and optional `data-contrast="high"` layers—high contrast remaps semantic tokens to WCAG AAA pairs without forking entire component library.

Test tokens against real components, not only swatch page—`color.text.secondary` on `color.surface.container` fails contrast more often than designers expect.

## Migration from hardcoded values

Codemod pass: grep `#2563EB` and `--legacy-blue` replacements; run visual regression on top twenty screens. Keep legacy aliases one release:

```css
--legacy-primary: var(--color-action-primary);
```

Remove aliases when Sentry/console shows zero deprecated variable warnings.

## Performance

Thousands of CSS variables do not hurt runtime—avoid generating per-component tokens (button-primary-padding-left) unless build pipeline automates; semantic groups stay human-maintainable (~80-150 tokens typical mid-size app).

## Color space

Define tokens in OKLCH for perceptual uniformity when generating palettes—convert to hex for CSS output in Style Dictionary transform custom plugin.

## Rollout guidance

Token breaking rename ships codemod script in tools/ directory executed once developers pull main—CI fails old token CSS variable references grep pattern until codemod run committed.

Cross-functional review includes design for UX-facing work, security for auth or storage, and platform for native bridges. Token changes that affect spacing, color contrast, or touch targets need design sign-off before merge.

## Dark mode and theme switching

Apply themes via `data-theme` attribute, not class toggling on `<body>`:

```css
:root, [data-theme="light"] {
  --color-bg: var(--token-color-neutral-0);
  --color-text: var(--token-color-neutral-900);
}
[data-theme="dark"] {
  --color-bg: var(--token-color-neutral-900);
  --color-text: var(--token-color-neutral-0);
}
```

Avoid flash of wrong theme — inline script in `<head>` reads `localStorage` before paint. Test contrast ratios in both themes with automated axe checks in CI.

## Token governance at scale

| Role | Responsibility |
|------|----------------|
| Design | Owns Figma token source, approves new tokens |
| Platform | Style Dictionary pipeline, CI validation |
| Product teams | Consume tokens, propose additions via RFC |
| Accessibility | Reviews contrast and motion token changes |

Staging soaks 24 hours for risky token changes while dashboards watch error rates. Canary internal staff first, then 5% production, then full rollout if crash-free sessions hold within baseline tolerance.

## Common production mistakes

Teams get frontend design tokens theming wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of frontend design tokens theming fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [Design Tokens Community Group spec](https://designtokens.org/)
- [Style Dictionary](https://amzn.github.io/style-dictionary/)
- [Tokens Studio for Figma](https://tokens.studio/)
- [CSS custom properties (MDN)](https://developer.mozilla.org/en-US/docs/Web/CSS/Using_CSS_custom_properties)
- [Material Design tokens](https://m3.material.io/foundations/design-tokens/overview)
