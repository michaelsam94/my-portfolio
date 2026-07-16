---
title: "Modern Color with OKLCH"
slug: "web-color-functions-oklch"
description: "Use OKLCH color in CSS for perceptually uniform palettes: syntax, comparison with HSL and LCH, wide-gamut support, and building accessible color systems."
datePublished: "2026-03-15"
dateModified: "2026-03-15"
tags: ["Web", "CSS", "Design", "Frontend"]
keywords: "OKLCH, CSS color, perceptual color, wide gamut, color palette, P3, LCH, color contrast"
faq:
  - q: "What is OKLCH and why is it better than HSL for CSS?"
    a: "OKLCH is a perceptual color space where L is lightness, C is chroma (saturation), and H is hue. Unlike HSL, where yellow at 50% lightness looks much brighter than blue at 50% lightness, OKLCH lightness values produce visually uniform results across all hues. This makes it practical to generate color palettes by adjusting L and C while keeping perceived brightness consistent, which is essential for accessible design systems."
  - q: "Can I use OKLCH in production browsers?"
    a: "Yes. OKLCH is supported in all modern browsers as of 2024: Chrome 111+, Firefox 113+, Safari 15.4+, and Edge 111+. Provide HSL or hex fallbacks for older browsers using @supports or the cascade. In 2026, baseline support covers over 95% of users globally, making OKLCH viable as the primary color format with hex fallbacks only for legacy environments."
  - q: "How does OKLCH help with wide-gamut displays?"
    a: "OKLCH can express colors beyond the sRGB gamut that HSL and hex cannot represent. On displays supporting Display P3 or Rec.2020, OKLCH colors with high chroma values render as more vivid, saturated colors. The browser automatically clamps to the display's gamut. This means a single OKLCH definition looks good on both standard and wide-gamut screens, with wide-gamut displays showing richer colors automatically."
---

I generated a palette in HSL: ten hues at 50% saturation and 50% lightness. Yellow screamed. Blue whispered. Purple looked fine. The palette was mathematically consistent and visually a mess. HSL's lightness axis doesn't match human perception — it's based on the underlying RGB model, not how bright colors actually look. OKLCH fixes this by using a perceptually uniform space where equal L values look equally bright regardless of hue. It's the color format CSS has needed for decades, and it's finally usable in production.

## OKLCH syntax

```css
.element {
  color: oklch(0.62 0.19 250);    /* lightness chroma hue */
  background: oklch(0.95 0.02 250);
  border-color: oklch(0.45 0.15 250);
}
```

- **L** (lightness): 0 to 1 (or 0% to 100%). Perceptually uniform.
- **C** (chroma): 0 to ~0.4 for sRGB. Higher values may exceed sRGB gamut.
- **H** (hue): 0 to 360 degrees, same as HSL.

Optional alpha: `oklch(0.62 0.19 250 / 0.5)`

## Perceptual uniformity in practice

Same lightness, different hues — all look equally bright:

```css
--red:    oklch(0.65 0.2 25);
--orange: oklch(0.65 0.2 65);
--yellow: oklch(0.65 0.2 100);
--green:  oklch(0.65 0.2 145);
--blue:   oklch(0.65 0.2 250);
--purple: oklch(0.65 0.2 300);
```

In HSL, `hsl(60, 100%, 50%)` (yellow) looks neon while `hsl(240, 100%, 50%)` (blue) looks dark. In OKLCH, both at L=0.65 look like they have the same visual weight.

## Building a color scale

Generate a systematic palette by varying lightness with fixed chroma and hue:

```css
:root {
  --blue-50:  oklch(0.97 0.02 250);
  --blue-100: oklch(0.93 0.04 250);
  --blue-200: oklch(0.87 0.08 250);
  --blue-300: oklch(0.78 0.12 250);
  --blue-400: oklch(0.68 0.16 250);
  --blue-500: oklch(0.58 0.19 250);
  --blue-600: oklch(0.50 0.18 250);
  --blue-700: oklch(0.42 0.16 250);
  --blue-800: oklch(0.35 0.13 250);
  --blue-900: oklch(0.28 0.10 250);
}
```

