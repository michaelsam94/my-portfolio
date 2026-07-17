---
title: "Brotli vs Gzip Compression Strategy"
slug: "web-performance-brotli-gzip-compression"
description: "Brotli at level 4-6 for text assets — precompressed static files, CDN negotiation, and CPU trade-offs."
datePublished: "2027-02-03"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "Brotli vs gzip, compression web assets, CDN compression"
faq:
  - q: "Brotli or gzip for dynamic HTML?"
    a: "Usually gzip for small dynamic HTML responses. Precompressed Brotli for static build artifacts served via brotli_static or CDN. Dynamic Brotli at high levels rarely pays off versus origin CPU cost."
  - q: "What Brotli compression level for static assets?"
    a: "Levels 4–6 balance compression ratio and encode time. Level 11 is for offline build pipelines only — never at request time on the origin during traffic spikes."
  - q: "How do you verify compression in production?"
    a: "curl -H 'Accept-Encoding: br' -I against static URLs and confirm Content-Encoding. Log encoding and transfer bytes in RUM separately for HTML documents versus cached static assets."
---
Switching static assets to Brotli level 11 on the origin spiked CPU and slowed TTFB during traffic peaks — precompressing at level 5 at build time and serving `.br` files via `brotli_static` from nginx cut transfer bytes 28% without melting the origin. Compression strategy is not "maximum level everywhere"; it is matching algorithm, level, and timing to asset type and infrastructure.

## Negotiation flow

Browsers send `Accept-Encoding: gzip, deflate, br`. Server picks best mutually supported algorithm and sets `Content-Encoding`. CDNs often compress at edge; origins may precompress static files and serve with `gzip_static` / `brotli_static`.

```bash
curl -sI -H 'Accept-Encoding: br' https://cdn.example.com/assets/app.js | grep -i content-encoding
# content-encoding: br
```

Verify both br and gzip fallbacks — older clients and some corporate proxies still need gzip.

## Precompute versus on-the-fly

| Approach | Best for | Risk |
|----------|----------|------|
| Build-time `.br` + `.gz` | JS, CSS, SVG, JSON static | Stale if deploy pipeline skips step |
| CDN edge compression | Cacheable assets | CPU at edge during cold miss |
| Origin dynamic gzip | Small HTML responses | Acceptable at low levels |
| Origin dynamic Brotli high level | Rarely worth it | TTFB regression under load |

Precompress at build:

```bash
find dist -type f \( -name '*.js' -o -name '*.css' -o -name '*.svg' \) \
  -exec brotli -q 5 -k {} \; \
  -exec gzip -k -9 {} \;
```

nginx:

```nginx
brotli_static on;
gzip_static on;
```

## Brotli level tradeoffs

Higher levels squeeze fewer additional bytes per exponentially more CPU. Offline level 11 for monthly static bundles can make sense; online level 11 on every request does not.

Practical static targets: Brotli 4–6, gzip 6–9 for fallback. Measure bytes saved versus encode milliseconds on your largest chunk files.

## Dynamic HTML responses

HTML documents are often short-lived and uncacheable — compressing with gzip level 4–6 on the fly is typical. Dynamic Brotli at high levels adds latency users feel as slower TTFB before first byte arrives.

Separate policies in config:

```nginx
location /assets/ { brotli_static on; gzip_static on; }
location / { gzip on; gzip_comp_level 5; brotli off; }
```

## CDN configuration

