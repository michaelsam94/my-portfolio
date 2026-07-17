---
title: "modulepreload for ES Module Chains"
slug: "web-performance-module-preload-import"
description: "modulepreload critical module graph entries — dependency chain warming vs over-preloading bandwidth."
datePublished: "2027-02-11"
dateModified: "2026-07-17"
tags:
  - "Performance"
  - "ES Modules"
  - "Loading"
keywords: "modulepreload link, ES module preload, critical module chain"
faq:
  - q: "Does modulepreload replace import maps?"
    a: "No. Import maps resolve bare specifiers; modulepreload warms specific resolved URLs. You still need correct map configuration — preload the resolved URL the browser will actually fetch."
  - q: "Should I modulepreload lazy route chunks?"
    a: "Only if the route is likely on the critical path for first paint. Preloading all route chunks competes with entry module bandwidth and hurts LCP on slow networks."
  - q: "How do I verify modulepreload is working?"
    a: "In DevTools Network, filter Initiator: preload and confirm only expected modules load early. Compare waterfall with and without hints on throttled 4G."
faqAnswers:
  - question: "When is web performance module preload import the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for web performance module preload import?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back web performance module preload import safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
We preloaded the entire ES module graph — forty-two modulepreload tags — and FCP regressed because the browser fetched every lazy route before the entry module finished parsing.

## Why this breaks in production

We preloaded the entire ES module graph — forty-two modulepreload tags — and FCP regressed because the browser fetched every lazy route before the entry module finished parsing.

**When:** When your entry chunk dynamically imports above-the-fold UI and LCP depends on a nested module

**Avoid:** Preloading every dynamic import instead of only modules on the critical path to interactive

## How it works

`modulepreload` fetches and parses ES modules before the importer runs, inserting them into the module map. Unlike script preload, it respects module semantics including CORS and strict mode.

Map your bundle with Vite `--metafile` or webpack stats. Preload only modules on the path from entry to LCP and first interaction — not every lazy route chunk.

Cap at three to five modulepreload tags. On 4G, each extra preload competes with the hero image for bandwidth. Verify hrefs match post-import-map resolved URLs.

In DevTools Network, filter Initiator preload. Compare FCP and LCP p75 with hints on vs off using RUM throttled profiles.

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

```html
<link rel="modulepreload" href="/assets/entry-abc123.js" crossorigin />
<link rel="preload" href="/hero.avif" as="image" type="image/avif" fetchpriority="high" />
<link rel="preconnect" href="https://cdn.example.com" crossorigin />
```

## When to prioritize

When your entry chunk dynamically imports above-the-fold ui and lcp depends on a nested module.

## Anti-pattern

Preloading every dynamic import instead of only modules on the critical path to interactive.

## Deep dive: rollout discipline (1)

We preloaded the entire ES module graph — forty-two modulepreload tags — and FCP regressed because the browser fetched every lazy route before the entry module finished parsing. When rolling out changes to modulepreload for critical ES module chains, compare canary p75 INP and LCP to control for a full business day in target regions before promoting to 100%. Document rollback in the PR: feature flag name, cache purge procedure, or revert commit — whichever restores prior behavior fastest at 2 a.m.

Slice metrics by device class and connection effective type. A fix helping desktop fiber but regressing mid-tier Android 4G should pause rollout, not ship globally.

## Deep dive: failure rehearsal (2)

Rehearse `Preloading every dynamic import instead of only modules on the critical path to interactive` in a 30-minute game day before peak season. For modulepreload for critical ES module chains, measure time-to-detect and time-to-mitigate — not only time-to-root-cause in a postmortem doc.

Manual paths worth scripting: hard refresh mid-flow, browser back after async submit, double-click primary action, offline toggle during mutation, keyboard-only navigation with screen reader.

## Deep dive: observability (3)

Wire custom RUM marks around the user journey modulepreload for critical ES module chains affects. Log correlation IDs across client beacons and server logs. Alert on week-over-week p75 regression on tier-1 routes — global averages hide bad canaries.

Leading indicators: error rate, validation failures, queue depth. Lagging: support tickets, conversion, churn. Both must move together to confirm the fix matched user pain.

