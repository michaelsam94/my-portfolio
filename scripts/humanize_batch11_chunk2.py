#!/usr/bin/env python3
"""Humanize batch-11 chunk 2 posts from /tmp/batch11_chunk_2.txt — topic-specific, no boilerplate."""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
BATCH_FILE = Path("/tmp/batch11_chunk_2.txt")
DATE_MOD = "2026-07-17"
TARGET = 1200
WORD_PAT = re.compile(r"\b[\w'-]+\b")
BOILER = (
    "Validate this in staging",
    "Additional production considerations",
    "Document the decision, owner",
    "Architecture and boundaries",
    "The gap between reading about",
)


def wc(text: str) -> int:
    return len(WORD_PAT.findall(text))


def parse_fm(raw: str) -> tuple[str, str]:
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return "", raw
    return parts[1], parts[2].lstrip("\n")


def extract_field(fm: str, key: str) -> str | None:
    m = re.search(rf'^{key}:\s*"([^"]*)"', fm, re.M)
    return m.group(1) if m else None


def extract_tags(fm: str) -> list[str]:
    tags = []
    in_tags = False
    for line in fm.splitlines():
        if line.strip() == "tags:":
            in_tags = True
            continue
        if in_tags:
            if line.startswith("  - "):
                tags.append(line[4:].strip().strip('"'))
            else:
                break
    return tags


def needs_rewrite(raw: str, body: str) -> bool:
    if wc(body) < TARGET:
        return True
    return any(b in raw for b in BOILER)


def yaml_quote(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def build_fm(slug: str, old_fm: str, faq: list[tuple[str, str]]) -> str:
    title = extract_field(old_fm, "title") or slug.replace("-", " ").title()
    desc = extract_field(old_fm, "description") or ""
    pub = extract_field(old_fm, "datePublished") or DATE_MOD
    tags = extract_tags(old_fm) or ["Engineering"]
    kw = extract_field(old_fm, "keywords") or slug.replace("-", ", ")
    lines = [
        "---",
        f'title: "{yaml_quote(title)}"',
        f'slug: "{slug}"',
        f'description: "{yaml_quote(desc)}"',
        f'datePublished: "{pub}"',
        f'dateModified: "{DATE_MOD}"',
        "tags:",
    ]
    for t in tags:
        lines.append(f'  - "{yaml_quote(t)}"')
    lines.append(f'keywords: "{yaml_quote(kw)}"')
    lines.append("faq:")
    for q, a in faq:
        lines.append(f'  - q: "{yaml_quote(q)}"')
        lines.append(f'    a: "{yaml_quote(a)}"')
    lines.append("---")
    return "\n".join(lines)


# Import article bodies from companion module
sys.path.insert(0, str(Path(__file__).parent))
from batch11_chunk2_articles import ARTICLES  # noqa: E402


def main():
    slugs = [s.strip() for s in BATCH_FILE.read_text().splitlines() if s.strip()]
    done = skipped = 0
    results = []

    for slug in slugs:
        path = BLOG / f"{slug}.md"
        if not path.exists():
            results.append((slug, "missing", 0))
            continue
        raw = path.read_text()
        fm, body = parse_fm(raw)
        if not needs_rewrite(raw, body):
            skipped += 1
            results.append((slug, "skipped", wc(body)))
            continue
        if slug not in ARTICLES:
            results.append((slug, "no_content", wc(body)))
            continue
        art = ARTICLES[slug]
        new_raw = build_fm(slug, fm, art["faq"]) + "\n\n" + art["body"].strip() + "\n"
        path.write_text(new_raw)
        done += 1
        results.append((slug, "done", wc(art["body"])))

    print(f"DONE={done} SKIPPED={skipped}")
    samples = [(s, st, w) for s, st, w in results if st == "done"][:3]
    for s, _, w in samples:
        print(f"SAMPLE {s} {w}w")
    missing = [s for s, st, _ in results if st in ("no_content", "missing")]
    if missing:
        print("MISSING:", ", ".join(missing))


if __name__ == "__main__":
    main()
