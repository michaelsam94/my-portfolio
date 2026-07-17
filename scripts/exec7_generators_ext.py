"""Extended generators for exec7 batch."""
from __future__ import annotations

def register_all(register):
    @register("nextjs-edge-runtime-limitations")
    def _nextjs_edge_runtime_limitations():
        return ({"title": "Edge Runtime Limitations in Next.js", "slug": "nextjs-edge-runtime-limitations",
                 "description": "What works and breaks on Edge: Node APIs, bundle size, cold starts, and when to stay on Node.js runtime.",
                 "tags": ['Next.js', 'Edge', 'Runtime'], "keywords": "Next.js edge runtime limitations, Edge vs Node runtime Next.js",
                 "published": "2026-07-18"},
                [
                 ("What APIs are unavailable on Edge Runtime?", "Node.js core modules like fs, crypto.createHash (limited), child_process, and native addons. Use Web APIs: fetch, Web Crypto, TextEncoder. Database drivers needing TCP often fail."),
                 ("Should Route Handlers use Edge by default?", "Only for lightweight auth checks, geo routing, A/B assignment, and proxying. Data mutations and ORM access belong on Node.js runtime."),
                 ("How do I debug Edge bundle size errors?", "Run next build and inspect .next/server/edge chunks. Use @vercel/nft or bundle analyzer. Split heavy logic to Node Route Handlers called from Edge."),
                ],
                """Your middleware worked perfectly in development. In production on Edge, `fs.readFile` throws, Prisma fails to connect, and a 2MB dependency blows past the bundle limit. Edge Runtime trades Node.js compatibility for global low-latency deployment—but only some workloads fit.

## ('Choosing Edge vs Node runtime', \"Export `runtime = 'edge'` only when you have measured latency win and confirmed dependency compatibility.\\n\\n```typescript\\nexport const runtime = 'edge';\\n\\nexport async function GET() {\\n  const country = request.headers.get('x-vercel-ip-country') ?? 'US';\\n  return Response.json({ country });\\n}\\n```\\n\\nDefault to Node.js runtime until profiling proves Edge benefit.\")

## ('Bundle size constraints', 'Edge functions ship as bundled JavaScript with strict size limits (typically 1–4MB depending on platform). ORMs, PDF libraries, and image processing libraries exceed limits quickly.\\n\\nPattern: Edge validates JWT and routes; Node handler processes business logic via internal fetch.')

## ('Database and ORM pitfalls', 'Prisma, pg, mysql2 use Node TCP sockets unavailable on Edge. Use HTTP-based data APIs: Prisma Accelerate, PlanetScale serverless driver, Supabase REST, or your own Node API.\\n\\nNever import PrismaClient in edge middleware—it fails at build or runtime.')

## ('Cold starts and latency', 'Edge cold starts are faster than Node serverless but still exist. Keep handler logic minimal. Avoid top-level await of heavy initialization.\\n\\nWarm critical paths with scheduled pings only if your platform charges for invocations—often unnecessary on Vercel Edge.')

## ('Web Crypto vs Node crypto', \"Use Web Crypto API for JWT verification on Edge:\\n\\n```typescript\\nimport { jwtVerify } from 'jose';\\n\\nconst { payload } = await jwtVerify(token, secret);\\n```\\n\\n`jsonwebtoken` depends on Node crypto—replace with `jose` for Edge compatibility.\")

## ('Production decision matrix', '| Use case | Runtime |\\n|----------|--------|\\n| Geo redirect | Edge |\\n| JWT gate | Edge |\\n| Stripe webhook | Node |\\n| PDF generation | Node |\\n| RSC data fetch with ORM | Node |')

""")

    @register("nextjs-fetch-cache-next-revalidate")
    def _nextjs_fetch_cache_next_revalidate():
        return ({"title": "Fetch Cache and next.revalidate in Next.js", "slug": "nextjs-fetch-cache-next-revalidate",
                 "description": "Time-based ISR with fetch next.revalidate, stale-while-revalidate semantics, and per-fetch TTL tuning.",
                 "tags": ['Next.js', 'Caching', 'ISR'], "keywords": "Next.js fetch revalidate, next.revalidate ISR, fetch cache TTL",
                 "published": "2026-12-30"},
                [
                 ("What is the difference between export const revalidate and next.revalidate?", "Route segment revalidate sets default for the page. fetch next.revalidate overrides per request. The shortest TTL wins when composing multiple fetches on one page."),
                 ("Does next.revalidate work with POST fetch?", "No. Only GET and HEAD responses cache. Mutations must use cache: 'no-store'."),
                 ("What happens during revalidation window?", "Users may see stale content until background revalidation completes—stale-while-revalidate. First request after TTL triggers regeneration; concurrent requests still get stale until new cache entry ready."),
                ],
                """Product listings refresh every 60 seconds; legal disclaimers change twice a year. One global `revalidate` export on the page forces both to the same TTL. Per-fetch `next.revalidate` lets each data source declare its own freshness contract.

## ('Per-fetch TTL', '```typescript\\nconst products = await fetch(`${API}/products`, {\\n  next: { revalidate: 60 },\\n});\\n\\nconst legal = await fetch(`${API}/legal`, {\\n  next: { revalidate: 86400 },\\n});\\n```\\n\\nDocument TTL rationale in code comments—future engineers will otherwise unify TTLs incorrectly.')

## ('Combining revalidate with tags', \"```typescript\\nawait fetch(url, {\\n  next: { revalidate: 300, tags: ['products'] },\\n});\\n```\\n\\nTags enable on-demand invalidation before TTL expires. Use both: TTL as safety net, tags for event-driven updates.\")

## ('Stale-while-revalidate behavior', \"After TTL expires, Next.js serves cached response while regenerating in background. Monitor `x-nextjs-cache: STALE` during incidents.\\n\\nFor zero-stale requirements, use cache: 'no-store' or on-demand revalidation only.\")

## ('Self-hosted considerations', 'Multi-instance deployments need shared cache for consistent revalidate behavior. Single-node `next start` uses filesystem cache—scale horizontally requires custom cache handler or platform support.')

## ('Testing TTL', 'Use `next build && next start`, not dev server. Wait TTL duration or mock time in integration tests. Assert content updates after revalidate window plus regeneration time.')

## ('Anti-patterns', 'Setting revalidate: 1 on high-traffic pages—regeneration storm under load. Setting revalidate: false (infinite) without tags—content never updates until redeploy.')

""")

    return None