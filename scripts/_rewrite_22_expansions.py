# Additional sections to reach >=1200 words per post

EXPANSIONS = {}

EXPANSIONS["seo-javascript-rendering-crawl"] = r"""

## Framework-specific rendering notes

**Next.js App Router** defaults to Server Components — indexable HTML is the happy path if you avoid marking entire pages `"use client"`. Fetch product data in server components; isolate interactivity to leaf client components.

**Nuxt and SvelteKit** offer SSR/SSG with similar splits. Verify `ssr: true` in production build, not just dev.

**Create React App / Vite SPA** without SSR requires prerender plugin (vite-plugin-ssr, react-snapshot) or dynamic rendering bridge for indexable routes.

```javascript
// Vite SSR entry sketch — HTML includes content
export async function render(url) {
  const html = ReactDOMServer.renderToString(<App url={url} />);
  return template.replace("<!--app-->", html);
}
```

## Internal linking and JS navigation

Client-side routers must emit real `<a href>` for crawl discovery. Buttons that `navigate()` without href hide links from initial HTML unless sitemap compensates — fragile.

```tsx
// Prefer
<Link href="/products/widget">Widget</Link>
// Over onClick-only navigation for indexable destinations
```

## Measuring index coverage

Weekly dashboard:

- Indexed URLs / submitted sitemap URLs
- Crawl requests per day vs new product count
- Median days from first crawl to indexed for new SKUs

Regression in any metric after JS deploy triggers URL Inspection batch on top 100 revenue URLs.

## International and hreflang with SSR

CSR hreflang injected post-load may be missed on first pass. Emit alternates in server HTML:

```html
<link rel="alternate" hreflang="en-us" href="https://example.com/en/product" />
<link rel="alternate" hreflang="de-de" href="https://example.com/de/product" />
```

## Staging parity

SSR bugs often appear only under production CDN caching. Test rendered HTML from edge, not localhost. Compare `Cache-Control` headers — accidental `private` on HTML slows Googlebot refresh.

Treat JavaScript rendering as a production SLO: time-to-index for new content, not a one-time audit checklist."""

EXPANSIONS["seo-meta-robots-noindex-patterns"] = r"""

## noindex vs robots.txt Disallow

| Mechanism | Blocks crawl | Blocks index | Needs crawl to read |
|-----------|--------------|--------------|---------------------|
| noindex | No | Yes | Yes |
| Disallow | Usually | No* | N/A |

*Google may index URLs without crawling if linked externally — URL-only results.

Removing Disallow to apply noindex on legacy URLs is a known migration pattern — unblocking crawl lets Google read noindex and drop entries.

## CMS and headless patterns

Headless CMS preview URLs often leak. Automate:

```typescript
export function robotsForHost(host: string) {
  if (host.includes("preview") || host.includes("staging")) {
    return { index: false, follow: false };
  }
  return { index: true, follow: true };
}
```

Wire into `generateMetadata` or edge middleware consistently — one forgotten template indexes entire preview tenant.

## Paginated series

Google consolidated pagination guidance: self-referencing canonical on each page; do not noindex page 2+ unless content truly duplicates page 1 entirely. Ecommerce category page 2 with unique products should index.

## PDF and document assets

Investor PDFs, spec sheets, and internal decks uploaded to `/public` get indexed without HTML. Header policy:

```apache
<FilesMatch "\.(pdf|docx)$">
  Header set X-Robots-Tag "noindex, noarchive"
</FilesMatch>
```

## Legal and compliance pages

Privacy policy and terms should **index** — users search for them. noindex on legal pages creates trust gaps in SERP.

## Testing directives before launch

Automated smoke on deploy:

```bash
curl -sI https://staging.example.com/ | grep -i x-robots-tag
curl -s https://staging.example.com/ | grep -i 'meta name="robots"'
```

Fail pipeline if production host returns noindex.

## Post-incident cleanup

If staging indexed: verify noindex live, remove from sitemap, optional Search Console removal tool for urgent cases, fix internal links pointing to staging, rotate secrets if staging exposed auth bypass.

Meta robots directives are contract between your platform and crawlers — encode them in infrastructure as code, not one-off HTML edits."""

