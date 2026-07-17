---
title: "AI Agents: Cdn Cache Purge Strategies"
slug: "agent-cdn-cache-purge-strategies"
description: "CDN cache purge strategies for agent-facing assets — selective invalidation, surrogate keys, soft purges, rate limits, and coordination with embedding pipeline deploys."
datePublished: "2026-04-12"
dateModified: "2026-04-12"
tags: ["AI", "Agent", "Cdn"]
keywords: "CDN cache purge, cache invalidation, surrogate keys, soft purge, CloudFront invalidation, Fastly purge, agent static assets, purge API rate limits"
faq:
  - q: "When should you purge the CDN versus relying on cache TTL?"
    a: "Purge when stale content is user-visible and TTL hasn't expired — security fixes, corrected agent prompts in static bundles, wrong retrieval metadata in edge-cached JSON, or branding changes. Prefer short TTLs plus stale-while-revalidate for non-critical assets; reserve purges for correctness-critical or zero-day fixes where waiting 3600 seconds is unacceptable."
  - q: "What is the difference between hard purge and soft purge?"
    a: "Hard purge removes objects from edge caches immediately; the next request fetches from origin. Soft purge (Fastly, some Cloudflare tiers) marks objects stale and revalidates on next request without origin thundering herd. Soft purge is safer for high-traffic agent widget endpoints; hard purge is necessary when content must disappear instantly (PII leak, revoked API docs)."
  - q: "How do surrogate keys prevent purge storms during agent deploys?"
    a: "Tag responses with surrogate-key headers grouping related objects (tenant, model-version, prompt-bundle-v3). One API call purges all keys matching a deploy artifact instead of listing thousands of URLs. Agent platforms that ship prompt templates as hashed static files still need key-based purge when unhashed config endpoints change."
  - q: "What purge rate limits should teams plan for?"
    a: "CloudFront allows 1,000 free invalidation paths per month then charges per path; wildcard paths count as one but still propagate slowly at scale. Fastly and Cloudflare offer higher API limits but per-service quotas apply. Design purge budgets: batch URL lists, dedupe purge requests in CI, and use versioned URLs as the default so most deploys need zero purges."
---
An agent product team shipped a hotfix to a JavaScript widget that rendered chat UI — and watched half their users still get the broken build six hours later. CI ran `./purge-all.sh /*` against CloudFront, hit the monthly invalidation cap on path three of a monorepo deploy, and silently continued. Edge nodes in Asia served cached `agent-widget.v2.js` while US users got `v3`. Cache purging is not an afterthought to CDN setup; for agent platforms serving static prompts, SDK bundles, and tenant-branded assets at the edge, **purge strategy is release engineering**.

Agent workloads mix cacheable and uncacheable surfaces. Inference APIs must never cache. But marketing embeds, admin dashboards, OpenAPI specs, precomputed retrieval manifests, and WebAssembly tokenizers often sit behind a CDN. When a prompt injection patch lands or a tenant offboards and their branded assets must vanish, you need predictable invalidation — not prayer and `Cache-Control: no-cache` in panic.

## Cache layers in agent architectures

Typical stack:

```
Browser ──► CDN edge ──► Origin (S3 / API gateway / Next.js)
                │
                └── Cached: static JS/CSS, public docs, manifest JSON
                    Bypass: /v1/chat/completions, /v1/agents/run, auth
```

Purges operate at the **CDN edge** and sometimes **downstream** (browser cache via shorter TTLs, service worker caches). A CDN purge does not clear a user's browser if `max-age=31536000` was sent yesterday. Strategy must cover all layers.

| Asset type | Versioning approach | Purge needed? |
|------------|--------------------|--------------:|
| Hashed JS bundles (`app.a1b2c3.js`) | Content hash in filename | Rarely — new deploy = new URL |
| Unversioned config (`/config/agent.json`) | None | Yes, on every config change |
| Tenant logos (`/assets/tenant/{id}/logo.png`) | Path keyed by tenant | Yes, on rebrand |
| OpenAPI / tool schemas | Semver path or ETag | Purge or short TTL |
| Public RAG corpus snapshots | Immutable snapshot id | No — rotate snapshot id |

