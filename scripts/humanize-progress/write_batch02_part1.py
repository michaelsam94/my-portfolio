#!/usr/bin/env python3
"""Write/expand batch 02 part 1 blog posts to >=1200 words."""
import re
from pathlib import Path

BLOG = Path(__file__).resolve().parents[2] / "content" / "blog"

# slug -> (frontmatter dict fields preserved via regex, body markdown)
POSTS = {}

def write_post(filename: str, frontmatter: str, body: str):
    path = BLOG / filename
    content = f"---\n{frontmatter.strip()}\n---\n\n{body.strip()}\n"
    path.write_text(content)
    words = len(re.sub(r"---.*?---", "", content, flags=re.S).split())
    return words
