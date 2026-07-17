#!/usr/bin/env python3
"""Final pass: strip wave2 boilerplate, append topic addenda, set dateModified."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content/blog"
DATE = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")

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

WAVE2 = (
    "The gap between reading about", "I have applied these patterns across product sites",
    "## Problem framing", "Copying a tutorial without matching your constraints",
    "What problem does", "What is Next.js Partial Prerendering in Production?",
    "What is CSP Headers via Next.js Middleware?", "What is Next.js Instrumentation",
    "Teams ship backend changes without rehearsing", "If you are implementing",
    "## Architecture and boundaries", "## Implementation patterns",
    "## Accessibility requirements", "## Security and privacy considerations",
    "## Testing strategy", "## Common production mistakes", "## Debugging and triage workflow",
    "## Operational checklist", "## Performance tuning notes", "## Rollout and migration",
    "## Testing recommendations", "## Incident patterns we see",
)

from exec7_addenda import ADDENDA, FAQS  # noqa: E402


def wc(t: str) -> int:
    return len(WORD.findall(t))


def git_raw(slug: str) -> str:
    return subprocess.check_output(["git", "show", f"HEAD:content/blog/{slug}.md"], cwd=ROOT, text=True)


def parse(raw: str) -> tuple[dict, str]:
    p = raw.split("---", 2)
    fm, body = p[1], p[2]
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


def strip_wave2(body: str) -> str:
    for m in WAVE2:
        if m.startswith("##") and m in body:
            body = body.split(m)[0]
        elif m in body:
            while m in body:
                i = body.find(m)
                n = body.find("\n\n## ", i + 1)
                if n == -1:
                    body = body[:i]
                else:
                    body = body[:i] + body[n + 2:]
    return body.strip()


def bad_faq(faq: list) -> bool:
    bad = ("What problem does", "production pattern for frontend", "What is Next.js Partial",
           "What is CSP Headers", "What is Next.js Instrumentation", "production gaps teams hit")
    return not faq or any(any(b in s for b in bad) for pair in faq for s in pair)


def fm(meta: dict) -> str:
    L = ["---", f'title: "{meta["title"]}"', f'slug: "{meta["slug"]}"', f'description: "{meta["description"]}"',
         f'datePublished: "{meta["published"]}"', f'dateModified: "{DATE}"', "tags:"]
    for t in meta.get("tags") or ["Engineering"]:
        L.append(f'  - "{t}"')
    L += [f'keywords: "{meta["keywords"]}"', "faq:"]
    for q, a in meta.get("faq") or []:
        L += [f'  - q: "{q}"', f'    a: "{a}"']
    return "\n".join(L) + "\n---"


def main():
    summary = {"rewritten": [], "skipped": [], "errors": []}
    for slug in SLUGS:
        raw = git_raw(slug)
        meta, body = parse(raw)
        if slug in FAQS:
            meta["faq"] = FAQS[slug]
        elif bad_faq(meta.get("faq", [])):
            meta["faq"] = FAQS.get(slug, meta.get("faq", []))

        if slug in ADDENDA and ADDENDA[slug].get("replace"):
            body = ADDENDA[slug]["replace"]
        else:
            body = strip_wave2(body)
            if slug in ADDENDA:
                add = ADDENDA[slug].get("append", "")
                if add and add not in body:
                    body = body + "\n\n" + add

        while wc(body) < TARGET and slug in ADDENDA:
            pad = ADDENDA[slug].get("pad", "")
            if not pad or pad in body:
                break
            body += "\n\n" + pad

        content = fm(meta) + "\n\n" + body.strip() + "\n"
        bw = wc(content.split("---", 2)[2])
        if bw < TARGET:
            summary["errors"].append({"slug": slug, "words": bw})
            continue
        (BLOG / slug + ".md").write_text(content) if False else (BLOG / f"{slug}.md").write_text(content)
        summary["rewritten"].append({"slug": slug, "words": bw})

    (ROOT / "scripts/exec7_rewrite_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
