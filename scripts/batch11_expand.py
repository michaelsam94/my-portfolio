#!/usr/bin/env python3
"""Append topic-specific expansions to batch11 posts under 1200 words."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content/blog"
BATCH = Path("/tmp/batch11_chunk_1.txt")
DATE = "2026-07-17"
WORD = re.compile(r"\b[\w'-]+\b")

STRIP = [
    r"## Common production mistakes\n.*?(?=\n## |\Z)",
    r"## Debugging and triage workflow\n.*?(?=\n## |\Z)",
    r"## Operational checklist for teams\n.*?(?=\n## |\Z)",
    r"## Architecture and boundaries\n.*?(?=\n## |\Z)",
    r"## Accessibility requirements\n.*?(?=\n## |\Z)",
    r"## Security and privacy considerations\n.*?(?=\n## |\Z)",
    r"## Testing strategy\n.*?(?=\n## |\Z)",
    r"Treat production rollout as a measured change:.*?\n\n",
    r"The gap between reading about .*? — not a conference demo\.\n\n",
    r"I have applied these patterns across product sites where Core Web Vitals.*?\n\n",
    r"Validate in staging with production-like data volumes\..*?\n\n",
    r"Document the timeline during triage\..*?\n\n",
    r"Testing strategy for .*? gives false confidence.*?\n\n",
    r"System design for .*? breaks at scale when hot keys.*?\n\n",
]

GENERIC = "is a production pattern for frontend and product engineering"

EXPANSIONS: dict[str, str] = {
    "system-design-file-storage-dropbox": """## Bandwidth and sync cost modeling

Sync cost scales with changed chunks, not file size. A 1 GB file with one byte changed uploads one new chunk (~4 MB) plus metadata. Model monthly egress per active user: average daily changed bytes × device count × user base. Teams underestimate mobile sync on cellular — offer Wi-Fi-only sync for large files and show upload progress with pause/resume via multipart upload sessions tied to chunk manifests.""",

    "system-design-metrics-monitoring": """## Recording rules and query performance

Ad-hoc PromQL across raw metrics at dashboard load time does not scale. Pre-compute expensive aggregations with recording rules:

```yaml
groups:
  - name: checkout_recording
    rules:
      - record: checkout:http_requests:rate5m
        expr: sum(rate(http_requests_total{service="checkout"}[5m])) by (endpoint, status)
```

Dashboards query recorded metrics; alerts use the same recordings for consistency. Without recording rules, a Grafana dashboard with twenty panels each running `rate()` over millions of series will timeout during incidents — exactly when you need dashboards most.""",

    "system-design-news-feed": """## Feed freshness vs infrastructure cost

Push fan-out trades write amplification for read speed. Measure fan-out queue lag as a first-class SLO: if lag exceeds 30 seconds, users see stale feeds even though posts succeeded. Pull-only celebrity feeds add read latency — cache celebrity recent posts in a shared Redis layer with 10-second TTL so pull merges stay fast. A/B test ranking changes on a shadow feed pipeline before promoting weights to production; bad ranking deploys are reversible without re-fan-out.""",

    "system-design-notification-system": """## Delivery guarantees and provider quirks

APNs and FCM have different failure semantics. APNs returns permanent failures for uninstalled apps — remove dead tokens from your device registry. FCM supports topic subscriptions for broadcast but adds delivery latency. Email providers throttle by domain reputation — warm up sending domains gradually after migration. SMS is expensive; reserve for OTP and critical alerts. Log delivery status per channel with provider message IDs for support lookup when users claim they never received an alert.""",

    "system-design-payment-system": """## Webhook reliability and idempotent handlers

Payment processors confirm state via webhooks — `charge.succeeded`, `charge.refunded`. Webhooks arrive at-least-once, sometimes out of order. Handlers must be idempotent on event ID:

```python
async def handle_webhook(event: WebhookEvent):
    if await processed_events.exists(event.id):
        return 200
    await apply_event(event)
    await processed_events.mark(event.id)
    return 200
```

Verify webhook signatures before processing. Respond 200 quickly and process async if handler work is slow — providers retry on timeout and duplicate delivery is guaranteed.""",

    "system-design-ride-sharing": """## Geospatial indexing at match time