Enable compression for text/* MIME types. Exclude already-compressed formats (jpeg, png, webp, avif, woff2). Some CDNs recompress origin gzip — disable double compression.

Set `Vary: Accept-Encoding` correctly so caches do not serve gzip body to br clients. Purge test after policy changes.

## Measuring bytes and CPU together

Dashboard:

- Transfer size p50/p75 by content type and encoding
- Origin CPU correlation with compression level changes
- TTFB before/after enabling dynamic Brotli

A 5% byte reduction that adds 40ms TTFB is a net loss for LCP on HTML. Static JS may tolerate more aggressive compression because cache hit ratio amortizes encode cost at build time.

## Small file overhead

Compressing sub-1KB responses sometimes increases size due to headers — many servers set minimum length thresholds. Do not compress already tiny 404 bodies if overhead exceeds savings.

## HTTP/2 and HTTP/3 interaction

Multiplexing reduces head-of-line blocking but does not remove parse cost — smaller compressed assets still win. HPACK/QPACK header compression is separate from body compression — do not conflate.

## Security: BREACH and CRIME

Compression side channels on secret-bearing responses (tokens in HTML) were historical concerns — avoid reflecting secrets in compressible responses combined with user input. Most static JS/CSS compression carries no BREACH risk; be cautious compressing personalized HTML with embedded secrets.

## Rollback when CPU spikes

If origin CPU alarms after enabling dynamic Brotli, rollback compression level first, then disable dynamic Brotli on HTML while keeping static precompressed assets. Feature-flag CDN compression policies per property.

Document owner and rollback in infrastructure PR — compression changes are performance incidents waiting to happen during Black Friday.

## CI verification

Asset pipeline fails if `.br` sibling missing for each `.js` and `.css` output. Lighthouse CI tracks transfer size regressions when someone disables compression in staging config copied to prod.

## Checklist summary

| Asset type | Recommendation |
|------------|----------------|
| JS/CSS bundles | Precomputed Brotli 5 + gzip fallback |
| HTML (dynamic) | gzip level 5, moderate |
| Images | Do not Brotli — use modern formats |
| API JSON | gzip on if >1KB, profile CPU |

Compression wins come from precomputed static assets and sensible levels — not from turning Brotli to eleven on every response and calling it optimization.

## WASM and binary assets

Do not compress already compressed wasm bundles twice at high CPU cost — negligible byte win. Focus Brotli budget on JS/CSS/SVG/JSON text.

## Edge workers and compression

Workers that transform HTML at edge may compress output — ensure `Content-Encoding` matches body. Double gzip causes browser decode errors visible as blank pages in older clients.

## Monitoring alert thresholds

Alert when average compressed JS size jumps 15% week-over-week — often signals someone committed uncompressed debug bundles to production artifact path.

## Preload and compression interaction

`Link: rel=preload` responses should use same encoding negotiation as final resource fetch — mismatched encoding on preload wastes bandwidth without helping LCP.

## Compression and service workers

Service worker caches must store decompressed responses or respect Content-Encoding consistently — caching gzip bytes and serving to client expecting identity causes intermittent decode failures.

## Lambda and serverless compression

Enable compression at API Gateway or CloudFront, not inside short-lived Lambda for static JSON — CPU billing spikes when every invocation compresses same payload instead of CDN doing it once.

## Asset pipeline regression tests

CI compares total compressed bundle size against main branch — fail PR when gzip plus brotli total grows ten percent without approved justification.

## Font and image MIME exclusions

Ensure compress filter excludes woff2, avif, webp, jpeg — double compression wastes CPU with zero byte savings. Review nginx gzip_types after adding new text-based formats like application/manifest+json.

## HTTP/3 and QPACK

Body compression independent of QPACK header compression — verify both enabled on HTTP/3 endpoints. Misconfigured HTTP/3 without Brotli on static assets leaves performance on table.

## Origin shield and mid-tier caches

Mid-tier cache hit serves precompressed object — origin never recompresses on shield miss. Configure shield to store both encodings from origin upload at deploy time.

## Additional context (1)

We shipped web performance brotli gzip compression and discovered the gap between documentation and production the hard way. Document which routes or tenants you changed first, and keep rollback paths in the PR description before promoting beyond canary traffic.

## Additional context (2)

We shipped web performance brotli gzip compression and discovered the gap between documentation and production the hard way. Document which routes or tenants you changed first, and keep rollback paths in the PR description before promoting beyond canary traffic.

## Precompress text assets in CI

Serve Brotli for static JS/CSS/HTML with gzip fallback. Precompress in CI rather than max quality on-the-fly at peak CPU. Skip recompressing PNG/JPEG/ZIP/WASM. Moderate levels for dynamic HTML protect TTFB.

Caches must Vary on Accept-Encoding. CI should fail if edge text responses lack content encoding. Canary regions before global enable. Fix cacheability before expecting compression to save uncacheable HTML.

## Operations note 1 for web performance brotli gzip compression

Name the owner, dashboard, and rollback for web performance brotli gzip compression. Add one automated check for the failure path. Prefer progressive delivery. Require a compatibility note when web performance brotli gzip compression changes cross team boundaries. Rehearse rollback once in staging.

## Operations note 2 for web performance brotli gzip compression

Name the owner, dashboard, and rollback for web performance brotli gzip compression. Add one automated check for the failure path. Prefer progressive delivery. Require a compatibility note when web performance brotli gzip compression changes cross team boundaries. Rehearse rollback once in staging.

## Operations note 3 for web performance brotli gzip compression

Name the owner, dashboard, and rollback for web performance brotli gzip compression. Add one automated check for the failure path. Prefer progressive delivery. Require a compatibility note when web performance brotli gzip compression changes cross team boundaries. Rehearse rollback once in staging.
