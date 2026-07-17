#!/usr/bin/env python3
"""Rewrite batch-04 DevOps posts: unique structure, >=1200 words, topic FAQs."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
PROGRESS = ROOT / "scripts" / "humanize-progress" / "batch-04.json"
WORD_PAT = re.compile(r"\b[\w'-]+\b")
TEMPLATE_MARKERS = (
    "Problem framing:",
    "Design principles for",
    "Documentation your team should maintain",
    "Pre-production checklist",
    "Common questions from reviewers",
    "Version and compatibility notes",
)

SLUGS = [
    "devops-experiment-tracking-governance",
    "devops-external-dns-automation",
    "devops-fact-table-grain-design",
    "devops-fault-injection-staging",
    "devops-feast-online-offline-sync",
    "devops-feature-flag-cd-integration",
    "devops-feature-store-backfill",
    "devops-feature-store-feast",
    "devops-feature-store-governance",
    "devops-feature-store-materialization",
    "devops-feature-store-monitoring",
    "devops-feature-store-point-in-time",
    "devops-feature-store-schema-evolution",
    "devops-finops-showback-chargeback",
    "devops-flux-helm-controller",
    "devops-flux-image-automation",
    "devops-game-day-planning",
    "devops-gateway-api-httproute-canary",
    "devops-gateway-api-migration",
    "devops-github-actions-reusable-workflows",
    "devops-gitlab-ci-child-pipelines",
    "devops-gitops-disaster-recovery",
    "devops-gitops-drift-detection",
    "devops-gitops-helm-kustomize-hybrid",
    "devops-gitops-multi-cluster",
]


def wc(text: str) -> int:
    return len(WORD_PAT.findall(text))


def fm(meta: dict) -> str:
    tags = "\n".join(f'  - "{t}"' for t in meta["tags"])
    faqs = "\n".join(
        f'  - q: "{f["q"]}"\n    a: "{f["a"]}"' for f in meta["faq"]
    )
    return f"""---
title: "{meta['title']}"
slug: "{meta['slug']}"
description: "{meta['description']}"
datePublished: "{meta['datePublished']}"
dateModified: "2026-07-17"
tags:
{tags}
keywords: "{meta['keywords']}"
faq:
{faqs}
---"""


# Content lives in separate module to keep this file runnable
from _rewrite_batch04_content import POSTS  # noqa: E402
from _rewrite_batch04_expand import EXPANSIONS, EXPANSIONS2  # noqa: E402


def write_posts():
    results = []
    for slug in SLUGS:
        if slug not in POSTS:
            raise KeyError(f"Missing content for {slug}")
        meta, body = POSTS[slug]
        meta["slug"] = slug
        body = body.strip() + EXPANSIONS.get(slug, "") + EXPANSIONS2.get(slug, "")
        full = fm(meta) + "\n" + body.strip() + "\n"
        path = BLOG / f"{slug}.md"
        path.write_text(full, encoding="utf-8")
        body_wc = wc(body)
        results.append({"slug": slug, "words": body_wc, "ok": body_wc >= 1200})
    return results


def update_progress(slugs: list[str]):
    data = json.loads(PROGRESS.read_text(encoding="utf-8"))
    done = set(data.get("done", []))
    done.update(slugs)
    data["done"] = sorted(done)
    data["updatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    data["notes"] = f"Rewrote {len(slugs)} posts in batch-04 worker run"
    PROGRESS.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main():
    results = write_posts()
    update_progress(SLUGS)
    ok = sum(1 for r in results if r["ok"])
    print(f"Wrote {len(results)} posts; {ok} meet >=1200 words")
    for r in results:
        flag = "OK" if r["ok"] else "SHORT"
        print(f"  [{flag}] {r['slug']}: {r['words']} words")
    short = [r for r in results if not r["ok"]]
    if short:
        raise SystemExit(f"{len(short)} posts under 1200 words")


if __name__ == "__main__":
    main()
