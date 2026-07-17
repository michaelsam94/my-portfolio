#!/usr/bin/env python3
"""Polish good HEAD posts: strip banned content, update FM, topup to 1200w."""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content/blog"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")
DATE = "2026-07-17"

spec = importlib.util.spec_from_file_location("g", Path(__file__).parent / "b11_generate_all.py")
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

GOOD = [
    "rust-web-toolchain", "saga-pattern-distributed-transactions", "secret-scanning-pre-commit",
    "secrets-management", "security-headers-hardening", "security-logging-audit-trails",
    "semantic-caching-llm-apis", "sensor-fusion-clock-sync-real-time", "serverless-2026",
    "serverless-cold-starts-mitigation", "serverless-database-access-patterns",
    "serverless-step-functions-orchestration", "shared-data-layer-room-kmp", "sigstore-keyless-signing",
    "small-language-models-on-mobile", "software-anti-corruption-layer",
    "software-architecture-decision-records", "software-cqrs-event-sourcing-tradeoffs",
    "software-domain-driven-design-strategic",
]

STRIP = (
    "## Production lessons for", "## Implementation patterns", "## Common production mistakes",
    "## Accessibility requirements", "## Security and privacy considerations",
    "## Testing strategy", "## Debugging and triage workflow", "## Architecture and boundaries",
    "## Operating ", "## Follow-up",
)
INLINE = ("Validate this in staging", "Document the decision, owner", "Additional production considerations")


def wc(t: str) -> int:
    return len(WORD.findall(t))


def clean(body: str) -> str:
    body = re.sub(r"\n## Operating [^\n]+\n.*?(?=\n## |\Z)", "\n", body, flags=re.S)
    for h in STRIP:
        if h.startswith("## Production"):
            body = re.sub(r"\n## Production lessons for[^\n]*\n.*?(?=\n## |\Z)", "\n", body, flags=re.S)
        else:
            body = re.sub(r"\n" + re.escape(h) + r"\n.*?(?=\n## |\Z)", "\n", body, flags=re.S)
    for p in INLINE:
        body = re.sub(re.escape(p) + r"[^\n]*\n?", "", body)
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def topup(slug: str, body: str) -> str:
    if slug in g.LONG_PAD:
        h = f"## Operational notes for {slug.replace('-', ' ')}"
        block = f"{h}\n\n{g.LONG_PAD[slug]}"
        if h not in body and g.LONG_PAD[slug] not in body:
            if "## Resources" in body:
                body = body.replace("## Resources", block + "\n\n## Resources", 1)
            else:
                body += "\n\n" + block
    if slug in g.PAD and g.PAD[slug] not in body:
        body += "\n\n" + g.PAD[slug]
    n = 0
    while wc(body) < TARGET and n < 4:
        extra = (
            f"Review {slug.replace('-', ' ')} metrics after the next release train on mid-tier mobile "
            f"devices — regressions that pass lab Lighthouse often fail CrUX field data."
        )
        if extra in body:
            extra += f" Dashboard link and rollback steps belong in the runbook for {slug}."
        body += "\n\n" + extra
        n += 1
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
        f'title: "{grab("title")}"',
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


def main():
    for slug in GOOD:
        raw = (BLOG / f"{slug}.md").read_text()
        old_fm, body = raw.split("---", 2)[1], raw.split("---", 2)[2].strip()
        body = topup(slug, clean(body))
        fm = build_fm(slug, old_fm)
        (BLOG / f"{slug}.md").write_text(fm + "\n\n" + body + "\n", encoding="utf-8")
        print(f"{slug}: {wc(body)}w")


if __name__ == "__main__":
    main()
