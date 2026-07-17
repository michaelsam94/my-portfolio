---
title: "Pa11y for Automated Accessibility Testing"
slug: "pa11y-automated-accessibility-testing"
description: "Pa11y crawls routes for WCAG violations — CI configuration, sitemap-driven audits, and threshold policies."
datePublished: "2026-08-16"
dateModified: "2026-07-17"
tags: ["Accessibility", "Testing", "CI"]
keywords: "pa11y CI, automated accessibility audit, WCAG testing"
faq:
  - q: "What does Pa11y check that axe alone might miss?"
    a: "Pa11y crawls full URLs in a headless browser, catching route-specific issues, navigation flows, and cross-page context. axe in component tests is faster for PR feedback; Pa11y suits sitemap-wide regression sweeps before release."
  - q: "Should Pa11y failures block CI merges?"
    a: "Block on errors (WCAG violations at your configured standard). Warn on notices initially while teams fix legacy debt. Tighten to zero errors on critical paths — checkout, login, settings — first."
  - q: "How do I reduce Pa11y flakiness in CI?"
    a: "Wait for network idle or explicit selectors, pin Pa11y and Chromium versions, run against stable staging URLs, and ignore third-party iframe violations only with documented allowlist entries — not blanket suppression."

---

Accessibility regressions ship when teams rely on manual QA alone before release. Pa11y runs headless Chrome against URLs you specify, reports WCAG issues with selectors and help URLs, and fits CI pipelines better than quarterly manual audits. It does not replace screen reader testing — it catches missing alt text, contrast failures, and invalid ARIA at scale.

This post covers Pa11y CI configuration, sitemap-driven crawls, threshold policies, and how we pair Pa11y with axe without duplicate noise.


## Pa11y CI configuration

```json
{
  "defaults": {
    "standard": "WCAG2AA",
    "timeout": 60000,
    "wait": 500,
    "chromeLaunchConfig": { "args": ["--no-sandbox"] }
  },
  "urls": [
    "http://localhost:3000/",
    "http://localhost:3000/pricing",
    "http://localhost:3000/login"
  ]
}
```

Run via `pa11y-ci` in GitHub Actions after `next build && next start`. Fail the job on `error` count > 0 for protected branches.

## Sitemap-driven audits

Generate URL list from sitemap.xml for nightly cron — catches marketing pages engineers forget:

```bash
curl -s https://staging.example.com/sitemap.xml |   xmllint --xpath '//*[local-name()="loc"]/text()' - |   pa11y-ci --config .pa11yci.json --sitemap -
```

Cap concurrency (`--concurrency 2`) so staging doesn't melt under 400 parallel page loads.

## Threshold policies and baselines

Track error count trend, not binary pass/fail forever:

| Policy | Gate |
|--------|------|
| Critical paths | 0 errors, merge blocked |
| Marketing site | ≤5 known legacy errors with linked tickets |
| Nightly full crawl | Alert Slack if +10 errors vs 7d baseline |

Store `.pa11y-ci-results.json` artifacts per build — diff tickets when new violations appear.

## Pairing Pa11y with axe-core

Use **axe in PR** for changed routes (fast feedback). Use **Pa11y nightly** for full-site regression. Map rule IDs between tools — duplicate reporting the same `color-contrast` failure in both Slack channels erodes trust.

## Dynamic content and auth-gated routes

Pa11y needs login cookies or `actions` scripts to reach authenticated pages:

```json
{
  "urls": [{
    "url": "http://localhost:3000/dashboard",
    "actions": [
      "set field #email to test@example.com",
      "set field #password to testpass",
      "click element #submit",
      "wait for url to be http://localhost:3000/dashboard"
    ]
  }]
}
```

Store test credentials in CI secrets — rotate quarterly.

## False positives and allowlists

`.pa11yci` ignore rules need ticket references:

```json
"ignore": [
  "WCAG2AA.Principle1.Guideline1_4.1_4_3.G18.Fail#payment-iframe"
]
```

Review allowlist monthly — payment iframes often fix contrast on vendor upgrade; your ignore hides real regressions.






## Reporting for product and legal

Export Pa11y HTML reports for accessibility conformance claims — attach to release tickets. WCAG "effort" documentation for EU Accessibility Act requests benefits from dated CI artifacts proving regression testing, not one-time audits.

## Performance impact of accessibility CI

Pa11y adds 2–8 minutes to pipelines depending on URL count. Shard URLs across matrix jobs by path prefix (`/blog`, `/app`) — parallel jobs finish faster than one sequential crawl.

## HTMLCS vs axe runner in Pa11y

Pa11y defaults to HTML_CodeSniffer — rule IDs differ from axe. Teams standardize on `pa11y-runner-axe` for consistent rule naming with component tests:

```bash
npm install pa11y pa11y-ci @pa11y/pa11y-runner-axe
```

```json
"defaults": { "runner": "axe" }
```

## Screen reader spot-check checklist

