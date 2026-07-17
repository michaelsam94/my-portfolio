---
title: "Sanitizing HTML User Content Safely"
slug: "xss-sanitize-html-user-content"
description: "DOMPurify configuration for rich text — allowlist tags, hook for links, and SSR sanitization parity."
datePublished: "2026-10-17"
dateModified: "2026-07-17"
tags:
  - "Security"
  - "XSS"
  - "DOMPurify"
keywords: "DOMPurify sanitize HTML, user content XSS, rich text security"
faq:
  - q: "DOMPurify config?"
    a: "USE_PROFILES html or svg selectively; forbid style if not needed. ADD_URI_SAFE_ATTR for data attributes only if required."
  - q: "Server-side sanitize too?"
    a: "Always sanitize server-side on ingest — client sanitize is defense in depth, not primary."
  - q: "Markdown to HTML?"
    a: "Sanitize after markdown render — markdown allows raw HTML passthrough by default in many parsers."
faqAnswers:
  - question: "When is xss sanitize html user content the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for xss sanitize html user content?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back xss sanitize html user content safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
DOMPurify blocked script but allowed onerror on SVG — tightening ALLOWED_TAGS and using hook to strip event handlers stopped stored XSS in comment previews.

## Why this breaks in production

DOMPurify blocked script but allowed onerror on SVG — tightening ALLOWED_TAGS and using hook to strip event handlers stopped stored XSS in comment previews.

**When:** When rich text comments, bios, or CMS content renders as HTML

**Avoid:** Regex strip of script tags — misses img onerror, javascript: URLs, and SVG vectors

## How it works

Rehearse anti-pattern in design review: Regex strip of script tags — misses img onerror, javascript: URLs, and SVG vectors

Rollback via feature flag or cache purge must be documented in the PR before merge.

## Implementation

Test refresh, back, double-submit, offline, and keyboard-only paths manually.

## Failure modes

Third-party scripts change without your deploy — audit quarterly.

Global metric averages hide regional or device-class regressions.

## Measurement

Slice dashboards by route, device, connection type, release version.

Alert week-over-week p75 regression on tier-1 surfaces.

## Ship checklist

Link runbook from dashboard — not buried wiki.

Quarterly re-verify after browser releases and traffic shifts.

## Reference implementation

```typescript
import DOMPurify from "dompurify";
const clean = DOMPurify.sanitize(input, {
  ALLOWED_TAGS: ["b", "i", "em", "strong", "a", "p", "ul", "ol", "li", "code"],
  ALLOWED_ATTR: ["href", "title"],
});
el.replaceChildren(document.createRange().createContextualFragment(clean));
```

## When to prioritize

When rich text comments, bios, or cms content renders as html.

## Anti-pattern

Regex strip of script tags — misses img onerror, javascript: URLs, and SVG vectors.

## Deep dive: third-party drift (1)

Tag managers, chat widgets, and payment iframes change without your deploy. Quarterly audit script inventory on critical routes. Compare lab metrics with ad blockers enabled vs disabled — the delta reveals third-party cost.

For sanitize HTML user content with allowlists, corporate proxies and Save-Data alter behavior versus staging on office Wi-Fi. Field validation beats conference demos.

## Deep dive: rollout discipline (2)

DOMPurify blocked script but allowed onerror on SVG — tightening ALLOWED_TAGS and using hook to strip event handlers stopped stored XSS in comment previews. When rolling out changes to sanitize HTML user content with allowlists, compare canary p75 INP and LCP to control for a full business day in target regions before promoting to 100%. Document rollback in the PR: feature flag name, cache purge procedure, or revert commit — whichever restores prior behavior fastest at 2 a.m.

Slice metrics by device class and connection effective type. A fix helping desktop fiber but regressing mid-tier Android 4G should pause rollout, not ship globally.

## Deep dive: failure rehearsal (3)

Rehearse `Regex strip of script tags — misses img onerror, javascript: URLs, and SVG vectors` in a 30-minute game day before peak season. For sanitize HTML user content with allowlists, measure time-to-detect and time-to-mitigate — not only time-to-root-cause in a postmortem doc.

Manual paths worth scripting: hard refresh mid-flow, browser back after async submit, double-click primary action, offline toggle during mutation, keyboard-only navigation with screen reader.

## Deep dive: observability (4)

Wire custom RUM marks around the user journey sanitize HTML user content with allowlists affects. Log correlation IDs across client beacons and server logs. Alert on week-over-week p75 regression on tier-1 routes — global averages hide bad canaries.

Leading indicators: error rate, validation failures, queue depth. Lagging: support tickets, conversion, churn. Both must move together to confirm the fix matched user pain.

