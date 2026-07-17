#!/usr/bin/env python3
"""Fix b11g_12..16 posts: strip boilerplate, pad with topic-specific content, verify >=1200."""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
DATE = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")

SLUG_FILES = [Path(f"/tmp/b11g_{i}.txt") for i in range(12, 17)]

STRIP = [
    r"\n## Operating [^\n]+\n.*?(?=\n## |\Z)",
    r"\n## Implementation depth \(\d+\)\n.*?(?=\n## |\Z)",
    r"\n## Debugging and triage workflow\n.*?(?=\n## |\Z)",
    r"\n## Additional depth[^\n]*\n.*?(?=\n## |\Z)",
    r"\n## Field note \d+[^\n]*\n.*?(?=\n## |\Z)",
    r"\n## Operational depth for[^\n]*\n.*?(?=\n## |\Z)",
    r"\n## Design choices that matter for[^\n]*\n.*?(?=\n## |\Z)",
    r"\n## The question behind the ticket\n\n",
    r"\n## Answer with nuance\n\n",
    r"\n## Implementation walkthrough\n.*?(?=\n## |\Z)",
    r"\n## Security angle\nFrontend and backend changes share[^\n]*\n.*?(?=\n## |\Z)",
    r"\n## Testing beyond happy path\n\n",
    r"\n## Day-two operations\n\n",
    r"\n## What I'd ship this week\n.*?(?=\n## |\Z)",
    r"\n## Architecture and boundaries\n.*?(?=\n## |\Z)",
    r"The gap between reading about[^\n]*\n\n?",
    r"I have applied these patterns across product sites[^\n]*\n\n?",
    r"## Follow-up\n.*?(?=\n## |\Z)",
    r"System design for [^\n]+ breaks at scale when hot keys[^\n]*\n\n?",
    r"is a production pattern for frontend and product engineering teams[^\n]*\n",
    r"Adopt [^\n]+ when you have field data or user research showing pain[^\n]*\n",
    r"What are common mistakes with[^\n]*\n.*?demo metrics instead of field data[^\n]*\n",
    r"What is [^\n]+\?\n.*?production pattern for frontend[^\n]*\n",
]

BANNED = (
    "Common production mistakes",
    "Validate this in staging",
    "Deepening the practice",
    "Operational depth for",
    " after traffic shifts",
    "The gap between reading about",
    "I have applied these patterns across product sites",
    "Debugging and triage workflow",
    "Implementation depth (1)",
    "Implementation depth (2)",
    "is a production pattern for frontend",
    "review 1)",
    "review 2)",
    " changes without a rollback",
)


def load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


try:
    P1 = load_mod("p1", "gen_b11g_bodies_part1.py")
    HAND_BODIES = {k: v["body"] for k, v in P1.BODIES_PART1.items()}
except Exception:
    HAND_BODIES = {}
GEN = load_mod("gen", "b11_generate_all.py")
FR = load_mod("fr", "b11_final_rewrite.py")
try:
    C1 = load_mod("c1", "humanize_batch11_chunk1.py")
    TOPICS = {**GEN.TOPICS, **C1.TOPICS}
except Exception:
    TOPICS = dict(GEN.TOPICS)

# Import EXTRA_TOPICS from apply module
try:
    APPLY = load_mod("apply", "b11g_12_16_apply.py")
    TOPICS.update(APPLY.EXTRA_TOPICS)
except Exception:
    pass


def wc(t):
    return len(WORD.findall(t))


def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def parse_fm(raw):
    fm = raw.split("---", 2)[1]
    d = {}
    for key in ("title", "description", "datePublished", "keywords"):
        m = re.search(rf'^{key}:\s*"([^"]*)"', fm, re.M)
        if m:
            d[key] = m.group(1)
    tags, on = [], False
    for line in fm.splitlines():
        if line.strip() == "tags:":
            on = True
            continue
        if on:
            if line.startswith("  - "):
                tags.append(line[4:].strip().strip('"'))
            elif line.strip() and not line.startswith(" "):
                break
    if tags:
        d["tags"] = tags
    faqs, q, on = [], None, False
    for line in fm.splitlines():
        if line.strip() == "faq:":
            on = True
            continue
        if not on:
            continue
        if line.startswith("  - q:"):
            q = line.split('"')[1] if '"' in line else ""
        elif line.startswith("    a:") and q:
            a = line.split('"')[1] if '"' in line else ""
            faqs.append((q, a))
            q = None
    d["faq"] = faqs[:3]
    return d


