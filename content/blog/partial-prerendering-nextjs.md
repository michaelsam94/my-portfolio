---
title: "Partial Prerendering: Static Speed, Dynamic Content"
slug: "partial-prerendering-nextjs"
description: "Partial Prerendering in Next.js explained: serve a static shell instantly from the edge, stream the dynamic holes, and stop choosing between fast and fresh."
datePublished: "2026-06-22"
dateModified: "2026-07-17"
tags: ["Next.js", "Performance", "React", "Rendering"]
keywords: "Partial Prerendering, PPR, Next.js, static shell, streaming, edge caching, dynamic content"
faq:
  - q: "What is Partial Prerendering in Next.js?"
    a: "Partial Prerendering (PPR) is a rendering model that serves a static, instantly-cacheable shell of a page while streaming in the dynamic parts at request time. It combines the speed of static generation with the freshness of server rendering in a single page, instead of forcing you to pick one per route."
  - q: "How is PPR different from ISR or SSR?"
    a: "SSR renders the whole page dynamically on each request; ISR serves a fully static page and regenerates it on a schedule. PPR mixes both within one page — the static shell is served immediately from cache, and only the dynamic components (wrapped in Suspense) are computed per request and streamed in."
  - q: "When should I use Partial Prerendering?"
    a: "Use PPR for pages that are mostly static but have a few personalized or frequently-changing regions — a product page with live inventory, a dashboard with a static frame and dynamic widgets, or a marketing page with a personalized header. It gives fast first paint without making the whole page uncacheable."
---

For years, Next.js rendering was a per-route decision with an annoying trade-off baked in: make the page static and it's blazing fast but can't show anything personalized or fresh, or make it dynamic and it's always current but pays server-render latency on every request. Real pages rarely fit either box. A product page is 90% static — layout, description, images — with a 10% dynamic sliver like live inventory or a personalized recommendation. Partial Prerendering (PPR) exists to stop forcing that all-or-nothing choice.

The idea: serve a static shell instantly, and stream the dynamic holes in at request time, on the same page. Here's how it works and where it actually helps.

## The problem PPR solves

Consider a typical product page. Under the old model you had two bad options. Static generation gives you an instant, cacheable page, but now the "12 left in stock" and "recommended for you" bits are frozen at build time — useless. Switch the route to dynamic rendering and those bits are fresh, but now the *entire* page, including the parts that never change, is computed per request and can't sit in a CDN cache. You've made 90% of the page slow to keep 10% of it fresh.

PPR refuses the premise. It looks at your page, finds the parts that can be prerendered, bakes those into a static shell, and marks the dynamic parts as holes to be filled per request:

```tsx
import { Suspense } from "react";

export default function ProductPage({ id }: { id: string }) {
  return (
    <main>
      <ProductHeader id={id} />                    {/* static: prerendered */}
      <ProductDescription id={id} />               {/* static: prerendered */}
      <Suspense fallback={<InventorySkeleton />}>
        <LiveInventory id={id} />                   {/* dynamic: streamed at request time */}
      </Suspense>
      <Suspense fallback={<RecsSkeleton />}>
        <Recommendations userId={/* per-user */ null} /> {/* dynamic: streamed */}
      </Suspense>
    </main>
  );
}
```

The Suspense boundary is the mechanism. Anything outside a Suspense boundary that doesn't read request-time data (cookies, headers, search params) gets prerendered into the static shell. Anything inside a boundary that *does* read request-time data becomes a dynamic hole. You express the split with component structure, not route config.

## How it actually serves

The serving path is what makes PPR fast. On a request:

1. The static shell is served *immediately* from the edge cache — no server render, no database, just cached HTML. First paint is essentially instant, the same speed as a fully static page.
2. In the same streamed response, the dynamic holes are computed on the server and streamed in as they resolve, replacing their fallback skeletons.

So the user sees a complete, laid-out page right away, with the personalized and live bits filling in a beat later — rather than staring at a blank screen while the whole page renders, or seeing a stale page. It's one HTTP response that starts static and finishes dynamic. This is the streaming SSR model from [React Server Components in production](https://blog.michaelsam94.com/react-server-components-production/) applied at the page-architecture level, with the added twist that the shell is CDN-cacheable.

## Why this is better than the alternatives

The comparison table makes the value clear:

| Model | First paint | Freshness | Cacheable at edge |
|---|---|---|---|
| Full static (SSG) | Instant | Stale | Yes |
| ISR | Instant | Periodic | Yes (until revalidate) |
| Full dynamic (SSR) | Slow (per-request render) | Always fresh | No |
| Partial Prerendering | Instant (shell) | Dynamic parts always fresh | Shell yes, holes no |

