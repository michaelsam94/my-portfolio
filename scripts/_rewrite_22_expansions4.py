# Fourth expansion — additional depth for posts still under 1200 words

EXPANSIONS4 = {}

def block(slug, *paragraphs):
    EXPANSIONS4[slug] = "\n\n" + "\n\n".join(paragraphs)

block("serverless-database-access-patterns",
    "## Lambda provisioned concurrency and DB spikes",
    "Provisioned concurrency eliminates cold starts for hot paths but does not reduce connection count — it can increase baseline connections if each warm instance holds one. Size Proxy for provisioned units plus burst concurrency headroom.",
    "## Transaction scope in handlers",
    "Keep transactions shorter than Lambda timeout margin — long transactions hold Proxy slots and block other invocations. Batch writes with UNNEST in single statement instead of loop of INSERTs inside one transaction spanning network calls to Stripe.",
)

block("shared-data-layer-room-kmp",
    "## Version skew between app and schema",
    "Ship database migration before app reading new columns — feature flags gate UI while old app versions still run; backward compatible migrations add nullable columns first, backfill, then enforce NOT NULL in later release.",
    "## Shared cache invalidation",
    "When server pushes config invalidation event, repository clears specific table or row keys — event schema in commonMain, platform push handler in androidMain/iosMain. Room `invalidate()` or targeted delete queries maintain consistency without full wipe.",
)

block("supply-chain-dependency-pinning",
    "## CI cache poisoning awareness",
    "Remote cache keys must include lockfile hash — otherwise restored node_modules from previous lock pollutes build. Nx and Turborepo document lockfile in cache key inputs explicitly.",
    "## Signed commits on lockfile changes",
    "Require signed commits or CODEOWNERS review on lockfile paths — attacker PR that bumps malicious transitive dependency caught by security team review rule.",
)

block("technical-writing-for-engineers",
    "## Slack to doc workflow",
    "Resolve recurring Slack questions by linking existing doc or creating FAQ entry same day — Slack is ephemeral, doc compounds. Bot command `/docsearch query` reduces duplicate answers.",
    "## Incident doc updates",
    "Postmortem action item 'update runbook section X' merged within one week or escalated — stale runbook erodes trust faster than missing doc.",
)

block("testing-compose-uis-v2",
    "## Lazy list test scroll",
    "Items not composed until scrolled — use `performScrollToIndex` on LazyColumn with testTag on list before asserting child. Failure 'node not found' often means not scrolled not missing UI.",
    "## Idling resource custom",
    "Register Espresso idling resource for Compose when legacy View interoperability or async image loading — `ComposeIdlingResource` bridges until idle.",
    "## Screenshot golden path",
    "Capture device-specific goldens in CI dedicated job — emulator API level pinned; macOS host goldens differ from Linux CI, pick one source of truth.",
)

block("testing-mutation-testing",
    "## Stryker ignore patterns",
    "Ignore strings, console.log, import statements — focus mutants on conditional logic and arithmetic. Config `mutator.excludedMutations` documents team policy.",
    "## Mutation vs coverage in Sonar",
    "SonarQube mutation plugin surfaces mutation score dashboard — leadership sees coverage and effectiveness together.",
)

block("testing-playwright-e2e",
    "## iframe and shadow DOM",
    "`page.frameLocator('#payment-iframe').getByRole('button')` — Playwright pierces shadow in many cases; document patterns for Stripe Elements iframe tests.",
    "## Rate limiting in E2E",
    "Throttle parallel workers against staging — 50 parallel logins may trigger WAF; match worker count to staging capacity documented in platform runbook.",
)

block("testing-property-based-testing",
    "## Link to formal methods",
    "Properties approximate algebraic laws — teams doing formal spec may extract properties as executable spec subset. Document property as 'law' in domain glossary.",
    "## Hypothesis profiles",
    "Define dev, ci, and thorough profiles in conftest — `@settings(profile='ci')` keeps PR fast, nightly uses thorough.",
    "## Seed replay",
    "`@reproduce_failure` decorator saves failing example — check into test file as regression when shrink finds subtle bug.",
)

block("testing-snapshot-testing-tradeoffs",
    "## Snapshot review in PR template",
    "Checkbox: 'I reviewed snapshot diff visually' required when snap files change — template enforces human glance.",
    "## Partial snapshot",
    "Snapshot only `<Alert message={...} />` fragment not full page layout — reduces noise while guarding component contract.",
)

block("testing-test-data-builders",
    "## Defaults reflect production constraints",
    "Default email valid format, default dates timezone-aware UTC — tests fail early if domain adds validation builders violate.",
    "## Composable scenarios",
    "`Scenario.newUser().withOrder().withRefund()` — scenario object composes builders for integration test narratives readable by PM.",
)

block("testing-test-doubles-mocks-stubs",
    "## Test pyramid per double type",
    "Document team preference: fake for repos, stub for APIs, mock for side effects only — architecture guild ratifies, reviewers enforce.",
    "## Static mock avoidance",
    "Mock static singletons last resort — wrap in instance interface injectable in tests; static mocks global state leak between tests.",
)

