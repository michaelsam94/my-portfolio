#!/usr/bin/env python3
"""Apply unique ≥1200-word posts for b11s_3/4/5 slugs — no shared boilerplate."""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
DATE = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")

SLUG_FILES = ["/tmp/b11s_3.txt", "/tmp/b11s_4.txt", "/tmp/b11s_5.txt"]

# Already handled by _rewrite_22_runner in same batch
SKIP = {
    "testing-compose-uis-v2",
    "testing-test-doubles-mocks-stubs",
    "supply-chain-dependency-pinning",
    "shared-data-layer-room-kmp",
    "technical-writing-for-engineers",
    "timeseries-influxdb-vs-timescale",
    "testing-unit-vs-integration-balance",
    "timeseries-prometheus-remote-write",
}

STRIP = [
    r"\n## Operating [^\n]+\n.*?(?=\n## |\Z)",
    r"\n## Additional depth on[^\n]*\n.*?(?=\n## |\Z)",
    r"\n## Closing notes\n.*?(?=\n## |\Z)",
    r"Validate this in staging with production-like data volume[^\n]*\n",
    r"## Options compared honestly\n.*?(?=\n## |\Z)",
    r"## Technical deep dive\nWhen teams skip this layer[^\n]*\n",
    r"## Patterns that compose well\n\n",
    r"## Pre-ship checklist\n\n",
    r"## Where to go from here\n.*?(?=\n## |\Z)",
    r"## Related reading and specs\n.*?(?=\n## |\Z)",
    r"## Coordination with backend and platform\n.*?(?=\n## |\Z)",
    r"If I were prioritizing one action this sprint[^\n]*\n",
    r"Performance and reliability work compounds when tied to business metrics[^\n]*\n",
    r"## Why this breaks in production\n.*?(?=\n## |\Z)",
    r"## How it works\nMap the full pipeline[^\n]*\n.*?(?=\n## |\Z)",
    r"## Implementation\nShip the smallest vertical slice[^\n]*\n.*?(?=\n## |\Z)",
    r"## Anti-patterns to delete\n.*?(?=\n## |\Z)",
    r"## The question behind the ticket\n\n",
    r"## Answer with nuance\n\n",
    r"## Implementation walkthrough\n.*?(?=\n## |\Z)",
    r"## Security angle\nFrontend and backend changes share[^\n]*\n.*?(?=\n## |\Z)",
    r"## Testing beyond happy path\n\n",
    r"## Day-two operations\n\n",
    r"## What I'd ship this week\n.*?(?=\n## |\Z)",
]

BANNED = (
    "Validate this in staging",
    "If I were prioritizing one action",
    "Options compared honestly",
    "When teams skip this layer",
    "is a production pattern for frontend and product engineering teams",
    "Teams ship without field measurement",
    "What is the main production risk with",
    "Adopt when you have field data or user research showing pain",
    "Architecture depth for ",
    "Deep implementation notes",
    "On-call and regression guards",
)

GENERIC_FAQ_MARKERS = (
    "is a production pattern for frontend",
    "Teams ship without field measurement",
    "What is the main production risk with",
    "Adopt when you have field data",
)


def load_modules():
    mods = {}
    for name, path in [
        ("ex2", "expand_batch11_chunk2.py"),
        ("fr", "b11_final_rewrite.py"),
        ("rw", "b11_rw_combined.py"),
        ("rwe", "b11_rw_expansions.py"),
    ]:
        spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mods[name] = mod
    return mods


MODS = load_modules()


def load_slugs() -> list[str]:
    slugs = []
    for f in SLUG_FILES:
        with open(f) as fh:
            slugs.extend(line.strip() for line in fh if line.strip())
    return slugs


def wc(text: str) -> int:
    return len(WORD.findall(text))


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def git_raw(slug: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "show", f"HEAD:content/blog/{slug}.md"],
            text=True,
            cwd=ROOT,
        )
    except subprocess.CalledProcessError:
        return None


