---
title: "Edge Computing: Running Code at the Edge"
slug: "edge-computing-functions"
description: "What edge computing means for engineers: edge functions, cold starts, runtime limits, and when running code at the edge beats a regional origin server."
datePublished: "2026-06-17"
dateModified: "2026-06-17"
tags: ["Edge Computing", "Serverless", "Performance", "Backend"]
keywords: "edge computing, edge functions, Cloudflare Workers, Vercel Edge, edge runtime, cold start, latency"
faq:
  - q: "What is edge computing in web development?"
    a: "Edge computing runs your code in data centers physically close to users — often 100+ locations worldwide — instead of a single region. For web apps this means edge functions that execute at the CDN layer, cutting round-trip latency for things like auth, redirects, personalization, and API routing."
  - q: "What is the difference between edge functions and serverless functions?"
    a: "Serverless functions (like AWS Lambda) run in one region on a full Node.js runtime with generous memory and time limits. Edge functions run in many locations on a lighter runtime (often V8 isolates) with tighter limits and near-zero cold starts, trading capability for proximity and startup speed."
  - q: "Do edge functions have cold starts?"
    a: "Much smaller ones. Platforms built on V8 isolates (Cloudflare Workers, Vercel Edge) start in around a millisecond because they don't boot a container per request. Traditional container-based serverless can take hundreds of milliseconds to seconds on a cold start."
---

Edge computing gets described in marketing terms so often that engineers reasonably tune it out. Stripped down, it's a simple trade: run your code in one of a hundred-plus locations near the user instead of one region far away, in exchange for a more limited runtime. Whether that trade is worth it depends entirely on what the code does — and getting that judgment right is the actual skill.

I've moved specific workloads to the edge (auth checks, geo-routing, A/B assignment) and deliberately kept others in region (anything touching a single primary database). Here's the framework I use, and the constraints that decide it.

## Why proximity matters: it's the round trips

The speed of light is not negotiable. A user in Cairo hitting a server in Virginia eats roughly 150–200 ms per round trip just in network latency, before your code does anything. If a request needs several sequential round trips — TLS handshake, auth check, redirect, then the real request — that latency stacks. Edge computing collapses the distance for the parts that can run near the user, so the handshake and the quick decisions happen in Marseille or Johannesburg instead of across an ocean.

The catch: this only helps if the edge code doesn't then have to turn around and talk to a database that lives in one region. An edge function that makes a 180 ms call back to your primary Postgres has *added* a hop, not removed one. Proximity helps when the work can complete at the edge, or when it saves round trips (early redirects, cache decisions, rejecting bad requests before they cross the ocean).

## The edge runtime is not Node.js

This is the constraint that surprises people. Most edge platforms — Cloudflare Workers, Vercel Edge Functions, Deno Deploy — run on V8 isolates rather than full Node.js processes. That gives near-instant startup but takes things away:

- No `fs`, no native modules, no arbitrary TCP sockets in most cases.
- Web-standard APIs (`fetch`, `Request`, `Response`, `crypto.subtle`, `Web Streams`) rather than the full Node API surface.
- Tight limits on CPU time per request, memory, and bundle size.

```js
// A Cloudflare Worker: web-standard APIs, no Node built-ins
export default {
  async fetch(request) {
    const country = request.headers.get("cf-ipcountry") ?? "US";
    if (blockedCountries.has(country)) {
      return new Response("Unavailable in your region", { status: 451 });
    }
    return fetch(request); // forward to origin
  },
};
```

So "move it to the edge" often means "rewrite it against web-standard APIs and fit it in a small bundle." Libraries that pull in Node built-ins won't run. Check compatibility before you promise anyone a migration.

## Cold starts: the edge's quiet advantage

The reason edge functions feel different from Lambda is cold start behavior. A container-based serverless function that hasn't run recently has to spin up a container and boot a runtime — hundreds of milliseconds to seconds. V8 isolates don't do that; a new isolate spins up in around a millisecond because it's a lightweight sandbox inside an already-running process, not a fresh container.

For latency-sensitive, spiky, or globally distributed traffic, this near-zero cold start is a genuine differentiator. It's why edge is a natural fit for middleware-style work that runs on *every* request and can't afford a warm-up penalty. If your workload is steady and already keeps containers warm, the cold-start advantage matters less.

## What actually belongs at the edge

The workloads that pay off at the edge share a shape: fast, stateless (or state that's globally replicated), and either terminal at the edge or latency-saving.

| Good fit at the edge | Keep in region |
|---|---|
| Auth/JWT verification, redirects | Long transactions against a primary DB |
| Geo-routing and personalization | Heavy compute (image/video processing) |
| A/B test assignment | Anything needing large libraries / Node APIs |
| Bot filtering, rate limiting | Strongly-consistent multi-step writes |
| Caching and cache-key logic | Workflows longer than the CPU-time budget |

The rate-limiting and bot-filtering cases are especially strong: you reject bad traffic at the edge before it ever reaches your origin, which protects it. That pairs directly with [rate limiting and backpressure](https://blog.michaelsam94.com/rate-limiting-backpressure/) strategies.

## Data at the edge is the hard part

Compute is easy to distribute; data is not. The whole thing falls apart if your globally-distributed function serializes on a single database. The realistic patterns:

- **Edge caching / KV stores** — Cloudflare KV, Workers Cache, or edge-replicated key-value for read-heavy, eventually-consistent data. Great for config, feature flags, sessions.
- **Globally distributed databases** — Turso (libSQL), Cloudflare D1, or globally-replicated Postgres so reads happen near the function.
- **Read at edge, write to region** — serve reads from a nearby replica and route writes to the primary, accepting replication lag.

If your data model needs strong consistency and single-primary writes, be honest that the edge is only helping the read and decision paths, and design accordingly. Some teams pair edge with [local-first architectures](https://blog.michaelsam94.com/local-first-apps-crdts/) so the client holds authoritative state and the edge just syncs — a different but powerful answer to the data-distance problem.

## A pragmatic adoption path

Don't rewrite your app to be "edge-native" on day one. The high-value first move is putting *middleware* at the edge — auth, redirects, geo, A/B, bot filtering — while your main application stays where it is. This captures the latency wins on the every-request path with minimal risk, and it's exactly the shape Next.js middleware and Vercel Edge encourage.

From there, move specific API routes to the edge only when they're stateless or can read from edge-local data, and measure. The metric that matters is real user latency (p75/p95 by geography), not a synthetic benchmark from your own region. WebAssembly is increasingly part of this story too — running [WASI-based Wasm at the edge](https://blog.michaelsam94.com/webassembly-beyond-browser-wasi/) lets you push non-JavaScript workloads into the same near-user runtime.

## The honest summary

Edge computing is a real latency tool, not magic. It shines for fast, stateless, every-request work and for saving round trips near the user, and its near-zero cold starts make it ideal for middleware. It fights you when your data lives in one region and your code has to keep phoning home. Match the workload to the constraint — light, stateless, latency-sensitive at the edge; heavy, stateful, consistency-critical in region — and it earns its place. Force everything to the edge and you'll add hops while congratulating yourself on being modern.

## Resources

- [Cloudflare Workers documentation](https://developers.cloudflare.com/workers/)
- [Vercel Edge Functions](https://vercel.com/docs/functions/edge-functions)
- [Deno Deploy](https://docs.deno.com/deploy/manual/)
- [MDN: Web APIs](https://developer.mozilla.org/en-US/docs/Web/API)
- [Cloudflare KV](https://developers.cloudflare.com/kv/)
- [web.dev: measuring performance](https://web.dev/articles/user-centric-performance-metrics)
