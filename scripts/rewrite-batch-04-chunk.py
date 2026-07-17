#!/usr/bin/env python3
"""Generate remaining batch-04 blog rewrites >= 1200 words."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOG = ROOT / "content/blog"

# Each entry: slug -> (title, description, tags, keywords, faqs, body)
# Body is markdown after frontmatter closing ---

ARTICLES = {}

def article(slug, title, description, tags, keywords, faqs, body):
    faq_yaml = "\n".join(
        f'  - q: "{q}"\n    a: "{a}"' for q, a in faqs
    )
    tag_yaml = "\n".join(f'  - "{t}"' for t in tags)
    kw = ", ".join(keywords)
    content = f"""---
title: "{title}"
slug: "{slug}"
description: "{description}"
datePublished: "2026-07-01"
dateModified: "2026-07-17"
tags:
{tag_yaml}
keywords: "{kw}"
faq:
{faq_yaml}
---

{body}
"""
    return content

# Script will be populated - run separately after articles dict filled

if __name__ == "__main__":
    slugs = list(ARTICLES.keys())
    for slug, data in ARTICLES.items():
        path = BLOG / f"{slug}.md"
        path.write_text(article(slug, *data))
        words = len(path.read_text().split())
        print(f"{words} {slug}")
    print(f"Wrote {len(slugs)} files")
