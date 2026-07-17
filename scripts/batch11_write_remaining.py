#!/usr/bin/env python3
"""Write remaining batch11 posts that need full rewrites."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content/blog"
DATE = "2026-07-17"
WORD = re.compile(r"\b[\w'-]+\b")

def wc(t): return len(WORD.findall(t))
def w(slug, fm, body):
    p = BLOG / f"{slug}.md"
    p.write_text(f"---\n{fm}\n---\n\n{body}\n", encoding="utf-8")
    return wc(body)

# Import all post content
from batch11_remaining import POSTS  # noqa

if __name__ == "__main__":
    results = []
    for slug, (fm, body) in POSTS.items():
        fm = re.sub(r'^dateModified:.*$', f'dateModified: "{DATE}"', fm, flags=re.M)
        c = w(slug, fm.strip(), body.strip())
        results.append((slug, c))
    print(f"Wrote {len(results)} posts")
    for s, c in sorted(results, key=lambda x: -x[1])[:5]:
        print(f"  {s}: {c}")
