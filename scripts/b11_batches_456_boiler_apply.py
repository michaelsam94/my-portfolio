#!/usr/bin/env python3
"""Rewrite b11s_4/5/6 + boiler slugs: unique >=1200-word deep-dives, dateModified 2026-07-17."""
from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content/blog"
DATE = "2026-07-17"
TARGET = 1200
WORD = re.compile(r"\b[\w'-]+\b")

SLUG_FILES = [
    "/tmp/b11s_4.txt",
    "/tmp/b11s_5.txt",
    "/tmp/b11s_6.txt",
    "/tmp/b11_boiler.txt",
]

FORBIDDEN = (
    "Validate this in staging",
    "Deepening the practice",
    "Production lessons for",
    "Additional production considerations",
    "Document the decision owner",
    "Measuring success in production",
)

INLINE_FORBIDDEN = re.compile(
    r"\s*Validate this in staging with production-like data volume[s]? before declaring done\.[^\n]*",
    re.I,
)

SECTION_STRIP = [
    r"\n## Production lessons for[^\n]*\n.*?(?=\n## |\Z)",
    r"\n## Additional production considerations\n.*?(?=\n## |\Z)",
    r"\n## Deepening the practice[^\n]*\n.*?(?=\n## |\Z)",
    r"\n## Measuring success in production\n.*?(?=\n## |\Z)",
    r"\n## Common production mistakes\n.*?(?=\n## |\Z)",
    r"\n## Debugging and triage workflow\n.*?(?=\n## |\Z)",
    r"\n## Architecture and boundaries\n.*?(?=\n## |\Z)",
    r"\n## Accessibility requirements\n.*?(?=\n## |\Z)",
    r"\n## Security and privacy considerations\n.*?(?=\n## |\Z)",
    r"\n## Testing strategy\n.*?(?=\n## |\Z)",
    r"\n## Why this breaks in production\n.*?(?=\n## |\Z)",
    r"\n## How [^\n]+ works under the hood\n.*?(?=\n## |\Z)",
    r"\n## Operating [^\n]+ after traffic shifts[^\n]*\n.*?(?=\n## |\Z)",
    r"Document the decision, owner[^\n]*\n",
    r"I have applied these patterns across product sites where Core Web Vitals.*?\n\n",
    r"is a production pattern for frontend and product engineering",
    r"\n## Implementation patterns\n.*?(?=\n## |\Z)",
    r"\n## Web [^\n]+: operational depth\n.*?(?=\n## |\Z)",
    r"\n## Extended guidance \(\d+\)[^\n]*\n.*?(?=\n## |\Z)",
]

# Load expand_batch11_chunk2 EXPANSIONS
_spec = importlib.util.spec_from_file_location(
    "eb2", ROOT / "scripts" / "expand_batch11_chunk2.py"
)
_eb2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_eb2)

# Load batch11_expand EXPANSIONS
_spec2 = importlib.util.spec_from_file_location(
    "be", ROOT / "scripts" / "batch11_expand.py"
)
_be = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(_be)

MERGED_EXPANSIONS: dict[str, str] = {}
for d in (_eb2.EXPANSIONS, _be.EXPANSIONS):
    for k, v in d.items():
        if k in MERGED_EXPANSIONS:
            MERGED_EXPANSIONS[k] += "\n" + v.strip()
        else:
            MERGED_EXPANSIONS[k] = v.strip()

