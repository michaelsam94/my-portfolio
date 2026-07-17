#!/usr/bin/env python3
"""Restore b11s_3/4/5 posts: prefer clean ≥1200w content, git HEAD fallback, dateModified 2026-07-17."""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
DATE = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")

SLUG_FILES = ["/tmp/b11s_3.txt", "/tmp/b11s_4.txt", "/tmp/b11s_5.txt"]

BANNED_PHRASES = (
    "Validate this in staging with production-like data volume",
    "If I were prioritizing one action this sprint",
    "Options compared honestly",
    "When teams skip this layer",
    "is a production pattern for frontend and product engineering teams",
    "Teams ship without field measurement",
    "What is the main production risk with",
    "Adopt when you have field data or user research showing pain",
    "A concrete playbook for",
    "Security work around",
    "Architecture depth for ",
    "Deep implementation notes",
    "On-call and regression guards",
    "Pick based on traffic shape and failure cost",
)

GENERIC_FAQ = (
    "is a production pattern for frontend",
    "Teams ship without field measurement",
    "What is the main production risk with",
)

# Paragraph-level removal for known template blocks
PARA_STRIP = [
    re.compile(r"\n## A concrete playbook for[^\n]*\n.*?(?=\n## |\Z)", re.S),
    re.compile(r"\n### Controls that actually change outcomes\n.*?(?=\n## |\Z)", re.S),
    re.compile(r"\n### Incident-shaped verification\n.*?(?=\n## |\Z)", re.S),
    re.compile(r"\n### Measurement\nTrack mean time to remediate findings related to.*?(?=\n## |\Z)", re.S),
    re.compile(r"\n### Pitfalls specific to this domain\n.*?(?=\n## |\Z)", re.S),
]


def load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


EX2 = load_module("ex2", "expand_batch11_chunk2.py")
R22 = load_module("r22", "_rewrite_22_expansions.py")
FR = load_module("fr", "b11_final_rewrite.py")
RWE = load_module("rwe", "b11_rw_expansions.py")


def load_slugs() -> list[str]:
    slugs = []
    for f in SLUG_FILES:
        with open(f) as fh:
            slugs.extend(line.strip() for line in fh if line.strip())
    return slugs


def wc(text: str) -> int:
    return len(WORD.findall(text))


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def git_raw(slug: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "show", f"HEAD:content/blog/{slug}.md"],
            text=True,
            cwd=ROOT,
        )
    except subprocess.CalledProcessError:
        return None


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
            a = line.split('"')[1] if '"' in line else line.split(":", 1)[1].strip()
            faqs.append((q, a))
            q = None
    d["faq"] = faqs[:3]
    return d


def faq_generic(faqs: list[tuple[str, str]]) -> bool:
    blob = " ".join(q + a for q, a in faqs)
    return any(g in blob for g in GENERIC_FAQ)


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


def strip_banned(body: str) -> str:
    for pat in PARA_STRIP:
        body = pat.sub("\n", body)
    paragraphs = body.split("\n\n")
    clean = []
    for para in paragraphs:
        if any(b in para for b in BANNED_PHRASES):
            continue
        clean.append(para)
    body = "\n\n".join(clean)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def has_banned(text: str) -> bool:
    return any(b in text for b in BANNED_PHRASES)


def pick_meta(slug: str, cur_raw: str, head_raw: str | None) -> dict:
    cur_m = parse_fm(cur_raw)
    head_m = parse_fm(head_raw) if head_raw else {}
    meta = head_m if head_m.get("title") else cur_m
    if faq_generic(meta.get("faq", [])):
        if not faq_generic(cur_m.get("faq", [])):
            meta["faq"] = cur_m["faq"]
        elif head_m.get("faq") and not faq_generic(head_m.get("faq", [])):
            meta["faq"] = head_m["faq"]
    for k in ("description", "tags", "keywords"):
        if not meta.get(k) and cur_m.get(k):
            meta[k] = cur_m[k]
    return meta


def gather_expansions(slug: str) -> list[str]:
    parts: list[str] = []
    for src in (
        R22.EXPANSIONS.get(slug, ""),
        EX2.EXPANSIONS.get(slug, ""),
        FR.UNIQUE.get(slug, ""),
    ):
        if isinstance(src, str) and src.strip():
            parts.append(src.strip())
    rwe = RWE.EXPANSIONS.get(slug, [])
    if isinstance(rwe, list):
        parts.extend(s.strip() for s in rwe if s.strip())
    out: list[str] = []
    for p in parts:
        if p not in out:
            out.append(p)
    return out


def augment_body(slug: str, body: str) -> str:
    for exp in gather_expansions(slug):
        if exp not in body:
            if "## Resources" in body:
                body = body.replace("## Resources", exp + "\n\n## Resources", 1)
            else:
                body += "\n\n" + exp
    return body.strip()


def process(slug: str) -> tuple[str, int, bool]:
    path = BLOG / f"{slug}.md"
    cur_raw = path.read_text(encoding="utf-8")
    head_raw = git_raw(slug)
    meta = pick_meta(slug, cur_raw, head_raw)

    candidates = []
    for label, raw in [("cur", cur_raw), ("head", head_raw)]:
        if not raw:
            continue
        body = strip_banned(raw.split("---", 2)[2])
        body = augment_body(slug, body)
        w = wc(body)
        banned = has_banned(body)
        candidates.append((w, banned, body, label))

    # Prefer non-banned; then highest word count
    good = [c for c in candidates if not c[1] and c[0] >= TARGET]
    pool = good if good else [c for c in candidates if not c[1]] or candidates
    pool.sort(key=lambda x: -x[0])
    best_w, best_banned, best_body, _ = pool[0]

    if best_w < TARGET:
        return "short", best_w, True

    if best_banned:
        return "banned", best_w, True

    if len(meta.get("faq", [])) < 3:
        return "faq", best_w, True

    path.write_text(build_fm(meta, slug) + "\n\n" + best_body + "\n", encoding="utf-8")
    return "ok", best_w, False


def main() -> int:
    slugs = load_slugs()
    results = []
    for slug in slugs:
        status, w, bad = process(slug)
        results.append((slug, status, w))

    ok = sum(1 for _, s, _ in results if s == "ok")
    print(f"PASS {ok}/{len(slugs)}")
    for slug, status, w in sorted(results):
        mark = "✓" if status == "ok" else "✗"
        print(f"{mark} {w:4d}  {status:8s}  {slug}")
    return 0 if ok == len(slugs) else 1


if __name__ == "__main__":
    sys.exit(main())
