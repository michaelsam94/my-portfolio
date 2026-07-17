#!/usr/bin/env python3
"""Rewrite b11_need_0 + b11_need_1 slugs: unique deep content, no shared boilerplate."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
SLUG_FILES = [Path("/tmp/b11_need_0.txt"), Path("/tmp/b11_need_1.txt")]
DATE_MOD = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")

STRIP_PATTERNS = [
    r"\n## Operational notes for[^\n]*\n.*?(?=\n## |\Z)",
    r"\n## Deep dive: edge case \d+ for[^\n]*\n.*?(?=\n## |\Z)",
    r"\n## Production lessons for[^\n]*\n.*?(?=\n## |\Z)",
    r"\n## Implementation patterns\n.*?(?=\n## Resources|\Z)",
    r"\n## Accessibility requirements\n.*?(?=\n## |\Z)",
    r"\n## Security and privacy considerations\n.*?(?=\n## |\Z)",
    r"\n## Testing strategy\n.*?(?=\n## |\Z)",
    r"\n## Common production mistakes\n.*?(?=\n## |\Z)",
    r"\n## Debugging and triage workflow\n.*?(?=\n## |\Z)",
    r"\n## Architecture and boundaries\n.*?(?=\n## |\Z)",
    r"Validate this in staging with production-like data volume[^\n]*\n",
    r"Document the decision, owner, and rollback path[^\n]*\n",
    r"\nPrefer boring, repeatable process[^\n]*\n",
    r"\nTreat operational readiness as part[^\n]*\n",
    r"\nRun the change through your standard PR checklist[^\n]*\n",
    r"\nShare a short write-up in your engineering channel[^\n]*\n",
    r"\| Primary metric \| Improve vs baseline \|.*?\n\n",
]

# Topic-specific sections appended when body still under TARGET after strip
EXPANSIONS: dict[str, str] = {
    "rust-web-toolchain": """
## Measuring the toolchain swap in your repo

Do not trust marketing benchmarks. Instrument your own monorepo:

```bash
hyperfine --warmup 2 'npx eslint . && npx prettier --check .'
hyperfine --warmup 2 'npx @biomejs/biome check .'
```

Track cold `next build`, warm HMR on your largest route, and CI wall-clock for lint plus typecheck. Biome often cuts lint from minutes to seconds on multi-thousand-file apps; Turbopack makes sluggish HMR feel instant. If SWC cannot cover a Babel plugin you depend on, keep that plugin path explicitly — mixed toolchains are fine during migration.

## When Rust tooling is the wrong move

Stay on ESLint if custom rules that oxc/Biome cannot express yet would take a multi-sprint rewrite. Stay on webpack if exotic loaders have no SWC/Rolldown equivalent. Speed that breaks compliance or i18n pipelines is not a win. Most teams only consume these tools; budget Rust only if tooling is your product.
""",
    "saga-pattern-distributed-transactions": """
## Timeouts, sagas, and the orphan state

Every orchestrated saga needs per-step timeouts. A payment service that never responds leaves inventory reserved indefinitely unless the orchestrator fires a compensation timer. Store `started_at` and `deadline_at` on each saga instance; a background sweeper marks stuck sagas for manual review when compensation also fails.

## Testing compensations before production

Unit tests cover happy path easily; sagas fail in compensation. Table-test each `(forward_step, failure_point)` pair and assert compensations run in reverse order with idempotent side effects mocked. Integration tests should kill a service mid-saga in staging and verify the system reaches a compensated state without orphaned money or inventory.
""",
    "secret-scanning-pre-commit": """
## Making pre-commit hooks stick organization-wide

Hooks developers bypass are theater. Reduce friction: one-command bootstrap (`pre-commit install`), keep scans under two seconds on typical diffs, mirror the same scan in CI, and document `--no-verify` as unacceptable for secrets. When a fixture triggers the scanner, fix the fixture to use obvious fakes (`sk_test_xxx`) rather than teaching people to skip hooks. Every allowlist entry needs a ticket ID and review.
""",
    "secrets-management": """
## Break-glass and emergency access

Break-glass admin credentials exist for when normal auth is broken. They should be disabled by default, require hardware MFA, log every action with mandatory ticket reference, and trigger immediate alerts. Review break-glass usage weekly — any entry without a matching incident ticket is a finding. Dynamic secrets shrink break-glass need; use them for routine database access instead of shared passwords in a vault folder.
""",
}

# Full body replacements for posts destroyed by generic templates
FULL_BODIES: dict[str, str] = {}

def load_full_bodies():
    """Import bodies from companion module."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "b11_bodies", Path(__file__).parent / "b11_need_bodies.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    FULL_BODIES.update(mod.BODIES)


def wc(text: str) -> int:
    return len(WORD.findall(text))


def parse_fm(raw: str) -> tuple[str, str]:
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return "", raw
    return parts[1], parts[2].lstrip("\n")


def extract_field(fm: str, key: str) -> str | None:
    m = re.search(rf'^{key}:\s*"([^"]*)"', fm, re.M)
    return m.group(1) if m else None