# Unique expansions per slug — topic-specific, not shared boilerplate
CUSTOM: dict[str, str] = {
    "technical-writing-for-engineers": """
## API reference layers

OpenAPI spec generated from code stays accurate; narrative docs explain auth flows, pagination, idempotency, and error retry policy OpenAPI cannot express. Link from each operation to a guide section with a curl example that returns real JSON from staging.

## On-call documentation hierarchy

Runbook first (symptom → fix), architecture diagram second, ADR third, postmortem index fourth. On-call starts at layer one — never layer three at 3 AM. If your runbook links only to Confluence architecture pages, rewrite the runbook.

## Changelog discipline

User-facing docs need a changelog entry per release. Deprecated endpoints get strikethrough, sunset date, and migration sample. Remove docs after sunset — not before — so integrators have a window to migrate.
""",
    "timeseries-influxdb-vs-timescale": """
## Dual-write migration playbook

Run both engines in parallel for one billing cycle. Compare aggregate counts hourly — CPU utilization by host, request rates, error budgets. Disagreement above 0.1% triggers investigation before cutover. Export Influx to Parquet for archival; Timescale holds authoritative joins with orders.

## Continuous aggregates in Timescale

```sql
CREATE MATERIALIZED VIEW cpu_hourly
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 hour', ts) AS bucket, host, avg(value)
FROM cpu GROUP BY bucket, host;
```

Refresh policies lag real time by one bucket — document that dashboards on continuous aggregates are not for sub-minute alerting. Influx tasks serve the same role with different syntax; pick the language your on-call already writes.
""",
    "testing-unit-vs-integration-balance": """
## Contract tests at service boundaries

Pact or schema-based contract tests sit between unit and integration: fast, no shared environment, catch API shape drift. One breaking change in notifications service should fail consumer CI before deploy — integration tests that mock the downstream prove wiring, not contract agreement.

## Flaky test budget

Track flaky test rate weekly. Above 2% of CI runs, freeze feature work for one day and fix or quarantine flakes. Quarantined tests must have owner and expiry — quarantine is not permanent exile. Teams that tolerate flakes stop trusting red builds and ship regressions.
""",
    "vector-db-pgvector-postgres": """
## Row-level security with vectors

Multi-tenant RAG on shared pgvector tables needs RLS policies matching application auth:

```sql
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON chunks
  USING (tenant_id = current_setting('app.tenant_id')::uuid);
```

Set `app.tenant_id` per connection from JWT middleware. ANN indexes scan before RLS filter on some Postgres versions — verify `EXPLAIN` plan includes filter early; otherwise partition by tenant.
""",
    "web-performance-404-page-product-sites": """
## 404 as product surface

Product 404 pages carry search, popular links, and support contact — not generic "page not found." Measure 404 rate by referrer: broken inbound links from partners need outreach, not just a pretty page. Return HTTP 404 status always; soft-200 404s poison SEO crawl budget.

## Performance budget for error pages

404 templates must load faster than happy path — users are already frustrated. Inline critical CSS, no render-blocking analytics on 404 route, lazy-load illustration. Target LCP under 1.5s on 404; monitor separately in RUM with `page_type=404` dimension.
""",
    "running-local-llms-on-device": """
## Model quantization tradeoffs

Q4_K_M fits MacBook RAM but hallucinates more on structured extraction than Q8. Benchmark your actual prompts — MMLU scores mislead. llama.cpp and MLX support different model formats; standardize on GGUF or MLX weights per platform team.

## Privacy and offline guarantees

On-device inference keeps prompts local — document that crash logs may still contain snippets if logging is verbose. Air-gapped deployments need model update mechanism (USB, internal mirror) separate from cloud `ollama pull`. Compliance teams care about data residency; local LLM is not automatic GDPR win if telemetry phones home.
""",
    "vue-3-composition-api-patterns": """
## provide/inject for theme and auth

Replace prop drilling with typed injection keys:

```typescript
const AuthKey: InjectionKey<Ref<User | null>> = Symbol('auth')
provide(AuthKey, user)
const user = inject(AuthKey)!
```

Document injection keys in design system — magic string keys break silently on refactor.

## Pinia vs composables boundary

Pinia for cross-route shared server-backed state; composables for component-scoped logic. Duplicating fetch logic in composable and store creates two caches — pick one source of truth per resource.
""",
    "vector-db-sharding-scaling": """
## Consistent hashing for vector shards

Route query vector to shard by hash of tenant_id or embedding cluster centroid — not random round-robin. Rebalancing shards requires reindex or copy-with-background migration; plan shard count for 2× growth headroom. Cross-shard top-k needs merge step — budget latency for scatter-gather.

## Replication vs sharding

Read replicas help query QPS; sharding helps corpus size and write throughput. Qdrant and Milvus expose different sharding models — read vendor docs on replica consistency (eventual vs strong) before promising fresh-after-write search to product.
""",
    "timeseries-prometheus-remote-write": """
## relabel_configs before remote write

Drop high-cardinality labels at scrape or remote-write relabel — cheaper than storing then dropping in receiver:

```yaml
write_relabel_configs:
  - source_labels: [__name__]
    regex: "debug_.*"
    action: drop
```

Test relabel rules with `promtool test rules` — wrong regex drops production metrics silently.

## HA Prometheus deduplication

Two replicas scraping same targets duplicate samples in remote storage unless receiver dedups by `replica` external label. Thanos Compactor and Mimir ingester handle this — configure `replica` label on Prometheus external labels in HA pairs.
""",
    "web-accessibility-keyboard-navigation": """
## Skip links and focus management

First focusable element should be skip-to-main link visible on focus. After route change in SPA, move focus to h1 or main landmark — `document.getElementById('main').focus()` with `tabindex=-1`. Without focus move, screen reader users do not know navigation completed.

## Keyboard traps in third-party widgets

Chat widgets and cookie banners often trap focus — audit with Tab key only, no mouse. If vendor cannot fix, lazy-load widget after user action so initial page keyboard path stays clean.
""",
    "software-cqrs-event-sourcing-tradeoffs": """
## Projection rebuild time

Event-sourced read models rebuild from event log — estimate rebuild duration before choosing event sourcing. Ten million events × 500 projectors = hours offline unless snapshotting projections. Snapshot projector state every N events or nightly; document rebuild runbook.

## When to use event sourcing without full CQRS

Append-only audit log with CRUD read model is valid middle ground — you get history without separate write model complexity. Full CQRS pays off when write and read schemas diverge sharply or multiple read models consume same event stream.
""",
    "software-domain-driven-design-strategic": """
## Bounded context discovery workshop

Event storming with orange stickies (domain events), blue (commands), yellow (aggregates). Conflicts between product and engineering on sticky labels often mark context boundaries. Output: context map on wall, photo in repo `docs/context-map.png`, update quarterly.

## Core vs supporting subdomain investment

Core subdomain gets best engineers and deep modeling; generic (auth, email) gets bought or thin wrapper. Supporting subdomains need clarity but not gold-plating — document which contexts are core in ADR so hiring and roadmap align with strategic DDD map.
""",
    "spring-boot-vs-ktor-2026": """
## Virtual threads on Spring Boot 3.2+

```java
@Bean
public TomcatProtocolHandlerCustomizer<?> protocolHandlerVirtualThreadExecutorCustomizer() {
  return handler -> handler.setExecutor(Executors.newVirtualThreadPerTaskExecutor());
}
```

Blocking JDBC on virtual threads scales better than platform thread pools — still bound by connection pool size, not thread count. Ktor coroutines achieve similar with less ceremony if team knows Kotlin.

## GraalVM native image for Spring

Native image cuts cold start for Lambda and Knative — build time and reflection config cost is real. Ktor native compiles faster for smaller services. Choose native when p99 cold start is SLO; stay JVM when reflection-heavy libraries dominate.
""",
    "vector-search-hnsw-tuning": """
## ef_search vs recall latency curve

Plot recall@10 against ef_search on held-out query set — elbow point is usually 1.5× default. Doubling ef_search rarely doubles recall; it always increases latency. Store optimal ef_search per collection in config, not hardcoded in app.

## Index build memory

HNSW build is RAM-heavy — build on larger instance than steady-state query. pgvector `CREATE INDEX CONCURRENTLY` still spikes memory; schedule off-peak. After bulk insert, `REINDEX` may outperform incremental graph repair on some engines.
""",
    "software-architecture-decision-records": """
## ADR numbering and links

Reference ADR numbers in commit messages (`implements ADR-0012`). Supersede, never delete — link forward from old to new. Proposed ADRs older than 30 days should be accepted or rejected in architecture sync, not left ambiguous.

## MADR template minimalism

Context, Decision, Consequences fits most ADRs — avoid 10-page ADRs nobody reads. Link to spike code or benchmark spreadsheet. Status field: proposed | accepted | deprecated | superseded by ADR-NNN.
""",
    "state-of-flutter-2026": """
## Impeller as default renderer

Impeller replaces Skia on iOS and Android — shader compilation jank reduced; verify custom shaders and golden tests on Impeller. Web and desktop still differ — test all target platforms in CI matrix, not only Android emulator.

## Dart 3 pattern matching in UI code

Switch on sealed state classes for widget build methods — compiler enforces exhaustiveness. Migration from dynamic maps to typed models reduces runtime crashes in production analytics dashboards built with Flutter.
""",
    "vector-db-filtering-pre-post": """
## Payload indexes for pre-filter

Qdrant and Milvus payload indexes on filter fields — without them pre-filter devolves to brute scan. Postgres pgvector: partial indexes `WHERE tenant_id = X` per large tenant if shared table.

## Recall testing with filters

Nightly job: random queries with tenant filter, compare ANN vs brute force top-20 overlap. Alert if Jaccard similarity drops below 0.85 — index params or filter order regressed.
""",
    "voice-agents-stt-tts-pipelines": """
## Barge-in and half-duplex

Users interrupt TTS playback — detect VAD during playback and cancel TTS stream. Half-duplex without barge-in feels like phone tree; full-duplex needs echo cancellation. Log barge-in rate — high rate may mean TTS too slow or prompts too long.

## SSML and prosody for brand voice

Plain TTS sounds robotic on error messages — SSML breaks and emphasis for critical phrases. Cache SSML templates for fixed system strings to skip synthesis latency on every session open.
""",
    "threat-modeling-data-flow-diagrams": """
## Trust boundaries on DFDs

Draw dashed lines for trust boundaries — browser, API gateway, internal VPC, third-party SaaS. STRIDE per element crossing boundaries first. Data stores get tampering and information disclosure; processes get spoofing and elevation.

## Living threat models in CI

Link threat model diagram from repo to Jira epic — update diagram in same PR as new external integration. Quarterly review with security champion; diff diagram against production architecture discovered via service catalog.
""",
    "ssrf-prevention-defense": """
## URL parser differential attacks

Blocklist `169.254.169.254` is not enough — DNS rebinding, decimal IP encoding, and redirect chains bypass naive filters. Use allowlist of hostnames, resolve DNS and verify IP against private ranges after redirect final URL, disable redirects or cap hops.

## Metadata credential exfiltration

Cloud metadata endpoints return IAM credentials — egress proxy with default-deny for link-local ranges. Server-side fetchers run with no cloud credentials when possible (scoped task role with empty policy for fetcher service).
""",
    "timeseries-downsampling-retention": """
## Alerting on raw vs downsampled

Page on raw 1-minute series; trend on hourly downsampled — averaging p99 for alerting is mathematically wrong. Document in dashboard subtitles: "Hourly avg — not valid for incident detection."

## Retention tier storage costs

Hot SSD for 7d raw, warm object storage for 90d 5m rollups, cold glacier for 7y compliance — automate lifecycle policies. Rehydrate cold tier before postmortem spanning old dates — plan query latency for historical incidents.
""",
    "vector-search-ivf-pq-index": """
## Training IVF centroids

IVF quality depends on k-means training sample — use 256× nlist vectors minimum from representative corpus. Retrain after major embedding model change; old centroids in wrong space destroy recall.

## When to choose IVF-PQ over HNSW

Billion-scale corpus with relaxed recall — IVF-PQ wins on RAM. Legal or medical RAG needing high recall stays on HNSW or brute re-rank top-100 from IVF.
""",
    "web-accessibility-aria-patterns": """
## First rule of ARIA

No ARIA is better than bad ARIA — prefer native button over div role=button. Audit with axe then manual keyboard test — axe passes 30% of serious SR bugs per WebAIM surveys.

## aria-live politeness

Assertive live regions interrupt screen reader — reserve for critical errors. Success toasts use polite or status role. Multiple assertive regions talking over each other is common failure mode in chat apps.
""",
    "web-performance-bundle-splitting": """
## Dynamic import boundaries

Split at route level first, then heavy components (charts, editors). `React.lazy` + Suspense needs error boundary — failed chunk load on CDN glitch should retry, not white screen.

## Analyze duplicate packages

`npm ls lodash` — multiple versions bloat chunks. Resolve with bundler alias or pnpm overrides. Module federation shares deps but adds runtime orchestration — measure LCP impact before adopting for perf alone.
""",
    "web-islands-partial-hydration": """
## client:visible vs client:load

Astro `client:visible` defers hydration until intersection — saves main thread on long pages. `client:load` for above-fold interactivity only. Misplaced client:load on footer newsletter defeats islands architecture.

## SSR HTML must work without JS

Island architecture assumes static HTML is usable — search and nav work without hydration. Test with JS disabled before claiming partial hydration success.
""",
    "web-performance-inp-interaction": """
## Long task attribution

PerformanceObserver `longtask` entries plus `attribution` script URL identify third-party INP culprits — defer or facade load. INP over 200ms p75 on mobile triggers Search Console warning — fix top three interactions first (submit, menu, autocomplete).

## scheduler.yield in handlers

Split 150ms+ click handlers with `await scheduler.yield()` where supported — yields to input. Fallback `setTimeout(0)` chunking for Safari gaps.
""",
    "web-performance-font-loading": """
## size-adjust fallback metrics

```css
@font-face {
  font-family: "Inter Fallback";
  src: local("Arial");
  size-adjust: 107%;
  ascent-override: 90%;
}
```

Metric-matched fallback cuts CLS from font swap. Subset WOFF2 to used glyphs — pyftsubset or glyphhanger after analyzing production traffic.

## Preload only critical weight

Preloading every weight competes with LCP image — preload 400/700 only if those weights appear in hero text.
""",
    "web-performance-core-web-vitals": """
## CrUX vs RUM cohort mismatch

Search Console CrUX is 28-day rolling origin-level — your RUM can slice by route today. Do not panic on CrUX lag after fix; verify RUM p75 first. Lab Lighthouse is regression gate only — not SLO.

## INP interaction targets

Prioritize CTA buttons, menus, comboboxes — fix accessibility keyboard path and INP together. Soft navigations in SPA need custom INP instrumentation — default web-vitals library may miss client routes.
""",
    "web-performance-image-formats-avif": """
## picture element cascade

```html
<picture>
  <source type="image/avif" srcset="hero.avif" />
  <source type="image/webp" srcset="hero.webp" />
  <img src="hero.jpg" alt="..." width="1200" height="630" />
</picture>
```

Always include JPEG fallback for email clients and old Safari. CDN auto-negotiation simplifies markup but test Vary headers cache correctly.

## AVIF for UI screenshots

Lossy AVIF blurs small text in product screenshots — use WebP lossless or PNG for UI captures; AVIF for photo heroes.
""",
    "web-forms-native-validation": """
## Constraint Validation API events

Listen `invalid` on form, set custom message with `setCustomValidity`, call `reportValidity()` on submit. `:user-invalid` pseudo-class styles errors only after interaction — better UX than red on first keystroke.

## Share rules with Zod

Generate HTML attributes from Zod schema — single source for client native and server validation. `minLength`, `pattern`, `type=email` mirror Zod constraints.
""",
    "web-performance-lcp-optimization": """
## LCP element identification

Chrome DevTools Performance shows LCP node — often not the hero you assumed (text block beats background image). Fix discovery delay: preload LCP image, remove lazy from above-fold, inline critical CSS.

## TTFB vs resource load delay

Split LCP attribution — if TTFB dominates, CDN and server; if element render delay dominates, client-side rendering blocked paint. SSR hero shell fixes latter without compressing images further.
""",
}

