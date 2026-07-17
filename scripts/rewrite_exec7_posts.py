#!/usr/bin/env python3
"""Rewrite exec7 blog posts as unique human deep dives. No wave2 template."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
DATE_MOD = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")
BANNED = ("## Problem framing", "Copying a tutorial without matching your constraints",
          "The gap between reading about", "I have applied these patterns across product sites")

SLUGS = [
    "nextjs-csp-headers-middleware", "nextjs-draft-mode-preview-content",
    "nextjs-dynamic-import-ssr-false", "nextjs-edge-runtime-limitations",
    "nextjs-fetch-cache-next-revalidate", "nextjs-font-optimization-self-hosted",
    "nextjs-generate-static-params-dynamic", "nextjs-image-optimization",
    "nextjs-instrumentation-observability", "nextjs-intercepting-routes-patterns",
    "nextjs-internationalization-routing", "nextjs-layout-shared-state-patterns",
    "nextjs-link-prefetch-behavior", "nextjs-loading-ui-error-boundaries",
    "nextjs-metadata-dynamic-og-images", "nextjs-metadata-seo-api",
    "nextjs-middleware-edge-runtime", "nextjs-parallel-routes-modal-patterns",
    "nextjs-partial-prerendering-ppr", "nextjs-route-handlers-api-design",
    "nextjs-route-segment-config-cache", "nextjs-script-component-strategies",
    "nextjs-server-actions-error-handling", "nextjs-streaming-skeleton-architecture",
    "nextjs-turbopack-production-migration", "nextjs-unstable-cache-server-functions",
    "node-bullmq-job-priority-retries", "node-cluster-mode-vs-worker-threads",
    "node-cluster-scaling", "node-drizzle-orm-type-safe-sql",
    "node-env-validation-zod-envalid", "node-event-loop-lag-monitoring",
    "node-express-async-error-handling", "node-fastify-plugin-architecture",
    "node-graceful-shutdown-sigterm", "node-http-agent-keepalive-pooling",
    "node-memory-leak-heap-snapshot", "node-nestjs-module-boundaries",
    "node-opentelemetry-auto-instrumentation", "node-pino-structured-logging",
    "node-prisma-transaction-isolation", "node-streams-backpressure",
    "node-typeorm-migration-production", "node-worker-threads-cpu",
    "oauth-pkce-mobile", "oauth2-authorization-code-flow",
    "oauth2-client-credentials-m2m", "oauth2-client-credentials-scopes",
    "oauth2-device-authorization-tv", "oauth2-device-flow-tv",
]

# Import article bodies from companion module
from exec7_articles import ARTICLES  # noqa: E402


def wc(text: str) -> int:
    return len(WORD.findall(text))


def needs_rewrite(raw: str) -> bool:
    body = raw.split("---", 2)[2] if raw.count("---") >= 2 else raw
    if wc(body) < TARGET:
        return True
    return any(b in raw for b in BANNED)


def main() -> None:
    summary = {"rewritten": [], "skipped": [], "missing": [], "errors": []}

    for slug in SLUGS:
        path = BLOG / f"{slug}.md"
        if not path.exists():
            summary["missing"].append(slug)
            continue
        raw = path.read_text()
        if slug not in ARTICLES and not needs_rewrite(raw):
            summary["skipped"].append({"slug": slug, "words": wc(raw.split("---", 2)[2]), "reason": "already good"})
            continue
        if slug not in ARTICLES:
            summary["errors"].append({"slug": slug, "error": "no article content defined"})
            continue
        content = ARTICLES[slug]
        if not content.startswith("---"):
            summary["errors"].append({"slug": slug, "error": "invalid frontmatter"})
            continue
        body = content.split("---", 2)[2]
        if wc(body) < TARGET:
            summary["errors"].append({"slug": slug, "error": f"body only {wc(body)} words"})
            continue
        path.write_text(content)
        summary["rewritten"].append({"slug": slug, "words": wc(body), "dateModified": DATE_MOD})

    out = ROOT / "scripts" / "exec7_rewrite_summary.json"
    out.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
