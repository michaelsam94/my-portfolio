#!/usr/bin/env python3
"""Overwrite 20 agent blog slugs with unique deep-dives — no boilerplate."""
from pathlib import Path

BLOG = Path(__file__).resolve().parents[1] / "content/blog"
DATE = "2026-07-17"

POSTS = {}

# Each value: (title, description, tags, keywords, faqs, body)
# faqs: list of (q, a)

def fm(title, slug, desc, tags, keywords, faqs, date_pub="2025-11-04"):
    lines = [
        "---",
        f'title: "{title}"',
        f'slug: "{slug}"',
        f'description: "{desc}"',
        f'datePublished: "{date_pub}"',
        f'dateModified: "{DATE}"',
        f'tags: {tags}',
        f'keywords: "{keywords}"',
        "faq:",
    ]
    for q, a in faqs:
        lines.append(f'  - q: "{q}"')
        lines.append(f'    a: "{a}"')
    lines.append("---")
    return "\n".join(lines)


# Import bodies from companion module to keep this file runnable
from _urgent_rewrite_agent_20_bodies import BODIES  # noqa: E402

SLUGS = list(BODIES.keys())

def main():
    for slug, data in BODIES.items():
        title, desc, tags, keywords, faqs, body, date_pub = data
        content = fm(title, slug, desc, tags, keywords, faqs, date_pub) + "\n" + body
        path = BLOG / f"{slug}.md"
        path.write_text(content, encoding="utf-8")
        words = len(content.split())
        boiler = "Design principles that survive production" in content
        print(f"{slug}: {words} words, boiler={boiler}, date={DATE}")

if __name__ == "__main__":
    main()
