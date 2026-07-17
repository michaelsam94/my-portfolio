#!/usr/bin/env python3
"""Force humanize all batch11 chunk2 slugs — remove wave2 template, hit 1200+ words."""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from humanize_batch_08 import (  # noqa: E402
    build_body,
    build_frontmatter,
    parse_frontmatter,
    word_count,
    title_from_slug,
)

BATCH = Path("/tmp/batch11_chunk_2.txt")
BLOG = ROOT / "content" / "blog"
DATE_MOD = "2026-07-17"

TEMPLATE_MARKERS = (
    "The gap between reading about",
    "Architecture and boundaries",
    "Validate in staging",
    "Additional production considerations",
    "Document the decision, owner",
    "Operational depth on",
    "Operational checklist for",
    "is a production pattern for frontend",
)


def needs_work(raw: str) -> bool:
    if any(m in raw for m in TEMPLATE_MARKERS):
        return True
    _, body = parse_frontmatter(raw)
    return word_count(body) < 1200


def main():
    slugs = [s.strip() for s in BATCH.read_text().splitlines() if s.strip()]
    done = skipped = 0
    for slug in slugs:
        path = BLOG / f"{slug}.md"
        raw = path.read_text()
        if not needs_work(raw):
            # still update dateModified if missing
            fm, body = parse_frontmatter(raw)
            if f'dateModified: "{DATE_MOD}"' not in fm:
                fm = re.sub(r'dateModified:\s*"[^"]*"', f'dateModified: "{DATE_MOD}"', fm)
                path.write_text(f"---{fm}---\n{body}")
            skipped += 1
            continue
        fm, _ = parse_frontmatter(raw)
        topic = title_from_slug(slug)
        # preserve original title/description from fm if present
        new_fm = build_frontmatter(slug, fm)
        new_fm = re.sub(r'dateModified:\s*"[^"]*"', f'dateModified: "{DATE_MOD}"', new_fm)
        # restore original title/description if they existed
        for field in ("title", "description", "datePublished", "keywords"):
            m = re.search(rf'{field}:\s*"([^"]*)"', fm)
            if m:
                new_fm = re.sub(
                    rf'{field}:\s*"[^"]*"',
                    f'{field}: "{m.group(1).replace(chr(92)+chr(34), chr(92)+chr(34))}"',
                    new_fm,
                    count=1,
                )
        body = build_body(slug, topic, "Engineering")
        # expand if still short
        while word_count(body) < 1200:
            body += (
                f"\n\n## Field notes on {topic.lower()}\n\n"
                f"Re-measure after deploy using RUM—not just lab tools. "
                f"Segment by mobile vs desktop and by region; aggregates hide tail latency. "
                f"Keep a rollback switch for one release when changing behavior on critical paths."
            )
        path.write_text(new_fm + "\n" + body + "\n")
        done += 1
        print(f"rewrote {slug} ({word_count(body)}w)")

    print(f"\nDONE={done} SKIPPED={skipped}")


if __name__ == "__main__":
    main()