Automated pass ≠ accessible. After Pa11y green on checkout, manually verify: focus order through payment iframe, error announcements on card decline, modal trap escape on 3DS challenge overlay.

## Integrating with GitHub PR comments

`pa11y-ci-reporter-html` uploads artifact; use GitHub Action to comment error count on PR — reviewers see accessibility diff without opening CI logs. Cap comment length; link full HTML report artifact.

## Mobile viewport audits

Run Pa11y twice per URL — desktop and mobile Chrome emulation (`chromeLaunchConfig.defaultViewport`). Responsive nav drawer violations often missed in desktop-only CI.

## WCAG 2.2 new criteria focus

Target **Focus Not Obscured** and **Dragging Movements** on filter/sort UIs — Pa11y WCAG2AA runner may need WCAG2.2 plugin config as standards mature. Track 2.2 gaps separately from 2.1 debt.

## GitHub Actions workflow example

```yaml
name: pa11y
on: [pull_request]
jobs:
  a11y:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci && npm run build && npm run start &
      - run: npx wait-on http://localhost:3000
      - run: npx pa11y-ci --config .pa11yci.json
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: pa11y-report
          path: pa11y-ci-results.json
```

Pin Node and pa11y versions in repo — unpinned `npx pa11y-ci` broke CI when HTMLCS rules changed upstream.

## Cookie and consent banners

Cookie banners block focus order and trigger contrast violations. Pa11y crawl must dismiss banner via `actions` click or seed `localStorage` consent flag before audit — otherwise every page fails on overlay contrast.

## Flaky rule: animation and motion

Pause CSS animations in CI with `prefers-reduced-motion: reduce` emulation or inject stylesheet `*, *::before, *::after { animation: none !important }` — prevents intermittent "element obscured" failures on loading skeletons.

## Triage workflow for new violations

When Pa11y fails on PR: (1) confirm reproducible locally with same URL, (2) check if violation in third-party iframe — allowlist only with vendor ticket, (3) assign WCAG level — error vs notice, (4) link fix commit to rule ID in PR description for audit trail.

## Pa11y vs Lighthouse accessibility

Lighthouse a11y score is coarse — one violation can drop score disproportionately. Pa11y lists each selector. Use Lighthouse for performance budgets; Pa11y for merge-blocking a11y regressions on critical routes.

## Resources worth bookmarking

Official Pa11y CI docs, deque axe rule descriptions (when using axe runner), and W3C understanding docs linked from each error — paste understanding URL in Jira tickets so fixes educate engineers.

## Monorepo route discovery

In turborepo with multiple apps, generate `.pa11yci` URL list from each app's sitemap in CI matrix — don't hardcode localhost paths that drift.

## Custom rules and standards

Extend pa11y with custom runners for brand requirements (minimum 16px body text). Document divergence from WCAG as internal standard tier.

## Baseline snapshot testing

Store JSON snapshot of violation count per URL — PR fails only on new violations (similar to jest snapshot). Reduces legacy debt paralysis while blocking regressions.

## Designer handoff

Pa11y HTML report links W3C technique URLs — attach report to Figma ticket when contrast fails. Designers fix tokens at source.

## Localization and pa11y

Run pa11y on `/de` and `/en` routes — German copy expansion breaks button overlap violations not seen in English layout.

## Component library gate

Storybook + `@storybook/addon-a11y` for atoms; Pa11y for composed pages — division prevents debating which tool owns buttons vs checkout.

## SLA for fix triage

P0 checkout violation fixed 48h; P2 marketing page 2 sprints — attach SLA to Pa11y rule severity in triage doc.

## Executive reporting

Monthly chart: total violations trending down, new vs fixed — accessibility program needs metrics beyond binary pass for budget renewal.
## Contract testing with design tokens

Export design tokens JSON — script asserts token contrast ratios in CI complementary to Pa11y page scans. Catches systematic button color regression before deploy.

## Violation ownership routing

Pa11y JSON output parsed to assign GitHub CODEOWNERS by URL prefix — `/checkout` violations auto-request review from payments squad.

## Staging data realism

Empty cart checkout skips half of form violations — seed staging with realistic products, errors, and discount states Pa11y actions exercise.

## Performance budget interaction

Pa11y wait 500ms may miss lazy-loaded images without alt — increase wait on media-heavy routes or inject `loading=complete` wait action.

## Contract with legal on WCAG level

Claim WCAG 2.1 AA in terms only if Pa11y gate enforces AA on all revenue paths — marketing claims must match CI standard string.

## On-call for accessibility regressions

Treat P0 a11y on checkout like payment outage — rollback path documented. Color contrast failure on Pay button is revenue incident.

## Resources

- [web.dev — Core Web Vitals](https://web.dev/vitals/)
- [WCAG 2.2 Quick Reference](https://www.w3.org/WAI/WCAG22/quickref/)
- [MDN Web Docs — Web APIs](https://developer.mozilla.org/en-US/docs/Web/API)
- [Next.js Documentation](https://nextjs.org/docs)
- [React Documentation](https://react.dev/)
