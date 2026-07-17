# Sixth expansion — targeted for remaining sub-1200 posts

EXPANSIONS6 = {}

def pad(slug, content):
    EXPANSIONS6[slug] = "\n\n" + content.strip()

pad("supply-chain-dependency-pinning", """
## Language-specific lockfile gotchas

Ruby Bundler `Gemfile.lock` must commit; Bundler 2+ different resolution than Bundler 1 — pin Bundler version in CI image. Python `requirements.txt` without hashes is not pinned — use pip-tools or poetry lock. Elixir mix.lock committed. Swift Package.resolved for apps. Consistency across polyglot monorepo means one CI job per ecosystem verifying lock integrity, not one generic install script.

## Air-gapped environments

Offline registries mirror pinned tarballs — export lockfile-resolved packages to internal mirror quarterly. Builds in classified networks cannot phone npmjs.org; pin plus mirror is only path. Document mirror sync procedure in platform runbook with checksum verification identically to public registry integrity fields.

## Pre-commit hooks

```yaml
# .pre-commit-config.yaml hook runs npm ci --dry-run or equivalent
# rejects commit when package.json changed without lockfile
```

Automate discipline developers forget in hurry — hook message explains how to fix not just fails opaque.
""")

pad("testing-compose-uis-v2", """
## Accessibility merge semantics tests

When multiple children merge contentDescription, test merged value matches design spec — regression breaks TalkBack and test using merged semantics. Compose UI Test `onNodeWithContentDescription` matches merged tree; verify not child internal tag.

## waitUntil pattern catalog

| Condition | waitUntil predicate |
|-----------|---------------------|
| Async load | node count > 0 |
| Error banner | text exists |
| Navigation | tag exists |

Centralize helpers `waitForTag(tag)` extension on ComposeTestRule reducing copy-paste wait loops with magic timeouts.

## Integration with CI caching

Gradle configuration cache plus test cache — changing testTag in composable invalidates only affected test class cache. Keep testTag strings stable across refactors when behavior unchanged to preserve cache hit rate.
""")

pad("testing-mutation-testing", """
## Surviving mutants review meeting

Weekly 30-minute review of new survivors with author of original test — pedagogical not punitive. Survivor demonstrates missing assertion or equivalent mutant to exclude. Meeting notes feed testing guild guidelines document updated quarterly.

## Mutation on generated code policy

OpenAPI generated clients excluded — mutants on generated getters meaningless. Hand-written adapter layer on generated client included — business logic adapting API to domain is mutation target. Clear glob list in stryker.config.json checked into repo CODEOWNERS qa team.

## Cost cap

Set max mutants per CI run — Stryker `reporters` dashboard tracks cost trend; if CI bill exceeds threshold, reduce scope not disable entirely. Finance accepts mutation CI cost when tied to reduced incident count metric presented quarterly.
""")

pad("testing-playwright-e2e", """
## Storage state rotation

Rotate E2E user passwords monthly — storage state files in repo encrypted or regenerated in CI setup job not committed with long-lived tokens. Security audit flags committed JWT in `.auth/user.json` — generate fresh each pipeline run.

## Debugging CI-only failures

Download trace artifact; compare viewport and timezone CI uses versus local — date picker tests fail UTC vs local midnight. Set `timezoneId: 'America/New_York'` in playwright config explicitly documenting team standard.

## Component vs E2E ownership

Product bug in button label — component test or unit catches faster; E2E only for journey. Overlap intentional at smoke level only — duplicate coverage acceptable for top three revenue paths not entire suite.
""")

pad("testing-property-based-testing", """
## Law: associativity example

For merge function merging configs: `merge(a, merge(b,c)) equals merge(merge(a,b), c)` — property with three generated configs. Violation finds edge case order-dependent defaults in nested config merge production bug class.

## Generator composition

`st.lists(st.integers(), min_size=1, max_size=100)` combined with `st.sampled_from(['add','remove'])` for operation sequences — build complex generators from simple ones documented in team property catalog.

## Regression from production bug

Every production bug fix from missing edge case adds property when invariant articulable — else example test. Postmortem action item type: PROPERTY or EXAMPLE tagged in ticket for QA tracking adoption metric.
""")

pad("testing-snapshot-testing-tradeoffs", """
## Snapshot in monorepo packages

Package A snapshots should not import Package B unstable markup — snapshot isolation per package boundary. Turborepo `--filter=package` test task runs snapshot verify per changed package keeping CI fast.

## Accessibility snapshot alternative

Instead of HTML snapshot, assert accessibility tree string normalized — closer to assistive tech output without pixel brittleness. Experimental but useful for design system alert components.

## Reviewer training

Ten-minute guild session: how to read snapshot diff, when approve vs reject, when ask for explicit assertion instead — reduces blind approve culture more than policy memo.
""")

pad("testing-test-data-builders", """
## Builder and property-based combo

`@given(st.data())` draw builder with random overrides on optional fields — combines structured validity with exploratory fuzz. Hypothesis `data()` strategy calls builder methods randomly per documented API.

## Immutable builds

Builder `build()` returns frozen object `Object.freeze` in JS tests — catch tests accidentally mutating shared fixture polluting downstream tests. Kotlin `copy()` data class from builder output new instance each time.

## Naming collision avoidance

Prefix builder personas with role not real names — `AdminUserBuilder` not `JohnBuilder` — reduces confusion and insensitive naming in test logs.
""")

pad("testing-test-doubles-mocks-stubs", """
## Document double choice in test file header

Comment block: `// Uses FakeWalletRepo — real SQL behavior, no mock` — future maintainer understands why Mockito absent. Three-line comment prevents mock reintroduction without thought.

## Integration test with Testcontainers

Testcontainers is real dependency not double — sits above integration layer. Naming clarity: double means in-memory substitute; container means real process different category in test strategy doc.

## Mock verification order

Assert state outcome first, interaction second — if outcome wrong, fail fast before brittle verify call count debugging wild goose chase.
""")

