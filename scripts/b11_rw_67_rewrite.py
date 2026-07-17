#!/usr/bin/env python3
"""Rewrite b11_rw_6 + b11_rw_7 slugs: unique ≥1200-word deep dives, topic FAQ×3, no boilerplate."""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
SLUG_FILES = [Path("/tmp/b11_rw_6.txt"), Path("/tmp/b11_rw_7.txt")]
DATE = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")

BANNED = (
    "Architecture and boundaries",
    "Regarding **",
    "is a production pattern for frontend",
    "The gap between reading about",
    "I have applied these patterns across product sites",
    "Common production mistakes",
    "Debugging and triage workflow",
    "Accessibility requirements",
    "Security and privacy considerations",
    "Testing strategy",
    "Operating ",
    "after traffic shifts",
    "Field-validate on mid-tier Android",
    "Connect this section to the user-visible symptom",
    "Teams that skip this slice",
)

sys.path.insert(0, str(ROOT / "scripts"))
from b11_rw_67_bodies import BODIES, FAQS  # noqa: E402

spec = importlib.util.spec_from_file_location("hb", ROOT / "scripts/humanize_batch11_chunk3.py")
hb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hb)
spec2 = importlib.util.spec_from_file_location("w8", ROOT / "scripts/b11_w8_rewrite.py")
w8 = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(w8)
from b11_need_8_9_10_apply import NEED_8_TOPICS  # noqa: E402

EXTRA_TOPICS: dict[str, tuple] = {
    "seo-sitemap-dynamic-generation": (
        "Our sitemap listed fifty thousand URLs with lastmod set to generation time — Google stopped trusting the signal and crawl efficiency dropped on product pages that actually changed.",
        "dynamic sitemap generation for large apps",
        "When published URL sets change frequently and exceed static export limits",
        "Setting lastmod to Date.now() on every build regardless of content updated_at",
        [
            ("Dynamic vs static sitemap?", "Generate from CMS or database when URLs exceed a few thousand or change daily. Static files work for marketing sites; apps with user-generated or catalog content need dynamic generation at request or build time."),
            ("When to split sitemaps?", "Use a sitemap index when any single file exceeds 50,000 URLs or 50MB uncompressed. Split by locale, content type, or update frequency so high-churn sections do not invalidate stable URLs."),
            ("How should lastmod behave?", "Tie lastmod to real content updated_at from your database. False lastmod on every deploy erodes crawler trust in the entire sitemap — worse than omitting lastmod entirely."),
        ],
    ),
    "web-performance-attribution-reporting-api": (
        "Marketing lost cross-site conversion visibility when third-party cookies died — Attribution Reporting API with Privacy Sandbox enrollment recovered aggregate campaign ROI without fingerprinting users.",
        "Attribution Reporting API for privacy-preserving marketing measurement",
        "When cookie-based attribution breaks and you need aggregate conversion data under consent constraints",
        "Loading attribution scripts synchronously in head without consent gating or understanding noise thresholds",
        [
            ("What does Attribution Reporting API measure?", "Cross-site and same-site conversions with privacy-preserving aggregation — click-through and view-through attribution with configurable lookback windows and noise for small cohorts."),
            ("How does it interact with consent mode?", "Tag firing and attribution registration must respect consent state. Load measurement scripts only after analytics consent; document behavior when consent is denied."),
            ("When is aggregate data too noisy?", "Small conversion volumes get randomized noise. Campaigns below platform thresholds need longer windows or server-side first-party measurement — not raw API counts alone."),
        ],
    ),
    "web-performance-brotli-gzip-compression": (
        "Switching static assets to Brotli level 11 on the origin spiked CPU and slowed TTFB — precompressing at level 5 at build time and serving brotli_static from nginx cut bytes 28% without origin melt.",
        "Brotli vs gzip compression strategy for web assets",
        "When text assets (HTML, CSS, JS, JSON, SVG) dominate transfer size on slow networks",
        "Using maximum Brotli level on dynamic compression at request time instead of precompressed static files",
        [
            ("Brotli or gzip for all assets?", "Brotli for precompressed static text assets; gzip fallback via Accept-Encoding negotiation. Images and video are already compressed — do not double-compress binary formats."),
            ("What Brotli level for build-time?", "Levels 4–6 balance ratio and encode speed for CI. Level 11 is for offline compression only — never on the hot request path."),
            ("How to verify compression in production?", "curl -H 'Accept-Encoding: br' -I URL and check Content-Encoding. CDN dashboards show cache hit ratio by encoding — ensure Vary: Accept-Encoding is correct."),
        ],
    ),
    "seo-open-graph-twitter-cards": (
        "Slack previews showed our default logo on every blog post until we added route-specific og:image at 1200×630 — social referral CTR rose 22% in the first month.",
        "Open Graph and Twitter Card optimization for social previews",
        "When organic social or messaging apps drive meaningful referral traffic",
        "Relying on a single site-wide og:image or wrong dimensions that platforms crop unpredictably",
        [
            ("Required Open Graph tags?", "og:title, og:description, og:image (absolute URL), og:url, og:type — at minimum. twitter:card (summary_large_image) and twitter:image for X previews."),
            ("What og:image size?", "1200×630 px for summary_large_image. Keep important content in center safe zone — LinkedIn and Slack crop differently."),
            ("Dynamic OG for SPAs?", "Generate per-route OG tags server-side or via edge middleware. Client-only React Helmet runs too late for crawlers that do not execute JavaScript."),
        ],
    ),
}

