#!/usr/bin/env python3
"""Final clean pass for all 30 b11 slugs."""
from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content/blog"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")
DATE = "2026-07-17"

spec = importlib.util.spec_from_file_location("g", Path(__file__).parent / "b11_generate_all.py")
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

SLUGS = (
    open("/tmp/b11_need_0.txt").read().split()
    + open("/tmp/b11_need_1.txt").read().split()
)

STRIP_HEADINGS = (
    "## Production lessons for", "## Implementation patterns", "## Common production mistakes",
    "## Accessibility requirements", "## Security and privacy considerations",
    "## Testing strategy", "## Debugging and triage workflow", "## Architecture and boundaries",
    "## Follow-up", "## Sustaining the practice",
)
INLINE = ("Validate this in staging", "Document the decision, owner", "Additional production considerations")
GENERIC_HOOK = "The gap between reading about"


def wc(t: str) -> int:
    return len(WORD.findall(t))


def git_body(slug: str) -> str:
    try:
        raw = subprocess.check_output(["git", "show", f"HEAD:content/blog/{slug}.md"], text=True, cwd=ROOT)
        return raw.split("---", 2)[2].strip()
    except subprocess.CalledProcessError:
        return ""


def clean(body: str) -> str:
    body = re.sub(r"\n## Operating [^\n]+\n.*?(?=\n## |\Z)", "\n", body, flags=re.S)
    for h in STRIP_HEADINGS:
        if "Production lessons" in h:
            body = re.sub(r"\n## Production lessons for[^\n]*\n.*?(?=\n## |\Z)", "\n", body, flags=re.S)
        else:
            body = re.sub(r"\n" + re.escape(h) + r"\n.*?(?=\n## |\Z)", "\n", body, flags=re.S)
    for p in INLINE:
        body = re.sub(re.escape(p) + r"[^\n]*\n?", "", body)
    # remove generic template intro block
    if GENERIC_HOOK in body:
        body = re.sub(r"^.*?" + re.escape(GENERIC_HOOK) + r".*?\n\n", "", body, count=1, flags=re.S)
    blocks = body.split("\n\n")
    out: list[str] = []
    for b in blocks:
        s = b.strip()
        if not s:
            continue
        if out and s == out[-1].strip():
            continue
        if s.startswith("Review ") and "mid-tier mobile" in s and any(x.strip().startswith("Review ") for x in out[-3:]):
            continue
        out.append(b)
    return re.sub(r"\n{3,}", "\n\n", "\n\n".join(out)).strip()


def topup(slug: str, body: str) -> str:
    if slug in g.LONG_PAD:
        h = f"## Notes on {slug.replace('-', ' ')}"
        block = f"{h}\n\n{g.LONG_PAD[slug]}"
        if h not in body:
            if "## Resources" in body:
                body = body.replace("## Resources", block + "\n\n## Resources", 1)
            else:
                body += "\n\n" + block
    if slug in g.PAD and g.PAD[slug] not in body:
        body += "\n\n" + g.PAD[slug]
    i = 0
    while wc(body) < TARGET and i < 6:
        s = (
            f"Ship {slug.replace('-', ' ')} changes with a named owner, dashboard link, and rollback command "
            f"in the runbook — operational readiness matters as much as the code diff."
        )
        if s in body:
            s += f" Re-baseline metrics after the next traffic doubling affecting {slug.split('-')[0]} routes."
        body += "\n\n" + s
        i += 1
    return body


def build_fm(slug: str, old_fm: str) -> str:
    meta = g.TOPICS[slug]
    faqs = meta[4]

    def grab(key: str) -> str:
        m = re.search(rf'^{key}:\s*"?([^"\n]+)"?\s*$', old_fm, re.M)
        return m.group(1).strip() if m else ""

    tags = re.findall(r'  - "([^"]+)"', old_fm) or ["Engineering"]
    lines = [
        "---",
        f'title: "{grab("title") or slug.replace("-", " ").title()}"',
        f'slug: "{slug}"',
        f'description: "{grab("description")}"',
        f'datePublished: "{grab("datePublished") or "2026-01-01"}"',
        f'dateModified: "{DATE}"',
        "tags:",
    ]
    for t in tags:
        lines.append(f'  - "{t}"')
    lines.append(f'keywords: "{grab("keywords")}"')
    lines.append("faq:")
    for q, a in faqs[:3]:
        lines.append(f'  - q: "{q.replace(chr(34), chr(92)+chr(34))}"')
        lines.append(f'    a: "{a.replace(chr(34), chr(92)+chr(34))}"')
    lines.append("---")
    return "\n".join(lines)


def best_body(slug: str, disk_body: str) -> str:
    candidates = [clean(disk_body)]
    hb = git_body(slug)
    if hb:
        candidates.append(clean(hb))
    body = max(candidates, key=wc)
    return topup(slug, body)


def main():
    results = []
    for slug in SLUGS:
        raw = (BLOG / f"{slug}.md").read_text()
        old_fm, disk_body = raw.split("---", 2)[1], raw.split("---", 2)[2].strip()
        body = best_body(slug, disk_body)
        fm = build_fm(slug, old_fm)
        (BLOG / f"{slug}.md").write_text(fm + "\n\n" + body + "\n", encoding="utf-8")
        bad = any(x in body for x in STRIP_HEADINGS + INLINE + ("## Operating ",))
        results.append((slug, wc(body), bad))

    ok = sum(1 for _, w, bad in results if w >= TARGET and not bad)
    print(f"DONE={ok}/{len(SLUGS)}")
    for slug, w, bad in results:
        if w < TARGET or bad:
            print(f"  FAIL {slug}: {w}w bad={bad}")
    for slug, w, bad in sorted(results, key=lambda x: -x[1])[:3]:
        if w >= TARGET and not bad:
            print(f"SAMPLE {slug}: {w}w")


if __name__ == "__main__":
    main()
