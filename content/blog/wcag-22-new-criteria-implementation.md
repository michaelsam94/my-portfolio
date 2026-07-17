---
title: "Implementing WCAG 2.2 New Success Criteria"
slug: "wcag-22-new-criteria-implementation"
description: "WCAG 2.2 adds focus appearance, target size, and dragging alternatives — implementation checklist for product teams."
datePublished: "2026-08-01"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "WCAG 2.2 implementation, focus appearance, target size minimum"
faq:
  - q: "Which WCAG 2.2 success criteria are Level AA?"
    a: "Six new AA criteria: 2.4.11 Focus Not Obscured (Minimum), 2.5.7 Dragging Movements, 2.5.8 Target Size (Minimum), 3.2.6 Consistent Help, 3.3.7 Redundant Entry, and 3.3.8 Accessible Authentication (Minimum)."
  - q: "How do sticky headers fail Focus Not Obscured?"
    a: "Fixed nav and cookie banners can cover the focused element during keyboard Tab navigation. Fix with scroll-padding-top matching sticky height, scrollIntoView on focus, or collapsing banners when focus moves underneath."
  - q: "How do you test Target Size (Minimum)?"
    a: "Measure the clickable bounding box including padding — minimum 24×24 CSS pixels. Icon buttons at 20×20 fail even when they look fine visually. Primary mobile actions should target 44×44 for usability even when 24 passes compliance."
---
Forty-seven new violations appeared the week WCAG 2.2 became the procurement standard — mostly sticky headers obscuring keyboard focus and 20×20 icon buttons on mobile checkout. WCAG 2.1 AA is no longer sufficient for contracts referencing "latest WCAG." Version 2.2 adds nine success criteria; six are Level AA and change how product teams ship navigation, forms, and authentication.

## Map the nine new criteria

| Criterion | Level | What changed |
|-----------|-------|--------------|
| 2.4.11 Focus Not Obscured (Minimum) | AA | Sticky UI cannot fully hide focused element |
| 2.4.12 Focus Not Obscured (Enhanced) | AAA | No part of focus indicator hidden |
| 2.4.13 Focus Appearance | AAA | Minimum focus indicator area and contrast |
| 2.5.7 Dragging Movements | AA | Provide single-pointer alternative to drag |
| 2.5.8 Target Size (Minimum) | AA | 24×24 CSS px minimum clickable area |
| 3.2.6 Consistent Help | A | Help mechanisms in consistent relative order |
| 3.3.7 Redundant Entry | A | Auto-fill or select previously entered data |
| 3.3.8 Accessible Authentication (Minimum) | AA | No cognitive function test for login |
| 3.3.9 Accessible Authentication (Enhanced) | AAA | Stricter auth without object recognition |

Procurement teams care about the AA set. Plan remediation against 2.4.11, 2.5.7, 2.5.8, 3.2.6, 3.3.7, and 3.3.8 first.

## 2.4.11 Focus Not Obscured in sticky chrome

Keyboard users Tab through forms while fixed headers, cookie banners, and chat widgets stack at the viewport edge. axe may pass while manual audit fails because focus moves under opaque layers.

Fix patterns:

```css
html {
  scroll-padding-top: calc(var(--header-height) + var(--banner-height));
}
```

On banner open, scroll focused element into view once:

```typescript
document.addEventListener("focusin", (e) => {
  const target = e.target as HTMLElement;
  if (banner.isOpen && banner.covers(target)) {
    target.scrollIntoView({ block: "nearest", behavior: "prefers-reduced-motion" ? "auto" : "smooth" });
  }
});
```

Collapse sticky promo bars when focus moves beneath them, or use `position: sticky` with documented z-index layering instead of overlapping fixed stacks.

## 2.5.8 Target Size on icon buttons

Toolbar icons at 16×16 or 20×20 fail AA even when visually crisp. Expand hit area with transparent padding:

```css
.icon-btn {
  min-width: 24px;
  min-height: 24px;
  padding: 12px; /* visual icon stays 20px inside */
}
```

Primary mobile actions — checkout submit, add to cart — should target 44×44 CSS pixels for usability. Compliance minimum is 24×24; user error rate drops with larger targets.

## 2.5.7 Dragging alternatives

Kanban boards, image croppers, and range sliders need single-pointer alternatives: buttons to move cards, numeric inputs for crop coordinates, text fields for range values. Drag can remain for efficiency; it cannot be the only path.

Document alternatives in component stories and QA scripts — "move item with keyboard" must be testable without simulated drag APIs.

## 3.3.8 Accessible Authentication

CAPTCHA puzzles requiring users to identify traffic lights fail unless an accessible alternative exists. Prefer WebAuthn passkeys, magic links, or OTP without puzzle friction. If risk engine requires step-up, offer accessible channel — not image classification alone.

