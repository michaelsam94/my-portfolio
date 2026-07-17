---
title: "Navigation Timing API for RUM"
slug: "web-performance-navigation-timing-api"
description: "Navigation Timing Level 2 metrics — DNS, TTFB, domInteractive breakdown in custom RUM beacons."
datePublished: "2027-01-23"
dateModified: "2026-07-17"
tags:
  - "Performance"
  - "RUM"
  - "Monitoring"
keywords: "Navigation Timing API, RUM performance metrics, TTFB measurement"
faq:
  - q: "Navigation Timing Level 2 vs legacy?"
    a: "Use PerformanceNavigationTiming (Level 2) — it replaces deprecated performance.timing and works with PerformanceObserver for SPA navigations when paired with soft-nav beacons."
  - q: "How do SPAs use Navigation Timing?"
    a: "Initial load uses the API directly; subsequent route changes need custom marks or the soft-navigation spec. Do not assume one page load metric covers SPA transitions."
  - q: "Which metrics correlate with Core Web Vitals?"
    a: "domContentLoadedEventEnd and loadEventEnd correlate weakly with LCP/INP. Use Navigation Timing for diagnostics, CrUX/RUM CWV for SLOs."
faqAnswers:
  - question: "When is web performance navigation timing api the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for web performance navigation timing api?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back web performance navigation timing api safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
Our RUM dashboard showed 200ms TTFB while users complained of slow loads — Navigation Timing revealed 1.8s spent in redirect chains and TLS handshakes the server metric never saw.

## Why this breaks in production

Our RUM dashboard showed 200ms TTFB while users complained of slow loads — Navigation Timing revealed 1.8s spent in redirect chains and TLS handshakes the server metric never saw.

**When:** When you need field data on redirect, DNS, TLS, and DOM phases beyond server-side TTFB

**Avoid:** Reporting only responseStart minus fetchStart without breaking down redirect and TLS time

## How it works

Rehearse anti-pattern in design review: Reporting only responseStart minus fetchStart without breaking down redirect and TLS time

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

When you need field data on redirect, dns, tls, and dom phases beyond server-side ttfb.

## Anti-pattern

Reporting only responseStart minus fetchStart without breaking down redirect and TLS time.

## Deep dive: third-party drift (1)

Tag managers, chat widgets, and payment iframes change without your deploy. Quarterly audit script inventory on critical routes. Compare lab metrics with ad blockers enabled vs disabled — the delta reveals third-party cost.

For Navigation Timing API for Real User Monitoring, corporate proxies and Save-Data alter behavior versus staging on office Wi-Fi. Field validation beats conference demos.

## Deep dive: rollout discipline (2)

Our RUM dashboard showed 200ms TTFB while users complained of slow loads — Navigation Timing revealed 1. When rolling out changes to Navigation Timing API for Real User Monitoring, compare canary p75 INP and LCP to control for a full business day in target regions before promoting to 100%. Document rollback in the PR: feature flag name, cache purge procedure, or revert commit — whichever restores prior behavior fastest at 2 a.m.

Slice metrics by device class and connection effective type. A fix helping desktop fiber but regressing mid-tier Android 4G should pause rollout, not ship globally.

## Deep dive: failure rehearsal (3)

Rehearse `Reporting only responseStart minus fetchStart without breaking down redirect and TLS time` in a 30-minute game day before peak season. For Navigation Timing API for Real User Monitoring, measure time-to-detect and time-to-mitigate — not only time-to-root-cause in a postmortem doc.

Manual paths worth scripting: hard refresh mid-flow, browser back after async submit, double-click primary action, offline toggle during mutation, keyboard-only navigation with screen reader.

## Deep dive: observability (4)

Wire custom RUM marks around the user journey Navigation Timing API for Real User Monitoring affects. Log correlation IDs across client beacons and server logs. Alert on week-over-week p75 regression on tier-1 routes — global averages hide bad canaries.

Leading indicators: error rate, validation failures, queue depth. Lagging: support tickets, conversion, churn. Both must move together to confirm the fix matched user pain.

## Deep dive: third-party drift (5)

Tag managers, chat widgets, and payment iframes change without your deploy. Quarterly audit script inventory on critical routes. Compare lab metrics with ad blockers enabled vs disabled — the delta reveals third-party cost.