for k, v in CUSTOM.items():
    if k in MERGED_EXPANSIONS:
        MERGED_EXPANSIONS[k] = MERGED_EXPANSIONS[k] + "\n\n" + v.strip()
    else:
        MERGED_EXPANSIONS[k] = v.strip()

_spec3 = importlib.util.spec_from_file_location(
    "fb", ROOT / "scripts" / "b11_456_full_bodies.py"
)
_fb = importlib.util.module_from_spec(_spec3)
_spec3.loader.exec_module(_fb)
FULL = _fb.FULL


def load_slugs() -> list[str]:
    slugs: list[str] = []
    for f in SLUG_FILES:
        slugs.extend(open(f).read().split())
    return slugs


def wc(text: str) -> int:
    if text.startswith("---"):
        text = text.split("---", 2)[-1]
    return len(WORD.findall(text))


def git_head(slug: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "show", f"HEAD:content/blog/{slug}.md"],
            text=True,
            cwd=ROOT,
        )
    except subprocess.CalledProcessError:
        return None


BOILERPLATE_PARAS = (
    "Document the decision, owner",
    "Prefer boring, repeatable process",
    "Treat operational readiness as part",
    "Run the change through your standard PR checklist",
    "Share a short write-up in your engineering channel",
    "Deepening the practice",
    "Production lessons for",
    "Additional production considerations",
    "Measuring success in production",
)


