#!/usr/bin/env python3
"""Restore corrupted terraform drift + modules posts."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
WORD_PAT = re.compile(r"\b[\w'-]+\b")

POSTS: dict = {}
exec((Path(__file__).parent / "_rewrite_sd_tf_bodies_p4.py").read_text(encoding="utf-8"))

EXPANSIONS: dict[str, str] = {}
exec(  # noqa: S102
    (Path(__file__).parent / "_rewrite_sd_tf_expand.py").read_text(encoding="utf-8").split("def wc")[0]
)

EXTRA: dict[str, str] = {}
exec(  # noqa: S102
    (Path(__file__).parent / "_rewrite_sd_tf_expand2.py").read_text(encoding="utf-8").split("def wc")[0]
)


def wc(text: str) -> int:
    return len(WORD_PAT.findall(text))


def write_post(slug: str) -> int:
    data = POSTS[slug]
    meta = data["meta"]
    body = data["body"].strip()
    if slug in EXPANSIONS:
        head, tail = body.split("## Synthesis", 1)
        body = head.rstrip() + "\n" + EXPANSIONS[slug].strip() + "\n\n## Synthesis" + tail
    if slug in EXTRA:
        head, tail = body.split("## Synthesis", 1)
        body = head.rstrip() + "\n" + EXTRA[slug].strip() + "\n\n## Synthesis" + tail

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
    (BLOG / f"{slug}.md").write_text(fm + body + "\n", encoding="utf-8")
    return wc(body)


if __name__ == "__main__":
    for slug in ("terraform-drift-detection", "terraform-modules-composition"):
        print(f"{slug}: {write_post(slug)}")
