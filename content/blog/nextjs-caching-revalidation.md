---
title: "Caching and Revalidation in Next.js"
slug: "nextjs-caching-revalidation"
description: "Master Next.js App Router caching: fetch cache, full route cache, router cache, revalidation strategies, and debugging stale data."
datePublished: "2025-08-25"
dateModified: "2026-07-17"
tags:
keywords: "Next.js caching, App Router cache, revalidateTag, revalidatePath, ISR Next.js, fetch cache options, stale data Next.js"
faq:
  - q: "Why does my Next.js page show stale data after a database update?"
    a: "The App Router caches at multiple layers: fetch responses, full route HTML, and client router cache. A database update alone does not invalidate any of them. Call revalidatePath or revalidateTag after mutations, or set cache: 'no-store' on fetches that must always be fresh."
  - q: "What is the difference between revalidatePath and revalidateTag?"
    a: "revalidatePath invalidates cached pages tied to a URL path. revalidateTag invalidates fetch requests tagged with next: { tags: ['posts'] }. Use tags when one data source feeds multiple pages."
  - q: "How do I disable caching for a specific page?"
    a: "Export const dynamic = 'force-dynamic' in the page or layout, or use cache: 'no-store' on all fetch calls in that route segment. Use sparingly—disabling cache removes static generation benefits."
---
You deployed a blog post editor, published an article, and refreshed the homepage—the old version still appears. The database has the new content. The App Router cached the page at build time and has no idea you changed anything. Next.js 13+ caching is powerful but layered: fetch cache, full route cache, and client router cache each behave differently. Understanding which layer holds your stale data saves hours of confused `router.refresh()` calls.

## The four cache layers

```
Request → Router Cache (client) → Full Route Cache (server)
                ↓
         Data Cache (fetch) → Origin (DB/API)
```

| Layer | Location | Duration | Invalidation |
|-------|----------|----------|--------------|
| Request memoization | Server (per request) | Single render | Automatic |
| Data Cache | Server (persistent) | Until revalidation | `revalidateTag`, `revalidatePath`, TTL |
| Full Route Cache | Server (persistent) | Until revalidation | `revalidatePath`, rebuild |
| Router Cache | Client (memory) | Session / 30s static | `router.refresh()`, navigation |

## Fetch cache options

```typescript
// Cached indefinitely (default for static pages)
const posts = await fetch("https://api.example.com/posts");

// Revalidate every 60 seconds (ISR)
const posts = await fetch("https://api.example.com/posts", {
  next: { revalidate: 60 },
});

// Never cache
const user = await fetch("https://api.example.com/me", {
  cache: "no-store",
});

// Tag for on-demand revalidation
const post = await fetch(`https://api.example.com/posts/${slug}`, {
  next: { tags: [`post-${slug}`] },
});
```

In Server Components, identical fetch calls in one render are deduplicated automatically.

## On-demand revalidation

**After a Server Action or webhook:**

```typescript
import { revalidatePath, revalidateTag } from "next/cache";

export async function publishPost(slug: string) {
  await db.post.update({ where: { slug }, data: { published: true } });
  revalidateTag(`post-${slug}`);
  revalidatePath("/blog");
  revalidatePath(`/blog/${slug}`);
}
```

**From an external webhook (Route Handler):**

```typescript
// app/api/revalidate/route.ts
import { revalidateTag } from "next/cache";
import { NextRequest } from "next/server";

export async function POST(request: NextRequest) {
  const secret = request.nextUrl.searchParams.get("secret");
  if (secret !== process.env.REVALIDATE_SECRET) {
    return Response.json({ error: "Invalid" }, { status: 401 });
  }
  const tag = request.nextUrl.searchParams.get("tag");
  if (tag) revalidateTag(tag);
  return Response.json({ revalidated: true });
}
```

## Route segment config

```typescript
// app/dashboard/page.tsx
export const dynamic = "force-dynamic";     // never cache this page
export const revalidate = 0;                // same effect
export const fetchCache = "force-no-store"; // all fetches uncached
```

```typescript
// app/blog/page.tsx
export const revalidate = 3600; // ISR: rebuild at most once per hour
```

`dynamic = 'force-static'` pins the page at build time regardless of fetch options.

## Debugging stale data

Add logging to identify which layer serves stale content:

```typescript
const res = await fetch(url, { next: { revalidate: 60, tags: ["posts"] } });
console.log("cache status:", res.headers.get("x-nextjs-cache")); // HIT, MISS, STALE
```

| Symptom | Likely layer | Fix |
|---------|-------------|-----|
| Stale after client navigation | Router cache | `router.refresh()` |
| Stale after hard refresh | Data or full route cache | `revalidatePath` |
| Stale only in production | Build-time static generation | Check `dynamic` export |
| Fresh in dev, stale in prod | Expected—dev disables most caching | Test with `next build && next start` |

## Cache composition example

A product page fetches product data and reviews:

```typescript
// app/products/[id]/page.tsx
export const revalidate = 300; // 5-minute ISR