Driver-rider matching queries drivers within a radius of pickup location. Geo-hash or H3 cells partition the space — query adjacent cells for candidates within radius instead of full table scan. Update driver location every 3–5 seconds during active sessions; stale locations cause missed matches. Surge pricing multipliers live in a separate fast-read store keyed by H3 cell — match latency and pricing lookup must not share the same hot database connection pool.""",

    "system-design-search-autocomplete": """## Multilingual and locale-specific indexes

Autocomplete indexes are per-locale — German compound words, CJK n-gram tokenization, and RTL display order each need separate index pipelines. Never mix locales in one completion field; "gift" means present in English and poison in German. Route suggest requests to locale-specific index shards via `Accept-Language` or explicit user preference. Pre-warm cache keys per locale during deploy so cold-start after index rebuild does not spike latency globally.""",

    "system-design-ticketing-booking": """## Seat locking and double-booking prevention

Concert and airline booking share the same core problem: hold inventory during checkout with TTL. Optimistic locking on seat rows (`UPDATE seats SET status='held' WHERE id=? AND status='available'`) fails closed when zero rows updated. Display held seats as unavailable to other users immediately via WebSocket or short-poll on seat map. When hold expires, broadcast seat release so waiting users can grab released inventory — this creates burst traffic; rate-limit seat map refreshes per client.""",

    "system-design-url-shortener": """## Abuse prevention and link safety

Short links hide destination URLs — attackers use them for phishing. Scan destinations at creation time against malware blocklists; re-scan periodically for compromised destinations. Rate-limit creation per IP and API key. Offer preview interstitial for suspicious domains. Log click analytics without storing full user-agent strings at high cardinality — aggregate by country and referrer domain instead.""",

    "system-design-video-streaming": """## Adaptive bitrate ladder design

ABR players switch quality based on buffer health and throughput estimates. Encode each title in a ladder (240p through 4K) with segment duration 2–6 seconds. CDN caches segments by URL; origin shield reduces origin load during viral content. Live streaming adds DVR window complexity — segment availability TTL must exceed rewind duration. Monitor rebuffer ratio per quality rung; if 1080p rebuffer spikes on mobile networks, adjust ladder to promote 720p sooner.""",

    "technical-writing-for-engineers": """## Review workflow that keeps docs honest

Treat doc changes like code: PR review, CI link checking, ownership in CODEOWNERS. Require doc updates in the same PR as breaking API changes — block merge if `CHANGELOG` or API reference is stale. Schedule quarterly "doc debt" sprints to fix top ten support-ticket topics that lack runbooks. Measure doc success by time-to-resolution in support tickets referencing doc links, not by page view count alone.""",

    "terraform-drift-detection": """## Drift response playbooks

When drift detection finds manual console changes, classify: intentional hotfix (import into Terraform state), mistaken change (revert via apply), or emergency override (document exception with expiry date). Run drift detection on schedule, not just pre-apply — drift between applies accumulates silently. Integrate with Slack alerting showing resource diff summary so on-call can triage without opening full plan output.""",

    "terraform-modules-composition": """## Module interface design

Good modules expose minimal variables with sensible defaults and outputs only what callers need. Avoid passing raw provider configurations into child modules — use provider aliases and explicit `providers` blocks. Version modules with semantic release tags; pin consumers to `~>` minor versions. Document upgrade notes in CHANGELOG when output shapes change — silent output renames break downstream CI that references module outputs.""",

    "terraform-state-management-backends": """## State locking and team workflows

Remote state without locking corrupts on concurrent apply. S3 backend uses DynamoDB for locks; GCS uses native locking; Terraform Cloud provides managed locking. Never disable locking to "speed up" CI — two applies racing produce state corruption that takes hours to untangle. Use separate state files per environment and per blast-radius boundary — one monolithic state for entire org means every apply risks everything.""",

    "terraform-testing-policy-as-code": """## Policy testing before enforcement

Write Rego or Sentinel policies with positive and negative test cases before enabling deny mode. Start policies in advisory mode — log violations without blocking — for two weeks to measure blast radius. Common false positives: naming convention policies blocking legitimate legacy resources. Conftest unit tests on Terraform plan JSON catch policy regressions in CI without touching live cloud accounts.""",

    "terraform-workspaces-environments": """## Workspaces vs separate state

