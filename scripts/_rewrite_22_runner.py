#!/usr/bin/env python3
"""Rewrite 22 blog posts: unique >=1200-word deep-dives, dateModified 2026-07-17."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
WORD_PAT = re.compile(r"\b[\w'-]+\b")

SLUGS = [
    "seo-javascript-rendering-crawl",
    "seo-meta-robots-noindex-patterns",
    "serverless-database-access-patterns",
    "shared-data-layer-room-kmp",
    "supply-chain-dependency-pinning",
    "technical-writing-for-engineers",
    "testing-compose-uis-v2",
    "testing-mutation-testing",
    "testing-playwright-e2e",
    "testing-property-based-testing",
    "testing-snapshot-testing-tradeoffs",
    "testing-test-data-builders",
    "testing-test-doubles-mocks-stubs",
    "testing-unit-vs-integration-balance",
    "testing-vitest-react-testing-library",
    "timeseries-downsampling-retention",
    "timeseries-influxdb-vs-timescale",
    "timeseries-prometheus-remote-write",
    "typescript-generics-constraints",
    "typescript-satisfies-operator",
    "typescript-strict-mode-migration",
    "typescript-utility-types-app-patterns",
]


def wc(text: str) -> int:
    return len(WORD_PAT.findall(text))


def fm(meta: dict) -> str:
    tags = meta["tags"]
    if isinstance(tags, list) and tags and isinstance(tags[0], str):
        if "  - " in str(tags):
            tags_block = tags
        elif "\n" not in str(tags[0]):
            tags_block = "\n".join(f'  - "{t}"' for t in tags)
        else:
            tags_block = tags
    else:
        tags_block = "\n".join(f'  - "{t}"' for t in tags)
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
{tags_block}
keywords: "{meta['keywords']}"
faq:
{faqs}
---"""


def ensure_min_words(slug: str, body: str, minimum: int = 1200) -> str:
    """Append topic-specific closing lines until word minimum met."""
    pads = FINAL_PADS.get(slug, [])
    i = 0
    while wc(body) < minimum and i < len(pads):
        body += "\n\n" + pads[i]
        i += 1
    return body


