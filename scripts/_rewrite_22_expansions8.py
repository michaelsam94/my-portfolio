# Eighth expansion — last mile to 1200 words (concise closing sections)

EXPANSIONS8 = {}

def e(slug, text):
    EXPANSIONS8[slug] = "\n\n" + text.strip()

e("testing-mutation-testing", """
## Operational summary

Roll out mutation testing where incorrect logic has direct financial or security impact. Keep a documented exclusion list for generated and boilerplate code so CI time stays predictable. Review surviving mutants weekly; either add a targeted test or record an equivalent-mutant justification. Mutation score should rise or hold steady — a drop after a refactor is a signal to strengthen assertions before merge, not noise to ignore.
""")

e("testing-playwright-e2e", """
## Operational summary

Cap the E2E suite at critical journeys: authentication, purchase or signup, and one admin path if applicable. Every spec should declare which production risk it mitigates in the PR description. Prefer API seeding over UI setup steps. Run Chromium on PRs; schedule Firefox and WebKit nightly. Attach traces on failure and delete specs that duplicate stable lower-layer tests unless they guard a known regression that only reproduces in a real browser.
""")

e("testing-property-based-testing", """
## Operational summary

Maintain a short catalog of properties beside your domain module: name, invariant, generator notes. Add one property when a production bug reveals a missing law, not only an missing example. Keep CI example counts modest; reserve large runs for nightly jobs. When Hypothesis shrinks a failure, commit the minimal case as a regression example so the next developer understands the bug without re-running thousands of iterations locally.
""")

e("testing-snapshot-testing-tradeoffs", """
## Operational summary

Treat snapshots as contracts on stable output — serializers, CLI text, email HTML — not as a substitute for behavior tests on interactive UI. Reject PRs that update snapshots without a plain-language explanation of what changed and why it is correct. If a snapshot file grows beyond roughly fifty lines, split it or replace it with explicit assertions. Monthly snapshot count reviews prevent slow accumulation of unreviewed golden files that train teams to click approve without reading diffs.
""")

e("testing-test-data-builders", """
## Operational summary

Centralize defaults for each aggregate root and name recurring personas in object mothers referenced by QA and support docs. Use unique identifiers in parallel CI. Validate at `build()` time with the same schema or constructor rules production uses. When validation rules change, update builders in the same PR as production code so tests never construct illegal objects that pass in CI but fail in staging with confusing error messages unrelated to the feature under test.
""")

e("testing-test-doubles-mocks-stubs", """
## Operational summary

Publish a one-page team guide: fakes for repositories, stubs for HTTP, mocks for irreversible side effects. Flag tests that mock more than two collaborators — often a design smell worth refactoring before adding another mock. Clean mocks between tests. Prefer hand-written fakes when behavior is simple; generated mocks when verifying interaction with a heavy external SDK is the point. Doubles should clarify boundaries, not hide missing integration coverage on wiring that only breaks in production.
""")

e("testing-unit-vs-integration-balance", """
## Operational summary

Tag escaped production bugs with the test layer that would have caught them if it existed. Adjust investment toward the layer with the highest escape rate, not toward an abstract pyramid ratio. Set CI duration SLOs per layer and prune tests that duplicate coverage without adding signal. Integration tests on real PostgreSQL via Testcontainers catch migration and SQL bugs unit tests with mocked JDBC cannot. Revisit balance after major architecture changes such as monolith extraction or auth redesign.
""")

e("testing-vitest-react-testing-library", """
## Operational summary

Standardize Vitest setup with MSW lifecycle hooks and `@testing-library/jest-dom`. Enforce `userEvent` over `fireEvent` for new tests. Keep component CI under a few minutes by sharding large packages. Test behavior users see — roles, labels, alerts — not component state or private hooks. Pair a fast Vitest suite with a handful of Playwright smokes for routing and auth integration; do not re-implement entire journeys in both layers unless a past incident proved browser-specific failure modes require it.
""")

e("timeseries-downsampling-retention", """
## Operational summary

Publish retention tiers with estimated storage bytes and owners in the observability runbook. Alert when retention jobs stop dropping chunks or disk growth exceeds forecast. Route long-range dashboard queries to rollups automatically; raw tables are for recent incident debugging only. Coordinate retention shortening with analytics and finance stakeholders six weeks ahead so executive dashboards migrate to rollup datasources before raw data disappears. Legal hold labels must exclude affected series from deletion jobs with an audit trail tied to case tickets.
""")

e("timeseries-influxdb-vs-timescale", """
## Operational summary

Choose based on who writes queries and what ops model you already run. SQL teams with Postgres expertise usually ship faster on Timescale; metrics-only greenfield pipelines with line-protocol ingest often start simpler on Influx. Run a POC with production-like cardinality and your real query authors, not only synthetic load scripts. Document export paths and training time in the same ADR as the selection. Revisit the decision after twelve to eighteen months of production cardinality and cost data — POC assumptions rarely match Black Friday reality.
""")

e("timeseries-prometheus-remote-write", """
## Operational summary

Alert on remote-write queue lag and failed samples before drops occur. Size receivers for peak ingest with headroom, not daily averages. Drop high-cardinality noise with relabel rules before bytes leave Prometheus. Quarterly failover drills measure RPO when a region is lost. Grafana dashboards used in incidents should document whether they query local Prometheus, remote long-term storage, or both — mixed sources without deduplication confuse triage when series appear duplicated or gaps after outages are mistaken for application bugs.
""")

e("typescript-generics-constraints", """
## Operational summary

Default to unbounded generics only when the function truly works on any type. Add `extends` when you access properties or require keyof safety. Replace `as any` inside generic utilities with proper constraints and named intermediate types when chains grow hard to read. Include a short generics exercise in onboarding: implement typed `pluck` or `groupBy`. Code review should flag new generic helpers that cast instead of constrain — that is the primary signal your team needs a constraint, not a suppression comment.
""")

e("typescript-satisfies-operator", """
## Operational summary

Use `satisfies` on internal config literals — themes, route maps, feature flags — where literal autocomplete and typo detection matter. Keep type annotations on exports when you intentionally widen types for consumers. Combine with Zod on external boundaries for runtime validation plus compile-time literal preservation on fixtures. Migrate annotation-based config files incrementally one directory per PR. Track adoption as a percentage of new config objects using `satisfies` rather than forcing a big-bang rewrite that repeats the failed strict-mode-in-one-PR pattern teams already learned to avoid.
""")

e("typescript-strict-mode-migration", """
## Operational summary

Enable `noImplicitAny` and `strictNullChecks` first; merge fixes in small PRs with a decreasing `@ts-expect-error` budget tracked in CI. New packages extend a shared strict tsconfig from day one. Measure production `undefined is not an object` errors before and after null-check migration on a pilot service — the drop justifies continued investment to leadership better than line counts. Delete the loose tsconfig only when error count hits zero and celebrate that milestone; long migrations without visible progress burn out the team maintaining dual configs for quarters.
""")

e("typescript-utility-types-app-patterns", """
## Operational summary

Derive API DTOs from domain entities with `Pick`, `Omit`, and `Partial` instead of maintaining parallel interfaces that drift. Name intermediate types when utility chains exceed two operations — readability in review matters as much as correctness. Pair compile-time DTOs with Zod or OpenAPI inference at boundaries so runtime validation and static types share one source of truth. Security review API responses by listing which entity fields `Pick` exposes; accidental inclusion of internal fields is a compile-time mistake if utilities derive from the entity rather than copy-pasted JSON examples that silently diverge when the model adds sensitive columns.
""")