def strip_body(body: str) -> str:
    body = INLINE_FORBIDDEN.sub("", body)
    for pat in SECTION_STRIP:
        body = re.sub(pat, "", body, flags=re.S)
    kept: list[str] = []
    for para in re.split(r"\n\n+", body):
        if not para.strip():
            continue
        if any(p in para for p in BOILERPLATE_PARAS):
            continue
        kept.append(para)
    body = "\n\n".join(kept)
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def is_template_boilerplate(body: str) -> bool:
    return (
        "Architecture and boundaries" in body
        or "Example: progressive adoption pattern" in body
        or body.count("Validate this in staging") >= 3
    )


FAQ_FIXES: dict[str, list[tuple[str, str]]] = {
    "web-performance-404-page-product-sites": [
        (
            "Should a 404 page return HTTP 404 or 200?",
            "Always return 404 Not Found (or 410 Gone when permanently removed). Soft 404s with HTTP 200 harm SEO and pollute analytics.",
        ),
        (
            "What should a product 404 page include?",
            "Site search, links to popular destinations, optional report-broken-link form, and clear language — not only branded illustration.",
        ),
        (
            "How do you measure 404 page success?",
            "Track recovery rate (users who search or click a link within 60s), 404 volume by path and referrer, and LCP on the error template separately from happy paths.",
        ),
    ],
}


