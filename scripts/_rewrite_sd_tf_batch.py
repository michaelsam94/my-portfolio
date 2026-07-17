#!/usr/bin/env python3
"""Rewrite system-design + terraform batch as unique >=1200-word deep-dives."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
WORD_PAT = re.compile(r"\b[\w'-]+\b")
TARGET = 1200

POSTS: dict[str, dict] = {}


def wc(text: str) -> int:
    return len(WORD_PAT.findall(text))


def write_post(slug: str, meta: dict, body: str) -> int:
    path = BLOG / f"{slug}.md"
    fm = f"""---
title: "{meta['title']}"
slug: "{slug}"
description: "{meta['description']}"
datePublished: "{meta['datePublished']}"
dateModified: "2026-07-17"
tags: {meta['tags']}
keywords: "{meta['keywords']}"
faq:
  - q: "{meta['faq'][0]['q']}"
    a: "{meta['faq'][0]['a']}"
  - q: "{meta['faq'][1]['q']}"
    a: "{meta['faq'][1]['a']}"
  - q: "{meta['faq'][2]['q']}"
    a: "{meta['faq'][2]['a']}"
---

"""
    content = fm + body.strip() + "\n"
    path.write_text(content, encoding="utf-8")
    return wc(body)


# Content loaded from companion data files
_here = Path(__file__).parent
for _part in ("p1", "p2", "p3", "p4"):
    exec((_here / f"_rewrite_sd_tf_bodies_{_part}.py").read_text(encoding="utf-8"))

if __name__ == "__main__":
    counts = {}
    for slug, data in POSTS.items():
        counts[slug] = write_post(slug, data["meta"], data["body"])
    print("Word counts (body only):")
    for slug in sorted(counts):
        flag = "OK" if counts[slug] >= TARGET else "SHORT"
        print(f"  {slug}: {counts[slug]} [{flag}]")
    short = [s for s, c in counts.items() if c < TARGET]
    if short:
        raise SystemExit(f"Below {TARGET} words: {short}")