async function getProduct(id: string) {
  return fetch(`${API}/products/${id}`, {
    next: { tags: [`product-${id}`] },
  }).then((r) => r.json());
}

async function getReviews(id: string) {
  return fetch(`${API}/products/${id}/reviews`, {
    next: { tags: [`reviews-${id}`], revalidate: 60 },
  }).then((r) => r.json());
}
```

When a new review arrives, `revalidateTag('reviews-${id}')` updates reviews without rebuilding the entire product page cache.

## Opting out strategically

Not everything should be cached:
- User-specific dashboards: `cache: 'no-store'`
- Cart and checkout: `dynamic = 'force-dynamic'`
- Public marketing pages: static or ISR with long TTL
- Blog posts: ISR with on-demand revalidation on publish

Over-caching user data is a security issue—two users seeing the same cached `/account` response is worse than a slow page.

## On-demand revalidation patterns

Webhook-driven invalidation from CMS:

```typescript
// app/api/revalidate/route.ts
import { revalidateTag } from "next/cache";

export async function POST(request: Request) {
  const secret = request.headers.get("x-revalidate-secret");
  if (secret !== process.env.REVALIDATE_SECRET) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }
  const { tag } = await request.json();
  revalidateTag(tag);
  return Response.json({ revalidated: true, tag });
}
```

CMS publish webhook → `POST /api/revalidate` with `{ tag: "blog-post-123" }`. Narrow tags prevent cascade invalidation.

## Debugging cache in production

```typescript
// Temporary — log cache status in fetch
const res = await fetch(url, { next: { tags: ["products"] } });
console.log("cache:", res.headers.get("x-nextjs-cache")); // HIT, MISS, STALE
```

Common fixes:
- **`no-store` inherited** — check layout.tsx parent segment config
- **Dynamic functions** — `cookies()` or `headers()` in layout opts entire subtree out of static cache
- **fetch without cache option** — defaults changed in App Router vs Pages Router

Test production caching with `next build && next start`, never `next dev`.

Pair with [Next.js metadata SEO API](https://blog.michaelsam94.com/nextjs-metadata-seo-api/) when cache invalidation must update OG tags simultaneously.

## Production validation (1)

Ship changes behind feature flags when behavior crosses route or service boundaries. Canary deploy with automatic rollback when error rate or p95 latency regresses beyond SLO budget. Document which metrics prove success—user-visible latency, error ratio, conversion—not only CPU graphs.

When operating **Next.js caching revalidation** (`nextjs-caching-revalidation`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.

## Failure modes (2)

Recurring incidents: missing idempotency on retried paths, connection pool exhaustion masquerading as slow queries, retry storms amplifying partial outages. Design explicit timeouts on every outbound call.

When operating **Next.js caching revalidation** (`nextjs-caching-revalidation`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.

## Observability (3)

Structured logs include trace_id and tenant_id on every error path. Metrics: request rate, error ratio, duration histogram, queue depth or pool wait. Traces: one span per dependency.

When operating **Next.js caching revalidation** (`nextjs-caching-revalidation`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.

## Security review (4)

Least-privilege credentials, no PII in logs, fail-closed auth defaults. Secrets rotate without redeploy where possible. Never log raw tokens or authorization headers.

When operating **Next.js caching revalidation** (`nextjs-caching-revalidation`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.

## Testing strategy (5)

Integration tests against real Postgres/Redis in CI with Testcontainers. Load test at 2× peak with production-like payloads. Chaos: inject dependency latency and verify degradation matches runbooks.

When operating **Next.js caching revalidation** (`nextjs-caching-revalidation`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.

## Rollout checklist (6)

Staging mirrors production topology for cache, pools, and timeouts. Rollback path tested quarterly. On-call runbook fits one page: symptom, dashboard, mitigation, rollback.

When operating **Next.js caching revalidation** (`nextjs-caching-revalidation`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.

## Performance tuning (7)

Measure p50/p95 before optimizing. Change one variable at a time—pool size, batch size, TTL, timeout. Profile CPU for JSON serialization and regex; profile IO for N+1 and pool wait.

When operating **Next.js caching revalidation** (`nextjs-caching-revalidation`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.

## On-call triage (8)

Confirm scope: one tenant, region, or deploy stage? Check deploys and migrations in last 24h. Compare golden signals to baseline. Rollback first during incident if faster than root cause.

When operating **Next.js caching revalidation** (`nextjs-caching-revalidation`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.