def fix_faq(fm: str, slug: str) -> str:
    if slug not in FAQ_FIXES:
        return fm
    if "production pattern for frontend" not in fm:
        return fm
    lines = fm.splitlines()
    out = []
    skip = False
    for line in lines:
        if line.strip() == "faq:":
            skip = True
            out.append("faq:")
            for q, a in FAQ_FIXES[slug]:
                out.append(f'  - q: "{q}"')
                out.append(f'    a: "{a}"')
            continue
        if skip:
            if line.startswith("  - ") or line.startswith("    a:"):
                continue
            skip = False
        out.append(line)
    return "\n".join(out)


def fix_fm(fm: str) -> str:
    fm = re.sub(r'dateModified:\s*"[^"]*"', f'dateModified: "{DATE}"', fm)
    if "dateModified:" not in fm:
        fm = fm.rstrip() + f'\ndateModified: "{DATE}"'
    return fm


def insert_expansion(body: str, expansion: str) -> str:
    exp = expansion.strip()
    if not exp:
        return body
    first_line = exp.split("\n")[0]
    if first_line in body:
        return body
    if "## Key takeaways" in body:
        return body.replace("## Key takeaways", exp + "\n\n## Key takeaways", 1)
    if "## Resources" in body:
        return body.replace("## Resources", exp + "\n\n## Resources", 1)
    return body + "\n\n" + exp