def extract_tags(fm: str) -> list[str]:
    tags, in_tags = [], False
    for line in fm.splitlines():
        if line.strip() == "tags:":
            in_tags = True
            continue
        if in_tags:
            if line.startswith("  - "):
                tags.append(line[4:].strip().strip('"'))
            else:
                break
    return tags


def extract_faq(fm: str) -> list[tuple[str, str]]:
    faqs, q, in_faq = [], None, False
    for line in fm.splitlines():
        if line.strip() == "faq:":
            in_faq = True
            continue
        if not in_faq:
            continue
        if line.startswith("  - q:"):
            q = line.split('"')[1] if '"' in line else line.split(":", 1)[1].strip()
        elif line.startswith("    a:") and q:
            a = line.split('"')[1] if '"' in line else line.split(":", 1)[1].strip()
            faqs.append((q, a))
            q = None
    return faqs[:3]


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def build_fm(slug: str, old_fm: str, faqs: list[tuple[str, str]]) -> str:
    title = extract_field(old_fm, "title") or slug.replace("-", " ").title()
    desc = extract_field(old_fm, "description") or ""
    pub = extract_field(old_fm, "datePublished") or DATE_MOD
    tags = extract_tags(old_fm) or ["Engineering"]
    kw = extract_field(old_fm, "keywords") or slug.replace("-", ", ")
    lines = [
        "---",
        f'title: "{esc(title)}"',
        f'slug: "{slug}"',
        f'description: "{esc(desc)}"',
        f'datePublished: "{pub}"',
        f'dateModified: "{DATE_MOD}"',
        "tags:",
    ]
    for t in tags:
        lines.append(f'  - "{esc(t)}"')
    lines.append(f'keywords: "{esc(kw)}"')
    lines.append("faq:")
    for q, a in faqs[:3]:
        lines.append(f'  - q: "{esc(q)}"')
        lines.append(f'    a: "{esc(a)}"')
    lines.append("---")
    return "\n".join(lines)


def strip_boilerplate(body: str) -> str:
    for pat in STRIP_PATTERNS:
        body = re.sub(pat, "\n", body, flags=re.S)
    # collapse excessive blank lines
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def ensure_resources(body: str, slug: str) -> str:
    if "## Resources" not in body:
        body += "\n\n## Resources\n\n- See official documentation for this topic.\n"
    return body


def process_slug(slug: str) -> dict:
    path = BLOG / f"{slug}.md"
    if not path.exists():
        return {"slug": slug, "status": "missing", "words": 0}
    raw = path.read_text(encoding="utf-8")
    old_fm, body = parse_fm(raw)
    faqs = extract_faq(old_fm)

    if slug in FULL_BODIES:
        body = FULL_BODIES[slug].strip()
        if slug in getattr(__import__("b11_need_bodies", fromlist=["FAQS"]), "FAQS", {}):
            pass
    else:
        body = strip_boilerplate(body)
        if slug in EXPANSIONS and EXPANSIONS[slug].strip() not in body:
            # insert expansion before Resources
            exp = EXPANSIONS[slug].strip()
            if "## Resources" in body:
                body = body.replace("## Resources", exp + "\n\n## Resources", 1)
            else:
                body = body + "\n\n" + exp

    body = ensure_resources(body, slug)

    # pad with topic-specific expansion if still short
    while wc(body) < TARGET and slug in EXPANSIONS:
        extra = EXPANSIONS.get(f"{slug}__pad")
        if not extra or extra in body:
            break
        body = body.replace("## Resources", extra.strip() + "\n\n## Resources", 1)

    fm = build_fm(slug, old_fm, faqs)
    path.write_text(fm + "\n\n" + body.strip() + "\n", encoding="utf-8")
    w = wc(body)
    bad = any(
        p in path.read_text()
        for p in (
            "Validate this in staging",
            "## Operational notes for",
            "## Deep dive: edge case",
            "## Production lessons for",
            "Primary metric | Improve vs baseline",
        )
    )
    return {
        "slug": slug,
        "status": "done" if w >= TARGET and not bad else "check",
        "words": w,
        "bad": bad,
    }


def main():
    try:
        load_full_bodies()
    except Exception as e:
        print(f"Warning: could not load b11_need_bodies.py: {e}")

    slugs = []
    for f in SLUG_FILES:
        slugs.extend(s.strip() for s in f.read_text().splitlines() if s.strip())

    results = [process_slug(s) for s in slugs]
    done = sum(1 for r in results if r["status"] == "done")
    check = [r for r in results if r["status"] == "check"]
    samples = sorted(
        [r for r in results if r["status"] == "done"], key=lambda x: -x["words"]
    )[:3]
    print(f"DONE={done}/{len(slugs)} CHECK={len(check)}")
    for r in check:
        print(f"  CHECK {r['slug']}: {r['words']}w bad={r.get('bad')}")
    for r in samples:
        print(f"  SAMPLE {r['slug']}: {r['words']}w")


if __name__ == "__main__":
    main()
