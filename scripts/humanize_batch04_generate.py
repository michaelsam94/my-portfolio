#!/usr/bin/env python3
"""Humanize batch-04 DevOps blog posts (>=1200 words, unique sections)."""
import json
import re
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content/blog"
PROGRESS = ROOT / "scripts/humanize-progress/batch-04.json"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")
TOPICS = {}


def topic(slug, title, desc, tags, keywords, faqs, sections, date_pub, date_mod="2026-07-17"):
    TOPICS[slug] = (title, desc, tags, keywords, faqs, sections, date_pub, date_mod)


def render(slug, data):
    title, desc, tags, keywords, faqs, sections, date_pub, date_mod = data
    lines = [
        f'title: "{title}"',
        f'slug: "{slug}"',
        f'description: "{desc}"',
        f'datePublished: "{date_pub}"',
        f'dateModified: "{date_mod}"',
        "tags:",
    ]
    for t in tags:
        lines.append(f'  - "{t}"')
    lines.append(f'keywords: "{keywords}"')
    lines.append("faq:")
    for q, a in faqs:
        lines.append(f'  - q: "{q}"')
        lines.append(f'    a: "{a}"')
    parts = []
    for item in sections:
        heading, paras = item[0], item[1]
        code = item[2] if len(item) > 2 else None
        parts.append(f"## {heading}\n")
        for p in paras:
            parts.append(p + "\n")
        if code:
            parts.append(code.strip() + "\n")
    return "\n".join(lines), "\n".join(parts)


def wc(text):
    return len(WORD.findall(text))

# Topic definitions appended below