Pair with rate limiting and device signals server-side — client-only CAPTCHA is both inaccessible and bypassable.

## 3.3.7 Redundant Entry

Multi-step checkout asking for shipping address twice fails unless prior entry is auto-populated or selectable. Use `autocomplete` attributes, copy-from-billing toggles, and session persistence across steps.

## 3.2.6 Consistent Help

Help link, chat launcher, and support phone must appear in the same relative order across pages in a flow. Moving chat from bottom-right to header on step two disorients users with cognitive disabilities.

## VPAT and audit workflow

Update VPAT 2.5 references from WCAG 2.1 to 2.2. Re-run automated scans — axe 4.8+ includes many 2.2 rules. Manual test matrix:

- Tab through checkout with cookie banner + sticky nav open
- Measure icon button bounding boxes in DevTools
- Complete auth without puzzle CAPTCHA
- Verify help placement on all wizard steps

Track defects in accessibility backlog with criterion ID — "2.5.8 checkout toolbar" not vague "button too small."

## Design system tokens

Encode minimum target size in component primitives:

```tsx
export const IconButton = styled.button`
  min-width: var(--target-min, 24px);
  min-height: var(--target-min, 24px);
`;
```

Breaking changes in design system propagate fixes faster than page-by-page patches.

## Regression prevention in CI

Run axe with WCAG 2.2 tag set on critical routes in pull requests. Add Playwright tests asserting focus visibility after opening cookie banner. Block merge on new 2.5.8 violations in checkout components.

## Coordinating with legal and sales

Sales promises "WCAG 2.2 AA compliant" in RFPs — engineering needs lead time before contract signature. Flag sticky header redesigns and icon-dense admin tools as 2.2 risk during design review, not post-launch audit.

WCAG 2.2 is not a checkbox exercise — sticky chrome, icon density, and auth friction are where real products fail. Fix focus obscuring and target size before audit week, and bake criterion IDs into your component library so regressions fail CI instead of customer contracts.

## 3.2.6 Consistent Help in multi-step flows

Checkout wizards that move chat widget from footer to header between steps fail 3.2.6. Define help region order in layout shell — child routes inherit, not override.

## 3.3.7 Redundant Entry in B2B forms

Company address entered on account creation and again on first invoice triggers redundant entry failures. Offer "same as billing" checkbox with programmatic copy — not empty fields user must retype.

## Training design and QA teams

Designers need 2.2 checklist on Figma component specs: minimum target, focus behavior under sticky chrome, drag alternatives. QA scripts include keyboard-only paths with banner open — not only axe green runs on closed banner state.

## European Accessibility Act timeline

EAA affects products sold in EU from June 2025 onward — WCAG 2.2 AA referenced in EN 301 549 updates. Align VPAT statements before enterprise renewals ask for evidence.

## Measuring remediation progress

Track open violations by criterion ID in Jira — burn-down chart per 2.5.8 vs 2.4.11. Executive dashboard shows AA blockers remaining, not generic "a11y issues" count.

## 2.5.7 Dragging alternatives for sortable lists

Provide move-up/move-down buttons alongside drag handles in admin tables. Keyboard users and voice control users complete reorder tasks without pointer drag. Document pattern in design system data table spec.

## 2.4.12 and 2.4.13 at AAA

Enterprise clients requesting AAA need Enhanced Focus Not Obscured and Focus Appearance — plan extra design budget for sticky chrome elimination or focus ring area minimums beyond AA compliance.

## Procurement evidence pack

Export axe JSON, manual test recordings, and VPAT section mapping to criterion IDs — sales engineering attaches pack to RFP responses without asking engineering for ad hoc screenshots each deal.

## Additional context (1)

Forty-seven new violations appeared the week WCAG 2.2 became the procurement standard—mostly sticky headers and 20px icon buttons. Document which routes or tenants you changed first, and keep rollback paths in the PR description before promoting beyond canary traffic.

## Additional context (2)

Forty-seven new violations appeared the week WCAG 2.2 became the procurement standard—mostly sticky headers and 20px icon buttons. Document which routes or tenants you changed first, and keep rollback paths in the PR description before promoting beyond canary traffic.

## WCAG 2.2 criteria that change components

Focus appearance, dragging alternatives, target size, accessible authentication, and consistent help force design-system API changes. Dense tables need spacious modes. Auth should support managers and passkeys instead of cognitive puzzles.

Automate axe checks; manually verify keyboard and screen reader paths. Keep evidence recordings. Push fixes into primitives so product teams inherit compliance. Track accessibility escapes found in production versus design-system CI.