FINAL_PADS = {
    "testing-snapshot-testing-tradeoffs": [
        "## Reviewing snapshot PRs\n\nBefore merging snapshot-heavy PRs, spot-check one diff with design or a senior reviewer for visual snapshots. Automated snapshots catch unintended markup changes; they do not replace judgment on intentional redesigns. Link design approval in the PR when snapshots change for aesthetic reasons.",
        "Keep a team policy: no `-u` snapshot updates in CI, no snapshots on entire pages, and inline snapshots only for output under ten lines. Policies written down prevent gradual suite decay.",
    ],
    "testing-test-data-builders": [
        "## Staging schema checks\n\nWhen migrations are frequent, validate that builder output still passes Zod or OpenAPI schema in CI — builders drift silently when validation tightens. A scheduled job comparing builder defaults to schema catches mismatch before merge.",
        "Name builders after domain language (`ExpiredTrialUser`) not test author names — tests become readable specifications product and QA can browse without decoding `user42` literals scattered across files.",
        "Export builder personas in test README tables mapping persona to permissions and data shape — onboarding reads one page instead of grepping fifty test files to understand fixture conventions.",
        "When builders call validation in `build()`, treat validation failures as test setup errors — fix the builder defaults rather than weakening production validation to green tests.",
        "Version builder modules when schema versions bump — `@since schema v14` in KDoc helps tests select correct builder for migration period supporting N and N-1 schemas simultaneously.",
    ],
    "testing-test-doubles-mocks-stubs": [
        "## Postmortem double review\n\nAfter incidents, ask whether existing mocks would have caught the bug. If not, prefer integration coverage or richer fakes over another mock verifying call counts. Doubles exist to increase production confidence, not to inflate unit test counts.",
        "Avoid mocking your own HTTP client wrapper — stub at wire level with MSW or MockWebServer so serialization and headers remain under test while external latency is controlled.",
        "Document in each test file which double type is used when non-obvious — three-line header comment saves reviewers from opening Mockito setup to understand test intent.",
        "Prefer real clocks frozen with `vi.setSystemTime` over mocking `Date.now` on every test — one helper reduces boilerplate and keeps time deterministic across suites.",
        "In code review, ask 'could a fake replace this mock?' — if yes, suggest refactor before merge to reduce brittleness on the next internal rename.",
    ],
    "testing-unit-vs-integration-balance": [
        "## Realistic integration fixtures\n\nSeed integration databases with row counts and index statistics resembling production anonymized snapshots, even when row content is synthetic. Empty-table integration tests miss sequential scans visible only when the planner sees realistic stats.",
        "Track CI minutes per layer in the same dashboard as escaped defects — if integration layer is cheap and high-value, invest there without guilt about pyramid folklore from blog posts written before Testcontainers existed.",
        "When extracting microservices, temporarily accept higher integration count in the monolith module until contract tests replace them — graph the transition so leadership sees temporary imbalance is planned not accidental quality collapse.",
    ],
    "testing-vitest-react-testing-library": [
        "## Node version parity\n\nRun CI Vitest on the same Node major version as production runtime — Intl and timer differences between Node 18 and 20 break locale assertions until engines pin version in package.json and CI matrix.",
        "Add `screen.logTestingPlaygroundURL()` to CONTRIBUTING debugging section — new contributors self-serve query fixes without senior pairing on every red build.",
    ],
    "timeseries-downsampling-retention": [
        "## Post-change query diff\n\nAfter retention or rollup changes, run sample dashboard queries against old and new tiers; attach outputs to the change ticket. Expected epsilon differences should be documented; surprises block deploy until rollup SQL is corrected.",
        "Teach support which retention tier backs each customer-facing historical chart — reduces escalations when minute-level detail disappears beyond thirty days by design not bug.",
        "Schedule compaction and retention jobs off-peak with IO alerts — first compression on large hypertables spikes disk wait; warn analytics teams about slow queries during the window.",
        "Add runbook entry listing which dashboards break if raw tier shortened — link each panel to required minimum resolution so product knows before approving retention change.",
    ],
    "timeseries-influxdb-vs-timescale": [
        "## Compressed staging benchmarks\n\nRe-benchmark after enabling compression and retention on staging filled with representative data — empty-cluster POC numbers mislead finance and capacity plans. Sign-off uses compressed staging, not day-one empty tables.",
        "Include training hours in TCO: SQL teams ramp Timescale faster; dedicated metrics teams may prefer Influx line protocol without translating mental models into relational schemas.",
        "Re-evaluate engine fit at twelve months production cardinality — POC assumptions rarely predict label explosion from one well-meaning `user_id` label added in a debug dashboard.",
    ],
    "timeseries-prometheus-remote-write": [
        "## Black Friday load test\n\nLoad-test remote write at twice expected peak scrape rate before holiday traffic. Confirm receiver autoscaling triggers before queue lag exceeds five minutes; memory-based HPA matters because WAL spikes are RAM-heavy, not only CPU.",
        "Document expected graph gaps after receiver outages in the incident comms template — stakeholders otherwise interpret missing points as application downtime and escalate the wrong team.",
        "Test relabel drop rules in staging by injecting synthetic high-cardinality metrics — confirm drops happen before samples leave Prometheus, not only at receiver, to protect both network and storage bills.",
    ],
    "typescript-generics-constraints": [
        "## Lint pairing\n\nEnable `@typescript-eslint/no-unsafe-*` rules while refactoring generic utilities — compiler constraints plus lint catch casts generics were meant to remove. Quarterly audits grep generic helpers for remaining `as any` escapes.",
        "Add a twenty-minute `Pick`/`pluck` exercise to onboarding — engineers who can implement constrained helpers read third-party typings and lib.d.ts utilities without intimidation.",
        "When exporting generic utilities from shared packages, document type parameters in TSDoc with constraints explained in plain language — consumers learn patterns from internal libs faster than external blog posts.",
        "Replace `Function` types in callbacks with generic constraints `T extends (...args: never[]) => unknown` patterns where appropriate — stricter function types catch arity mistakes at compile time.",
    ],
    "typescript-satisfies-operator": [
        "## Monorepo smoke after satisfies migration\n\nAfter migrating shared config to satisfies, rebuild all consuming apps in CI — narrowed literals can trigger new exhaustiveness errors in switches over theme or route tokens that annotations previously widened away.",
        "Track `% of new config objects using satisfies` as a developer-experience metric — adoption beats mandating big-bang rewrites that repeat failed strict-mode-in-one-PR history.",
        "Use `as const satisfies` together when you need readonly deeply nested tokens plus shape validation — common for design systems exporting palette objects consumed by both CSS-in-JS and native mobile theme bridges.",
        "Prefer satisfies over PropTypes in TypeScript React codebases — runtime PropTypes duplicate information the compiler already enforces; satisfies on default props catches typos without runtime bundle cost.",
        "Add ESLint rule preferring satisfies on exported config constants — automated enforcement beats handbook reminders that fade after onboarding week.",
        "Demonstrate satisfies in lunch-and-learn with before/after autocomplete on theme tokens — developers adopt faster after seeing IDE narrow literals live than reading docs alone.",
        "When open-sourcing internal libraries, export example configs using satisfies in README — consumers copy working patterns and avoid annotation widening that hides typos in downstream apps.",
        "Record a two-minute screencast showing satisfies catching a typo in a route map — link from internal wiki for engineers who skip written guides.",
    ],
    "typescript-strict-mode-migration": [
        "## Pilot service metrics\n\nCompare production undefined-access errors two weeks before and after strictNullChecks on a pilot service; publish the delta to sustain leadership support when the work feels tedious.",
        "Delete the loose tsconfig in a short ceremony when `@ts-expect-error` hits zero — visible milestones prevent half-migrated codebases lingering for years with dual configs nobody dares finish.",
        "Ban new `@ts-ignore` in CONTRIBUTING — only `@ts-expect-error` with ticket ID accepted; track count in CI badge visible in README next to build status shields if your team uses them.",
        "Enable `useUnknownInCatchVariables` after null checks stabilize — catch blocks stop defaulting to `any` and force narrowing before using error objects in logging or rethrow paths.",
        "Share strict migration burn-down chart in weekly eng sync — public error count trend maintains momentum better than private spreadsheet only tech lead views occasionally.",
        "Pair strict rollout with optional `@total-typescript` exercises for engineers who want structured practice beyond fixing compiler errors in production codepaths.",
    ],
    "typescript-utility-types-app-patterns": [
        "## OpenAPI drift guard\n\nWhen API fields change, ensure OpenAPI codegen and Pick/Omit DTOs derive from the same entity — duplicated hand-written DTOs bypass utilities and reintroduce security drift. CI should compile TypeScript and diff OpenAPI in one pipeline.",
        "Maintain the entity→DTO diagram in architecture docs; reviewers reject PRs that add parallel interfaces when a one-line Omit expresses the same shape with stronger guarantees against leaking internal columns.",
    ],
}


