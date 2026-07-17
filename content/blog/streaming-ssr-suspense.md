---
title: "Streaming SSR and Suspense Boundaries"
slug: "streaming-ssr-suspense"
description: "Streaming SSR and Suspense boundaries explained: how progressive rendering cuts TTFB, streams a shell first, and hydrates selectively without blocking on slow data."
datePublished: "2026-04-05"
dateModified: "2026-07-17"
tags: ["Web", "Frontend", "Performance"]
keywords: "streaming SSR, Suspense, server rendering, progressive rendering, TTFB, selective hydration, shell streaming"
faq:
  - q: "What is streaming SSR?"
    a: "Streaming SSR is server-side rendering that sends HTML to the browser in chunks as it's produced, instead of waiting for the entire page to render before responding. The server flushes an initial shell immediately, then streams in the remaining sections as their data resolves. This lowers Time to First Byte and lets the browser start painting and loading assets far earlier than with all-or-nothing SSR."
  - q: "How do Suspense boundaries relate to streaming?"
    a: "A Suspense boundary marks a region of the UI that can render a fallback (like a skeleton) while its data or code loads. During streaming SSR, each boundary becomes a unit of streaming: the server sends the fallback immediately as part of the shell, then streams the resolved content for that boundary when it's ready. Boundaries are how you tell the framework which parts of the page may arrive later."
  - q: "What is selective hydration?"
    a: "Selective hydration lets the browser hydrate parts of the page independently as their code and streamed HTML arrive, rather than waiting to hydrate the whole tree at once. It also prioritizes hydrating components the user interacts with first. Combined with streaming, it means a page can become interactive in pieces, and a slow section never blocks interactivity elsewhere."
faqAnswers:
  - question: "When is streaming ssr suspense the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for streaming ssr suspense?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back streaming ssr suspense safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
Classic server-side rendering has a cruel property: the user sees nothing until the server has rendered *everything*. One slow database query for the recommendations widget holds the entire HTML response hostage, and the browser sits on a blank screen. Streaming SSR breaks that coupling. The server sends an initial HTML shell the instant it's ready, then streams the rest of the page in chunks as each region's data resolves. Suspense boundaries are how you declare which regions are allowed to arrive late. Together they turn "wait for the slowest thing, then show everything" into "show the fast things now, fill in the slow things as they come."

I've spent a lot of time chasing Time to First Byte and Largest Contentful Paint on content-heavy React apps, and streaming SSR is the technique that moved those numbers the most without gutting features. Here's how it actually works and where the sharp edges are.

## The problem with all-or-nothing SSR

Traditional `renderToString` is synchronous and total. The server fetches all data, renders the complete tree, and only then sends a byte to the browser. Your TTFB is therefore bounded by your slowest data dependency. If your header, nav, and article render in 40ms but a personalized sidebar takes 800ms on a cold cache, the user waits 800ms+ for a blank page before anything paints.

Worse, this compounds: the browser can't discover and preload CSS, fonts, or scripts referenced later in the document until it receives the HTML, so a slow render delays the entire asset pipeline. All-or-nothing SSR makes your fastest content pay for your slowest.

## Streaming: send the shell first

Streaming flips the order of operations. The server renders and flushes what's ready immediately — typically the layout, header, navigation, and any statically-known content — as the initial "shell." The browser receives that, starts parsing, discovers and preloads assets, and paints. Meanwhile the server keeps working on the slower regions and streams their HTML down the same response as it resolves.

In React, the server API is `renderToPipeableStream` (Node) or `renderToReadableStream` (edge/web streams):

```javascript
import { renderToPipeableStream } from "react-dom/server";

app.get("/product/:id", (req, res) => {
  const { pipe } = renderToPipeableStream(<App id={req.params.id} />, {
    bootstrapScripts: ["/client.js"],
    onShellReady() {
      // Shell is ready — flush it now, don't wait for suspended data.
      res.setHeader("Content-Type", "text/html");
      pipe(res);
    },
    onError(err) {
      console.error(err);
    },
  });
});
```

`onShellReady` fires as soon as everything *outside* Suspense boundaries has rendered. That's your fast TTFB. The suspended regions stream afterward.

## Suspense boundaries are the unit of streaming

A `<Suspense>` boundary wraps a region that might not be ready yet and provides a fallback to show in the meantime:

```jsx
function ProductPage({ id }) {
  return (
    <Layout>
      <ProductHeader id={id} />        {/* fast, in the shell */}
      <Suspense fallback={<ReviewsSkeleton />}>
        <Reviews id={id} />            {/* slow — streams in later */}
      </Suspense>
      <Suspense fallback={<RecsSkeleton />}>
        <Recommendations id={id} />    {/* slow — independent boundary */}
      </Suspense>
    </Layout>
  );
}
```