EXPANSIONS["serverless-database-access-patterns"] = r"""

## Prisma and ORM pooling

Prisma on Lambda needs explicit datasource URL to Proxy and small pool settings when using Data Proxy or Accelerate:

```prisma
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}
```

Without Proxy, set `connection_limit=1` in URL for direct RDS — reduces per-instance connections but does not solve spike concurrency alone.

## Neon and serverless Postgres

Neon separates compute and storage with built-in connection pooling endpoint (`-pooler` hostname). Similar pattern to Proxy — point Lambda at pooler URL, not direct compute.

## VPC cold start tradeoff

Lambda in VPC needs ENI setup — adds cold start latency. Minimize VPC-attached Lambdas; use Proxy public endpoint with auth, or Data API, when security model allows.

## SQS batch processing

Process batch with single connection:

```python
def handler(event, context):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for record in event["Records"]:
                process(cur, record)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
```

One connection per batch, not per record.

## RLS and Lambda identity

Postgres Row Level Security with `SET LOCAL app.user_id` per transaction — set session variable once per invocation, not per query without transaction wrapper.

## Cost model

Proxy has hourly cost; compare to outage cost and engineer pager time. Dynamo on-demand spiky vs RDS always-on — hybrid often wins for read-heavy catalog with write-light events.

## Load test script

Simulate step concurrency ramp before launch:

```bash
aws lambda invoke --function-name api --payload file://event.json \
  --cli-read-timeout 0 /dev/null &
# repeat N times, watch DatabaseConnections
```

Document max safe concurrency in runbook next to `reserved_concurrency` setting.

Serverless database access matures when teams treat connections as global scarce resources — not free per invocation."""

EXPANSIONS["shared-data-layer-room-kmp"] = r"""

## Gradle version catalog alignment

Pin Room, SQLite, and KSP versions in `libs.versions.toml` — KMP breaks on mismatched compiler plugin versions across modules.

## Flow and Room

DAO `Flow` emissions integrate with `stateIn` in ViewModel:

```kotlin
class ItemViewModel(dao: ItemDao) : ViewModel() {
    val items = dao.observeAll()
        .map { list -> list.map { it.toDomain() } }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())
}
```

Collect in UI with `collectAsStateWithLifecycle()` on Android; SwiftUI consumes via wrapper exposing `StateFlow` as observable.

## iOS Swift interop

Expose repository with `@ObjCName` or SKIE-generated Swift API — Room stays Kotlin; SwiftUI never touches SQL directly.

## Encryption

SQLCipher via expect/actual driver wrapper for sensitive offline cache — key from iOS Keychain / Android Keystore through platform secure storage interface.

## Migration testing matrix

| Test | Android | iOS | commonTest |
|------|---------|-----|------------|
| Migration 1→2 | ✓ | ✓ | ✓ |
| Destructive fallback | instrumented | simulator | in-memory |

## Offline queue conflict UI

When sync fails, surface `synced=false` items in UI with retry — repository exposes `observePending()` Flow.

## Performance

Index columns used in WHERE and ORDER BY. `@Upsert` batch in transactions for bulk refresh — single transaction per sync wave, not per row.

Room KMP rewards teams that treat shared module as product — with migration CI, platform factories, and repository APIs stable enough for Swift and Kotlin UI teams to parallelize."""

EXPANSIONS["supply-chain-dependency-pinning"] = r"""

## Docker and pinned installs

```dockerfile
# BAD
RUN npm install

# GOOD
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts
COPY . .
RUN npm run build
```

Layer caching preserves lock integrity — changing source without lock change reuses dependency layer.

## Python uv and pip-tools

```bash
uv pip compile pyproject.toml -o requirements.lock
uv pip sync requirements.lock
```

Modern pipelines adopt uv for speed with same pinning discipline.

## Go modules proxy

`GOPROXY=https://proxy.golang.org,direct` with `go.sum` committed — CI `go mod verify` catches tampering.

## License compliance

Lockfiles feed FOSSA/License Finder scans — unpinned installs change licenses without review.

## Emergency CVE patch process

1. OSV alert on pinned package
2. Renovate PR with bump + CI
3. If zero-day: manual pin to patched version, expedited review, post-deploy SBOM diff archived

## Monorepo considerations

pnpm `workspace:` protocol with single lockfile — avoid per-package divergent trees. Nx affected builds skip unchanged packages but still install from root lock.

## Deny lists

Block known malicious package versions in Artifactory/npm proxy:

```json
{ "blockedPackages": { "event-stream": ["3.3.4"] } }
```

Pinning is baseline — combine with egress controls on CI runners preventing unknown registry calls.

Supply-chain safety is reproducibility plus review velocity — pinned trees make both possible."""