PPR is the only row that gets instant first paint *and* per-request freshness on the parts that need it. You're no longer trading the whole page's speed for one widget's freshness. The static shell absorbs the latency win; the holes absorb the freshness need.

## The design skill: minimize the dynamic surface

The trap with PPR is treating it as "turn it on and everything gets fast." What actually determines the win is how much of your page you keep static. Every component that reads request-time data pulls itself and its subtree into the dynamic path. So the discipline is:

- **Push dynamic reads to leaves.** Read cookies/headers as deep in the tree as possible so the largest amount of surrounding UI stays prerenderable — the same "push the boundary down" instinct as the RSC client/server split.
- **Wrap only the truly dynamic bits in Suspense.** A too-large Suspense boundary makes a big region dynamic when only a small piece of it needed to be.
- **Give every hole a good fallback.** The skeleton is what the user sees during the instant-shell phase, so make it match the final layout to avoid layout shift.

Get this right and your dynamic surface is a few small holes in a fast static page. Get it wrong and you've reinvented full SSR with extra steps.

## Where it fits, and the current status

PPR shines for pages that are mostly static with pockets of dynamism: product and content pages with live or personalized fragments, dashboards with a static frame and per-user widgets, marketing pages with a personalized nav. For pages that are almost entirely dynamic (a fully personalized feed), there's little static shell to cache and the benefit shrinks — plain dynamic rendering is fine there.

One practical note: PPR has been an experimental/incremental feature in Next.js, enabled per-route and evolving across releases, so pin your version expectations and check the current docs before relying on it in production. It composes well with edge deployment — the static shell served from a nearby edge cache is exactly the kind of near-user win I covered in [running code at the edge](https://blog.michaelsam94.com/edge-computing-functions/).

## The takeaway

Partial Prerendering ends the false choice between fast and fresh. Structure your page so the unchanging majority prerenders into a static shell that serves instantly from cache, and let the genuinely dynamic minority stream in through Suspense boundaries. The engineering work is deciding what's static versus dynamic and keeping the dynamic surface small — do that, and you get static-page first paint with server-page freshness on the same route. That combination used to require awkward workarounds; PPR makes it the default shape of a well-built Next.js page.

## CDN cache keys and personalization

PPR shells cache at edge; dynamic holes must not poison cache keys. Ensure `Vary` headers and Next.js `cache` directives exclude cookies from static shell keys unless hole components explicitly opt into personalized caching.

```tsx
export const dynamic = 'force-static'; // shell
// Inside LiveInventory:
export const dynamic = 'force-dynamic';
```

Misconfigured `cookies()` in layout components forces entire page dynamic — the anti-pattern PPR is meant to fix.

## Fallback UI and CLS

Skeleton components for Suspense fallbacks must match final layout dimensions — inventory widget jumping from 40px to 200px tanks CLS. Reserve min-height in shell CSS.

## Measuring PPR success

Compare **TTFB** (shell) vs **LCP element** (often dynamic hole). Success: TTFB drops toward static baseline while LCP element still fresh. RUM split by `x-nextjs-ppr` debug header in staging before enabling in production.

## `experimental_ppr` rollout

Enable per layout segment — root marketing layout PPR-on, `/admin` dynamic-off. Misconfigured segment boundaries propagate PPR unexpectedly; integration test asserts `x-nextjs-cache` headers per route class.

## Streaming errors inside Suspense holes

Dynamic hole throws — error boundary inside Suspense shows fallback, not whole page 500. User still sees static product shell with "inventory unavailable" chip — better than blank document.

## Edge vs Node hole rendering

Holes hitting regional DB should run Node runtime if edge lacks DB driver — mixing runtime in same route tree needs explicit `export const runtime = 'nodejs'` on dynamic child components.

## Resources

- [Next.js: Partial Prerendering](https://nextjs.org/docs/app/getting-started/partial-prerendering)
- [React: Suspense](https://react.dev/reference/react/Suspense)
- [Next.js rendering fundamentals](https://nextjs.org/docs/app/building-your-application/rendering)
- [web.dev: Core Web Vitals](https://web.dev/articles/vitals)
- [web.dev: Rendering on the web](https://web.dev/articles/rendering-on-the-web)
- [MDN: Streams API](https://developer.mozilla.org/en-US/docs/Web/API/Streams_API)