**Default to immutable URLs.** Purge is the exception for resources you chose not to version.

## Purge mechanisms compared

**URL purge (path invalidation)** — list exact paths or wildcards (`/static/agent/*`). Simple, provider-native, rate-limited.

**Prefix / directory purge** — invalidate everything under a prefix. One call, but over-invalidates if prefix is broad.

**Surrogate key purge** — origin sends `Surrogate-Key: tenant-441 prompt-bundle-2026-04-12`; purge API accepts keys, not URLs. Best for agent multi-tenant assets where one logical change touches dozens of files.

**Tag purge (Cloudflare Cache-Tag)** — similar to surrogate keys via `Cache-Tag` response header.

**Soft purge** — mark stale, revalidate in background or on next request. Reduces origin spikes when millions of embeds refetch simultaneously.

Choose by CDN vendor and traffic shape. Fastly excels at surrogate keys; CloudFront users often combine versioned assets with targeted invalidations; Cloudflare favors cache tags.

## Implementing surrogate-key purges

Origin must emit keys on every cacheable response:

```typescript
// middleware/cdnSurrogateKeys.ts
export function withSurrogateKeys(
  res: Response,
  keys: string[],
  cacheControl = "public, max-age=3600, stale-while-revalidate=86400"
): Response {
  const headers = new Headers(res.headers);
  headers.set("Cache-Control", cacheControl);
  headers.set("Surrogate-Key", keys.join(" "));
  // Cloudflare alternative: headers.set("Cache-Tag", keys.join(","));
  return new Response(res.body, { status: res.status, headers });
}

// Tenant-branded agent embed config
app.get("/embed/:tenantId/config.json", async (req, res) => {
  const cfg = await loadTenantConfig(req.params.tenantId);
  const body = JSON.stringify(cfg);
  return withSurrogateKeys(
    new Response(body, { headers: { "Content-Type": "application/json" } }),
    [`tenant-${cfg.tenantId}`, `embed-config`, `prompt-v${cfg.promptVersion}`]
  );
});
```

Deploy pipeline purges by key when prompt version bumps:

```bash
#!/usr/bin/env bash
# scripts/purge-prompt-version.sh
set -euo pipefail
PROMPT_VERSION="${1:?prompt version required}"
FASTLY_SERVICE_ID="${FASTLY_SERVICE_ID:?}"
FASTLY_TOKEN="${FASTLY_TOKEN:?}"

curl -sf -X POST "https://api.fastly.com/service/${FASTLY_SERVICE_ID}/purge" \
  -H "Fastly-Key: ${FASTLY_TOKEN}" \
  -H "Accept: application/json" \
  -H "Surrogate-Key: prompt-v${PROMPT_VERSION}" \
  -d ''
echo "Purged surrogate key prompt-v${PROMPT_VERSION}"
```

For CloudFront, invalidation API accepts paths — no native surrogate keys. Mitigations: shorter TTL on config paths, Lambda@Edge key routing, or migrate hot config to versioned S3 objects with CloudFront pointing at versioned prefixes.

## CI/CD integration and deduplication

Purge calls belong in deploy pipelines **after** origin confirms new artifacts, **before** traffic shift — or immediately after for config-only changes.

Anti-patterns:

- Purging `/*` on every commit — expensive, slow propagation, hides missing versioning
- Parallel deploy jobs each purging the same paths — duplicate API calls, quota burn
- Purging before S3 sync completes — edge refetches stale origin

Better pattern — centralized purge coordinator:

```typescript
// deploy/purgeCoordinator.ts
import { createHash } from "crypto";
import Redis from "ioredis";

const redis = new Redis(process.env.REDIS_URL!);

export async function requestPurge(keys: string[]): Promise<void> {
  const sorted = [...keys].sort().join("|");
  const digest = createHash("sha256").update(sorted).digest("hex");

  // Dedupe within 10-minute window
  const acquired = await redis.set(`purge:dedupe:${digest}`, "1", "EX", 600, "NX");
  if (!acquired) {
    console.log("Skipping duplicate purge request", keys);
    return;
  }

  await cdnClient.purgeSurrogateKeys(keys);
  await auditLog.write({ action: "cdn_purge", keys, digest, at: new Date().toISOString() });
}
```

