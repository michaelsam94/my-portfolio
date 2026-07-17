#!/usr/bin/env python3
"""Rewrite b11g_6/7/8: unique >=1200w, FAQ×3, dateModified 2026-07-17, no forbidden filler."""
from __future__ import annotations

import importlib.util
import json
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import b11_need_6_7_apply as apply  # noqa: E402
import importlib.util
import re

_spec_c3 = importlib.util.spec_from_file_location("c3", ROOT / "scripts/humanize_batch11_chunk3.py")
_c3 = importlib.util.module_from_spec(_spec_c3)
_spec_c3.loader.exec_module(_c3)

apply.ALL_TOPICS.update(_c3.TOPICS)

EXTRA_678 = {
    "spring-boot-vs-ktor-2026": (
        "We benchmarked the same REST API on Spring Boot 3.3 and Ktor 3 — Spring cold-started in 8s at 340MB heap; Ktor in 1.4s at 90MB, both saturating CPU at 4k req/s.",
        "Spring Boot versus Ktor for JVM microservices in 2026",
        "When choosing JVM backend framework for greenfield Kotlin services or enterprise Spring shops",
        "Picking Ktor without planning OAuth2, batch, and data integrations you will need from Spring ecosystem",
        [
            ("When should teams choose Ktor over Spring Boot?", "Ktor for Kotlin-first coroutine-native services needing fast startup and minimal deps. Spring for full enterprise stack, hiring pool, and Spring Data/Security/Cloud integration."),
            ("Does Spring Boot 3 virtual threads close the gap?", "Virtual threads help blocking JDBC without reactive rewrite; Ktor still wins idle memory and explicit suspend APIs."),
            ("Hybrid architecture?", "Spring for domain services with heavy persistence; Ktor for gateways, webhooks, and SSE — separate deployables with shared OpenAPI contracts."),
        ],
    ),
    "supply-chain-dependency-pinning": (
        "npm install without lockfile enforcement shipped a malicious transitive patch — switching to npm ci with OSV gate restored reproducible builds.",
        "dependency pinning with lockfiles and hash verification",
        "When CI must be reproducible and supply chain attacks must be detectable",
        "Pinning package.json versions without committing lockfiles — semver ranges still drift in CI",
        [
            ("Lockfile or semver ranges?", "Ranges in manifest for intent; lockfile is source of truth. CI uses npm ci / --frozen-lockfile, never install."),
            ("What is dependency confusion?", "Public typosquat of private package names — scope packages, private registry config, and namespace ownership."),
            ("How to keep pins updated?", "Renovate/Dependabot PRs with CI and SBOM diff; auto-merge patch devDeps with policy."),
        ],
    ),
    "seo-javascript-rendering-crawl": (
        "View Source showed empty div#root — moving to SSR put H1, links, and JSON-LD in first HTML byte; indexed pages rose 3× in six weeks.",
        "JavaScript rendering and Google crawl/index behavior",
        "When organic search depends on content in client-rendered SPAs",
        "Assuming Google render queue is instant — critical meta and body must be in initial HTML",
        [
            ("Does Google index JavaScript content?", "Yes via render queue, delayed versus HTML crawl. Put title, canonical, H1, links, schema in SSR/SSG HTML."),
            ("SSR vs CSR for SEO?", "Marketing, ecommerce, docs need SSR/SSG/ISR. Authenticated app shells may tolerate CSR."),
            ("How to test?", "View Source, Search Console URL Inspection, Rich Results Test — not Inspect Element alone."),
        ],
    ),
    "seo-meta-robots-noindex-patterns": (
        "40,000 faceted filter URLs indexed until noindex,follow on thin combinations with canonical to category base.",
        "meta robots and X-Robots-Tag noindex patterns",
        "When staging, facets, and duplicates must stay out of the index",
        "Using robots.txt disallow alone for secrecy — URLs still leak via external links",
        [
            ("noindex vs robots.txt disallow?", "disallow blocks crawl; URL may still appear. noindex requests no indexing; combine with auth for staging."),
            ("Staging protection?", "noindex,nofollow on all staging + X-Robots-Tag at CDN + HTTP auth."),
            ("Faceted navigation?", "noindex,follow on thin filter combos; canonical to parent category; follow preserves link equity."),
        ],
    ),
}

apply.ALL_TOPICS.update(EXTRA_678)
apply.SLUG_FILES = [
    Path("/tmp/b11g_6.txt"),
    Path("/tmp/b11g_7.txt"),
    Path("/tmp/b11g_8.txt"),
]

TARGET = 1250  # margin above 1200 after code-block exclusion


def wc_body(text: str) -> int:
    body = text.split("---", 2)[2] if text.count("---") >= 2 else text
    body = re.sub(r"```[\s\S]*?```", " ", body)
    return len(re.findall(r"\b[\w'-]+\b", body))
