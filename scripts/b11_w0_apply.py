#!/usr/bin/env python3
"""Apply humanized rewrites for /tmp/b11_w0.txt slugs."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content/blog"
SLUG_FILE = Path("/tmp/b11_w0.txt")
DATE = "2026-07-17"
WORD = re.compile(r"\b[\w'-]+\b")
TARGET = 1200

# Import bodies from companion module
from b11_w0_bodies import POSTS  # noqa: E402


def wc(text: str) -> int:
    return len(WORD.findall(text))


def parse_fm(raw: str) -> dict:
    parts = raw.split("---", 2)
    fm = parts[1]
    d: dict = {"slug": ""}
    for line in fm.splitlines():
        if line.startswith("title:"):
            d["title"] = line.split(":", 1)[1].strip().strip('"')
        elif line.startswith("slug:"):
            d["slug"] = line.split(":", 1)[1].strip().strip('"')
        elif line.startswith("description:"):
            d["description"] = line.split(":", 1)[1].strip().strip('"')
        elif line.startswith("datePublished:"):
            d["datePublished"] = line.split(":", 1)[1].strip().strip('"')
        elif line.startswith("tags:"):
            d["tags"] = []
        elif line.strip().startswith("- ") and "tags" in d and "keywords" not in d:
            d.setdefault("tags", []).append(line.strip()[2:].strip('"'))
        elif line.startswith("keywords:"):
            d["keywords"] = line.split(":", 1)[1].strip().strip('"')
    return d


def build_fm(meta: dict, faqs: list[tuple[str, str]]) -> str:
    lines = [
        "---",
        f'title: "{meta["title"]}"',
        f'slug: "{meta["slug"]}"',
        f'description: "{meta["description"]}"',
        f'datePublished: "{meta.get("datePublished", "2026-01-01")}"',
        f'dateModified: "{DATE}"',
        "tags:",
    ]
    for t in meta.get("tags", ["Engineering"]):
        lines.append(f'  - "{t}"')
    lines.append(f'keywords: "{meta.get("keywords", "")}"')
    lines.append("faq:")
    for q, a in faqs:
        lines.append(f'  - q: "{q}"')
        lines.append(f'    a: "{a}"')
    lines.append("---")
    return "\n".join(lines)


def main() -> None:
    slugs = [s.strip() for s in SLUG_FILE.read_text().splitlines() if s.strip()]
    results = []
    for slug in slugs:
        if slug not in POSTS:
            results.append({"slug": slug, "status": "missing_body", "words": 0})
            continue
        faqs, body = POSTS[slug]
        path = BLOG / f"{slug}.md"
        meta = parse_fm(path.read_text(encoding="utf-8")) if path.exists() else {"slug": slug, "title": slug}
        meta["slug"] = slug
        fm = build_fm(meta, faqs)
        path.write_text(f"{fm}\n\n{body.strip()}\n", encoding="utf-8")
        w = wc(body)
        results.append({"slug": slug, "status": "done" if w >= TARGET else "under", "words": w})
    done = sum(1 for r in results if r["status"] == "done")
    samples = sorted([r for r in results if r["words"] >= TARGET], key=lambda x: -x["words"])[:3]
    out = {"done": done, "total": len(slugs), "samples": samples, "results": results}
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
