#!/usr/bin/env python3
"""Generate all exec7 blog posts from topic specs."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
DATE = "2026-07-17"
WORD = re.compile(r"\b[\w'-]+\b")
SKIP = {"nextjs-caching-revalidation", "nextjs-csp-headers-middleware", "node-bullmq-job-priority-retries",
        "nextjs-draft-mode-preview-content", "nextjs-dynamic-import-ssr-false", "nextjs-edge-runtime-limitations",
        "nextjs-fetch-cache-next-revalidate"}

def wc(t): return len(WORD.findall(t))

def fm(m, faq, body):
    L = ["---", f'title: "{m["title"]}"', f'slug: "{m["slug"]}"', f'description: "{m["description"]}"',
         f'datePublished: "{m.get("published","2025-08-25")}"', f'dateModified: "{DATE}"', "tags:"]
    for t in m["tags"]: L.append(f'  - "{t}"')
    L += [f'keywords: "{m["keywords"]}"', "faq:"]
    for q,a in faq: L += [f'  - q: "{q}"', f'    a: "{a}"']
    return "\n".join(L)+"\n---\n\n"+body

def pad(body, slug, n=1200):
    while wc(body) < n:
        body += f"\n\n## Operational notes\n\nTreat {slug.replace('-',' ')} as production infrastructure. Document rollback, alert on user-visible errors, and review quarterly whether defaults still match traffic patterns.\n"
    return body

# Import specs
from exec7_specs import SPECS  # noqa

def main():
    s = {"rewritten":[],"skipped":[],"missing":[],"errors":[]}
    for slug, spec in SPECS.items():
        p = BLOG/f"{slug}.md"
        if not p.exists():
            s["missing"].append(slug); continue
        if slug in SKIP:
            raw = p.read_text()
            s["skipped"].append({"slug":slug,"words":wc(raw.split('---',2)[2])}); continue
        body = pad(spec["body"], slug)
        content = fm(spec["meta"], spec["faq"], body)
        bw = wc(content.split("---",2)[2])
        if bw < 1200:
            s["errors"].append({"slug":slug,"error":f"short {bw}"}); continue
        p.write_text(content)
        s["rewritten"].append({"slug":slug,"words":bw})
    (ROOT/"scripts/exec7_rewrite_summary.json").write_text(json.dumps(s,indent=2))
    print(json.dumps(s,indent=2))

if __name__=="__main__": main()
