#!/usr/bin/env python3
"""Patch ONLY failing b11_w0 slugs — never overwrite passing posts."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOG = ROOT / "content/blog"
DATE = "2026-07-17"
WORD = re.compile(r"\b[\w'-]+\b")
TARGET = 1200
BANNED = [
    "Validate this in staging",
    "Additional production considerations",
    "Measuring success in production",
    "We keep a living FAQ",
    "Document the decision, owner",
    "production pattern for frontend",
    "Architecture and boundaries",
    "The gap between reading about",
]

sys_path = Path(__file__).parent
import sys
sys.path.insert(0, str(sys_path))
from b11_w0_complete import POSTS as _complete_posts  # noqa: E402

_bodies: dict = {}
exec(open(sys_path / "b11_w0_complete_bodies.py").read(), {"POSTS": _bodies})
POSTS = {**_complete_posts, **_bodies}

FAQ_FIX: dict[str, list[tuple[str, str]]] = {
    "seo-javascript-rendering-crawl": [
        ("Can Google index JavaScript-rendered content?", "Yes, via headless Chromium in a second crawl wave, but rendering consumes crawl budget and adds delay. Critical content should appear in the initial HTML response."),
        ("What is crawl budget?", "The number of URLs Googlebot fetches per day on your site. Large slow sites hit limits; small sites rarely need to worry unless crawl waste from faceted URLs is high."),
        ("SSR or static generation for SEO?", "Server-render or statically generate indexable public pages. Client-side rendering alone is acceptable for authenticated app shells behind login."),
    ],
    "seo-meta-robots-noindex-patterns": [
        ("noindex vs robots.txt disallow?", "disallow prevents crawling but URLs may still appear as link-only results. noindex allows crawl but excludes from search results — use noindex when you need Google to see canonical signals on duplicate URLs."),
        ("Should staging use noindex?", "Yes, plus authentication. noindex is not access control — it only asks crawlers not to index."),
        ("When to noindex faceted URLs?", "Multi-filter combinations producing thin duplicate content. Keep the base category indexable with follow links to facets users need."),
    ],
}

STRIP = [
    r"\n## Common production mistakes\n[\s\S]*?(?=\n## Resources|\Z)",
    r"The gap between reading about[\s\S]*?\n\n",
    r"## Architecture and boundaries[\s\S]*?(?=\n## |\n## Resources|\Z)",
    r"## Implementation patterns[\s\S]*?(?=\n## |\n## Resources|\Z)",
    r"Validate this in staging[\s\S]*?(?=\n\n|\Z)",
    r"Document the decision, owner[\s\S]*?(?=\n\n|\Z)",
    r"\n## Operating [^\n]+\n[\s\S]*?(?=\n## |\Z)",
    r"\n## Follow-up\n[\s\S]*?(?=\n## |\Z)",
]


def wc(text: str) -> int:
    return len(WORD.findall(text))


def strip_body(body: str) -> str:
    for pat in STRIP:
        body = re.sub(pat, "", body, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def check(text: str) -> dict:
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {"ok": False, "words": 0, "faq": 0, "banned": True, "dm": "MISSING"}
    fm, body = parts[1], parts[2]
    w = wc(body)
    faq = len(re.findall(r"^\s*-\s+q:", fm, re.M))
    bad = any(b in text for b in BANNED)
    dm = re.search(r'dateModified: "([^"]+)"', fm)
    dm_val = dm.group(1) if dm else "MISSING"
    ok = w >= TARGET and faq == 3 and not bad and dm_val == DATE
    return {"ok": ok, "words": w, "faq": faq, "banned": bad, "dm": dm_val}


def build_fm(fm: str, faqs: list[tuple[str, str]] | None = None) -> str:
    fm = re.sub(r'^dateModified:.*$', f'dateModified: "{DATE}"', fm, flags=re.M)
    if faqs:
        lines, in_faq, skip = [], False, False
        for line in fm.splitlines():
            if line.strip() == "faq:":
                in_faq, skip = True, True
                lines.append(line)
                continue
            if skip:
                if line.startswith("  - q:") or line.startswith("    a:"):
                    continue
                skip = False
            if in_faq:
                for q, a in faqs:
                    lines.append(f'  - q: "{q}"')
                    lines.append(f'    a: "{a}"')
                in_faq = False
                continue
            lines.append(line)
        fm = "\n".join(lines)
    return fm.strip()


def git_head(slug: str) -> str:
    r = subprocess.run(
        ["git", "show", f"HEAD:content/blog/{slug}.md"],
        cwd=ROOT, capture_output=True, text=True,
    )
    return r.stdout if r.returncode == 0 else ""


def write_post(slug: str, text: str) -> dict:
    path = BLOG / f"{slug}.md"
    path.write_text(text, encoding="utf-8")
    return check(path.read_text(encoding="utf-8"))


def main() -> None:
    slugs = Path("/tmp/b11_w0.txt").read_text().strip().split("\n")
    results = []
    for slug in slugs:
        path = BLOG / f"{slug}.md"
        cur = path.read_text(encoding="utf-8") if path.exists() else ""
        status = check(cur)
        if status["ok"]:
            results.append({"slug": slug, **status})
            continue

        # Prefer full rewrite from POSTS if available and better
        if slug in POSTS:
            candidate = POSTS[slug]
            cstatus = check(candidate)
            if cstatus["words"] >= status["words"] and not cstatus["banned"]:
                text = candidate
                if slug in FAQ_FIX and "production pattern for frontend" in text:
                    p = text.split("---", 2)
                    fm = build_fm(p[1], FAQ_FIX[slug])
                    text = f"---\n{fm}\n---\n{p[2]}"
                text = re.sub(r'^dateModified:.*$', f'dateModified: "{DATE}"', text, flags=re.M)
                status = write_post(slug, text if text.endswith("\n") else text + "\n")
                results.append({"slug": slug, **status})
                continue

        # Else restore best of cur/head, strip boilerplate, fix FAQ
        head = git_head(slug)
        best = cur
        if head and wc(head.split("---", 2)[2]) > wc(cur.split("---", 2)[2] if cur.count("---") >= 2 else cur):
            best = head
        parts = best.split("---", 2)
        if len(parts) < 3:
            results.append({"slug": slug, "ok": False, "words": 0})
            continue
        fm = build_fm(parts[1], FAQ_FIX.get(slug))
        body = strip_body(parts[2])
        text = f"---\n{fm}\n---\n\n{body}\n"
        status = write_post(slug, text)
        results.append({"slug": slug, **status})

    done = sum(1 for r in results if r.get("ok"))
    samples = sorted([(r["slug"], r["words"]) for r in results if r.get("ok")], key=lambda x: -x[1])[:3]
    print(json.dumps({"done": done, "total": len(slugs), "samples": samples, "fail": [r for r in results if not r.get("ok")]}, indent=2))


if __name__ == "__main__":
    main()
