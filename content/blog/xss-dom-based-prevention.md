---
title: "DOM-Based XSS Prevention in SPAs"
slug: "xss-dom-based-prevention"
description: "DOM XSS from innerHTML, location.hash, and postMessage — sanitization and strict source validation in React."
datePublished: "2026-10-16"
dateModified: "2026-07-17"
tags:
  - "Security"
  - "XSS"
  - "React"
keywords: "DOM XSS prevention, SPA XSS, React XSS security"
faq:
  - q: "Common DOM XSS sinks?"
    a: "innerHTML, outerHTML, insertAdjacentHTML, eval, setTimeout string, location assignment. Use textContent or sanitize with DOMPurify."
  - q: "postMessage XSS?"
    a: "Validate event.origin against allowlist; never pass event.data to sinks without schema validation."
  - q: "Can CSP stop DOM XSS?"
    a: "Strict CSP with nonces helps inline; Trusted Types enforce sink policies — strongest client-side DOM XSS defense."
faqAnswers:
  - question: "When is xss dom based prevention the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for xss dom based prevention?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back xss dom based prevention safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
location.hash fed into innerHTML without sanitization — a crafted link exfiltrated session tokens via DOM XSS that WAF never saw because payload never hit the server.

## Why this breaks in production

location.hash fed into innerHTML without sanitization — a crafted link exfiltrated session tokens via DOM XSS that WAF never saw because payload never hit the server.

**When:** When URL fragments, postMessage, or client storage flow into DOM sinks

**Avoid:** Trusting client-side routing params for document.write or eval sinks

## How it works

Rehearse anti-pattern in design review: Trusting client-side routing params for document.write or eval sinks

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

When url fragments, postmessage, or client storage flow into dom sinks.

## Anti-pattern

Trusting client-side routing params for document.write or eval sinks.

## Deep dive: observability (1)

Wire custom RUM marks around the user journey DOM-based XSS prevention in client-rendered apps affects. Log correlation IDs across client beacons and server logs. Alert on week-over-week p75 regression on tier-1 routes — global averages hide bad canaries.

Leading indicators: error rate, validation failures, queue depth. Lagging: support tickets, conversion, churn. Both must move together to confirm the fix matched user pain.

## Deep dive: third-party drift (2)

Tag managers, chat widgets, and payment iframes change without your deploy. Quarterly audit script inventory on critical routes. Compare lab metrics with ad blockers enabled vs disabled — the delta reveals third-party cost.

For DOM-based XSS prevention in client-rendered apps, corporate proxies and Save-Data alter behavior versus staging on office Wi-Fi. Field validation beats conference demos.

## Deep dive: rollout discipline (3)

location. When rolling out changes to DOM-based XSS prevention in client-rendered apps, compare canary p75 INP and LCP to control for a full business day in target regions before promoting to 100%. Document rollback in the PR: feature flag name, cache purge procedure, or revert commit — whichever restores prior behavior fastest at 2 a.m.

Slice metrics by device class and connection effective type. A fix helping desktop fiber but regressing mid-tier Android 4G should pause rollout, not ship globally.

## Deep dive: failure rehearsal (4)

Rehearse `Trusting client-side routing params for document.write or eval sinks` in a 30-minute game day before peak season. For DOM-based XSS prevention in client-rendered apps, measure time-to-detect and time-to-mitigate — not only time-to-root-cause in a postmortem doc.

Manual paths worth scripting: hard refresh mid-flow, browser back after async submit, double-click primary action, offline toggle during mutation, keyboard-only navigation with screen reader.

## Deep dive: observability (5)

Wire custom RUM marks around the user journey DOM-based XSS prevention in client-rendered apps affects. Log correlation IDs across client beacons and server logs. Alert on week-over-week p75 regression on tier-1 routes — global averages hide bad canaries.

Leading indicators: error rate, validation failures, queue depth. Lagging: support tickets, conversion, churn. Both must move together to confirm the fix matched user pain.

## Deep dive: third-party drift (6)

Tag managers, chat widgets, and payment iframes change without your deploy. Quarterly audit script inventory on critical routes. Compare lab metrics with ad blockers enabled vs disabled — the delta reveals third-party cost.

