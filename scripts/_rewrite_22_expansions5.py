# Fifth expansion — final substantive sections (500+ words each where needed)

EXPANSIONS5 = {}

def E(slug, text):
    EXPANSIONS5[slug] = "\n\n" + text.strip()

E("shared-data-layer-room-kmp", """
## Case study: catalog offline browse

Retail app shared Room layer caches product catalog for aisle mode with poor connectivity. Repository `observeCategory(slug)` returns Flow from DAO; background sync job in platform scheduler calls `refreshCategory` every six hours on WiFi. iOS BGTaskScheduler and Android WorkManager constraints configured separately but call same `SyncCoordinator` in commonMain. Analytics events for sync success/failure emitted through expect/actual analytics bridge without importing Firebase into common code.

## Debugging sync conflicts

Log structured sync events with `entity_id`, `local_version`, `remote_version`, `resolution` enum — grep across Android and iOS logs during beta. Room transaction log on debug builds prints SQL duration; slow queries optimized in shared migration benefit both platforms. When user reports stale price, support script queries local DB export from in-app debug menu — same export format both platforms because same schema.
""")

E("supply-chain-dependency-pinning", """
## Regulatory and audit context

SOC2 and ISO audits ask for evidence of dependency controls — committed lockfiles plus CI install from lock satisfies auditor checklist item on change management. Export SBOM each release tagged `v1.2.3` stored alongside artifact for seven years if finance regulations require. Pen test findings often include "unpinned dependencies" — remediate before report published.

## Interaction with Dependabot security alerts

GitHub alerts on vulnerable lockfile versions — alert without lockfile update PR is noise. Configure auto-open PR with bump; merge when CI green. Critical CVSS merge within 24h SLA; moderate within sprint. Document exception process when upgrade breaks API — temporary pin to patched minor with compensating control WAF rule rare and time-boxed.
""")

E("technical-writing-for-engineers", """
## Templates that accelerate writing

Runbook template, ADR template, README template in `.github/` — copy reduces blank page paralysis. Template includes section headers only; delete sections that do not apply rather than leaving TODO placeholders in production docs. RFC template for cross-team proposals: problem, options, decision, rollout — comments in Google Doc phase, final state in git ADR.

## Writing for on-call under stress

Runbook steps numbered; each step one action verb. Link to dashboard with exact URL including time range params. Avoid "see wiki" without path — deep link or copy-paste query. If step requires human judgment, say "if error rate > 5% proceed to step 7 else step 12" — decision tree beats prose paragraph at 3 AM.
""")

E("testing-compose-uis-v2", """
## Testing Navigation Compose

```kotlin
composeRule.onNodeWithContentDescription("Open menu").performClick()
composeRule.onNodeWithTag("nav_settings").performClick()
composeRule.onNodeWithText("Settings").assertIsDisplayed()
```

Navigation graph back stack: system back `composeRule.onNodeWithContentDescription("Navigate up").performClick()` or `Espresso.pressBack()`. Test deep link intent with `createAndroidComposeRule` activityRule scenario starting from VIEW intent URI.

## Visual regression with Compose

Paparazzi library snapshots composables without emulator — JVM unit speed with pixel diff. Complement semantics tests: Paparazzi catches color/spacing; semantics tests catch behavior. Choose Paparazzi for design system components; ComposeTestRule for interaction flows.

## Test naming convention

`givenEmptyCart_whenCheckoutClicked_showsError` — readable in CI failure notifications without opening file. Align with Gherkin language product understands for trio amigos sessions.
""")

E("testing-mutation-testing", """
## Worked example: discount cap

Production code: `if (discount > max) discount = max`. Mutants: `>=`, `<`, remove cap. Tests asserting only `applyDiscount(10)` returns number miss mutants — add boundary tests AND mutation run confirms. Survivor on `>=` mutant means add test `{ discount: max, expect: max }` and `{ discount: max+1, expect: max }`.

## Organizational adoption path

Month 1: measure baseline mutation score on payments module without gate. Month 2: fix top ten survivors. Month 3: enable CI gate at baseline minus 5% floor. Month 4: expand to auth module. Sudden gate day zero causes rebellion; gradual transparency builds trust that mutation finds real gaps not bureaucratic score.
""")