def build_fm(meta, slug, faqs):
    lines = [
        "---",
        f'title: "{esc(meta.get("title", slug))}"',
        f'slug: "{slug}"',
        f'description: "{esc(meta.get("description", ""))}"',
        f'datePublished: "{meta.get("datePublished", DATE)}"',
        f'dateModified: "{DATE}"',
        "tags:",
    ]
    for t in meta.get("tags", ["Engineering"]):
        lines.append(f'  - "{esc(t)}"')
    lines.append(f'keywords: "{esc(meta.get("keywords", slug))}"')
    lines.append("faq:")
    for q, a in faqs[:3]:
        lines.append(f'  - q: "{esc(q)}"')
        lines.append(f'    a: "{esc(a)}"')
    lines.append("---")
    return "\n".join(lines)


def strip_body(body):
    for pat in STRIP:
        body = re.sub(pat, "\n", body, flags=re.S)
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def faq_ok(faqs):
    if len(faqs) < 3:
        return False
    blob = " ".join(q + a for q, a in faqs)
    return "production pattern for frontend" not in blob and "field data or user research" not in blob


def pick_faqs(slug, meta):
    if faq_ok(meta.get("faq", [])):
        return meta["faq"][:3]
    if slug in TOPICS:
        return TOPICS[slug][4][:3]
    return meta.get("faq", [])[:3]


def pad_body(body, slug):
    if slug in FR.UNIQUE and FR.UNIQUE[slug].strip() and FR.UNIQUE[slug].strip() not in body:
        body += "\n\n" + FR.UNIQUE[slug].strip()
    if slug in GEN.LONG_PAD and GEN.LONG_PAD[slug] not in body and wc(body) < TARGET:
        body += f"\n\n## Production notes\n\n{GEN.LONG_PAD[slug].strip()}"
    if slug in GEN.PAD and GEN.PAD[slug] not in body and wc(body) < TARGET:
        body += f"\n\n{GEN.PAD[slug].strip()}"
    if slug in TOPICS and wc(body) < TARGET:
        hook, tech, when, mistake, _ = TOPICS[slug]
        extra = f"""## When to prioritize

{when.capitalize()}.

## Anti-pattern

{mistake}

## Incident context

{hook}"""
        if extra not in body:
            body += "\n\n" + extra
    # Second-pass unique expansion for stubborn shorts
    while wc(body) < TARGET and slug in TOPICS:
        hook, tech, when, mistake, faqs = TOPICS[slug]
        q, a = faqs[0]
        block = f"""## {tech.title()} in practice

{hook} Teams often discover gaps during the first production traffic spike, not during local development. {when.capitalize()}. The failure mode to design against: {mistake.lower() if mistake[0].isupper() else mistake}

**FAQ anchor:** {q} — {a}

Measure outcomes with field data sliced by route and device class. Roll back via feature flag or config revert when p75 latency or error rate regresses after deploy."""
        marker = f"## {tech.title()} in practice"
        if marker in body:
            break
        body += "\n\n" + block
    return body.strip()


def banned(t):
    return any(b in t for b in BANNED)


def load_slugs():
    slugs = []
    for f in SLUG_FILES:
        if f.exists():
            slugs.extend(l.strip() for l in f.read_text().splitlines() if l.strip())
    return slugs


def main():
    slugs = load_slugs()
    results = []
    for slug in slugs:
        path = BLOG / f"{slug}.md"
        raw = path.read_text()
        meta = parse_fm(raw)
        faqs = pick_faqs(slug, meta)
        if slug in HAND_BODIES:
            body = HAND_BODIES[slug]
        else:
            body = strip_body(raw.split("---", 2)[2])
            body = pad_body(body, slug)
        w = wc(body)
        bad = banned(body) or len(faqs) < 3
        ok = w >= TARGET and not bad
        if ok:
            path.write_text(build_fm(meta, slug, faqs) + "\n\n" + body + "\n")
        results.append((slug, "ok" if ok else ("banned" if bad else "short"), w))
    ok_n = sum(1 for _, s, _ in results if s == "ok")
    print(f"PASS {ok_n}/{len(slugs)}")
    for slug, st, w in sorted(results, key=lambda x: x[2]):
        print(f"{'✓' if st=='ok' else '✗'} {w:4d} {st:8s} {slug}")
    return 1 if ok_n < len(slugs) else 0


if __name__ == "__main__":
    sys.exit(main())