## Deep dive: third-party drift (5)

Tag managers, chat widgets, and payment iframes change without your deploy. Quarterly audit script inventory on critical routes. Compare lab metrics with ad blockers enabled vs disabled — the delta reveals third-party cost.

For sanitize HTML user content with allowlists, corporate proxies and Save-Data alter behavior versus staging on office Wi-Fi. Field validation beats conference demos.

## Deep dive: rollout discipline (6)

DOMPurify blocked script but allowed onerror on SVG — tightening ALLOWED_TAGS and using hook to strip event handlers stopped stored XSS in comment previews. When rolling out changes to sanitize HTML user content with allowlists, compare canary p75 INP and LCP to control for a full business day in target regions before promoting to 100%. Document rollback in the PR: feature flag name, cache purge procedure, or revert commit — whichever restores prior behavior fastest at 2 a.m.

Slice metrics by device class and connection effective type. A fix helping desktop fiber but regressing mid-tier Android 4G should pause rollout, not ship globally.

## Deep dive: failure rehearsal (7)

Rehearse `Regex strip of script tags — misses img onerror, javascript: URLs, and SVG vectors` in a 30-minute game day before peak season. For sanitize HTML user content with allowlists, measure time-to-detect and time-to-mitigate — not only time-to-root-cause in a postmortem doc.

Manual paths worth scripting: hard refresh mid-flow, browser back after async submit, double-click primary action, offline toggle during mutation, keyboard-only navigation with screen reader.

## Deep dive: observability (8)

Wire custom RUM marks around the user journey sanitize HTML user content with allowlists affects. Log correlation IDs across client beacons and server logs. Alert on week-over-week p75 regression on tier-1 routes — global averages hide bad canaries.

Leading indicators: error rate, validation failures, queue depth. Lagging: support tickets, conversion, churn. Both must move together to confirm the fix matched user pain.

## Deep dive: third-party drift (9)

Tag managers, chat widgets, and payment iframes change without your deploy. Quarterly audit script inventory on critical routes. Compare lab metrics with ad blockers enabled vs disabled — the delta reveals third-party cost.

For sanitize HTML user content with allowlists, corporate proxies and Save-Data alter behavior versus staging on office Wi-Fi. Field validation beats conference demos.

## Deep dive: rollout discipline (10)

DOMPurify blocked script but allowed onerror on SVG — tightening ALLOWED_TAGS and using hook to strip event handlers stopped stored XSS in comment previews. When rolling out changes to sanitize HTML user content with allowlists, compare canary p75 INP and LCP to control for a full business day in target regions before promoting to 100%. Document rollback in the PR: feature flag name, cache purge procedure, or revert commit — whichever restores prior behavior fastest at 2 a.m.

Slice metrics by device class and connection effective type. A fix helping desktop fiber but regressing mid-tier Android 4G should pause rollout, not ship globally.

## Deep dive: failure rehearsal (11)

Rehearse `Regex strip of script tags — misses img onerror, javascript: URLs, and SVG vectors` in a 30-minute game day before peak season. For sanitize HTML user content with allowlists, measure time-to-detect and time-to-mitigate — not only time-to-root-cause in a postmortem doc.

Manual paths worth scripting: hard refresh mid-flow, browser back after async submit, double-click primary action, offline toggle during mutation, keyboard-only navigation with screen reader.

## Deep dive: observability (12)

Wire custom RUM marks around the user journey sanitize HTML user content with allowlists affects. Log correlation IDs across client beacons and server logs. Alert on week-over-week p75 regression on tier-1 routes — global averages hide bad canaries.

Leading indicators: error rate, validation failures, queue depth. Lagging: support tickets, conversion, churn. Both must move together to confirm the fix matched user pain.

## Deep dive: third-party drift (13)

Tag managers, chat widgets, and payment iframes change without your deploy. Quarterly audit script inventory on critical routes. Compare lab metrics with ad blockers enabled vs disabled — the delta reveals third-party cost.

For sanitize HTML user content with allowlists, corporate proxies and Save-Data alter behavior versus staging on office Wi-Fi. Field validation beats conference demos.

## Deep dive: rollout discipline (14)

DOMPurify blocked script but allowed onerror on SVG — tightening ALLOWED_TAGS and using hook to strip event handlers stopped stored XSS in comment previews. When rolling out changes to sanitize HTML user content with allowlists, compare canary p75 INP and LCP to control for a full business day in target regions before promoting to 100%. Document rollback in the PR: feature flag name, cache purge procedure, or revert commit — whichever restores prior behavior fastest at 2 a.m.

Slice metrics by device class and connection effective type. A fix helping desktop fiber but regressing mid-tier Android 4G should pause rollout, not ship globally.