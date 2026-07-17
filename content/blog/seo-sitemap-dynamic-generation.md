---
title: "Dynamic Sitemap Generation for Apps"
slug: "seo-sitemap-dynamic-generation"
description: "Sitemaps for dynamic routes — Next.js sitemap.ts, lastmod accuracy, and pagination for large catalogs."
datePublished: "2026-09-26"
dateModified: "2026-07-17"
tags: ["SEO", "Sitemap", "Next.js"]
keywords: "dynamic sitemap generation, Next.js sitemap, XML sitemap"
faq:
  - q: "Dynamic vs static sitemap?"
    a: "Generate from CMS or database for large or frequently changing sites."
  - q: "Splitting?"
    a: "Use sitemap index when exceeding 50k URLs or 50MB per file."
  - q: "lastmod?"
    a: "Tie to real content updated_at — false lastmod erodes trust."
---

Sitemap listed fifty thousand URLs with `lastmod` always `now()` — crawlers stopped trusting our signals. Dynamic sitemaps keep search engines aligned with publishable URL sets, but dishonest metadata is worse than no sitemap.

## Generate from source of truth

Query CMS or database for canonical published URLs — not client router paths that never 200 from server. Exclude noindex routes, faceted duplicates, and authenticated app shells.

```typescript
// app/sitemap.ts — Next.js App Router
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const rows = await db.queryPublishedUrls({ limit: 50000, offset: 0 });
  return rows.map((r) => ({
    url: `https://example.com${r.path}`,
    lastModified: r.contentUpdatedAt,
    changeFrequency: r.type === "blog" ? "weekly" : "monthly",
    priority: r.type === "product" ? 0.8 : 0.5,
  }));
}
```

## Pagination and sitemap index

Split when exceeding 50,000 URLs or 50 MB uncompressed per file. Sitemap index references chunk files — crawlers fetch in parallel.

## lastmod must reflect real edits

Tie `lastmod` to editorial `contentUpdatedAt`, not deploy timestamp or cache bust. False lastmod erodes trust — Google may ignore future lastmod on your property.

## Include only indexable URLs

Apply same rules as robots meta: if page is noindex, omit from sitemap. Including noindex URLs wastes crawl budget and confuses monitoring.

## CI validation

```bash
curl -s https://staging.example.com/sitemap.xml | xmllint --noout -
# Compare count to DB
psql -c "SELECT count(*) FROM pages WHERE published AND indexable;"
```

Alert if sitemap count diverges from database beyond tolerance — template bug or publish pipeline stuck.

## Cache headers

Sitemap can cache at CDN 1–24 h with purge on bulk publish. `ETag` helps conditional requests from crawlers. Do not cache stale sitemap after mass unpublish event without purge.

## Multilingual hreflang

Either separate sitemap per locale or `xhtml:link` alternates in each URL entry — pick one strategy documented in SEO runbook.

## Next.js sitemap.ts pattern

Generate sitemap from database with cursor pagination — never load all URLs into memory. Split into sitemap index when exceeding fifty thousand URLs or fifty megabytes per file.

## lastmod honesty

Tie `lastmod` to editorial `contentUpdatedAt`, not CMS cache-bust timestamps. False lastmod erodes crawler trust when every URL shows today's date without content change.

## Resources

- [Google sitemap guidelines](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap)
- [Next.js sitemap docs](https://nextjs.org/docs/app/api-reference/file-conventions/metadata/sitemap)

## Operational checklist (1)

Before promoting Seo Sitemap Dynamic Generation changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (2)

Re-baseline Seo Sitemap Dynamic Generation after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (3)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Seo Sitemap Dynamic Generation touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (4)

Before promoting Seo Sitemap Dynamic Generation changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (5)

Re-baseline Seo Sitemap Dynamic Generation after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (6)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Seo Sitemap Dynamic Generation touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (7)

Before promoting Seo Sitemap Dynamic Generation changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (8)

Re-baseline Seo Sitemap Dynamic Generation after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (9)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Seo Sitemap Dynamic Generation touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (10)

Before promoting Seo Sitemap Dynamic Generation changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Telemetry and ownership for seo sitemap dynamic generation

Pair a leading operational signal with a lagging user or risk outcome. Page on burn related to seo sitemap dynamic generation, not vanity counters. Keep a named owner and a dashboard link in the service catalog entry.

| Check | Expected for seo sitemap dynamic generation |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 1: inject the failure mode you fear for seo sitemap dynamic generation in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Rollout sequence for seo sitemap dynamic generation

Prefer flags, weighted routes, or dual-running configs. Rehearse rollback once in staging. The on-call note for seo sitemap dynamic generation should include the revert command and the expected user-visible effect within five minutes.

Concrete probe 2: inject the failure mode you fear for seo sitemap dynamic generation in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Cross-team contracts for seo sitemap dynamic generation

Document producers, consumers, timeouts, and idempotency keys. Silent schema or policy changes are how seo sitemap dynamic generation breaks without a clear owner in the incident channel.

| Check | Expected for seo sitemap dynamic generation |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 3: inject the failure mode you fear for seo sitemap dynamic generation in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Capacity and cost notes for seo sitemap dynamic generation

Estimate QPS, payload size, cardinality, and downstream saturation. Functionally correct seo sitemap dynamic generation changes still cause outages through pool exhaustion, crawl waste, or CPU amplification.

Concrete probe 4: inject the failure mode you fear for seo sitemap dynamic generation in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Reviewer checklist for seo sitemap dynamic generation

Ask what happens when the dependency is slow, when authz is skipped on batch jobs, and when clients retry. Those three questions catch most seo sitemap dynamic generation regressions before production.

| Check | Expected for seo sitemap dynamic generation |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 5: inject the failure mode you fear for seo sitemap dynamic generation in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Incident patterns around seo sitemap dynamic generation

Most incidents involving seo sitemap dynamic generation start as a silent drift: a secondary path skips the control, a retry amplifies load, or a config default from a tutorial ships to production. Write the failure story before the happy path.

Concrete probe 6: inject the failure mode you fear for seo sitemap dynamic generation in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Invariants to enforce for seo sitemap dynamic generation

Name three invariants that must hold after every deploy of seo sitemap dynamic generation. Encode at least one in an automated test that fails when the invariant is disabled. Reviewers should reject PRs that only cover the primary UI path.

| Check | Expected for seo sitemap dynamic generation |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 7: inject the failure mode you fear for seo sitemap dynamic generation in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.
