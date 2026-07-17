# Second expansion pass — ensure all posts >= 1200 words

EXPANSIONS2 = {}

def _pad(slug, sections):
    EXPANSIONS2[slug] = "\n\n" + "\n\n".join(sections)

_pad("seo-javascript-rendering-crawl", [
    "## Vendor script impact on rendering",
    "Third-party tags (A/B testing, chat widgets, consent managers) execute in Googlebot's render pass. Delay non-critical scripts with `async`/`defer` and load after LCP element paints. Tag managers firing synchronous pixels block render queue completion — measure with WebPageTest filmstrip on Googlebot user-agent emulation.",
    "## Bing and secondary engines",
    "Bing crawls JavaScript with its own renderer — do not optimize exclusively for Google. SSR benefits all engines and social scrapers (Slack, LinkedIn) that do not execute JavaScript. Open Graph tags must appear in initial HTML for link previews.",
    "## Release checklist",
    "Before shipping CSR-only changes to indexable templates: run Screaming Frog in JavaScript rendering mode, export non-200 and thin-content URLs, compare to server-rendered baseline diff. Block release if indexed URL count drops in staging Search Console property mirror.",
])

_pad("seo-meta-robots-noindex-patterns", [
    "## Search Console validation",
    "After applying noindex to URL class, use URL Inspection live test — confirm 'Indexing allowed? No: noindex detected.' Monitor 'Excluded by noindex' count rising for target URLs while indexed count falls over two crawl cycles.",
    "## A/B test pages",
    "Experiment variants should noindex or canonical to control — duplicate experiment URLs pollute index. Optimize experimentation platform config to inject meta on variant URLs automatically.",
    "## WordPress and CMS defaults",
    "Many CMS plugins add site-wide noindex on 'discourage search engines' checkbox — verify production checkbox off after clone from staging DB. Automated DB migration scripts sometimes copy `blog_public=0` option silently.",
])

_pad("serverless-database-access-patterns", [
    "## Azure Functions and SQL",
    "Azure SQL with connection pooling enabled on server side; Functions still benefit from limiting concurrent connections via `MaxConcurrentCalls` and using `SqlConnection` reuse pattern identical to Lambda.",
    "## Cloudflare Workers and D1",
    "Workers accessing D1 SQLite edge database — different model: no TCP connection pool to regional Postgres; understand D1 consistency limits for global apps.",
    "## Runbook template",
    "Document: max Lambda concurrency, Proxy max connections percent, RDS max_connections, alert thresholds, rollback via reserved concurrency cap, contact for DBA slot release during incident.",
])

_pad("shared-data-layer-room-kmp", [
    "## Schema export in CI",
    "Room schema JSON diff in PR — fail if migration missing for entity change. Same pattern as Flyway for server databases.",
    "## Binary compatibility",
    "Shared module versioned independently — semver bump when migration required; apps pin shared version and run migration on upgrade.",
    "## DataStore coexistence",
    "Some teams keep preferences in DataStore and entities in Room — clear boundary: structured query data Room, key-value prefs DataStore, never duplicate same data both places.",
])

_pad("supply-chain-dependency-pinning", [
    "## SBOM in incident response",
    "When CVE-XXXX announced, query SBOM for package presence across services in minutes. Unpinned installs require regenerating lock from prod node_modules under fire — unacceptable delay.",
    "## npm overrides field",
    "Emergency transitive patch via package.json `overrides` — document temporary override with expiry ticket; merge upstream fix when maintainers publish.",
    "## Training",
    "Onboard engineers: never commit without lockfile change when package.json changes; CI enforces with `npm ci` failure on mismatch.",
])

_pad("technical-writing-for-engineers", [
    "## Diagram standards",
    "One diagram per ADR: boxes named with services not people, arrows labeled with protocol (HTTPS, gRPC, Kafka). Update diagram in same PR as code change or file ticket — stale diagrams worse than none.",
    "## Versioning docs with API",
    "Deprecated endpoint: strikethrough in docs, sunset date header, migration code sample. Remove docs after sunset — not before.",
    "## Feedback widget",
    "'Was this helpful?' on doc pages — low scores trigger triage queue for tech writer pairing.",
])

_pad("testing-compose-uis-v2", [
    "## Tablet and foldable",
    "Window size class changes layout — test with `composeRule.setContent` and manual configuration qualifiers or `createAndroidComposeRule` on tablet AVD in nightly job.",
    "## Locale testing",
    "`composeRule.setContent` with `CompositionLocalProvider(LocalConfiguration provides Configuration(locale=Locale(\"ar\")))` — verify RTL layout in semantics assertions.",
    "## Performance",
    "Avoid `onAllNodes` huge trees in loop — query specific tags. Large semantics scans slow instrumented suite.",
])

_pad("testing-mutation-testing", [
    "## Management metrics",
    "Report mutation score trend quarterly to engineering leadership alongside escaped defect rate — justify CI CPU investment.",
    "## Scope creep",
    "Do not mutation-test generated protobuf getters — configure exclusions explicitly or noise drowns signal.",
    "## Developer UX",
    "Local `stryker run` on single file before PR — catches weak tests before CI 20-minute mutation job.",
])

_pad("testing-playwright-e2e", [
    "## flake detection",
    "Track test pass rate per spec over 30 runs — quarantine specs below 95% pass rate.",
    "## Environment variables",
    "`.env.e2e` in repo with dummy values; secrets from CI vault at runtime. Document required vars in README E2E section.",
    "## Accessibility in E2E",
    " `@axe-core/playwright` scan on critical pages after functional flow passes — catch regressions unit tests miss.",
])

