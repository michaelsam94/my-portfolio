#!/usr/bin/env python3
"""Final pass: write only when result >=1200 words, no banned, FAQx3; else keep best available."""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content/blog"
DATE = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")

BANNED = (
    "Validate this in staging", "If I were prioritizing", "Options compared honestly",
    "is a production pattern for frontend", "Teams ship without field measurement",
    "A concrete playbook for", "Additional depth", "Field note 1 (",
    "requires explicit ownership in production", "The gap between reading about",
    "Extend monitoring for", "## Supplement", "Architecture and boundaries",
    "When to prioritize", "Anti-pattern to avoid", "In production, debounce and throttle",
    "Quarterly re-baseline after browser",
)

EXTRA = {
    "web-performance-debounce-throttle-input": """
## Svelte and Solid cleanup

Debounced handlers must clear timers on component destroy — Svelte `destroy()` and Solid `onCleanup` — or timers fire after unmount causing state updates on torn-down trees.

## Micro-frontend search ownership

When header search and results live in separate federated bundles, debounce timer in one bundle does not cancel fetch started by another — centralize query state in shell application.""",
    "web-performance-breadcrumb-navigation-seo": """
## Log file 404 on crumb hrefs

Apache or CDN logs with Googlebot user-agent hitting 404 on category crumb URLs indicate stale CMS slug — fix data export not just React template.

## Storybook SEO guard

Design system Storybook includes `toJsonLd(crumbs)` helper test — designers cannot merge breadcrumb UI changes without matching structured data output.""",
    "web-performance-404-page-product-sites": """
## Marketing CMS link checker

Block email and landing page publish until CI HEAD-check passes for every href — one broken launch-day URL generates thousands of paid 404s.

## Cache-Control on 404 responses

Use short max-age so redirect fixes after deploy propagate within minutes, not hours behind CDN cache.""",
    "sec-dependency-audit-automation": """
## Monorepo per-package scans

Matrix CI runs audit in each workspace producing artifacts — root-only scan misses vulnerable transitive in unpublished packages.""",
    "serverless-event-driven-architecture": """
## Partial SQS batch failure

Return `batchItemFailures` from Lambda so one poison message does not retry entire batch of ten successfully processed records.""",
    "software-cqrs-event-sourcing-tradeoffs": """
## Snapshot cadence

Snapshot aggregates every N events or T minutes — balance replay time against snapshot storage growth.""",
    "software-domain-driven-design-strategic": """
## Event storming quarterly

Refresh context map after org restructure — stale boundaries mislead architects more than no map.""",
    "software-architecture-decision-records": """
## PR template ADR link

Require ADR number for persistence and messaging changes — reviewers verify decision context before code.""",
    "testing-unit-vs-integration-balance": """
## Contract tests at boundaries

Pact or similar at service edges replaces some integration tests — faster CI with same breaking-change detection.""",
    "timeseries-influxdb-vs-timescale": """
## Continuous aggregates refresh policy

Timescale refresh lag versus InfluxDB downsampling tasks — pick based on acceptable staleness for dashboards.""",
    "timeseries-prometheus-remote-write": """
## Remote write shard tuning

Too many shards increases cardinality labels on receiver — start conservative and scale with HA pair capacity.""",
}


def load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ex2 = load("ex2", "expand_batch11_chunk2.py")
r22 = load("r22", "_rewrite_22_expansions.py")
fr = load("fr", "b11_final_rewrite.py")
wp = load("wp", "b11s345_webperf_three.py")
p1 = load("p1", "_rewrite_22_content_p1.py")
p2 = load("p2", "_rewrite_22_content_p2.py")
R22 = {**p1.POSTS, **p2.POSTS}


def slugs() -> list[str]:
    out = []
    for f in ("/tmp/b11s_3.txt", "/tmp/b11s_4.txt", "/tmp/b11s_5.txt"):
        out.extend(line.strip() for line in open(f) if line.strip())
    return out


def wc(t: str) -> int:
    return len(WORD.findall(t))


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def git_raw(slug: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "show", f"HEAD:content/blog/{slug}.md"], text=True, cwd=ROOT
        )
    except subprocess.CalledProcessError:
        return None


def parse_fm(raw: str) -> dict:
    fm = raw.split("---", 2)[1]
    d: dict = {}
    for key in ("title", "description", "datePublished", "keywords"):
        m = re.search(rf'^{key}:\s*"([^"]*)"', fm, re.M)
        if m:
            d[key] = m.group(1)
    tags, on = [], False
    for line in fm.splitlines():
        if line.strip() == "tags:":
            on = True
            continue
        if on:
            if line.startswith("  - "):
                tags.append(line[4:].strip().strip('"').strip("'"))
            elif line.strip() and not line.startswith(" "):
                break
    if tags:
        d["tags"] = tags
    faqs, q, on = [], None, False
    for line in fm.splitlines():
        if line.strip() == "faq:":
            on = True
            continue
        if not on:
            continue
        if line.startswith("  - q:"):
            q = line.split('"')[1] if '"' in line else line.split(":", 1)[1].strip()
        elif line.startswith("    a:") and q:
            faqs.append((q, line.split('"')[1] if '"' in line else line.split(":", 1)[1].strip()))
            q = None
    d["faq"] = faqs[:3]
    return d


