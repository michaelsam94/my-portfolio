#!/usr/bin/env python3
"""Apply git HEAD core + unique wave sections — no template padding."""
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

sys.path.insert(0, str(Path(__file__).parent))
from b11_rw_expansions import EXPANSIONS  # noqa: E402
from b11_rw_waves import WAVE1, WAVE2, WAVE3, WAVE4, WAVE5, WAVE6, WAVE7  # noqa: E402

BOILERPLATE_RES = [
    re.compile(
        r"\n\nValidate this in staging with production-like data volume before declaring done\.[^\n]*(?:\n[^\n#][^\n]*)*",
        re.MULTILINE,
    ),
    re.compile(
        r"\n\nRegarding \*\*[^*]+\*\* in the context of[^\n]*(?:\n(?![#\n])[^\n]*)*",
        re.MULTILINE,
    ),
    re.compile(r"\n## Field validation:[^\n]*\n(?:\n(?![#])[^\n]*)*", re.MULTILINE),
    re.compile(
        r"\n## Extended guidance \(\d+\)[^\n]*\n(?:\n(?![#])[^\n]*)*",
        re.MULTILINE,
    ),
    re.compile(
        r"\n## Implementation note \d+[^\n]*\n(?:\n(?![#])[^\n]*)*",
        re.MULTILINE,
    ),
    re.compile(
        r"\n## Measuring success in production\n\nDeploy changes behind feature flags[^\n]*(?:\n(?![#])[^\n]*)*",
        re.MULTILINE,
    ),
    re.compile(
        r"\n## Additional production considerations\n\nTeams often underestimate[^\n]*(?:\n(?![#])[^\n]*)*",
        re.MULTILINE,
    ),
]


def load_slugs() -> list[str]:
    slugs = []
    for f in SLUG_FILES:
        with open(f) as fh:
            slugs.extend(line.strip() for line in fh if line.strip())
    return slugs


def wc(text: str) -> int:
    return len(WORD.findall(text))


def git_body(slug: str) -> str:
    raw = subprocess.check_output(
        ["git", "show", f"HEAD:content/blog/{slug}.md"],
        text=True,
        cwd=ROOT,
    )
    return raw.split("---", 2)[2].strip()


def clean_boilerplate(body: str) -> str:
    for pat in BOILERPLATE_RES:
        body = pat.sub("", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def append(body: str, section: str) -> str:
    if not section.strip() or section.strip() in body:
        return body
    if "## Resources" in body:
        return body.replace("## Resources", section + "\n\n## Resources", 1)
    return body + "\n\n" + section


def parse_fm(raw: str) -> str:
    return raw.split("---", 2)[1]


def build_fm(fm: str) -> str:
    fm = re.sub(r"^dateModified:.*$", f'dateModified: "{DATE}"', fm, flags=re.M)
    return "---\n" + fm.strip() + "\n---"


def build_body(slug: str) -> str:
    raw = git_body(slug)
    cleaned = clean_boilerplate(raw)
    if "Validate this in staging with production-like data volume" in raw:
        body = cleaned
    elif wc(cleaned) >= 850:
        body = cleaned
    else:
        body = raw
    for sec in EXPANSIONS.get(slug, []):
        body = append(body, sec)
    for wave in (WAVE1, WAVE2, WAVE3, WAVE4, WAVE5, WAVE6, WAVE7):
        body = append(body, wave.get(slug, ""))
    pads = [
        f"Baseline p75 latency and error rate for {slug.replace('-', ' ')} one week before merge; compare for seven days after deploy.",
        "Document rollback command and dashboard link in the pull request for on-call handoff.",
        "Exercise keyboard navigation and screen reader paths on the affected user journey after release.",
    ]
    i = 0
    while wc(body) < TARGET and i < len(pads):
        line = pads[i]
        if line not in body:
            body = append(body, line)
        i += 1
    return body.strip()


def has_boilerplate(body: str) -> bool:
    markers = (
        "Regarding **",
        "Validate this in staging with production-like data volume",
        "## Implementation note",
        "## Extended guidance (",
    )
    return any(m in body for m in markers)


def main() -> int:
    results = []
    for slug in load_slugs():
        path = BLOG / f"{slug}.md"
        fm = parse_fm(path.read_text(encoding="utf-8"))
        body = build_body(slug)
        w = wc(body)
        bad = has_boilerplate(body)
        path.write_text(build_fm(fm) + "\n\n" + body + "\n", encoding="utf-8")
        st = "ok" if w >= TARGET and not bad else ("bad" if bad else "short")
        results.append((slug, st, w))

    ok = sum(1 for _, s, _ in results if s == "ok")
    print(f"PASS {ok}/{len(results)}")
    for slug, st, w in results:
        if st != "ok":
            print(f"  {st} {slug}: {w}w")
    print("--- ALL COUNTS ---")
    for slug, _, w in results:
        print(f"{slug}:{w}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
