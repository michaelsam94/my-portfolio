---
title: "Bundle Splitting Strategies"
slug: "web-performance-bundle-splitting"
description: "Reduce initial load with code splitting: dynamic imports, route-based chunks, vendor separation, bundle analysis, and preload strategies for modern bundlers."
datePublished: "2026-05-07"
dateModified: "2026-05-07"
tags: ["Web", "Performance", "JavaScript", "Frontend"]
keywords: "code splitting, bundle splitting, dynamic import, webpack chunks, Vite rollup, tree shaking, lazy loading"
faq:
  - q: "What is the difference between code splitting and tree shaking?"
    a: "Tree shaking removes unused exports from modules at build time — if you import one function from a library, the rest of the library is excluded. Code splitting divides your application into separate bundles loaded on demand. Tree shaking reduces bundle size; code splitting reduces initial bundle size by deferring code the user hasn't needed yet."
  - q: "When should I use dynamic import() versus static import?"
    a: "Use static imports for code needed on every page — utilities, core components, polyfills. Use dynamic import() for route-specific pages, modal content, admin panels, chart libraries, and anything behind user interaction. The dynamic import creates a separate chunk fetched only when the import executes."
  - q: "How do I know if my bundles are too large?"
    a: "Analyze with webpack-bundle-analyzer, rollup-plugin-visualizer, or Vite's built-in stats. Flag any initial chunk over 200KB gzipped. Check Network tab for unused JavaScript in Lighthouse. Set performance budgets in CI — fail builds when main chunk exceeds your threshold."
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

## Measuring success in production

Deploy changes behind feature flags when possible so you can compare metrics between control and treatment groups. Use Real User Monitoring to capture performance data from actual devices and network conditions — lab tools alone miss the long tail of user experiences. Set up alerts for regressions: a 10% LCP increase week-over-week warrants investigation before it hits CrUX.

Document your baseline metrics before making changes. Performance work without measurement is guesswork. Share results with the team — concrete numbers ("LCP improved 800ms on mobile") build support for continued investment in web performance and reliability.

Review changes quarterly. Browser updates, new API support, and traffic pattern shifts can obsolete previous optimizations or create new opportunities. What worked in 2024 may not be the best approach in 2026.

## Additional production considerations

Teams often underestimate the maintenance cost of performance optimizations. Automate what you can: CI bundle budgets, Lighthouse CI on PRs, and RUM dashboards that alert on regressions. Manual audits don't scale past a handful of pages.

Security and performance intersect more than teams expect. Third-party scripts that hurt INP also expand your attack surface. Self-hosting fonts and critical assets reduces both latency and supply-chain risk. Review every external dependency quarterly — remove what you no longer need.

Accessibility and performance share goals: semantic HTML helps screen readers and gives the browser better rendering hints. Native elements like dialog, popover, and details reduce JavaScript while improving accessibility. Prefer platform features over custom implementations when they meet your requirements.

Mobile users dominate traffic for most sites. Test on real mid-tier Android hardware, not just desktop Chrome. Simulated throttling in DevTools approximates network conditions but not CPU constraints. A fix that helps desktop may be invisible on mobile if the bottleneck is JavaScript execution, not network.

Collaborate with backend teams on TTFB and API response times. Frontend optimizations can't fix a 2-second server response. Set SLAs for API endpoints that feed critical pages and measure them in the same RUM pipeline as Core Web Vitals.

## Resources

- [MDN: Dynamic imports](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/import)
- [Vite build options](https://vitejs.dev/config/build-options.html)
- [webpack code splitting](https://webpack.js.org/guides/code-splitting/)
- [rollup-plugin-visualizer](https://github.com/btd/rollup-plugin-visualizer)
- [web.dev: Reduce JavaScript payloads](https://web.dev/articles/reduce-javascript-payloads-using-code-splitting)