def parse_fm(raw: str) -> dict:
    fm = raw.split("---", 2)[1]
    d: dict = {}
    for key in ("title", "description", "datePublished", "keywords"):
        m = re.search(rf'^{key}:\s*"([^"]*)"', fm, re.M)
        if m:
            d[key] = m.group(1)
    tags, on = [], False
    for line in fm.splitlines():
        if line.strip() == "tags:":
            on = True
            continue
        if on:
            if line.startswith("  - "):
                tags.append(line[4:].strip().strip('"').strip("'"))
            elif line.strip() and not line.startswith(" "):
                break
    if tags:
        d["tags"] = tags
    faqs, q, on = [], None, False
    for line in fm.splitlines():
        if line.strip() == "faq:":
            on = True
            continue
        if not on:
            continue
        if line.startswith("  - q:"):
            q = line.split('"')[1] if '"' in line else line.split(":", 1)[1].strip()
        elif line.startswith("    a:") and q:
            a = line.split('"')[1] if '"' in line else line.split(":", 1)[1].strip()
            faqs.append((q, a))
            q = None
    d["faq"] = faqs[:3]
    return d


def faq_is_generic(faqs: list[tuple[str, str]]) -> bool:
    if len(faqs) < 3:
        return True
    blob = " ".join(q + " " + a for q, a in faqs)
    return any(m in blob for m in GENERIC_FAQ_MARKERS)


def build_fm(meta: dict, slug: str) -> str:
    lines = [
        "---",
        f'title: "{esc(meta.get("title", slug))}"',
        f'slug: "{slug}"',
        f'description: "{esc(meta.get("description", ""))}"',
        f'datePublished: "{meta.get("datePublished", DATE)}"',
        f'dateModified: "{DATE}"',
        "tags:",
    ]
    for t in meta.get("tags", ["Engineering"]):
        lines.append(f'  - "{esc(t)}"')
    lines.append(f'keywords: "{esc(meta.get("keywords", slug))}"')
    lines.append("faq:")
    for q, a in meta.get("faq", [])[:3]:
        lines.append(f'  - q: "{esc(q)}"')
        lines.append(f'    a: "{esc(a)}"')
    lines.append("---")
    return "\n".join(lines)


def strip_body(body: str) -> str:
    for pat in STRIP:
        body = re.sub(pat, "\n", body, flags=re.S)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def gather_expansions(slug: str) -> list[str]:
    parts: list[str] = []
    sources = [
        MODS["fr"].UNIQUE.get(slug),
        MODS["ex2"].EXPANSIONS.get(slug),
        MODS["rw"].EXTRA.get(slug),
    ]
    rwe = MODS["rwe"].EXPANSIONS.get(slug, [])
    if isinstance(rwe, list):
        sources.extend(rwe)
    elif isinstance(rwe, str):
        sources.append(rwe)
    for src in sources:
        if src and src.strip() and src.strip() not in parts:
            parts.append(src.strip())
    return parts