Each step is visually equidistant. In HSL, you'd need to hand-tune every step because the perceptual distance between 90% and 80% lightness varies by hue.

## Comparison with other color formats

| Format | Perceptually uniform | Wide gamut | Browser support |
|---|---|---|---|
| Hex/RGB | No | No | Universal |
| HSL | No | No | Universal |
| LCH | Yes | Yes | Modern browsers |
| OKLCH | Yes (better than LCH) | Yes | Modern browsers |
| Display P3 | N/A | Yes | Safari, Chrome |
| color-mix() | Depends on space | Depends | Modern browsers |

OKLCH improves on LCH by using a better lightness model (Oklab) that handles blue hues more accurately. LCH's lightness is distorted in the blue region, which is why OKLCH is preferred for CSS.

## Wide-gamut colors

On P3 displays, OKLCH can render colors more vivid than sRGB allows:

```css
.vivid {
  /* This blue is more saturated than any sRGB hex can express */
  color: oklch(0.55 0.25 250);
}
```

The browser clamps to the display's available gamut. On sRGB screens, it renders the closest sRGB equivalent. On P3 screens, you get the full saturation. One definition, adaptive rendering.

Check gamut support:

```css
@supports (color: oklch(0 0 0)) {
  .accent { color: oklch(0.55 0.25 250); }
}
@supports not (color: oklch(0 0 0)) {
  .accent { color: #2563eb; } /* sRGB fallback */
}
```

## Accessible contrast with OKLCH

Because L is perceptually uniform, contrast ratios are predictable from lightness values:

```css
/* Text on background: aim for L difference ≥ 0.4 for WCAG AA */
--text:       oklch(0.20 0.02 250);  /* dark text */
--background: oklch(0.98 0.01 250);  /* light background */
/* L difference: 0.78 → passes AA and AAA */
```

Generate accessible pairs programmatically:

```javascript
function contrastPair(hue, chroma) {
  return {
    text:       `oklch(0.20 ${chroma} ${hue})`,
    background: `oklch(0.97 ${chroma * 0.3} ${hue})`,
    accent:     `oklch(0.55 ${chroma} ${hue})`,
    accentText: `oklch(0.98 0.01 ${hue})`,
  };
}
```

## color-mix with OKLCH

Blend colors in perceptual space:

```css
.element {
  /* Mix blue and white in OKLCH for a perceptually correct tint */
  background: color-mix(in oklch, oklch(0.55 0.2 250) 25%, white);
}
```

`color-mix(in srgb, ...)` produces muddy midpoints. `color-mix(in oklch, ...)` produces clean tints and shades.

## Migrating from HSL/hex

Convert existing colors with DevTools or tools:

1. Chrome DevTools color picker supports OKLCH — paste a hex value and read the OKLCH equivalent
2. [oklch.com](https://oklch.com) — interactive OKLCH picker with gamut visualization
3. Build new palettes in OKLCH; keep hex as fallback

```css
:root {
  --primary: #3b82f6;                          /* fallback */
  --primary: oklch(0.62 0.19 250);             /* override */
}
```

The cascade handles fallback automatically — browsers that don't understand OKLCH use the hex.

## Common production mistakes

Teams get color functions oklch wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of color functions oklch fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When color functions oklch misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [oklch.com color picker](https://oklch.com/)
- [CSS Color Module Level 4](https://www.w3.org/TR/css-color-4/)
- [OKLCH in CSS (Evil Martians)](https://evilmartians.com/chronicles/oklch-in-css-why-quit-rgb-hsl)
- [Can I use OKLCH](https://caniuse.com/mdn-css_types_color_oklch)
- [colorjs.io conversion library](https://colorjs.io/)
