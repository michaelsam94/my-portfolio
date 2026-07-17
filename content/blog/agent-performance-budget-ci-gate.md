---
title: "AI Agents: Performance Budget Ci Gate"
slug: "agent-performance-budget-ci-gate"
description: "Enforce web performance budgets in CI with Lighthouse, bundle analysis, and flaky-test controls—so regressions fail pulls before users feel them."
datePublished: "2026-07-11"
dateModified: "2026-07-11"
tags: ["AI", "Agent", "Performance"]
keywords: "performance budget, CI gate, Lighthouse CI, bundle size, Core Web Vitals, regression prevention"
faq:
  - q: "Which metrics belong in a performance budget?"
    a: "Start with field-aligned Core Web Vitals—LCP, INP, CLS—plus transfer size for JavaScript and CSS on critical routes. Add TTFB for SSR apps and main-thread blocking time if your product is interaction-heavy. Avoid vanity scores alone; budget real user metrics proxies lab can approximate."
  - q: "Should performance gates block merges on first failure?"
    a: "Use warn-only for two sprints while baselines stabilize, then enforce on protected branches. First failures should post a diff comment with the metric, delta, and likely file—developers fix faster when the bot names the offending chunk."
  - q: "How do you reduce Lighthouse CI flakiness?"
    a: "Pin Chromium version, run three medians and compare the median not the best, throttle CPU and network consistently, warm caches identically, and disable unrelated animations in test accounts. Never run perf jobs on shared runners without resource isolation if variance exceeds 5%."
  - q: "What if a legitimate feature exceeds the budget?"
    a: "Require an explicit budget bump in the same PR with product sign-off in the commit message or linked ticket. Budgets are contracts; silent erosion recreates the problem you built the gate to stop."
---
Performance regressions rarely arrive as a single 800 KB dependency. They arrive as twelve "small" changes across three teams: a marketing pixel here, a chart library there, an icon pack imported with `import *`. By the time Real User Monitoring shows LCP climbing, the diff that caused it is six releases ago and nobody owns the rollback.

A performance budget CI gate turns "we should check Lighthouse before release" into a mechanical merge blocker on critical routes. This article covers choosing budgets, wiring Lighthouse CI and bundle checks into GitHub Actions, and keeping the signal trustworthy enough that engineers do not `#skip-perf` every other PR.

## Budgets are per-route contracts, not global scores

One global "Performance score > 90" fails teams building both a marketing homepage and a logged-in dashboard with WebSockets. Define budgets per URL or user journey:

| Route | LCP (lab) | JS transfer | CSS transfer | Notes |
|-------|-----------|-------------|--------------|-------|
| `/` | ≤ 2.2s | ≤ 180 KB | ≤ 40 KB | SSR hero image priority |
| `/app/dashboard` | ≤ 2.8s | ≤ 420 KB | ≤ 60 KB | Code-split charts |
| `/checkout` | ≤ 2.0s | ≤ 150 KB | ≤ 30 KB | Zero third-party scripts |

Derive numbers from **field data** (CrUX, RUM) at p75, then tighten 10–15% in lab to account for throttling variance. If you lack field data, ship RUM first—budgets without production baselines are guesses.

Also budget **JavaScript execution time** on interaction-heavy SPAs. Transfer size alone misses hydrated frameworks that parse large JSON on the main thread.

## Repository layout for budget as code

Commit budgets beside the app so changes are reviewed like any other config:

```
perf/
  budgets.json          # thresholds per URL
  lighthouserc.js       # LHCI config
  urls.txt              # paths to test
scripts/
  check-bundle-size.mjs # webpack/vite stats gate
```

`budgets.json` example consumable by custom scripts and LHCI assertions:

```json
{
  "/": {
    "resourceSizes": [
      { "resourceType": "script", "budget": 184320 },
      { "resourceType": "stylesheet", "budget": 40960 }
    ],
    "timings": [
      { "metric": "largest-contentful-paint", "budget": 2200 },
      { "metric": "cumulative-layout-shift", "budget": 0.1 }
    ]
  }
}
```

Document how to run locally: `npm run perf:check` should mirror CI within 5% variance.

## Lighthouse CI in GitHub Actions

Pin versions. Unpinned `@lhci/cli@latest` is a flaky-test factory.

```yaml
# .github/workflows/performance.yml
name: Performance Budget

on:
  pull_request:
    branches: [main]

jobs:
  lighthouse:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm

      - run: npm ci
      - run: npm run build
      - run: npm run start:ci &  # production server on :3000
      - run: npx wait-on http://127.0.0.1:3000

      - name: Run Lighthouse CI
        run: npx @lhci/cli@0.14.0 autorun
        env:
          LHCI_GITHUB_APP_TOKEN: ${{ secrets.LHCI_GITHUB_APP_TOKEN }}

      - name: Bundle size gate
        run: node scripts/check-bundle-size.mjs
```

`lighthouserc.js`:

```javascript
module.exports = {
  ci: {
    collect: {
      url: ["http://127.0.0.1:3000/", "http://127.0.0.1:3000/app/dashboard"],
      numberOfRuns: 3,
      settings: {
        preset: "desktop",
        throttling: {
          rttMs: 40,
          throughputKbps: 10240,
          cpuSlowdownMultiplier: 1,
        },
      },
    },
    assert: {
      assertions: {
        "largest-contentful-paint": ["error", { maxNumericValue: 2800 }],
        "total-blocking-time": ["warn", { maxNumericValue: 200 }],
        "resource-summary:script:size": ["error", { maxNumericValue: 430000 }],
      },
    },
    upload: {
      target: "temporary-public-storage",
    },
  },
};
```