# Unique padding — topic-specific only, no shared template paragraphs
PADDING: dict[str, str] = {
    "sec-dependency-audit-automation": """
## Gradle and Maven in polyglot monorepos

Java services need `dependency-check-maven` or OWASP Dependency-Check in Gradle with suppressions file reviewed in PR. Python microservices use `pip-audit` against the locked requirements export. One central security dashboard aggregating OSV results from all lockfile types beats siloed per-language alerts nobody triages.

## License compliance alongside CVE scanning

FOSSA or ScanCode flag GPL contamination in transitive deps — legal risk separate from CVE severity. Block merge when copyleft appears in mobile SDK shipped to App Store with incompatible license terms.""",
    "web-performance-debounce-throttle-input": """
## React 19 useDeferredValue for search

When debouncing controlled input state, consider `useDeferredValue(query)` so typing stays instant while filtered list updates lag one frame behind — smoother than debouncing setState on every keystroke for large virtualized lists.

## Passive listeners on scroll containers

Throttle handlers attached to scroll must use `{ passive: true }` or browsers block scrolling waiting for preventDefault check. Debounced resize handlers on window similarly benefit from passive where applicable.""",
    "testing-contract-testing-microservices": """
## Pact broker and can-i-deploy

Publish pacts to Pact Broker; `can-i-deploy` gate checks whether consumer version is safe against current provider production version before deploy. Without broker, pact JSON files in git rot when teams forget to regenerate.

## Bi-directional contracts

Provider-driven contracts help when many consumers share one API — provider publishes expected requests; consumers verify they still match. Use when consumer-driven pacts become unmanageable with twenty downstream teams.""",
    "serverless-event-driven-architecture": """
## EventBridge archive and replay

Enable event archive on domain bus for compliance and disaster recovery. Replay filtered events to new consumer versions during projection rebuilds — idempotency table mandatory before replay button gets clicked in prod incident.

## Partial batch failure in SQS Lambda

Report batch item failures so only failed messages retry:

```python
return {"batchItemFailures": [{"itemIdentifier": record["messageId"]}]}
```

Without partial failure, one poison message in batch of ten causes nine successful reprocessing duplicates.""",
    "web-dialog-element-modal": """
## Nested dialogs and stacking

Second `showModal()` on nested dialog works in modern browsers — focus traps inner dialog. Close inner before outer. For drawer-over-modal patterns, prefer single dialog with CSS layout over double modal stack confusing screen readers.

## Scrollable dialog bodies

Long content inside dialog needs `max-height` and `overflow-y: auto` on inner container, not the dialog element itself — otherwise backdrop scroll lock fights user trying to read terms of service.""",
    "web-performance-breadcrumb-navigation-seo": """
## JSON-LD BreadcrumbList validation

Each `ListItem` needs `position`, `name`, and `item` URL. Last item may omit `item` when representing current page without link. Mismatch between visible breadcrumb text and schema triggers rich result warnings in Search Console.

## Mobile truncation UX

Truncate middle segments on narrow viewports (`Home > … > Product`) while keeping full schema in JSON-LD — users see compact trail; crawlers get complete hierarchy.""",
    "vector-db-pgvector-postgres": """
## HNSW versus IVFFlat in pgvector

HNSW builds slower, queries faster, no training step — default for most new deployments. IVFFlat needs `lists` tuning and periodic rebuild after bulk insert — legacy choice when HNSW memory budget too high on small instances.

## Connection pooling with vector queries

PgBouncer transaction mode breaks prepared statements some ORMs use for vector inserts — session mode or disable prepared statements for embedding batch jobs.""",
    "web-performance-404-page-product-sites": """
## Soft 404 detection

Return HTTP 404 status, not 200 with "not found" text — Google treats soft 404s as quality issues. Monitor Search Console soft 404 report after SPA routing changes.

## 404 search and popular links

Embed site search and top category links on 404 — recovered sessions convert better than minimalist error pages. Track 404 URL frequency in analytics; fix top broken inbound links from marketing campaigns.""",
    "running-local-llms-on-device": """
## Model quantization on Apple Silicon

MLX and llama.cpp GGUF Q4_K_M balances quality and speed on M-series Macs. Benchmark tokens/sec for your prompt template length — marketing claims use tiny contexts.

## Privacy boundary for on-device inference

User prompts never leave device — document in privacy policy. Crash logs must scrub prompt fragments if logging enabled for debug builds only.""",
    "vue-3-composition-api-patterns": """
## toRef and toRefs for destructuring props

Destructuring props loses reactivity — use `toRefs(props)` or access via `props.x` in setup. Common bug when migrating Options API components.

## watchEffect versus watch cleanup

`watchEffect` runs immediately and tracks deps automatically — use for sync side effects. Provide cleanup function returning from watch callback when registering DOM listeners or timers.""",
    "vector-db-sharding-scaling": """
## Resharding without full downtime

Dual-write to old and new shard ring during migration; backfill historical vectors; flip read path when lag zero. Vector IDs must be globally unique across shards — UUID not auto-increment.

## Cross-shard query fan-out

Global k-NN requires querying all shards and merging top-k — latency grows linearly. Consider routing queries by metadata filter first to shrink shard set.""",
    "web-accessibility-keyboard-navigation": """
## Skip links and landmark targets

Skip link href must match existing `id` on `main` — duplicate ids break focus target. Test skip link as first Tab stop on every template variant.

## Focus visible versus focus outline removal

Never `outline: none` without `:focus-visible` replacement — keyboard users lose position. Design system tokens for focus ring color meeting 3:1 contrast against adjacent colors.""",
    "web-components-form-association": """
## Labels and form association for custom controls

Use `internals.setFormValue` together with `aria-labelledby` pointing to visible label — form association does not replace accessible naming for screen readers.

## Disabled and readonly states

Implement `formDisabledCallback` and reflect disabled state to internal controls — browser grayed-out styling may not apply automatically to shadow DOM widgets.""",
    "software-cqrs-event-sourcing-tradeoffs": """
## Snapshot frequency tuning

Snapshot every N events or every T minutes — replay from snapshot plus tail events faster than full stream replay. Snapshot too frequent bloats storage; too rare makes recovery slow.

## Event schema upcasting

Version events with `schemaVersion` field; upcasters transform v1 to v2 on read during replay. Test upcasters with golden event fixtures from production anonymized samples.""",
    "software-domain-driven-design-strategic": """
## Team topology and context alignment

Conway's law: organization chart becomes architecture. Align squad boundaries to bounded contexts — one team per context ideal. Shared context across five teams guarantees integration meetings without end.

## Evolutionary architecture metrics

Track cross-context coupling via import graph or API call matrix. Rising coupling signals context boundary erosion — refactor or merge contexts deliberately, not accidentally.""",
    "spring-boot-vs-ktor-2026": """
## Virtual threads on Spring Boot 3.2+

Project Loom virtual threads make blocking JDBC acceptable at higher concurrency — configure `spring.threads.virtual.enabled=true` and load-test against platform thread pool baseline.

## Ktor server engine selection

Netty versus CIO — Netty mature for HTTP/1.1 and HTTP/2; CIO lighter for microservices with moderate traffic. Benchmark with your typical JSON payload sizes, not hello-world.""",
    "vector-search-hnsw-tuning": """
## ef_search versus recall tradeoff

Higher `ef_search` at query time improves recall at latency cost — tune per use case: support search needs high recall; autocomplete may accept lower recall for speed.

## Reindex after parameter change

Changing M or ef_construction requires index rebuild — plan maintenance window or blue-green index alias swap in Elasticsearch/OpenSearch.""",
    "web-accessibility-screen-reader-testing": """
## Screen reader plus browser matrix

Test NVDA+Firefox and VoiceOver+Safari minimum — Chrome+NVDA behaves differently from Firefox+NVDA on same page. Document expected behavior per combo in test plan.

## Live region politeness for dynamic updates

`aria-live="polite"` for non-urgent status; `assertive` only for errors requiring immediate attention — overuse of assertive interrupts task flow.""",
    "software-architecture-decision-records": """
## ADR templates that get used

Keep template to Context, Decision, Consequences — three sections. Long templates gather dust. Link ADR from code comments at integration points: `// See ADR-0014 for cache TTL rationale`.

## Superseding without losing history

Mark status `Superseded by ADR-0023` — never delete rejected decisions; newcomers repeat debates without tombstones.""",
    "state-of-flutter-2026": """
## Wasm and Flutter web compile target

Wasm compilation improves web performance but increases bundle size — measure LCP on 3G for your target markets before enabling by default.

## Impeller on older Android GPUs

Maintain device lab with minimum supported hardware — Mali-G52 and similar may show rendering bugs Impeller team fixes quarterly.""",
    "vector-db-filtering-pre-post": """
## Pre-filter cardinality explosion

Metadata filter returning 90% of collection makes pre-filter HNSW slower than post-filter — analyze filter selectivity in staging with production query logs.

## Hybrid score with BM25 plus vector

Post-filter rerank combining lexical and vector scores helps SKUs with exact model numbers — pure vector misses alphanumeric codes.""",
    "voice-agents-stt-tts-pipelines": """
## Barge-in handling

When user interrupts TTS playback, cancel audio buffer and flush LLM stream — half-second delay feels like talking to voicemail. WebRTC VAD or STT partial confidence triggers interrupt.

## Telephony versus web audio codecs

PSTN narrowband limits TTS quality — choose phone-optimized voices. Web agents use Opus wideband; do not reuse telephony pipeline config.""",
}


