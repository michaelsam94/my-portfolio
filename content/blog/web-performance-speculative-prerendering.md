---
title: "Speculation Rules API for Prerendering"
slug: "web-performance-speculative-prerendering"
description: "Speculation Rules prerender on hover — eagerness tuning, privacy implications, and Next.js integration."
datePublished: "2027-01-22"
dateModified: "2026-07-17"
tags:
  - "Performance"
  - "Navigation"
  - "Prefetch"
keywords: "Speculation Rules API, prerender on hover, document prerender"
faq:
  - q: "Prerender vs prefetch?"
    a: "Prerender loads and renders full page in hidden tab — instant navigation but higher cost. Prefetch only fetches resources. Use prerender sparingly for high-confidence next pages."
  - q: "How to measure speculation hit rate?"
    a: "Track prerender activation vs actual navigations in RUM. Hit rate below 30% means rules are too aggressive — tune URL patterns."
  - q: "Mobile data concerns?"
    a: "Respect Save-Data; disable prerender on slow connections. Speculation Rules support eagerness levels — use conservative on mobile breakpoints."
faqAnswers:
  - question: "When is web performance speculative prerendering the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for web performance speculative prerendering?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back web performance speculative prerendering safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
Speculation Rules prerendered the wrong checkout step for logged-out users — cached personalized HTML leaked session state until we scoped rules to anonymous routes only.

## Why this breaks in production

Speculation Rules prerendered the wrong checkout step for logged-out users — cached personalized HTML leaked session state until we scoped rules to anonymous routes only.

**When:** When navigation patterns are highly predictable and bandwidth cost is acceptable

**Avoid:** Prerendering authenticated routes without matching Vary headers and cache isolation

## How it works

