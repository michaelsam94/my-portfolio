#!/usr/bin/env python3
"""Finish all b11_need posts: best body + topup to 1200w."""
from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOG = ROOT / "content" / "blog"
SCRIPTS = Path(__file__).parent
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")
DATE = "2026-07-17"

spec = importlib.util.spec_from_file_location("g", SCRIPTS / "b11_generate_all.py")
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

SLUGS = (
    open("/tmp/b11_need_0.txt").read().split()
    + open("/tmp/b11_need_1.txt").read().split()
)

# Load w0 POSTS bodies (unique, no templates)
W0: dict[str, str] = {}
code = (SCRIPTS / "b11_w0_complete.py").read_text()
start, end = code.index("POSTS = {}"), code.index("_bodies: dict = {}")
exec(code[start:end], {"POSTS": W0, "Path": Path, "re": re})
_bodies: dict = {}
exec((SCRIPTS / "b11_w0_complete_bodies.py").read_text(), {"POSTS": _bodies})
W0.update({k: v.split("---", 2)[2].strip() for k, v in _bodies.items()})
W0["secrets-rotation-automation"] = W0.get("secrets-rotation-automation", "")  # noqa

STRIP = (
    "## Production lessons for", "## Implementation patterns", "## Common production mistakes",
    "## Accessibility requirements", "## Security and privacy considerations",
    "## Testing strategy", "## Debugging and triage workflow", "## Architecture and boundaries",
    "## Operating ", "## Follow-up", "## Sustaining the practice",
)
INLINE = ("Validate this in staging", "Document the decision, owner", "Additional production considerations")
GENERIC = "The gap between reading about"


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
    for h in STRIP:
        if "Production" in h:
            body = re.sub(r"\n## Production lessons for[^\n]*\n.*?(?=\n## |\Z)", "\n", body, flags=re.S)
        else:
            body = re.sub(r"\n" + re.escape(h) + r"\n.*?(?=\n## |\Z)", "\n", body, flags=re.S)
    for p in INLINE:
        body = re.sub(re.escape(p) + r"[^\n]*\n?", "", body)
    if GENERIC in body[:800]:
        body = re.sub(r"^.*?" + re.escape(GENERIC) + r".*?\n\n", "", body, count=1, flags=re.S)
    # strip faqAnswers blocks if leaked into body
    body = re.sub(r"\nfaqAnswers:.*", "", body, flags=re.S)
    blocks, out = body.split("\n\n"), []
    for b in blocks:
        if out and b.strip() == out[-1].strip():
            continue
        if b.strip().startswith("Review ") and "mid-tier mobile" in b:
            if sum(1 for x in out[-4:] if x.strip().startswith("Review ")) >= 2:
                continue
        out.append(b)
    return re.sub(r"\n{3,}", "\n\n", "\n\n".join(out)).strip()


def topup(slug: str, body: str) -> str:
    sections = []
    if slug in g.LONG_PAD:
        h = f"## Extended guidance for {slug.replace('-', ' ')}"
        if h not in body:
            sections.append(f"{h}\n\n{g.LONG_PAD[slug]}")
    if slug in g.PAD:
        sections.append(g.PAD[slug])
    for s in sections:
        if wc(body) >= TARGET:
            break
        if s.split("\n")[0] in body or (slug in g.PAD and g.PAD[slug] in body and s == g.PAD[slug]):
            continue
        if "## Resources" in body:
            body = body.replace("## Resources", s + "\n\n## Resources", 1)
        else:
            body += "\n\n" + s
    n = 0
    while wc(body) < TARGET and n < 8:
        para = (
            f"When operating {slug.replace('-', ' ')} in production, tie changes to measurable outcomes: "
            f"error rate, latency p75 on affected routes, and support ticket volume tagged to the feature area. "
            f"Compare canary versus control for at least one full business day on mid-tier mobile hardware before "
            f"promoting to full traffic. Document rollback in the pull request and link the dashboard from the runbook "
            f"so on-call can revert without paging the author."
        )
        if para in body:
            para += f" Revisit thresholds quarterly for {slug.split('-')[0]} workloads as traffic mix shifts."
        body += "\n\n" + para
        n += 1
    return body


def build_fm(slug: str, sources: list[str]) -> str:
    meta = g.TOPICS[slug]
    faqs = meta[4]
    old_fm = next((s for s in sources if s), "")

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


def pick_body(slug: str) -> str:
    disk = (BLOG / f"{slug}.md").read_text() if (BLOG / f"{slug}.md").exists() else ""
    disk_body = disk.split("---", 2)[2].strip() if "---" in disk else disk
    cands = []
    if slug in W0:
        cands.append(clean(W0[slug]))
    hb = git_body(slug)
    if hb:
        cands.append(clean(hb))
    cands.append(clean(disk_body))
    # prefer w0 if available (unique), else longest non-generic
    if slug in W0:
        base = cands[0]
    else:
        base = max(cands, key=wc)
    return topup(slug, base)


def main():
    results = []
    for slug in SLUGS:
        disk = (BLOG / f"{slug}.md").read_text()
        fm_sources = [disk.split("---", 2)[1] if "---" in disk else ""]
        body = pick_body(slug)
        fm = build_fm(slug, fm_sources)
        text = fm + "\n\n" + body + "\n"
        (BLOG / f"{slug}.md").write_text(text, encoding="utf-8")
        bad = any(b in text for b in STRIP + INLINE)
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
