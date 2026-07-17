#!/usr/bin/env python3
"""Generate unique ≥1200-word b11_rw posts — no template boilerplate."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content/blog"
DATE = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")

SLUG_FILES = ["/tmp/b11_rw_2.txt", "/tmp/b11_rw_3.txt"]

BANNED = (
    "Validate this in staging with production-like data volume",
    "Review 1: teams that treat",
    "assumptions age faster than code",
    "Production engineering for",
    "Operating ",
    "after traffic shifts",
    "## Architecture and boundaries",
    "## Accessibility requirements",
    "## Common production mistakes",
    "## Debugging and triage workflow",
    "Additional depth on",
    "Teams that treat this as a one-time checklist",
    "The gap between reading about",
    "If I were prioritizing one action this sprint",
    "Options compared honestly",
    "Pick based on traffic shape and failure cost",
    "Regarding **",
    "Teams that skip this slice of the problem",
    "Field-validate on mid-tier Android",
    "Compare p75 on mid-tier Android",
    "Document rollback steps in the PR before merge",
    "Staging lies",
    "Manual paths: hard refresh mid-flow",
)

SKIP = set()  # slugs already good


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
    return len(WORD.findall(text))


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def parse_fm(raw: str) -> dict:
    fm = raw.split("---", 2)[1]
    d = {"slug": ""}
    m = re.search(r'^title:\s*"([^"]*)"', fm, re.M)
    if m:
        d["title"] = m.group(1)
    for key in ("description", "datePublished", "keywords"):
        m = re.search(rf'^{key}:\s*"([^"]*)"', fm, re.M)
        if m:
            d[key] = m.group(1)
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


def git_body(slug: str) -> str | None:
    try:
        raw = subprocess.check_output(
            ["git", "show", f"HEAD:content/blog/{slug}.md"],
            text=True,
            cwd=ROOT,
        )
        return raw.split("---", 2)[2]
    except subprocess.CalledProcessError:
        return None


def strip_boilerplate(body: str) -> str:
    for b in BANNED:
        while b in body:
            idx = body.index(b)
            # remove paragraph containing banned phrase
            start = body.rfind("\n\n", 0, idx)
            end = body.find("\n\n", idx)
            if end == -1:
                end = len(body)
            body = body[: start + 1] + body[end:]
    body = re.sub(r"\n## Field validation:[^\n]*\n.*?(?=\n## |\Z)", "", body, flags=re.S)
    body = re.sub(r"\n## Operating [^\n]+\n.*?(?=\n## |\Z)", "", body, flags=re.S)
    body = re.sub(r"\n## Additional depth on[^\n]*\n.*?(?=\n## |\Z)", "", body, flags=re.S)
    body = re.sub(r"\n## Closing notes\n.*?(?=\n## |\Z)", "", body, flags=re.S)
    body = re.sub(r"\n## Closing\n.*?(?=\n## |\Z)", "", body, flags=re.S)
    body = re.sub(r"\n## Summary\n.*?(?=\n## |\Z)", "", body, flags=re.S)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def has_boilerplate(text: str) -> bool:
    return any(b in text for b in BANNED)


# Import unique expansions
from b11_rw_expansions import EXPANSIONS  # noqa: E402
from b11_rw_supplements import SUPPLEMENTAL  # noqa: E402


def build_article(slug: str, body: str) -> str:
    body = strip_boilerplate(body)
    expansions = EXPANSIONS.get(slug, [])
    for section in expansions:
        if section.strip() and section.strip() not in body:
            if "## Resources" in body:
                body = body.replace("## Resources", section + "\n\n## Resources", 1)
            else:
                body += "\n\n" + section
    return body.strip()


def process(slug: str) -> dict:
    path = BLOG / f"{slug}.md"
    if slug in SKIP and path.exists():
        raw = path.read_text(encoding="utf-8")
        body = raw.split("---", 2)[2]
        w = wc(body)
        if w >= TARGET and not has_boilerplate(raw):
            meta = parse_fm(raw)
            meta["slug"] = slug
            fm = build_fm(meta, slug)
            path.write_text(fm + "\n\n" + body.strip() + "\n", encoding="utf-8")
            return {"slug": slug, "status": "skip", "words": w}

    raw = path.read_text(encoding="utf-8")
    meta = parse_fm(raw)
    meta["slug"] = slug

    # Prefer git HEAD core content if current is template garbage
    base = git_body(slug) or raw.split("---", 2)[2]
    body = build_article(slug, base)
    w = wc(body)

    if w < TARGET:
        # still write if we can expand further in a future pass; try supplemental
        extra = SUPPLEMENTAL.get(slug, "")
        if extra and extra.strip() not in body:
            if "## Resources" in body:
                body = body.replace("## Resources", extra + "\n\n## Resources", 1)
            else:
                body += "\n\n" + extra
            w = wc(body)

    if w < TARGET:
        return {"slug": slug, "status": "short", "words": w}

    if has_boilerplate(body):
        return {"slug": slug, "status": "boilerplate", "words": w}

    fm = build_fm(meta, slug)
    path.write_text(fm + "\n\n" + body + "\n", encoding="utf-8")
    return {"slug": slug, "status": "ok", "words": w}


def main():
    slugs = load_slugs()
    results = [process(s) for s in slugs]
    ok = sum(1 for r in results if r["status"] in ("ok", "skip") and r["words"] >= TARGET)
    bad = [r for r in results if r["status"] not in ("ok", "skip") or r["words"] < TARGET]
    print(f"PASS {ok}/{len(slugs)}")
    for r in bad:
        print(f"  {r['status']} {r['slug']}: {r['words']}w")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
