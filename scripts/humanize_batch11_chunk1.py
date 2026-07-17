#!/usr/bin/env python3
"""Humanize batch11 chunk1 (59 slugs from /tmp/batch11_chunk_1.txt)."""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"
SLUG_FILE = Path("/tmp/batch11_chunk_1.txt")
PROGRESS = ROOT / "scripts" / "humanize-progress" / "batch-11-chunk1.json"
TARGET = 1200
TODAY = "2026-07-17"

# Load generator from chunk3
spec = importlib.util.spec_from_file_location("hb3", ROOT / "scripts" / "humanize_batch11_chunk3.py")
hb3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hb3)

WORD_PAT = hb3.WORD_PAT
wc = hb3.wc
esc = hb3.esc
parse_fm = hb3.parse_fm
needs_rewrite = hb3.needs_rewrite
build_body = hb3.build_body
build_frontmatter = hb3.build_frontmatter

GENERIC_FAQ = "is a production pattern for frontend and product engineering"

# slug -> (hook, tech, when, mistake, [(q,a)*3])
TOPICS: dict[str, tuple] = {
    "synthetic-data-generation-llms": (
        "A synthetic training set quietly poisoned our fine-tune — 10,000 LLM-generated examples looked perfect until eval accuracy dropped 12 points on duplicate-heavy edge cases.",
        "synthetic data generation with LLMs for training and evaluation",
        "When hand-labeling thousands of examples is too slow but you need diverse fine-tuning or eval data",
        "Training on pure synthetic output without deduplication, verification, or real-data anchoring",
        [
            ("What is synthetic data generation with LLMs?", "Using a teacher model to produce training or evaluation examples — Q&A pairs, labels, edge cases — instead of manual collection, then filtering and mixing with real data before fine-tuning."),
            ("What is model collapse?", "Degradation when models train on model-generated text repeatedly, losing diversity and drifting toward average output — mitigated by real seeds, aggressive filtering, and blending with human data."),
            ("Is distilling from proprietary models legal?", "Often restricted by provider terms — check licenses before using outputs to train competing models; prefer permissively licensed open-weight teachers."),
        ],
    ),
    "system-design-chat-messaging": (
        "A group message to 500 members fan-out lagged 40 seconds during a product launch — users saw delays not because Cassandra was slow, but because we treated presence as a blocking dependency.",
        "real-time chat and messaging at scale",
        "When building one-to-one or group messaging with ordering, delivery receipts, and offline sync",
        "Blocking message delivery on presence checks or using a single SQL table for all messages without sharding",
        [
            ("WebSockets or long polling for chat?", "WebSockets for production duplex low-latency; long polling as fallback for restrictive networks — support both with transport negotiation."),
            ("How to store billions of messages?", "Partition by conversation ID in Cassandra/Scylla; paginate with cursors; never unsharded SQL at scale."),
            ("Offline message delivery?", "Persist, push notification, inbox queue; client syncs on reconnect with last-seen sequence number."),
        ],
    ),
    "system-design-distributed-cache": (
        "A hot product key expiring during a flash sale triggered a cache stampede that pushed PostgreSQL p99 to 800ms — one mutex per key fixed it in an afternoon.",
        "distributed caching with Redis and cache-aside patterns",
        "When read-heavy workloads overwhelm the database with repeated identical queries",
        "Fixed-window TTL on hot keys without stampede protection or L1 local buffer",
        [
            ("Distributed vs in-process cache?", "Distributed for shared state across instances; in-process for instance-local data with acceptable staleness — often use both L1+L2."),
            ("Prevent cache stampede?", "Request coalescing, probabilistic early expiration, never-expire hot keys with proactive refresh, local L1 buffer."),
            ("Which eviction policy?", "LRU general purpose; LFU for heavy-tail popularity; combine TTL with LRU for memory pressure."),
        ],
    ),
    "system-design-ecommerce-checkout": (
        "Black Friday taught us that payment success without order creation is not an edge case — it's a reconciliation emergency that happens whenever order service hiccups under load.",
        "e-commerce checkout with inventory reservation and saga compensations",
        "When checkout spans inventory, payment, and order services that fail independently",
        "Using two-phase commit across services or skipping idempotency on payment retries",
        [
            ("Prevent overselling?", "Atomic inventory reservation before payment with TTL; release on payment failure or expiry."),
            ("Payment succeeds, order fails?", "Durable queue retries order creation; reconciliation finds orphaned payments; idempotency keys on both sides."),
            ("2PC for checkout?", "No — use saga with compensating actions; each step idempotent for safe retries."),
        ],
    ),
    "system-design-file-storage-dropbox": (
        "Two users uploading the same installer shared 94% of chunks — without content-defined chunking and dedup, we would have paid for that storage twice.",
        "cloud file storage with chunk deduplication and sync",
        "When building Dropbox-style sync with versioning and conflict handling at petabyte scale",
        "Fixed-size chunking without content-defined boundaries — insertions invalidate all trailing chunks",
        [
            ("How does deduplication work?", "Hash fixed or content-defined chunks; store once, reference-count; increment on reuse across users and versions."),
            ("Offline edit conflicts?", "Detect concurrent modification; keep both versions as conflicted copy; notify user — last-writer-wins loses data."),
            ("Storage backend?", "Object storage for chunks; relational/NoSQL for metadata; never blob content in SQL."),
        ],
    ),
    "system-design-metrics-monitoring": (
        "At 3 AM the on-call engineer needed which service and endpoint in sixty seconds — metrics answered; logs would still be querying.",
        "metrics and monitoring platforms at scale",
        "When thousands of services emit time-series data needing alerting and dashboards",
        "High-cardinality labels like user_id on request counters — storage explosion in a week",
        [
            ("Metrics vs logs vs traces?", "Metrics aggregate health; logs detail events; traces follow request paths — use all three."),
            ("Cardinality explosion?", "Limit labels to low-cardinality dimensions; drop or aggregate excessive series; never label with request IDs."),
            ("Push vs pull?", "Pull for K8s long-running services; push for serverless and batch via collector gateway — most use both."),
        ],
    ),
    "system-design-news-feed": (
        "A celebrity with twelve million followers cannot use write fan-out — hybrid push-for-normal, pull-for-celebrity is how production feeds survive.",
        "social news feed generation and ranking",
        "When users follow hundreds of accounts and need ranked timelines under 100ms",
        "Pure fan-out on write for all users regardless of follower count",
        [
            ("Fan-out on write vs read?", "Write pushes to follower feeds — fast read, slow write; read merges at request — fast write, slow read; hybrid by follower threshold."),
            ("Ranking beyond chronological?", "Recency, engagement velocity, relationship strength, diversity — candidate generation then lightweight ranker."),
            ("Feed pagination?", "Cursor-based with timestamp+id composite; offset breaks on concurrent inserts."),
        ],
    ),
    "system-design-notification-system": (
        "Order-shipped in dev was one email; in prod it was push vs email vs quiet hours vs dedup vs locale — a platform, not a function call.",
        "multi-channel notification delivery platforms",
        "When product events trigger push, email, SMS with preferences and deduplication",
        "Sending duplicate notifications on at-least-once queue delivery without idempotency keys",
        [
            ("Prevent duplicate notifications?", "Idempotency key per event+user+channel; dedup store with TTL matching window."),
            ("Notification preferences at scale?", "Per-user per-type per-channel lookup; fail open for security alerts; fail closed for marketing."),
            ("Push vs email vs SMS?", "Push for urgent action; email for detail; SMS sparingly for critical — user-configurable per type."),
        ],
    ),
    "system-design-payment-system": (
        "Double charges generate chargebacks; lost payments mean free products — payment architecture tolerates zero 'mostly correct'.",
        "payment processing with authorization, capture, and ledger reconciliation",
        "When building payment flows requiring idempotency and PCI-compliant card handling",
        "Storing raw card numbers or skipping idempotency keys on timeout retries",
        [
            ("Authorization vs capture?", "Auth holds funds; capture moves money — auth at checkout, capture at ship for physical goods."),
            ("Exactly-once charging?", "Idempotency keys stored with results; retries return cached outcome without re-processing."),
            ("Store card numbers?", "Never — use processor tokenization; SAQ A with hosted fields."),
        ],
    ),
    "system-design-rate-limiter": (
        "Fifty thousand requests per minute from one API key starved the database until Redis token bucket returned 429 and everyone else recovered.",
        "distributed rate limiting across API gateway instances",
        "When protecting APIs from abuse and ensuring fair usage across tenants",
        "Local in-memory counters without shared state — limits fail across instances",
        [
            ("Token bucket vs sliding window?", "Token bucket allows controlled bursts; sliding window enforces hard cap in rolling period."),
            ("Multi-server rate limiting?", "Central Redis with atomic Lua scripts; all gateways read/write shared counters."),
            ("HTTP status for rate limits?", "429 with Retry-After and X-RateLimit-* headers on success responses too."),
        ],
    ),
    "system-design-ride-sharing": (
        "Matching drivers to riders in real time is a geo-index problem — full table scans on driver locations fail before you reach city-scale.",
        "ride-sharing dispatch and location matching",
        "When pairing supply and demand with live location updates and surge pricing",
        "Polling driver locations from primary database without geo-sharding or cell indexing",
        [
            ("Driver-rider matching?", "Geo-hash or H3 cells; query adjacent cells; update location every few seconds during active trip."),
            ("Surge pricing?", "Demand/supply ratio per cell; transparent multiplier before confirm; cap during emergencies per regulation."),
            ("ETA accuracy?", "Historical travel times per cell pair; live traffic feeds; separate estimate from match latency SLO."),
        ],
    ),
    "system-design-search-autocomplete": (
        "Users expect suggestions before finishing 'blu' — p95 under 100ms server-side or the product feels broken compared to Google-trained expectations.",
        "search autocomplete and typeahead at scale",
        "When prefix suggestions must rank millions of terms with personalization under 100ms",
        "Querying full search index on every keystroke without prefix cache or debounce",
        [
            ("Data structure for autocomplete?", "Trie, Elasticsearch completion suggester, or edge n-grams — FST compression in production indexes."),
            ("Ranking suggestions?", "Prefix match, popularity, CTR history, recency, business rules — precompute hot prefixes offline."),
            ("Latency budget?", "p95 under 100ms total; debounce client 150-300ms; cancel in-flight on new keystrokes."),
        ],
    ),
    "system-design-ticketing-booking": (
        "Selling the last seat to three users simultaneously is a row-lock problem — optimistic reservation with TTL beats hope.",
        "ticketing and seat reservation systems",
        "When holding inventory during checkout with concurrent buyers and payment timeouts",
        "Checking availability only at payment time without atomic hold during checkout session",
        [
            ("Prevent double booking?", "Atomic seat hold with TTL; UPDATE WHERE status=available; release on timeout or payment failure."),
            ("Waitlist?", "FIFO queue on sold-out; timed payment window when seat released; bot limits per account."),
            ("Payment timeout vs hold TTL?", "Hold TTL must exceed max payment time plus user think time; reconcile charged-without-seat edge case."),
        ],
    ),
    "system-design-url-shortener": (
        "Short links hide destinations — without malware scanning and rate limits, your domain becomes a phishing CDN.",
        "URL shortening with encoding, analytics, and abuse prevention",
        "When generating compact links with high read volume and custom domains",
        "Sequential integer IDs revealing total link count and enabling enumeration attacks",
        [
            ("Base62 vs hash IDs?", "Hash of URL with collision check or distributed ID generator — avoid predictable sequences."),
            ("Custom domains?", "Automate TLS via ACME; validate DNS before activation; isolate misconfigured customer domains."),
            ("Abuse prevention?", "Rate-limit creation; scan destinations; preview interstitial for flagged domains."),
        ],
    ),
    "system-design-video-streaming": (
        "Users buffer not because bitrate is wrong but because CDN missed the segment — ABR cannot fix origin shield gaps.",
        "video streaming with adaptive bitrate and CDN delivery",
        "When delivering VOD and live streams to millions with variable network conditions",
        "Single bitrate encoding without ladder — mobile users buffer on 4K streams",
        [
            ("ABR ladder design?", "Multiple encodes per title; player switches by buffer health; segment duration 2-6s by live vs VOD."),
            ("Live vs VOD pipeline?", "Separate queues — live missed window is permanent; VOD can retry transcode overnight."),
            ("DRM?", "Widevine/FairPlay for premium; license server separate trust boundary from CDN cache."),
        ],
    ),
    "tanstack-query-patterns": (
        "Cached server data in Redux goes stale silently — TanStack Query exists because server state is not client state.",
        "TanStack Query patterns for React server state",
        "When React apps fetch from APIs and need caching, invalidation, and optimistic updates",
        "Scattered string query keys without hierarchy — invalidation refetches everything or misses stale data",
        [
            ("What problem does TanStack Query solve?", "Server state caching, background refetch, deduplication — replaces useEffect fetch boilerplate."),
            ("TanStack Query vs Redux?", "Query for server state; small store for UI state — most Redux was cached API data."),
            ("Query invalidation?", "invalidateQueries with hierarchical keys — prefix match refetches nested queries."),
        ],
    ),
    "technical-writing-for-engineers": (
        "The best incident runbook had one accurate command; the worst was forty screens of stale Confluence — technical writing is information architecture under deadline.",
        "technical writing and documentation for engineers",
        "When READMEs, runbooks, and design docs must be used by tired on-call engineers",
        "Burying the fix below history and architecture — inverted pyramid violated",
        [
            ("Useful vs ignored docs?", "Answer specific question in under two minutes; copy-pasteable commands; current with code."),
            ("README structure?", "What it does, quickstart, config, common tasks, troubleshooting — architecture after runnable."),
            ("Docs in same repo?", "Yes — docs-as-code with PR review and CI link checks; wikis without review rot."),
        ],
    ),
    "terraform-drift-detection": (
        "Console hotfixes during an outage become permanent until drift detection shows production diverged from state three sprints ago.",
        "Terraform drift detection and remediation",
        "When infrastructure must match declared state and manual changes need visibility",
        "Running drift detection only pre-apply — changes between applies accumulate silently",
        [
            ("Scheduled vs event drift?", "Nightly full scan plus post-apply verification; alert on discrepancy with resource diff summary."),
            ("Import vs revert?", "Intentional hotfix imported within 24h; mistaken change reverted; undocumented drift is debt."),
            ("Tools?", "terraform plan against refreshed state; Spacelift, env0, or Terraform Cloud drift detection."),
        ],
    ),
    "terraform-modules-composition": (
        "Modules calling modules calling modules hid a variable passthrough bug that applied prod networking to staging.",
        "Terraform module composition and reuse",
        "When sharing infrastructure patterns across teams without copy-paste root modules",
        "Deep nesting beyond two levels without testing examples/ directory per module",
        [
            ("Module interface design?", "Minimal variables with defaults; outputs only what callers need; semantic version tags."),
            ("Testing modules?", "terraform validate in CI; terratest apply/destroy in ephemeral account nightly."),
            ("Composition vs nesting?", "Compose at root module; flatten deep chains; test each module independently."),
        ],
    ),
    "terraform-state-management-backends": (
        "Concurrent apply without state locking corrupted production state — two engineers, one bad afternoon, hours of recovery.",
        "Terraform remote state and backend configuration",
        "When teams share infrastructure state requiring locking and access control",
        "Disabling locking or monolithic state for entire org — every apply risks everything",
        [
            ("State locking?", "S3+DynamoDB, GCS native, or TFC — never concurrent apply without lock."),
            ("Separate state per env?", "Yes — separate backends and accounts for prod; not workspace toggle on laptop."),
            ("State backup?", "terraform state pull before migrate; versioned storage; practice restore in dev."),
        ],
    ),
    "terraform-testing-policy-as-code": (
        "A policy advisory for six weeks blocked nothing — the non-compliant S3 bucket was public until deny mode and a failing CI job.",
        "Terraform policy-as-code with OPA, Sentinel, or Conftest",
        "When infrastructure changes need automated compliance before apply",
        "Enabling deny policies without test cases — false positives block all deploys or get disabled",
        [
            ("OPA vs Sentinel?", "OPA/Rego portable across K8s and TF; Sentinel TFC-native — pick by platform."),
            ("Advisory vs deny?", "Start advisory two weeks; measure violations; then enforce deny with tested policies."),
            ("Testing policies?", "Conftest on plan JSON in CI; positive and negative fixtures per rule."),
        ],
    ),
    "terraform-workspaces-environments": (
        "terraform workspace select prod from a laptop should be structurally impossible — separate backends and CI pipelines enforce that.",
        "Terraform workspaces vs environment isolation",
        "When managing dev/staging/prod infrastructure with Terraform",
        "Using workspaces as sole prod isolation while sharing credentials and state backend",
        [
            ("Workspaces vs separate state?", "Workspaces share config — OK dev/staging one account; prod needs separate state and account."),
            ("Secrets in workspaces?", "CI secret store or TFC sensitive variables — never commit tfvars secrets."),
            ("Promotion flow?", "Merge infra code through branches with increasing approval gates — not manual workspace switch."),
        ],
    ),
    "testing-compose-uis-v2": (
        "Compose UI tests asserting pixel position broke on every font update — semantics and testTag discipline fixed the suite.",
        "testing Jetpack Compose UI with semantics and test tags",
        "When verifying Compose screens for behavior and accessibility in CI",
        "Testing implementation details instead of semantics — breaks on refactor without behavior change",
        [
            ("Semantics vs testTag?", "Prefer contentDescription and role; testTag when no semantic equivalent — avoid over-tagging."),
            ("Flaky Compose tests?", "Idling resources for animations; custom idling for async; createAndroidComposeRule with isolated state."),
            ("Robolectric vs device?", "Robolectric for logic; device/instrumentation for touch targets and real rendering."),
        ],
    ),
    "testing-contract-testing-microservices": (
        "Renaming customerId to customer_id broke notifications in production — integration tests mocked the downstream service.",
        "contract testing with Pact and consumer-driven contracts",
        "When microservices share APIs and integration tests are slow or environment-contended",
        "Integration tests with mocked downstream — proves wiring not contract agreement",
        [
            ("What is contract testing?", "Consumer defines expected interactions; provider verifies in isolation via pact files."),
            ("Vs integration testing?", "Contract tests run fast without full stack; integration tests need shared environment."),
            ("When adopt Pact?", "Multiple teams, slow integration suites, production breaks from API changes."),
        ],
    ),
    "testing-coroutines-flows-turbine": (
        "A Flow test passed with delay(1000) that always timed out in CI — Turbine with test scheduler made async deterministic.",
        "testing Kotlin coroutines and Flows with Turbine",
        "When verifying async streams and coroutine scopes in Android and KMP code",
        "runBlocking with real delays instead of TestScope and virtual time",
        [
            ("Turbine vs collect?", "Turbine asserts emissions in order with timeouts; cleaner than manual collect jobs."),
            ("TestScope?", "StandardTestDispatcher advances virtual time — no real Thread.sleep in tests."),
            ("Testing SharedFlow?", "ExtraBufferCapacity and replay affect assertions — document expected hot vs cold behavior."),
        ],
    ),
    "testing-flaky-tests-root-causes": (
        "Retry-until-green hid a race condition for three months — the test was telling us the product was broken, not that CI was unlucky.",
        "identifying and fixing flaky test root causes",
        "When CI trust erodes from non-deterministic test failures",
        "Retry decorators on flaky tests instead of fixing timing or isolation",
        [
            ("Common flake causes?", "Shared mutable state, real time, network without mock, test order dependency."),
            ("Quarantine policy?", "Move flaky tests to nightly quarantine until fixed — track count as team health metric."),
            ("Detect flakes?", "Run tests 100x locally; bisect timing; use --repeat in CI on changed tests."),
        ],
    ),
    "testing-mutation-testing": (
        "100% line coverage still shipped a bug — mutants changing > to >= survived because assertions were too weak.",
        "mutation testing with PIT, Stryker, and mutmut",
        "When unit test coverage numbers lie about assertion strength",
        "Chasing coverage percentage without mutation score on critical modules",
        [
            ("Mutation score?", "Percentage of mutants killed — measures assertion strength not lines executed."),
            ("CI cost?", "Run nightly on core modules; shard by package; cache analysis per git tree."),
            ("Surviving mutants?", "Strengthen assertions or mark equivalent mutants — do not disable categories wholesale."),
        ],
    ),
    "testing-playwright-e2e": (
        "E2E passed locally, failed in CI at login — global storage state reuse cut suite time 80% and fixed isolation bugs.",
        "Playwright end-to-end testing patterns",
        "When critical user journeys need real browser verification in CI",
        "Hardcoded waits and xpath selectors — flakes on every UI tweak",
        [
            ("Flake resistance?", "getByRole locators; auto-wait; fresh context per test; MSW for API when appropriate."),
            ("Auth reuse?", "globalSetup saves storageState; authenticated projects skip login per test."),
            ("Trace on failure?", "trace on-first-retry; video retain-on-failure; artifact links in CI comments."),
        ],
    ),
    "testing-property-based-testing": (
        "Unit tests used unique list elements exclusively — property test found sort dropped duplicates on input [3,3,1].",
        "property-based testing with Hypothesis, QuickCheck, and jqwik",
        "When pure functions have invariants better expressed as for-all properties",
        "Only example tests with hand-picked inputs missing edge cases generators find automatically",
        [
            ("Property vs example tests?", "Properties verify invariants for all generated inputs; examples document specific regressions."),
            ("Vs fuzz testing?", "Fuzz finds crashes; property tests assert invariants and shrink failures."),
            ("Slow properties?", "Reduce max_examples in CI; full count nightly; custom generators for valid domain inputs."),
        ],
    ),
    "testing-pyramid-vs-trophy": (
        "The testing trophy emphasizes integration tests where bugs actually live — not deleting unit tests, rebalancing effort.",
        "testing pyramid vs testing trophy for modern apps",
        "When deciding test investment across unit, integration, and E2E layers",
        "100% unit tests with every dependency mocked — green suite, production failures",
        [
            ("Pyramid vs trophy?", "Pyramid emphasizes unit base; trophy emphasizes integration/static analysis for modern stacks with UI and API boundaries."),
            ("How many E2E?", "Few critical paths — login, checkout, core workflow — not every edge case."),
            ("Static analysis layer?", "Lint, typecheck, security scan in trophy — catch bugs before runtime tests."),
        ],
    ),
    "testing-snapshot-testing-tradeoffs": (
        "Snapshot PRs with 4000 lines of diff get approved without reading — scoped snapshots on design system primitives only.",
        "snapshot testing tradeoffs in Jest and Vitest",
        "When catching unintended UI or serialization changes automatically",
        "Page-level snapshots that change weekly and train reviewers to click update blindly",
        [
            ("When snapshots help?", "Stable components, email templates, serialized API responses — small stable output."),
            ("When they hurt?", "Whole pages, frequently changing marketing copy — noise exceeds signal."),
            ("Review discipline?", "Second reviewer for snapshot-only changes; pair with explicit assertions on critical content."),
        ],
    ),
    "testing-test-data-builders": (
        "Shared mutable builder defaults caused test B to fail only when test A ran first — fresh build() per test fixed order dependency.",
        "test data builders and object factories",
        "When tests need varied complex domain objects without copy-paste setup",
        "Fixture dicts mutated across tests or builders with shared list defaults",
        [
            ("Builders vs fixtures?", "Builders for variation with defaults; fixtures for static shared setup — fresh instances per test."),
            ("Naming?", "OrderBuilder not DbOrderFactory — match domain language; document default assumptions."),
            ("Randomized data?", "Fixed seed in CI for reproducible failures; random only for property-style exploration."),
        ],
    ),
    "testing-test-doubles-mocks-stubs": (
        "Over-mocked tests broke on refactor without behavior change — fakes and real Testcontainers caught the wiring bug.",
        "test doubles: mocks, stubs, spies, and fakes",
        "When isolating units from external systems in tests",
        "Mocking every collaborator — tests coupled to call order and internal methods",
        [
            ("Mock vs stub vs fake?", "Stub returns canned data; mock verifies interaction; fake has working implementation for tests."),
            ("When not to mock?", "Prefer fake in-memory repository over mock ORM — tests behavior not SQL call sequence."),
            ("Contract for fakes?", "Run same contract tests against fake and sandbox integration."),
        ],
    ),
    "testing-unit-vs-integration-balance": (
        "Six mocked services proved our handler called mock — one Testcontainers integration test proved Postgres constraint actually worked.",
        "balancing unit and integration tests",
        "When CI needs confidence without fifteen-minute suites or false confidence from mocks",
        "Integration tests that mock the database — wiring test not integration test",
        [
            ("Honeycomb vs pyramid?", "More integration tests at service boundaries; fewer unit tests of trivial getters."),
            ("Testcontainers?", "Real Postgres/Redis in CI Docker — catch SQL and config errors mocks miss."),
            ("Suite time budget?", "Keep integration under ten minutes or teams skip; parallelize by module."),
        ],
    ),
    "testing-vitest-react-testing-library": (
        "Vitest plus Testing Library made component tests fast enough to run on every save — MSW at network layer kept tests realistic.",
        "Vitest with React Testing Library patterns",
        "When testing React components with fast feedback in Vite projects",
        "fireEvent click without userEvent — misses disabled button and pointer event bugs",
        [
            ("Query priority?", "getByRole, getByLabelText, getByText — getByTestId last resort."),
            ("MSW setup?", "handlers by domain; server.use per test for errors; reset handlers after each test."),
            ("Vitest isolation?", "pool forks for global pollution; mock reset between tests."),
        ],
    ),
    "threat-modeling-data-flow-diagrams": (
        "Uploaded HTML served from app domain stole session cookies — one threat modeling session would have flagged the cross-origin data flow.",
        "threat modeling with data-flow diagrams and STRIDE",
        "Before implementing features handling untrusted input or crossing trust boundaries",
        "Architecture diagrams without data flows — miss where untrusted data enters",
        [
            ("When threat model?", "Before implementation and on major architecture changes — cheap to fix in design."),
            ("STRIDE?", "Spoofing, Tampering, Repudiation, Information Disclosure, DoS, Elevation — per component and flow."),
            ("Tools?", "Whiteboard fine; MS Threat Modeling Tool or OWASP Threat Dragon for STRIDE generation."),
        ],
    ),
    "threat-modeling-stride": (
        "STRIDE per element sounds tedious until spoofing on your admin API without MFA shows up in the same session as tampering on unsigned webhooks.",
        "STRIDE threat categorization for system design",
        "When systematically identifying threats at each trust boundary and data store",
        "Running STRIDE once at project start and never updating when architecture changes",
        [
            ("STRIDE per element?", "Apply each category to processes, data stores, flows, and external entities — focus trust boundaries first."),
            ("Prioritize mitigations?", "DREAD scoring or High/Medium/Low; fix High before ship; document accepted Low risk."),
            ("STRIDE vs attack trees?", "STRIDE categorizes; attack trees enumerate paths — complementary not replacement."),
        ],
    ),
    "time-series-databases-iot": (
        "Ten million devices reconnecting after outage created an ingestion spike that dropped samples — queue buffering before TSDB write saved the pipeline.",
        "time-series databases for IoT ingestion and querying",
        "When device telemetry arrives at high volume with retention and downsampling needs",
        "Device ID as high-cardinality metric label — series explosion in days",
        [
            ("TSDB for IoT?", "InfluxDB, TimescaleDB, QuestDB — ingest bursts via Kafka/Kinesis buffer before write."),
            ("Cardinality?", "Aggregate by device type and region; store device metadata separately from metric labels."),
            ("Retention?", "Raw short window for debug; downsampled long window for capacity planning."),
        ],
    ),
    "timeseries-downsampling-retention": (
        "Alerting on five-minute downsampled latency missed thirty-second spikes that triggered SLA credits — hot tier alerts, warm tier trends.",
        "time-series downsampling and retention policies",
        "When storing metrics long-term without unbounded storage cost",
        "Averaging percentiles when downsampling — mathematically meaningless",
        [
            ("Aggregation per type?", "Counters sum/rate; gauges avg/min/max; histograms need raw or max of p99 not avg of p99."),
            ("Retention tiers?", "Hot full resolution for alerts; warm downsampled for trends; cold compliance archive."),
            ("User-facing charts?", "Label downsampled ranges so users know resolution limits incident investigation."),
        ],
    ),
    "timeseries-influxdb-vs-timescale": (
        "Team knew SQL — Timescale JOIN with orders table beat exporting Influx to CSV for billing reconciliation.",
        "InfluxDB vs TimescaleDB for time-series workloads",
        "When choosing time-series storage for metrics or IoT data",
        "Picking based on benchmark blog without matching query patterns team already knows",
        [
            ("Influx strengths?", "High ingest, built-in downsampling tasks, Flux/InfluxQL for metrics-native queries."),
            ("Timescale strengths?", "PostgreSQL SQL, JOINs with relational data, familiar ops for PG teams."),
            ("Hybrid?", "Dual-write during migration; compare query results before cutover."),
        ],
    ),
    "timeseries-prometheus-remote-write": (
        "Remote write buffer filled during backend outage — samples dropped silently until we monitored wal_corruptions and send_errors.",
        "Prometheus remote write to long-term storage",
        "When Prometheus local retention insufficient and global view needed",
        "HA Prometheus duplicate remote write without receiver deduplication — double-counted rates",
        [
            ("Remote write reliability?", "Monitor buffer size, retry rate, dropped samples; configure queue_config capacity."),
            ("HA dedup?", "Thanos/Mimir dedup replica labels at query time — without it dashboards lie."),
            ("Cardinality at receiver?", "Per-tenant series limits — one bad deploy should not crash global metrics."),
        ],
    ),
    "tokenization-bpe-explained": (
        "GPT tokenizers split 'unhappiness' into subwords you would never guess — BPE merge table determines model efficiency and OOV behavior.",
        "byte-pair encoding tokenization for LLMs",
        "When understanding how text becomes tokens for training and inference",
        "Assuming word boundaries match tokenizer splits — breaks prompt engineering and context budgeting",
        [
            ("What is BPE?", "Iteratively merge frequent byte pairs into subword vocabulary — balances compression and granularity."),
            ("Vocab size tradeoff?", "Larger vocab shorter sequences but bigger embedding table; train on representative corpus."),
            ("Multilingual?", "Joint BPE shares subwords across languages; language-specific vocabs for single-language deployment."),
        ],
    ),
    "transformer-attention-explained": (
        "Attention is not magic — it is weighted lookup where queries find relevant keys and blend values, parallelized as matrix multiply.",
        "transformer self-attention mechanism",
        "When implementing or debugging attention-based models and context limits",
        "O(n²) memory surprise at long context — standard attention does not scale without FlashAttention or sparse patterns",
        [
            ("Q K V?", "Query searches; Key matched against; Value blended output — softmax weights the combination."),
            ("Multi-head?", "Parallel attention subspaces concatenated — different heads learn different relationship types."),
            ("KV cache?", "Inference caches keys/values for prior tokens — memory grows linearly with generation length."),
        ],
    ),
    "typescript-branded-types-safety": (
        "Swapped account IDs in transferFunds compiled clean — both were string until branded AccountId caught it pre-merge.",
        "TypeScript branded types for nominal safety",
        "When distinct primitives must not be interchangeable at compile time",
        "Type aliases documenting intent without enforcement — structural typing treats them as identical",
        [
            ("What is branded type?", "Phantom property makes string UserId distinct from OrderId at compile time."),
            ("Runtime cost?", "Zero — brands erase; validation only at construction boundaries."),
            ("When use?", "IDs, currencies, units, validated tokens — any same-shaped values that must not mix."),
        ],
    ),
    "typescript-conditional-mapped-types": (
        "Conditional types filtered API response keys at compile time — manual Pick definitions duplicated across twelve files until one mapped type unified them.",
        "TypeScript conditional and mapped types",
        "When transforming types based on conditions or keys programmatically",
        "Copy-pasting Pick/Omit variants instead of one mapped type with keyof constraints",
        [
            ("Conditional types?", "T extends U ? X : Y — filter and transform based on type relationships."),
            ("Mapped types?", "Iterate keys with modifiers Readonly, Partial, or template remapping."),
            ("Distributive conditionals?", "Union distributes over conditional — understand when infer applies per member."),
        ],
    ),
    "typescript-const-type-parameters": (
        "Generic tuple inference widened ['a','b'] to string[] until const type parameter preserved literal tuple for route config.",
        "const type parameters in TypeScript 5",
        "When generic functions should preserve literal inference from arguments",
        "Forcing callers to write as const on every literal argument to generic helpers",
        [
            ("const T extends?", "Type parameter infers readonly literal types instead of widening to string or number."),
            ("Use cases?", "Tuple configs, route definitions, design tokens passed to generic factories."),
            ("Library authors?", "Improves DX — consumers get literals without as const ceremony."),
        ],
    ),
    "typescript-discriminated-unions": (
        "Switch on event.type without never check meant new event kind compiled silently — exhaustiveness is the point of discriminated unions.",
        "discriminated unions for type-safe state machines",
        "When modeling variants with shared and unique fields in TypeScript",
        "Optional fields simulating variants — compiler cannot narrow without discriminant",
        [
            ("Discriminated union?", "Shared field kind/tag with literal types narrows in switch automatically."),
            ("Exhaustiveness?", "default: const _exhaustive: never = value catches unhandled variants at compile time."),
            ("Vs inheritance?", "Unions are closed set of variants; easier to exhaust than class hierarchies in TS."),
        ],
    ),
    "typescript-generics-constraints": (
        "extends Serializable documented the contract better than casting inside the function body — constraints visible to callers.",
        "generic constraints with extends in TypeScript",
        "When type parameters need minimum capability guarantees",
        "Unconstrained generics defaulting to unknown then asserting — hides requirements",
        [
            ("extends vs assertion?", "Constraint documents required shape; assertion hides bugs until runtime."),
            ("keyof T?", "Common pattern for typed property access without string index signature."),
            ("Multiple constraints?", "Intersection extends T & U — rare; prefer single interface combining requirements."),
        ],
    ),
    "typescript-module-augmentation-globals": (
        "Express Request needed userId on every handler — module augmentation once beat declaring global in every route file.",
        "module augmentation for global and third-party types",
        "When extending types from libraries without forking @types packages",
        "declare global any on Request — loses all type safety for augmented fields",
        [
            ("Module augmentation?", "declare module 'express-serve-static-core' { interface Request { userId: string } }"),
            ("Where declare?", "Dedicated .d.ts in tsconfig include — not scattered in .ts implementation files."),
            ("Upgrade risk?", "Upstream @types changes can break augmentation — test on dependency bumps."),
        ],
    ),
    "typescript-path-mapping-monorepo": (
        "Relative imports ../../../shared broke when we moved one package — path aliases and workspace names fixed the graph.",
        "TypeScript path mapping in monorepos",
        "When packages reference each other without deep relative paths",
        "paths in tsconfig without matching bundler and test runner config — CI passes one fails other",
        [
            ("paths vs workspaces?", "Prefer @org/pkg workspace imports; paths for internal src aliases within package."),
            ("Test runner?", "Vitest/Jest moduleNameMapper must mirror paths — or tests diverge from build."),
            ("Project references?", "Build order via references; composite projects for incremental builds."),
        ],
    ),
    "typescript-result-type-error-handling": (
        "Thrown exceptions in checkout hid failure paths from type signatures — Result at API boundary made callers handle failure explicitly.",
        "Result types for explicit error handling in TypeScript",
        "When functions fail predictably and callers must handle errors without try/catch sprawl",
        "Result everywhere including internal helpers — nested ok checks worse than exceptions internally",
        [
            ("Result vs throw?", "Result at module boundaries; exceptions OK internally if team convention clear."),
            ("Ergonomics?", "No ? operator — helper map/andThen reduces nesting; consider neverthrow library."),
            ("HTTP mapping?", "Consistent Err to status code table — 404 vs 400 vs 500 from error variant."),
        ],
    ),
    "typescript-satisfies-operator": (
        "Config object lost literal types with annotation Config but satisfies Config kept 'dark' as literal for theme union.",
        "satisfies operator for validation without widening",
        "When objects must match interface while preserving literal inference",
        "Type annotation widening literal keys to string — loses exhaustiveness in switch on config.mode",
        [
            ("satisfies vs annotation?", "satisfies validates without widening; annotation widens to interface field types."),
            ("vs as const?", "as const freezes values; satisfies validates against external type — combine both when needed."),
            ("ESLint?", "prefer-satisfies encourages over annotation on config objects."),
        ],
    ),
    "typescript-strict-mode-migration": (
        "strictNullChecks alone found 400 null dereferences — enabling full strict one flag at a time beat big-bang weekend.",
        "incremental migration to TypeScript strict mode",
        "When adopting strict compiler options on legacy JavaScript or loose TS codebases",
        "Enabling strict all at once — PR too large to review; reverts lose momentum",
        [
            ("Order of flags?", "strictNullChecks first; noImplicitAny second; strictFunctionTypes when callbacks typed."),
            ("Legacy escape?", "@ts-expect-error with ticket ID and expiry — not @ts-ignore permanent."),
            ("Track progress?", "Weekly error count dashboard; celebrate downward trend not zero-or-nothing."),
        ],
    ),
    "typescript-strict-null-checks-migration": (
        "optional?.chained everywhere masked places that needed explicit guard — strict null checks forced real invariants at boundaries.",
        "migrating to strictNullChecks",
        "When undefined and null must be handled explicitly in TypeScript",
        "Non-null assertion ! as default fix — hides real undefined paths",
        [
            ("Fix patterns?", "Narrowing guards, optional chaining, nullish coalescing — assertDefined helper at boundaries."),
            ("Optional param?", "param?: T accepts missing and undefined; be consistent across API surface."),
            ("DB rows?", "Query result types often optional until existence proven — model explicitly."),
        ],
    ),
    "typescript-template-literal-types": (
        "Route params typed from `/users/${id}` template caught typo in `/user/${id}` at compile time — stringly routes became checked.",
        "template literal types for routes and events",
        "When string patterns should be validated at type level",
        "Complex template types slowing tsserver — split modules if autocomplete lags",
        [
            ("Route typing?", "Combine template literals with union of param names for typed router helpers."),
            ("Limits?", "Recursive depth limits — watch for excessively deep instantiation errors."),
            ("Runtime match?", "Types do not validate runtime strings — pair with Zod or parser at boundary."),
        ],
    ),
    "typescript-type-guards-narrowing": (
        "filter(Boolean) did not narrow (T|null)[] to T[] until isDefined type predicate — guards must be explicit for compiler.",
        "type guards and discriminated narrowing",
        "When TypeScript needs help narrowing union types in conditionals",
        "Casting with as instead of guard — bypasses checking without runtime validation",
        [
            ("User-defined guard?", "function isUser(x: unknown): x is User with runtime check inside."),
            ("in operator?", "Narrows discriminated unions on kind field in switch."),
            ("Array filter?", "Type predicate on callback required for filter to narrow array type."),
        ],
    ),
    "typescript-utility-types-app-patterns": (
        "Partial for PATCH and Required for create DTOs — utility types beat hand-rolling optional variants per endpoint.",
        "TypeScript utility types in application patterns",
        "When transforming interfaces for API layers without duplicate definitions",
        "Custom Optional<T> duplicating Partial — learn stdlib before reinventing",
        [
            ("Partial vs Pick?", "Partial all optional for updates; Pick subset for response DTOs."),
            ("Awaited?", "Unwrap Promise return types from async functions for typed handlers."),
            ("Readonly?", "Deep readonly for config passed through call stack without mutation."),
        ],
    ),
    "typescript-zod-runtime-validation": (
        "Malformed CMS payload crashed checkout until Zod at API boundary failed in dev with field path not user session.",
        "Zod runtime validation with inferred TypeScript types",
        "When external JSON needs validation at system boundaries",
        "Duplicate interface plus Zod schema drifting apart — use z.infer from single schema",
        [
            ("Schema first?", "Define Zod schema; infer type with z.infer — single source of truth."),
            ("Where validate?", "HTTP handlers, env at boot, form submit — not every internal function call."),
            ("Error UX?", "flatten or format for field-level form errors from safeParse."),
        ],
    ),
    "using-ai-coding-agents-senior-engineer": (
        "Senior engineers using AI agents ship faster on boilerplate and slower on architecture — the skill is knowing which is which before accepting the diff.",
        "using AI coding agents effectively as a senior engineer",
        "When integrating Cursor, Copilot, or agents into professional development workflow",
        "Accepting large agent diffs without reading — subtle security and logic bugs slip through",
        [
            ("Where agents help seniors?", "Boilerplate, test scaffolding, regex, migration scripts — bounded tasks with clear verification."),
            ("Where they hurt?", "Architecture decisions, security boundaries, subtle concurrency — human owns the invariant."),
            ("Review discipline?", "Same bar as junior PR — agent author does not get skip review; run tests and read diff line by line."),
        ],
    ),
}


