#!/usr/bin/env python3
"""Rewrite batch11_chunk_1 posts: humanize, expand, remove boilerplate."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
BATCH = Path("/tmp/batch11_chunk_1.txt")
DATE_MOD = "2026-07-17"
WORD_PAT = re.compile(r"\b[\w'-]+\b")

BOILERPLATE_SECTIONS = [
    r"## Common production mistakes\n.*?(?=\n## |\Z)",
    r"## Debugging and triage workflow\n.*?(?=\n## |\Z)",
    r"## Operational checklist for teams\n.*?(?=\n## |\Z)",
    r"## Architecture and boundaries\n.*?(?=\n## Implementation|\n## |\Z)",
    r"## Accessibility requirements\n.*?(?=\n## |\Z)",
    r"## Security and privacy considerations\n.*?(?=\n## |\Z)",
    r"Treat production rollout as a measured change:.*?\n\n",
    r"Document the timeline during triage\. Future you.*?\n\n",
    r"Validate in staging with production-like data volumes\..*?\n\n",
    r"The gap between reading about .*? — not a conference demo\.\n\n",
    r"I have applied these patterns across product sites where Core Web Vitals.*?\n\n",
]

GENERIC_FAQ_PATTERNS = [
    r"is a production pattern for frontend and product engineering",
    r"when you have field data or user research showing pain",
    r"Teams often optimize for demo metrics instead of field data",
]


def wc(text: str) -> int:
    return len(WORD_PAT.findall(text))


def parse_frontmatter(content: str) -> tuple[str, str]:
    if not content.startswith("---"):
        raise ValueError("No frontmatter")
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError("Malformed frontmatter")
    return parts[1], parts[2].lstrip("\n")


def update_fm(fm: str) -> str:
    if re.search(r"^dateModified:", fm, re.M):
        fm = re.sub(r'^dateModified:.*$', f'dateModified: "{DATE_MOD}"', fm, flags=re.M)
    else:
        fm = fm.rstrip() + f'\ndateModified: "{DATE_MOD}"'
    return fm


def has_generic_faq(fm: str) -> bool:
    return any(p in fm for p in GENERIC_FAQ_PATTERNS)


def strip_boilerplate(body: str) -> str:
    for pat in BOILERPLATE_SECTIONS:
        body = re.sub(pat, "", body, flags=re.S)
    # Remove duplicate operational checklist blocks
    while body.count("## Operational checklist for teams") > 0:
        body = re.sub(
            r"## Operational checklist for teams\n.*?(?=\n## |\Z)",
            "",
            body,
            count=1,
            flags=re.S,
        )
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def write_post(slug: str, fm: str, body: str) -> int:
    path = BLOG / f"{slug}.md"
    path.write_text(f"---\n{fm.strip()}\n---\n\n{body.strip()}\n", encoding="utf-8")
    return wc(body)


def load_custom() -> dict[str, tuple[str, str]]:
    """Import handcrafted full rewrites."""
    from batch11_content import POSTS  # noqa: WPS433

    return POSTS


def main() -> None:
    sys.path.insert(0, str(Path(__file__).parent))
    slugs = [s.strip() for s in BATCH.read_text().splitlines() if s.strip()]
    custom = load_custom()
    done, skipped = 0, 0
    results: list[tuple[str, int, str]] = []

    for slug in slugs:
        path = BLOG / f"{slug}.md"
        if not path.exists():
            print(f"MISSING: {slug}")
            continue

        if slug in custom:
            fm, body = custom[slug]
            count = write_post(slug, fm, body)
            done += 1
            results.append((slug, count, "rewritten"))
            continue

        raw = path.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(raw)
        cleaned = strip_boilerplate(body)
        words = wc(cleaned)
        generic = has_generic_faq(fm)

        if words >= 1200 and not generic:
            fm = update_fm(fm)
            count = write_post(slug, fm, cleaned)
            skipped += 1
            results.append((slug, count, "skipped-cleanup-only"))
            continue

        print(f"NEEDS CUSTOM REWRITE: {slug} ({words} words, generic_faq={generic})")

    print(f"\nDone: {done}, Skipped: {skipped}, Need manual: {len(slugs) - done - skipped}")
    for slug, count, status in sorted(results, key=lambda x: -x[1])[:5]:
        print(f"  {slug}: {count} words ({status})")


if __name__ == "__main__":
    main()
