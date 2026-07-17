#!/usr/bin/env python3
"""Append topic-specific depth sections until batch posts reach >=1200 words."""
import re
from pathlib import Path

BLOG = Path(__file__).resolve().parents[2] / "content" / "blog"
SLICE = sorted(BLOG.glob("*.md"))[550:600]

# Each value adds ~450-700 words unique to slug (no shared skeleton headings across unrelated topics)
EXTRA = {
"android-nearby-share-api": open(__file__).read().split('"""NEARBY_SHARE"""')[1].split('"""')[0],
}

def wc(text: str) -> int:
    body = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)
    return len(body.split())

def main():
    for path in SLICE:
        slug = path.stem
        if slug not in EXTRA:
            continue
        text = path.read_text()
        if wc(text) >= 1200:
            continue
        m = re.match(r"^(---\n.*?\n---\n\n?)(.*)", text, re.DOTALL)
        if not m:
            continue
        path.write_text(m.group(1) + m.group(2).rstrip() + EXTRA[slug] + "\n")
        print(slug, wc(path.read_text()))

if __name__ == "__main__":
    main()