GENERIC = ("is a production pattern for frontend", "Teams ship without field measurement", "What is the main production risk")


def good_faq(faqs: list[tuple[str, str]]) -> bool:
    if len(faqs) < 3:
        return False
    blob = " ".join(q + a for q, a in faqs)
    return not any(g in blob for g in GENERIC)


def strip_body(body: str) -> str:
    paras = []
    for p in body.split("\n\n"):
        if any(b in p for b in BANNED):
            continue
        if p.strip().startswith("## Field note") or p.strip().startswith("## Supplement"):
            continue
        paras.append(p)
    return re.sub(r"\n{3,}", "\n\n", "\n\n".join(paras)).strip()


def banned(text: str) -> bool:
    return any(b in text for b in BANNED)


def expansions(slug: str) -> list[str]:
    out = []
    for src in (
        r22.EXPANSIONS.get(slug, ""),
        ex2.EXPANSIONS.get(slug, ""),
        fr.UNIQUE.get(slug, ""),
        EXTRA.get(slug, ""),
    ):
        if isinstance(src, str) and src.strip():
            out.append(src.strip())
    return out


def augment(body: str, slug: str) -> str:
    for e in expansions(slug):
        if e not in body:
            body = body.rstrip() + "\n\n" + e
    return body.strip()


def candidates(slug: str) -> list[str]:
    c = []
    if slug in wp.POSTS:
        c.append(strip_body(wp.POSTS[slug][1]))
    if slug in R22:
        c.append(strip_body(R22[slug][1].strip() + r22.EXPANSIONS.get(slug, "")))
    g = git_raw(slug)
    if g:
        c.append(strip_body(g.split("---", 2)[2]))
    cur = (BLOG / f"{slug}.md").read_text(encoding="utf-8")
    c.append(strip_body(cur.split("---", 2)[2]))
    return [augment(x, slug) for x in c if x.strip()]


def build_fm(meta: dict, slug: str) -> str:
    lines = [
        "---",
        f'title: "{esc(meta.get("title", slug))}"',
        f'slug: "{slug}"',
        f'description: "{esc(meta.get("description", ""))}"',
        f'datePublished: "{meta.get("datePublished", DATE)}"',
        f'dateModified: "{DATE}"',
        "tags:",
    ]
    for t in meta.get("tags", ["Engineering"]):
        lines.append(f'  - "{esc(t)}"')
    lines.append(f'keywords: "{esc(meta.get("keywords", slug))}"')
    lines.append("faq:")
    for q, a in meta.get("faq", [])[:3]:
        lines.append(f'  - q: "{esc(q)}"')
        lines.append(f'    a: "{esc(a)}"')
    lines.append("---")
    return "\n".join(lines)


def pick_meta(slug: str) -> dict:
    head, cur = git_raw(slug), (BLOG / f"{slug}.md").read_text(encoding="utf-8")
    meta = parse_fm(head or cur)
    if slug in wp.POSTS:
        meta = {**meta, **wp.POSTS[slug][0]}
    elif slug in R22:
        meta = {**meta, **R22[slug][0]}
    if not good_faq(meta.get("faq", [])):
        for src in (cur, head or ""):
            if not src:
                continue
            f2 = parse_fm(src).get("faq", [])
            if good_faq(f2):
                meta["faq"] = f2
                break
    return meta


def score(body: str) -> tuple[int, int]:
    """Higher is better: (ok_flag, word_count)"""
    ok = 1 if (wc(body) >= TARGET and not banned(body)) else 0
    return (ok, wc(body))


def main() -> int:
    results = []
    for slug in slugs():
        path = BLOG / f"{slug}.md"
        cur_raw = path.read_text(encoding="utf-8")
        cur_body = strip_body(cur_raw.split("---", 2)[2])
        cur_score = score(cur_body)

        best_body = cur_body
        best_score = cur_score
        for cand in candidates(slug):
            sc = score(cand)
            if sc > best_score:
                best_body, best_score = cand, sc

        meta = pick_meta(slug)
        ok = best_score[0] == 1 and len(meta.get("faq", [])) >= 3
        if ok:
            path.write_text(build_fm(meta, slug) + "\n\n" + best_body + "\n", encoding="utf-8")
        results.append((slug, best_score[1], ok))

    passed = sum(1 for _, _, ok in results if ok)
    for slug, w, ok in sorted(results):
        print(f"{'OK' if ok else 'NO'}\t{w}\t{slug}")
    print(f"\nPass: {passed}/{len(results)}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