_pad("testing-property-based-testing", [
    "## Shrinking debug",
    "Hypothesis `verbosity=Verbosity.verbose` locally when counterexample confusing — prints shrink steps.",
    "## Domain constraints",
    "Use `assume()` sparingly — too many rejects cause Hypothesis health check failure; narrow strategy instead.",
    "## Pair with example tests",
    "Property finds bug — add minimal example regression named after ticket ID forever.",
])

_pad("testing-snapshot-testing-tradeoffs", [
    "## Platform-specific snapshots",
    "iOS vs Android snapshot dirs differ — do not share snap files cross-platform.",
    "## CI diff review",
    "Require second reviewer when snapshot-only PR exceeds 100 lines changed.",
    "## Storybook interaction tests",
    "Storybook 8 test runner captures component states — alternative to manual snapshot of every story file.",
])

_pad("testing-test-data-builders", [
    "## Immutability",
    "Builder returns new object each build — no shared mutable default object across tests causing order dependence.",
    "## Cross-language builders",
    "Same persona names in Kotlin and TypeScript test factories for microservice system — 'AdminAlice' means same auth claims everywhere.",
    "## Property-based + builders",
    "Generate random valid builder output as input to property — combines structured domain with generative fuzz.",
])

_pad("testing-test-doubles-mocks-stubs", [
    "## HttpClient fake",
    "OkHttp MockWebServer or MSW — stub HTTP without mocking your wrapper class — tests real serialization path.",
    "## Verify interaction sparingly",
    "One mock expectation per test — multiple verifies brittle; split tests.",
    "## Legacy code seams",
    "Extract interface at boundary before introducing fake — characterization test first if refactoring risky.",
])

_pad("testing-unit-vs-integration-balance", [
    "## Microservice test pyramid",
    "Each service: unit domain, integration repo, contract provider test, one smoke E2E through gateway — not full journey every service.",
    "## Database migration test",
    "Flyway migrate on empty + seed integration test — catches broken migration SQL unit tests never see.",
    "## Delete tests",
    "Remove tests that mock everything and assert nothing — net negative maintenance.",
])

_pad("testing-vitest-react-testing-library", [
    "## happy-dom vs jsdom",
    "Vitest supports happy-dom — faster, some API gaps; pick one per project consistently.",
    "## Testing error boundaries",
    "Mock console.error, trigger throw, assert fallback UI — error boundaries silent in tests without setup.",
    "## Strict mode double render",
    "React 18 Strict Mode double-invokes effects in dev — tests using effect counters may need adjustment; use RTL patterns not effect counts.",
])

_pad("timeseries-downsampling-retention", [
    "## SLO calculations",
    "Error budget burn queries use 30d rollups — align rollup granularity with SLO window to avoid math mismatch.",
    "## Replay ingest",
    "Historical backfill at coarse resolution after policy change — batch job from warehouse export, not re-scrape.",
    "## GDPR deletion",
    "Retention drop must support per-user series deletion in multi-tenant metrics — design labels knowing erasure requirements.",
])

_pad("timeseries-influxdb-vs-timescale", [
    "## Team skill assessment",
    "Score team 1–5 on SQL vs Flux fluency — honest score drives recommendation more than benchmark charts.",
    "## POC criteria",
    "POC must include: ingest sustained RPS, query p95 at 7d and 90d range, backup restore drill, cost projection at 12 months.",
    "## Observability correlation",
    "Join traces to metrics — Tempo/Jaeger trace_id label in Prometheus regardless of backend choice.",
])

_pad("timeseries-prometheus-remote-write", [
    "## Multi-region",
    "Remote write to region-local Mimir — query federation across regions for global dashboards; understand replication lag.",
    "## Terraform modules",
    "Pin Mimir/Thanos module versions — infrastructure drift breaks remote write auth silently.",
    "## Testing receiver",
    "Load test receiver with `promtool` recording rules output replay before production cutover.",
])

_pad("typescript-generics-constraints", [
    "## Type predicate generics",
    "```typescript\nfunction isArray<T>(value: T | T[]): value is T[] {\n  return Array.isArray(value);\n}\n```",
    "Predicates narrow union with constraints on type parameter.",
    "## Generic hooks",
    "React `useLocalStorage<T extends string | number>` — constrain storable JSON types.",
    "## Review checklist",
    "PR review: any new generic function accessing property without extends gets comment.",
])

_pad("typescript-satisfies-operator", [
    "## Theme design tokens",
    "Design system colors as const object satisfies Record<TokenName, `#${string}`> — design QA and type QA aligned.",
    "## API route config",
    "Next.js route segment config object satisfies expected shape — catch typo in `dynamic` value union.",
    "## Pair with zod",
    "Runtime parse then satisfies static type on exported constant — belt and suspenders for config files.",
])

_pad("typescript-strict-mode-migration", [
    "## Editor strict by default",
    "VS Code workspace tsconfig strict for new folders — template repo starts strict day zero.",
    "## Metrics dashboard",
    "Track `@ts-expect-error` count, `any` usage count via eslint rule over time — visualize migration progress.",
    "## Celebrate milestones",
    "Enable strictNullChecks party when error zero — cultural reinforcement beats mandate memo.",
])

_pad("typescript-utility-types-app-patterns", [
    "## OpenAPI codegen alignment",
    "Generated types from OpenAPI — wrap with Pick/Omit for internal DTOs rather than editing generated files.",
    "## Prisma model helpers",
    "`Prisma.UserGetPayload<{ select: { id: true, email: true } }>` overlaps with Pick — choose one style per codebase.",
    "## Document naming convention",
    "Suffix: `UserEntity` DB, `User` domain, `UserDto` API, `CreateUserInput` writes — utilities map between layers in typed functions.",
])
