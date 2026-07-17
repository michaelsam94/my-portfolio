---
title: "APCA Color Contrast for Agent-Generated UIs"
slug: "agent-color-contrast-apca"
description: "Replace WCAG 2.x ratio checks with APCA perceptual contrast for agent-built interfaces: Lc thresholds, polarity, CI gates, and accessible theme generation."
datePublished: "2026-06-28"
dateModified: "2026-06-28"
tags: ["Accessibility", "Design Systems", "AI Agents", "CSS"]
keywords: "APCA contrast, accessible perceptual contrast algorithm, agent UI generation, WCAG 3 contrast, color contrast CI"
faq:
  - q: "Why does APCA replace WCAG 2.x contrast ratio for agent-generated UIs?"
    a: "WCAG 2.x uses a simple luminance ratio that mis-ranks many real color pairs — especially dark mode, thin text, and colored backgrounds. APCA models perceptual lightness and polarity (light-on-dark vs dark-on-light) separately, producing scores that correlate better with readability. Agents that auto-pick colors need a metric that matches human perception, not a 20-year-old formula."
  - q: "What Lc score should body text target in APCA?"
    a: "For fluent body text (≥16px regular weight), target Lc 75+ on the intended background. Large bold headings can pass at Lc 60. Non-text UI boundaries and icons often need Lc 45–60 depending on size. Always validate with the actual font size and weight — APCA is not font-size-agnostic."
  - q: "Can I run APCA checks in CI for every agent-generated theme?"
    a: "Yes. Parse computed CSS custom properties or design-token JSON, run APCA per text/background pair with declared font metadata, and fail the build on pairs below threshold. Cache token snapshots so agent theme diffs produce deterministic reports. Pair with axe-core for structural a11y; APCA covers the color leg."
  - q: "Does APCA work for transparent overlays and gradients?"
    a: "APCA expects a single effective background color. For alpha compositing, flatten foreground over background first (same as WCAG). Gradients need per-stop evaluation or worst-case sampling at text bounding boxes. Agents should prefer solid surfaces behind text rather than text directly on gradients."
---

LLM agents that generate dashboards, chat widgets, and inline forms increasingly pick their own color palettes. A theme that passes `contrast-ratio: 4.5:1` in DevTools can still fail real users — especially in dark mode, with thin weights, or on saturated brand backgrounds. **APCA** (Accessible Perceptual Contrast Algorithm), headed toward WCAG 3, measures contrast the way vision works: lightness perception, polarity, and font size all matter.

If you gate agent UI output on WCAG 2.x alone, you will ship illegible combinations that technically pass. APCA fixes most of those false positives and false negatives — but only if you integrate it into token generation, not as a manual spot check after launch.

## WCAG 2.x vs APCA in practice

WCAG 2.x contrast ratio compares relative luminance of two sRGB colors:

```
ratio = (L1 + 0.05) / (L2 + 0.05)   where L1 > L2
```

APCA returns a signed **Lc** value (lightness contrast):

- **Positive Lc**: dark text on light background
- **Negative Lc**: light text on dark background
- **Magnitude**: higher absolute value = more readable

| Scenario | WCAG 2.x | APCA Lc | Human read |
|----------|----------|---------|------------|
| #777 on #fff body text | Pass 4.6:1 | Lc ~62 | Marginal — APCA flags caution |
| #fff on #0080ff button | Pass 4.5:1 | Lc ~48 | Fail for small text |
| 14px #aaa on #1a1a1a | Fail 4.5:1 | Lc ~-72 | Pass for large bold only |

Agents optimising for "pass WCAG" will converge on mathematically valid but perceptually weak pairs. Switch the objective function to APCA Lc thresholds.

## Computing APCA in your pipeline

Use the reference implementation via `apca-w3` (npm) or port the published coefficients. Core steps:

1. Convert sRGB to linear RGB
2. Compute perceptual lightness (Y) for text and background
3. Apply polarity-specific exponents and clamps
4. Return signed Lc