def pick_meta(slug: str) -> dict:
    head = git_raw(slug)
    cur = (BLOG / f"{slug}.md").read_text(encoding="utf-8")
    head_meta = parse_fm(head) if head else {}
    cur_meta = parse_fm(cur)
    meta = head_meta if head_meta.get("title") else cur_meta
    if faq_is_generic(meta.get("faq", [])) and not faq_is_generic(cur_meta.get("faq", [])):
        meta["faq"] = cur_meta["faq"]
    if faq_is_generic(meta.get("faq", [])) and not faq_is_generic(head_meta.get("faq", [])):
        meta["faq"] = head_meta["faq"]
    if faq_is_generic(meta.get("faq", [])):
        # keep whatever we have; writer must fix manually — prefer head
        pass
    meta["slug"] = slug
    return meta


def build_body(slug: str) -> str:
    head = git_raw(slug)
    if head:
        body = strip_body(head.split("---", 2)[2])
    else:
        body = strip_body((BLOG / f"{slug}.md").read_text().split("---", 2)[2])

    for exp in gather_expansions(slug):
        if exp not in body:
            if "## Resources" in body:
                body = body.replace("## Resources", exp + "\n\n## Resources", 1)
            else:
                body += "\n\n" + exp

    if wc(body) < TARGET and slug in PADDING and PADDING[slug].strip() not in body:
        body += "\n\n" + PADDING[slug].strip()

    return body.strip()


