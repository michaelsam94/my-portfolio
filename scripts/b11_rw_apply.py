#!/usr/bin/env python3
"""Apply unique ≥1200-word bodies for b11_rw slugs."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
DATE = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")

SLUG_FILES = [
    "/tmp/b11_rw_0.txt",
    "/tmp/b11_rw_1.txt",
    "/tmp/b11_rw_2.txt",
]


def load_slugs() -> list[str]:
    slugs = []
    for f in SLUG_FILES:
        with open(f) as fh:
            for line in fh:
                s = line.strip()
                if s:
                    slugs.append(s)
    return slugs


def wc(text: str) -> int:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            text = parts[2]
    return len(WORD.findall(text))


def parse_fm(raw: str):
    p = raw.split("---", 2)
    return p[1], p[2] if len(p) > 2 else ""


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def extract_field(fm: str, key: str):
    m = re.search(rf'^{key}:\s*"([^"]*)"', fm, re.M)
    return m.group(1) if m else None


def extract_tags(fm: str):
    tags, on = [], False
    for line in fm.splitlines():
        if line.strip() == "tags:":
            on = True
            continue
        if on:
            if line.startswith("  - "):
                tags.append(line[4:].strip().strip('"').strip("'"))
            elif line.strip() and not line.startswith(" "):
                break
    return tags


def extract_faq(fm: str):
    out, q, on = [], None, False
    for line in fm.splitlines():
        if line.strip() == "faq:":
            on = True
            continue
        if not on:
            continue
        if line.startswith("  - q:"):
            q = line.split('"')[1] if '"' in line else line.split(":", 1)[1].strip()
        elif line.startswith("    a:") and q:
            out.append((q, line.split('"')[1] if '"' in line else line.split(":", 1)[1].strip()))
            q = None
    return out[:3]


def fm_block(slug: str, old_fm: str, faqs=None) -> str:
    faqs = faqs or extract_faq(old_fm)
    title = extract_field(old_fm, "title") or slug
    desc = extract_field(old_fm, "description") or ""
    pub = extract_field(old_fm, "datePublished") or DATE
    tags = extract_tags(old_fm) or ["Engineering"]
    kw = extract_field(old_fm, "keywords") or slug
    lines = [
        "---",
        f'title: "{esc(title)}"',
        f'slug: "{slug}"',
        f'description: "{esc(desc)}"',
        f'datePublished: "{pub}"',
        f'dateModified: "{DATE}"',
        "tags:",
    ]
    for t in tags:
        lines.append(f'  - "{esc(t)}"')
    lines.append(f'keywords: "{esc(kw)}"')
    lines.append("faq:")
    for q, a in faqs[:3]:
        lines.append(f'  - q: "{esc(q)}"')
        lines.append(f'    a: "{esc(a)}"')
    lines.append("---")
    return "\n".join(lines)


def write_post(slug: str, body: str, faqs=None) -> int:
    path = BLOG / f"{slug}.md"
    old_fm, _ = parse_fm(path.read_text(encoding="utf-8"))
    path.write_text(
        fm_block(slug, old_fm, faqs) + "\n\n" + body.strip() + "\n",
        encoding="utf-8",
    )
    return wc(body)


def main():
    from b11_rw_bodies import BODIES, SKIP, FAQ_OVERRIDES  # noqa: E402

    slugs = load_slugs()
    results = []
    for slug in slugs:
        if slug in SKIP:
            w = wc((BLOG / f"{slug}.md").read_text(encoding="utf-8"))
            results.append((slug, "skip", w))
            continue
        if slug not in BODIES:
            results.append((slug, "missing", 0))
            continue
        faqs = FAQ_OVERRIDES.get(slug)
        w = write_post(slug, BODIES[slug], faqs)
        status = "ok" if w >= TARGET else "short"
        results.append((slug, status, w))

    ok = sum(1 for _, s, w in results if s in ("ok", "skip") and w >= TARGET)
    short = [r for r in results if r[1] == "short" or (r[1] == "skip" and r[2] < TARGET)]
    missing = [r for r in results if r[1] == "missing"]
    print(f"PASS {ok}/{len(slugs)} (target {TARGET}+ words)")
    if short:
        print(f"SHORT ({len(short)}):")
        for slug, _, w in short:
            print(f"  {slug}: {w}")
    if missing:
        print(f"MISSING ({len(missing)}):")
        for slug, _, _ in missing:
            print(f"  {slug}")
    return 1 if short or missing else 0


if __name__ == "__main__":
    sys.exit(main())
