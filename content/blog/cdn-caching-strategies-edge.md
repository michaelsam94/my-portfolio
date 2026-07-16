---
title: "CDN Caching Strategies"
slug: "cdn-caching-strategies-edge"
description: "CDN edge caching reduces latency and origin load. Configure Cache-Control headers, cache keys, stale-while-revalidate, and cache invalidation for static assets and API responses."
datePublished: "2025-01-23"
dateModified: "2025-01-23"
tags: ["DevOps", "Infrastructure", "CDN", "Performance"]
keywords: "CDN caching strategy, Cache-Control headers, edge caching, cache invalidation CDN, stale-while-revalidate, CloudFront caching"
faq:
  - q: "What should I cache at the CDN edge?"
    a: "Cache static assets (JS, CSS, images, fonts) aggressively with long TTLs and content hashes in filenames. Cache public API responses that change infrequently (product catalogs, blog posts). Never cache personalized responses (user dashboards, auth tokens) or mutations (POST/PUT/DELETE) unless explicitly designed with surrogate keys."
  - q: "How do cache invalidation and purging work?"
    a: "Invalidation tells the CDN to fetch fresh content on next request — by URL path or cache tag. Purge is immediate removal. Prefer cache-busting via filename hashes (app.a1b2c3.js) over purging — purges propagate in seconds to minutes and can spike origin load. Use purges for HTML entry points and emergency fixes only."
  - q: "What is stale-while-revalidate?"
    a: "stale-while-revalidate tells the CDN to serve stale cached content immediately while fetching a fresh copy in the background. Users get fast responses; the next request gets updated content. Ideal for semi-static API responses like product listings that can tolerate brief staleness."
---

Every request that hits your origin is latency your users feel and money you spend. A CDN caches responses at edge locations worldwide — a user in Tokyo gets your JavaScript from a Tokyo PoP, not your Virginia origin. But caching wrong sends stale data, breaks auth, or caches nothing because your headers say `Cache-Control: private, no-store` on everything. CDN strategy is header design, cache key configuration, and knowing what not to cache.

## Cache-Control fundamentals

```http
# Static assets (hashed filenames) — cache forever
Cache-Control: public, max-age=31536000, immutable

# HTML entry point — short TTL, revalidate
Cache-Control: public, max-age=60, stale-while-revalidate=300

# API public catalog — moderate TTL with SWR
Cache-Control: public, max-age=300, stale-while-revalidate=600

# User-specific data — never cache at CDN
Cache-Control: private, no-store

# Authenticated API — browser only, not CDN
Cache-Control: private, max-age=0
```

| Directive | Meaning |
|-----------|---------|
| public | CDN and browser can cache |
| private | Browser only, not CDN |
| max-age=N | Fresh for N seconds |
| s-maxage=N | CDN-specific max-age (overrides max-age for shared caches) |
| immutable | Don't revalidate during max-age (for hashed assets) |
| stale-while-revalidate=N | Serve stale for N seconds while refreshing |
| no-store | Don't cache at all |

## Filename hashing for static assets

```html
<script src="/assets/app.a1b2c3d4.js"></script>
<link rel="stylesheet" href="/assets/styles.e5f6g7h8.css">
```

Content hash in filename = infinite cache TTL. New deploy = new filename = no invalidation needed. Only `index.html` needs short TTL.

Vite, Webpack, and Next.js do this automatically in production builds.

## Cache key design

Default cache key: URL path + query string. Customize for API responses:

```
# CloudFront cache policy
Cache key: /api/v1/products/*
Include headers: Accept-Encoding
Exclude cookies: all
Exclude query strings: utm_*, fbclid
```

Including cookies in cache key creates one cache entry per user — effectively no caching. Strip cookies for public endpoints at the CDN.

## Surrogate keys for granular invalidation

Tag responses for bulk purge:

```http
# Origin response
Cache-Control: public, s-maxage=3600
Surrogate-Key: products product-123 category-electronics
```

```bash
# Purge all product pages when catalog updates
curl -X POST "https://api.cloudflare.com/client/v4/zones/{zone}/purge_cache" \
  -d '{"tags": ["products"]}'
```

Fastly and Cloudflare support surrogate key / cache tag purging. CloudFront uses path-based invalidation (more limited).

## Tiered caching strategy

```
Browser cache (max-age)
    ↓ miss
CDN edge (s-maxage)
    ↓ miss
CDN shield / regional tier
    ↓ miss
Origin
```