```typescript
import { calcAPCA, sRGBtoY, alphaBlend } from "apca-w3";

interface ContrastCheckInput {
  foreground: string;       // hex or rgb
  background: string;
  fontSizePx: number;
  fontWeight: number;       // 400, 600, 700
  isLargeText?: boolean;
}

interface ContrastResult {
  lc: number;
  passes: boolean;
  requiredLc: number;
  polarity: "dark-on-light" | "light-on-dark";
}

function requiredLc(fontSizePx: number, fontWeight: number): number {
  const isBold = fontWeight >= 700 || (fontWeight >= 600 && fontSizePx >= 16);
  const isLarge = fontSizePx >= 24 || (fontSizePx >= 18.66 && isBold);
  if (isLarge) return 60;
  return 75;  // fluent body text baseline
}

export function checkApcaContrast(input: ContrastCheckInput): ContrastResult {
  const fgY = sRGBtoY(input.foreground);
  const bgY = sRGBtoY(input.background);
  const lc = calcAPCA(fgY, bgY);
  const required = requiredLc(input.fontSizePx, input.fontWeight);

  return {
    lc,
    passes: Math.abs(lc) >= required,
    requiredLc: required,
    polarity: lc >= 0 ? "dark-on-light" : "light-on-dark",
  };
}

// Alpha compositing before check
export function checkOnSurface(
  textColor: string,
  overlayColor: string,
  baseSurface: string,
  fontSizePx: number,
  fontWeight: number
): ContrastResult {
  const effectiveBg = alphaBlend(overlayColor, baseSurface);
  return checkApcaContrast({
    foreground: textColor,
    background: effectiveBg,
    fontSizePx,
    fontWeight,
  });
}
```

Always pass **actual** font size and weight from the component spec. APCA thresholds vary; treating all text as "body" hides failures on captions and labels.

## Design tokens agents should emit

Agent-generated themes should output structured tokens, not raw hex scattered in CSS:

```json
{
  "color": {
    "surface": {
      "default": { "value": "#0f1419", "type": "color" },
      "raised":  { "value": "#1a2332", "type": "color" }
    },
    "text": {
      "primary":   { "value": "#e7ecf3", "type": "color", "on": "surface.default" },
      "secondary": { "value": "#9aa8b8", "type": "color", "on": "surface.default" }
    },
    "accent": {
      "primary": { "value": "#3d8bfd", "type": "color" }
    }
  },
  "typography": {
    "body":  { "fontSize": "16px", "fontWeight": 400 },
    "label": { "fontSize": "13px", "fontWeight": 500 }
  }
}
```

Validation script walks `text.*.on` pairs:

```typescript
function validateThemeTokens(theme: ThemeTokens): Violation[] {
  const violations: Violation[] = [];

  for (const [name, token] of Object.entries(theme.color.text)) {
    const bgToken = theme.color.surface[token.on.replace("surface.", "")];
    const typo = theme.typography[token.typoRef ?? "body"];
    const result = checkApcaContrast({
      foreground: token.value,
      background: bgToken.value,
      fontSizePx: parseFloat(typo.fontSize),
      fontWeight: typo.fontWeight,
    });
    if (!result.passes) {
      violations.push({ pair: `text.${name}/surface`, lc: result.lc, required: result.requiredLc });
    }
  }
  return violations;
}
```

## Auto-fix strategies for agents

When an agent proposes a palette that fails APCA, repair before render — do not ask the user to pick different hex values manually.

**Strategy 1 — adjust lightness only (preserve hue):**

```typescript
function nudgeToPassApca(
  fg: string,
  bg: string,
  fontSizePx: number,
  fontWeight: number,
  maxSteps = 20
): string {
  let candidate = fg;
  for (let i = 0; i < maxSteps; i++) {
    const { passes } = checkApcaContrast({ foreground: candidate, background: bg, fontSizePx, fontWeight });
    if (passes) return candidate;
    candidate = adjustOkLchLightness(candidate, bg, +4); // move away from bg in OKLCH
  }
  throw new Error("Cannot reach APCA threshold without leaving brand gamut");
}
```

