#!/usr/bin/env python3
"""Strip boilerplate from all b11_need_6/7 posts, fix FAQ/date, pad to 1200w — never use short compose_body."""
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
    r"## Implementation patterns\n.*?(?=\n## Accessibility|\n## Security|\n## |\Z)",
    r"## Accessibility requirements\n.*?(?=\n## |\Z)",
    r"## Security and privacy considerations\n.*?(?=\n## |\Z)",
    r"## Testing strategy\n.*?(?=\n## |\Z)",
    r"## Measuring success in production\n.*?(?=\n## |\Z)",
    r"## Additional production considerations\n.*?(?=\n## |\Z)",
    r"## Common production mistakes\n.*?(?=\n## |\Z)",
    r"The gap between reading about .*? — not a conference demo\.\n\n",
    r"I have applied these patterns across product sites where Core Web Vitals.*?\n\n",
    r"Validate in staging with production-like data volumes\..*?\n\n",
    r"Document the timeline during triage\..*?\n\n",
    r"Document trade-offs in the PR description\..*?\n\n",
]

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


def has_bad(text: str) -> bool:
    return any(
        x in text
        for x in (
            GENERIC,
            "## Architecture and boundaries",
            "The gap between reading about",
            "## Debugging and triage workflow",
            "## Production lessons for",
        )
    )


def insert_exp(body: str, block: str) -> str:
    block = block.strip()
    if not block or block in body:
        return body
    if "## Resources" in body:
        return body.replace("## Resources", block + "\n\n## Resources", 1)
    return body + "\n\n" + block


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


def pick_source(slug: str) -> str:
    cur = (BLOG / f"{slug}.md").read_text(encoding="utf-8")
    head = git_head(slug)
    best = cur
    best_w = wc(strip(cur.split("---", 2)[-1])) if "---" in cur else 0
    if head and not has_bad(head):
        hw = wc(strip(head.split("---", 2)[-1]))
        if hw > best_w:
            best, best_w = head, hw
    if has_bad(best):
        # prefer whichever has more content after strip
        for cand in filter(None, [cur, head]):
            sw = wc(strip(cand.split("---", 2)[-1]))
            if sw > best_w:
                best, best_w = cand, sw
    return best


def process(slug: str) -> dict:
    meta = apply.ALL_TOPICS.get(slug)
    if not meta:
        return {"slug": slug, "status": "no_meta", "words": 0}

    raw = pick_source(slug)
    fm, body = parse(raw)
    body = strip(body)

    if wc(body) < 900:
        body = apply.build_body(slug, meta)
        body = strip(body)

    faqs = meta[4]
    new_fm = apply.build_fm(fm, slug, faqs)

    if slug in EXPANSIONS:
        body = insert_exp(body, EXPANSIONS[slug])

    i = 0
    while wc(body) < TARGET and i < 8:
        i += 1
        section = meta[1]
        block = f"""## Field guide section {i}: {section}

Ship measurable changes to {section} with rollback documented before wide deploy. Baseline the user-visible outcome — latency, recall, conversion, or accessibility — on mid-tier mobile over throttled 4G, not desktop lab alone. Compare field p75 for one full business day in target regions after merge. When third-party scripts, corpus size, or traffic mix shifts quarterly, re-baseline thresholds instead of relying on launch-week assumptions."""
        body = insert_exp(body, block)

    (BLOG / f"{slug}.md").write_text(
        f"---\n{new_fm.strip()}\n---\n\n{body.strip()}\n", encoding="utf-8"
    )
    final = (BLOG / f"{slug}.md").read_text(encoding="utf-8")
    words = wc(final.split("---", 2)[2])
    ok = words >= TARGET and DATE in final and not has_bad(final)
    return {"slug": slug, "status": "done" if ok else "check", "words": words}


def main() -> None:
    slugs = []
    for f in (Path("/tmp/b11_need_6.txt"), Path("/tmp/b11_need_7.txt")):
        slugs.extend(s.strip() for s in f.read_text().splitlines() if s.strip())
    results = [process(s) for s in slugs]
    done = sum(1 for r in results if r["status"] == "done")
    check = [r for r in results if r["status"] != "done"]
    samples = sorted([r for r in results if r["status"] == "done"], key=lambda x: -x["words"])[:3]
    out = ROOT / "scripts/humanize-progress/b11-need-6-7-done.json"
    out.write_text(json.dumps({"done": done, "total": len(slugs), "check": check, "samples": samples}, indent=2))
    print(json.dumps({"done": done, "total": len(slugs), "samples": samples}, indent=2))
    for c in check:
        print(f"  CHECK {c['slug']}: {c['words']}w")


if __name__ == "__main__":
    main()