E("testing-playwright-e2e", """
## Page object maintenance

Keep locators private in page class; tests call `checkoutPage.completePurchase()`. When button text changes, update one page object not forty tests. Page objects live in `e2e/pages/` colocated with spec files per feature domain.

## Handling 3rd party widgets

Stripe, reCAPTCHA, chat widgets block automation — use test mode keys, disable captcha in staging via env, stub iframe payment with Playwright route fulfill of success response. Document staging config required for green E2E in platform onboarding doc.

## Performance budgets in E2E

Assert navigation timing: `expect(page).toHaveURL(/dashboard/, { timeout: 10000 })` — fail if SPA routing regresses. Optional Lighthouse CI step in same pipeline as Playwright smoke for performance regression signal separate from functional smoke.
""")

E("testing-property-based-testing", """
## Model-based testing intro

State machine model: valid transitions deposit, withdraw, overdraft disallowed. Property: after any sequence of valid operations balance equals sum of deposits minus withdrawals. Hypothesis stateful testing generates operation sequences exploring edge states single examples miss.

## Numeric properties cautions

Floating point: use integers cents or `decimal` type; property on floats needs epsilon compare. Overflow: generate near MAX_INT when testing accumulator. Division: assume divisor non-zero.

## Teaching workshop outline

Hour workshop: (1) example test limits demo failing case, (2) write roundtrip property together, (3) watch shrink, (4) add to CI with small example count. Teams leave with one property in their module — adoption beats mandate from QA ivory tower.
""")

E("testing-snapshot-testing-tradeoffs", """
## Email and notification templates

Snapshot HTML email bodies — marketing reviews copy change in PR diff. Plain text alternative snapshot separately — multipart email regressions common when HTML changes but text forgotten.

## Internationalization snapshots

Snapshot default locale; separate snap file per locale when translations diverge layout not just string — `Alert.snap.en`, `Alert.snap.ar`. CI job runs locale matrix shard parallel.

## When to delete snapshots entirely

Design system mature with visual regression service — delete Jest DOM snapshots replaced by Chromatic. Migration PR removes snap files and adds visual test config — net reduction maintenance if team commits to visual platform cost.
""")

E("testing-test-data-builders", """
## Parallel test isolation

Builder generates unique email `user-${randomUUID()}@test.com` per build — parallel CI workers do not collide on unique DB constraint. Seeded random when reproducible failure needed.

## GraphQL test data

Builder produces variables object matching GraphQL mutation input type — `CreateOrderVariablesBuilder` aligns with codegen types, compile error when schema adds required field.

## Legacy fixture migration

Replace 500-line JSON fixture file incrementally: introduce builder, migrate ten tests per PR, delete fixture chunk when zero references — strangler fig pattern for test data debt.
""")

E("testing-test-doubles-mocks-stubs", """
## Hand-written fakes vs mock frameworks

Fake `InMemoryEventBus` with subscribe/publish — twenty lines, no Mockito magic, readable in code review. Prefer hand fake when behavior simple; Mockito when verifying interaction with heavy external SDK.

## Testing retries

Stub HTTP 503 twice then 200 — assert client retried three times without mocking retry loop internals if client uses exponential backoff interface injected.

## Cleanup after mock

`verifyNoInteractions` on unused mocks in `@AfterEach` — detects test pollution when mock leaked calls from previous test due to shared static wiring bug.
""")

E("testing-unit-vs-integration-balance", """
## Frontend balance specifics

Component tests with MSW majority; few Playwright smokes; unit tests for pure formatters and hooks. Trophy shape for SPA — not identical to backend pyramid.

## Legacy system strangle

Characterization integration tests on legacy monolith module before extract — high integration count temporary during strangler fig migration; delete when service extracted and contract tests replace.

## Leadership reporting

Dashboard: test count by layer, CI duration by layer, escaped defects by layer tag — quarterly review adjusts investment with data not ideology about pyramid posters.
""")

E("testing-vitest-react-testing-library", """
## Testing forms

```typescript
await user.type(screen.getByLabelText(/email/i), "bad");
await user.click(screen.getByRole("button", { name: /submit/i }));
expect(await screen.findByRole("alert")).toHaveTextContent(/invalid email/i);
```

Assert validation messages visible — users see errors not `input.validity` internal.

## Router testing

```typescript
render(<App />, { wrapper: ({ children }) => <MemoryRouter initialEntries={["/checkout"]}>{children}</MemoryRouter> });
```

Or `@testing-library/react` with `createMemoryRouter` in React Router v6.4 data APIs.

## Performance testing components

Not load testing — assert expensive list virtualized does not render 10000 DOM nodes: `expect(screen.getAllByRole('listitem')).toHaveLength(lessThan(50))` after scroll simulation if applicable.
""")