Here's the sequence the browser actually receives:

1. The shell arrives with `ProductHeader` fully rendered and *both* skeletons in place. The page paints immediately.
2. `Reviews` resolves on the server; React streams a chunk containing the real reviews HTML plus a tiny inline script that swaps it in where the skeleton was.
3. `Recommendations` resolves independently and streams the same way.

Each boundary is autonomous. A slow `Recommendations` never delays `Reviews`. Placing boundaries well is the actual skill: too coarse and you're back to waiting for the slowest thing in a big region; too fine and you get a distracting popcorn of skeletons. I place them around genuinely independent, data-bound sections and keep the shell truly fast.

## Selective hydration ties it together

Streaming HTML would be half a solution if the page still had to hydrate as one monolithic block. Selective hydration is the client-side counterpart: React hydrates each boundary's content as its HTML and code arrive, independently, and prioritizes whatever the user interacts with. If someone clicks a not-yet-hydrated section, React hydrates *that* first, out of order.

The practical effect: interactivity arrives in pieces and tracks user attention, instead of the whole page being dead until one big hydration pass finishes. A slow-loading widget at the bottom can't freeze the button at the top.

## How it relates to the broader rendering shift

Streaming SSR is one thread in a larger move toward server-owned rendering with less client work. [React Server Components in production](https://blog.michaelsam94.com/react-server-components-production/) build directly on streaming — Server Components render on the server and stream their output, with client components hydrating selectively inside Suspense boundaries. And [partial prerendering in Next.js](https://blog.michaelsam94.com/partial-prerendering-nextjs/) combines a *statically prerendered* shell served instantly from the edge with dynamic holes streamed in at request time, which is essentially streaming SSR with the shell pre-baked. If you understand Suspense boundaries as the streaming unit, all three of these click into place as variations on the same idea.

## The tradeoffs I've actually hit

Streaming is not free lunch, and pretending otherwise leads to pain:

- **HTTP status and headers commit early.** Once you flush the shell, you've sent a 200 and your headers. You can't later decide to redirect or return a 500 for the whole page. Errors inside a boundary become boundary-level error UI, not a page-level status — plan your error handling around that.
- **Layout shift from fallbacks.** If a skeleton's dimensions don't match the resolved content, you get CLS when the real content streams in. Size your fallbacks to match, or you trade one metric for another.
- **Streaming and some caching/CDN layers interact awkwardly.** Not every proxy handles chunked, long-lived responses gracefully; verify your edge actually streams rather than buffering the whole response (which silently defeats the point).
- **Debugging is harder.** A response that arrives in pieces over time is trickier to inspect than a single document. Good observability on server render timings per boundary pays off.

## Where I'd start

If you have an all-or-nothing SSR app with a slow section dragging down TTFB, streaming is one of the highest-leverage changes available. Identify the fast, always-available content and make it the shell. Wrap each slow, independently-fetched region in a Suspense boundary with a correctly-sized skeleton. Switch the server to a streaming render API. Then measure: TTFB should drop toward the shell's render time, and LCP should improve because assets get discovered earlier.

One caution from experience: measure on real devices and throttled networks, not just a fast laptop on office wifi. Streaming's benefit is largest exactly where all-or-nothing SSR hurts most — mid-range phones on slow mobile links, where each hundred milliseconds of blank screen is time a user might spend leaving. On a fast connection the difference between streamed and buffered can be nearly invisible, which is how a buffering proxy quietly erases the win without anyone catching it in a demo.

The mindset shift is the real deliverable. Stop thinking of a page as one render that either succeeds or fails, and start thinking of it as a fast shell plus a set of independently-arriving regions. Once that clicks, you stop letting your slowest query dictate your users' first impression — and that's the whole point.

## Resources

- [React — renderToPipeableStream](https://react.dev/reference/react-dom/server/renderToPipeableStream)
- [React — Suspense reference](https://react.dev/reference/react/Suspense)
- [React 18 — New Suspense SSR Architecture (discussion)](https://github.com/reactwg/react-18/discussions/37)
- [web.dev — Optimize Time to First Byte](https://web.dev/articles/ttfb)
- [MDN — Streams API](https://developer.mozilla.org/en-US/docs/Web/API/Streams_API)
- [Next.js — Streaming and Suspense](https://nextjs.org/docs/app/building-your-application/routing/loading-ui-and-streaming)