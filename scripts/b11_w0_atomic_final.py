#!/usr/bin/env python3
"""Single-process atomic finalize for all b11_w0 slugs."""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOG = ROOT / "content/blog"
SCRIPTS = Path(__file__).parent
DATE = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")
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

STRIP = [
    r"\n## Common production mistakes\n[\s\S]*?(?=\n## Resources|\Z)",
    r"\n## Deep dive[^\n]*\n[\s\S]*?(?=\n## |\n## Resources|\Z)",
    r"The gap between reading about[\s\S]*?\n\n",
    r"## Architecture and boundaries[\s\S]*?(?=\n## |\n## Resources|\Z)",
    r"## Implementation patterns[\s\S]*?(?=\n## |\n## Resources|\Z)",
    r"Validate this in staging[\s\S]*?(?=\n\n|\Z)",
    r"Document the decision, owner[\s\S]*?(?=\n\n|\Z)",
    r"\n## Operating [^\n]+\n[\s\S]*?(?=\n## |\Z)",
    r"\n## Follow-up\n[\s\S]*?(?=\n## |\Z)",
    r"\n## Rollout and ownership\n[\s\S]*?(?=\n## |\Z)",
]


def wc(t: str) -> int:
    return len(WORD.findall(t))


def strip_body(body: str) -> str:
    for pat in STRIP:
        body = re.sub(pat, "", body, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def has_banned(text: str) -> bool:
    return any(b in text for b in BANNED)


def git_head(slug: str) -> str:
    r = subprocess.run(
        ["git", "show", f"HEAD:content/blog/{slug}.md"],
        cwd=ROOT, capture_output=True, text=True,
    )
    return r.stdout if r.returncode == 0 else ""


def load_posts() -> dict[str, str]:
    spec = importlib.util.spec_from_file_location("c", SCRIPTS / "b11_w0_complete.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.POSTS


def load_expand():
    spec = importlib.util.spec_from_file_location("fin", SCRIPTS / "b11_w0_finalize.py")
    fin = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fin)
    return fin


def main() -> None:
    slugs = Path("/tmp/b11_w0.txt").read_text().strip().split("\n")
    posts = load_posts()
    fin = load_expand()
    EXPAND = fin.EXPAND
    FAQS = fin.FAQS
    outputs: dict[str, str] = {}

    for slug in slugs:
        path = BLOG / f"{slug}.md"
        cur = path.read_text(encoding="utf-8") if path.exists() else ""
        gh = git_head(slug)
        bodies = []
        if slug in posts and posts[slug].count("---") >= 2:
            bodies.append(strip_body(posts[slug].split("---", 2)[2]))
        if cur.count("---") >= 2:
            bodies.append(strip_body(cur.split("---", 2)[2]))
        if gh.count("---") >= 2:
            bodies.append(strip_body(gh.split("---", 2)[2]))
        bodies = [b for b in bodies if b]
        body = max(bodies, key=wc) if bodies else ""
        for section in EXPAND.get(slug, []):
            if wc(body) >= TARGET:
                break
            if section.strip() not in body:
                body += "\n\n" + section.strip()
        if wc(body) < TARGET and gh.count("---") >= 2:
            for section in re.split(r"\n(?=## )", strip_body(gh.split("---", 2)[2])):
                if wc(body) >= TARGET:
                    break
                s = section.strip()
                if s and s not in body and not has_banned(s) and not s.startswith("## Deep dive"):
                    body += "\n\n" + s
        src = posts.get(slug) or cur or gh
        meta = fin.parse_meta(src.split("---", 2)[1], slug)
        faqs = FAQS.get(slug) or fin.extract_faq(src.split("---", 2)[1])
        if len(faqs) < 3 and gh.count("---") >= 2:
            faqs = fin.extract_faq(gh.split("---", 2)[1]) or faqs
        fm = fin.build_fm(meta, faqs[:3])
        outputs[slug] = f"{fm}\n\n{body.strip()}\n"

    for slug, text in outputs.items():
        (BLOG / f"{slug}.md").write_text(text, encoding="utf-8")

    results = []
    for slug in slugs:
        t = outputs[slug]
        w = wc(t.split("---", 2)[2])
        faq = len(re.findall(r"^\s*-\s+q:", t.split("---", 2)[1], re.M))
        bad = has_banned(t)
        ok = w >= TARGET and faq == 3 and not bad
        results.append({"slug": slug, "ok": ok, "words": w, "banned": bad})
    done = sum(1 for r in results if r["ok"])
    samples = sorted([(r["slug"], r["words"]) for r in results if r["ok"]], key=lambda x: -x[1])[:3]
    print(json.dumps({"done": done, "samples": samples, "fail": [r for r in results if not r["ok"]]}, indent=2))


if __name__ == "__main__":
    main()
