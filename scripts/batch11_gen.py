#!/usr/bin/env python3
"""Generate batch11 content by expanding cleaned existing bodies."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
BATCH = Path("/tmp/batch11_chunk_1.txt")
DATE_MOD = "2026-07-17"
WORD_PAT = re.compile(r"\b[\w'-]+\b")

BOILER = [
    r"## Common production mistakes\n.*?(?=\n## |\Z)",
    r"## Debugging and triage workflow\n.*?(?=\n## |\Z)",
    r"## Operational checklist for teams\n.*?(?=\n## |\Z)",
    r"Treat production rollout as a measured change:.*?\n\n",
    r"The gap between reading about .*? — not a conference demo\.\n\n",
    r"I have applied these patterns across product sites where Core Web Vitals.*?\n\n",
    r"## Architecture and boundaries\n.*?(?=\n## |\Z)",
    r"## Accessibility requirements\n.*?(?=\n## |\Z)",
    r"## Security and privacy considerations\n.*?(?=\n## |\Z)",
    r"## Testing strategy\n.*?(?=\n## |\Z)",
    r"Validate in staging with production-like data volumes\..*?\n\n",
    r"Document the timeline during triage\..*?\n\n",
    r"Document trade-offs in the PR description\..*?\n\n",
    r"Testing strategy for .*? gives false confidence.*?\n\n",
    r"System design for .*? breaks at scale when hot keys.*?\n\n",
]

GENERIC_FAQ = "is a production pattern for frontend and product engineering"

# Unique closing sections per slug (topic-specific, no boilerplate)
EXPANSIONS: dict[str, str] = {}

def wc(t: str) -> int:
    return len(WORD_PAT.findall(t))


def parse(path: Path) -> tuple[str, str]:
    raw = path.read_text(encoding="utf-8")
    parts = raw.split("---", 2)
    return parts[1], parts[2].lstrip("\n")


def strip(body: str) -> str:
    for p in BOILER:
        body = re.sub(p, "", body, flags=re.S)
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def update_fm(fm: str) -> str:
    fm = re.sub(r'^dateModified:.*$', f'dateModified: "{DATE_MOD}"', fm, flags=re.M)
    return fm


def write(slug: str, fm: str, body: str) -> int:
    (BLOG / f"{slug}.md").write_text(f"---\n{fm.strip()}\n---\n\n{body.strip()}\n", encoding="utf-8")
    return wc(body)


# Import full rewrites
from batch11_full import FULL  # noqa: E402

def main():
    slugs = [s.strip() for s in BATCH.read_text().splitlines() if s.strip()]
    done, skipped = 0, 0
    samples = []

    for slug in slugs:
        path = BLOG / slug + ".md" if False else BLOG / f"{slug}.md"
        if slug in FULL:
            fm, body = FULL[slug]
            fm = update_fm(fm) if 'dateModified' in fm else fm.replace('datePublished', f'dateModified: "{DATE_MOD}"\ndatePublished', 1)
            if 'dateModified' not in fm:
                fm = re.sub(r'(datePublished:.*)', rf'\1\ndateModified: "{DATE_MOD}"', fm, count=1)
            count = write(slug, fm, body)
            done += 1
            samples.append((slug, count))
            continue

        fm, body = parse(path)
        if GENERIC_FAQ in fm and slug not in FULL:
            print(f"WARN: {slug} has generic FAQ but no full rewrite")
        cleaned = strip(body)
        if slug in EXPANSIONS:
            cleaned = cleaned + "\n\n" + EXPANSIONS[slug]
        words = wc(cleaned)
        if words >= 1200 and GENERIC_FAQ not in fm:
            fm = update_fm(fm)
            count = write(slug, fm, cleaned)
            skipped += 1
            samples.append((slug, count))
            continue
        print(f"PENDING: {slug} ({words} words)")

    print(f"Done: {done}, Skipped: {skipped}")
    for s, c in sorted(samples, key=lambda x: -x[1])[:3]:
        print(f"  sample: {s} = {c} words")

if __name__ == "__main__":
    main()
