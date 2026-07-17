#!/usr/bin/env python3
"""Generate complete blog deep-dives for b11g batch 12-16."""
from __future__ import annotations
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "content" / "blog"
DATE_MOD = "2026-07-17"

def fm(meta: dict, body: str) -> str:
    lines = ["---"]
    for k, v in meta.items():
        if k == "faq":
            lines.append("faq:")
            for item in v:
                lines.append(f'  - q: "{item["q"]}"')
                lines.append(f'    a: "{item["a"]}"')
        elif isinstance(v, list):
            if all(isinstance(x, str) for x in v):
                lines.append(f"{k}: {v}")
            else:
                lines.append(f"{k}:")
                for x in v:
                    lines.append(f'  - "{x}"')
        else:
            lines.append(f'{k}: "{v}"')
    lines.append("---")
    return "\n".join(lines) + "\n\n" + body.strip() + "\n"

def word_count(text: str) -> int:
    return len(re.sub(r"^---.*?---\n", "", text, flags=re.S).split())

ARTICLES: dict[str, dict] = {}

# Import article bodies from companion module
from gen_b11g_bodies import BODIES  # noqa: E402

def build_all():
    for slug, data in BODIES.items():
        meta = {k: v for k, v in data.items() if k != "body"}
        meta["slug"] = slug
        meta["dateModified"] = DATE_MOD
        ARTICLES[slug] = fm(meta, data["body"])

def write_all():
    build_all()
    ROOT.mkdir(parents=True, exist_ok=True)
    counts = {}
    for slug, content in ARTICLES.items():
        path = ROOT / f"{slug}.md"
        path.write_text(content, encoding="utf-8")
        counts[slug] = word_count(content)
    return counts

if __name__ == "__main__":
    counts = write_all()
    under = {s: w for s, w in counts.items() if w < 1200}
    print(f"Written: {len(counts)}")
    print(f"Under 1200: {len(under)}")
    if under:
        for s, w in sorted(under.items(), key=lambda x: x[1]):
            print(f"  {w} {s}")
    else:
        print(f"Min words: {min(counts.values())}")
        print(f"Max words: {max(counts.values())}")
        print(f"Avg words: {sum(counts.values()) // len(counts)}")