## Deep dive: third-party drift (4)

Tag managers, chat widgets, and payment iframes change without your deploy. Quarterly audit script inventory on critical routes. Compare lab metrics with ad blockers enabled vs disabled — the delta reveals third-party cost.

For modulepreload for critical ES module chains, corporate proxies and Save-Data alter behavior versus staging on office Wi-Fi. Field validation beats conference demos.

## Deep dive: rollout discipline (5)

We preloaded the entire ES module graph — forty-two modulepreload tags — and FCP regressed because the browser fetched every lazy route before the entry module finished parsing. When rolling out changes to modulepreload for critical ES module chains, compare canary p75 INP and LCP to control for a full business day in target regions before promoting to 100%. Document rollback in the PR: feature flag name, cache purge procedure, or revert commit — whichever restores prior behavior fastest at 2 a.m.

Slice metrics by device class and connection effective type. A fix helping desktop fiber but regressing mid-tier Android 4G should pause rollout, not ship globally.

## Deep dive: failure rehearsal (6)

Rehearse `Preloading every dynamic import instead of only modules on the critical path to interactive` in a 30-minute game day before peak season. For modulepreload for critical ES module chains, measure time-to-detect and time-to-mitigate — not only time-to-root-cause in a postmortem doc.

Manual paths worth scripting: hard refresh mid-flow, browser back after async submit, double-click primary action, offline toggle during mutation, keyboard-only navigation with screen reader.

## Deep dive: observability (7)

Wire custom RUM marks around the user journey modulepreload for critical ES module chains affects. Log correlation IDs across client beacons and server logs. Alert on week-over-week p75 regression on tier-1 routes — global averages hide bad canaries.

Leading indicators: error rate, validation failures, queue depth. Lagging: support tickets, conversion, churn. Both must move together to confirm the fix matched user pain.

## Deep dive: third-party drift (8)

Tag managers, chat widgets, and payment iframes change without your deploy. Quarterly audit script inventory on critical routes. Compare lab metrics with ad blockers enabled vs disabled — the delta reveals third-party cost.

For modulepreload for critical ES module chains, corporate proxies and Save-Data alter behavior versus staging on office Wi-Fi. Field validation beats conference demos.

## Deep dive: rollout discipline (9)

We preloaded the entire ES module graph — forty-two modulepreload tags — and FCP regressed because the browser fetched every lazy route before the entry module finished parsing. When rolling out changes to modulepreload for critical ES module chains, compare canary p75 INP and LCP to control for a full business day in target regions before promoting to 100%. Document rollback in the PR: feature flag name, cache purge procedure, or revert commit — whichever restores prior behavior fastest at 2 a.m.

Slice metrics by device class and connection effective type. A fix helping desktop fiber but regressing mid-tier Android 4G should pause rollout, not ship globally.

## Deep dive: failure rehearsal (10)

Rehearse `Preloading every dynamic import instead of only modules on the critical path to interactive` in a 30-minute game day before peak season. For modulepreload for critical ES module chains, measure time-to-detect and time-to-mitigate — not only time-to-root-cause in a postmortem doc.

Manual paths worth scripting: hard refresh mid-flow, browser back after async submit, double-click primary action, offline toggle during mutation, keyboard-only navigation with screen reader.

## Deep dive: observability (11)

Wire custom RUM marks around the user journey modulepreload for critical ES module chains affects. Log correlation IDs across client beacons and server logs. Alert on week-over-week p75 regression on tier-1 routes — global averages hide bad canaries.

Leading indicators: error rate, validation failures, queue depth. Lagging: support tickets, conversion, churn. Both must move together to confirm the fix matched user pain.

## Deep dive: third-party drift (12)

Tag managers, chat widgets, and payment iframes change without your deploy. Quarterly audit script inventory on critical routes. Compare lab metrics with ad blockers enabled vs disabled — the delta reveals third-party cost.

For modulepreload for critical ES module chains, corporate proxies and Save-Data alter behavior versus staging on office Wi-Fi. Field validation beats conference demos.