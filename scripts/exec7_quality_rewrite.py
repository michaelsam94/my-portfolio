#!/usr/bin/env python3
"""Quality rewrite: preserve good git content, strip wave2, append unique topic expansions."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
DATE = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")

WAVE2_MARKERS = (
    "## Problem framing", "Copying a tutorial without matching your constraints",
    "The gap between reading about", "I have applied these patterns across product sites",
    "What problem does", "What is Next.js Partial Prerendering",
    "What is CSP Headers via Next.js Middleware", "What is Next.js Instrumentation",
    "Teams ship backend changes without rehearsing", "If you are implementing",
)

STRIP_SECTIONS = [
    "## Common production mistakes", "## Debugging and triage workflow",
    "## Operational checklist", "## Performance tuning notes", "## Rollout and migration",
    "## Testing recommendations", "## Incident patterns we see",
    "## Architecture and boundaries", "## Implementation patterns",
    "## Accessibility requirements", "## Security and privacy considerations",
    "## Testing strategy",
]

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

from exec7_unique_expansions import EXPANSIONS, FAQ_OVERRIDES, FULL_REPLACE  # noqa: E402


def wc(t: str) -> int:
    return len(WORD.findall(t))


def is_wave2(raw: str) -> bool:
    return any(m in raw for m in WAVE2_MARKERS)


def git_show(slug: str) -> str:
    return subprocess.check_output(
        ["git", "show", f"HEAD:content/blog/{slug}.md"], cwd=ROOT, text=True
    )


def parse_fm(raw: str) -> tuple[dict, str]:
    parts = raw.split("---", 2)
    fm, body = parts[1], parts[2]
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
        "title": g("title"), "slug": g("slug"), "description": g("description"),
        "published": g("datePublished") or "2025-08-25", "keywords": g("keywords"), "tags": tags, "faq": faq,
    }, body


def build_fm(meta: dict) -> str:
    lines = ["---", f'title: "{meta["title"]}"', f'slug: "{meta["slug"]}"',
             f'description: "{meta["description"]}"', f'datePublished: "{meta["published"]}"',
             f'dateModified: "{DATE}"', "tags:"]
    for t in meta.get("tags") or ["Engineering"]:
        lines.append(f'  - "{t}"')
    lines.append(f'keywords: "{meta["keywords"]}"')
    lines.append("faq:")
    for q, a in meta.get("faq") or []:
        lines.append(f'  - q: "{q}"')
        lines.append(f'    a: "{a}"')
    lines.append("---")
    return "\n".join(lines)


def strip_wave2(body: str) -> str:
    for m in STRIP_SECTIONS:
        if m in body:
            body = body.split(m)[0]
    for opener in ["The gap between reading about", "I have applied these patterns"]:
        if opener in body:
            i = body.find(opener)
            n = body.find("\n\n## ", i)
            if n > i:
                body = body[:i] + body[n + 2 :]
    return body.strip()


def bad_faq(faq: list) -> bool:
    if not faq:
        return True
    bad = ("What problem does", "production pattern for frontend", "What is Next.js Partial",
           "What is CSP Headers", "What is Next.js Instrumentation", "production gaps teams hit")
    return any(any(b in x for b in bad) for pair in faq for x in pair)


def main():
    summary = {"rewritten": [], "skipped": [], "errors": []}
    for slug in SLUGS:
        try:
            raw = git_show(slug)
        except subprocess.CalledProcessError:
            raw = (BLOG / f"{slug}.md").read_text()
        meta, body = parse_fm(raw)
        if slug in FAQ_OVERRIDES:
            meta["faq"] = FAQ_OVERRIDES[slug]
        elif bad_faq(meta.get("faq", [])):
            meta["faq"] = EXPANSIONS.get(slug, {}).get("faq", meta.get("faq", []))

        if slug in FULL_REPLACE:
            body = FULL_REPLACE[slug]
        else:
            body = strip_wave2(body)
            exp = EXPANSIONS.get(slug, {}).get("body", "")
            if exp and exp not in body:
                body = body + "\n\n" + exp

        while wc(body) < TARGET:
            extra = EXPANSIONS.get(slug, {}).get("pad", "")
            if not extra or extra in body:
                break
            body += "\n\n" + extra

        content = build_fm(meta) + "\n\n" + body.strip() + "\n"
        bw = wc(content.split("---", 2)[2])
        if bw < TARGET:
            summary["errors"].append({"slug": slug, "words": bw})
            continue
        (BLOG / f"{slug}.md").write_text(content)
        summary["rewritten"].append({"slug": slug, "words": bw, "wave2_was": is_wave2(raw)})

    (ROOT / "scripts/exec7_rewrite_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
