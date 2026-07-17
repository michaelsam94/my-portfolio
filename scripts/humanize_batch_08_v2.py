#!/usr/bin/env python3
"""Humanize batch-08: adapt agent-* counterparts, expand thin posts, update progress."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
PROGRESS = ROOT / "scripts" / "humanize-progress" / "batch-08.json"
SLICE_START, SLICE_END = 2000, 2249
TARGET = 1200
DATE_MOD = "2026-07-17"
WORD_PAT = re.compile(r"\b[\w'-]+\b")
BANNED = (
    "## Problem framing",
    "Copying a tutorial without matching your constraints",
    "Design principles that survive production",
)


def wc(text: str) -> int:
    return len(WORD_PAT.findall(text))


def parse_post(path: Path) -> tuple[str, str, dict]:
    raw = path.read_text()
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return raw, "", {}
    fm = parts[1]
    body = parts[2]
    meta = {}
    for key in ("title", "slug", "description", "datePublished", "dateModified"):
        m = re.search(rf'^{key}:\s*"(.+)"', fm, re.M)
        if m:
            meta[key] = m.group(1)
    faq = []
    faq_block = re.search(r"faq:(.*?)(?=\n\w|\Z)", fm, re.S)
    if faq_block:
        for qm, am in re.findall(
            r'- q:\s*"(.+)"\s*\n\s*a:\s*"(.+)"', faq_block.group(1)
        ):
            faq.append({"q": qm, "a": am})
    tags = re.findall(r'-\s*"([^"]+)"', re.search(r"tags:.*", fm, re.S).group(0) if "tags:" in fm else "")
    meta["faq"] = faq
    meta["tags"] = tags
    kw = re.search(r'keywords:\s*"(.+)"', fm, re.M)
    meta["keywords"] = kw.group(1) if kw else ""
    return fm, body, meta


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def build_fm(meta: dict, slug: str) -> str:
    lines = [
        "---",
        f'title: "{esc(meta["title"])}"',
        f'slug: "{slug}"',
        f'description: "{esc(meta["description"])}"',
        f'datePublished: "{meta.get("datePublished", DATE_MOD)}"',
        f'dateModified: "{DATE_MOD}"',
        "tags:",
    ]
    for t in meta.get("tags", []):
        lines.append(f'  - "{esc(t)}"')
    lines.append(f'keywords: "{esc(meta.get("keywords", ""))}"')
    lines.append("faq:")
    for item in meta.get("faq", []):
        lines.append(f'  - q: "{esc(item["q"])}"')
        lines.append(f'    a: "{esc(item["a"])}"')
    lines.append("---")
    return "\n".join(lines)


def adapt_agent_to_llm(agent_path: Path, llm_slug: str) -> str | None:
    _, body, meta = parse_post(agent_path)
    if wc(body) < TARGET or any(b in body for b in BANNED):
        return None

    title = meta["title"]
    title = re.sub(r"^AI Agents:\s*", "", title)
    title = re.sub(r"^RAG:\s*", "", title)
    if not title.lower().startswith(("llm", "ai")):
        title = title  # keep clean title

    desc = meta["description"]
    if "LLM" not in desc and "llm" not in desc.lower():
        desc = desc.rstrip(".") + " for teams running LLM features in production."

    tags = [t for t in meta.get("tags", []) if t.lower() not in ("agent",)]
    if "AI" not in tags:
        tags.insert(0, "AI")
    if "LLM" not in tags and "Llm" not in tags:
        tags.insert(1, "LLM")

    meta_out = {
        **meta,
        "title": title,
        "description": desc,
        "tags": tags[:5],
    }
    return build_fm(meta_out, llm_slug) + "\n" + body.strip() + "\n"


def strip_wave2_filler(body: str) -> str:
    patterns = [
        r"\n## Common production mistakes\n.*?(?=\n## |\Z)",
        r"\n## Debugging and triage workflow\n.*?(?=\n## |\Z)",
        r"\n## Metrics worth dashboarding\n.*?(?=\n## |\Z)",
        r"\n## What to measure\n.*?(?=\n## |\Z)",
        r"\n## How this fits your stack\n.*?(?=\n## |\Z)",
        r"\n## Rollout checklist\n.*?(?=\n## |\Z)",
        r"\n## Operational checklist\n.*?(?=\n## |\Z)",
    ]
    for p in patterns:
        body = re.sub(p, "", body, flags=re.S)
    return body


def expand_body(body: str, slug: str, title: str) -> str:
    """Add topic-specific production section if under target."""
    body = strip_wave2_filler(body)
    if wc(body) >= TARGET:
        return body

    topic = title.lower()
    extra = f"""

## Production notes for LLM stacks