def has_banned(text: str) -> bool:
    return any(b in text for b in BANNED)


def main() -> int:
    slugs = [s for s in load_slugs() if s not in SKIP]
    results = []
    for slug in slugs:
        meta = pick_meta(slug)
        body = build_body(slug)
        w = wc(body)
        banned = has_banned(body)
        ok = w >= TARGET and not banned and len(meta.get("faq", [])) >= 3
        if ok:
            (BLOG / f"{slug}.md").write_text(
                build_fm(meta, slug) + "\n\n" + body + "\n", encoding="utf-8"
            )
        results.append((slug, "ok" if ok else ("banned" if banned else "short"), w))

    # Also refresh dateModified on SKIP slugs
    for slug in load_slugs():
        if slug in SKIP:
            path = BLOG / f"{slug}.md"
            raw = path.read_text(encoding="utf-8")
            meta = parse_fm(raw)
            body = strip_body(raw.split("---", 2)[2])
            w = wc(body)
            banned = has_banned(body)
            ok = w >= TARGET and not banned
            if ok:
                path.write_text(build_fm(meta, slug) + "\n\n" + body + "\n", encoding="utf-8")
                results.append((slug, "ok-skip", w))
            else:
                results.append((slug, "fail-skip", w))

    ok_n = sum(1 for _, s, _ in results if s.startswith("ok"))
    print(f"PASS {ok_n}/{len(load_slugs())}")
    for slug, st, w in sorted(results, key=lambda x: x[0]):
        mark = "✓" if st.startswith("ok") else "✗"
        print(f"{mark} {w:4d}  {st:12s}  {slug}")
    bad = [r for r in results if not r[1].startswith("ok")]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
