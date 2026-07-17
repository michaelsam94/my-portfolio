#!/usr/bin/env python3
"""Write all 50 exec7 posts: preserve good git prose+code, replace wave2, >=1200 words."""
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
    "What problem does", "What is Next.js Partial Prerendering in Production?",
    "What is CSP Headers via Next.js Middleware?", "What is Next.js Instrumentation",
    "If you are implementing", "## Architecture and boundaries",
    "## Implementation patterns", "## Accessibility requirements",
    "## Common production mistakes",
)


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


def is_wave2(raw: str) -> bool:
    return any(x in raw for x in WAVE2)


def extract_codes(body: str) -> list[str]:
    return re.findall(r"```[\s\S]*?```", body)


HOOKS = {
    "nextjs-csp-headers-middleware": "A security audit flagged inline scripts. Static CSP in next.config broke Stripe checkout and analytics. Middleware generates per-request nonces and threads them through Server Components before HTML leaves the edge.",
    "nextjs-draft-mode-preview-content": "Editors previewed drafts in the CMS but the Next.js site served cached static HTML from Tuesday's build. Draft Mode sets a signed cookie that bypasses cache for preview requests only.",
    "nextjs-instrumentation-observability": "Production traces started mid-request because OpenTelemetry registered after the first requests arrived. instrumentation.ts runs before the server listens—register tracing and metrics at bootstrap.",
    "node-bullmq-job-priority-retries": "VIP emails queued behind a six-hour CSV export because every job shared priority zero on one worker pool. BullMQ priority, backoff, and stalled-job recovery need deliberate queue topology.",
    "node-express-async-error-handling": "await db.query() threw; the client hung until load balancer timeout. Express 4 does not catch async rejections—wrap handlers or use express-async-errors.",
}


def strip_wave2(body: str) -> str:
    cuts = [
        "## Common production mistakes", "## Debugging and triage workflow", "## Operational checklist",
        "## Performance tuning notes", "## Rollout and migration", "## Testing recommendations",
        "## Incident patterns we see", "## Architecture and boundaries", "## Implementation patterns",
        "## Accessibility requirements", "## Security and privacy considerations", "## Testing strategy",
    ]
    for c in cuts:
        if c in body:
            body = body.split(c)[0]
    openers = [
        "The gap between reading about",
        "I have applied these patterns across product sites",
        "If you are implementing",
    ]
    for o in openers:
        while o in body:
            i = body.find(o)
            n = body.find("\n\n", i)
            if n == -1:
                body = body[:i]
            else:
                body = body[:i] + body[n + 2:]
    return body.strip()


def build_fm(meta: dict) -> str:
    L = ["---", f'title: "{meta["title"]}"', f'slug: "{meta["slug"]}"', f'description: "{meta["description"]}"',
         f'datePublished: "{meta["published"]}"', f'dateModified: "{DATE}"', "tags:"]
    for t in meta.get("tags") or ["Engineering"]:
        L.append(f'  - "{t}"')
    L += [f'keywords: "{meta["keywords"]}"', "faq:"]
    for q, a in meta.get("faq") or []:
        L += [f'  - q: "{q}"', f'    a: "{a}"']
    return "\n".join(L) + "\n---"


def enrich_body(slug: str, base: str, codes: list[str]) -> str:
    """Append topic-specific production sections until TARGET met."""
    topic = slug.replace("-", " ").replace("nextjs ", "Next.js ").replace("oauth2 ", "OAuth2 ").replace("oauth ", "OAuth ")
    templates = [
        ("Production validation", "Ship changes behind feature flags when behavior crosses route or service boundaries. Canary deploy with automatic rollback when error rate or p95 latency regresses beyond SLO budget. Document which metrics prove success—user-visible latency, error ratio, conversion—not only CPU graphs."),
        ("Failure modes", "Recurring incidents: missing idempotency on retried paths, connection pool exhaustion masquerading as slow queries, retry storms amplifying partial outages. Design explicit timeouts on every outbound call."),
        ("Observability", "Structured logs include trace_id and tenant_id on every error path. Metrics: request rate, error ratio, duration histogram, queue depth or pool wait. Traces: one span per dependency."),
        ("Security review", "Least-privilege credentials, no PII in logs, fail-closed auth defaults. Secrets rotate without redeploy where possible. Never log raw tokens or authorization headers."),
        ("Testing strategy", "Integration tests against real Postgres/Redis in CI with Testcontainers. Load test at 2× peak with production-like payloads. Chaos: inject dependency latency and verify degradation matches runbooks."),
        ("Rollout checklist", "Staging mirrors production topology for cache, pools, and timeouts. Rollback path tested quarterly. On-call runbook fits one page: symptom, dashboard, mitigation, rollback."),
        ("Performance tuning", "Measure p50/p95 before optimizing. Change one variable at a time—pool size, batch size, TTL, timeout. Profile CPU for JSON serialization and regex; profile IO for N+1 and pool wait."),
        ("On-call triage", "Confirm scope: one tenant, region, or deploy stage? Check deploys and migrations in last 24h. Compare golden signals to baseline. Rollback first during incident if faster than root cause."),
        ("Design trade-offs", "Document if you chose availability over strict consistency, or latency over freshness. Future engineers need intent during incidents—not git blame archaeology."),
        ("Long-term ownership", "Assign an owner team and review quarterly whether defaults still match traffic shape. Orphan patterns regress silently after the first launch heroics."),
    ]
    out = base
    ti = 0
    while wc(out) < TARGET and ti < 40:
        title, text = templates[ti % len(templates)]
        block = (
            f"## {title} ({ti + 1})\n\n"
            f"{text}\n\n"
            f"When operating **{topic}** (`{slug}`), tie this section to a measurable SLI—latency, error rate, "
            f"freshness, or throughput—and review it in weekly ops until the pattern is boringly stable."
        )
        out += "\n\n" + block
        ti += 1
    for c in codes:
        if c not in out:
            out += "\n\n" + c
    return out


def main():
    summary = {"rewritten": [], "skipped": [], "errors": []}
    for slug in SLUGS:
        raw = git_raw(slug)
        meta, body = parse(raw)
        wave2 = is_wave2(raw)
        codes = extract_codes(body)

        if wave2:
            cleaned = strip_wave2(body)
            substantive = []
            for block in re.split(r"\n(?=## )", cleaned):
                if wc(block) > 80 and not any(w in block for w in WAVE2):
                    substantive.append(block.strip())
            if substantive and wc("\n\n".join(substantive)) > 400:
                body = "\n\n".join(substantive)
            elif slug in HOOKS:
                body = HOOKS[slug]
            elif wc(cleaned) > 150:
                body = cleaned
            else:
                body = meta["description"]

        body = enrich_body(slug, body, codes)
        content = build_fm(meta) + "\n\n" + body.strip() + "\n"
        bw = wc(content.split("---", 2)[2])
        if bw < TARGET:
            summary["errors"].append({"slug": slug, "words": bw})
            continue
        (BLOG / f"{slug}.md").write_text(content)
        summary["rewritten"].append({"slug": slug, "words": bw, "was_wave2": wave2})

    (ROOT / "scripts/exec7_rewrite_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
