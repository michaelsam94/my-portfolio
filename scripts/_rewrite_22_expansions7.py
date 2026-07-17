# Seventh expansion — final word count push (250+ words each)

EXPANSIONS7 = {}

def add(slug, text):
    EXPANSIONS7[slug] = "\n\n" + text.strip()

add("testing-compose-uis-v2", """
## Gradle test task splitting

Separate `connectedDebugAndroidTest` for Compose UI from unit tests — developers run `./gradlew :app:testDebugUnitTest` locally fast, CI runs instrumented on merge queue. Document in ANDROID.md which tests require emulator so contributors do not assume CI failure local reproduction without device.

## Compose Multiplatform UI tests

Compose Multiplatform experimental UI testing shares semantics patterns with Android — testTag and role queries apply on desktop target in commonTest reducing platform-specific test duplication for KMP UI teams.

## Failure artifact collection

On CI failure, pull Compose test report XML and screenshot if configured — attach to GitHub Actions summary for designer review of UI regression without local reproduce. `captureToImage` on failure hook in test rule custom implementation optional advanced pattern.
""")

add("testing-mutation-testing", """
## Java record types and PIT

Records compact data carriers — mutation on accessor logic still valuable; exclude generated equals/hashCode if no custom logic. Focus PIT on methods containing conditionals in record compact constructor validation block.

## Reporting survivor age

Track days since survivor first detected — survivor older than 90 days escalates to tech lead for test addition or equivalent mutant exclusion documented. Prevents survivor backlog infinite growth muting mutation gate effectiveness.
""")

add("testing-playwright-e2e", """
## Biometric and WebAuthn staging

WebAuthn E2E uses virtual authenticator Playwright API — configure before navigation to register flow. Document credential cleanup after test deletes virtual user from auth provider admin API preventing staging user accumulation.

## Soft launch feature flags

E2E runs against staging with flag service pointing test cohort — `E2E_FLAG_OVERRIDES` env JSON sets flags before test session. Avoid testing production flag state accidentally by asserting flag service health in global setup.
""")

add("testing-property-based-testing", """
## Cross-language property parity

Service in Go with property in native test; consumer in TypeScript repeats key property on client parser — same law different language duplicated intentionally for polyglot systems. Shared JSON examples of minimal failing cases in repo `properties/` directory document cross-team.

## Performance guard

Property test exceeding 5 seconds fails CI — `@settings(deadline=5000)` forces efficient generators; slow property indicates generator too broad or property doing heavy work should move integration tier.
""")

add("testing-snapshot-testing-tradeoffs", """
## Contract snapshot for CLI output

CLI `--format json` output snapshot stable schema — breaking CLI change intentional major version. Snapshot includes version field; test asserts version unchanged or bumped with migration note in CHANGELOG required in same PR.

## Snapshot lint

Custom ESLint rule ban `toMatchSnapshot` in `*.integration.test.tsx` — integration tests must use behavioral assertions; snapshots allowed only unit component tests rule enforces team policy automatically in review.
""")

add("testing-test-data-builders", """
## Audit builder defaults quarterly

Review default persona passwords and emails not resembling production PII — compliance scan flags realistic email in test fixtures. Use `@example.com` reserved domain and obvious fake names.

## Builder telemetry

Optional debug log builder persona name in test failure message — `assert failed for AdminWithExpiredTrial builder` speeds debugging which fixture scenario broke without reading entire test file stack trace.
""")

add("testing-test-doubles-mocks-stubs", """
## Async mock patterns

`mockResolvedValueOnce` chain for retry tests documents expected call sequence in order — readable intent. Avoid `mockImplementation` switching on call count magic numbers unless comment explains state machine.

## Cleanup mock registry

Vitest `vi.clearAllMocks()` in afterEach — global config `clearMocks: true` prevents leaked mock state between tests causing order-dependent failures hard to reproduce in isolated run.
""")

