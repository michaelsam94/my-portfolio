#!/usr/bin/env python3
"""Write complete unique b11_rw articles — loads bodies from JSON."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
BODIES_JSON = Path(__file__).parent / "b11_rw_bodies.json"
DATE = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")
SLUG_FILES = ["/tmp/b11_rw_0.txt", "/tmp/b11_rw_1.txt", "/tmp/b11_rw_2.txt"]

BANNED = (
    "Validate this in staging with production-like data volume",
    "Review 1: teams that treat",
    "assumptions age faster than code",
    "Production engineering for",
    "The gap between reading about",
    "If I were prioritizing one action this sprint",
    "Options compared honestly",
    "Pick based on traffic shape and failure cost",
    "Additional depth on",
    "Teams that treat this as a one-time checklist",
    "## Architecture and boundaries",
    "## Accessibility requirements",
    "## Common production mistakes",
)


def load_slugs() -> list[str]:
    slugs = []
    for f in SLUG_FILES:
        with open(f) as fh:
            slugs.extend(line.strip() for line in fh if line.strip())
    return slugs


def wc(text: str) -> int:
    if text.startswith("---"):
        text = text.split("---", 2)[2]
    return len(WORD.findall(text))


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def parse_fm(raw: str) -> dict:
    fm = raw.split("---", 2)[1]
    d: dict = {}
    for key in ("title", "description", "datePublished", "keywords"):
        m = re.search(rf'^{key}:\s*"([^"]*)"', fm, re.M)
        if m:
            d[key] = m.group(1)
    tags, on = [], False
    for line in fm.splitlines():
        if line.strip() == "tags:":
            on = True
            continue
        if on and line.startswith("  - "):
            tags.append(line[4:].strip().strip('"').strip("'"))
        elif on and line.strip() and not line.startswith(" "):
            break
    if tags:
        d["tags"] = tags
    faqs, q, on = [], None, False
    for line in fm.splitlines():
        if line.strip() == "faq:":
            on = True
            continue
        if not on:
            continue
        if line.startswith("  - q:"):
            q = line.split('"')[1] if '"' in line else line.split(":", 1)[1].strip()
        elif line.startswith("    a:") and q:
            faqs.append((q, line.split('"')[1] if '"' in line else line.split(":", 1)[1].strip()))
            q = None
    d["faq"] = faqs[:3]
    return d


def build_fm(meta: dict, slug: str) -> str:
    lines = [
        "---",
        f'title: "{esc(meta.get("title", slug))}"',
        f'slug: "{slug}"',
        f'description: "{esc(meta.get("description", ""))}"',
        f'datePublished: "{meta.get("datePublished", DATE)}"',
        f'dateModified: "{DATE}"',
        "tags:",
    ]
    for t in meta.get("tags", ["Engineering"]):
        lines.append(f'  - "{esc(t)}"')
    lines.append(f'keywords: "{esc(meta.get("keywords", slug))}"')
    lines.append("faq:")
    for q, a in meta.get("faq", [])[:3]:
        lines.append(f'  - q: "{esc(q)}"')
        lines.append(f'    a: "{esc(a)}"')
    lines.append("---")
    return "\n".join(lines)


def has_boilerplate(text: str) -> bool:
    return any(b in text for b in BANNED)


def main() -> int:
    bodies = json.loads(BODIES_JSON.read_text(encoding="utf-8"))
    slugs = load_slugs()
    results = []
    for slug in slugs:
        path = BLOG / f"{slug}.md"
        if slug not in bodies:
            results.append((slug, "missing", 0))
            continue
        body = bodies[slug].strip()
        w = wc(body)
        bad = has_boilerplate(body)
        if w < TARGET or bad:
            results.append((slug, "bad" if bad else "short", w))
            continue
        meta = parse_fm(path.read_text(encoding="utf-8"))
        meta["slug"] = slug
        path.write_text(build_fm(meta, slug) + "\n\n" + body + "\n", encoding="utf-8")
        results.append((slug, "ok", w))

    ok = sum(1 for _, s, w in results if s == "ok")
    print(f"PASS {ok}/{len(slugs)}")
    for slug, st, w in results:
        if st != "ok":
            print(f"  {st} {slug}: {w}w")
    return 0 if ok == len(slugs) else 1


if __name__ == "__main__":
    sys.exit(main())
