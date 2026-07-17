---
title: "Dynamic Import with SSR False in Next.js"
slug: "nextjs-dynamic-import-ssr-false"
description: "Lazy-load client-only components with next/dynamic and ssr:false without breaking RSC boundaries."
datePublished: "2027-01-08"
dateModified: "2026-07-17"
tags:
keywords: "next/dynamic ssr false, client-only component Next.js"
faq:
  - q: "When should I use ssr: false?"
    a: "For browser-only APIs: window, localStorage, WebGL, maps, rich text editors. Never for SEO-critical content."
  - q: "Can I use ssr:false in Server Components?"
    a: "No. dynamic() with ssr:false must be called from a Client Component. Import the dynamic wrapper from a 'use client' file."
  - q: "Does ssr:false hurt Core Web Vitals?"
    a: "It can increase CLS if loading state lacks dimensions. Always provide loading skeleton with fixed height."
---
A chart library accessed `window` during server render and crashed the build. Wrapping it in `next/dynamic` with `{ ssr: false }` fixed production—but introduced a layout shift that dropped CLS scores. Dynamic imports defer JavaScript and skip server rendering for client-only modules; used correctly they shrink bundles, used carelessly they flash empty boxes on screen.

## Basic pattern

```tsx
"use client";
import dynamic from "next/dynamic";

const Chart = dynamic(() => import("./Chart"), {
  ssr: false,
  loading: () => <div className="h-64 animate-pulse bg-muted" />,
});

export function DashboardChart({ data }) {
  return <Chart data={data} />;
}
```

The `"use client"` boundary is mandatory. Server Components cannot call `dynamic(..., { ssr: false })`.

## Splitting heavy editor bundles

Rich text editors (TipTap, Lexical, Monaco) add 200–800KB gzip. Load only on edit routes:

```tsx
const Editor = dynamic(() => import("@/components/RichEditor"), {
  ssr: false,
  loading: () => <EditorSkeleton />,
});
```

Measure with `@next/bundle-analyzer`. Confirm editor chunk absent from homepage bundle.

## Named exports

```tsx
const DatePicker = dynamic(
  () => import("./DatePicker").then((m) => m.DatePicker),
  { ssr: false }
);
```

Default export preferred for tree-shaking clarity.

## Prefetching dynamic chunks

Next.js prefetches dynamic imports on hover for `<Link>` routes. Client-only components still download on navigation—ssr:false does not mean lazy on interaction unless you combine with conditional render:

```tsx
const [showMap, setShowMap] = useState(false);
return (
  <>
    <button onClick={() => setShowMap(true)}>Show map</button>
    {showMap && <MapComponent />}
  </>
);
```

## App Router and RSC composition

Pattern: Server Component fetches data, passes props to Client wrapper that dynamic-imports visualization:

```tsx
// app/analytics/page.tsx — Server Component
export default async function Page() {
  const data = await getAnalytics();
  return <AnalyticsClient data={data} />;
}

// AnalyticsClient.tsx — "use client"
const Chart = dynamic(() => import("./Chart"), { ssr: false });
export function AnalyticsClient({ data }) { return <Chart data={data} />; }
```

Never fetch inside client-only dynamic components if data is needed for SEO—fetch on server, render client-only shell.

## Error boundaries

Dynamic import failures (network blip on chunk load) need error UI:

```tsx
const Map = dynamic(() => import("./Map"), {
  ssr: false,
  loading: () => <MapSkeleton />,
});
// Wrap in React error boundary at parent level
```

## Testing

Jest/Vitest cannot render ssr:false components without mock. Use `dynamic: () => require('./Component')` mock or test the loading skeleton separately.

## Anti-patterns

- ssr:false on above-fold LCP content — kills SEO and delays paint
- Multiple nested dynamic imports without loading states — cumulative layout shift
- ssr:false to avoid fixing hydration mismatches — fix the mismatch instead

## Resources

- [next/dynamic documentation](https://nextjs.org/docs/app/building-your-application/optimizing/lazy-loading)
- [React lazy and Suspense](https://react.dev/reference/react/lazy)


## Monitoring chunk load failures


Track dynamic import errors in RUM: `import().catch` wrapper or error boundary reporting. Chunk load failures spike after deploys when users hold stale HTML referencing old chunk hashes—pair with long cache on hashed assets and short cache on HTML.


## Accessibility during load


Loading skeletons need `aria-busy="true"` and meaningful labels. Screen readers should announce when client-only content replaces skeleton. Do not trap focus in loading state.


## Production notes on dynamic import ssr false

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on dynamic import ssr false

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on dynamic import ssr false

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on dynamic import ssr false

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on dynamic import ssr false

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on dynamic import ssr false

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on dynamic import ssr false

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on dynamic import ssr false

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on dynamic import ssr false

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on dynamic import ssr false

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on dynamic import ssr false

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on dynamic import ssr false

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on dynamic import ssr false

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on dynamic import ssr false

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on dynamic import ssr false

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on dynamic import ssr false

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on dynamic import ssr false

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on dynamic import ssr false

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on dynamic import ssr false

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on dynamic import ssr false

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on dynamic import ssr false

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.


## Production notes on dynamic import ssr false

Ship incrementally with rollback paths. Measure p95 latency and error rate before and after changes. Document trade-offs in ADRs so on-call understands why the current design exists.
