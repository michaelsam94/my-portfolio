#!/usr/bin/env python3
"""Write unique ≥1200-word bodies for all b11_need slugs."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
DATE = "2026-07-17"
WORD = re.compile(r"\b[\w'-]+\b")

SLUGS = (
    open("/tmp/b11_need_0.txt").read().split()
    + open("/tmp/b11_need_1.txt").read().split()
)


def wc(t: str) -> int:
    return len(WORD.findall(t))


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
                tags.append(line[4:].strip().strip('"'))
            else:
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
            q = line.split('"')[1]
        elif line.startswith("    a:") and q:
            out.append((q, line.split('"')[1]))
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


def write(slug: str, body: str, faqs=None):
    path = BLOG / f"{slug}.md"
    old_fm, _ = parse_fm(path.read_text(encoding="utf-8"))
    path.write_text(fm_block(slug, old_fm, faqs) + "\n\n" + body.strip() + "\n", encoding="utf-8")
    return wc(body)


# Import all article bodies
from b11_need_bodies import BODIES, FAQ_OVERRIDES  # noqa: E402


def main():
    results = []
    for slug in SLUGS:
        if slug == "rust-web-toolchain":
            results.append((slug, "skip", wc(parse_fm((BLOG / f"{slug}.md").read_text())[1])))
            continue
        if slug not in BODIES:
            results.append((slug, "missing", 0))
            continue
        faqs = FAQ_OVERRIDES.get(slug)
        w = write(slug, BODIES[slug], faqs)
        results.append((slug, "ok" if w >= 1200 else "short", w))
    done = sum(1 for _, s, w in results if s in ("ok", "skip") and w >= 1200)
    print(f"DONE={done}/{len(SLUGS)}")
    for slug, st, w in results:
        if st not in ("ok", "skip") or w < 1200:
            print(f"  {st} {slug}: {w}w")
    samples = sorted([(s, w) for s, st, w in results if w >= 1200], key=lambda x: -x[1])[:3]
    for s, w in samples:
        print(f"SAMPLE {s}: {w}w")


if __name__ == "__main__":
    main()