**Strategy 2 — swap polarity**: if light-on-dark fails on a dark surface, try a raised surface token behind text instead of changing text color.

**Strategy 3 — constrain agent prompt**: provide a pre-validated palette in the system prompt and forbid arbitrary hex. Agents are better at composing with tokens than inventing accessible colors from scratch.

## CI integration

Add a job that runs on every PR touching `tokens/` or agent theme output:

```yaml
# .github/workflows/apca-contrast.yml
jobs:
  apca:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npm run tokens:build
      - run: node scripts/validate-apca.mjs --strict
      - run: node scripts/validate-apca.mjs --report=apca-violations.json
      - uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: apca-violations
          path: apca-violations.json
```

`--strict` fails on any sub-threshold pair. Upload artifacts on failure so designers see exact token pairs without reproducing locally.

For Storybook-driven component libraries, add a test per story:

```typescript
// apca.stories.test.ts
import { composeStories } from "@storybook/react";
import * as stories from "./Button.stories";

const composed = composeStories(stories);

describe("APCA contrast", () => {
  test.each(Object.entries(composed))("%s meets Lc thresholds", async (_name, Story) => {
    const { container } = render(<Story />);
    const violations = scanDomForApcaViolations(container);
    expect(violations).toEqual([]);
  });
});
```

## Dark mode and forced colors

Dark mode is where WCAG 2.x false passes cluster. Rules for agents:

- Never reuse light-mode text tokens on dark surfaces without re-validation.
- Prefer **surface elevation** (lighter layers stacked on darker base) over bright text on pure black — APCA handles mid-tone backgrounds more predictably.
- Test `prefers-contrast: more` and Windows High Contrast: APCA does not replace system forced-colors media queries; provide `@media (forced-colors: active)` overrides.

```css
@media (forced-colors: active) {
  .agent-card {
    border: 1px solid CanvasText;
    background: Canvas;
    color: CanvasText;
  }
}
```

## Agent prompt guardrails

System prompt excerpt for UI-generating agents:

```
COLOR RULES (mandatory):
- Use only tokens from the provided theme JSON.
- Do not invent hex colors.
- Primary text must use color.text.primary on its declared surface.
- If a combination fails APCA Lc 75 for body text, call adjust_theme_contrast tool before returning JSX.
- For buttons: text on accent.primary must pass Lc 60 minimum at button font size (14px semibold).
```

Expose `adjust_theme_contrast` as a tool the agent calls programmatically — not a suggestion.

## Monitoring in production

Client-side sampling catches theme drift from A/B flags or tenant overrides:

```typescript
function sampleApcaAudit(sampleRate = 0.01) {
  if (Math.random() > sampleRate) return;
  const violations = scanDomForApcaViolations(document.body);
  if (violations.length > 0) {
    telemetry.send("apca_violation", { count: violations.length, samples: violations.slice(0, 5) });
  }
}
```

Alert when violation rate exceeds baseline — often indicates a bad theme deploy or agent override path bypassing token validation.

## The takeaway

Agent-generated UIs need perceptual contrast gates, not legacy ratio checkboxes. Integrate APCA at token validation, CI, and agent tool boundaries; preserve hue via OKLCH nudging when auto-fixing; and treat font metadata as part of the contrast contract. Users with low vision should not be the first testers of your agent's color choices.

## Resources

- [APCA Readability Criterion (WCAG 3 draft)](https://readtech.org/ARC/)
- [apca-w3 npm package](https://www.npmjs.com/package/apca-w3)
- [Inclusively Hidden — APCA introduction](https://www.myndex.com/APCA/)
- [OKLCH color adjustments for accessible palettes](https://developer.chrome.com/docs/css-ui/accessibility-colors)
- [W3C Silver Task Force contrast research](https://www.w3.org/WAI/GL/task-forces/silver/wiki/Contrast_Research)