pad("testing-unit-vs-integration-balance", """
## Service level objectives for tests

Target: P95 CI unit job under 3 minutes, integration under 12, E2E nightly under 45 — adjust test counts when SLO breached not arbitrary ratio target. Tests are production system consuming CI resources deserving SLO monitoring.

## Feature flag testing

Unit test flag logic; integration test flag service wiring returns correct variant; E2E optional single path with flag on — layered coverage matches flag risk not all E2E permutations.

## Delete integration test when unit plus contract sufficient

Quarterly audit: integration test runtime >30s mocking nothing — ask can contract test replace. Prune suite growth preventing CI SLO death spiral.
""")

pad("testing-vitest-react-testing-library", """
## Colocated tests

`Button.tsx` adjacent `Button.test.tsx` — import path short, discoverability high. Barrel exports do not re-export tests — keep test imports direct.

## Fake timers with userEvent

`vi.useFakeTimers()` conflicts userEvent real timers — use `@testing-library/user-event` v14+ `advanceTimers` option or real timers for debounce tests. Document project standard in testing README avoiding each developer rediscovering conflict.

## Coverage thresholds per directory

`src/lib/` 90% unit coverage gate; `src/components/` 75% — Vitest coverage config `thresholds` per glob. Integration tests in `*.integration.test.tsx` excluded from unit threshold counted separately.
""")

pad("timeseries-downsampling-retention", """
## Observability of retention jobs

Metric `retention_chunks_dropped_total` incremented when chunk deleted — alert if zero unexpectedly long indicating job stuck. Dashboard panel retention bytes freed per day validating policy effect not just configured.

## User-facing query latency SLI

Track p95 query latency for 7d range on hourly rollup vs 24h range on raw — validate routing logic picks correct tier. Regression when routing broken shows raw table scan timeout on large range.

## Legal discovery hold implementation

Tag series with hold flag in label or metadata table — retention job SQL `WHERE NOT legal_hold` — legal team process to attach hold case number ticket linking metric series IDs affected.
""")

pad("timeseries-influxdb-vs-timescale", """
## Grafana dashboard portability

Dashboard JSON uses datasource UID — migrating engines update UID and query language in same migration PR. Maintain dashboard version note in README which engine validated.

## Developer local setup friction

Docker compose Influx vs Timescale Postgres — measure minutes to first query in onboarding doc honest comparison. Timescale wins teams already running Postgres locally; Influx wins greenfield metrics-only side project.

## Support contract evaluation

Enterprise support SLAs compared when POC narrows to two finalists — ops team input weighted equal to query benchmark numbers in vendor selection scorecard.
""")

pad("timeseries-prometheus-remote-write", """
## Capacity planning receive path

Calculate samples per second from scrape configs times series count — compare to receiver documented ingest limit with 50% headroom. Load test at 150% expected peak before holiday traffic.

## Multi-tenant isolation

Separate remote write URLs or headers per tenant — blast radius containment when one tenant cardinality explosion threatens shared receive. Platform chargeback per tenant ingest rate.

## Upgrade coordination

Prometheus upgrade plus Mimir upgrade compatibility matrix checked before either bump — remote write protocol version assumptions documented in joint upgrade runbook single page both teams sign off.
""")

pad("typescript-generics-constraints", """
## Anti-pattern catalog

`function bad<T>(x: T) { return (x as any).foo }` — fix with constraint not deeper cast. Code review bot comment template links internal generics guide section.

## Generic defaults documentation

TSDoc `@typeParam T - entity with id field` on generic function — IDE hover teaches junior engineers constraint meaning without opening guide.

## Performance testing generics

Generics erase — no runtime cost difference; do not avoid generics for micro-performance imaginary gains in hot path without profiling proof.
""")

pad("typescript-satisfies-operator", """
## IDE experience

satisfies preserves literal autocomplete in VS Code — demo in onboarding showing `theme.primary` autocompletes `'red' | 'blue'` not string. Developer experience argument converts skeptics faster than type theory lecture.

## Breaking change detection

When Theme union adds color, satisfies on theme object errors compile — migration guide for design system documents new token addition checklist includes updating satisfies objects in codebase grep.

## Combined with const assertion on arrays

Tuple satisfies for route table preserves order for priority routing matching — type system encodes business rule route order matters not just set of routes.
""")

pad("typescript-strict-mode-migration", """
## Executive summary one-pager

Non-technical summary for leadership: strict mode reduces production undefined errors, migration incremental, no customer-facing downtime — requested budget one sprint per quarter. Links error Sentry trend chart before after strictNullChecks on pilot service.

## Pairing strict with runtime validation

Zod at boundary plus strict internal types — external unknown parsed once, internal strict types thereafter. Migration order: Zod boundaries first or strict first debated — document team choice either valid if consistent.

## Celebrate zero ts-expect-error sprint

When count hits zero, team ritual — small milestone recognition. Morale on migration long march matters for retention engineers doing tedious null fixes.
""")

pad("typescript-utility-types-app-patterns", """
## Codegen alignment workshop

Hour session mapping OpenAPI schema types to Pick Omit DTO layers live — team leaves with shared naming convention document. Reduces PR review debate CreateUserInput vs UserCreateDto naming drift.

## Utility type readability rule

If Pick Omit chain exceeds two operations, extract named type alias — lint rule custom optional `max-utility-chain-depth` in ESLint custom rule or review checklist item.

## Deprecation typing

`@deprecated` JSDoc on UserV1 types while UserV2 derived from new entity — compiler warnings on usage drive migration visible in IDE not only docs.
""")