def extract_good_faq(raw: str) -> list[tuple[str, str]] | None:
    if GENERIC_FAQ in raw:
        return None
    faqs = []
    for m in re.finditer(r'- q: "([^"]*)"\s*\n\s*a: "([^"]*)"', raw):
        faqs.append((m.group(1), m.group(2)))
    return faqs[:3] if len(faqs) >= 3 else None


def process_slug(slug: str) -> dict:
    path = BLOG / f"{slug}.md"
    if not path.exists():
        return {"slug": slug, "status": "missing", "words": 0}
    raw = path.read_text(encoding="utf-8")
    if not needs_rewrite(raw):
        return {"slug": slug, "status": "skipped", "words": wc(raw.split("---", 2)[-1])}
    meta = TOPICS.get(slug)
    if not meta:
        return {"slug": slug, "status": "no_metadata", "words": 0}
    existing = parse_fm(raw)
    existing["slug"] = slug
    hook, tech, when, mistake, default_faqs = meta
    faqs = extract_good_faq(raw) or default_faqs
    fm = build_frontmatter(existing, faqs)
    body = build_body(slug, (hook, tech, when, mistake, faqs))
    path.write_text(fm + "\n\n" + body, encoding="utf-8")
    return {"slug": slug, "status": "done", "words": wc(body)}


def main():
    slugs = [s.strip() for s in SLUG_FILE.read_text().splitlines() if s.strip()]
    results = [process_slug(s) for s in slugs]
    done = sum(1 for r in results if r["status"] == "done")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    under = [r for r in results if r["status"] == "done" and r["words"] < TARGET]
    samples = sorted([r for r in results if r["status"] == "done"], key=lambda x: -x["words"])[:3]
    report = {
        "done": done,
        "skipped": skipped,
        "under_1200": len(under),
        "samples": samples,
        "results": results,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"done": done, "skipped": skipped, "under_1200": len(under), "samples": samples}, indent=2))
    if under:
        print("UNDER:", [(r["slug"], r["words"]) for r in under])


if __name__ == "__main__":
    main()
