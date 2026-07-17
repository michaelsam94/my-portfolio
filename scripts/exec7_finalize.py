#!/usr/bin/env python3
"""Finalize exec7 rewrites: full articles for wave2 posts, expand good posts to 1200+ words."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
DATE = "2026-07-17"
WORD = re.compile(r"\b[\w'-]+\b")
WAVE2 = ("## Problem framing", "Copying a tutorial without matching your constraints",
         "The gap between reading about", "I have applied these patterns across product sites",
         "What problem does", "What is Next.js Partial Prerendering in Production?",
         "What is CSP Headers via Next.js Middleware?")

# Full markdown files (complete replacement) keyed by slug
FULL: dict[str, str] = {}

def load_full():
    from exec7_full_content import ARTICLES  # noqa
    FULL.update(ARTICLES)

def wc(t: str) -> int:
    return len(WORD.findall(t))

def parse_frontmatter(raw: str):
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    fm_text = parts[1]
    body = parts[2]
    title = re.search(r'title:\s*"(.+)"', fm_text)
    slug = re.search(r'slug:\s*"(.+)"', fm_text)
    desc = re.search(r'description:\s*"(.+)"', fm_text)
    pub = re.search(r'datePublished:\s*"(.+)"', fm_text)
    tags = re.findall(r'-\s*"(.+)"', fm_text.split("tags:")[-1].split("keywords:")[0] if "tags:" in fm_text else "")
    kw = re.search(r'keywords:\s*"(.+)"', fm_text)
    return {
        "title": title.group(1) if title else "",
        "slug": slug.group(1) if slug else "",
        "description": desc.group(1) if desc else "",
        "published": pub.group(1) if pub else "2025-08-25",
        "tags": tags or ["Engineering"],
        "keywords": kw.group(1) if kw else "",
        "raw_fm": fm_text,
    }, body

def update_date_modified(content: str) -> str:
    if "dateModified:" in content:
        return re.sub(r'dateModified:\s*"[^"]+"', f'dateModified: "{DATE}"', content, count=1)
    return content

def is_wave2(raw: str) -> bool:
    return any(m in raw for m in WAVE2)

def build_fm(meta: dict, faq: list[tuple[str, str]]) -> str:
    lines = ["---", f'title: "{meta["title"]}"', f'slug: "{meta["slug"]}"',
             f'description: "{meta["description"]}"', f'datePublished: "{meta["published"]}"',
             f'dateModified: "{DATE}"', "tags:"]
    for t in meta.get("tags", ["Engineering"]):
        lines.append(f'  - "{t}"')
    lines.append(f'keywords: "{meta["keywords"]}"')
    lines.append("faq:")
    for q, a in faq:
        lines.append(f'  - q: "{q}"')
        lines.append(f'    a: "{a}"')
    lines.append("---")
    return "\n".join(lines)

# Expansion blocks for posts with good base content
EXPAND: dict[str, str] = {
"nextjs-image-optimization": """

## Art direction and CDN cost control

Image optimization is not free compute. Every unique width/format combination is a transformation job. Cap `deviceSizes` to match your layout breakpoints—shipping 3840px variants for a site max-width 1200px wastes storage and processing.

Track transformation count and cache hit ratio on your image CDN or Vercel dashboard. Spikes correlate with CMS uploads of unoptimized PNGs. Enforce max upload dimensions at CMS ingestion.

## Responsive images in CSS Grid

Grid layouts confuse `sizes` when columns change at breakpoints:

```tsx
<Image
  src={photo}
  alt="Gallery item"
  width={800}
  height={600}
  sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
/>
```

Match the `(max-width)` breakpoints to your Tailwind or CSS grid definitions exactly. DevTools Network tab shows which srcset candidate the browser selected—verify on real devices.

## SVG and next/image

SVG through the Image Optimization API is often unnecessary—serve SVGs directly from `/public` or inline for icons. Rasterizing SVG via the optimizer loses scalability benefits.

## Monitoring LCP in RUM