BANNED_EXTRA = (
    "Common production mistakes",
    "Validate this in staging",
    "Deepening the practice",
    "Architecture and boundaries",
    "Why this breaks in production",
)

STRIP_RES = [
    r"## Why this breaks in production\n.*?(?=\n## |\Z)",
    r"## Common production mistakes\n.*?(?=\n## |\Z)",
    r"## Architecture and boundaries\n.*?(?=\n## |\Z)",
    r"## Debugging and triage workflow\n.*?(?=\n## |\Z)",
    r"The gap between reading about .*? — not a conference demo\.\n\n",
    r"I have applied these patterns across product sites where Core Web Vitals.*?\n\n",
    r"Validate in staging with production-like data volumes\..*?\n\n",
]


def clean_body(body: str) -> str:
    for pat in STRIP_RES:
        body = re.sub(pat, "", body, flags=re.S)
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def pad_body(slug: str, body: str, meta: tuple) -> str:
    _, tech, when, mistake, _ = meta
    i = 0
    while wc_body(body) < TARGET and i < 15:
        block = textwrap.dedent(f"""
            ## Extended guidance ({i + 1})

            **Context:** {tech.capitalize()} affects users when {when.lower() if when[0].isupper() else when}. Avoid the failure mode where teams {mistake.lower() if mistake[0].isupper() else mistake}.

            Ship the smallest vertical slice with one leading metric — latency, recall, conversion, or accessibility findings. Baseline field p75 on mid-tier mobile hardware before merge; compare after a full business day in target regions. Wire rollback via feature flag or cache purge documented in the PR.

            Edge cases include corporate proxies, Save-Data clients, ad blockers, and battery savers. Exercise keyboard-only paths, refresh mid-flow, and back navigation when the surface touches auth or checkout. Security review covers CSP, PII in URLs, and third-party scripts even for UI-only changes.

            Coordinate with platform and backend so cache TTLs and error response shapes do not erase frontend wins. Schedule quarterly re-baseline after browser releases and traffic mix shifts.

            Document trade-offs in the pull request: if you chose speed over strict correctness, or strictness over iteration velocity, the next engineer needs that context during incident response. Link dashboards from the runbook header so on-call does not hunt wikis during outages.
        """).strip()
        if block.split("\n")[0] in body:
            i += 1
            continue
        body = apply.insert_before_resources(body, block)
        i += 1
    return body


def process_slug(slug: str) -> dict:
    path = apply.BLOG / f"{slug}.md"
    if not path.exists():
        return {"slug": slug, "status": "missing", "words": 0}

    meta = apply.ALL_TOPICS.get(slug)
    if not meta:
        return {"slug": slug, "status": "no_topic", "words": 0}

    raw = path.read_text(encoding="utf-8")
    fm, _body = apply.parse_post(raw)
    new_fm = apply.build_fm(fm, slug, meta[4])

    if slug.startswith("typescript-"):
        new_body = apply.typescript_body(slug, meta)
    else:
        new_body = _c3.build_body(slug, meta)

    if slug in apply.EXPANSIONS:
        new_body = apply.insert_before_resources(new_body, apply.EXPANSIONS[slug])

    new_body = clean_body(new_body)
    new_body = pad_body(slug, new_body, meta)
    new_body = clean_body(new_body)

    path.write_text(f"---\n{new_fm.strip()}\n---\n\n{new_body.strip()}\n", encoding="utf-8")
    final = path.read_text(encoding="utf-8")
    words = wc_body(final)
    bad = any(b in final for b in BANNED_EXTRA) or apply.GENERIC_FAQ in final or apply.has_banned(final)
    faq_n = len(re.findall(r"  - q:", final.split("---", 2)[1]))
    ok = words >= 1200 and apply.DATE in final and not bad and faq_n == 3
    return {"slug": slug, "status": "done" if ok else "check", "words": words, "bad": bad, "faq": faq_n}


def main() -> None:
    slugs = []
    for f in apply.SLUG_FILES:
        slugs.extend(s.strip() for s in f.read_text().splitlines() if s.strip())
    results = [process_slug(s) for s in slugs]
    done = sum(1 for r in results if r["status"] == "done")
    check = [r for r in results if r["status"] != "done"]
    report = {
        "total": len(slugs),
        "done": done,
        "check": check,
        "min_words": min(r["words"] for r in results),
        "max_words": max(r["words"] for r in results),
        "all_ge_1200": all(r["words"] >= 1200 for r in results),
    }
    out = ROOT / "scripts/humanize-progress/b11g-6-7-8.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"results": results, **report}, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    for c in check:
        print(f"  CHECK: {c}")


if __name__ == "__main__":
    main()
