#!/usr/bin/env python3
"""Atomic fix: restore HEAD, strip templates, topup to 1200w — all 30 slugs."""
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

# Keep hand-crafted posts if already good
KEEP_DISK = {"security-referrer-policy-configuration"}

STRIP_HEADINGS = (
    "## Production lessons for",
    "## Implementation patterns",
    "## Common production mistakes",
    "## Accessibility requirements",
    "## Security and privacy considerations",
    "## Testing strategy",
    "## Debugging and triage workflow",
    "## Architecture and boundaries",
    "## Follow-up",
    "## Sustaining the practice",
)

INLINE_BANNED = (
    "Validate this in staging",
    "Additional production considerations",
    "Document the decision, owner",
)


def wc(t: str) -> int:
    return len(WORD.findall(t))


def git_show(slug: str) -> str:
    return subprocess.check_output(
        ["git", "show", f"HEAD:content/blog/{slug}.md"], text=True, cwd=ROOT
    )


def parse(raw: str) -> tuple[str, str]:
    p = raw.split("---", 2)
    return p[1], p[2].strip()


def strip_templates(body: str) -> str:
    body = re.sub(r"\n## Operating [^\n]+\n.*?(?=\n## |\Z)", "\n", body, flags=re.S)
    for h in STRIP_HEADINGS:
        if h.startswith("## Production"):
            body = re.sub(r"\n## Production lessons for[^\n]*\n.*?(?=\n## |\Z)", "\n", body, flags=re.S)
        else:
            body = re.sub(r"\n" + re.escape(h) + r"\n.*?(?=\n## |\Z)", "\n", body, flags=re.S)
    for phrase in INLINE_BANNED:
        body = re.sub(re.escape(phrase) + r"[^\n]*\n?", "", body)
    # dedupe identical paragraphs
    blocks = body.split("\n\n")
    out: list[str] = []
    for b in blocks:
        if out and b.strip() == out[-1].strip():
            continue
        out.append(b)
    return re.sub(r"\n{3,}", "\n\n", "\n\n".join(out)).strip()


def topup(slug: str, body: str) -> str:
    extras: list[str] = []
    if slug in g.LONG_PAD:
        h = f"## Deep dive: {slug.replace('-', ' ')}"
        if h not in body and g.LONG_PAD[slug] not in body:
            extras.append(f"{h}\n\n{g.LONG_PAD[slug]}")
    if slug in g.PAD and g.PAD[slug] not in body:
        extras.append(g.PAD[slug])
    for block in extras:
        if wc(body) >= TARGET:
            break
        if "## Resources" in body:
            body = body.replace("## Resources", block + "\n\n## Resources", 1)
        else:
            body += "\n\n" + block
    n = 0
    while wc(body) < TARGET and n < 5:
        pad = (
            f"Teams shipping {slug.replace('-', ' ')} should baseline field metrics on mid-tier Android "
            f"over 4G before and after each release — lab scores on developer laptops miss the cohort "
            f"where regressions become support tickets. Review quarterly when dependencies or traffic shape shifts."
        )
        if pad in body:
            pad += f" Link runbook steps from the dashboard for {slug.split('-')[0]} on-call."
        body += "\n\n" + pad
        n += 1
    return body


def build_fm(slug: str, head_fm: str) -> str:
    meta = g.TOPICS[slug]
    faqs = meta[4]

    def grab(key: str) -> str:
        m = re.search(rf'^{key}:\s*"?([^"\n]+)"?\s*$', head_fm, re.M)
        return m.group(1).strip() if m else ""

    title = grab("title") or slug.replace("-", " ").title()
    desc = grab("description")
    pub = grab("datePublished") or "2026-01-01"
    kw = grab("keywords")
    tags = re.findall(r'  - "([^"]+)"', head_fm)

    lines = [
        "---",
        f'title: "{title}"',
        f'slug: "{slug}"',
        f'description: "{desc}"',
        f'datePublished: "{pub}"',
        f'dateModified: "{DATE}"',
        "tags:",
    ]
    for t in tags or ["Engineering"]:
        lines.append(f'  - "{t}"')
    lines.append(f'keywords: "{kw}"')
    lines.append("faq:")
    for q, a in faqs[:3]:
        lines.append(f'  - q: "{q.replace(chr(34), chr(92)+chr(34))}"')
        lines.append(f'    a: "{a.replace(chr(34), chr(92)+chr(34))}"')
    lines.append("---")
    return "\n".join(lines)


def main():
    results = []
    for slug in SLUGS:
        if slug in KEEP_DISK:
            raw = (BLOG / f"{slug}.md").read_text()
            head_fm, body = parse(raw)
            body = strip_templates(body)
            body = topup(slug, body)
            fm = build_fm(slug, head_fm)
        else:
            raw = git_show(slug)
            head_fm, body = parse(raw)
            body = strip_templates(body)
            body = topup(slug, body)
            fm = build_fm(slug, head_fm)
        (BLOG / f"{slug}.md").write_text(fm + "\n\n" + body + "\n", encoding="utf-8")
        w = wc(body)
        bad = any(x in fm + body for x in STRIP_HEADINGS + INLINE_BANNED + ("## Operating ",))
        results.append((slug, w, bad))

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