EXPANSIONS["technical-writing-for-engineers"] = r"""

## API reference layers

OpenAPI spec generated from code stays accurate; narrative docs explain auth flows, pagination, idempotency, and error retry policy OpenAPI cannot express.

```yaml
# openapi excerpt — pair with prose on rate limits
paths:
  /charges:
    post:
      summary: Create charge (idempotent via Idempotency-Key header)
```

Link from each operation to guide section with curl example.

## On-call documentation hierarchy

1. Runbook (symptom → fix)
2. Architecture diagram (context)
3. ADR (why built this way)
4. Postmortem index (historical failures)

On-call starts at layer 1 — never layer 3 at 3 AM.

## Writing for international teams

Simple sentences, avoid idioms, define acronyms, UTC timestamps always, explicit locale assumptions in date formatting docs.

## Docs search

If using MkDocs/Docusaurus, configure local search or Algolia — unsearchable docs become Slack questions.

## Measuring doc success

- Time-to-first-success for onboarding survey
- Support ticket tags "docs unclear"
- Search zero-result queries

Quarterly review top zero-result queries → new pages.

## Changelog discipline

User-facing docs need changelog entry per release — link migration guides for breaking API changes.

## Pair writing

Engineer drafts accuracy; tech writer edits clarity — 30-minute pairing beats async comment wars.

Technical writing compounds — every hour invested in quickstart saves ten hours of interrupts over the doc lifetime."""

EXPANSIONS["testing-compose-uis-v2"] = r"""

## Hilt and Compose tests

```kotlin
@HiltAndroidTest
class HomeScreenTest {
    @get:Rule(order = 0)
    val hiltRule = HiltAndroidRule(this)

    @get:Rule(order = 1)
    val composeRule = createAndroidComposeRule<MainActivity>()

    @Before fun setup() = hiltRule.inject()
}
```

Replace production bindings with `@TestInstallIn` fakes for deterministic UI.

## Navigation testing

```kotlin
composeRule.onNodeWithContentDescription("Show details").performClick()
composeRule.onNodeWithTag("detail_screen").assertIsDisplayed()
```

Test tags on root of each destination — navigation graphs change; tags stabilize assertions.

## Custom semantics

```kotlin
Modifier.semantics { contentDescription = "Loading" }
```

Merge properties carefully — duplicate descriptions confuse TalkBack and tests.

## Screenshot tests

`captureToImage()` on Compose nodes for visual regression — supplement semantics tests, not replace.

## Multimodule CI

`:feature:checkout` instrumented tests run only when `:feature:checkout` affected — Gradle test caching saves hours.

## Accessibility test automation

```kotlin
composeRule.onNodeWithRole(Role.Button).assertHasClickAction()
```

Compose Test `assertIsToggleable()` etc. — catch missing roles before manual audit.

Compose UI tests pay off when semantics are designed alongside UI — not bolted on after release."""

EXPANSIONS["testing-mutation-testing"] = r"""

## Mutation testing in legacy code

Start with new modules — 100% mutation on greenfield, expand radius quarterly. Legacy monolith full run may take days.

## Kotlin PIT

```xml
<targetClasses><param>com.app.domain.*</param></targetClasses>
<avoidCallsTo><param>java.util.Objects</param></avoidCallsTo>
```

Exclude generated code, Lombok boilerplate, DTOs without logic.

## Equivalent mutant examples

Changing `i++` to `i--` in unused variable — PIT marks equivalent; do not chase score.

## Team workflow

PR comment bot posts mutation score delta — "+2% on payments module" visible in review.

## Relation to coverage gates

Coverage 80% gate + mutation 75% on domain — coverage alone insufficient; mutation catches weak asserts.

## Performance

Run mutation on subset of tests touching mutated class — Stryker `mutate` glob narrow.

Mutation testing humbles coverage dashboards — use it where wrong math costs money."""

