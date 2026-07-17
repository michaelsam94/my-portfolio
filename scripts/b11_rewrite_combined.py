#!/usr/bin/env python3
"""Humanize + deep-dive rewrite for b11_w9, b11_w10, b11_w11 — no boilerplate."""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
SLUG_FILES = [Path("/tmp/b11_w9.txt"), Path("/tmp/b11_w10.txt"), Path("/tmp/b11_w11.txt")]
TARGET = 1200
TODAY = "2026-07-17"
WORD_PAT = re.compile(r"\b[\w'-]+\b")

BANNED = (
    "Review 1: teams that treat",
    "assumptions age faster than code",
    "Operating ",
    "after traffic shifts",
    "Field notes (",
    "Validate this in staging",
    "Production engineering for",
)

spec = importlib.util.spec_from_file_location("hb", ROOT / "scripts" / "humanize_batch11_chunk3.py")
hb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hb)

# Import article bodies
sys.path.insert(0, str(ROOT / "scripts"))
from b11_article_bodies import BODIES  # noqa: E402


def wc(text: str) -> int:
    return len(WORD_PAT.findall(text))


def has_boilerplate(text: str) -> bool:
    return any(b in text for b in BANNED)


def all_slugs() -> list[str]:
    slugs = []
    for f in SLUG_FILES:
        slugs.extend(s.strip() for s in f.read_text().splitlines() if s.strip())
    return slugs


def write_post(slug: str, body: str) -> int:
    path = BLOG / f"{slug}.md"
    raw = path.read_text(encoding="utf-8")
    existing = hb.parse_fm(raw)
    existing["slug"] = slug
    meta = hb.TOPICS[slug]
    fm = hb.build_frontmatter(existing, meta[4])
    path.write_text(fm + "\n\n" + body.strip() + "\n", encoding="utf-8")
    return wc(body)


def main() -> None:
    slugs = all_slugs()
    results = []
    for slug in slugs:
        if slug not in hb.TOPICS:
            results.append({"slug": slug, "status": "no_topic", "words": 0})
            continue
        if slug not in BODIES:
            results.append({"slug": slug, "status": "no_body", "words": 0})
            continue
        body = BODIES[slug]
        words = wc(body)
        if words < TARGET:
            results.append({"slug": slug, "status": "under_target", "words": words})
            continue
        count = write_post(slug, body)
        results.append({"slug": slug, "status": "done", "words": count})

    done = sum(1 for r in results if r["status"] == "done")
    failed = [r for r in results if r["status"] != "done"]
    samples = sorted([r for r in results if r["status"] == "done"], key=lambda x: -x["words"])[:3]
    report = {"done": done, "total": len(slugs), "failed": failed, "samples": samples}
    out = ROOT / "scripts" / "humanize-progress" / "b11-w9-w10-w11.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"done": done, "total": len(slugs), "failed_count": len(failed), "samples": samples}, indent=2))
    if failed:
        for f in failed:
            print(f"  FAIL: {f['slug']} ({f['status']}, {f['words']} words)")


if __name__ == "__main__":
    main()