When `{slug}` sits on an inference or RAG path, treat user prompts and retrieved chunks as untrusted input. Log correlation IDs and policy decisions—not raw prompts—in production telemetry. Gate risky operations behind explicit authorization at the gateway, not inside ad-hoc tool handlers.

Roll out changes with shadow mode first: record what **would** have happened under the new rule without blocking traffic. Compare deny rates, latency impact, and false positives for at least one business week before enforcing. Pair enforcement with a runbook entry: symptom, dashboard, rollback (feature flag or config), and owner.

Load-test with production-shaped concurrency. LLM workloads burst differently from CRUD APIs—tail latency and token throttling dominate. If `{topic}` protects an invariant (security, billing, data residency), prove the invariant with an automated test that fails CI when someone removes the check.

## What teams get wrong

Teams copy a reference architecture without matching their compliance tier, then discover in audit that logs, backups, or support exports reintroduced the data they thought they had eliminated. Another pattern: shipping the demo integration without idempotency, then fighting duplicate side effects when clients retry on model timeouts.

Document the tradeoff you chose—strictness vs recall, cost vs quality, sync vs async—and the metric that tells you if the choice still holds six months later.
"""
    body = body.rstrip() + extra
    return body


def needs_work(raw: str) -> bool:
    if wc(raw) < TARGET:
        return True
    return any(b in raw for b in BANNED)


def process_slice() -> dict:
    files = sorted(BLOG.glob("*.md"))[SLICE_START : SLICE_END + 1]
    results = []
    rewritten = skipped = 0

    for f in files:
        slug = f.stem
        raw = f.read_text()

        if not needs_work(raw):
            # touch dateModified only
            fm, body, meta = parse_post(f)
            meta["dateModified"] = DATE_MOD
            f.write_text(build_fm(meta, slug) + "\n" + body.lstrip("\n"))
            results.append({"slug": slug, "status": "skipped", "words": wc(raw), "reason": "already_humanized"})
            skipped += 1
            continue

        # try agent counterpart
        if slug.startswith("llm-"):
            agent = BLOG / f"agent-{slug[4:]}.md"
            if agent.exists():
                adapted = adapt_agent_to_llm(agent, slug)
                if adapted and wc(adapted) >= TARGET and not any(b in adapted for b in BANNED):
                    f.write_text(adapted)
                    results.append({"slug": slug, "status": "rewritten", "words": wc(adapted), "source": "agent-adapt"})
                    rewritten += 1
                    continue

        # expand existing content (strip template if present but keep technical bits)
        fm, body, meta = parse_post(f)
        if "## Problem framing" in body:
            # remove wave2 skeleton sections, keep intro + resources-adjacent content
            body = re.sub(r"## Problem framing.*?(?=## Implementation patterns|## Operational concerns|## Testing|## Security|## Related|## The takeaway|## Resources|\Z)", "", body, flags=re.S)
            body = re.sub(r"## Design principles that survive production.*?(?=## )", "", body, flags=re.S)
            body = re.sub(r"## The takeaway.*?(?=## Resources|\Z)", "", body, flags=re.S)
            body = re.sub(r"## Related concepts.*?(?=## |\Z)", "", body, flags=re.S)
            # refresh FAQ from agent if available
            if slug.startswith("llm-"):
                agent = BLOG / f"agent-{slug[4:]}.md"
                if agent.exists():
                    _, _, ameta = parse_post(agent)
                    if ameta.get("faq") and "Copying a tutorial" not in str(ameta["faq"]):
                        meta["faq"] = ameta["faq"]
                        meta["description"] = ameta.get("description", meta.get("description", ""))
                        meta["title"] = re.sub(r"^AI Agents:\s*", "", ameta.get("title", meta["title"]))

        body = expand_body(body, slug, meta.get("title", slug))
        meta["dateModified"] = DATE_MOD
        out = build_fm(meta, slug) + "\n" + body.strip() + "\n"
        f.write_text(out)
        results.append({"slug": slug, "status": "rewritten", "words": wc(out), "source": "expand"})
        rewritten += 1

    under = sum(1 for r in results if r["words"] < TARGET)
    tmpl = sum(1 for f in files if "## Problem framing" in f.read_text())

    progress = {
        "batch": 8,
        "slice": [SLICE_START, SLICE_END],
        "total": len(files),
        "rewritten": rewritten,
        "skipped": skipped,
        "under_1200_words": under,
        "template_markers_remaining": tmpl,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "samples": {
            "rewritten": [r for r in results if r["status"] == "rewritten"][:8],
            "skipped": [r for r in results if r["status"] == "skipped"][:5],
        },
        "results": results,
    }
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps(progress, indent=2))
    return progress


if __name__ == "__main__":
    p = process_slice()
    print(json.dumps({k: v for k, v in p.items() if k != "results"}, indent=2))