EXPANSIONS["testing-playwright-e2e"] = r"""

## Visual comparisons

```typescript
await expect(page).toHaveScreenshot("homepage.png", { maxDiffPixels: 100 });
```

Commit baseline images — review visual diffs in PR like snapshots.

## Mobile viewports

```typescript
projects: [{ name: "mobile", use: { ...devices["Pixel 7"] } }]
```

Critical flows test mobile — half traffic, most checkout bugs.

## API setup before UI

```typescript
test.beforeEach(async ({ request }) => {
  await request.post("/api/test/seed", { data: { userId: "e2e-1" } });
});
```

Seed via API faster than UI signup every test.

## Parallel isolation

Unique user per worker: `testUser-${test.info().parallelIndex}` — avoid collision in parallel CI.

## Soft assertions for diagnostics

```typescript
await expect.soft(page.getByText("Welcome")).toBeVisible();
await expect.soft(page.getByText("Balance")).toBeVisible();
```

Collect multiple failures per run — useful smoke diagnostics.

## Playwright Component Testing

CT isolates components without full app — faster than E2E for widget behavior; still real browser.

Playwright rewards treating tests as product code — fixtures, helpers, and traces maintained like production services."""

EXPANSIONS["testing-property-based-testing"] = r"""

## Rust proptest

```rust
proptest! {
    #[test]
    fn roundtrip(ref s in "\\PC*") {
        prop_assert_eq!(decode(encode(s)), s);
    }
}
```

Ecosystem-native for Rust services.

## Linking to unit tests

When property fails, Hypothesis writes `@example` decorator with shrunk case — commit as regression.

## Stateful properties

Model operations as sequence — insert then delete leaves empty set. Hypothesis `stateful` API for state machine testing.

## Performance budgets

Properties run 100+ cases — keep generators fast; heavy properties nightly only.

## Documentation value

Property names document invariants better than example table in comment block:

```python
# Property: normalize_email is idempotent.
@given(st.emails())
def test_idempotent(email): ...
```

Property tests encode laws your domain must obey — treat failures as specification bugs, not test annoyances."""

EXPANSIONS["testing-snapshot-testing-tradeoffs"] = r"""

## Jest snapshot serializers

Custom serializer for dates — stable output:

```javascript
expect.addSnapshotSerializer({
  test: (val) => val instanceof Date,
  print: (val) => val.toISOString(),
});
```

## Email HTML snapshots

Transactional email templates benefit from snapshot — one place to review markup; pair with Litmus for client rendering.

## Snapshot in code review tools

Configure GitHub to collapse snap files by default but require explicit expand for large diffs — policy in CONTRIBUTING.

## Deletion strategy

When removing snapshot, add explicit assertion first in same PR — never delete coverage without replacement.

## Component library packages

Design system publishes components — snapshot per variant in Storybook test runner alternative to monolithic story snapshots.

Snapshots are guardrails on stable output — not a strategy for exploratory UI development."""

EXPANSIONS["testing-test-data-builders"] = r"""

## TypeScript partial deep merge

```typescript
function buildUser(overrides: DeepPartial<User> = {}): User {
  return merge(structuredClone(defaultUser), overrides);
}
```

Careful with nested merge semantics — document behavior.

## Database fixtures

Integration tests: builder → SQL insert via repository — same builder as unit tests keeps shape consistent.

## Anti-corruption layer

Map builder output through adapter under test — builder represents external API shape, not domain.

## Documentation in builders

```typescript
/** Admin with billing override — use for refund tests */
adminWithBilling(): UserBuilder { ... }
```

JSDoc on mother methods explains scenario.

## Compose with factories

`OrderBuilder.withUser(userBuilder.build())` — link entities without orphan FK violations in DB tests.

Builders scale with domain — refactor early when three tests copy same twelve-field literal."""

