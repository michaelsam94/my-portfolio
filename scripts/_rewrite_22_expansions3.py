# Third expansion — final push to >=1200 words for all posts

EXPANSIONS3 = {}

def add(slug, text):
    EXPANSIONS3[slug] = "\n\n" + text.strip()

add("seo-meta-robots-noindex-patterns", """
## Enterprise multi-site governance

Large orgs maintain spreadsheet of hostnames with expected robots policy — automated nightly crawler compares live meta and headers to registry, pages security on mismatch. Include marketing campaign microsites often forgotten after campaign ends.

## Cookie consent and noindex

GDPR banners sometimes inject noindex on entire site when misconfigured — consent platform A/B test accidentally sets noindex on control bucket. Monitor Search Console indexing status after consent vendor changes.

## Canonical plus noindex interaction

noindex URL can still specify canonical to preferred URL — Google may consolidate signals but not index noindex page. Use when phasing out duplicate URL space without immediate redirect capability.
""")

add("serverless-database-access-patterns", """
## GCP Cloud Functions and Cloud SQL

Cloud SQL Auth Proxy sidecar or connector library pools connections similarly to RDS Proxy. Set `max_instances` on Cloud Functions to cap concurrent DB connections during traffic spikes.

## PlanetScale and Vitess

Serverless MySQL platforms shard connections — understand transaction limitations across shards before migrating Lambda CRUD.

## Observability

Emit metric `db_pool_wait_ms` from Lambda custom metric when connection acquisition slow — early warning before timeouts cascade to 502 responses at API Gateway.
""")

add("shared-data-layer-room-kmp", """
## Offline-first UX patterns

Repository exposes `Flow<LoadState<T>>` combining local cache and network refresh — UI shows stale-while-revalidate with timestamp. Single pattern in commonMain; Snackbar on sync failure via expect/actual notification bridge.

## Conflict resolution UI copy

User-facing strings stay platform-specific; conflict enum and resolution logic shared. Map `ConflictType.DIVERGED` to localized string in Android `strings.xml` and iOS `Localizable.strings`.

## Performance profiling

Android Studio Database Inspector for Room; iOS Instruments with logging SQL trace enabled in debug builds. Shared slow query list prioritized in sprint — indexes added in common migration benefit both platforms simultaneously.
""")

add("supply-chain-dependency-pinning", """
## Hermetic builds

Bazel and Nix provide hermetic dependency graphs beyond language lockfiles — consider for security-critical artifacts where reproducibility includes compiler toolchain hash.

## Private fork pinning

Fork of upstream library pinned to git SHA in package.json:

```json
"dependencies": {
  "critical-lib": "github:myorg/critical-lib#commitSHA"
}
```

Review fork quarterly for upstream merge — pinned fork becomes silent security debt.

## Audit trail

Every lockfile PR requires linked ticket for reason — dependency update, security CVE, feature need. Blame log explains why version exists years later during incident.
""")

add("technical-writing-for-engineers", """
## Conference talk vs written doc

Talks inspire; docs instruct. Convert talk content to docs by adding commands, prerequisites, and failure modes absent from slides. Link video at top of doc for narrative learners.

## AI-assisted drafts

LLM drafts outline acceptable; engineer must run commands and verify output before merge. Mark AI-assisted docs with review date — models hallucinate flags and API shapes.

## Ownership model

Each doc page has named owner in front matter — orphaned docs without owner deleted in annual cleanup unless adopted.
""")

add("testing-compose-uis-v2", """
## Preview parameter testing

```kotlin
@Preview
@Composable
fun LoginPreview() { LoginScreen(onSubmit = {}) }

@Test
fun loginPreviewRenders() {
    composeRule.setContent { LoginPreview() }
    composeRule.onNodeWithText("Sign in").assertExists()
}
```

Preview-driven tests catch regressions in isolated components before integration screen tests.

## Modal and dialog tests

```kotlin
composeRule.onNodeWithText("Delete").performClick()
composeRule.onNodeWithTag("confirm_dialog").assertIsDisplayed()
composeRule.onNodeWithText("Confirm").performClick()
```

Dialogs often in separate composition — waitForIdle after open.

## GitHub Actions emulator

Use reactivecircus/android-emulator-runner with API 34 image; cache AVD snapshot for Compose instrumented job under 15 minutes.

## Semantics merge policy

Document team rule: interactive elements must have contentDescription OR visible text OR testTag — PR checklist item for accessibility and testability together.
""")

