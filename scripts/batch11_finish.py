#!/usr/bin/env python3
"""Strip boilerplate, update dateModified, add topic expansions for batch11."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content/blog"
BATCH = Path("/tmp/batch11_chunk_1.txt")
DATE_MOD = "2026-07-17"
WORD_PAT = re.compile(r"\b[\w'-]+\b")

STRIP = [
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

# Topic-specific sections appended before ## Resources (or at end)
EXPAND: dict[str, str] = {}

def wc(t: str) -> int:
    return len(WORD_PAT.findall(t))

def parse(raw: str) -> tuple[str, str]:
    p = raw.split("---", 2)
    return p[1], p[2].lstrip("\n")

def strip_body(body: str) -> str:
    for pat in STRIP:
        body = re.sub(pat, "", body, flags=re.S)
    while "## Operational checklist" in body:
        body = re.sub(r"## Operational checklist for teams\n.*?(?=\n## |\Z)", "", body, count=1, flags=re.S)
    return re.sub(r"\n{3,}", "\n\n", body).strip()

def update_fm(fm: str) -> str:
    return re.sub(r'^dateModified:.*$', f'dateModified: "{DATE_MOD}"', fm, flags=re.M)

def insert_before_resources(body: str, section: str) -> str:
    if "## Resources" in body:
        return body.replace("## Resources", section + "\n\n## Resources", 1)
    return body + "\n\n" + section

def write(slug: str, fm: str, body: str) -> int:
    (BLOG / f"{slug}.md").write_text(f"---\n{fm.strip()}\n---\n\n{body.strip()}\n", encoding="utf-8")
    return wc(body)

# Load full rewrites for posts needing complete replacement
from batch11_remaining import FULL  # noqa: E402

def main():
    done = skipped = pending = 0
    samples = []
    for slug in BATCH.read_text().splitlines():
        slug = slug.strip()
        if not slug:
            continue
        path = BLOG / f"{slug}.md"
        raw = path.read_text(encoding="utf-8")
        fm, body = parse(raw)

        if slug in FULL:
            nfm, nbody = FULL[slug]
            c = write(slug, update_fm(nfm), nbody)
            done += 1
            samples.append((slug, c))
            continue

        cleaned = strip_body(body)
        if slug in EXPAND:
            cleaned = insert_before_resources(cleaned, EXPAND[slug])
        fm = update_fm(fm)
        w = wc(cleaned)
        generic = GENERIC_FAQ in fm

        if w >= 1200 and not generic:
            c = write(slug, fm, cleaned)
            if w >= 1200 and GENERIC_FAQ not in raw:
                skipped += 1
            else:
                done += 1
            samples.append((slug, c))
        else:
            pending += 1
            print(f"PENDING {slug}: {w} words generic_faq={generic}")

    print(f"Done: {done}, Skipped: {skipped}, Pending: {pending}")
    for s, c in sorted(samples, key=lambda x: -x[1])[:3]:
        print(f"  {s}: {c}")

if __name__ == "__main__":
    main()
