---
title: "AI Agents: Accessibility Automated Axe"
slug: "agent-accessibility-automated-axe"
description: "axe-core catches a meaningful slice of WCAG violations before they reach users — but only if you wire it into CI with the right rules, scopes, and triage workflow for dynamic UIs."
datePublished: "2026-06-19"
dateModified: "2026-06-19"
tags: ["AI", "Agent", "Accessibility"]
keywords: "axe-core, accessibility testing, WCAG, automated a11y, Playwright, CI pipeline, Deque, aria, screen reader"
faq:
  - q: "What percentage of accessibility issues can axe detect automatically?"
    a: "Deque and industry studies consistently cite roughly 30–57% of WCAG issues as automatable, depending on page complexity and conformance target. axe-core covers a large share of automatable rules, but manual testing remains required for focus order, meaningful sequence, cognitive load, and most ARIA authoring mistakes in custom widgets."
  - q: "Should axe failures block CI merges?"
    a: "Block on impact levels you can enforce without drowning in legacy debt. A common rollout: warn-only for 30 days while fixing critical/serious violations, then fail CI on critical and serious. Never silently ignore moderate rules on new components — scope rules to changed files if the full site baseline is noisy."
  - q: "Why do axe tests pass locally but fail in CI?"
    a: "Typical causes: CI runs before content loads (missing waitFor/ network idle), different viewport sizes hiding mobile-only components, dark-mode or reduced-motion variants not tested, fonts not loaded (affecting color contrast calculations), and shadow DOM content not included in the scan scope."
  - q: "How is axe different from Lighthouse accessibility audits?"
    a: "Both use axe under the hood for many rules, but Lighthouse samples a single page load with throttling and mixes a11y with performance SEO. axe-core in your test suite lets you scan specific components, run against authenticated states, configure rule tags (WCAG 2.1 AA), and integrate with custom reporters tied to PR diffs."
---
Automated accessibility testing will not make your product accessible. It will stop you from shipping the same five bugs on every pull request — missing button labels, images without alt text, contrast ratios that fail in production lighting conditions, form fields with no associated labels.

axe-core, maintained by Deque Systems, is the de facto engine inside that guardrail. It powers Lighthouse, many CI plugins, and browser extensions. The engineering question is not "should we use axe" but "how do we integrate it so developers fix violations instead of muting rules."

## The rule stack: what axe actually checks

axe organizes checks into rules mapped to WCAG success criteria. Each violation includes:

- **Impact**: critical, serious, moderate, minor
- **Help URL**: links to Deque University remediation guidance
- **Selectors**: DOM nodes implicated (when determinable)

Automatable rules include:

- Missing accessible names on interactive elements
- Invalid ARIA attributes and roles
- Insufficient color contrast (with computed styles)
- Duplicate IDs
- Empty headings and links
- Missing document language
- Form inputs without labels

Not automatable (manual or assistive-tech testing required):

- Logical focus order vs visual order
- Whether alt text is *meaningful*
- Whether custom combobox keyboard behavior matches APG patterns
- Whether error messages are understandable

Treat axe as a linter for accessibility, not a certificate of compliance.

## Layering axe into the test pyramid

```
                    ┌─────────────────────┐
                    │ Manual + AT testing │  (screen reader, keyboard)
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ E2E axe on flows    │  (checkout, signup)
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ Component axe       │  (Storybook, unit)
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ ESLint jsx-a11y       │  (static, pre-commit)
                    └─────────────────────┘
```

Static analysis catches mistakes before render. Component-level axe catches composition bugs (nested interactive elements). E2E axe catches routing, lazy loading, and CMS content issues static tools never see.

## Component tests with Playwright and @axe-core/playwright

```typescript
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.describe("Checkout accessibility", () => {
  test("payment step has no critical violations", async ({ page }) => {
    await page.goto("/checkout/payment");
    await page.waitForSelector('[data-testid="pay-button"]', { state: "visible" });

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .exclude('[data-testid="third-party-widget"]') // document exclusions
      .analyze();

    const blocking = results.violations.filter(
      (v) => v.impact === "critical" || v.impact === "serious"
    );

    expect(
      blocking,
      formatViolations(blocking)
    ).toHaveLength(0);
  });
});

function formatViolations(violations: AxeResults["violations"]): string {
  return violations
    .map(
      (v) =>
        `[${v.impact}] ${v.id}: ${v.description}\n` +
        v.nodes.map((n) => `  ${n.target.join(" ")}`).join("\n")
    )
    .join("\n\n");
}
```

The `waitForSelector` line matters. axe scans the DOM as-is; skeleton screens and spinner-only buttons produce false violations (empty buttons) or miss real ones (content loaded after scan).

## Storybook integration for faster feedback

Running axe on every story catches regressions where components are reused in new contexts:

```typescript
// storybook/preview.ts
import { axe, toHaveNoViolations } from "jest-axe";
import { expect } from "@storybook/jest";

expect.extend(toHaveNoViolations);

// In story play function:
export const Primary: Story = {
  play: async ({ canvasElement }) => {
    const results = await axe(canvasElement, {
      rules: {
        "color-contrast": { enabled: true },
        region: { enabled: false }, // disable page-level rules in isolation
      },
    });
    await expect(results).toHaveNoViolations();
  },
};
```

Disable page-level rules (`region`, `bypass`) for isolated components — they assume a full document structure.

## Rule configuration without silencing everything

Teams drowning in violations reach for `disable` rules globally. That trades CI green for false confidence. Prefer:

**Tag-based scoping.** Run `wcag21aa` in CI, add `best-practice` as warnings only.

**Per-file overrides with justification.** Require a comment linking to a ticket when disabling a rule.

**Differential scanning.** Scan only routes affected by the PR using changed-file detection from your monorepo graph.

```javascript
// axe.config.ci.js
module.exports = {
  runOnly: {
    type: "tag",
    values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"],
  },
  rules: {
    // Flaky third-party embed — tracked in A11Y-441
    "frame-title": { enabled: false },
  },
  reporter: "v2",
};
```

Document every disabled rule in an accessibility debt register with owner and remediation date.

## Dynamic content and SPAs

Single-page apps break naive axe runs because:

1. Route transitions do not reload the document
2. Modals mount outside the main tree
3. Infinite scroll adds nodes after initial scan

Pattern: scan after navigation settles, include open modal states as separate test cases.

```typescript
test("delete confirmation dialog is accessible", async ({ page }) => {
  await page.goto("/settings/account");
  await page.getByRole("button", { name: "Delete account" }).click();
  await page.getByRole("dialog").waitFor();

  const results = await new AxeBuilder({ page })
    .include('[role="dialog"]')
    .analyze();

  expect(results.violations).toHaveLength(0);
});
```

For focus management, pair axe with explicit keyboard tests — axe does not verify focus moved into the dialog.

## Shadow DOM and web components

axe-core traverses open shadow roots by default. Closed shadow roots are invisible to any automated tool. If your design system uses closed mode, expose test hooks or run manual AT passes on those components.

```typescript
const results = await new AxeBuilder({ page })
  .include("my-design-system-button")
  .analyze();
```

Custom elements must expose accessible names via `aria-label`, `aria-labelledby`, or text content in the light DOM.

## AI-generated UI and accessibility debt

Teams shipping LLM-generated interfaces face a predictable violation cluster:

- Clickable `<div>` elements without roles or keyboard handlers
- Placeholder alt text ("image") on generated illustrations
- Heading levels skipped (h1 → h4) because the model flattened structure
- Color pairs that pass in the IDE theme but fail on the production dark mode

If agents produce JSX, run axe in the generation pipeline before the PR opens — not after merge. Pair with eslint-plugin-jsx-a11y on the generated output template.

## Triage workflow that developers actually follow

Violations without ownership rot. A workable triage loop:

1. **CI posts a PR comment** with violation count, diff from base branch, and top three rules broken
2. **Impact-first sorting** — critical before minor
3. **Duplicate grouping** — one missing-label rule affecting 40 nodes is one fix in a shared Input component
4. **Weekly debt burndown** for violations outside PR scope

Assign `#a11y` CODEOWNERS on design system packages so fixes land at the source.

## What still requires human testing

Schedule quarterly manual passes with:

- VoiceOver on Safari (macOS/iOS)
- NVDA on Firefox (Windows)
- Keyboard-only navigation through primary flows

Automated axe clears the mechanical violations so manual sessions focus on behavior: Does the live region announce streaming chat responses? Does the autocomplete follow WAI-ARIA combobox keyboard patterns?

## Measuring progress without gaming metrics

Track:

- Violations per page by impact (trend down)
- New violations introduced per PR (should → 0 after baseline)
- Mean time to fix critical violations
- Percent of routes covered by E2E axe (coverage gap = risk)

Do not optimize "axe score" by disabling rules. Optimize user outcomes and WCAG conformance level (AA for most public products).

Publish a quarterly accessibility report shared with product and design leadership. Include violation trends, routes still lacking E2E coverage, and the top three recurring rule IDs. Visibility keeps accessibility out of the "we will fix it after launch" pile.

axe in CI is a contract: no new serious accessibility regressions ship unnoticed. It is cheap to run, well-documented, and integrates with the same Playwright suite you already maintain. The hard part is organizational — keeping rules enabled, fixing root causes in shared components, and admitting that green CI does not mean you are done.

## Resources

- [axe-core GitHub repository and rule descriptions](https://github.com/dequelabs/axe-core)
- [Deque University: axe browser extension](https://www.deque.com/axe/browser-extensions/)
- [@axe-core/playwright npm package](https://www.npmjs.com/package/@axe-core/playwright)
- [WAI-ARIA Authoring Practices Guide (APG)](https://www.w3.org/WAI/ARIA/apg/)
- [WCAG 2.1 Quick Reference](https://www.w3.org/WAI/WCAG21/quickref/)