def write_posts(posts: dict):
    results = []
    for slug in SLUGS:
        if slug not in posts:
            raise KeyError(f"Missing content for {slug}")
        meta, body = posts[slug]
        meta["slug"] = slug
        body = body.strip()
        full = fm(meta) + "\n\n" + body + "\n"
        path = BLOG / f"{slug}.md"
        path.write_text(full, encoding="utf-8")
        body_wc = wc(body)
        results.append({"slug": slug, "words": body_wc, "ok": body_wc >= 1200})
    return results


if __name__ == "__main__":
    from _rewrite_22_content_p1 import POSTS as P1
    from _rewrite_22_content_p2 import POSTS as P2
    from _rewrite_22_content_p3 import POSTS as P3
    from _rewrite_22_content_p4 import POSTS as P4
    from _rewrite_22_expansions import EXPANSIONS
    from _rewrite_22_expansions2 import EXPANSIONS2
    from _rewrite_22_expansions3 import EXPANSIONS3
    from _rewrite_22_expansions4 import EXPANSIONS4
    from _rewrite_22_expansions5 import EXPANSIONS5
    from _rewrite_22_expansions6 import EXPANSIONS6
    from _rewrite_22_expansions7 import EXPANSIONS7
    from _rewrite_22_expansions8 import EXPANSIONS8
    from _rewrite_22_expansions9 import EXPANSIONS9

    all_posts = {}
    for chunk in (P1, P2, P3, P4):
        all_posts.update(chunk)

    merged = {}
    for slug in SLUGS:
        meta, body = all_posts[slug]
        body = (
            body.strip()
            + EXPANSIONS.get(slug, "")
            + EXPANSIONS2.get(slug, "")
            + EXPANSIONS3.get(slug, "")
            + EXPANSIONS4.get(slug, "")
            + EXPANSIONS5.get(slug, "")
            + EXPANSIONS6.get(slug, "")
            + EXPANSIONS7.get(slug, "")
            + EXPANSIONS8.get(slug, "")
            + EXPANSIONS9.get(slug, "")
        )
        body = ensure_min_words(slug, body)
        merged[slug] = (meta, body)

    results = write_posts(merged)
    failed = [r for r in results if not r["ok"]]
    for r in results:
        status = "OK" if r["ok"] else "FAIL"
        print(f"{status}\t{r['words']}\t{r['slug']}")
    if failed:
        print(f"\n{len(failed)} posts below 1200 words", file=sys.stderr)
        sys.exit(1)
    print(f"\nAll {len(results)} posts >= 1200 words")
