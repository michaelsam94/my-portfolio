#!/usr/bin/env python3
"""Apply batch11 rewrites: strip boilerplate, inject expansions, write posts."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content/blog"
BATCH = Path("/tmp/batch11_chunk_1.txt")
DATE_MOD = "2026-07-17"
WORD_PAT = re.compile(r"\b[\w'-]+\b")

STRIP_PATTERNS = [
    r"## Common production mistakes\n.*?(?=\n## |\Z)",
    r"## Debugging and triage workflow\n.*?(?=\n## |\Z)",
    r"## Operational checklist for teams\n.*?(?=\n## |\Z)",
    r"## Architecture and boundaries\n.*?(?=\n## |\Z)",
    r"## Accessibility requirements\n.*?(?=\n## |\Z)",
    r"## Security and privacy considerations\n.*?(?=\n## |\Z)",
    r"## Testing strategy\n.*?(?=\n## |\Z)",
    r"Treat production rollout as a measured change:.*?\n\n",
    r"The gap between reading about .*? — not a conference demo\.\n\n",
    r"I have applied these patterns across product sites where Core Web Vitals.*?\n\n",
    r"Validate in staging with production-like data volumes\..*?\n\n",
    r"Document the timeline during triage\..*?\n\n",
    r"Document trade-offs in the PR description\..*?\n\n",
    r"Testing strategy for .*? gives false confidence.*?\n\n",
    r"System design for .*? breaks at scale when hot keys.*?\n\n",
]

GENERIC_FAQ = "is a production pattern for frontend and product engineering"

# Import full body rewrites for posts needing complete replacement
sys.path.insert(0, str(Path(__file__).parent))
from batch11_bodies import BODIES  # noqa: E402


def wc(text: str) -> int:
    return len(WORD_PAT.findall(text))


def parse(path: Path) -> tuple[str, str]:
    raw = path.read_text(encoding="utf-8")
    parts = raw.split("---", 2)
    return parts[1], parts[2].lstrip("\n")


def strip_boiler(body: str) -> str:
    for pat in STRIP_PATTERNS:
        body = re.sub(pat, "", body, flags=re.S)
    while "## Operational checklist" in body:
        body = re.sub(
            r"## Operational checklist for teams\n.*?(?=\n## |\Z)",
            "",
            body,
            count=1,
            flags=re.S,
        )
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def update_fm(fm: str, new_faq: list | None = None) -> str:
    fm = re.sub(r'^dateModified:.*$', f'dateModified: "{DATE_MOD}"', fm, flags=re.M)
    if new_faq and GENERIC_FAQ in fm:
        faq_block = "faq:\n" + "\n".join(
            f'  - q: "{q}"\n    a: "{a}"' for q, a in new_faq
        )
        fm = re.sub(r"faq:\n(?:  - q:.*?\n    a: .*?\n)+", faq_block + "\n", fm, flags=re.S)
    return fm


def write_post(slug: str, fm: str, body: str) -> int:
    path = BLOG / f"{slug}.md"
    path.write_text(f"---\n{fm.strip()}\n---\n\n{body.strip()}\n", encoding="utf-8")
    return wc(body)


def main() -> None:
    slugs = [s.strip() for s in BATCH.read_text().splitlines() if s.strip()]
    done, skipped = 0, 0
    results: list[tuple[str, int, str]] = []

    for slug in slugs:
        path = BLOG / f"{slug}.md"
        if not path.exists():
            print(f"MISSING: {slug}")
            continue

        fm, body = parse(path)
        generic_faq = GENERIC_FAQ in fm

        if slug in BODIES:
            entry = BODIES[slug]
            if len(entry) == 3:
                new_fm, new_body, faq = entry
                fm = update_fm(new_fm, faq)
            else:
                new_fm, new_body = entry
                fm = update_fm(new_fm)
            count = write_post(slug, fm, new_body)
            done += 1
            results.append((slug, count, "rewritten"))
            continue

        cleaned = strip_boiler(body)
        words = wc(cleaned)

        if words >= 1200 and not generic_faq:
            fm = update_fm(fm)
            count = write_post(slug, fm, cleaned)
            skipped += 1
            results.append((slug, count, "skipped"))
            continue

        print(f"NO BODY: {slug} ({words} words, generic={generic_faq})")

    print(f"\nDone: {done}, Skipped: {skipped}")
    top = sorted(results, key=lambda x: -x[1])
    for slug, count, status in top[:3]:
        print(f"  {slug}: {count} words ({status})")


if __name__ == "__main__":
    main()