| Content type | Browser | CDN edge | Strategy |
|-------------|---------|----------|----------|
| Hashed JS/CSS | 1 year | 1 year | immutable |
| HTML | 0–60s | 60s | SWR |
| Public API | 0 | 5 min | SWR + surrogate keys |
| Images | 1 day | 1 week | URL versioning |
| User API | no-store | bypass | origin only |

## Origin shield

Enable origin shield (CloudFront Origin Shield, Fastly Shield) — one CDN PoP fetches from origin, other PoPs fetch from shield. Reduces origin requests 80%+ for popular content.

## Common mistakes

**Caching authenticated responses:** If `Authorization` header is in cache key, every user misses. If it's excluded, users see each other's data. Default: don't CDN-cache authenticated endpoints.

**Varying on too many headers:** `Vary: Accept-Language, Accept-Encoding, Cookie` multiplies cache entries. Minimize Vary headers.

**Forgetting HTTPS redirect caching:** Cache 301 redirects carefully — a bad redirect cached for hours is painful.

**No cache monitoring:** Track CDN hit ratio (target > 90% for static assets), origin request rate, and `Age` header in responses.

## CloudFront example

```yaml
# Terraform — cache behavior for static assets
ordered_cache_behavior {
  path_pattern     = "/assets/*"
  allowed_methods  = ["GET", "HEAD"]
  cached_methods   = ["GET", "HEAD"]
  target_origin_id = "s3-origin"

  forwarded_values {
    query_string = false
    cookies { forward = "none" }
  }

  min_ttl     = 86400
  default_ttl = 31536000
  max_ttl     = 31536000
  compress    = true
}
```

Modern CloudFront uses cache policies and origin request policies instead of forwarded_values — migrate if on legacy config.

## Cache invalidation at scale

Purging by URL doesn't scale for CMS with 100K pages. Use surrogate keys (Fastly) or cache tags (Cloudflare, CloudFront via custom headers):

```
# Origin response
Cache-Control: public, max-age=3600, s-maxage=86400
Surrogate-Key: product-123 category-shoes
```

Purge `product-123` when inventory changes — one API call, all related URLs invalidated. Without tags, you're guessing URL patterns or purging `/*` (origin meltdown).

## Stale-while-revalidate in production

`stale-while-revalidate=86400` serves stale content while fetching fresh in background — users never wait on origin latency spikes:

```
Cache-Control: public, max-age=60, stale-while-revalidate=3600, stale-if-error=86400
```

| Directive | Purpose |
|-----------|---------|
| max-age=60 | Fresh for 1 minute |
| stale-while-revalidate | Serve stale up to 1 hour while revalidating |
| stale-if-error | Serve stale up to 24 hours if origin 5xx |

Tune `max-age` to content change frequency. Product pages: 60–300s. Static assets with hashed filenames: immutable, 1 year.

## Debugging cache misses

Check response headers in browser DevTools:

- `X-Cache: Hit from cloudfront` vs `Miss`
- `Age: 847` — seconds since cached
- `CF-Cache-Status: HIT` on Cloudflare

Common miss causes: `Set-Cookie` on response, `Cache-Control: private`, query strings not in cache key when content varies by query, `Authorization` header forwarded incorrectly.

Log origin request rate separately from CDN request rate — a spike in origin traffic with flat CDN traffic means hit ratio collapsed.

Pair with [edge computing on Cloudflare Workers](https://blog.michaelsam94.com/edge-computing-cloudflare-workers/) for dynamic cache key normalization.

## Production checklist

- [ ] Surrogate keys/tags for cache invalidation by entity
- [ ] `stale-while-revalidate` tuned per content type
- [ ] Authenticated responses never CDN-cached by default
- [ ] Hit ratio monitored (target > 90% static assets)
- [ ] Origin shield enabled for popular content

## Common production mistakes

Teams get caching strategies edge wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of caching strategies edge fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [MDN Cache-Control reference](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control)
- [CloudFront caching best practices](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/ConfiguringCaching.html)
- [Fastly surrogate keys guide](https://www.fastly.com/documentation/guides/concepts/edge-state/cache/surrogate-keys/)
- [web.dev — HTTP caching](https://web.dev/articles/http-cache)
- [Cloudflare cache rules documentation](https://developers.cloudflare.com/cache/)
