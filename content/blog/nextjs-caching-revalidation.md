---
title: "Caching and Revalidation in Next.js"
slug: "nextjs-caching-revalidation"
description: "Master Next.js App Router caching: fetch cache, full route cache, router cache, revalidation strategies, and debugging stale data."
datePublished: "2025-08-25"
dateModified: "2025-08-25"
tags: ["Web", "Next.js", "Performance", "Architecture"]
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

## Common production mistakes

Teams get caching revalidation wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of caching revalidation fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [Next.js caching overview](https://nextjs.org/docs/app/building-your-application/caching) — official four-layer explanation
- [fetch API cache options](https://nextjs.org/docs/app/api-reference/functions/fetch) — `next.revalidate` and tags
- [revalidatePath reference](https://nextjs.org/docs/app/api-reference/functions/revalidatePath) — path-based invalidation
- [revalidateTag reference](https://nextjs.org/docs/app/api-reference/functions/revalidateTag) — tag-based invalidation
- [Route segment config](https://nextjs.org/docs/app/api-reference/file-conventions/route-segment-config) — `dynamic`, `revalidate` exports