Terraform workspaces share backend configuration — convenient for dev/staging in one account, dangerous for prod isolation. Production should use separate state files, separate AWS accounts, and separate CI pipelines — not a workspace toggle. Workspace-based env switching tempts `terraform workspace select prod` from a laptop; separate backends make accidental prod apply structurally harder.""",

    "testing-compose-uis-v2": """## Semantics and test tags

Compose UI tests should assert semantics (content description, role) over pixel position. Use `testTag` sparingly — prefer user-visible properties. Synchronization with idling resources prevents flaky interactions; register custom idling for animations and async loads. Robolectric covers logic; device tests cover touch targets and real rendering. Screenshot tests complement semantics tests for visual regressions layout alone won't catch.""",

    "testing-mutation-testing": """## Interpreting mutation scores

High mutation score means tests catch injected bugs — low score means tests assert too weakly. Target 70–80% on core domain modules; 100% is expensive and diminishing returns. Kill surviving mutants by strengthening assertions, not by disabling equivalent mutants. Run mutation testing nightly, not per PR — it is CPU-intensive. Focus on payment, auth, and pricing modules first where logic bugs cost money.""",

    "testing-playwright-e2e": """## Flake resistance patterns

Playwright's auto-wait reduces flakes but does not eliminate them. Use `locator` API over raw selectors; chain `getByRole` for accessibility-aligned queries. Isolate tests with fresh browser context per test — shared state causes order-dependent failures. Run E2E against staging with production-like data seed, not empty databases. Parallelize by spec file, not by test within file, when tests share database state.""",

    "testing-property-based-testing": """## Stateful testing for complex domains

When properties involve sequences of operations — push/pop, credit/debit, open/close — use stateful property testing (Hypothesis RuleBasedStateMachine, QuickCheck dynamic). Define rules for valid operations and invariants that must hold after every step. Model-based testing compares a simple reference implementation against optimized production code — if they diverge on random operation sequences, the optimized version has a bug.""",

    "testing-snapshot-testing-tradeoffs": """## When snapshots help vs hurt

Snapshots excel at catching unintended UI tree changes in stable components — design system primitives, email templates, serialized API responses. They fail when used for entire pages that change weekly — reviewers click "update snapshot" without reading. Scope snapshots to small, stable outputs. Pair with deliberate assertions on critical content, not snapshot-only tests. Store snapshots in git LFS if binary screenshots; prefer serialized component trees for reviewability.""",

    "testing-test-data-builders": """## Builder patterns vs fixtures

Builders shine when tests need variations of complex objects — `OrderBuilder().withItems(3).withExpiredCoupon().build()`. Fixtures hide setup in conftest.py and become shared mutable state if not careful — each test should get fresh instances. Default sensible values in builders so one-line builds work for happy path; chain methods override specifics. Name builders after domain concepts, not database table names.""",

    "testing-test-doubles-mocks-stubs": """## Choosing the right double

Martin Fowler's taxonomy still applies: dummies fill parameters, stubs return canned answers, spies record calls, mocks verify interaction. Over-mocking couples tests to implementation — prefer testing observable behavior through public interfaces. Fake implementations (in-memory repository) beat mocks for integration-style unit tests. Reserve mocks for external services you cannot instantiate — payment gateway, third-party API.""",

    "testing-unit-vs-integration-balance": """## The integration test honeycomb

Unit tests prove logic; integration tests prove wiring. The costly mistake is mocking everything in "integration" tests until they prove nothing. Test containers (Testcontainers, Docker Compose in CI) give real Postgres and Redis without shared staging environments. One integration test per critical path — checkout, signup, password reset — catches config errors unit tests miss. Keep integration suite under ten minutes or teams skip it.""",

    "testing-vitest-react-testing-library": """## Vitest and RTL ergonomics

Vitest's Vite-native speed encourages more component tests — use that velocity. Testing Library queries in priority order: getByRole, getByLabelText, getByText, getByTestId last. `userEvent` over `fireEvent` for realistic interaction simulation. Mock network at MSW layer, not by mocking fetch in every test file. Co-locate tests with components; shared render helpers wrap providers (QueryClient, Router, Theme) once.""",

    "threat-modeling-stride": """## Prioritizing mitigations with DREAD

After STRIDE identifies threats, score with DREAD (Damage, Reproducibility, Exploitability, Affected users, Discoverability) or simple High/Medium/Low. Fix High threats before shipping; Medium threats get tickets with owners; Low threats go to backlog with accepted-risk documentation. Re-score after mitigations land — threat models are living documents, not one-time audit artifacts.""",

    "time-series-databases-iot": """## IoT ingestion burst patterns

IoT devices burst on reconnect after outage — millions of devices reporting simultaneously. Ingestion pipeline needs queue buffering (Kafka, Kinesis) before time-series write. Tag cardinality explodes if every device ID becomes a metric label; store device metadata separately, aggregate metrics by device type and region. Retention policies differ: raw 7 days for debugging, downsampled 1 year for capacity planning.""",

    "timeseries-downsampling-retention": """## Choosing aggregation functions per metric type

Counters downsample with `sum` or `rate` — gauges with `avg`, `min`, `max` depending on question. Never average percentiles — average of p99s is meaningless. Use max of p99 for capacity planning, or store raw histograms and recompute. Document downsampling rules in runbooks so on-call understands why dashboard shows different values at 1-hour vs 1-minute resolution.""",

    "timeseries-influxdb-vs-timescale": """## Operational tradeoffs in practice

InfluxDB excels at high-cardinality metric ingestion with built-in downsampling (tasks, retention policies). TimescaleDB gives SQL familiarity and JOINs with relational data — ideal when metrics correlate with business tables. Hybrid architectures write metrics to Influx and export aggregates to Postgres for billing reports. Pick based on query patterns your team already knows; operational familiarity beats benchmark wins.""",

    "timeseries-prometheus-remote-write": """## Remote write reliability

Remote write buffers samples during backend outage — monitor buffer size and drop rate. Configure `queue_config` capacity and batch size for your network. HA pairs of Prometheus sending duplicate remote write creates duplicate samples — use deduplication in receiver (Cortex, Mimir) or accept 2x write volume. Test failover by blocking remote write endpoint in staging and verifying local Prometheus retention covers gap duration.""",

    "tokenization-bpe-explained": """## Vocabulary size and OOV tradeoffs

BPE vocabulary size controls compression vs granularity. Small vocab (8K) means longer sequences but fewer parameters in embedding layer. Large vocab (100K+) captures rare words as single tokens but increases embedding memory. Production LLMs use 32K–128K with byte-level fallback for true OOV. Train tokenizer on representative corpus — code tokenizer on natural text produces terrible splits for programming tokens.""",

    "typescript-path-mapping-monorepo": """## Path aliases across package boundaries

`paths` in tsconfig resolve at compile time only — bundlers and test runners need matching config. In monorepos, prefer package names (`@org/shared`) via workspace protocol over deep relative imports. Ensure `references` in tsconfig align with build order for project references. Jest/Vitest need `moduleNameMapper` mirroring paths; missing mapping causes tests to pass while production build fails or vice versa.""",

    "typescript-result-type-error-handling": """## Result types at API boundaries

`Result<T, E>` makes failure explicit in the type system — callers must handle `Err`. At HTTP boundaries, map `Err` to status codes consistently. Do not propagate Result through every internal function — use exceptions internally if team convention prefers, but convert to Result at module boundaries exposed to other teams. Rust's `?` operator has no TypeScript equivalent; helper functions reduce nested `if (result.ok)` chains.""",

    "typescript-satisfies-operator": """## satisfies vs as const vs type annotation

`satisfies` validates shape without widening — `const config = { ... } satisfies Config` keeps literal types for keys while checking Config compliance. Type annotation `const config: Config = { ... }` widens literals to Config's field types. `as const` freezes values but does not validate against an interface. Use satisfies when you want both inference and validation — config objects, theme tokens, route maps.""",

    "typescript-strict-mode-migration": """## Incremental strictness rollout

Enable `strict` flags one at a time across codebase: `strictNullChecks` first (highest bug catch), then `noImplicitAny`, then `strictFunctionTypes`. Use `@ts-expect-error` with ticket references for legacy files during migration — not `@ts-ignore` without expiry. CI rule: no new `@ts-expect-error` without approval. Track error count weekly; celebrate downward trend even if not zero yet.""",

    "typescript-strict-null-checks-migration": """## Narrowing patterns for legacy code

After enabling strictNullChecks, legacy code explodes with `possibly undefined`. Fix with narrowing guards, optional chaining, and nullish coalescing — not non-null assertion (`!`) as default. Database rows that are "always present" in business logic still type as optional until query proves existence. Create typed helper `assertDefined(x, 'context')` for invariant enforcement at boundaries instead of scattering `!`.""",

    "typescript-template-literal-types": """## Route and event type safety

Template literal types excel at typed routes and event names: `type Route = \`/users/${string}\`` combined with mapped types for params. Extract route params with conditional types. Over-engineering stringly-typed APIs into template literal unions has diminishing returns — use for API surfaces with finite known patterns, not every string field in the database.""",

    "typescript-type-guards-narrowing": """## Custom type guards and predicates

User-defined type guards (`function isUser(x: unknown): x is User`) centralize validation logic reusable across modules. `in` operator narrowing works for discriminated unions. Avoid casting after guard — if guard is wrong, fix guard. Combine with Zod `.safeParse` at runtime boundaries and type predicate wrapper for TypeScript narrowing in one call.""",

    "typescript-utility-types-app-patterns": """## Utility types in application code

`Partial<T>` for update DTOs, `Pick<T, Keys>` for API response subsets, `Omit<T, Keys>` for create forms without id. `Record<string, T>` for dictionaries with known value type. `Readonly<T>` for config objects passed deep into call stacks. Do not recreate utilities — know stdlib types before writing custom `Optional<T>` aliases that duplicate Partial.""",

    "typescript-zod-runtime-validation": """## Zod at system boundaries

Define schema once, infer type with `z.infer<typeof Schema>`. Validate at boundaries: HTTP handlers, form submission, env vars at startup (`createEnv` pattern). Use `.transform` for coercion (string query param to number) and `.refine` for cross-field rules. Compose schemas for nested API responses. On validation failure, return structured errors to clients — Zod's `.flatten()` or `.format()` for field-level messages in forms.""",
}

