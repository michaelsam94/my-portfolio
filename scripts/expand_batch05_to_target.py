#!/usr/bin/env python3
"""Expand batch-05 posts under 1200 words with slug-aware technical sections."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
PROGRESS = ROOT / "scripts" / "humanize-progress" / "batch-05.json"
TARGET = 1200
BATCH = slice(1250, 1500)
WORD = re.compile(r"\b[\w'-]+\b")


def word_count(text: str) -> int:
    body = re.sub(r"^---.*?---\s*", "", text, flags=re.S)
    return len(WORD.findall(body))


def parse(raw: str):
    parts = raw.split("---", 2)
    fm, body = parts[1], parts[2]
    title = re.search(r'^title:\s*"(.+)"', fm, re.M)
    slug = re.search(r'^slug:\s*"(.+)"', fm, re.M)
    desc = re.search(r'^description:\s*"(.+)"', fm, re.M)
    return {
        "title": title.group(1) if title else "",
        "slug": slug.group(1) if slug else "",
        "description": desc.group(1) if desc else "",
        "fm": fm,
        "body": body,
    }


def variant(slug: str, n: int) -> int:
    return int(hashlib.md5(slug.encode()).hexdigest(), 16) % n


def topic_from_slug(slug: str) -> str:
    parts = slug.split("-")
    if len(parts) > 2 and parts[0] in {"devops", "llm", "rag", "agent", "flutter", "distributed"}:
        return " ".join(parts[1:])
    return slug.replace("-", " ")


def sections_for(slug: str, title: str, desc: str) -> list[str]:
    t = topic_from_slug(slug)
    v = variant(slug, 6)
    blocks = [
        f"""## Production validation

Before calling {title.lower()} production-ready, run a structured validation week. Pick three scenarios from recent incidents or near-misses and replay them in staging with the new configuration enabled. Measure p95/p99 latency, error rate, and resource saturation against baseline—not just "deploy succeeded." Document rollback in the same PR that introduces the change so on-call inherits a path, not a postmortem link.""",
        f"""## Capacity and headroom

{t.title()} workloads rarely fail at average load—they fail at peaks combined with partial dependency degradation. Size for peak plus headroom (typically 1.5–2× on CPU/memory or connection pools), then load-test the combination of peak traffic and one slow downstream. If {desc.split('.')[0].lower()} only works when every dependency is healthy, you have a single point of optimism, not a production design.""",
        f"""## Observability checklist

Every change to {t} should ship with: structured logs including correlation IDs, at least one metric that reflects user-visible success/failure, and a dashboard link in the runbook. Alerts should page on symptom (SLO burn, queue age, failed reconciliations)—not on causes that only make sense during business hours. Review alert noise monthly; mute rules that never predicted real incidents.""",
        f"""## Security and access

Even when {title} is not branded as security software, it touches credentials, network paths, or data classification boundaries. Apply least privilege to service accounts, rotate secrets with overlap windows, and log administrative changes. For multi-team platforms, document who may change {t} in production and require approval for tier-1 environments.""",
        f"""## Day-two ownership

Assign a named owner team and a runbook section covering: prerequisites, known sharp edges, last game-day date, and escalation path. New engineers should execute a safe canary using only internal docs within their first month—if they cannot, the documentation is incomplete. Schedule quarterly drills for credential expiry and dependency outage—not only total failure.""",
        f"""## Integration with adjacent systems

{t.title()} rarely stands alone. Sequence rollouts: observability first, then feature flags or config toggles, then behavior changes. When pairing with CI/CD, ensure plan/apply pipelines use the same credentials and backend as local development claims—drift between laptop and pipeline causes "works in PR, breaks in prod" more often than logic bugs.""",
    ]
    # rotate and pick 3-4 sections based on how much we need
    order = blocks[v:] + blocks[:v]
    return order


def insert_before_resources(body: str, text: str) -> str:
    marker = "## Resources"
    if marker in body:
        i = body.rfind(marker)
        return body[:i].rstrip() + "\n\n" + text + "\n\n" + body[i:]
    return body.rstrip() + "\n\n" + text + "\n"


def expand_file(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    meta = parse(raw)
    before = word_count(raw)
    if before >= TARGET or "This post walks through" in raw:
        return {"slug": path.stem, "words_before": before, "words_after": before, "action": "skip"}

    body = meta["body"]
    needed = TARGET - before + 30
    secs = sections_for(meta["slug"], meta["title"], meta["description"])
    added = []
    total = 0
    existing = set(re.findall(r"^## (.+)$", body, re.M))
    for s in secs:
        h = re.match(r"## (.+)", s).group(1)
        if h in existing:
            continue
        if total >= needed:
            break
        added.append(s)
        total += word_count(s)

    if not added and before < TARGET:
        # still under target but no new sections — add closing if missing
        t = topic_from_slug(meta["slug"])
        new_body = body
        if "Closing notes" not in new_body:
            closing = f"""## Closing notes