EXPANSIONS["testing-test-doubles-mocks-stubs"] = r"""

## Contract tests vs mocks

Pact verifies provider against consumer contract — mock generated from contract, not imagination.

## Clock fake

```typescript
vi.useFakeTimers();
vi.setSystemTime(new Date("2026-07-17"));
```

Deterministic expiry tests without `setTimeout` flakiness.

## Spy on module

```typescript
const logSpy = vi.spyOn(console, "error").mockImplementation(() => {});
```

Spies record without full mock replacement.

## Integration test doubles

Testcontainers Postgres is not a mock — real dependency, controlled environment. Doubles spectrum from stub to production.

## Mockito strict stubs

Unused stubbing fails test — catches over-mocking early.

Name the double by intent — if verifying calls, mock; if providing data, stub; if simulating storage, fake."""

EXPANSIONS["testing-unit-vs-integration-balance"] = r"""

## Consumer-driven contracts

Pact on API boundary — integration without full E2E stack running.

## Slice tests

Spring `@WebMvcTest`, Nest testing module with real controller + mocked service — middle layer between unit and full integration.

## Frontend MSW integration

MSW in Vitest with real React Query stack — integration of data layer without backend.

## Defect taxonomy retro

Tag last quarter prod bugs: "mock wouldn't catch" vs "unit would catch" — data drives investment.

## Test debt budget

Allow +5 integration tests per sprint without deleting unit tests — gradual rebalance.

## Flaky integration fixes

Quarantine flaky integration with ticket — zero tolerance long-term; delete if not fixed in 30 days.

Balance is empirical — pyramid poster is starting point, production escape data is truth."""

EXPANSIONS["testing-vitest-react-testing-library"] = r"""

## Custom render wrapper

```typescript
function renderWithProviders(ui: React.ReactElement) {
  return render(
    <QueryClientProvider client={testQueryClient}>
      <ThemeProvider>{ui}</ThemeProvider>
    </QueryClientProvider>
  );
}
```

Centralize providers — tests stay DRY.

## Accessibility queries

```typescript
expect(screen.getByRole("textbox", { name: /email/i })).toBeRequired();
```

Role queries encode a11y contract.

## Debug screen

```typescript
import { screen } from "@testing-library/react";
screen.debug(undefined, 30000);
```

Print DOM on failure — faster than rerunning headed.

## Vitest pool options

```typescript
test: { pool: "forks", maxWorkers: 4 }
```

Tune CI workers — memory vs speed.

## Snapshot sparingly with RTL

Prefer explicit assertions — snapshots optional for serialized markup components.

Vitest + RTL succeeds when tests read like user stories — short, focused, run on every save."""

EXPANSIONS["timeseries-downsampling-retention"] = r"""

## Cardinality-aware retention

High-cardinality metrics (per-user) shorter retention than low-cardinality (per-region) — label-based policies in Cortex/Mimir.

## Legal hold

Compliance tier bypasses deletion — tag series `retention=legal` excluded from drop jobs.

## Backfill after policy change

Lowering retention does not instantly free disk — compaction runs async; monitor bytes after 24–48h.

## Grafana variables

Dashboard default `$__interval` auto-selects rollup resolution — train users not to force 15s on year range.

## Cost alerting

Project monthly storage from ingest rate × retention tiers — alert at 80% budget.

Downsampling policy is product decision disguised as ops — involve SRE and finance before ten-year raw retention."""

EXPANSIONS["timeseries-influxdb-vs-timescale"] = r"""

## Grafana datasource plugins

Both have mature Grafana support — evaluate Explore UX with your query patterns before committing.

## Edge and IoT

Influx line protocol from Telegraf agents at edge — batch write to cloud. Timescale needs TCP Postgres or HTTP wrapper.

## Multi-tenancy

Influx buckets/org tokens; Timescale schema-per-tenant or RLS — pick model matching auth system.

## Backup restore drills

Quarterly restore test — Influx backup format vs Postgres pg_dump + hypertable restore differ in RTO.

## Vendor lock-in exit

Document export format (Parquet, CSV, line protocol) before petabyte commit.

Choose engine where query authors already live — SQL shop rarely loves Flux long-term."""

