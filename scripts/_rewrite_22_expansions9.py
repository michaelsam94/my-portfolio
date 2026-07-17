# Ninth expansion — clean final padding (technical only)

EXPANSIONS9 = {}

def p(slug, text):
    EXPANSIONS9[slug] = "\n\n" + text.strip()

p("testing-mutation-testing", """
## Tooling reference

| Language | Tool | CI entry |
|----------|------|----------|
| TypeScript | Stryker + Vitest | `npx stryker run` |
| Java/Kotlin | PIT | `mvn org.pitest:pitest-maven:mutationCoverage` |
| .NET | Stryker.NET | `dotnet stryker` |
| Python | mutmut | `mutmut run` |

Publish HTML mutation reports as CI artifacts. Track mutation score weekly on payment and auth modules first; expand scope only after two stable months above your agreed floor. Pair mutation gates with flake stabilization — timeout mutants from unstable tests erode trust in the metric.
""")

p("testing-property-based-testing", """
## Library quick reference

| Language | Library | Minimal example |
|----------|---------|-----------------|
| Python | Hypothesis | `@given(st.integers())` |
| TypeScript | fast-check | `fc.assert(fc.property(...))` |
| Java | jqwik | `@Property void test(@ForAll int n)` |
| Rust | proptest | `proptest! { #[test] fn t(x in 0..100i32) {} }` |

Start with roundtrip properties on codecs and parsers, then idempotence on normalization functions. Add stateful properties only after the team reads shrinking output comfortably — unexplained minimal counterexamples frustrate newcomers unless someone walks through the first few in a guild session.
""")

p("testing-snapshot-testing-tradeoffs", """
## Replace-or-keep audit

During test-debt sprints, classify each snapshot: **keep** (stable serialized contract), **replace** with Testing Library assertions (behavior), **migrate** to visual regression (layout), or **delete** (duplicate coverage). Record decisions in a spreadsheet linked from the testing guide so future contributors do not resurrect deleted snapshots without understanding why they left. Teams that skip this audit accumulate silent approve habits that hide real regressions in noisy diffs.
""")

p("testing-test-data-builders", """
## Review checklist

Defaults must satisfy current validation rules. Builders return new instances — no shared mutable templates. Parallel-safe unique fields (emails, IDs). Object mothers name business scenarios QA recognizes. PRs adding long inline literals should extend builders instead. When the domain adds required fields, update builders in the same PR as schema changes so CI never constructs illegal fixtures that mask breaking changes until staging.
""")

p("testing-test-doubles-mocks-stubs", """
## When to escalate to integration tests

If a test mocks more than two collaborators or verifies more than one interaction chain, pause and ask whether a fake repository plus real SQL integration test expresses the scenario clearer. Mocks excel at verifying side effects at boundaries — email sent, charge captured — not at proving JOIN correctness or transaction isolation. Escalation to Testcontainers often reduces mock complexity while increasing confidence on the exact bugs mocks hide.
""")

p("testing-unit-vs-integration-balance", """
## Indicative ratios (adjust with data)

| System profile | Unit | Integration | E2E |
|--------------|------|-------------|-----|
| Pure domain library | high | low | minimal |
| CRUD + SQL service | medium | high | smoke only |
| SPA with BFF | medium | medium (MSW) | few journeys |

Revisit quarterly using escaped-defect tags. If SQL or migration bugs dominate postmortems, integration investment rises regardless of pyramid posters. If UI regressions dominate, shift toward component and E2E tests while keeping pure domain logic in fast unit tests without mocks.
""")

p("testing-vitest-react-testing-library", """
## Recommended defaults

```typescript
// vitest.config.ts excerpt
test: {
  environment: "jsdom",
  setupFiles: ["./src/test/setup.ts"],
  css: true,
  clearMocks: true,
}
```

Document `npm test` for watch mode and `vitest run --coverage` for CI in CONTRIBUTING. Pin Vitest to the Vite major version compatibility matrix your platform team maintains — upgrading Vite without paired Vitest bumps is a common source of Monday CI breakage after Dependabot merges without reading release notes.
""")

p("timeseries-downsampling-retention", """
## Dashboard datasource documentation

Each Grafana dashboard README should list which datasource UID serves raw vs rollup tiers and which time ranges are safe for each. On-call engineers should not guess during incidents. When shortening retention, migrate dashboards in the same change window with annotated gaps if historical holes are expected — finance and capacity reviewers need explicit notice before monthly trend panels change shape.
""")

p("timeseries-influxdb-vs-timescale", """
## Weighted scorecard (example)

Rate 1–5: SQL skill, Postgres ops maturity, JOIN need, line-protocol ingest volume, managed-service preference, export portability. Weight JOIN and ops highest when embedding metrics beside transactional data in the same Postgres fleet. Weight ingest protocol highest for device telemetry at the edge. Attach completed scorecard to the ADR; future engineers inherit rationale instead of re-debating the same benchmarks annually.
""")

p("timeseries-prometheus-remote-write", """
## Alert templates

```yaml
- alert: PrometheusRemoteWriteLag
  expr: time() - prometheus_remote_storage_queue_highest_sent_timestamp_seconds > 300
  for: 10m

- alert: PrometheusRemoteWriteFailures
  expr: rate(prometheus_remote_storage_samples_failed_total[5m]) > 0
  for: 5m
```

Page when samples fail or lag exceeds five minutes in production. Runbook: scale receive path, temporarily relabel-drop noncritical metrics, open vendor ticket if managed. After recovery, annotate Grafana gaps in incident channel — stakeholders interpreting month-over-month graphs need explicit notice that data holes are infrastructure artifacts not application outages.
""")

p("typescript-generics-constraints", """
## Practice exercise

Reimplement `Pick<T, K>` with `K extends keyof T` in a scratch file using mapped types. Then implement `pluck(obj, key)` with the same constraint. Compare to lib.d.ts utilities. Engineers who can write these from memory design safer shared `@org/types` packages without reaching for `any` when generics feel hard — the exercise takes twenty minutes and pays off on every API wrapper written afterward.
""")

p("typescript-satisfies-operator", """
## Upgrade note

`satisfies` requires TypeScript 4.9+. Pin `typescript` in engines and CI. After major TS upgrades, recompile config modules using satisfies — inference rules occasionally shift. Grep the codebase for `: Config = {` annotations on constants and migrate to satisfies incrementally; each migration PR should include a one-line note in CHANGELOG under Developer Experience so downstream teams know autocomplete improved on theme and route tokens.
""")

p("typescript-strict-mode-migration", """
## Optional flags after core strict

Enable `noUncheckedIndexedAccess` after `strictNullChecks` stabilizes — index accesses gain `| undefined` forcing guards. Consider `exactOptionalPropertyTypes` last; it changes optional prop semantics and churns heavily in React codebases. Document flag order in the migration ADR and track `@ts-expect-error` count per flag in a visible dashboard; stalling error count plateau means schedule slack to finish — half-strict codebases linger for years without public progress metrics.
""")

p("typescript-utility-types-app-patterns", """
## Layer diagram to maintain

```
UserEntity (DB)
  → Omit secrets → User (domain)
  → Pick public fields → UserPublic (API read)
  → Partial Pick mutable → UpdateUserInput (API write)
```

Keep this diagram in architecture docs; update when fields move between public and internal. Code review rejects hand-written DTO interfaces that duplicate entity fields when a one-line Pick or Omit expresses the same intent — duplication is where security leaks and stale types hide until production rejects requests.
""")
