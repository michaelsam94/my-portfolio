#!/usr/bin/env python3
"""Atomic finish for b11_last59 — minimal strip, expansions, verified word counts."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content/blog"
SLUGS = Path("/tmp/b11_last59.txt").read_text().strip().split("\n")
DATE = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")

MIN_STRIP = [
    r"## Common production mistakes\n.*?(?=\n## |\Z)",
    r"## Debugging and triage workflow\n.*?(?=\n## |\Z)",
    r"## Field notes \d+\n.*?(?=\n## |\Z)",
    r"## Operating [^\n]+ after traffic shifts[^\n]*\n.*?(?=\n## |\Z)",
]

INTRO_STRIP = [
    r"The gap between reading about .*? — not a conference demo\.\n\n",
    r"I have applied these patterns across product sites where Core Web Vitals.*?\n\n",
]

sys.path.insert(0, str(ROOT / "scripts"))
from batch11_expand import EXPANSIONS  # noqa: E402
from b11_last59_apply import ADDONS  # noqa: E402


def wc(text: str) -> int:
    return len(WORD.findall(text))


def strip_body(body: str) -> str:
    for pat in INTRO_STRIP:
        body = re.sub(pat, "", body, flags=re.S)
    for pat in MIN_STRIP:
        body = re.sub(pat, "", body, flags=re.S)
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def update_fm(fm: str) -> str:
    fm = re.sub(r'^dateModified:.*$', f'dateModified: "{DATE}"', fm, flags=re.M)
    return fm


def insert_section(body: str, section: str) -> str:
    heading = section.split("\n", 1)[0]
    if heading in body:
        return body
    if "## Resources" in body:
        return body.replace("## Resources", section + "\n\n## Resources", 1)
    return body + "\n\n" + section


def git_content(slug: str) -> str:
    return subprocess.check_output(["git", "show", f"HEAD:content/blog/{slug}.md"], text=True)


def parse(raw: str) -> tuple[str, str]:
    parts = raw.split("---", 2)
    return parts[1], parts[2].lstrip("\n")


def write_post(slug: str, fm: str, body: str) -> int:
    (BLOG / f"{slug}.md").write_text(f"---\n{fm.strip()}\n---\n\n{body.strip()}\n", encoding="utf-8")
    return wc(body)


# Extra unique sections for slugs still under target after primary expansions
EXTRA: dict[str, str] = {
    "seo-javascript-rendering-crawl": """## Dynamic rendering as a bridge

Google's dynamic rendering sends bot user-agents to a prerender service while users get CSR. Treat as temporary — maintenance cost of dual pipelines is high. Monitor indexed page count weekly; exit dynamic rendering once SSR ships.

## Render budget in Search Console

Crawl stats show render queue depth. If render requests lag crawl by days, indexation falls behind publish rate — prioritize SSR for high-value templates first.""",

    "seo-meta-robots-noindex-patterns": """## CMS preview URLs

Headless CMS preview links must carry noindex and auth — editors share preview URLs in Slack. Middleware checks preview secret header plus robots meta. Automated scan fails build if preview host lacks noindex.""",

    "supply-chain-dependency-pinning": """## Lockfile policy in CI

Fail PR when package-lock.json changes without corresponding package.json intent — dependabot PRs excepted. Document emergency override label for security patches requiring immediate merge.""",

    "system-design-search-autocomplete": """## Latency SLO for suggest API

Target p99 under 50 ms for autocomplete — users type faster than 100 ms intervals. Cache prefix trie in memory per region; warm on deploy from snapshot file to avoid cold-start latency spike.""",

    "system-design-url-shortener": """## Custom slug collision policy

Custom aliases retry on conflict with user-visible error — do not silently append random suffix without telling marketing team. Reserve slug namespace for internal short links separate from customer vanity slugs.""",

    "terraform-workspaces-environments": """## CI guardrails for workspace selection

Pipeline injects `TF_WORKSPACE` from branch name — main maps to prod workspace only on approved runner pool. Local `terraform workspace select prod` blocked by wrapper script outside break-glass hours.""",

    "testing-mutation-testing": """## CI integration for Stryker

Run mutation tests nightly on `src/billing/` only — full repo mutation takes eight hours. Publish mutation score badge in README; drop below 75% blocks release branch merge.""",

    "testing-playwright-e2e": """## Test data isolation

Each Playwright worker gets unique email prefix `{workerIndex}+user@example.com` — parallel tests never collide on unique email constraint. Global setup seeds reference data once; tests only create deltas.""",

    "testing-property-based-testing": """## Shrinking noise in CI

Cap Hypothesis `max_examples` at 100 in CI, 1000 locally — full search runs nightly. `@settings(deadline=None)` on slow properties to avoid flaky timeout on loaded CI runners.""",

    "testing-snapshot-testing-tradeoffs": """## Snapshot size limits

CI fails if snapshot file grows more than 20% without approval label — prevents accidental whole-page snapshot of infinite scroll container.""",

    "testing-test-data-builders": """## Randomized data with seeds

Use fixed seed in CI builders for reproducible failures — `faker.seed(12345)` in test setup. Random data locally catches edge cases; seeded data in CI enables bisect.""",

    "web-performance-http3-quic-benefits": """## Enterprise UDP policy

Document UDP/443 allowlist request template for customers behind strict firewalls — include fallback verification steps. Support portal article explains H2 fallback is automatic; no user action required unless corporate proxy blocks UDP entirely.""",

    "web-performance-multi-step-form-wizard": """## Error recovery UX

When server returns 500 on step three submit, preserve local draft and show retry with exponential backoff — do not clear wizard state. Display support reference ID from error response for phone support correlation.""",

    "web-performance-optimistic-navigation-ui": """## Loading bar honesty

If navigation exceeds three seconds, escalate from skeleton to explicit message — optimism without timeout feels broken. Cap view transition duration at 300 ms even if data still loading.""",

    "typescript-utility-types-app-patterns": """## Branded types over aliases

Use `type UserId = string & { readonly __brand: unique symbol }` for IDs — prevents passing ProductId where UserId expected. Utility types compose with brands: `Pick<BrandedUser, 'id'>` still carries brand.""",

    "web-signals-fine-grained-reactivity": """## DevTools integration

Enable Preact Signals devtools in staging — visualize which components subscribed to which signal during interaction test. Production builds strip devtools hook; staging reproduces missed subscription bugs.""",
}


def main() -> None:
    results = []
    for slug in SLUGS:
        subprocess.run(["git", "checkout", "HEAD", "--", f"content/blog/{slug}.md"], cwd=ROOT, capture_output=True)
        fm, body = parse(git_content(slug))
        body = strip_body(body)
        for src in (EXPANSIONS, ADDONS, EXTRA):
            if slug in src:
                body = insert_section(body, src[slug])
        fm = update_fm(fm)
        count = write_post(slug, fm, body)
        results.append({"slug": slug, "words": count, "ok": count >= TARGET})

    ok = sum(1 for r in results if r["ok"])
    failed = [r for r in results if not r["ok"]]
    samples = sorted(results, key=lambda x: -x["words"])[:5]
    print(f"Completed: {ok}/{len(SLUGS)}")
    if failed:
        print(f"Under {TARGET}: {len(failed)}")
        for r in failed:
            print(f"  {r['slug']}: {r['words']}")
    print("Sample word counts:")
    for r in samples:
        print(f"  {r['slug']}: {r['words']}")


if __name__ == "__main__":
    main()