add("testing-mutation-testing", """
## Mutation testing economics

Estimate CI cost: mutants × test suite seconds × hourly CI rate. If exceeds escaped bug cost, scope to diff-only mutation on PR. Full nightly still runs on domain packages.

## Kotlin coroutines mutants

Mutants on suspend function delay or dispatcher — survivors reveal tests not controlling time. Pair mutation with kotlinx-coroutines-test.

## Reporting to QA

Mutation survivors list exported as CSV — QA adds manual test cases for unkillable mutants representing high-risk paths automation missed.

## Integration with code review

Block merge if mutation score drops on touched files — GitHub Action comment lists surviving mutants with deep links to code lines.
""")

add("testing-playwright-e2e", """
## Test data factories in E2E

Factory creates user via API, returns credentials — test focuses on UI path only. Delete user in afterEach for cleanup unless isolated tenant.

## Network HAR recording

`recordHar` option captures network on failure — debug flaky API race without reproducing locally first time.

## Cross-browser policy

Run full matrix nightly; PR gate chromium only for speed — document policy so teams know Firefox regressions caught within 24h.

## Playwright MCP and agent debugging

Trace files attach to CI artifacts — on failure download trace, open Playwright Trace Viewer, step through DOM state before failure. Faster than re-running headed locally guessing timing.

## Selectors migration

When refactoring from CSS to role locators, migrate one spec file per PR — dual selectors temporarily with deprecation comment avoids big-bang breakage.
""")

add("testing-property-based-testing", """
## Custom strategies for domain

Build `st.from_type(UserId, lambda: st.uuids().map { UserId(it) })` — branded types get valid generators once, reused across properties.

## Parallel execution

Hypothesis examples run sequentially by default — mark heavy properties `@settings(max_examples=20)` in CI, 200 locally pre-push.

## Teaching properties in code review

Ask "what invariant should always hold?" — if answer exists, request property test alongside example test in review.

## Serialization roundtrips

JSON, protobuf, avro — property: parse(serialize(x)) equivalent to x under equality. Catches field number and naming drift across services.

## Negative testing

Generate invalid inputs expecting rejection — parser must not throw, return Result.error. Complement positive roundtrip properties.
""")

add("testing-snapshot-testing-tradeoffs", """
## Snapshot size limits in CI

Fail CI if any snapshot file grows >20% lines without approval label — prevents accidental whole-page snapshot addition.

## DOM snapshot vs accessibility tree snapshot

Some teams snapshot accessibility tree text — closer to user perception than HTML div soup.

## Deprecation workflow

Mark snapshot test `@deprecated` when replacing with RTL assertions — delete following sprint after replacement merged.

## Component props matrix

Table-driven snapshot: list of prop combinations, loop render and snapshot each variant with descriptive test name — structured alternative to one giant snap.
""")

add("testing-test-data-builders", """
## Builder validation errors

Builder `build()` throws if invalid combo — e.g. `expiredTrial` with `admin` role — catch impossible states at construction not assertion.

## Thread safety

Builders not thread-safe — create per test; static default templates copied per build via structuredClone.

## Graph builders

OrderBuilder.withLineItems(count) generates nested builders — fluent API for complex aggregates without 200-line fixture JSON files.

## Documentation site

Publish test persona catalog — "AdminAlice has billing override" linked from integration test README for QA alignment.
""")

add("testing-test-doubles-mocks-stubs", """
## Mockito verifyNoMoreInteractions

After test actions, verify no unexpected calls on mock — catches leaky interactions.

## Fake persistence in memory

Fake implements same interface as production repository — swap in DI test module Spring `@TestConfiguration`.

## Avoid mocking value types

Money, Email value objects — use real instances in tests; mocking strings hides formatting bugs.

## Record/replay HTTP

VCR cassettes for integration tests — real HTTP once, replay stub thereafter; update cassette when API contract changes intentionally.
""")

