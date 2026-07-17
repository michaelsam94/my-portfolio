#!/usr/bin/env python3
"""Write humanized batch-04 blog posts and progress JSON."""
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content/blog"
PROGRESS = ROOT / "scripts/humanize-progress/batch-04.json"

WORD = re.compile(r"\b[\w'-]+\b")


def wc(body: str) -> int:
    return len(WORD.findall(body))


def write_post(slug: str, fm: str, body: str) -> dict:
    path = BLOG / f"{slug}.md"
    content = f"---\n{fm.strip()}\n---\n{body.strip()}\n"
    path.write_text(content)
    count = wc(body)
    faq_count = fm.count("- q:")
    return {"slug": slug, "word_count": count, "faq_count": faq_count, "path": str(path.relative_to(ROOT))}


# Posts are written inline below; run script to materialize files.
POSTS = []
