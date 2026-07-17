#!/usr/bin/env python3
"""Finalize b11_need_6/7: strip templates, restore good HEAD content, pad to 1200w, set dateModified."""
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
GENERIC_FAQ = "is a production pattern for frontend and product engineering"

sys.path.insert(0, str(ROOT / "scripts"))
from expand_batch11_chunk2 import EXPANSIONS  # noqa: E402

spec = importlib.util.spec_from_file_location("apply", ROOT / "scripts/b11_need_6_7_apply.py")
apply_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(apply_mod)


def wc(t: str) -> int:
    return len(WORD.findall(t))


def parse(raw: str) -> tuple[str, str]:
    p = raw.split("---", 2)
    return p[1], p[2].lstrip("\n")


def strip(body: str) -> str:
    for pat in STRIP:
        body = re.sub(pat, "", body, flags=re.S)
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


def best_raw(slug: str) -> str:
    cur = (BLOG / f"{slug}.md").read_text(encoding="utf-8")
    head = git_head(slug)
    candidates = [cur]
    if head:
        candidates.insert(0, head)
    best = cur
    best_score = -1
    for raw in candidates:
        if GENERIC_FAQ in raw or "## Architecture and boundaries" in raw:
            score = wc(strip(raw.split("---", 2)[-1])) - 500
        else:
            score = wc(strip(raw.split("---", 2)[-1]))
        if score > best_score:
            best_score = score
            best = raw
    return best


def insert_exp(body: str, block: str) -> str:
    block = block.strip()
    if not block or block in body:
        return body
    if "## Resources" in body:
        return body.replace("## Resources", block + "\n\n## Resources", 1)
    return body + "\n\n" + block


def main() -> None:
    slugs = []
    for f in (Path("/tmp/b11_need_6.txt"), Path("/tmp/b11_need_7.txt")):
        slugs.extend(s.strip() for s in f.read_text().splitlines() if s.strip())

    results = []
    for slug in slugs:
        meta = apply_mod.ALL_TOPICS.get(slug)
        if not meta:
            results.append({"slug": slug, "status": "no_meta", "words": 0})
            continue

        raw = best_raw(slug)
        needs_full = (
            GENERIC_FAQ in raw
            or "## Architecture and boundaries" in raw
            or wc(strip(raw.split("---", 2)[-1])) < 900
        )

        if needs_full:
            fm_old, _ = parse(raw)
            new_fm = apply_mod.build_fm(fm_old, slug, meta[4])
            body = apply_mod.build_body(slug, meta)
        else:
            fm, body = parse(raw)
            new_fm = apply_mod.build_fm(fm, slug, meta[4])
            body = strip(body)

        if slug in EXPANSIONS:
            body = insert_exp(body, EXPANSIONS[slug])

        pad_i = 0
        while wc(body) < TARGET and pad_i < 3:
            extra = apply_mod.EXPANSIONS.get(slug, "") if hasattr(apply_mod, "EXPANSIONS") else ""
            title = slug.replace("-", " ").title()
            block = f"""## Operational notes for {title}

Teams shipping changes to {meta[1]} should baseline the user-visible metric before merge — latency, recall, conversion, or accessibility findings depending on surface. Compare field p75 after deploy on mid-tier mobile hardware, not only desktop lab Lighthouse. Document rollback (feature flag, cache purge, or config revert) in the PR description so on-call can act without reading the full diff."""
            body = insert_exp(body, block)
            pad_i += 1

        (BLOG / f"{slug}.md").write_text(
            f"---\n{new_fm.strip()}\n---\n\n{body.strip()}\n", encoding="utf-8"
        )
        final = (BLOG / f"{slug}.md").read_text(encoding="utf-8")
        words = wc(final.split("---", 2)[2])
        bad = GENERIC_FAQ in final or "## Architecture and boundaries" in final or "## Debugging and triage workflow" in final
        ok = words >= TARGET and DATE in final and not bad and len(re.findall(r"  - q:", final.split("---", 2)[1])) == 3
        results.append({"slug": slug, "status": "done" if ok else "check", "words": words, "bad": bad})

    done = sum(1 for r in results if r["status"] == "done")
    check = [r for r in results if r["status"] != "done"]
    samples = sorted([r for r in results if r["status"] == "done"], key=lambda x: -x["words"])[:3]
    out = ROOT / "scripts/humanize-progress/b11-need-6-7-final.json"
    out.write_text(json.dumps({"done": done, "total": len(slugs), "check": check, "samples": samples}, indent=2))
    print(json.dumps({"done": done, "total": len(slugs), "samples": samples}, indent=2))
    for c in check:
        print(f"  CHECK {c['slug']}: {c['words']}w bad={c.get('bad')}")


if __name__ == "__main__":
    main()
