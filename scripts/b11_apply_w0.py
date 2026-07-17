#!/usr/bin/env python3
"""Apply b11_w0_complete POSTS to b11_need slugs only."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOG = ROOT / "content" / "blog"
SCRIPTS = Path(__file__).parent

NEED = set(
    open("/tmp/b11_need_0.txt").read().split()
    + open("/tmp/b11_need_1.txt").read().split()
)

# Load POSTS from b11_w0_complete
POSTS: dict = {}
code = (SCRIPTS / "b11_w0_complete.py").read_text()
# Execute only POSTS definitions (lines before _bodies)
start = code.index('POSTS = {}')
end = code.index("_bodies: dict = {}")
exec(code[start:end], {"POSTS": POSTS, "Path": Path, "re": re})
_bodies: dict = {}
exec((SCRIPTS / "b11_w0_complete_bodies.py").read_text(), {"POSTS": _bodies})
POSTS.update(_bodies)

BANNED = [
    "Validate this in staging", "Document the decision, owner",
    "Implementation patterns", "Common production mistakes",
    "Accessibility requirements", "Security and privacy considerations",
    "## Production lessons for", "## Operating ",
]

def verify(text: str) -> tuple[int, int, bool, list]:
    body = text.split("---", 2)[2]
    w = len(re.findall(r"\b[\w'-]+\b", body))
    faq = len(re.findall(r"^\s*-\s+q:", text.split("---", 2)[1], re.M))
    bad = [b for b in BANNED if b in text]
    dm = 'dateModified: "2026-07-17"' in text
    return w, faq, dm, bad

def main():
    applied = 0
    for slug in sorted(NEED & POSTS.keys()):
        content = POSTS[slug]
        (BLOG / f"{slug}.md").write_text(content, encoding="utf-8")
        w, faq, dm, bad = verify(content)
        ok = w >= 1200 and faq == 3 and dm and not bad
        print(f"{'OK' if ok else 'NO'} {slug}: {w}w faq={faq} bad={bad}")
        applied += 1
    print(f"Applied {applied} posts from b11_w0_complete")

if __name__ == "__main__":
    main()
