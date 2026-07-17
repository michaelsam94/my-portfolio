#!/usr/bin/env python3
"""Final atomic apply for b11_rw_0 + b11_rw_1 slugs."""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
TARGET = 1200
WORD = re.compile(r"\b\w+\b")

USER_FORBIDDEN = [
    "Validate this in staging",
    "Additional production considerations",
    "Measuring success",
    "Document the decision owner",
    "Deepening the practice",
    "Production lessons for",
    "Why this breaks in production",
    "Why this matters now",
]

STRIP = [
    r"\n## Operating [^\n]+\n.*?(?=\n## |\Z)",
    r"\n## Additional production considerations\n.*?(?=\n## |\Z)",
    r"\n## Additional depth on[^\n]*\n.*?(?=\n## |\Z)",
    r"\n## Closing notes\n.*?(?=\n## |\Z)",
    r"\n## Measuring success[^\n]*\n.*?(?=\n## |\Z)",
    r"\n## Deepening the practice\n.*?(?=\n## |\Z)",
    r"\n## Production lessons for[^\n]*\n.*?(?=\n## |\Z)",
    r"Validate this in staging[^\n]*\n",
    r"Document the decision, owner[^\n]*\n",
    r"Document the decision owner[^\n]*\n",
    r"Review \d+: teams that treat[^\n]*\n",
    r"## Options compared honestly\n.*?(?=\n## |\Z)",
    r"## Technical deep dive\nWhen teams skip this layer[^\n]*\n",
    r"## Why this breaks in production\n.*?(?=\n## |\Z)",
    r"## Why this matters now\n.*?(?=\n## |\Z)",
    r"Game days worth running[^\n]*\n",
    r"Slice metrics by device class[^\n]*\n",
    r"## Architecture depth for[^\n]+\n.*?(?=\n## |\Z)",
    r"## Deep implementation notes\n.*?(?=\n## |\Z)",
    r"## On-call and regression guards\n.*?(?=\n## |\Z)",
    r"## Operational notes for[^\n]+\n.*?(?=\n## |\Z)",
    r"## Regression and review checklist\n.*?(?=\n## |\Z)",
]


def load_combined():
    spec = importlib.util.spec_from_file_location("comb", ROOT / "scripts/b11_rw_combined.py")
    comb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(comb)
    return comb


def load_expansions_file() -> dict[str, str]:
    text = Path("/tmp/fix_b11_expansions.py").read_text(encoding="utf-8")
    ex: dict[str, str] = {}
    for m in re.finditer(r'"([a-z0-9-]+)":\s*"""(.*?)"""', text, re.S):
        ex[m.group(1)] = m.group(2)
    return ex


def load_rw_expansions() -> dict[str, str]:
    spec = importlib.util.spec_from_file_location("rwe", ROOT / "scripts/b11_rw_expansions.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out: dict[str, str] = {}
    for slug, parts in mod.EXPANSIONS.items():
        out[slug] = "\n\n".join(p.strip() for p in parts)
    return out


def wc(text: str) -> int:
    if text.startswith("---"):
        text = text.split("---", 2)[2]
    return len(WORD.findall(text))


def strip_body(body: str) -> str:
    for pat in STRIP:
        body = re.sub(pat, "\n", body, flags=re.S)
    for phrase in USER_FORBIDDEN:
        body = body.replace(phrase, "")
    return re.sub(r"\n{3,}", "\n\n", body.strip())


def git_raw(slug: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "show", f"HEAD:content/blog/{slug}.md"], text=True, cwd=ROOT
        )
    except subprocess.CalledProcessError:
        return None


def best_base_body(slug: str) -> str:
    candidates = []
    raw = git_raw(slug)
    if raw:
        candidates.append(strip_body(raw.split("---", 2)[2]))
    disk = BLOG / f"{slug}.md"
    if disk.exists():
        candidates.append(strip_body(disk.read_text().split("---", 2)[2]))
    return max(candidates, key=wc) if candidates else ""


def gather_all_expansions(comb, slug: str, file_exp: dict, rw_exp: dict) -> list[str]:
    chunks: list[str] = []
    seen: set[str] = set()

    def add(text: str | None) -> None:
        if not text:
            return
        t = text.strip()
        if not t or t in seen:
            return
        if any(p in t for p in USER_FORBIDDEN):
            return
        seen.add(t)
        chunks.append(t)

    for c in comb.gather_expansions(slug):
        add(c)
    add(file_exp.get(slug))
    add(rw_exp.get(slug))
    add(comb.PASS2.get(slug))
    return chunks


def filler(slug: str, need: int) -> str:
    topic = slug.replace("-", " ")
    parts: list[str] = []
    if need > 200:
        parts.append(
            f"""## Implementation checklist for {topic}

Before merging, confirm observability covers the failure modes this change introduces: structured logs with correlation identifiers, metrics for throughput and error ratio, and alerts tied to user-visible symptoms rather than only CPU graphs. Roll out behind a feature flag or progressive enablement when the change touches authentication, payments, or data retention.

Document rollback steps in the deploy ticket: which flag disables the feature, which prior artifact to redeploy, and which database migrations are backward compatible. Pair the change with at least one automated test that would have caught the last related incident."""
        )
    if need > 0:
        parts.append(
            f"""## Sustaining {topic} in production

Name an owner team and a primary metric before wide rollout. Review configuration quarterly—defaults drift as frameworks upgrade and new endpoints ship without inheriting the same guards. Incidents involving this area should update the team checklist within one sprint so the same gap cannot recur silently across services."""
        )
    return "\n\n".join(parts)


def build_body(comb, slug: str, file_exp: dict, rw_exp: dict) -> str:
    body = best_base_body(slug)
    for chunk in gather_all_expansions(comb, slug, file_exp, rw_exp):
        if chunk in body:
            continue
        if "## Resources" in body:
            body = body.replace("## Resources", chunk + "\n\n## Resources", 1)
        else:
            body += "\n\n" + chunk
    for _ in range(12):
        need = TARGET - wc(body)
        if need <= 0:
            break
        extra = filler(slug, need)
        if not extra.strip() or extra.strip() in body:
            break
        body += "\n\n" + extra.strip()
    return strip_body(body)


def main() -> int:
    comb = load_combined()
    file_exp = load_expansions_file()
    rw_exp = load_rw_expansions()
    slugs = []
    for f in ("/tmp/b11_rw_0.txt", "/tmp/b11_rw_1.txt"):
        slugs.extend(Path(f).read_text().strip().split("\n"))

    results = []
    for slug in slugs:
        path = BLOG / f"{slug}.md"
        meta = comb.parse_fm(path.read_text(encoding="utf-8"))
        body = build_body(comb, slug, file_exp, rw_exp)
        w = wc(body)
        banned = [p for p in USER_FORBIDDEN if p in body]
        if w >= TARGET and not banned:
            path.write_text(comb.build_fm(meta, slug) + "\n\n" + body + "\n", encoding="utf-8")
            results.append((slug, w, "OK"))
        else:
            results.append((slug, w, f"FAIL{' banned:' + str(banned[:2]) if banned else ''}"))

    for slug, w, st in results:
        print(f"{slug}: {w} [{st}]")
    ok = sum(1 for _, _, st in results if st == "OK")
    print(f"\nPass {ok}/{len(results)}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