E("timeseries-downsampling-retention", """
## Capacity planning worksheet

Spreadsheet: series count × scrape interval × bytes per sample × retention days = GB. Model 20% headroom; present finance before Black Friday new product launch adds labels. Revise quarterly with actual cardinality from TSDB admin UI.

## Compaction operations window

Schedule downsampling jobs off-peak — Timescale compress policy maintenance IO spike; monitor disk IO wait during first compression on large hypertable. Communicate analytics team slow queries during window.

## Dual write period

Migrating retention policy: dual-write raw to new tier while backfill historical rollups — compare rollup query results within epsilon before dropping old tier. Document epsilon threshold per metric type gauge vs counter.
""")

E("timeseries-influxdb-vs-timescale", """
## Operational runbook differences

Influx backup restore drill uses `influx backup` CLI; Timescale uses `pg_dump` with hypertable awareness — on-call runbooks must not assume Postgres playbook for Influx host. Escalation paths differ: Influx Cloud vendor ticket vs DBA for RDS Timescale.

## Cost model worked example

One million series, 15s scrape, 90 day retention — calculate GB both engines with compression ratio assumptions from vendor docs (often 5-10x). Include query node cost not just storage — Timescale heavy analytics may need read replica Influx may need separate query tier depending edition.
""")

E("timeseries-prometheus-remote-write", """
## Runbook: receiver down

Step 1 confirm Prometheus queue metrics. Step 2 scale receive. Step 3 enable drop relabel for non-critical metrics if lag increasing. Step 4 page vendor if managed backend. Step 5 post-incident: gap in Grafana expected — annotate dashboards during gap window.

## Testing relabel configs

`promtool test rules` for recording rules; test remote write relabel with dry-run metric simulator injecting sample labels — catch accidental drop of `job` label breaking alerts downstream.

## Federation query pitfalls

Querying both Prometheus and Mimir may duplicate series if external labels not deduplicated — Grafana dedup in mixed datasource or standardize single query path for dashboards used in incidents.
""")

E("typescript-generics-constraints", """
## Workshop exercise

Implement `pluck<T, K extends keyof T>(obj: T, keys: K[]): Pick<T, K>` in pair programming interview — tests understanding constraints better than reverse linked list. Use in internal leveling rubric for mid-level TS promotion.

## Generic context React

`createContext<AuthState | undefined>(undefined)` — narrow with hook throwing if undefined eliminating repeated null checks in consumers. Constraint pattern applies UI frameworks not only utilities.
""")

E("typescript-satisfies-operator", """
## Migration codemod strategy

Run TS morph script replacing `: Config = {` with `= { ... } satisfies Config` in config directory only — one folder per PR. Measure compile error count before expanding scope.

## satisfies vs z.infer

Zod schema source of truth: infer type, use satisfies on example fixtures matching schema for test data — double validation compile and runtime in test suite bootstrap.
""")

E("typescript-strict-mode-migration", """
## Hiring and strict codebase

Job posting mentions strict TypeScript — signals quality to candidates; interview uses strict sandbox. Junior engineers onboard faster with compiler teaching null checks than tribal `any` escape knowledge.

## Shared tsconfig package

Monorepo `@org/tsconfig` base strict true — packages extend and only override if absolutely necessary with comment in tsconfig. Central bump TS version once for all packages.
""")

E("typescript-utility-types-app-patterns", """
## API response wrapper

```typescript
type ApiResponse<T> = { data: T; meta: { requestId: string } };
type UserResponse = ApiResponse<UserPublic>;
type UserListResponse = ApiResponse<UserPublic[]>;
```

Utility types compose — Pick UserPublic once, reuse in list and detail responses.

## Form state typing

```typescript
type FormErrors<T> = Partial<Record<keyof T, string>>;
type UserFormErrors = FormErrors<Pick<User, "email" | "name">>;
```

Partial Record pattern for field errors common in React Hook Form projects without third-party error type dependency.
""")