block("testing-unit-vs-integration-balance",
    "## Contract test ownership",
    "Consumer team publishes pact; provider verifies in CI — integration without full consumer deploy. Balance shifts integration left to boundary.",
    "## Local docker compose for dev",
    "docker-compose up postgres redis — developers run integration locally same as CI, reduces 'works on CI only' integration skips.",
)

block("testing-vitest-react-testing-library",
    "## act warnings",
    "Wrap state updates in `await act(async () => ...)` when testing hooks triggering async setState — Vitest logs act warnings failing CI if configured strict.",
    "## MSW handler override per test",
    "`server.use(http.get(...))` overrides default handlers — isolate error case test without separate server instance.",
)

block("timeseries-downsampling-retention",
    "## Anomaly detection on rollups",
    "Train anomaly models on hourly rollups even when alerts fire on 1m raw — reduces noise and compute; document alert evaluation resolution in alert annotation.",
    "## Cross-region retention",
    "EU metrics shorter raw retention for GDPR — label series with region, apply retention policy filter on ingest path.",
)

block("timeseries-influxdb-vs-timescale",
    "## Hybrid reference architecture",
    "Prometheus scrape → remote write Influx for ops metrics; Postgres/Timescale for business KPIs joined in Grafana with different datasources — accept two query languages if teams split.",
    "## Training plan",
    "Budget two-week learning path when adopting Flux or Timescale extensions — hidden cost in engine choice is upskilling not license.",
)

block("timeseries-prometheus-remote-write",
    "## Remote read legacy",
    "Remote read protocol deprecated in favor of unified query frontends — avoid building new remote read paths; plan Thanos/Mimir query instead.",
    "## exemplars and remote write",
    "Exemplars increase write volume — enable only on selected histograms; relabel drop exemplars on high-cardinality buckets if receiver struggles.",
)

block("typescript-generics-constraints",
    "## Generic type defaults in React props",
    "Component props generic with default `T = string` for uncontrolled input — inference works for common case, explicit generic for custom value types.",
    "## Lint @typescript-eslint/no-unnecessary-type-constraint",
    "Flag `T extends unknown` — remove noise constraints teaching bad habit.",
)

block("typescript-satisfies-operator",
    "## webpack DefinePlugin env",
    "Env vars object satisfies Record of allowed keys — typo in `process.env` mapping caught at compile when using satisfies on config module.",
    "## Internationalization keys",
    "Translation key map satisfies Record<MessageKey, string> — missing locale key compile error when merging new English keys.",
)

block("typescript-strict-mode-migration",
    "## eslint-disable escape hatch budget",
    "Track eslint-disable comments same as ts-expect-error — decreasing over time. No new disable without ticket.",
    "## lib.dom and strictNullChecks",
    "DOM APIs return nullable — wrap getElementById checks habit-forming; create `$` helper returning never throw element for app code.",
)

block("typescript-utility-types-app-patterns",
    "## DTO versioning",
    "V2 API: `CreateUserV2Input = Omit<UserV2, ...>` — version suffix on types prevents mixing v1/v2 handlers in same router file without compile error.",
    "## Readonly deep",
    "External config `Readonly<Config>` or deep readonly utility — prevent mutation of shared constants imported across modules.",
)

# Extra bulk paragraphs for shortest posts
SHORTFALL = {
    "testing-property-based-testing": [
        "## Worked example: sorting property",
        "Property: sorted array length equals input length; output is ordered; output is permutation of input (every element appears same count). Three properties together stronger than one `assert sorted(arr)`.",
        "## Worked example: URL parser",
        "Generate random strings, parse as URL when possible, property: scheme lowercase after normalize; host non-empty when absolute URL. Invalid inputs filtered with assume valid URL from generator.",
        "## CI integration pytest",
        "Add `--hypothesis-profile=ci` to pytest.ini in pipeline; developers run default profile locally with more examples. Document in CONTRIBUTING testing section.",
    ],
    "testing-test-data-builders": [
        "## Anti-corruption for external APIs",
        "StripeWebhookBuilder produces JSON matching Stripe fixture format — tests webhook handler without hitting Stripe sandbox for every case.",
        "## Builder discovery",
        "IDE live template `builder` expands to new Builder class skeleton — consistency across team faster than copying unrelated builder.",
    ],
    "testing-compose-uis-v2": [
        "## Multi-module Compose",
        "Feature modules export composable screens with testTag contract documented — app module integration test navigates via tags stable across refactors inside feature module.",
        "## Robolectric limitations",
        "Some Material3 components differ Robolectric vs device — mark tests `@RequiresDevice` for nightly instrumented when Robolectric gap found.",
    ],
}

for slug, paras in SHORTFALL.items():
    EXPANSIONS4[slug] = EXPANSIONS4.get(slug, "") + "\n\n" + "\n\n".join(paras)
