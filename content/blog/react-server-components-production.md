---
title: "React Server Components in Production"
slug: "react-server-components-production"
description: "What React Server Components change in production: zero-bundle data fetching, the server/client boundary, streaming SSR, and mistakes teams make adopting RSC."
datePublished: "2026-06-16"
dateModified: "2026-06-16"
tags: ["React", "Next.js", "Frontend", "Performance"]
keywords: "React Server Components, RSC, Next.js, server components, zero bundle, streaming SSR, client components"
faq:
  - q: "What are React Server Components?"
    a: "React Server Components (RSC) are components that render only on the server and never ship their code to the browser. They can fetch data directly, access server-only resources, and send a serialized UI tree to the client, which reduces JavaScript bundle size and moves data fetching off the client."
  - q: "What is the difference between Server Components and SSR?"
    a: "Traditional SSR renders your components to HTML on the server but still ships the same component JavaScript to the client to hydrate. Server Components never ship their code at all — only Client Components hydrate — so RSC reduces bundle size in a way plain SSR does not."
  - q: "When should a component be a Client Component?"
    a: "Use a Client Component whenever you need interactivity or browser APIs: state, effects, event handlers, refs, or things like localStorage. Everything else — data fetching, layout, static content — can stay a Server Component and stay out of the bundle."
---

The mental model that trips up most teams adopting React Server Components is thinking of them as "SSR, but more." They aren't. Server-side rendering runs your components on the server to produce HTML and then ships the same component code to the browser to hydrate it. React Server Components run on the server and *never ship their code to the browser at all*. That one difference — code that stays on the server — is the whole point, and it changes how you structure a React app in production.

I'll walk through what actually changes, where the boundary lives, how streaming fits, and the mistakes I've watched teams make in real Next.js App Router codebases.

## Zero-bundle data fetching is the real win

In a classic React app, fetching data means shipping the fetching logic, the client-side data library, and often the entire schema of transformation code to the browser, then making a round trip after hydration. With Server Components you fetch on the server, inside the component, before anything reaches the client:

```tsx
// app/dashboard/page.tsx — a Server Component (no "use client")
import { db } from "@/lib/db";

export default async function Dashboard() {
  const projects = await db.project.findMany({ orderBy: { updatedAt: "desc" } });
  return (
    <ul>
      {projects.map((p) => (
        <li key={p.id}>{p.name}</li>
      ))}
    </ul>
  );
}
```

None of that — not `db`, not the query, not the ORM — ends up in the browser bundle. The client receives a serialized description of the rendered UI. For a data-heavy dashboard, this can cut client JavaScript dramatically, and it removes the fetch-on-mount waterfall entirely because the data is already there when the HTML arrives. That combination — less JS to parse and no client round trip — is what moves the metrics that matter, especially on mobile CPUs.

## The server/client boundary is the design

The core skill with RSC is deciding what runs where. By default in the App Router, everything is a Server Component. You opt a subtree into the client with the `"use client"` directive, and that's a one-way door: once a module is a Client Component, everything it imports is bundled for the browser too.

The pattern that works is pushing the `"use client"` boundary as far down the tree as possible. Keep pages, layouts, and data-fetching wrappers on the server; make only the interactive leaves — a search box, a like button, a modal — client components:

```tsx
// A Server Component composing a small Client Component leaf
import { LikeButton } from "./like-button"; // "use client" lives inside this file

export default async function Post({ id }: { id: string }) {
  const post = await getPost(id);          // server-side, zero bundle
  return (
    <article>
      <h2>{post.title}</h2>
      <p>{post.body}</p>
      <LikeButton postId={post.id} initial={post.likes} /> {/* interactive island */}
    </article>
  );
}
```

The mistake I see constantly is slapping `"use client"` at the top of a page "to make it work," which drags the entire subtree into the bundle and throws away the benefit. When something breaks with a server/client error, resist the urge to escalate the whole page to the client — find the specific interactive piece and isolate it.

## What you cannot do in a Server Component

Server Components can't use state, effects, event handlers, refs, or browser APIs, because there's no client runtime for them. No `useState`, no `useEffect`, no `onClick`. If you need any of that, you need a Client Component. Conversely, Client Components can't be `async` and can't directly access server resources like your database or secrets. Props passed from a Server Component to a Client Component must be serializable — you can't pass a function or a class instance across the boundary.

Internalizing these two lists early saves a lot of confusion. Most "why doesn't this work" moments in RSC are a component on the wrong side of the boundary.

## Streaming and Suspense

Server Components pair with streaming SSR through Suspense. Instead of waiting for every data dependency before sending anything, you send the shell immediately and stream in slower parts as they resolve:

```tsx
import { Suspense } from "react";

export default function Page() {
  return (
    <>
      <Header />                              {/* instant */}
      <Suspense fallback={<Skeleton />}>
        <SlowRevenueChart />                  {/* streams in when ready */}
      </Suspense>
    </>
  );
}
```

The user sees the header and layout right away, and the slow chart fills in without blocking the rest of the page. This is a genuine UX improvement over the all-or-nothing SSR wait, and it composes naturally with [partial prerendering in Next.js](https://blog.michaelsam94.com/partial-prerendering-nextjs/), which takes the same idea further by serving a static shell instantly and streaming the dynamic holes.

## Production gotchas I've hit

A few things that don't show up in the tutorials:

- **Serialization cost.** Large data passed from server to client crosses the boundary as serialized payload. Fetching a 2 MB list on the server and handing all of it to a Client Component means you shipped 2 MB of RSC payload. Filter and shape data on the server; send only what the client needs.
- **Caching is confusing on purpose.** The App Router caches aggressively across several layers (request memoization, data cache, full-route cache). "Why is my data stale" is almost always a caching config, not a bug. Learn `revalidate`, `cache`, and `dynamic` before you go live, or you'll ship stale pages.
- **Third-party libraries.** Many popular libraries assume a client environment and need wrapping in a `"use client"` boundary. Context providers in particular must be Client Components; a common pattern is a thin `providers.tsx` client wrapper mounted high in the tree.
- **Environment leakage.** Because server code and client code live in the same files-adjacent tree, it's easy to import a server-only module into a client path and leak a secret into the bundle. Use the `server-only` package to make that a build error rather than a security incident.

## Is it worth adopting?

For content-heavy and data-heavy apps — dashboards, e-commerce, marketing sites with dynamic bits — RSC in production genuinely reduces client JavaScript and simplifies data fetching, and the streaming story is a real win on slow devices. For a small, highly-interactive SPA where almost everything is stateful, the benefit is thinner and the boundary discipline is overhead.

My advice: adopt it deliberately, keep the client boundary small and pushed to the leaves, respect the serialization cost, and spend an afternoon actually understanding the caching layers before launch. Done that way, React Server Components are one of the better things to happen to production React. Done carelessly, you get a "server" app that somehow still ships a giant bundle. If you're pairing RSC with edge deployment, it's worth reading about [running code at the edge](https://blog.michaelsam94.com/edge-computing-functions/) too, since where these components render affects latency.

## Resources

- [React docs: Server Components](https://react.dev/reference/rsc/server-components)
- [Next.js: Server and Client Components](https://nextjs.org/docs/app/building-your-application/rendering/composition-patterns)
- [React: Suspense](https://react.dev/reference/react/Suspense)
- [Next.js caching documentation](https://nextjs.org/docs/app/building-your-application/caching)
- [The `server-only` package](https://www.npmjs.com/package/server-only)
- [web.dev: Rendering on the web](https://web.dev/articles/rendering-on-the-web)
