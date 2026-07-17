---
title: "AI Agents: Lighthouse Ci Github Action"
slug: "agent-lighthouse-ci-github-action"
description: "Lighthouse Ci Github Action: production patterns for ai teams — design, implementation, testing, security, and operations."
datePublished: "2026-07-14"
dateModified: "2026-07-14"
tags: ["AI", "Agent", "Lighthouse"]
keywords: "agent, lighthouse, ci, github, action, ai, production, engineering, architecture"
faq:
  - q: "Should Lighthouse CI run on every pull request or only on frontend changes?"
    a: "Use path filters so Lighthouse runs when routes, bundles, or SSR templates change — but include shared layout and design-system packages in the filter. Agent chat UIs often regress from backend-driven HTML or streaming partials that path filters miss if scoped too narrowly."
  - q: "How many Lighthouse runs should CI take the median of?"
    a: "Three runs per URL on pinned Chromium is the practical minimum; five if variance exceeds 5% on shared runners. Compare the median score and median metric values, not the best run. A single lucky run hides regressions."
  - q: "What performance metrics matter most for agent-powered dashboards?"
    a: "Prioritize INP and Total Blocking Time on interaction-heavy routes, LCP on marketing and login pages, and CLS on streaming message layouts. Performance score alone is too coarse when token streaming causes layout shift without failing LCP."
  - q: "Can Lighthouse CI authenticate into a logged-in agent workspace?"
    a: "Yes — use LHCI puppeteerScript or a custom collect step that logs in via test credentials stored in GitHub secrets, then navigates to /app/chat before audit. Never commit credentials; rotate test accounts and scope them to read-only fixtures."
---
Your agent dashboard shipped with a 96 Lighthouse score in local dev. Two sprints later, CI is green, but support tickets mention "the chat feels slow" and RUM shows INP at 340ms p75. The diff that caused it merged because nobody ran Lighthouse against the authenticated `/app` route — only the public landing page.

Lighthouse CI in GitHub Actions closes that gap by turning performance checks into a repeatable pipeline artifact: same Chromium version, same throttling profile, same URLs, every pull request. This article walks through wiring LHCI for agent products — including logged-in flows, flaky-run controls, and assertions that fail merges when streaming UI regressions slip through bundle analysis alone.

## Why agent UIs need CI Lighthouse, not spot checks

Agent interfaces combine patterns that punish naive perf testing:

- **Streaming DOM growth** — message lists append tokens without virtualization; LCP and CLS move as content arrives.
- **Heavy client hydration** — markdown renderers, syntax highlighters, and tool-call cards load lazily but block the main thread on first paint.
- **WebSocket or SSE backpressure** — lab tests without live streams miss layout thrash when fifty tool events arrive in one second.

Running Lighthouse manually before release catches none of this at scale. CI enforces budgets on the routes that matter, stores historical reports, and attaches diffs to pull requests so reviewers see *which* metric moved, not just "Perf check failed."

Pair Lighthouse with bundle-size gates: transfer budgets catch new chart libraries; Lighthouse catches main-thread long tasks from parsing large JSON tool payloads.

## Repository layout and configuration

Commit performance config beside the app:

```
.github/workflows/lighthouse-ci.yml
lighthouserc.cjs
perf/
  urls.public.txt
  urls.authenticated.txt
  budgets.json
scripts/
  lhci-auth-puppeteer.js
```

`lighthouserc.cjs` centralizes collection and assertion rules:

```javascript
/** @type {import('@lhci/cli').LHCI.ServerCommand.Options} */
module.exports = {
  ci: {
    collect: {
      url: [
        "http://127.0.0.1:3000/",
        "http://127.0.0.1:3000/pricing",
      ],
      startServerCommand: "npm run start:ci",
      startServerReadyPattern: "ready on",
      numberOfRuns: 3,
      puppeteerScript: "./scripts/lhci-auth-puppeteer.js",
      settings: {
        preset: "desktop",
        chromeFlags: "--no-sandbox --disable-dev-shm-usage",
        throttlingMethod: "simulate",
        onlyCategories: ["performance", "accessibility"],
      },
    },
    assert: {
      assertions: {
        "categories:performance": ["error", { minScore: 0.85 }],
        "largest-contentful-paint": ["error", { maxNumericValue: 2800 }],
        "interactive": ["warn", { maxNumericValue: 4500 }],
        "cumulative-layout-shift": ["error", { maxNumericValue: 0.1 }],
        "total-blocking-time": ["error", { maxNumericValue: 350 }],
      },
    },
    upload: {
      target: "temporary-public-storage",
    },
  },
};
```

For authenticated agent routes, extend collection in a puppeteer script:

```javascript
// scripts/lhci-auth-puppeteer.js
module.exports = async (browser, context) {
  const page = await browser.newPage();
  await page.goto("http://127.0.0.1:3000/login");
  await page.type("#email", process.env.LHCI_TEST_EMAIL);
  await page.type("#password", process.env.LHCI_TEST_PASSWORD);
  await page.click('[data-testid="login-submit"]');
  await page.waitForURL("**/app/**");
  // LHCI continues audit on target URL with session cookies
};
```

Store `LHCI_TEST_EMAIL` and `LHCI_TEST_PASSWORD` in GitHub Actions secrets. Use a dedicated test tenant with frozen fixtures so audits stay deterministic.

## GitHub Actions workflow

Pin Node, Chromium, and `@lhci/cli` versions. Unpinned `@lhci/cli@latest` is a common source of "works on Tuesday" failures.