add("testing-unit-vs-integration-balance", """
## Architecture fitness function

ArchUnit test: repository interfaces not imported in domain package — enforces layer boundaries unit tests assume.

## Test naming convention

Prefix integration tests `IT` or suffix `IntegrationTest` — Maven failsafe vs surefire split execution times.

## Production traffic shadow

Compare integration test fixture responses to sampled production responses — detect schema drift before deploy.

## When to delete unit tests

Integration test covers same behavior with real DB — delete redundant mocked unit test unless unit runs 100x faster and runs on every keystroke in TDD loop.
""")

add("testing-vitest-react-testing-library", """
## Testing Server Components

Server Components tested indirectly via E2E or export pure child client components for RTL — document boundary in testing guide.

## userEvent vs fireEvent migration

Codemod fireEvent to userEvent — incremental PRs; document pointer events difference for checkbox vs click.

## Vitest workspace monorepo

```typescript
export default defineWorkspace([
  "packages/ui/vitest.config.ts",
  "packages/api/vitest.config.ts",
]);
```

Per-package config shares setup while isolating environments.

## Accessibility regression

eslint-plugin-jsx-a11y in lint-staged plus RTL role queries — duplicate signal intentional for critical flows.
""")

add("timeseries-downsampling-retention", """
## Prometheus downsampling in Thanos

Thanos Compactor produces 5m and 1h downsampled blocks in object storage — query frontend selects resolution by time range automatically when configured.

## VictoriaMetrics retention tiers

Single-binary VM supports per-namespace retention flags — evaluate when avoiding full Mimir operational overhead.

## Billing alignment

Chargeback metrics storage cost by team label — teams adding high-cardinality labels see storage line item next quarter, natural governance.
""")

add("timeseries-influxdb-vs-timescale", """
## Write amplification

Compare write WAF on identical synthetic load in POC — Influx WAL vs Postgres WAL behave differently under burst ingest.

## Read replica lag

Timescale read replicas for analytics queries lag primary — dashboard "real-time" SLA must account lag or query primary with caution.

## Exit strategy

Export Parquet historical before vendor switch — both engines support bulk export paths; verify export job in POC checklist not just ingest/query.
""")

add("timeseries-prometheus-remote-write", """
## WAL corruption recovery

Prometheus local WAL still critical for recent data and alerting — remote write does not replace local HA pair for alert evaluation uptime.

## Mimir limits configuration

`-ingester.max-global-series-per-user` — tune with platform team before onboarding new tenants dumping high-cardinality debug metrics.

## Grafana Cloud remote write

Managed option reduces ops — evaluate data residency and egress cost vs self-hosted Mimir on same math as build vs buy.
""")

add("typescript-generics-constraints", """
## satisfies with generic factories

Factory function returning generic constrained type — combine satisfies on config object with generic inference on return.

## TypeScript 5 satisfies improvements

Stay current with release notes — satisfies interaction with generics evolves; rerun strict compile after TS major upgrade.

## Library export surface

Export constrained generics from library — consumers get inference without exposing internal constraint types in public API docs.
""")

add("typescript-satisfies-operator", """
## satisfies on array of unions

```typescript
const routes = [
  { path: "/home", component: Home },
  { path: "/about", component: About },
] as const satisfies ReadonlyArray<RouteConfig>;
```

Preserves order literal tuple type for exhaustive switch.

## Reject excess keys

satisfies triggers excess property check on fresh object literals — catch typos like `emial` field on user config.

## Migration from PropTypes

React PropTypes runtime checks replaced by satisfies on default props object in TS projects — zero runtime cost.
""")

add("typescript-strict-mode-migration", """
## strictPropertyInitialization on DI

Constructor injection satisfies definite assignment — prefer constructor params over field initializers in Nest/Angular services.

## Gradual @types strictness

`skipLibCheck true` during migration — revisit false after strict stable to catch bad DefinitelyTyped usage.

## Production error correlation

After strictNullChecks ship, track `Cannot read property of undefined` in Sentry — should drop measurably within one release cycle.
""")

add("typescript-utility-types-app-patterns", """
## Omit never pattern

```typescript
type RemoveIndex<T> = { [K in keyof T as string extends K ? never : K]: T[K] };
```

Strip string index signature before Pick — advanced pattern for API response cleanup.

## Satisfies plus utility combo

Define base User, derive DTOs with Omit/Pick, validate constants with satisfies on enum-like maps — layered type safety.

## OpenAPI diff on CI

Breaking API change detection on generated types — coordinate with Partial update DTO versioning strategy (`UpdateUserV2Input`).
""")