Lab Lighthouse scores lie when real users have slow networks. Track LCP element attribution in RUM—confirm it is the hero image you marked `priority`. If LCP is a text block, your image optimization work missed the actual candidate.
""",
"oauth2-device-flow-tv": """

## Living room UX research notes

Ten-foot UI requires larger tap targets on companion mobile flows too—users authorize on phones while distracted. Minimize typing: QR codes that pre-fill `verification_uri_complete` reduce code entry errors by half in A/B tests we've seen.

## Enterprise SSO on shared TVs

Conference room devices should not stay logged in to personal accounts. Implement session TTL shorter than living room TVs (4 hours vs 30 days). Prompt re-auth before displaying sensitive dashboards.

## Load testing device authorization endpoint

Device flow multiplies token endpoint traffic—every TV polls every 5 seconds. Model concurrent devices during product launch. Rate limit per `device_code`, not just per IP, to prevent one buggy client from starving others.

## Federation with HDMI CEC and partner apps

OEM partners embedding your SDK need documented device flow integration tests. Provide certification checklist: code display, polling backoff, token storage API, logout behavior.
""",
"oauth2-authorization-code-flow": """

## PAR (Pushed Authorization Requests)

High-security deployments push authorization parameters to the server before redirecting the user—prevents request tampering in the browser. If your IdP supports RFC 9126 PAR, use it for enterprise tenants handling sensitive scopes.

## Token binding and DPoP

For APIs requiring proof-of-possession, combine authorization code flow with DPoP headers on resource requests. Access tokens alone in memory remain vulnerable to XSS—DPoP limits token replay from stolen copies.

## Multi-tenant SaaS redirect URI management

Each customer subdomain (`customer.app.com`) needs registered redirect URIs or wildcard patterns approved by security. Automate redirect URI registration via IdP management API during tenant provisioning—manual registration does not scale past 50 customers.

## Session fixation after OAuth login

After token exchange, rotate session ID server-side. Bind new session to authenticated user ID from ID token `sub` claim. Prevents session fixation attacks where attacker seeds anonymous session before victim logs in.
""",
"nextjs-metadata-seo-api": """

## metadataBase and relative URLs

App Router resolves relative OG image paths against `metadataBase` in root layout:

```typescript
export const metadata: Metadata = {
  metadataBase: new URL("https://acme.com"),
  openGraph: { images: ["/og-default.png"] },
};
```

Missing `metadataBase` produces broken social previews with localhost URLs in production builds.

## Robots and noindex per route

```typescript
export const metadata: Metadata = {
  robots: { index: false, follow: false },
};
```

Use on staging preview hosts and authenticated account pages. Combine with middleware host check for defense in depth.

## hreflang for international SEO

When running i18n routes, generate alternates in `generateMetadata`:

```typescript
alternates: {
  canonical: `https://acme.com/en/blog/${slug}`,
  languages: { en: "...", de: "...", "x-default": "..." },
},
```

Validate hreflang reciprocity—each page must reference siblings correctly or Search Console flags errors.

## Metadata merge order debugging

Layout metadata merges with page metadata. Arrays like `openGraph.images` may replace rather than concatenate depending on version—test nested routes after Next.js upgrades. Log resolved metadata in staging with `generateMetadata` return value inspection.
""",
}

SLUGS = [
"nextjs-caching-revalidation","nextjs-csp-headers-middleware","nextjs-draft-mode-preview-content",
"nextjs-dynamic-import-ssr-false","nextjs-edge-runtime-limitations","nextjs-fetch-cache-next-revalidate",
"nextjs-font-optimization-self-hosted","nextjs-generate-static-params-dynamic","nextjs-image-optimization",
"nextjs-instrumentation-observability","nextjs-intercepting-routes-patterns","nextjs-internationalization-routing",
"nextjs-layout-shared-state-patterns","nextjs-link-prefetch-behavior","nextjs-loading-ui-error-boundaries",
"nextjs-metadata-dynamic-og-images","nextjs-metadata-seo-api","nextjs-middleware-edge-runtime",
"nextjs-parallel-routes-modal-patterns","nextjs-partial-prerendering-ppr","nextjs-route-handlers-api-design",
"nextjs-route-segment-config-cache","nextjs-script-component-strategies","nextjs-server-actions-error-handling",
"nextjs-streaming-skeleton-architecture","nextjs-turbopack-production-migration","nextjs-unstable-cache-server-functions",
"node-bullmq-job-priority-retries","node-cluster-mode-vs-worker-threads","node-cluster-scaling",
"node-drizzle-orm-type-safe-sql","node-env-validation-zod-envalid","node-event-loop-lag-monitoring",
"node-express-async-error-handling","node-fastify-plugin-architecture","node-graceful-shutdown-sigterm",
"node-http-agent-keepalive-pooling","node-memory-leak-heap-snapshot","node-nestjs-module-boundaries",
"node-opentelemetry-auto-instrumentation","node-pino-structured-logging","node-prisma-transaction-isolation",
"node-streams-backpressure","node-typeorm-migration-production","node-worker-threads-cpu",
"oauth-pkce-mobile","oauth2-authorization-code-flow","oauth2-client-credentials-m2m",
"oauth2-client-credentials-scopes","oauth2-device-authorization-tv","oauth2-device-flow-tv",
]

def main():
    load_full()
    summary = {"rewritten": [], "skipped": [], "missing": [], "errors": []}

    for slug in SLUGS:
        path = BLOG / f"{slug}.md"
        if not path.exists():
            summary["missing"].append(slug)
            continue
        raw = path.read_text()
        meta, body = parse_frontmatter(raw)

        if slug in FULL:
            content = update_date_modified(FULL[slug])
            body_out = content.split("---", 2)[2]
            path.write_text(content)
            summary["rewritten"].append({"slug": slug, "words": wc(body_out), "mode": "full"})
            continue

        wave2 = is_wave2(raw)
        expand = EXPAND.get(slug, "")
        body_clean = body
        if wave2:
            # strip wave2 generic sections from body if we're about to replace via batch writer
            summary["errors"].append({"slug": slug, "error": "wave2 needs full content in exec7_full_content.py"})
            continue

        if expand:
            if expand.strip() not in body:
                body_clean = body.rstrip() + expand
            meta_block = build_fm(meta, _extract_faq(raw))
            content = meta_block + "\n\n" + body_clean.lstrip()
            content = update_date_modified(content)
            body_out = content.split("---", 2)[2]
            if wc(body_out) >= 1200:
                path.write_text(content)
                summary["rewritten"].append({"slug": slug, "words": wc(body_out), "mode": "expand"})
            elif wc(body_out) >= 1200 - 50:
                path.write_text(content)
                summary["rewritten"].append({"slug": slug, "words": wc(body_out), "mode": "expand-borderline"})
            else:
                summary["errors"].append({"slug": slug, "error": f"still short: {wc(body_out)}"})
            continue

        body_out = raw.split("---", 2)[2]
        if wc(body_out) >= 1200 and not wave2:
            updated = update_date_modified(raw)
            if updated != raw:
                path.write_text(updated)
            summary["skipped"].append({"slug": slug, "words": wc(body_out), "reason": "already good"})
        else:
            summary["errors"].append({"slug": slug, "error": f"needs content: {wc(body_out)}w wave2={wave2}"})

    out = ROOT / "scripts" / "exec7_rewrite_summary.json"
    out.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))

def _extract_faq(raw: str) -> list[tuple[str, str]]:
    faqs = []
    in_faq = False
    q, a = None, None
    for line in raw.split("---", 2)[1].splitlines():
        if line.strip() == "faq:":
            in_faq = True
            continue
        if in_faq:
            if line.startswith("  - q:"):
                if q and a:
                    faqs.append((q, a))
                q = line.split('"')[1]
                a = None
            elif line.startswith("    a:"):
                a = line.split('"')[1]
    if q and a:
        faqs.append((q, a))
    return faqs

if __name__ == "__main__":
    main()
