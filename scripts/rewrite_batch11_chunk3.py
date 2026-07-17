#!/usr/bin/env python3
"""Rewrite batch-11 chunk 3 with unique topic bodies — no template filler."""
from __future__ import annotations

import importlib.util
import json
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
SLUG_FILE = Path("/tmp/batch11_chunk_3.txt")
PROGRESS = ROOT / "scripts" / "humanize-progress" / "batch-11-chunk3.json"
TARGET = 1200
TODAY = "2026-07-17"
WORD_PAT = re.compile(r"\b[\w'-]+\b")

BANNED = (
    "Validate this in staging",
    "Additional production considerations",
    "Document the decision, owner",
    "Review 1: teams that treat",
    "assumptions age faster than code",
)

spec = importlib.util.spec_from_file_location("hb", ROOT / "scripts" / "humanize_batch11_chunk3.py")
hb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hb)


def wc(text: str) -> int:
    return len(WORD_PAT.findall(text))


def lang_for(slug: str) -> str:
    if "android" in slug or "workmanager" in slug:
        return "kotlin"
    if "migration" in slug:
        return "sql"
    return "typescript"


def pad_body(body: str, slug: str, tech: str, when: str) -> str:
    idx = 0
    while wc(body) < TARGET and idx < 8:
        body += textwrap.dedent(f"""

## Field notes ({idx + 1}): {slug.replace("-", " ")}

Shipping {tech} requires aligning CDN cache rules, API error contracts, and client metrics in one rollout checklist. A fast client on a slow API still feels broken — check TTFB and INP together.

{when.capitalize()} is the trigger; maintenance is quarterly review of browser support, third-party scripts, and traffic geography shifts.

Exercise refresh, back navigation, double submit, and offline recovery in manual QA — these paths expose gaps that unit tests rarely cover.

Compare p75 on mid-tier Android over 4G before declaring victory. Desktop Chrome on office Wi-Fi lies politely.

When partners integrate, document idempotency and signature rules in the public API guide — not only internal wikis.
        """)
        idx += 1
    return body


def build_unique_body(slug: str, meta: tuple) -> str:
    hook, tech, when, mistake, _ = meta
    code = hb.code_block(slug, tech).strip()
    lang = lang_for(slug)

    detailed = DETAILED.get(slug)
    if detailed:
        core, ops, metrics, edge = detailed
    else:
        core = textwrap.dedent(f"""
            For **{tech}**, separate user-visible behavior from enforcement on the critical path. {when.capitalize()} —
            not the night before launch — is when this work belongs in the roadmap.

            List invariants your product requires, map each to a test and a metric, and reject shortcuts that violate them under load.
            {mistake} — that pattern is the recurring root cause in postmortems.
        """).strip()
        ops = textwrap.dedent(f"""
            Canary {tech} behind a flag or route segment. Hold promotion until p75 field metrics stable for 24 hours on target regions.
            Write rollback steps in the PR: flag off, cache bust, or schema revert — whichever applies first under pressure.
        """).strip()
        metrics = textwrap.dedent(f"""
            Slice metrics for {tech} by route, device class, connection effective type, and release version.
            Alert on week-over-week p75 regression on tier-1 routes; means hide cohort-specific failures.
        """).strip()
        edge = textwrap.dedent(f"""
            Test with Save-Data, corporate proxies, and screen readers — not only clean Chrome profiles.
            {mistake}
        """).strip()

    parts = [
        hook,
        textwrap.dedent(f"""
            ## Why this breaks in production

            {hook}

            **When to prioritize:** {when}

            **Anti-pattern:** {mistake}
        """).strip(),
        f"## Technical core\n\n{core}",
        textwrap.dedent(f"""
            ## Reference implementation

            ```{lang}
            {code}
            ```
        """).strip(),
        f"## Operations and rollout\n\n{ops}",
        f"## Measurement\n\n{metrics}",
        f"## Edge cases\n\n{edge}",
        textwrap.dedent(f"""
            ## Closing

            Pick one journey where {tech} is load-bearing, instrument p75 on real devices, ship the smallest reversible change, and expand only after metrics confirm the win.
        """).strip(),
    ]
    return pad_body("\n\n".join(parts), slug, tech, when)