Rehearse anti-pattern in design review: Prerendering authenticated routes without matching Vary headers and cache isolation

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
performance.mark("start");
await applyChange();
performance.mark("end");
performance.measure("change", "start", "end");
```

## When to prioritize

When navigation patterns are highly predictable and bandwidth cost is acceptable.

## Anti-pattern

Prerendering authenticated routes without matching Vary headers and cache isolation.

## Deep dive: failure rehearsal (1)

Rehearse `Prerendering authenticated routes without matching Vary headers and cache isolation` in a 30-minute game day before peak season. For Speculation Rules API for prerender and prefetch, measure time-to-detect and time-to-mitigate — not only time-to-root-cause in a postmortem doc.

Manual paths worth scripting: hard refresh mid-flow, browser back after async submit, double-click primary action, offline toggle during mutation, keyboard-only navigation with screen reader.

## Deep dive: observability (2)

Wire custom RUM marks around the user journey Speculation Rules API for prerender and prefetch affects. Log correlation IDs across client beacons and server logs. Alert on week-over-week p75 regression on tier-1 routes — global averages hide bad canaries.

Leading indicators: error rate, validation failures, queue depth. Lagging: support tickets, conversion, churn. Both must move together to confirm the fix matched user pain.

## Deep dive: third-party drift (3)

Tag managers, chat widgets, and payment iframes change without your deploy. Quarterly audit script inventory on critical routes. Compare lab metrics with ad blockers enabled vs disabled — the delta reveals third-party cost.

For Speculation Rules API for prerender and prefetch, corporate proxies and Save-Data alter behavior versus staging on office Wi-Fi. Field validation beats conference demos.

## Deep dive: rollout discipline (4)

Speculation Rules prerendered the wrong checkout step for logged-out users — cached personalized HTML leaked session state until we scoped rules to anonymous routes only. When rolling out changes to Speculation Rules API for prerender and prefetch, compare canary p75 INP and LCP to control for a full business day in target regions before promoting to 100%. Document rollback in the PR: feature flag name, cache purge procedure, or revert commit — whichever restores prior behavior fastest at 2 a.m.

Slice metrics by device class and connection effective type. A fix helping desktop fiber but regressing mid-tier Android 4G should pause rollout, not ship globally.

## Deep dive: failure rehearsal (5)

Rehearse `Prerendering authenticated routes without matching Vary headers and cache isolation` in a 30-minute game day before peak season. For Speculation Rules API for prerender and prefetch, measure time-to-detect and time-to-mitigate — not only time-to-root-cause in a postmortem doc.

Manual paths worth scripting: hard refresh mid-flow, browser back after async submit, double-click primary action, offline toggle during mutation, keyboard-only navigation with screen reader.

## Deep dive: observability (6)

Wire custom RUM marks around the user journey Speculation Rules API for prerender and prefetch affects. Log correlation IDs across client beacons and server logs. Alert on week-over-week p75 regression on tier-1 routes — global averages hide bad canaries.

Leading indicators: error rate, validation failures, queue depth. Lagging: support tickets, conversion, churn. Both must move together to confirm the fix matched user pain.

## Deep dive: third-party drift (7)

Tag managers, chat widgets, and payment iframes change without your deploy. Quarterly audit script inventory on critical routes. Compare lab metrics with ad blockers enabled vs disabled — the delta reveals third-party cost.

For Speculation Rules API for prerender and prefetch, corporate proxies and Save-Data alter behavior versus staging on office Wi-Fi. Field validation beats conference demos.

## Deep dive: rollout discipline (8)

Speculation Rules prerendered the wrong checkout step for logged-out users — cached personalized HTML leaked session state until we scoped rules to anonymous routes only. When rolling out changes to Speculation Rules API for prerender and prefetch, compare canary p75 INP and LCP to control for a full business day in target regions before promoting to 100%. Document rollback in the PR: feature flag name, cache purge procedure, or revert commit — whichever restores prior behavior fastest at 2 a.m.

Slice metrics by device class and connection effective type. A fix helping desktop fiber but regressing mid-tier Android 4G should pause rollout, not ship globally.

## Deep dive: failure rehearsal (9)

Rehearse `Prerendering authenticated routes without matching Vary headers and cache isolation` in a 30-minute game day before peak season. For Speculation Rules API for prerender and prefetch, measure time-to-detect and time-to-mitigate — not only time-to-root-cause in a postmortem doc.

Manual paths worth scripting: hard refresh mid-flow, browser back after async submit, double-click primary action, offline toggle during mutation, keyboard-only navigation with screen reader.

## Deep dive: observability (10)

Wire custom RUM marks around the user journey Speculation Rules API for prerender and prefetch affects. Log correlation IDs across client beacons and server logs. Alert on week-over-week p75 regression on tier-1 routes — global averages hide bad canaries.

Leading indicators: error rate, validation failures, queue depth. Lagging: support tickets, conversion, churn. Both must move together to confirm the fix matched user pain.

## Deep dive: third-party drift (11)

Tag managers, chat widgets, and payment iframes change without your deploy. Quarterly audit script inventory on critical routes. Compare lab metrics with ad blockers enabled vs disabled — the delta reveals third-party cost.

For Speculation Rules API for prerender and prefetch, corporate proxies and Save-Data alter behavior versus staging on office Wi-Fi. Field validation beats conference demos.

## Deep dive: rollout discipline (12)

Speculation Rules prerendered the wrong checkout step for logged-out users — cached personalized HTML leaked session state until we scoped rules to anonymous routes only. When rolling out changes to Speculation Rules API for prerender and prefetch, compare canary p75 INP and LCP to control for a full business day in target regions before promoting to 100%. Document rollback in the PR: feature flag name, cache purge procedure, or revert commit — whichever restores prior behavior fastest at 2 a.m.

Slice metrics by device class and connection effective type. A fix helping desktop fiber but regressing mid-tier Android 4G should pause rollout, not ship globally.

## Deep dive: failure rehearsal (13)

Rehearse `Prerendering authenticated routes without matching Vary headers and cache isolation` in a 30-minute game day before peak season. For Speculation Rules API for prerender and prefetch, measure time-to-detect and time-to-mitigate — not only time-to-root-cause in a postmortem doc.

Manual paths worth scripting: hard refresh mid-flow, browser back after async submit, double-click primary action, offline toggle during mutation, keyboard-only navigation with screen reader.

## Deep dive: observability (14)

Wire custom RUM marks around the user journey Speculation Rules API for prerender and prefetch affects. Log correlation IDs across client beacons and server logs. Alert on week-over-week p75 regression on tier-1 routes — global averages hide bad canaries.

Leading indicators: error rate, validation failures, queue depth. Lagging: support tickets, conversion, churn. Both must move together to confirm the fix matched user pain.