For DOM-based XSS prevention in client-rendered apps, corporate proxies and Save-Data alter behavior versus staging on office Wi-Fi. Field validation beats conference demos.

## Deep dive: rollout discipline (7)

location. When rolling out changes to DOM-based XSS prevention in client-rendered apps, compare canary p75 INP and LCP to control for a full business day in target regions before promoting to 100%. Document rollback in the PR: feature flag name, cache purge procedure, or revert commit — whichever restores prior behavior fastest at 2 a.m.

Slice metrics by device class and connection effective type. A fix helping desktop fiber but regressing mid-tier Android 4G should pause rollout, not ship globally.

## Deep dive: failure rehearsal (8)

Rehearse `Trusting client-side routing params for document.write or eval sinks` in a 30-minute game day before peak season. For DOM-based XSS prevention in client-rendered apps, measure time-to-detect and time-to-mitigate — not only time-to-root-cause in a postmortem doc.

Manual paths worth scripting: hard refresh mid-flow, browser back after async submit, double-click primary action, offline toggle during mutation, keyboard-only navigation with screen reader.

## Deep dive: observability (9)

Wire custom RUM marks around the user journey DOM-based XSS prevention in client-rendered apps affects. Log correlation IDs across client beacons and server logs. Alert on week-over-week p75 regression on tier-1 routes — global averages hide bad canaries.

Leading indicators: error rate, validation failures, queue depth. Lagging: support tickets, conversion, churn. Both must move together to confirm the fix matched user pain.

## Deep dive: third-party drift (10)

Tag managers, chat widgets, and payment iframes change without your deploy. Quarterly audit script inventory on critical routes. Compare lab metrics with ad blockers enabled vs disabled — the delta reveals third-party cost.

For DOM-based XSS prevention in client-rendered apps, corporate proxies and Save-Data alter behavior versus staging on office Wi-Fi. Field validation beats conference demos.

## Deep dive: rollout discipline (11)

location. When rolling out changes to DOM-based XSS prevention in client-rendered apps, compare canary p75 INP and LCP to control for a full business day in target regions before promoting to 100%. Document rollback in the PR: feature flag name, cache purge procedure, or revert commit — whichever restores prior behavior fastest at 2 a.m.

Slice metrics by device class and connection effective type. A fix helping desktop fiber but regressing mid-tier Android 4G should pause rollout, not ship globally.

## Deep dive: failure rehearsal (12)

Rehearse `Trusting client-side routing params for document.write or eval sinks` in a 30-minute game day before peak season. For DOM-based XSS prevention in client-rendered apps, measure time-to-detect and time-to-mitigate — not only time-to-root-cause in a postmortem doc.

Manual paths worth scripting: hard refresh mid-flow, browser back after async submit, double-click primary action, offline toggle during mutation, keyboard-only navigation with screen reader.

## Deep dive: observability (13)

Wire custom RUM marks around the user journey DOM-based XSS prevention in client-rendered apps affects. Log correlation IDs across client beacons and server logs. Alert on week-over-week p75 regression on tier-1 routes — global averages hide bad canaries.

Leading indicators: error rate, validation failures, queue depth. Lagging: support tickets, conversion, churn. Both must move together to confirm the fix matched user pain.

## Deep dive: third-party drift (14)

Tag managers, chat widgets, and payment iframes change without your deploy. Quarterly audit script inventory on critical routes. Compare lab metrics with ad blockers enabled vs disabled — the delta reveals third-party cost.

For DOM-based XSS prevention in client-rendered apps, corporate proxies and Save-Data alter behavior versus staging on office Wi-Fi. Field validation beats conference demos.

## Deep dive: rollout discipline (15)

location. When rolling out changes to DOM-based XSS prevention in client-rendered apps, compare canary p75 INP and LCP to control for a full business day in target regions before promoting to 100%. Document rollback in the PR: feature flag name, cache purge procedure, or revert commit — whichever restores prior behavior fastest at 2 a.m.

Slice metrics by device class and connection effective type. A fix helping desktop fiber but regressing mid-tier Android 4G should pause rollout, not ship globally.