LHCI compares median of three runs. Use `error` for merge blockers, `warn` for metrics still stabilizing.

## Bundle size script that names the offender

Developers ignore "budget exceeded." They fix "added 92 KB via `recharts` in `DashboardChart.tsx`."

```javascript
// scripts/check-bundle-size.mjs
import { readFileSync } from "node:fs";
import gzipSize from "gzip-size";

const budgets = JSON.parse(readFileSync("perf/budgets.json", "utf8"));
const stats = JSON.parse(readFileSync("dist/stats.json", "utf8")); // webpack --json

const mainChunk = stats.assets.find((a) => a.name.startsWith("main"));
const size = gzipSize.sync(readFileSync(`dist/${mainChunk.name}`));
const budget = budgets["/app/dashboard"].resourceSizes.find(
  (r) => r.resourceType === "script"
).budget;

if (size > budget) {
  const modules = stats.modules
    .filter((m) => m.size > 5000)
    .sort((a, b) => b.size - a.size)
    .slice(0, 5)
    .map((m) => `  ${m.size} bytes  ${m.name}`)
    .join("\n");

  console.error(
    `JS gzip ${size} exceeds budget ${budget} by ${size - budget} bytes\nTop modules:\n${modules}`
  );
  process.exit(1);
}
```

Ensure production build emits `stats.json` in CI only—do not ship it to users.

## Controlling flake and false positives

Flaky perf CI erodes trust faster than no CI. Mitigations:

- **Dedicated runner labels** or self-hosted agents with fixed CPU for perf jobs
- **Median of N runs** (3 minimum; 5 for noisy SPAs)
- **Seed data** — fixed test user, frozen clock, disabled feature-flag randomness
- **Block third-party network** in CI or use mock ad/analytics endpoints; external scripts dominate variance
- **Compare against base branch** — fail only if delta exceeds threshold (e.g., LCP +300ms vs main) when absolute budgets are tight

```javascript
// Pseudo: delta gate — fail if PR regresses main median by >5%
const mainLcp = await fetchMainBranchArtifact("lcp-median");
const prLcp = currentRun.medianLcp;
if (prLcp > mainLcp * 1.05) {
  fail(`LCP regressed ${prLcp - mainLcp}ms vs main (${mainLcp}ms)`);
}
```

Store main-branch artifacts from the last green deploy.

## Team workflow integration

1. **Design review** — new routes add a row to `budgets.json` before UI ships.
2. **PR template** — checkbox: "Perf CI green or budget updated with ticket."
3. **Bot comment** — LHCI posts comparison table; required review for infra team only when budget file changes.
4. **Release** — sync lab budgets quarterly against CrUX p75 movement.

When product requests a heavy widget, the negotiation is numeric: "Accept 40 KB JS increase on dashboard—bump budget in same PR with VP sign-off."

## What to gate in CI vs monitor in production

| Signal | CI gate | Production monitor |
|--------|---------|-------------------|
| LCP on critical routes | Yes (lab proxy) | RUM p75 alert |
| INP | Warn in CI | RUM primary |
| CLS | Yes | RUM |
| JS bundle size | Yes | Optional |
| API latency | No (use contract tests) | APM SLO |
| CDN cache hit ratio | No | Dashboard |

CI catches preventable diffs; RUM catches configuration and traffic shifts lab never sees.

## When the gate fails mid-sprint

Triage order:

1. Re-run job once—variance vs real regression
2. Check if failure is third-party (compare network waterfall to main)
3. Identify chunk diff via stats.json
4. Fix, lazy-load, or remove—budget bump is last resort

Keep a public `#perf-ci` channel with last month's false-positive rate. Transparency keeps enforcement credible.

## Extending gates to preview deployments

Static CI on localhost misses CDN configuration, Brotli compression, and edge caching. Optionally run **scheduled** Lighthouse against staging or preview URLs with the same budgets but looser thresholds (+10%). Nightly drift catches infra regressions PR gates cannot see—misconfigured cache headers, accidental `no-store` on static assets, TLS middleboxes adding latency.

Do not block PRs on preview-only jobs; preview environments vary in cold-start behavior. Use them for trend graphs and Slack alerts, not merge gates.

## Accessibility and performance overlap

Focus management, layout shifts from lazy-loaded fonts, and modal scroll lock bugs hurt both CLS and accessibility scores. When perf CI flags CLS regression, check whether the fix is purely visual (reserve space for ads) or structural (missing dimensions on images). Teams that treat CLS as a design-system concern fix faster than teams that treat it as a Lighthouse chore.

Performance budget CI gates work when budgets reflect real user journeys, scripts tell engineers exactly what grew, and flake is fought as seriously as test flake. The outcome is not a green Lighthouse badge—it is one less silent multi-release slowdown reaching production.

## Resources

- [web.dev: Performance budgets](https://web.dev/articles/performance-budgets-101)
- [Lighthouse CI documentation](https://github.com/GoogleChrome/lighthouse-ci/blob/main/docs/getting-started.md)
- [Google Chrome: Core Web Vitals](https://web.dev/articles/vitals)
- [webpack-bundle-analyzer](https://github.com/webpack-contrib/webpack-bundle-analyzer)
- [Calibre: How to set useful performance budgets](https://calibreapp.com/docs/budgets/performance-budgets)