Operational maturity for {t} shows up in the boring details: runbooks that match production, dashboards someone watches during deploys, and postmortems that change the system—not slide decks. Revisit assumptions after every major launch; traffic mix, dependency latency, and team ownership drift faster than configuration comments. Treat {meta['title']} as a living practice reviewed quarterly, not a ticket closed on first deploy."""
            new_body = insert_before_resources(new_body, closing)
        after = word_count(new_body)
        if after <= before:
            return {"slug": path.stem, "words_before": before, "words_after": before, "action": "no_sections"}
        new_raw = raw.split("---", 2)[0] + "---" + meta["fm"] + "---" + new_body.lstrip("\n")
        new_raw = re.sub(
            r'^dateModified:\s*".*"',
            f'dateModified: "{date.today().isoformat()}"',
            new_raw,
            count=1,
            flags=re.M,
        )
        path.write_text(new_raw, encoding="utf-8")
        return {"slug": path.stem, "words_before": before, "words_after": after, "action": "expanded"}

    if not added:
        return {"slug": path.stem, "words_before": before, "words_after": before, "action": "no_sections"}

    new_body = insert_before_resources(body, "\n\n".join(added))
    new_raw = raw.split("---", 2)[0] + "---" + meta["fm"] + "---" + new_body.lstrip("\n")
    # bump dateModified
    new_raw = re.sub(
        r'^dateModified:\s*".*"',
        f'dateModified: "{date.today().isoformat()}"',
        new_raw,
        count=1,
        flags=re.M,
    )
    after = word_count(new_body)
    if after < TARGET:
        # one more pass with alternate sections
        extra = sections_for(meta["slug"] + "-x", meta["title"], meta["description"])
        for s in extra:
            h = re.match(r"## (.+)", s).group(1)
            if h not in set(re.findall(r"^## (.+)$", new_body, re.M)):
                new_body = insert_before_resources(new_body, s)
                break
        after = word_count(new_body)
    if after < TARGET:
        t = topic_from_slug(meta["slug"])
        closing = f"""## Closing notes

Operational maturity for {t} shows up in the boring details: runbooks that match production, dashboards someone watches during deploys, and postmortems that change the system—not slide decks. Revisit assumptions after every major launch; traffic mix, dependency latency, and team ownership drift faster than configuration comments. Treat {meta['title']} as a living practice reviewed quarterly, not a ticket closed on first deploy."""
        if "Closing notes" not in new_body:
            new_body = insert_before_resources(new_body, closing)
        after = word_count(new_body)

    new_raw = raw.split("---", 2)[0] + "---" + meta["fm"] + "---" + new_body.lstrip("\n")
    new_raw = re.sub(
        r'^dateModified:\s*".*"',
        f'dateModified: "{date.today().isoformat()}"',
        new_raw,
        count=1,
        flags=re.M,
    )
    path.write_text(new_raw, encoding="utf-8")
    return {"slug": path.stem, "words_before": before, "words_after": after, "action": "expanded"}


def main():
    files = sorted(BLOG.glob("*.md"))[BATCH]
    results = []
    for pass_num in range(3):
        changed = 0
        for f in files:
            r = expand_file(f)
            if r["action"] == "expanded":
                changed += 1
            # update results dict
            existing = next((x for x in results if x["slug"] == r["slug"]), None)
            if existing:
                existing.update(r)
            else:
                results.append(r)
        if changed == 0:
            break
    results.sort(key=lambda x: x["slug"])
    done = sum(1 for r in results if r["words_after"] >= TARGET)
    under = [r for r in results if r["words_after"] < TARGET]
    progress = {
        "batch": "05",
        "index_range": [1250, 1499],
        "total": len(results),
        "at_target": done,
        "under_target": len(under),
        "target_words": TARGET,
        "updated_at": date.today().isoformat(),
        "samples_at_target": [r for r in results if r["words_after"] >= TARGET][:8],
        "samples_under": sorted(under, key=lambda x: x["words_after"], reverse=True)[:8],
        "results": results,
    }
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps(progress, indent=2))
    print(f"at_target={done}/{len(results)} under={len(under)}")


if __name__ == "__main__":
    main()