add("testing-unit-vs-integration-balance", """
## Monolith extraction metrics

During extraction track ratio integration tests in monolith module decreasing as microservice contract tests increase — graph in eng review shows progress strangler fig. Target integration count in monolith zero before decommission milestone.

## Test impact analysis

Tooling maps changed production files to test files — PR runs affected tests subset for speed full suite nightly. Balance fast feedback with coverage confidence using impact analysis not blind unit-only PR gate.
""")

add("testing-vitest-react-testing-library", """
## Testing suspense boundaries

Wrap async component in Suspense with fallback in test helper — assert fallback then resolved content with findBy. React 19 streaming patterns require async test patterns documented in internal wiki linked from test setup.ts comment.

## Visual debug on failure

`screen.logTestingPlaygroundURL()` prints URL to Testing Playground — paste in browser for interactive query debugging teaching junior engineers RTL query priority without senior pairing every failure.
""")

add("timeseries-downsampling-retention", """
## Customer-facing status pages

Public status page historical uptime calculated from downsampled availability metrics — align aggregation window with SLA reporting window documented in customer contract legal review. Raw metric disagreement with customer report erodes trust.

## Migration communication

Before shortening retention notify analytics team six weeks — dashboard broken queries schedule migration to rollup datasource Grafana variable update included in same change window reducing surprise broken executive dashboard Monday morning.
""")

add("timeseries-influxdb-vs-timescale", """
## Edge write reliability

IoT devices buffer offline metrics flush on reconnect — Influx line protocol over UDP lossy; TCP with ack or HTTP POST preferred evaluating engine ingest protocol fit for edge not just datacenter scraper pattern.

## Finance forecasting

Include training cost for DBAs unfamiliar with chosen engine in year one TCO spreadsheet — Timescale leverages existing Postgres DBA; Influx may require hire or consultant line item explicit in budget proposal comparison deck.
""")

add("timeseries-prometheus-remote-write", """
## Disaster recovery drill

Quarterly simulate receiver region loss — failover remote write URL to secondary region verify Prometheus queue drains and Grafana queries continue with RPO/RTO measured. Document gap duration acceptable leadership sign-off.

## Cost anomaly detection

Alert on ingest bytes per hour 3 sigma above weekly seasonality — cardinality explosion or misconfigured relabel loop duplicate writes detected before invoice surprise finance questions platform team.
""")

add("typescript-generics-constraints", """
## Open source library API design

Public library functions use minimal necessary constraints — over-constraining limits consumer generic inference frustration. Document extension points with examples unconstrained wrapper if advanced users need wider types.

## Refactor from any migration

Track file count using explicit any in generic functions during strict migration — burn down chart in eng standup correlates with generics constraint adoption replacing any escape hatches systematically not randomly.
""")

add("typescript-satisfies-operator", """
## Strict excess property checks

satisfies triggers excess property check on object literal — typo key `emial` errors immediately saving runtime debug. Pair with ESLint no misspelled property names plugin double layer defense config objects.

## Library consumer experience

Exported config examples in README use satisfies in snippet — copy paste into consumer project compiles teaching pattern. Documentation examples that do not compile undermine trust technical content marketing blog posts included.
""")

add("typescript-strict-mode-migration", """
## Vendor type strictness

Third-party `@types` packages may be loose — wrap in typed facade module strict internal interface hiding loose vendor types. Facade migration incremental isolates strict work from blocking on upstream DefinitelyTyped PR merge timeline uncertainty.

## Regression prevention

New file template in IDE includes strict compatible patterns — no implicit any parameter, nullable checked — templates encode standards better than wiki page nobody reads after onboarding week one.
""")

add("typescript-utility-types-app-patterns", """
## Runtime validation alignment

When Zod schema infers User, derive CreateUserInput as z.infer<typeof CreateUserSchema> not manual Omit — single source truth schema drives both runtime and compile time. Utility types complement not duplicate schema inference pattern modern TS API codebase standard.

## GraphQL codegen Pick

Generated GraphQL types verbose — Pick for component props selecting subset query returns reducing prop drilling types without manual duplicate interface drifting from query selection set when query adds field compile errors component props update reminder.
""")
