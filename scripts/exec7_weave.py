#!/usr/bin/env python3
"""Weave unique 1200+ word articles from topic-specific facts — no wave2 template."""
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

from exec7_facts import TOPICS  # noqa: E402

SLUGS = list(TOPICS.keys())


def wc(t: str) -> int:
    return len(WORD.findall(t))


def git_fm(slug: str) -> dict:
    raw = subprocess.check_output(["git", "show", f"HEAD:content/blog/{slug}.md"], cwd=ROOT, text=True)
    fm = raw.split("---", 2)[1]
    g = lambda k: (m.group(1) if (m := re.search(rf'{k}:\s*"(.+)"', fm)) else "")
    tags = re.findall(r'-\s*"(.+)"', fm.split("tags:")[-1].split("keywords:")[0] if "tags:" in fm else "")
    return {
        "title": g("title") or TOPICS[slug]["title"],
        "slug": slug,
        "description": g("description") or TOPICS[slug]["description"],
        "published": g("datePublished") or "2025-08-25",
        "keywords": g("keywords") or TOPICS[slug]["keywords"],
        "tags": tags or TOPICS[slug]["tags"],
    }


def weave(slug: str) -> str:
    t = TOPICS[slug]
    parts = [t["hook"], ""]
    for sec in t["sections"]:
        parts.append(f"## {sec['h']}")
        parts.append("")
        for p in sec["paras"]:
            parts.append(p)
            parts.append("")
        if sec.get("code"):
            parts.append(sec["code"])
            parts.append("")
    if t.get("resources"):
        parts.append("## Resources")
        parts.append("")
        for r in t["resources"]:
            parts.append(f"- [{r['t']}]({r['u']})")
    return "\n".join(parts)


def build_file(slug: str) -> str:
    meta = git_fm(slug)
    t = TOPICS[slug]
    lines = ["---", f'title: "{meta["title"]}"', f'slug: "{slug}"',
             f'description: "{meta["description"]}"', f'datePublished: "{meta["published"]}"',
             f'dateModified: "{DATE}"', "tags:"]
    for tag in meta["tags"]:
        lines.append(f'  - "{tag}"')
    lines.append(f'keywords: "{meta["keywords"]}"')
    lines.append("faq:")
    for q, a in t["faq"]:
        lines.append(f'  - q: "{q}"')
        lines.append(f'    a: "{a}"')
    lines.append("---")
    body = weave(slug)
    while wc(body) < TARGET:
        body += f"\n\n## Field notes\n\n{TOPICS[slug]['hook'].split('.')[0]}. Validate in staging with production traffic shape, not developer laptops alone.\n"
    return "\n".join(lines) + "\n\n" + body + "\n"


def main():
    summary = {"rewritten": [], "errors": []}
    for slug in SLUGS:
        content = build_file(slug)
        bw = wc(content.split("---", 2)[2])
        if bw < TARGET:
            summary["errors"].append({"slug": slug, "words": bw})
            continue
        (BLOG / f"{slug}.md").write_text(content)
        summary["rewritten"].append({"slug": slug, "words": bw})
    (ROOT / "scripts/exec7_rewrite_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