For Navigation Timing API for Real User Monitoring, corporate proxies and Save-Data alter behavior versus staging on office Wi-Fi. Field validation beats conference demos.

## Deep dive: rollout discipline (6)

Our RUM dashboard showed 200ms TTFB while users complained of slow loads — Navigation Timing revealed 1. When rolling out changes to Navigation Timing API for Real User Monitoring, compare canary p75 INP and LCP to control for a full business day in target regions before promoting to 100%. Document rollback in the PR: feature flag name, cache purge procedure, or revert commit — whichever restores prior behavior fastest at 2 a.m.

Slice metrics by device class and connection effective type. A fix helping desktop fiber but regressing mid-tier Android 4G should pause rollout, not ship globally.

## Deep dive: failure rehearsal (7)

Rehearse `Reporting only responseStart minus fetchStart without breaking down redirect and TLS time` in a 30-minute game day before peak season. For Navigation Timing API for Real User Monitoring, measure time-to-detect and time-to-mitigate — not only time-to-root-cause in a postmortem doc.

Manual paths worth scripting: hard refresh mid-flow, browser back after async submit, double-click primary action, offline toggle during mutation, keyboard-only navigation with screen reader.

## Deep dive: observability (8)

Wire custom RUM marks around the user journey Navigation Timing API for Real User Monitoring affects. Log correlation IDs across client beacons and server logs. Alert on week-over-week p75 regression on tier-1 routes — global averages hide bad canaries.

Leading indicators: error rate, validation failures, queue depth. Lagging: support tickets, conversion, churn. Both must move together to confirm the fix matched user pain.

## Deep dive: third-party drift (9)

Tag managers, chat widgets, and payment iframes change without your deploy. Quarterly audit script inventory on critical routes. Compare lab metrics with ad blockers enabled vs disabled — the delta reveals third-party cost.

For Navigation Timing API for Real User Monitoring, corporate proxies and Save-Data alter behavior versus staging on office Wi-Fi. Field validation beats conference demos.

## Deep dive: rollout discipline (10)

Our RUM dashboard showed 200ms TTFB while users complained of slow loads — Navigation Timing revealed 1. When rolling out changes to Navigation Timing API for Real User Monitoring, compare canary p75 INP and LCP to control for a full business day in target regions before promoting to 100%. Document rollback in the PR: feature flag name, cache purge procedure, or revert commit — whichever restores prior behavior fastest at 2 a.m.

Slice metrics by device class and connection effective type. A fix helping desktop fiber but regressing mid-tier Android 4G should pause rollout, not ship globally.

## Deep dive: failure rehearsal (11)

Rehearse `Reporting only responseStart minus fetchStart without breaking down redirect and TLS time` in a 30-minute game day before peak season. For Navigation Timing API for Real User Monitoring, measure time-to-detect and time-to-mitigate — not only time-to-root-cause in a postmortem doc.

Manual paths worth scripting: hard refresh mid-flow, browser back after async submit, double-click primary action, offline toggle during mutation, keyboard-only navigation with screen reader.

## Deep dive: observability (12)

Wire custom RUM marks around the user journey Navigation Timing API for Real User Monitoring affects. Log correlation IDs across client beacons and server logs. Alert on week-over-week p75 regression on tier-1 routes — global averages hide bad canaries.

Leading indicators: error rate, validation failures, queue depth. Lagging: support tickets, conversion, churn. Both must move together to confirm the fix matched user pain.

## Deep dive: third-party drift (13)

Tag managers, chat widgets, and payment iframes change without your deploy. Quarterly audit script inventory on critical routes. Compare lab metrics with ad blockers enabled vs disabled — the delta reveals third-party cost.

For Navigation Timing API for Real User Monitoring, corporate proxies and Save-Data alter behavior versus staging on office Wi-Fi. Field validation beats conference demos.

## Deep dive: rollout discipline (14)

Our RUM dashboard showed 200ms TTFB while users complained of slow loads — Navigation Timing revealed 1. When rolling out changes to Navigation Timing API for Real User Monitoring, compare canary p75 INP and LCP to control for a full business day in target regions before promoting to 100%. Document rollback in the PR: feature flag name, cache purge procedure, or revert commit — whichever restores prior behavior fastest at 2 a.m.

Slice metrics by device class and connection effective type. A fix helping desktop fiber but regressing mid-tier Android 4G should pause rollout, not ship globally.