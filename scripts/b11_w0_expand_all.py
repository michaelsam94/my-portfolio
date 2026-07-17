#!/usr/bin/env python3
"""Expand all b11_w0 slugs to >=1200 words using POSTS + unique sections."""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOG = ROOT / "content/blog"
SCRIPTS = Path(__file__).parent
DATE = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")

spec = importlib.util.spec_from_file_location("b11_w0_complete", SCRIPTS / "b11_w0_complete.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
POSTS: dict[str, str] = mod.POSTS

# Import EXPAND from finalize
spec2 = importlib.util.spec_from_file_location("fin", SCRIPTS / "b11_w0_finalize.py")
fin = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(fin)
EXPAND = fin.EXPAND
FAQS = fin.FAQS
build_fm = fin.build_fm
parse_meta = fin.parse_meta
extract_faq = fin.extract_faq
strip_body = fin.strip_body
has_banned = fin.has_banned
git_head = fin.git_head


def wc(t: str) -> int:
    return len(WORD.findall(t))


def expand_body(slug: str, body: str) -> str:
    for section in EXPAND.get(slug, []):
        if wc(body) >= TARGET:
            break
        if section.strip() not in body:
            body += "\n\n" + section.strip()
    if wc(body) < TARGET:
        gh = git_head(slug)
        if gh.count("---") >= 2:
            gh_body = strip_body(gh.split("---", 2)[2])
            for section in re.split(r"\n(?=## )", gh_body):
                if wc(body) >= TARGET:
                    break
                s = section.strip()
                if s and s not in body and not has_banned(s):
                    body += "\n\n" + s
    return body


def main() -> None:
    slugs = Path("/tmp/b11_w0.txt").read_text().strip().split("\n")
    results = []
    for slug in slugs:
        path = BLOG / f"{slug}.md"
        source = POSTS.get(slug) or (path.read_text(encoding="utf-8") if path.exists() else git_head(slug))
        if source.count("---") < 2:
            results.append({"slug": slug, "ok": False})
            continue
        parts = source.split("---", 2)
        meta = parse_meta(parts[1], slug)
        faqs = FAQS.get(slug) or extract_faq(parts[1])
        if len(faqs) < 3:
            gh = git_head(slug)
            if gh.count("---") >= 2:
                faqs = extract_faq(gh.split("---", 2)[1]) or faqs
        bodies = [strip_body(parts[2])]
        if slug in POSTS and POSTS[slug].count("---") >= 2:
            bodies.append(strip_body(POSTS[slug].split("---", 2)[2]))
        if path.exists():
            cur = path.read_text(encoding="utf-8")
            if cur.count("---") >= 2:
                bodies.append(strip_body(cur.split("---", 2)[2]))
        gh = git_head(slug)
        if gh.count("---") >= 2:
            bodies.append(strip_body(gh.split("---", 2)[2]))
        bodies = [b for b in bodies if b and not has_banned(b)]
        body = max(bodies, key=wc) if bodies else ""
        body = expand_body(slug, body)
        fm = build_fm(meta, faqs[:3])
        path.write_text(f"{fm}\n\n{body.strip()}\n", encoding="utf-8")
        text = path.read_text()
        w = wc(text.split("---", 2)[2])
        ok = w >= TARGET and len(faqs) >= 3 and not has_banned(text)
        results.append({"slug": slug, "ok": ok, "words": w})

    done = sum(1 for r in results if r.get("ok"))
    samples = sorted([(r["slug"], r["words"]) for r in results if r.get("ok")], key=lambda x: -x[1])[:3]
    print(json.dumps({"done": done, "samples": samples, "fail": [r for r in results if not r.get("ok")]}, indent=2))


if __name__ == "__main__":
    main()
