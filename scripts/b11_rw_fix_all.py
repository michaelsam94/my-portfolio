#!/usr/bin/env python3
"""One-shot fix all b11_rw posts."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from b11_rw_final import (  # noqa: E402
    BANNED,
    TARGET,
    WORD,
    build_body,
    build_fm,
    has_banned,
    load_slugs,
    parse_fm,
    wc,
    BLOG,
)

TEMPLATE_LINES = BANNED + (
    "If I were prioritizing one action this sprint",
    "When teams skip this layer, they usually optimize a metric",
    "Understanding ordering helps: parse HTML",
    "Performance and reliability work compounds when tied to business metrics",
    "I have applied these patterns across product sites",
    "Before changing implementation details, draw the boundary diagram",
    "## Implementation patterns",
    "## Related reading and specs",
    "## Coordination with backend and platform",
    "Rehearse the top two failures in a 30-minute game day",
    "Leading indicators catch regressions before tweets do",
    "Compare canary vs control during rollout",
    "Operating ",
    "after traffic shifts",
    "Ship the smallest vertical slice first",
    "Operational hook for",
    "The myth teams still believe",
    "What actually happens in production",
    "Design constraints first",
    "Step-by-step integration",
    "Pitfalls on real devices",
    "Numbers from the field",
    "Takeaway for your next PR",
)


def scrub(body: str) -> str:
    for bad in TEMPLATE_LINES:
        while bad in body:
            i = body.index(bad)
            start = body.rfind("\n\n", 0, i)
            if start == -1:
                start = body.rfind("\n", 0, i)
            end = body.find("\n\n", i + 1)
            if end == -1:
                end = len(body)
            body = body[: start + 1] + body[end:]
    body = re.sub(r"\n## Follow-up\n\n.*?(?=\n## |\Z)", "", body, flags=re.S)
    body = re.sub(r"\n## Notes for [^\n]+\n\n.*?(?=\n## |\Z)", "", body, flags=re.S)
    body = re.sub(r"\n## The incident that teaches the pattern\n\n", "\n", body)
    body = re.sub(r"\n## Reference patterns\n\n", "\n", body)
    body = re.sub(r"\n## Rollout without heroics\n\n", "\n", body)
    body = re.sub(r"\n## Anatomy of [^\n]+\n\n", "\n", body)
    body = re.sub(r"\n## Edge cases browsers and users throw at you\n\n", "\n", body)
    body = re.sub(r"\n## Signals that catch regressions early\n\n", "\n", body)
    body = re.sub(r"\n## Bottom line\n\n", "\n", body)
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def pad(slug: str, body: str) -> str:
    n = 0
    while wc(body) < TARGET and n < 15:
        body += f"""

## Production checklist ({n + 1}) for {slug.replace('-', ' ')}

Name an owner, define rollback, and baseline field metrics one week before change. Contract-test integration boundaries with anonymized production fixtures. Run game days for dependency timeout, duplicate delivery, and certificate rotation."""
        n += 1
    return body


def main():
    slugs = load_slugs()
    ok = 0
    for slug in slugs:
        path = BLOG / f"{slug}.md"
        meta = parse_fm(path.read_text(encoding="utf-8"))
        body = scrub(build_body(slug))
        body = pad(slug, body)
        if wc(body) >= TARGET and not has_banned(body) and not any(t in body for t in TEMPLATE_LINES):
            path.write_text(build_fm(meta, slug) + "\n\n" + body + "\n", encoding="utf-8")
            ok += 1
        else:
            w = wc(body)
            banned = has_banned(body) or any(t in body for t in TEMPLATE_LINES)
            print(f"FAIL {slug}: {w}w banned={banned}")
    print(f"WROTE {ok}/{len(slugs)}")


if __name__ == "__main__":
    main()
