#!/usr/bin/env python3
"""Rewrite all 25 batch-04 posts to >=1200 words and update progress JSON."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

BLOG = Path("/Users/michael/Desktop/my-portfolio/content/blog")
PROGRESS = Path("/Users/michael/Desktop/my-portfolio/scripts/humanize-progress/batch-04.json")
TODAY = "2026-07-17"
MIN_WC = 1200

# Import full post definitions
from batch04_all_posts import POSTS  # noqa: E402

SLUGS = list(POSTS.keys())


def wc(text: str) -> int:
    return len(re.sub(r"```.*?```", "", text, flags=re.DOTALL).split())


def read_fm(slug: str) -> dict:
    text = (BLOG / f"{slug}.md").read_text()
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    return yaml.safe_load(m.group(1))


def write_post(slug: str, faq: list, body: str) -> int:
    fm = read_fm(slug)
    fm["faq"] = faq
    fm["dateModified"] = TODAY
    header = yaml.dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False)
    (BLOG / f"{slug}.md").write_text(f"---\n{header}---\n\n{body.strip()}\n")
    return wc(body)


def main():
    counts = {}
    for slug in SLUGS:
        faq, body = POSTS[slug]
        counts[slug] = write_post(slug, faq, body)
    prog = json.loads(PROGRESS.read_text())
    done = set(prog.get("done", []))
    done.update(SLUGS)
    prog["done"] = sorted(done)
    prog["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    prog["notes"] = f"Rewrote {len(SLUGS)} posts in batch-04 worker chunk (model serving + platform ops)"
    PROGRESS.write_text(json.dumps(prog, indent=2) + "\n")
    low = [s for s, w in counts.items() if w < MIN_WC]
    print(f"Written {len(counts)} posts. Below {MIN_WC} words: {len(low)}")
    for s in SLUGS:
        w = counts[s]
        print(f"  {w:4d} {'OK' if w >= MIN_WC else 'LOW'} {s}")
    return 0 if not low else 1


if __name__ == "__main__":
    raise SystemExit(main())
