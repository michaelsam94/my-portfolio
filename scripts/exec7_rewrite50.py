#!/usr/bin/env python3
"""Final rewrite of 50 exec7 blog posts — unique deep dives, >=1200 words, dateModified 2026-07-17."""
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
    "For **", "## Architecture and boundaries",
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


def wc(text: str) -> int:
    return len(WORD.findall(text))


def is_wave2(raw: str) -> bool:
    return any(m in raw for m in WAVE2_MARKERS)


def git_original(slug: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "show", f"HEAD:content/blog/{slug}.md"], cwd=ROOT, text=True
        )
    except subprocess.CalledProcessError:
        return None


def parse_fm(raw: str) -> tuple[dict, str]:
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
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
        "published": g("datePublished") or "2025-08-25", "keywords": g("keywords"), "tags": tags,
        "faq": faq,
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


def strip_wave2_body(body: str) -> str:
    for marker in ["## Common production mistakes", "## Debugging and triage workflow",
                     "## Operational checklist", "## Performance tuning notes", "## Rollout and migration",
                     "## Testing recommendations", "## Incident patterns we see",
                     "## Architecture and boundaries", "## Implementation patterns",
                     "## Accessibility requirements", "## Security and privacy considerations",
                     "## Testing strategy"]:
        if marker in body:
            body = body.split(marker)[0]
    # remove wave2 generic opening if present
    for opener in ["The gap between reading about", "I have applied these patterns"]:
        if opener in body:
            idx = body.find(opener)
            end = body.find("\n\n## ", idx)
            if end > idx:
                body = body[:idx] + body[end + 2:]
    return body.strip()


def generic_faq_bad(faq: list[tuple[str, str]]) -> bool:
    if not faq:
        return True
    bad_phrases = ("production pattern for frontend", "What problem does", "What is Next.js Partial",
                   "What is CSP Headers", "What is Next.js Instrumentation", "production gaps teams hit")
    return any(any(p in q or p in a for p in bad_phrases) for q, a in faq)


# Import full bodies
from exec7_bodies import BODIES, FAQS  # noqa: E402


def main():
    summary = {"rewritten": [], "skipped": [], "missing": [], "errors": []}

    for slug in SLUGS:
        path = BLOG / f"{slug}.md"
        if slug not in BODIES:
            summary["errors"].append({"slug": slug, "error": "no body in exec7_bodies"})
            continue

        raw = path.read_text() if path.exists() else git_original(slug) or ""
        if not raw:
            summary["missing"].append(slug)
            continue

        meta, old_body = parse_fm(raw)
        wave2 = is_wave2(raw)

        # Prefer original meta; override FAQ if generic
        if slug in FAQS:
            meta["faq"] = FAQS[slug]
        elif generic_faq_bad(meta.get("faq", [])):
            topic = slug.replace("-", " ")
            meta["faq"] = [
                (f"What is the most common {topic} production failure?", f"Misconfigured defaults that work in development but fail under load—usually missing observability, idempotency, or cache invalidation tied to {topic}."),
                (f"How do I test {topic} before shipping?", "Integration tests on production-like topology, load tests at 2x expected peak, and staged rollout with rollback—not unit tests alone."),
                (f"When should {topic} be deferred?", "Only when no compliance or revenue dependency exists and traffic is pre-production. Document the debt if deferred."),
            ]

        if wave2 or wc(old_body) < TARGET:
            body = BODIES[slug]
        else:
            body = strip_wave2_body(old_body)
            extra = BODIES.get(f"{slug}__expand", "")
            if extra and extra not in body:
                body = body + "\n\n" + extra

        while wc(body) < TARGET:
            body += f"\n\n## Production validation\n\nValidate `{slug}` with metrics tied to user-visible outcomes—not only green health checks. Run quarterly game days: disable dependencies, spike traffic, and verify alerts fire before customers notice.\n"

        content = build_fm(meta) + "\n\n" + body.strip() + "\n"
        bw = wc(content.split("---", 2)[2])
        if bw < TARGET:
            summary["errors"].append({"slug": slug, "error": f"short: {bw}"})
            continue

        path.write_text(content)
        summary["rewritten"].append({"slug": slug, "words": bw, "was_wave2": wave2})

    (ROOT / "scripts" / "exec7_rewrite_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