ALL_TOPICS = {**NEED_8_TOPICS, **w8.W8_TOPICS, **hb.TOPICS, **EXTRA_TOPICS}


def wc(t: str) -> int:
    return len(WORD.findall(t))


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def parse_fm(raw: str) -> str:
    return raw.split("---", 2)[1]


def extract_field(fm: str, key: str) -> str:
    m = re.search(rf'^{key}:\s*"([^"]*)"', fm, re.M)
    return m.group(1) if m else ""


def extract_tags(fm: str) -> list[str]:
    tags, on = [], False
    for line in fm.splitlines():
        if line.strip() == "tags:":
            on = True
            continue
        if on:
            if line.startswith("  - "):
                tags.append(line[4:].strip().strip('"'))
            elif line.strip() and not line.startswith(" "):
                break
    return tags


def build_fm(slug: str, old_fm: str, faqs: list[tuple[str, str]]) -> str:
    title = extract_field(old_fm, "title") or slug
    desc = extract_field(old_fm, "description") or ""
    pub = extract_field(old_fm, "datePublished") or DATE
    tags = extract_tags(old_fm) or ["Engineering"]
    kw = extract_field(old_fm, "keywords") or slug
    lines = [
        "---",
        f'title: "{esc(title)}"',
        f'slug: "{slug}"',
        f'description: "{esc(desc)}"',
        f'datePublished: "{pub}"',
        f'dateModified: "{DATE}"',
        "tags:",
    ]
    for t in tags:
        lines.append(f'  - "{esc(t)}"')
    lines.append(f'keywords: "{esc(kw)}"')
    lines.append("faq:")
    for q, a in faqs[:3]:
        lines.append(f'  - q: "{esc(q)}"')
        lines.append(f'    a: "{esc(a)}"')
    lines.append("---")
    return "\n".join(lines)


def get_faqs(slug: str) -> list[tuple[str, str]]:
    if slug in FAQS:
        return FAQS[slug]
    meta = ALL_TOPICS.get(slug)
    if meta:
        return meta[4]
    raise KeyError(f"No FAQs for {slug}")


def has_banned(text: str) -> bool:
    return any(b in text for b in BANNED)


def process(slug: str) -> dict:
    path = BLOG / f"{slug}.md"
    if not path.exists():
        return {"slug": slug, "status": "missing", "words": 0}
    if slug not in BODIES:
        return {"slug": slug, "status": "no_body", "words": 0}
    body = BODIES[slug].strip()
    words = wc(body)
    if words < TARGET:
        return {"slug": slug, "status": "under_target", "words": words}
    if has_banned(body):
        return {"slug": slug, "status": "banned_content", "words": words}
    old_fm = parse_fm(path.read_text(encoding="utf-8"))
    faqs = get_faqs(slug)
    fm = build_fm(slug, old_fm, faqs)
    path.write_text(fm + "\n\n" + body + "\n", encoding="utf-8")
    return {"slug": slug, "status": "done", "words": words}


def main() -> None:
    slugs = []
    for f in SLUG_FILES:
        slugs.extend(s.strip() for s in f.read_text().splitlines() if s.strip())
    results = [process(s) for s in slugs]
    done = [r for r in results if r["status"] == "done"]
    failed = [r for r in results if r["status"] != "done"]
    report = {"done": len(done), "total": len(slugs), "failed": failed, "word_counts": {r["slug"]: r["words"] for r in results}}
    out = ROOT / "scripts/humanize-progress/b11-rw-6-7.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"DONE={len(done)}/{len(slugs)}")
    for r in sorted(results, key=lambda x: x["slug"]):
        print(f"  {r['slug']}: {r['words']}w ({r['status']})")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
