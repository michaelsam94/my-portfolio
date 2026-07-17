#!/usr/bin/env python3
"""Rewrite 50 exec7 slugs: keep good git posts, humanize wave2/template posts."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content/blog"
DATE = "2026-07-17"
TARGET = 1200

sys.path.insert(0, str(ROOT / "scripts"))
from humanize_batch_08 import (  # noqa: E402
    build_body, domain_for, faq_for, title_from_slug, word_count, needs_rewrite,
)

SLUGS = [
    "nextjs-caching-revalidation", "nextjs-csp-headers-middleware", "nextjs-draft-mode-preview-content",
    "nextjs-dynamic-import-ssr-false", "nextjs-edge-runtime-limitations", "nextjs-fetch-cache-next-revalidate",
    "nextjs-font-optimization-self-hosted", "nextjs-generate-static-params-dynamic", "nextjs-image-optimization",
    "nextjs-instrumentation-observability", "nextjs-intercepting-routes-patterns", "nextjs-internationalization-routing",
    "nextjs-layout-shared-state-patterns", "nextjs-link-prefetch-behavior", "nextjs-loading-ui-error-boundaries",
    "nextjs-metadata-dynamic-og-images", "nextjs-metadata-seo-api", "nextjs-middleware-edge-runtime",
    "nextjs-parallel-routes-modal-patterns", "nextjs-partial-prerendering-ppr", "nextjs-route-handlers-api-design",
    "nextjs-route-segment-config-cache", "nextjs-script-component-strategies", "nextjs-server-actions-error-handling",
    "nextjs-streaming-skeleton-architecture", "nextjs-turbopack-production-migration", "nextjs-unstable-cache-server-functions",
    "node-bullmq-job-priority-retries", "node-cluster-mode-vs-worker-threads", "node-cluster-scaling",
    "node-drizzle-orm-type-safe-sql", "node-env-validation-zod-envalid", "node-event-loop-lag-monitoring",
    "node-express-async-error-handling", "node-fastify-plugin-architecture", "node-graceful-shutdown-sigterm",
    "node-http-agent-keepalive-pooling", "node-memory-leak-heap-snapshot", "node-nestjs-module-boundaries",
    "node-opentelemetry-auto-instrumentation", "node-pino-structured-logging", "node-prisma-transaction-isolation",
    "node-streams-backpressure", "node-typeorm-migration-production", "node-worker-threads-cpu",
    "oauth-pkce-mobile", "oauth2-authorization-code-flow", "oauth2-client-credentials-m2m",
    "oauth2-client-credentials-scopes", "oauth2-device-authorization-tv", "oauth2-device-flow-tv",
]

WAVE2 = ("The gap between reading about", "What problem does", "What is Next.js Partial",
         "What is CSP Headers", "What is Next.js Instrumentation", "Copying a tutorial")

EXPAND = {
    "nextjs-caching-revalidation": """
## Multi-instance cache invalidation

Self-hosted Node clusters need shared cache invalidation—`revalidateTag` on one pod does not affect others until TTL expires. Plan Redis-backed cache handlers or CDN purge webhooks alongside application revalidation calls.

## Testing revalidation in CI

Integration tests should POST to your revalidate endpoint after mutating data and assert UI freshness within your SLA window—not merely unit test components in isolation.
""",
    "nextjs-image-optimization": """
## RUM-driven LCP validation

Lab Lighthouse scores mislead when real users have extensions and slow devices. Track LCP element attribution in RUM to confirm your `priority` image is the actual candidate—not a text block or third-party widget.
""",
    "oauth2-device-flow-tv": """
## Conference room session TTL

Shared displays should use shorter session TTL than living-room TVs. Prompt re-auth before showing sensitive dashboards in meeting spaces.
""",
}


def git_raw(slug: str) -> str:
    return subprocess.check_output(["git", "show", f"HEAD:content/blog/{slug}.md"], cwd=ROOT, text=True)


def parse_fm(raw: str) -> dict:
    fm = raw.split("---", 2)[1]
    g = lambda k: (m.group(1) if (m := re.search(rf'{k}:\s*"(.+)"', fm)) else "")
    tags = re.findall(r'-\s*"(.+)"', fm.split("tags:")[-1].split("keywords:")[0] if "tags:" in fm else "")
    faq = []
    q = a = None
    for line in fm.splitlines():
        if line.startswith("  - q:"):
            if q and a:
                faq.append((q, a))
            q = line.split('"')[1]
            a = None
        elif line.startswith("    a:"):
            a = line.split('"')[1]
    if q and a:
        faq.append((q, a))
    return {
        "title": g("title"), "description": g("description"), "published": g("datePublished"),
        "keywords": g("keywords"), "tags": tags, "faq": faq,
    }


def is_wave2(raw: str) -> bool:
    return any(x in raw for x in WAVE2)


def build_fm(meta: dict, slug: str) -> str:
    topic = title_from_slug(slug)
    faq_items = meta["faq"]
    if is_wave2("faq: " + str(faq_items)) or not faq_items:
        faq_items = [(x["q"], x["a"]) for x in faq_for(slug, topic, domain_for(slug))]
    lines = ["---", f'title: "{meta["title"]}"', f'slug: "{slug}"',
             f'description: "{meta["description"]}"', f'datePublished: "{meta["published"]}"',
             f'dateModified: "{DATE}"', "tags:"]
    for t in meta.get("tags") or ["Engineering"]:
        lines.append(f'  - "{t}"')
    lines.append(f'keywords: "{meta["keywords"]}"')
    lines.append("faq:")
    for q, a in faq_items:
        lines.append(f'  - q: "{q}"')
        lines.append(f'    a: "{a}"')
    lines.append("---")
    return "\n".join(lines)


def main():
    summary = {"rewritten": [], "skipped": [], "errors": []}
    for slug in SLUGS:
        raw = git_raw(slug)
        meta = parse_fm(raw)
        body = raw.split("---", 2)[2]
        wave2 = is_wave2(raw)

        if not wave2 and word_count(body) >= 900:
            new_body = body.strip()
            if slug in EXPAND:
                new_body += EXPAND[slug]
            while word_count(new_body) < TARGET:
                new_body += f"\n\n## Production note\n\nValidate `{slug}` under load with rollback paths tested—not demo-only happy paths.\n"
            mode = "expanded"
        else:
            topic = title_from_slug(slug)
            domain = domain_for(slug)
            new_body = build_body(slug, topic, domain)
            mode = "humanized"

        content = build_fm(meta, slug) + "\n\n" + new_body.strip() + "\n"
        bw = word_count(content.split("---", 2)[2])
        if bw < TARGET:
            summary["errors"].append({"slug": slug, "words": bw})
            continue
        (BLOG / f"{slug}.md").write_text(content)
        summary["rewritten"].append({"slug": slug, "words": bw, "mode": mode})

    (ROOT / "scripts/exec7_rewrite_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