EXPANSIONS["timeseries-prometheus-remote-write"] = r"""

## OTLP vs remote write

Metrics from OpenTelemetry Collector can remote_write to same backend — unify scrape and push paths.

## Cardinality limits in Mimir

Configure per-tenant series limits — reject before storage, complement relabel drops.

## Compaction and object storage

Thanos compactor downsamples blocks in object store — separate from Prometheus local retention.

## Alert on remote write

```yaml
- alert: RemoteWriteLag
  expr: time() - prometheus_remote_storage_queue_highest_sent_timestamp_seconds > 300
  for: 10m
```

Page before queue drops samples.

## Cost optimization

S3 lifecycle to Glacier for blocks older than 2y — query latency tradeoff acceptable for compliance archives.

Remote write completes observability stack — local Prometheus for now, durable store for history and compliance."""

EXPANSIONS["typescript-generics-constraints"] = r"""

## Conditional types with generics

```typescript
type ApiResult<T> = T extends string ? { message: T } : { data: T };
```

Constraints combine with conditional distribution.

## infer keyword

```typescript
type ElementType<T extends readonly unknown[]> = T extends readonly (infer E)[] ? E : never;
```

Extract inner type from constrained array.

## Generic components (React)

```typescript
function Select<T extends string>(props: { options: T[]; value: T; onChange: (v: T) => void }) {
  ...
}
```

Literal union options preserved with satisfies on options array.

## Library authoring

Export generic functions with minimal constraints — document type params in TSDoc.

## Performance

Generics erase at compile — zero runtime cost; prefer over runtime typeof checks.

Master constraints once — most application TypeScript beyond CRUD is generic utilities and typed API boundaries."""

EXPANSIONS["typescript-satisfies-operator"] = r"""

## Discriminated union configs

```typescript
type Handler = { type: "a"; foo: string } | { type: "b"; bar: number };

const handlers = {
  a: { type: "a", foo: "x" },
  b: { type: "b", bar: 1 },
} as const satisfies Record<string, Handler>;
```

Exhaustive key set validated.

## CSS modules typing

```typescript
const styles = {
  button: "btn_primary",
  typo: "btn_primry", // error caught
} satisfies Record<"button" | "link", string>;
```

## ESLint consistent-type-assertions

Ban `as Foo` on object literals where satisfies applies — lint rule in strict teams.

## Migration from annotations

Codemod not perfect — search `: Theme = {` replace with `= { ... } satisfies Theme` incrementally.

`satisfies` belongs in every config-heavy TypeScript codebase — enable strictest benefit without literal widening tax."""

EXPANSIONS["typescript-strict-mode-migration"] = r"""

## strictNullChecks and React

Optional props: `name?: string` vs `name: string | undefined` — align with exactOptionalPropertyTypes if enabled later.

## Third-party types

```typescript
declare module "legacy-lib" {
  export function fetch(): unknown;
}
```

Wrap untyped deps — shrink @ts-expect-error surface.

## CI typecheck split

```json
"scripts": {
  "typecheck": "tsc --noEmit",
  "typecheck:strict": "tsc -p tsconfig.strict.json --noEmit"
}
```

Track strict project error count trending down.

## Onboarding new hires

Strict codebase — fewer runtime surprises; document migration history so they do not reintroduce any patterns.

## strictBindCallApply

Rare issues in event handler binding — fix with arrow functions in class fields.

Migration completes when strict tsconfig is default and legacy config deleted — ceremony matters for team morale."""

EXPANSIONS["typescript-utility-types-app-patterns"] = r"""

## NonNullable and Extract

```typescript
type NonNullUser = NonNullable<User | null>;
type ErrorCode = Extract<ApiError, { kind: "error" }>["code"];
```

## Parameters and ConstructorParameters

Wrap API handlers with typed deps:

```typescript
type RepoDeps = ConstructorParameters<typeof UserRepository>[0];
```

## Awaited for async returns

```typescript
type UserDto = Awaited<ReturnType<typeof fetchUser>>;
```

## Branded IDs with utility base

```typescript
type UserId = string & { readonly brand: unique symbol };
type User = { id: UserId; name: string };
type UserPublic = Pick<User, "id" | "name">;
```

## Zod + utility types

Infer from schema, Pick for public fields:

```typescript
const UserSchema = z.object({ id: z.string(), email: z.string(), secret: z.string() });
type User = z.infer<typeof UserSchema>;
type PublicUser = Pick<User, "id" | "email">;
```

Utility types keep DRY types honest — pair with runtime validation at boundaries for end-to-end safety."""
