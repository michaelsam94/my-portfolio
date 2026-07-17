#!/usr/bin/env python3
"""Final consolidated rewrite: all 12 SD/TF posts, unique, >=1200 words, no boilerplate."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
WORD_PAT = re.compile(r"\b[\w'-]+\b")
TARGET = 1200
BOILERPLATE_MARKERS = [
    "after traffic shifts (review",
    "teams that treat",
    "as a checklist item",
    "Problem framing",
    "Design principles that survive production",
    "The question behind the ticket",
]

POSTS: dict = {}
for part in ("p1", "p2", "p3", "p4"):
    exec((Path(__file__).parent / f"_rewrite_sd_tf_bodies_{part}.py").read_text(encoding="utf-8"))

SYNTHESIS_MARKERS = [
    "## Synthesis",
    "## Interview and production synthesis",
    "## What interviewers and production both probe",
]


def _load_dict(path: Path, name: str) -> dict:
    chunk = path.read_text(encoding="utf-8").split("\ndef wc")[0]
    ns: dict = {"__file__": str(path)}
    exec(chunk, ns)  # noqa: S102
    return ns[name]


EXPANSIONS = _load_dict(Path(__file__).parent / "_rewrite_sd_tf_expand.py", "EXPANSIONS")
EXTRA = _load_dict(Path(__file__).parent / "_rewrite_sd_tf_expand2.py", "EXTRA")
EXPAND3 = _load_dict(Path(__file__).parent / "_rewrite_sd_tf_expand3.py", "EXPAND3")
EXPAND4 = _load_dict(Path(__file__).parent / "_rewrite_sd_tf_expand4.py", "EXPAND4")
EXPAND5 = _load_dict(Path(__file__).parent / "_rewrite_sd_tf_expand5.py", "EXPAND5")
EXPAND6 = _load_dict(Path(__file__).parent / "_rewrite_sd_tf_expand6.py", "EXPAND6")
EXPAND7 = _load_dict(Path(__file__).parent / "_rewrite_sd_tf_expand7.py", "EXPAND7")
EXPAND8 = _load_dict(Path(__file__).parent / "_rewrite_sd_tf_expand8.py", "EXPAND8")
MANUAL: dict[str, str] = {}


def wc(text: str) -> int:
    return len(WORD_PAT.findall(text))


def _insert_before_closing(body: str, addition: str) -> str:
    for marker in SYNTHESIS_MARKERS:
        if marker in body:
            head, tail = body.split(marker, 1)
            return head.rstrip() + "\n" + addition.strip() + "\n\n" + marker + tail
    return body.rstrip() + "\n" + addition.strip()


def build_body(slug: str) -> str:
    body = POSTS[slug]["body"].strip()
    for extra_dict in (EXPANSIONS, EXTRA, MANUAL, EXPAND3, EXPAND4, EXPAND5, EXPAND6, EXPAND7, EXPAND8):
        if slug in extra_dict:
            body = _insert_before_closing(body, extra_dict[slug])
    return body.strip() + "\n"


def write_post(slug: str) -> int:
    meta = POSTS[slug]["meta"]
    body = build_body(slug)
    for m in BOILERPLATE_MARKERS:
        if m in body:
            raise ValueError(f"Boilerplate '{m}' in {slug}")

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
    (BLOG / f"{slug}.md").write_text(fm + body, encoding="utf-8")
    return wc(body)


if __name__ == "__main__":
    counts = {s: write_post(s) for s in POSTS}
    print("Final word counts (body):")
    short = []
    for slug in sorted(counts):
        flag = "OK" if counts[slug] >= TARGET else "SHORT"
        print(f"  {slug}: {counts[slug]} [{flag}]")
        if counts[slug] < TARGET:
            short.append(slug)
    if short:
        raise SystemExit(f"Below {TARGET}: {short}")