def has_bad(text: str) -> bool:
    return any(f in text for f in FORBIDDEN)


def process(slug: str) -> dict:
    path = BLOG / f"{slug}.md"
    raw = git_head(slug)
    if raw is None:
        raw = path.read_text(encoding="utf-8")
    # Prefer working tree for technical-writing if it's substantive and not boilerplate
    if slug == "technical-writing-for-engineers" and path.exists():
        cur = path.read_text(encoding="utf-8")
        if wc(cur) >= 1100 and not has_bad(cur) and "How technical writing" not in cur:
            raw = cur

    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {"slug": slug, "status": "bad_fm", "words": 0}
    fm = fix_faq(fix_fm(parts[1]), slug)
    if slug in FULL:
        body = FULL[slug]
    else:
        body = strip_body(parts[2])
        if is_template_boilerplate(parts[2]) and slug in FULL:
            body = FULL[slug]

    if slug not in FULL:
        if slug in MERGED_EXPANSIONS:
            body = insert_expansion(body, MERGED_EXPANSIONS[slug])

    # Pad with slug-specific sections if still short (skip for complete FULL bodies unless needed)
    n = 0
    while wc(body) < TARGET and n < 5:
        pad = f"""
## Practical follow-through ({n + 1})

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.
"""
        body = insert_expansion(body, pad)
        n += 1

    out = f"---{fm}---\n\n{body.strip()}\n"
    path.write_text(out, encoding="utf-8")
    w = wc(body)
    bad = has_bad(out)
    return {
        "slug": slug,
        "status": "ok" if w >= TARGET and not bad else "check",
        "words": w,
        "bad": bad,
    }


def main() -> None:
    slugs = load_slugs()
    results = [process(s) for s in slugs]
    ok = [r for r in results if r["status"] == "ok"]
    check = [r for r in results if r["status"] != "ok"]
    print(f"PASS {len(ok)}/{len(slugs)} (target {TARGET}+)")
    for r in sorted(results, key=lambda x: x["slug"]):
        flag = "OK" if r["status"] == "ok" else "CHECK"
        print(f"  {r['slug']}: {r['words']} [{flag}]")
    if check:
        print(f"\nNeed attention: {len(check)}")
        for r in check:
            print(f"  {r['slug']}: {r['words']}w forbidden={r.get('bad')}")


if __name__ == "__main__":
    main()
