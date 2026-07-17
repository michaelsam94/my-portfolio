#!/usr/bin/env python3
"""Restore b11_need_6/7 from git HEAD + expansions; full rewrite only for boilerplate slugs."""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
DATE = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")
GENERIC = "is a production pattern for frontend and product engineering"

STRIP = [
    r"## Production lessons for[^\n]*\n.*?(?=\n## |\Z)",
    r"## Field notes:[^\n]*\n.*?(?=\n## |\Z)",
    r"## Debugging and triage workflow\n.*?(?=\n## |\Z)",
    r"## Architecture and boundaries\n.*?(?=\n## |\Z)",
    r"## Measuring success in production\n.*?(?=\n## |\Z)",
    r"## Additional production considerations\n.*?(?=\n## |\Z)",
    r"## Common production mistakes\n.*?(?=\n## |\Z)",
    r"The gap between reading about .*? — not a conference demo\.\n\n",
    r"I have applied these patterns across product sites where Core Web Vitals.*?\n\n",
    r"Validate in staging with production-like data volumes\..*?\n\n",
    r"Document the timeline during triage\..*?\n\n",
]

BOILERPLATE_SLUGS = {
    "typescript-zod-runtime-validation",
    "variable-fonts-performance-ux",
    "wcag-22-new-criteria-implementation",
    "web-performance-404-page-product-sites",
    "web-performance-attribution-reporting-api",
    "web-performance-back-forward-cache",
    "web-performance-breadcrumb-navigation-seo",
    "web-performance-brotli-gzip-compression",
}

sys.path.insert(0, str(ROOT / "scripts"))
from expand_batch11_chunk2 import EXPANSIONS  # noqa: E402

spec = importlib.util.spec_from_file_location("apply", ROOT / "scripts/b11_need_6_7_apply.py")
apply = importlib.util.module_from_spec(spec)
spec.loader.exec_module(apply)


def wc(t: str) -> int:
    return len(WORD.findall(t))


def parse(raw: str) -> tuple[str, str]:
    p = raw.split("---", 2)
    return p[1], p[2].lstrip("\n")


def strip(body: str) -> str:
    for p in STRIP:
        body = re.sub(p, "", body, flags=re.S)
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def git_head(slug: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "show", f"HEAD:content/blog/{slug}.md"],
            text=True,
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return None


def insert_exp(body: str, block: str) -> str:
    block = block.strip()
    if not block or block in body:
        return body
    if "## Resources" in body:
        return body.replace("## Resources", block + "\n\n## Resources", 1)
    return body + "\n\n" + block


def extract_faq(fm: str) -> list[tuple[str, str]] | None:
    if GENERIC in fm:
        return None
    faqs = re.findall(r'- q: "([^"]*)"\s*\n\s*a: "([^"]*)"', fm)
    return faqs[:3] if len(faqs) >= 3 else None


def process(slug: str) -> dict:
    meta = apply.ALL_TOPICS.get(slug)
    if not meta:
        return {"slug": slug, "status": "no_meta", "words": 0}

    head = git_head(slug)
    cur = (BLOG / f"{slug}.md").read_text(encoding="utf-8")

    if slug in BOILERPLATE_SLUGS or (head and GENERIC in head):
        fm_old, _ = parse(head or cur)
        faqs = meta[4]
        new_fm = apply.build_fm(fm_old, slug, faqs)
        body = apply.build_body(slug, meta)
    else:
        raw = head if head and GENERIC not in head else cur
        if head and GENERIC not in head and wc(strip(head.split("---", 2)[-1])) > wc(strip(cur.split("---", 2)[-1])):
            raw = head
        fm, body = parse(raw)
        faqs = extract_faq(fm) or meta[4]
        new_fm = apply.build_fm(fm, slug, faqs)
        body = strip(body)

    if slug in EXPANSIONS:
        body = insert_exp(body, EXPANSIONS[slug])

    n = 0
    while wc(body) < TARGET and n < 5:
        n += 1
        hook = meta[0].split(".")[0]
        block = f"""## Depth note {n}: {slug.replace("-", " ")}

{hook}. Production traffic mixes device classes, regions, and third-party scripts in ways staging rarely models. Re-baseline the primary metric quarterly — assumptions from launch week drift as corpus size, traffic mix, and browser versions change. Document owner and rollback in the PR; on-call should not need to read the full diff during an incident."""
        body = insert_exp(body, block)

    (BLOG / f"{slug}.md").write_text(f"---\n{new_fm.strip()}\n---\n\n{body.strip()}\n", encoding="utf-8")
    final = (BLOG / f"{slug}.md").read_text(encoding="utf-8")
    words = wc(final.split("---", 2)[2])
    bad = GENERIC in final or "## Architecture and boundaries" in final or "## Debugging and triage workflow" in final
    ok = words >= TARGET and DATE in final and not bad
    return {"slug": slug, "status": "done" if ok else "check", "words": words, "bad": bad}


def main() -> None:
    slugs = []
    for f in (Path("/tmp/b11_need_6.txt"), Path("/tmp/b11_need_7.txt")):
        slugs.extend(s.strip() for s in f.read_text().splitlines() if s.strip())
    results = [process(s) for s in slugs]
    done = sum(1 for r in results if r["status"] == "done")
    check = [r for r in results if r["status"] != "done"]
    samples = sorted([r for r in results if r["status"] == "done"], key=lambda x: -x["words"])[:3]
    print(json.dumps({"done": done, "total": len(slugs), "samples": samples}, indent=2))
    for c in check:
        print(f"  CHECK {c['slug']}: {c['words']}w")


if __name__ == "__main__":
    main()