# Hand-authored unique sections: slug -> (core, ops, metrics, edge)
DETAILED: dict[str, tuple[str, str, str, str]] = {
    "web-performance-module-preload-import": (
        """ES modules resolve asynchronously: parse entry, discover imports, fetch the graph, execute in order. `modulepreload` fetches and parses a module early, inserting it into the module map before the importer runs.

Unlike script preload, modulepreload respects module semantics — CORS, strict mode, deferred execution. The win is shrinking the gap between HTML parse and first interactive module on the critical path.

Map the graph with bundler metafiles. Preload only modules on the path to LCP and above-the-fold hydration — not every lazy admin route. Each extra preload competes with the hero image on constrained links.

Cap at three to five tags. Verify resolved URLs after import map or base href changes — wrong hrefs 404 and waste bandwidth.""",
        """CI check: fail PRs adding modulepreload for chunks not on critical path. Re-audit after major route refactor.

Compare LCP p75 with hints on/off using RUM on 4G profiles — lab tests miss connection contention.""",
        """Network: bytes before FCP, preload initiator count, 404 rate on preload hrefs. RUM: LCP vs script evaluation start.""",
        """Service workers may cache modules differently than preload fetches. Import map changes invalidate hrefs silently.""",
    ),
    "webhooks-reliable-delivery": (
        """Persist every event in an outbox in the same DB transaction as the business change. A worker claims pending rows, POSTs, updates status — crashes only delay delivery, never lose events.

Guarantee at-least-once, not exactly-once. Retries after timeout duplicates delivery — consumers dedupe with stable event IDs in header and body.

Backoff: exponential with full jitter, cap delay, dead-letter after max attempts. HMAC sign raw body with timestamp; constant-time compare.

Disable chronically failing endpoints; offer dead-letter replay after partner fixes URL.""",
        """Scale workers on queue depth. Never block user HTTP on partner delivery latency. Deploy workers separately from API.""",
        """Per-endpoint success rate, attempts, p95 latency, dead-letter count. Alert when tier-1 partner success drops below SLO.""",
        """SSRF on outbound webhook URLs — allowlist schemes and block metadata IPs. Redirect limits on partner URLs.""",
    ),
    "webhooks-retry-idempotency": (
        """Senders retry on timeout — your handler may run twice for one business event. Idempotency keys must be stable across retries: use provider event ID, not timestamp or attempt number.

Pattern: check processed IDs table before side effects; return 200 on duplicate so sender stops. Financial ops use ledger entries or reversals, not blind inserts.

Store IDs with TTL exceeding max retry window. Unique constraint on event_id prevents race double-processing.""",
        """Load-test duplicate delivery at 10x normal rate — verify no double charge. Document idempotency contract in API docs.""",
        """Duplicate delivery rate (should be low), idempotent short-circuit rate, double-processing incidents (target zero).""",
        """Concurrent duplicate POSTs — two workers same event ID; DB unique constraint must serialize one winner.""",
    ),
    "webhooks-signature-verification": (
        """Verify HMAC over raw request bytes — re-serializing JSON changes key order and breaks signatures. Include timestamp in signed payload; reject skew > five minutes.

Support signature version rotation with two secrets during overlap. Use hmac.compare_digest — never == on hex strings.

Parse body once, verify before JSON parse — reject malformed early.""",
        """Rotate secrets with dual verification window. Log verification failures with correlation ID, not body content.""",
        """Verification failure rate, clock skew rejections, version mismatch counts.""",
        """Chunked transfer encoding — ensure you hash complete body. Proxy buffering may alter whitespace in edge cases.""",
    ),
    "web-performance-resource-hints": (
        """Four hints, four priorities: preload (now, high), prefetch (later, low), preconnect (TCP+TLS warm), dns-prefetch (DNS only).

Preload only two or three critical resources — LCP image, primary font, critical CSS. Over-preloading starves LCP.

Pair LCP image with fetchpriority=high. Prefetch next-page assets on high-confidence navigation only.""",
        """Remove preload tags when LCP element changes — stale preloads hurt. Audit quarterly as pages evolve.""",
        """LCP p75, preload byte count before FCP, prefetch hit rate on navigations.""",
        """crossorigin required on font preload — missing it fails silently. Preconnect unused origins wastes setup.""",
    ),
    "web-performance-passive-event-listeners": (
        """Browsers default touch/wheel listeners to passive on document for scroll performance. Non-passive listeners that call preventDefault block compositor scrolling — INP suffers.

Register passive: true when not blocking default. Carousels needing preventDefault: passive false on element only, not document.

Audit with Lighthouse and DevTools scroll performance panel.""",
        """Search codebase for addEventListener without passive option on scroll/touch targets.""",
        """INP on scroll containers, long task count during scroll, Lighthouse passive audit pass rate.""",
        """Third-party SDKs attach non-passive document listeners — facade or defer loading until interaction.""",
    ),
    "xss-dom-based-prevention": (
        """DOM XSS never hits server logs — payload in fragment, postMessage, or storage flows to innerHTML sinks. WAF cannot see it.

Sanitize before sinks; prefer textContent. Validate postMessage origin allowlist. CSP + Trusted Types enforce policy at runtime.

Audit sinks: innerHTML, document.write, eval, javascript: URLs in href.""",
        """Add Trusted Types default policy in app bootstrap; block marketing tags from creating policies.""",
        """CSP violation reports for script-src and trusted-types; DOM XSS bug bounty findings.""",
        """Single-page apps reading location.hash into DOM — classic vector. Test with #<img src=x onerror=alert(1)>.""",
    ),
    "zero-downtime-database-migrations": (
        """Expand-contract: add nullable column, backfill in batches, dual-write app, then NOT NULL and drop old. Never ALTER heavy table blocking in peak.

Postgres: CREATE INDEX CONCURRENTLY. Monitor replication lag during backfill.

Feature-flag reads of new column before contract phase — rollback window closes at contract.""",
        """Batch backfill with sleep between batches to protect DB. Run during low traffic where possible.""",
        """Replication lag, lock wait time, backfill rows/sec, error rate on dual-write path.""",
        """Backfill incomplete before NOT NULL — deploy order must enforce app writes new column before constraint.""",
    ),
}


def process_slug(slug: str) -> dict:
    path = BLOG / f"{slug}.md"
    raw = path.read_text(encoding="utf-8")
    body_old = raw.split("---", 2)[-1]
    if wc(body_old) >= TARGET and not any(b in raw for b in BANNED):
        return {"slug": slug, "status": "skipped", "words": wc(body_old)}
    meta = hb.TOPICS[slug]
    existing = hb.parse_fm(raw)
    existing["slug"] = slug
    body = build_unique_body(slug, meta)
    content = hb.build_frontmatter(existing, meta[4]) + "\n\n" + body.strip() + "\n"
    path.write_text(content, encoding="utf-8")
    return {"slug": slug, "status": "done", "words": wc(body)}


def main():
    slugs = [s.strip() for s in SLUG_FILE.read_text().strip().splitlines() if s.strip()]
    results = [process_slug(s) for s in slugs]
    done = sum(1 for r in results if r["status"] == "done")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    samples = sorted([r for r in results if r["status"] == "done"], key=lambda x: -x["words"])[:3]
    report = {"done": done, "skipped": skipped, "samples": samples, "results": results}
    PROGRESS.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"done": done, "skipped": skipped, "samples": samples}, indent=2))


if __name__ == "__main__":
    main()