Log every purge with actor, keys/paths, deploy id, and propagation status. Post-incident reviews ask "did we purge?" constantly.

## Agent-specific purge scenarios

**Prompt template updates** — if templates ship as static JSON at `/prompts/latest.json`, purge or (preferably) publish to `/prompts/2026-04-12T14:00:00Z.json` and update a tiny pointer file with 60-second TTL.

**SDK embed security patch** — hashed bundle gets new filename; purge unhashed entrypoints (`/embed.js`, `/loader.js`) that redirect or re-export.

**Tenant offboarding** — purge all keys `tenant-{id}`, `tenant-{id}-*`. Pair with origin ACL denial so refetch fails closed.

**Retrieval manifest changes** — edge-cached manifests listing chunk URLs for public agents must invalidate when corpus deletes occur; surrogate key `corpus-{corpusId}`.

**A/B experiment cleanup** — purge experiment-specific assets when bucketing ends to prevent stale variant leakage.

## Rate limits, cost, and propagation delay

CloudFront invalidations:

- First 1,000 paths/month free per account, then per-path fees
- Wildcard `/*.js` counts as one path but invalidation takes minutes to hours globally
- Maximum 3,000 concurrent invalidation requests (soft limit)

Plan **purge budgets** in runbooks. High-churn agent SaaS with per-tenant assets should not rely on URL invalidation alone.

Propagation is **eventually consistent**. Do not assume purge API 200 means all edges cleared instantly. Verify with:

```bash
# Check edge response from multiple PoPs via synthetic monitors
curl -sI "https://cdn.example.com/embed/acme/config.json" | grep -i x-cache
# Expect MISS or refreshed HIT after purge + allow 60-120s
```

Run synthetic checks from multiple regions after critical security purges.

## Security and abuse considerations

Purge APIs are powerful — a leaked token lets an attacker force origin load or cache bypass DoS. Store tokens in secrets managers, scope to purge-only IAM roles, and restrict CI service accounts. Never expose purge endpoints to agent tool handlers or user-triggered workflows without strict authorization.

Audit purge actions for insider threat and mistake detection. "Purged tenant-*" at 3 AM deserves a page.

For accidental PII in cached public docs, **hard purge** plus shortened browser TTL on affected paths. Soft purge is insufficient when compliance requires immediate invisibility.

## Coordinated invalidation with application caches

CDN purge does not flush Redis application caches holding session entitlements or feature flags. Agent runtimes often cache tool schemas in memory. Deploy runbooks should sequence:

1. Update origin data / flags
2. Flush application caches (Redis `UNLINK` by key pattern)
3. CDN purge surrogate keys
4. Verify end-to-end with canary tenant

Missing step 2 yields "CDN fresh, app stale" bugs that confuse debugging.

## Testing purge behavior

Staging CDN service (separate Fastly service or CloudFront distribution) mirrors production cache rules. Tests:

- Asset cached → purge key → assert `Age: 0` or `X-Cache: Miss`
- Wildcard vs key purge scope — ensure neighbor tenants unaffected
- Purge deduplication in CI — two parallel jobs, one API call
- Origin failure during revalidation — edge serves stale per `stale-if-error` if configured

Game-day: simulate hotfix deploy under load, measure origin QPS spike post-purge, tune soft purge vs pre-warming.

## Closing

CDN cache purge strategy for agent platforms boils down to: **version everything you can**, **tag what you cannot**, **purge by key not by panic wildcard**, and **instrument propagation**. Purges are a release tool with quotas and delay — not a substitute for immutable deploy artifacts. Teams that internalize this ship prompt fixes without six-hour edge schisms.

## Resources

- [Amazon CloudFront Invalidation](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Invalidation.html)
- [Fastly Surrogate Keys](https://www.fastly.com/documentation/guides/concepts/edge-state/cache/surrogate-keys/)
- [Cloudflare Cache Tags](https://developers.cloudflare.com/cache/how-to/purge-cache/purge-by-tags/)
- [HTTP Cache-Control and CDN behavior (RFC 9111)](https://www.rfc-editor.org/rfc/rfc9111.html)
- [Stale-while-revalidate at the edge](https://web.dev/articles/stale-while-revalidate)
