#!/usr/bin/env python3
"""Write 8 blog posts atomically. Run once."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "content" / "blog"

POSTS = {}

# Content loaded from variables below - script writes all at end
exec(open(__file__).read().split("# POST_BODIES_START")[1].split("# POST_BODIES_END")[0])

def word_count(text):
    return len(re.findall(r"\b[\w'-]+\b", text.split("---", 2)[2]))

for slug, content in POSTS.items():
    path = ROOT / f"{slug}.md"
    path.write_text(content)
    print(f"{slug}: {word_count(content)}")

# POST_BODIES_START
POSTS = {}
