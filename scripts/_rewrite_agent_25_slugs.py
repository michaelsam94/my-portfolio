#!/usr/bin/env python3
"""Rewrite 25 agent blog slugs: unique deep-dives, >=1200 words, dateModified 2026-07-17."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
WORD = re.compile(r"\b[\w'-]+\b")
BOILER = "Design principles that survive production"

SLUGS = [
    "agent-scheduled-job-leader-election",
    "agent-schema-migration-zero-downtime",
    "agent-schema-registry-avro",
    "agent-scope-minimization-principle",
    "agent-screen-reader-live-regions",
    "agent-scroll-driven-animations-css",
    "agent-secrets-scanning-precommit",
    "agent-semantic-layer-metrics",
    "agent-server-components-cache-revalidate",
    "agent-serverless-cold-start-mitigation",
    "agent-service-account-least-privilege",
    "agent-service-mesh-mtls-strict",
    "agent-session-based-recsys",
    "agent-session-fixation-prevention",
    "agent-settlement-cutoff-windows",
    "agent-short-lived-credentials-rotation",
    "agent-sidecar-resource-overhead",
    "agent-slot-filling-dialogue",
    "agent-slowly-changing-dimensions",
    "agent-sparse-dense-hybrid",
    "agent-speculation-rules-prerender",
    "agent-spiffe-spire-identity",
    "agent-spot-instance-interruption-handling",
    "agent-sso-saml-metadata-rotation",
]


def wc(t: str) -> int:
    return len(WORD.findall(t))


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


# Import content from part modules
from _agent25_content import POSTS  # noqa: E402


def main():
    failed = []
    for slug in SLUGS:
        if slug not in POSTS:
            print(f"MISSING {slug}", file=sys.stderr)
            failed.append(slug)
            continue
        meta, body = POSTS[slug]
        meta["slug"] = slug
        body = body.strip()
        full = fm(meta) + "\n\n" + body + "\n"
        (BLOG / f"{slug}.md").write_text(full, encoding="utf-8")
        w = wc(full)
        bp = BOILER in full
        ok = w >= 1200 and not bp
        print(f"{'OK' if ok else 'FAIL'}\t{w}\tbp={bp}\t{slug}")
        if not ok:
            failed.append(slug)
    if failed:
        sys.exit(1)
    print(f"\nDone: {len(SLUGS) - len(failed)}/{len(SLUGS)}")


if __name__ == "__main__":
    main()
