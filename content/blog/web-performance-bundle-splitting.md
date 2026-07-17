---
title: "Bundle Splitting Strategies"
slug: "web-performance-bundle-splitting"
description: "Reduce initial load with code splitting: dynamic imports, route-based chunks, vendor separation, bundle analysis, and preload strategies for modern bundlers."
datePublished: "2026-05-07"
dateModified: "2026-07-17"
tags: ["Web", "Performance", "JavaScript", "Frontend"]
keywords: "code splitting, bundle splitting, dynamic import, webpack chunks, Vite rollup, tree shaking, lazy loading"
faq:
  - q: "What is the difference between code splitting and tree shaking?"
    a: "Tree shaking removes unused exports from modules at build time — if you import one function from a library, the rest of the library is excluded. Code splitting divides your application into separate bundles loaded on demand. Tree shaking reduces bundle size; code splitting reduces initial bundle size by deferring code the user hasn't needed yet."
  - q: "When should I use dynamic import() versus static import?"
    a: "Use static imports for code needed on every page — utilities, core components, polyfills. Use dynamic import() for route-specific pages, modal content, admin panels, chart libraries, and anything behind user interaction. The dynamic import creates a separate chunk fetched only when the import executes."
  - q: "How do I know if my bundles are too large?"
    a: "Analyze with webpack-bundle-analyzer, rollup-plugin-visualizer, or Vite's built-in stats. Flag any initial chunk over 200KB gzipped. Check Network tab for unused JavaScript in Lighthouse. Set performance budgets in CI — fail builds when main chunk exceeds your threshold."
faqAnswers:
  - question: "When is web performance bundle splitting the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for web performance bundle splitting?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back web performance bundle splitting safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
Lighthouse flagged our app for shipping 890KB of JavaScript on the homepage. The bundle included an admin dashboard, a PDF renderer, and a charting library — none of which the homepage used. Route-based splitting and three dynamic imports dropped the initial payload to 142KB. First Contentful Paint improved by 1.8 seconds on a simulated 4G connection.

## Dynamic imports

```javascript
// Creates a separate chunk loaded on demand
const AdminPanel = lazy(() => import('./AdminPanel'));

function App() {
  return (
    <Suspense fallback={<Spinner />}>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/admin" element={<AdminPanel />} />
      </Routes>
    </Suspense>
  );
}
```

Vite and webpack automatically create a chunk file for each dynamic import path.

## Route-based splitting

Split at route boundaries — each page becomes its own chunk:

```javascript
// React Router with lazy routes
const routes = [
  { path: '/', component: lazy(() => import('./pages/Home')) },
  { path: '/dashboard', component: lazy(() => import('./pages/Dashboard')) },
  { path: '/settings', component: lazy(() => import('./pages/Settings')) },
];
```

Users visiting the homepage never download dashboard or settings code.

## Vendor chunk separation

Extract third-party libraries into a stable vendor chunk:

```javascript
// vite.config.ts
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
          charts: ['d3', 'recharts'],
        },
      },
    },
  },
});
```

Vendor chunks cache independently — when your app code changes, users don't re-download React.

## Component-level splitting

Split heavy components loaded on interaction:

```javascript
async function openPdfViewer(url) {
  const { PdfViewer } = await import('./PdfViewer');
  renderPdfViewer(PdfViewer, url);
}

button.addEventListener('click', () => openPdfViewer('/doc.pdf'));
```

Libraries like `@react-pdf/renderer` (400KB+) belong behind user actions, not in the initial bundle.

## Analyzing bundles

Vite with visualizer:

```bash
npm install -D rollup-plugin-visualizer

# vite.config.ts
import { visualizer } from 'rollup-plugin-visualizer';

plugins: [
  visualizer({ open: true, gzipSize: true }),
]
```

Look for:

- Duplicate dependencies across chunks
- Entire libraries imported for one function
- Large dependencies in the main chunk that could be lazy-loaded

Fix common issues:

```javascript
// Bad: imports entire lodash (70KB)
import _ from 'lodash';
_.debounce(fn, 300);

// Good: imports only debounce (2KB)
import debounce from 'lodash/debounce';
```

## Preloading critical chunks

Hint the browser to fetch upcoming chunks:

```html
<link rel="modulepreload" href="/assets/Dashboard-abc123.js" />
```

React Router can prefetch route chunks on link hover:

```jsx
<Link to="/dashboard" onMouseEnter={() => import('./pages/Dashboard')}>
  Dashboard
</Link>
```

Preload the next likely route without blocking the current page.

## Performance budgets

Set CI-enforced limits:

```javascript
// vite.config.ts with budget plugin
{
  name: 'bundle-budget',
  generateBundle(_, bundle) {
    for (const [name, chunk] of Object.entries(bundle)) {
      if (chunk.type === 'chunk' && chunk.code.length > 200_000) {
        this.warn(`Chunk ${name} exceeds 200KB limit`);
      }
    }
  },
}
```

| Chunk | Budget (gzip) |
|---|---|
| Main/entry | < 150 KB |
| Route chunks | < 100 KB each |
| Vendor | < 200 KB |
| Total initial | < 300 KB |

## Splitting strategy checklist

1. Split by route — every page gets its own chunk
2. Split heavy libraries — charts, editors, PDF, maps
3. Separate vendor from app code — stable caching
4. Tree-shake aggressively — named imports, side-effect-free modules
5. Analyze regularly — run bundle visualizer in CI
6. Preload predicted navigation — hover and viewport hints

## Dynamic import patterns in Next.js

Next.js App Router lazy-loads by default with dynamic():

```typescript
import dynamic from 'next/dynamic';

const Chart = dynamic(() => import('./Chart'), {
  loading: () => <Skeleton />,
  ssr: false,
});
```

Set `ssr: false` for browser-only libraries. The chart chunk loads only when the component renders.

## Monitoring bundle size in CI

Add `@next/bundle-analyzer` or `rollup-plugin-visualizer` to your CI pipeline. Fail builds when the main chunk grows more than 10KB week-over-week. Track trends, not just absolute limits.

## Module federation caveat

Module Federation shares dependencies at runtime across micro-frontends—reduces duplicate React but adds runtime orchestration complexity. Measure LCP impact of federation bootstrap before adopting for performance reasons alone.

## Service worker precaching vs splitting

Workbox precache main shell; runtime cache route chunks on first visit. Version precache manifest on deploy—stale SW serving old chunk hashes causes load failures; `skipWaiting` + `clientsClaim` strategy documented in SW migration runbook.

## Dynamic import boundaries

Split at route level first, then heavy components (charts, editors). `React.lazy` + Suspense needs error boundary — failed chunk load on CDN glitch should retry, not white screen.

## Analyze duplicate packages

`npm ls lodash` — multiple versions bloat chunks. Resolve with bundler alias or pnpm overrides. Module federation shares deps but adds runtime orchestration — measure LCP impact before adopting for perf alone.

## Practical follow-through (1)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Practical follow-through (2)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Practical follow-through (3)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Practical follow-through (4)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Practical follow-through (5)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Resources

- [MDN: Dynamic imports](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/import)
- [Vite build options](https://vitejs.dev/config/build-options.html)
- [webpack code splitting](https://webpack.js.org/guides/code-splitting/)
- [rollup-plugin-visualizer](https://github.com/btd/rollup-plugin-visualizer)
- [web.dev: Reduce JavaScript payloads](https://web.dev/articles/reduce-javascript-payloads-using-code-splitting)

## Save-Data aware prefetch

Skip hover prefetch when `navigator.connection.saveData` is true — mobile users on metered plans should not download route chunks speculatively.