# Full rewrites for posts with generic template FAQ
FULL_FAQ: dict[str, tuple[str, str, list[tuple[str, str]]]] = {}


def wc(t: str) -> int:
    return len(WORD.findall(t))


def parse(raw: str) -> tuple[str, str]:
    p = raw.split("---", 2)
    return p[1], p[2].lstrip("\n")


def strip(body: str) -> str:
    for pat in STRIP:
        body = re.sub(pat, "", body, flags=re.S)
    while "## Operational checklist" in body:
        body = re.sub(r"## Operational checklist for teams\n.*?(?=\n## |\Z)", "", body, count=1, flags=re.S)
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def update_fm(fm: str) -> str:
    return re.sub(r'^dateModified:.*$', f'dateModified: "{DATE}"', fm, flags=re.M)


def insert_expansion(body: str, section: str) -> str:
    if "## Resources" in body:
        return body.replace("## Resources", section + "\n\n## Resources", 1)
    return body + "\n\n" + section


def write(slug: str, fm: str, body: str) -> int:
    (BLOG / f"{slug}.md").write_text(f"---\n{fm.strip()}\n---\n\n{body.strip()}\n", encoding="utf-8")
    return wc(body)


def main():
    slugs = [s.strip() for s in BATCH.read_text().splitlines() if s.strip()]
    done = skipped = 0
    pending = []
    for slug in slugs:
        path = BLOG / f"{slug}.md"
        raw = path.read_text(encoding="utf-8")
        fm, body = parse(raw)
        if GENERIC in fm and slug not in EXPANSIONS:
            pending.append(slug)
            continue
        cleaned = strip(body)
        if slug in EXPANSIONS:
            cleaned = insert_expansion(cleaned, EXPANSIONS[slug])
        fm = update_fm(fm)
        w = wc(cleaned)
        if w >= 1200:
            write(slug, fm, cleaned)
            if slug in EXPANSIONS:
                done += 1
            else:
                skipped += 1
        else:
            pending.append(f"{slug}({w})")
    print(f"Expanded: {done}, Skipped: {skipped}, Pending: {len(pending)}")
    if pending:
        print("Pending:", pending[:20])


if __name__ == "__main__":
    main()