```yaml
# .github/workflows/lighthouse-ci.yml
name: Lighthouse CI

on:
  pull_request:
    branches: [main]
    paths:
      - "app/**"
      - "components/**"
      - "packages/ui/**"
      - "lighthouserc.cjs"
      - "perf/**"

concurrency:
  group: lhci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lighthouse:
    runs-on: ubuntu-latest
    timeout-minutes: 25

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm

      - name: Install dependencies
        run: npm ci

      - name: Build application
        run: npm run build
        env:
          NEXT_PUBLIC_AGENT_API: http://127.0.0.1:3000/api/mock

      - name: Run Lighthouse CI
        run: npx --yes @lhci/cli@0.14.0 autorun
        env:
          LHCI_TEST_EMAIL: ${{ secrets.LHCI_TEST_EMAIL }}
          LHCI_TEST_PASSWORD: ${{ secrets.LHCI_TEST_PASSWORD }}

      - name: Comment PR with report link
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const links = JSON.parse(fs.readFileSync('.lighthouseci/links.json', 'utf8'));
            const body = `### Lighthouse CI\n${links.map(l => `- [Report](${l})`).join('\n')}`;
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body,
            });
```

For monorepos, matrix over apps or use `working-directory`. Agent backends that SSR chat shells should build with the same `NODE_ENV=production` flags CI uses in deploy.

## Controlling flakiness on shared runners

Lighthouse variance above 5% erodes trust and invites `#skip-lhci` comments. Mitigations that work in production teams:

| Technique | Why it helps |
|-----------|--------------|
| Pin `@lhci/cli` and system Chrome | Eliminates audit-engine drift |
| `numberOfRuns: 3`, assert on median | One cold cache outlier does not fail PRs |
| Dedicated `runs-on` label or larger runner | CPU steal causes TBT swings |
| Disable animations in test theme | CLS from marketing confetti is noise |
| Warm server before collect | First request compiles SSR routes |

If variance persists, split **warn** vs **error** assertions: warn on INP-like proxies (TBT, max potential FID) for two sprints while fixing infra, then promote to error.

## Budget design for agent routes

Avoid one global performance score. Define per-route contracts in `perf/budgets.json`:

| Route | LCP (ms) | TBT (ms) | CLS | JS (KB) |
|-------|----------|----------|-----|---------|
| `/` | 2200 | 200 | 0.08 | 180 |
| `/app/chat` | 2800 | 350 | 0.05 | 420 |
| `/app/settings` | 2500 | 250 | 0.06 | 280 |

Derive numbers from field RUM p75, then tighten 10–15% for lab throttling. Agent chat routes legitimately carry more JS; budget accordingly rather than sharing marketing thresholds.

When a feature exceeds budget, require an explicit bump in the same PR with product sign-off in the commit message. Silent erosion recreates the problem the gate exists to prevent.

## Accessibility assertions alongside performance

Agent UIs fail accessibility in predictable ways: streaming regions without `aria-live` politeness, tool cards that steal focus, icon-only buttons without labels. Enable the accessibility category in LHCI and assert minimum score on public and authenticated routes.

```javascript
assertions: {
  "categories:accessibility": ["error", { minScore: 0.92 }],
  "color-contrast": "warn",
  "button-name": "error",
}
```

Accessibility regressions in agent products often correlate with perf work — disabling animations incorrectly, rendering markdown as raw HTML, or lazy-loading labels. Running both categories in one job keeps the feedback loop single.

## Operational integration

Treat LHCI like any other required check on protected branches. Store uploaded reports (LHCI server, GCS, or temporary links) for at least 90 days so you can bisect when RUM degrades without a failing PR.

Alert when **main branch median LCP** trends up three consecutive days even if no assertion failed — soft drift precedes hard failures. Correlate with deploy markers and model-version flags; sometimes backend latency masquerades as frontend LCP on SSR chat shells.

Document a local command mirroring CI:

```bash
npm run build && npx @lhci/cli autorun
```

Developers should reproduce failures in under ten minutes. If local and CI diverge by more than 5%, fix environment parity before loosening budgets.

## Failure modes teams actually hit

**Mock API too fast.** CI uses stubbed agent responses; production streams for eight seconds. Supplement LHCI with RUM on `/app/chat` and synthetic checks that replay recorded SSE traces in staging.

**Login puppeteer race.** Submit fires before hydration completes; audit runs on login page. Wait for network idle or a stable selector tied to app shell readiness.

**Third-party scripts in preview deploys.** Preview URLs inject analytics not present locally. Either block third parties in `startServerCommand` env or audit preview with the same CSP as production.

**Bundle gate passes, TBT fails.** Dynamic `import()` of a 2 MB highlighter chunk loads after FCP but blocks input. Add route-level `import()` analysis in CI, not just total JS weight.

## The takeaway

Lighthouse CI in GitHub Actions is not a vanity badge — it is a contract between frontend, design, and agent platform teams that critical routes stay within measurable bounds. Pin tooling, audit authenticated agent paths, assert medians over multiple runs, and pair lab budgets with field RUM. The goal is merges that cannot silently ship streaming UI regressions, not a green score on the marketing homepage alone.

## Resources

- [GoogleChrome/lighthouse-ci](https://github.com/GoogleChrome/lighthouse-ci) — official LHCI CLI and server documentation
- [web.dev/vitals](https://web.dev/vitals/) — Core Web Vitals definitions and thresholds
- [GitHub Actions: workflow syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions) — concurrency, secrets, path filters
- [Puppeteer authentication recipes](https://pptr.dev/guides/authentication) — session reuse for logged-in audits
- [Calibre / Speedcurve CI integrations](https://calibreapp.com/docs) — optional hosted comparison when temporary public storage is insufficient
