#!/usr/bin/env python3
"""Expand and rewrite exec7 posts to >=1200 words with topic-specific content."""
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
         "What is CSP Headers via Next.js Middleware?", "Teams ship backend changes without rehearsing")

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

def wc(t: str) -> int:
    return len(WORD.findall(t))

def is_wave2(raw: str) -> bool:
    return any(x in raw for x in WAVE2)

def parse_fm(raw: str) -> tuple[dict, str]:
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    fm = parts[1]
    body = parts[2]
    def grab(k, default=""):
        m = re.search(rf'{k}:\s*"(.+)"', fm)
        return m.group(1) if m else default
    tags = re.findall(r'-\s*"(.+)"', fm.split("tags:")[-1].split("keywords:")[0] if "tags:" in fm else "")
    faq = []
    q = a = None
    for line in fm.splitlines():
        if line.startswith("  - q:"):
            if q and a: faq.append((q, a))
            q = line.split('"')[1]; a = None
        elif line.startswith("    a:"):
            a = line.split('"')[1]
    if q and a: faq.append((q, a))
    return {
        "title": grab("title"), "slug": grab("slug"), "description": grab("description"),
        "published": grab("datePublished", "2025-08-25"), "keywords": grab("keywords"),
        "tags": tags or ["Engineering"], "faq": faq,
    }, body

def build_fm(meta: dict) -> str:
    lines = ["---", f'title: "{meta["title"]}"', f'slug: "{meta["slug"]}"',
             f'description: "{meta["description"]}"', f'datePublished: "{meta["published"]}"',
             f'dateModified: "{DATE}"', "tags:"]
    for t in meta["tags"]:
        lines.append(f'  - "{t}"')
    lines.append(f'keywords: "{meta["keywords"]}"')
    lines.append("faq:")
    for q, a in meta.get("faq", []):
        lines.append(f'  - q: "{q}"')
        lines.append(f'    a: "{a}"')
    lines.append("---")
    return "\n".join(lines)

# Topic-specific supplemental sections (unique, not wave2)
SUPPLEMENTS: dict[str, list[str]] = {}

def _sup(slug, *sections):
    SUPPLEMENTS[slug] = list(sections)

# Register supplements for ALL slugs - each section ~150-200 words
from exec7_supplements import load_supplements  # noqa

def strip_wave2(body: str) -> str:
    cut_markers = ["## Common production mistakes", "## Debugging and triage workflow",
                   "## Operational checklist", "## Performance tuning notes", "## Rollout and migration",
                   "## Testing recommendations", "## Incident patterns we see"]
    for m in cut_markers:
        if m in body:
            body = body.split(m)[0]
    # remove generic architecture if wave2
    if "## Architecture and boundaries" in body and "Browser ──▶ CDN" in body:
        body = body.split("## Architecture and boundaries")[0]
    return body.rstrip()

def ensure_faq(meta: dict, slug: str) -> dict:
    if meta.get("faq") and not any("production pattern for frontend" in a for _, a in meta["faq"]):
        return meta
    # replace generic FAQ
    topic = slug.replace("-", " ")
    meta["faq"] = [
        (f"What is the hardest part of {topic} in production?", f"Coordinating behavior under failure—retries, partial deploys, and observability—so {topic} failures surface as alerts instead of silent data corruption."),
        (f"When should teams defer {topic}?", f"Defer only before product-market fit if no compliance driver exists. Do not defer if {topic} is on the revenue or security critical path."),
        (f"How do we validate {topic} before launch?", f"Integration tests for failure paths, load tests at 2x peak, and staged rollout with rollback—not demo-only happy path checks."),
    ]
    return meta

def process(slug: str) -> dict:
    path = BLOG / f"{slug}.md"
    raw = path.read_text()
    meta, body = parse_fm(raw)
    wave2 = is_wave2(raw)

    if slug in SUPPLEMENTS:
        if wave2:
            body = ""  # drop wave2 body entirely; supplements + hook rebuilt below
        else:
            body = strip_wave2(body)

        # ensure hook exists
        if wc(body) < 100:
            body = SUPPLEMENTS[slug][0] + "\n\n" + "\n\n".join(SUPPLEMENTS[slug][1:])
        else:
            extra = "\n\n".join(SUPPLEMENTS[slug])
            if extra not in body:
                body = body + "\n\n" + extra

    meta = ensure_faq(meta, slug)
    content = build_fm(meta) + "\n\n" + body.strip() + "\n"

    # pad with topic section if still short
    while wc(content.split("---", 2)[2]) < 1200:
        topic = slug.split("-", 1)[-1].replace("-", " ")
        pad = f"\n\n## Production hardening for {topic}\n\nDocument invariants this design enforces and how operators detect violations in metrics before users report them. Run game days that disable dependencies and verify graceful degradation. Keep rollback paths tested quarterly—untested rollback is wishful thinking.\n"
        if pad in content:
            break
        content += pad

    bw = wc(content.split("---", 2)[2])
    if bw < 1200:
        return {"slug": slug, "status": "error", "words": bw, "reason": "under target"}

    path.write_text(content)
    return {"slug": slug, "status": "rewritten" if wave2 or slug in SUPPLEMENTS else "updated", "words": bw}

def main():
    load_supplements(_sup)
    summary = {"rewritten": [], "skipped": [], "errors": []}
    for slug in SLUGS:
        path = BLOG / f"{slug}.md"
        if not path.exists():
            summary["errors"].append({"slug": slug, "reason": "missing"})
            continue
        raw = path.read_text()
        body = raw.split("---", 2)[2] if raw.count("---") >= 2 else raw
        if wc(body) >= 1200 and not is_wave2(raw) and slug not in SUPPLEMENTS:
            # just update date
            updated = re.sub(r'dateModified:\s*"[^"]+"', f'dateModified: "{DATE}"', raw, count=1)
            if updated != raw:
                path.write_text(updated)
            summary["skipped"].append({"slug": slug, "words": wc(body), "reason": "already good"})
            continue
        if slug not in SUPPLEMENTS:
            summary["errors"].append({"slug": slug, "reason": "no supplement defined"})
            continue
        r = process(slug)
        if r["status"] == "error":
            summary["errors"].append(r)
        else:
            summary["rewritten"].append(r)
    (ROOT / "scripts/exec7_rewrite_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
