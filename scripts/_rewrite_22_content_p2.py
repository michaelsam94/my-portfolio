# Part 2: Testing articles (8)

POSTS = {}

POSTS["testing-compose-uis-v2"] = (
    {
        "title": "Testing Compose UIs With the New v2 Testing APIs",
        "description": "A practical guide to testing Jetpack Compose UIs: the semantics tree, ComposeTestRule, finders and assertions, synchronization, and how to write tests that don't flake.",
        "datePublished": "2026-04-24",
        "tags": ["Android", "Jetpack Compose", "Testing", "Kotlin"],
        "keywords": "Compose testing, UI testing Android, Compose test APIs, Compose UI tests, semantics, ComposeTestRule, test tags",
        "faq": [
            {
                "q": "How do Compose UI tests find elements without view IDs?",
                "a": "Compose tests query the semantics tree, not view IDs. You match nodes by text, content description, role, or an explicit testTag you attach via Modifier.testTag, then assert or act on the resulting node.",
            },
            {
                "q": "Do I need an emulator to test Compose UIs?",
                "a": "Not always. Instrumented tests with createAndroidComposeRule run on a device or emulator, but many pure-Compose tests run on the JVM with Robolectric via createComposeRule, which is far faster in CI.",
            },
            {
                "q": "Why are my Compose tests flaky?",
                "a": "Most flakiness comes from fighting the test clock. Avoid Thread.sleep, let Compose auto-synchronize on idle, and when you drive animations or coroutines manually use mainClock and waitUntil instead of arbitrary delays.",
            },
        ],
    },
    r"""Compose UI tests that asserted pixel coordinates broke on every font scale change. Tests that queried `R.id.title` never worked — Compose is not the View system. The v2 testing APIs stabilize around the **semantics tree**: a parallel representation of what TalkBack sees and what your tests should target. When you test semantics instead of layout internals, refactors that change implementation but preserve behavior keep tests green.

## Semantics tree fundamentals

Compose merges layout nodes into semantic nodes when they expose meaning — text, buttons, toggles, headings. Tests interact through **`SemanticsNodeInteraction`**, not coordinates.

```kotlin
@Composable
fun LoginScreen(onSubmit: (String) -> Unit) {
    var email by remember { mutableStateOf("") }
    Column(Modifier.semantics { testTagsAsResourceId = true }) {
        OutlinedTextField(
            value = email,
            onValueChange = { email = it },
            modifier = Modifier.testTag("email_field"),
            label = { Text("Email") },
        )
        Button(
            onClick = { onSubmit(email) },
            modifier = Modifier.testTag("submit_button"),
        ) {
            Text("Sign in")
        }
    }
}
```

Prefer **`testTag`** for elements without stable user-visible text. Use **`contentDescription`** for icons. Reserve text queries for copy you expect to remain stable.

## ComposeTestRule setup

**Robolectric / JVM (fast unit UI tests):**

```kotlin
class LoginScreenTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun submitsEmail() {
        var captured = ""
        composeRule.setContent {
            LoginScreen { captured = it }
        }
        composeRule.onNodeWithTag("email_field").performTextInput("a@b.com")
        composeRule.onNodeWithTag("submit_button").performClick()
        assertEquals("a@b.com", captured)
    }
}
```

**Instrumented tests (navigation, real Context):**

```kotlin
@get:Rule
val composeRule = createAndroidComposeRule<MainActivity>()
```

Pick instrumented tests when you need real `Activity` lifecycle, permission dialogs, or Hilt injection graphs that Robolectric mocks poorly.

## Finders and assertions

| Matcher | Use when |
|---------|----------|
| `onNodeWithText` | Stable visible copy |
| `onNodeWithTag` | Internal test hooks |
| `onNodeWithContentDescription` | Icons, images |
| `onNodeWithRole(Role.Button)` | Accessibility-aligned queries |

```kotlin
composeRule.onNodeWithText("Sign in").assertIsEnabled()
composeRule.onNodeWithTag("loading_indicator").assertDoesNotExist()
composeRule.onNodeWithText("Error: invalid email").assertIsDisplayed()
```

Use **`assertIsNotDisplayed()`** vs **`assertDoesNotExist()`** deliberately — hidden-but-present differs from not composed.

## Synchronization without flakiness

Compose test framework **auto-waits** for idle before assertions. Flakes come from:

- **`Thread.sleep`** — replace with `composeRule.waitUntil`
- **Animations** — use `composeRule.mainClock.autoAdvance = true` or advance manually
- **Coroutines** — inject `TestDispatcher` in ViewModels

```kotlin
composeRule.waitUntil(timeoutMillis = 5_000) {
    composeRule.onAllNodesWithTag("list_item").fetchSemanticsNodes().size >= 3
}
```

For **`LazyColumn`**, scroll to item before assertion:

```kotlin
composeRule.onNodeWithTag("user_list")
    .performScrollToNode(hasText("Alice"))
composeRule.onNodeWithText("Alice").assertIsDisplayed()
```

## Testing ViewModels and state hoisting

Keep business logic in ViewModels tested with **`runTest`** and Turbine for `StateFlow`. UI tests verify wiring:

```kotlin
@Test
fun showsErrorWhenViewModelFails() {
    val fakeVm = FakeLoginViewModel(LoginUiState(error = "Network down"))
    composeRule.setContent {
        LoginScreen(viewModel = fakeVm)
    }
    composeRule.onNodeWithText("Network down").assertIsDisplayed()
}
```

Do not duplicate every ViewModel test at UI layer — one integration path per critical screen.

## Accessibility as test contract

If tests only use testTags, you can ship inaccessible UI. Combine tags with role checks:

```kotlin
composeRule.onNode(hasClickAction() and hasText("Delete")).assertIsDisplayed()
```

Run **`printToLog()`** on semantics tree when debugging finder failures — output shows merged nodes and properties.

## CI configuration

- Shard instrumented tests by module; keep Robolectric suite under 5 minutes.
- Disable animations on CI emulators: `testInstrumentationRunnerArguments["disableAnimations"] = "true"`.
- Fail on **`FlakyTest`** annotations accumulating — fix or quarantine with ticket.

## Anti-patterns

- Testing private composables directly instead of screen API.
- Matching regex text on dynamic timestamps.
- Sharing testTags as string constants without `@VisibleForTesting` documentation.
- Using `createAndroidComposeRule` for every test — CI time explodes.

Compose v2 testing rewards the same discipline as React Testing Library: interact like a user, query stable semantics, let the framework synchronize. Layout details change; meaning should not.""",
)

POSTS["testing-mutation-testing"] = (
    {
        "title": "Mutation Testing for Test Quality",
        "description": "Mutation testing injects bugs into your code to verify tests actually catch them. Measure test suite effectiveness beyond line coverage with Stryker and PIT.",
        "datePublished": "2025-12-30",
        "tags": ["Testing", "Mutation Testing", "Quality", "Engineering"],
        "keywords": "mutation testing, Stryker mutation testing, PIT mutation testing, test quality metrics, mutation score, code coverage vs mutation testing",
        "faq": [
            {
                "q": "What is mutation testing and how does it differ from code coverage?",
                "a": "Code coverage measures which lines executed during tests. Mutation testing mutates source code — changing a conditional, removing a negation — and checks if tests fail. High coverage with low mutation score means tests execute code without asserting behavior. Mutation testing measures test effectiveness, not execution.",
            },
            {
                "q": "What is a good mutation score?",
                "a": "Teams often target 70–85% mutation score on core domain modules as a starting gate. 100% is expensive and may require equivalent mutants. Track trend over time rather than absolutes — a drop after a refactor signals missing assertions, not necessarily bad code.",
            },
            {
                "q": "Which tools run mutation tests in CI?",
                "a": "JavaScript/TypeScript uses Stryker Mutator. Java uses PIT (PITest). .NET has Stryker.NET. Python has mutmut. Run on changed files in PR CI for speed; nightly full runs on payment and auth modules where bug cost is highest.",
            },
        ],
    },
    r"""We had 92% line coverage on the pricing module. A one-character typo in a discount cap shipped to production because every test called `calculateTotal()` but only asserted the function returned *something* — not the correct number. Mutation testing would have changed `>` to `>=` and watched tests stay green. Coverage counted lines; it did not count whether anyone was looking.

## How mutation testing works

1. **Mutate** source — small syntactic change simulating realistic bug.
2. **Run tests** — if tests fail, mutant is **killed** (good).
3. If tests pass, mutant **survived** — gap in assertions or dead code.

Example mutant on JavaScript:

```javascript
// Original
if (discount > 100) throw new Error("cap");

// Mutant: replace > with >=
if (discount >= 100) throw new Error("cap");
```

A test calling `calculate({ discount: 50 })` without boundary assertion lets this survive.

| Term | Meaning |
|------|---------|
| Mutation score | killed / (killed + survived) |
| Equivalent mutant | Behavior-preserving change — false positive |
| Timeout | Test hung — often killed conservatively |

## Stryker for TypeScript

```bash
npm install -D @stryker-mutator/core @stryker-mutator/vitest-runner
npx stryker init
```

```json
// stryker.config.json
{
  "testRunner": "vitest",
  "mutate": ["src/pricing/**/*.ts"],
  "thresholds": { "high": 80, "low": 70, "break": 65 },
  "ignoreMutators": ["StringLiteral"]
}
```

Stryker runs tests in parallel per mutant — CPU heavy. Scope to changed files in PR:

```bash
npx stryker run --incremental
```

## PIT for Java/Kotlin

Maven plugin on domain modules:

```xml
<plugin>
  <groupId>org.pitest</groupId>
  <artifactId>pitest-maven</artifactId>
  <configuration>
    <targetClasses>
      <param>com.example.billing.*</param>
    </targetClasses>
    <mutationThreshold>75</mutationThreshold>
  </configuration>
</plugin>
```

PIT integrates with JUnit 5 and TestNG; historical line coverage correlation helps prioritize survivors.

## Interpreting survivors

Survived mutant categories:

- **Missing assertion** — most common fix.
- **Weak assertion** — `toBeTruthy()` instead of exact value.
- **Untested branch** — else path never executed meaningfully.
- **Equivalent mutant** — document and exclude with `# pitest: off` sparingly.

Fix by strengthening tests, not weakening production code to game score.

```typescript
// Before — survivor on boundary mutant
expect(calculateTotal({ discount: 100 })).toBeDefined();

// After — kills boundary mutants
expect(() => calculateTotal({ discount: 100 })).toThrow(/cap/);
expect(calculateTotal({ discount: 99 })).toBe(891);
```

## CI strategy

Full mutation runs are slow. Practical pipeline:

1. **PR**: Stryker incremental on touched packages — 10–15 min budget.
2. **Nightly**: full billing, auth, permissions modules.
3. **Gate**: fail if mutation score drops >5 points from baseline.

Store Stryker report as artifact; dashboard trend like coverage in SonarQube (mutation score plugin).

## Cost vs value

Run mutation testing on:

- Pricing, tax, permissions
- Crypto and auth token validation
- Parsing and serialization with security impact

Skip or sample on:

- Generated protobuf glue
- UI layout-only components (use visual regression instead)
- Config DTOs with no logic

## Limitations

- Flaky tests cause false kills/timeouts — stabilize first.
- Equivalent mutants waste cycles — manual review or Stryker `mutator.excludedMutations`.
- Does not replace E2E — kills unit gaps, not integration wiring.

Mutation testing is adversarial QA for your test suite. It hurts CI time where it matters and answers the question coverage evades: **if I introduced a one-line bug, would anyone notice before production?**""",
)

POSTS["testing-playwright-e2e"] = (
    {
        "title": "End-to-End Testing with Playwright",
        "description": "Playwright runs reliable browser tests across Chromium, Firefox, and WebKit with auto-waiting, network interception, and parallel execution. Patterns for maintainable E2E test suites.",
        "datePublished": "2026-01-02",
        "tags": ["Testing", "Playwright", "E2E", "Frontend"],
        "keywords": "Playwright E2E testing, end-to-end testing, browser automation, Playwright auto-wait, Playwright page object model, cross-browser testing",
        "faq": [
            {
                "q": "Why is Playwright more stable than Selenium for E2E tests?",
                "a": "Playwright auto-waits for elements to be actionable before clicks and fills, uses modern browser automation protocols (CDP, WebDriver BiDi), and bundles browser binaries with version lockstep. Selenium tests often fail on timing because explicit waits are manual and flaky. Playwright's locators retry until timeout by default.",
            },
            {
                "q": "How many E2E tests should a team maintain?",
                "a": "Cover critical user journeys only — signup, login, checkout, core workflow — typically tens of tests, not hundreds. E2E tests are slow and brittle at scale; push detail to unit and integration layers. Playwright shines on smoke and regression paths that justify real browser cost.",
            },
            {
                "q": "Should E2E tests run against production?",
                "a": "Run synthetic monitoring against production with read-only flows and dedicated test accounts. Full mutating E2E belongs in staging with production-like data. Never run destructive tests against prod; isolate test data and use feature flags to route test traffic.",
            },
        ],
    },
    r"""Selenium tests failed on "element not clickable" at 2 AM because a cookie banner animated in after the wait ended. Migrating the smoke suite to Playwright cut flaky failures from 23% to under 2% in six weeks — not because browsers got faster, but because locators auto-wait for actionability and trace files show exactly what the page looked like on failure. E2E tests should be few, fast enough for CI, and ruthless about scope.

## Project setup

```bash
npm init playwright@latest
```

```typescript
// playwright.config.ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
  ],
});
```

Run against **`next build && next start`** or staging — not `next dev` with HMR noise.

## Locators over selectors

Prefer user-facing locators:

```typescript
import { test, expect } from "@playwright/test";

test("checkout flow", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Shop" }).click();
  await page.getByRole("button", { name: "Add to cart" }).first().click();
  await page.getByRole("link", { name: "Cart" }).click();
  await expect(page.getByRole("heading", { name: "Your cart" })).toBeVisible();
  await page.getByRole("button", { name: "Checkout" }).click();
  await expect(page).toHaveURL(/checkout/);
});
```

Avoid `page.locator(".btn-primary:nth-child(3)")` — CSS structure changes break tests without user impact.

## Network control

Stub third parties and speed tests:

```typescript
await page.route("**/analytics/**", (route) => route.abort());
await page.route("**/api/products", async (route) => {
  await route.fulfill({ json: [{ id: "1", name: "Widget", price: 19.99 }] });
});
```

Use **`page.waitForResponse`** when asserting post-submit API calls:

```typescript
const responsePromise = page.waitForResponse("**/api/orders");
await page.getByRole("button", { name: "Place order" }).click();
expect((await responsePromise).ok()).toBeTruthy();
```

## Authentication fixtures

Save storage state once, reuse across tests:

```typescript
// auth.setup.ts
import { test as setup } from "@playwright/test";

setup("authenticate", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(process.env.E2E_USER!);
  await page.getByLabel("Password").fill(process.env.E2E_PASS!);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.context().storageState({ path: ".auth/user.json" });
});
```

```typescript
// playwright.config.ts
projects: [
  { name: "setup", testMatch: /auth.setup.ts/ },
  {
    name: "chromium",
    dependencies: ["setup"],
    use: { storageState: ".auth/user.json" },
  },
],
```

## Page object model — lightweight

Group locators and actions, not inheritance towers:

```typescript
export class CheckoutPage {
  constructor(private page: Page) {}
  async fillShipping(address: string) {
    await this.page.getByLabel("Address").fill(address);
  }
  async submit() {
    await this.page.getByRole("button", { name: "Pay now" }).click();
  }
}
```

## Debugging failures

```bash
npx playwright test --ui
npx playwright show-trace trace.zip
```

Trace viewer shows DOM snapshots, network, console — replace screenshot archaeology.

## CI practices

- Shard by project: `npx playwright test --shard=1/4`
- Set **`workers`** proportional to CPU
- Upload traces on failure in GitHub Actions
- Tag smoke: `@smoke` grep for PR gate; full suite nightly

## What not to E2E

- Every form validation rule — unit test Zod schemas.
- Pixel-perfect layout — visual snapshot subset only.
- API error matrix — contract tests with MSW.

Playwright E2E is insurance on journeys that pay the bills. Auto-waiting, traces, and disciplined scope make that insurance affordable.""",
)

POSTS["testing-property-based-testing"] = (
    {
        "title": "Property-Based Testing",
        "description": "Property-based testing generates hundreds of random inputs to verify universal properties hold. Find edge cases unit tests miss with QuickCheck, Hypothesis, and jqwik.",
        "datePublished": "2026-01-06",
        "tags": ["Testing", "Property-Based Testing", "Quality", "Engineering"],
        "keywords": "property-based testing, Hypothesis Python, QuickCheck Haskell, jqwik Java, generative testing, test properties not examples",
        "faq": [
            {
                "q": "What is a property in property-based testing?",
                "a": "A property is an invariant that must hold for all valid inputs — not a single expected output. Examples: sorting is idempotent, encode then decode equals original, addition is commutative. The framework generates hundreds of random inputs attempting to falsify the property, shrinking failures to minimal counterexamples.",
            },
            {
                "q": "When should I use property-based tests instead of example tests?",
                "a": "Use properties for pure functions with clear invariants — parsers, serializers, math, data structure operations, encoders. Use example tests for specific regression bugs and integration paths. Combine both: examples document known cases, properties explore unknown edge cases.",
            },
            {
                "q": "How does shrinking work in Hypothesis and QuickCheck?",
                "a": "When a random input fails, the framework simplifies it — smaller arrays, simpler strings — until it finds a minimal failing case. That counterexample is what you debug, not the original 500-element array. Shrinking turns chaotic failures into actionable bugs.",
            },
        ],
    },
    r"""Unit tests for `parseAmount` covered `"19.99"`, `"0"`, and `"-1"`. Production crashed on `"19.99 EUR"` because nobody tested currency suffixes. Property-based testing would have generated `"abc"`, `""`, very long strings, and unicode — and shrunk failure to the smallest string that broke parsing. Examples test what you imagine; properties test what you forgot.

## Properties vs examples

**Example test:** known input → known output.

**Property test:** forall valid inputs → invariant holds.

```python
from hypothesis import given, strategies as st

def encode_decode_roundtrip(data: bytes) -> bytes:
    return decode(encode(data))

@given(st.binary())
def test_encode_decode_roundtrip(data):
    assert decode(encode(data)) == data
```

```typescript
// fast-check
import fc from "fast-check";

test("sort is idempotent", () => {
  fc.assert(
    fc.property(fc.array(fc.integer()), (arr) => {
      const once = sort(arr);
      const twice = sort(once);
      expect(twice).toEqual(once);
    })
  );
});
```

## Common property patterns

| Property | Statement |
|----------|-----------|
| Roundtrip | `decode(encode(x)) == x` |
| Idempotence | `f(f(x)) == f(x)` |
| Commutativity | `f(a,b) == f(b,a)` |
| Inverse | `add(a,b) - b == a` |
| Oracle comparison | slow_reference(x) == optimized(x) |

## Hypothesis strategies

Build constrained generators:

```python
@given(st.emails())
def test_email_normalization(email):
    normalized = normalize_email(email)
    assert "@" in normalized
    assert normalized == normalized.lower()

@given(st.decimals(min_value=0, max_value=1_000_000, places=2))
def test_tax_never_exceeds_amount(amount):
    tax = calculate_tax(amount)
    assert 0 <= tax <= amount
```

Custom strategies for domain types:

```python
valid_sku = st.from_regex(r"[A-Z]{3}-\d{4}", fullmatch=True)
```

## jqwik for Java/Kotlin

```kotlin
@Property
fun reverseTwiceIsOriginal(@ForAll list: List<Int>) {
    assertEquals(list, list.reversed().reversed())
}
```

Integrates with JUnit 5; runs in CI like unit tests.

## Shrinking in action

Failure might start as `[9999, -42, 0, 88888]`. Shrinking reduces to `[0, -1]` — the minimal counterexample. Fix the bug, add regression example if useful:

```python
@given(st.integers())
def test_divide_non_zero(b):
    assume(b != 0)
    assert multiply(divide(100, b), b) == 100
```

**`assume()`** filters invalid inputs without counting as failure.

## Where properties shine

- JSON/MessagePack serializers
- Sorting and merge algorithms
- Date/time timezone conversions
- Permission matrix evaluation
- Compression codecs

## Where to be careful

- Nondeterministic code — inject clocks and random seeds.
- Tests with external IO — use properties on pure core, fake ports.
- Overly loose properties (`result is not None`) — tautologies waste CPU.

## CI configuration

- Default example count 100; increase locally with `--hypothesis-profile=dev`.
- Seed failures: `@settings(reproduce_failure=...)`.
- Time-box: `@settings(max_examples=50, deadline=200)` per property.

Property-based testing is fuzzing with academic manners — generators, shrinking, and invariants instead of random byte spray. Use it wherever a single clever counterexample would become a Sev-1.""",
)

POSTS["testing-snapshot-testing-tradeoffs"] = (
    {
        "title": "Snapshot Testing Trade-offs",
        "description": "Snapshot tests capture component output and detect unintended changes. Learn when snapshots help, when they hurt, and how to use them without creating maintenance nightmares.",
        "datePublished": "2026-01-10",
        "tags": ["Testing", "Snapshot Testing", "Frontend", "Quality"],
        "keywords": "snapshot testing, Jest snapshots, snapshot test trade-offs, visual regression testing, snapshot test maintenance, inline snapshots",
        "faq": [
            {
                "q": "When are snapshot tests valuable?",
                "a": "Snapshots help for stable serialized output — React component HTML, GraphQL responses, config generation, error message formatting. They catch unintended diffs when refactoring plumbing if the public output should not change. They fail loudly when someone updates UI without conscious review.",
            },
            {
                "q": "Why do snapshot tests get a bad reputation?",
                "a": "Teams snapshot entire pages, commit 10,000-line diffs, and blindly run update snapshots on every PR. That trains reviewers to ignore failures. Snapshots without scope become noise; small intentional changes require painful rebases.",
            },
            {
                "q": "What is the alternative to large component snapshots?",
                "a": "Prefer targeted assertions with Testing Library, inline snapshots of small strings, or dedicated visual regression tools (Chromatic, Percy) for CSS. Snapshot subcomponents with stable contracts, not whole app trees. Review snapshot diffs in PR like production code.",
            },
        ],
    },
    r"""The PR changed a button margin. The diff included 847 lines of snapshot updates because someone snapshotted the entire dashboard tree six months ago. Reviewers clicked approve without reading. A week later, a missing error banner shipped — the snapshot had updated away the assertion that mattered. Snapshot testing is not bad; **unbounded snapshot testing** is technical debt with a Jest command.

## How snapshot tests work

Render component or serialize output → compare to committed `.snap` file:

```tsx
import { render } from "@testing-library/react";
import { Alert } from "./Alert";

test("renders error alert", () => {
  const { container } = render(<Alert type="error" message="Payment failed" />);
  expect(container.firstChild).toMatchSnapshot();
});
```

First run writes snapshot; subsequent runs diff. **`toMatchInlineSnapshot()`** embeds small strings in the test file:

```tsx
expect(formatError("TIMEOUT")).toMatchInlineSnapshot(`"Request timed out after 30s"`);
```

Inline snapshots excel for pure functions with short output.

## When snapshots help

| Good fit | Why |
|----------|-----|
| Serializer output | JSON/XML structure regression |
| Error messages | Copy changes intentional review |
| Small presentational components | Stable markup contract |
| CLI `--help` text | Docs drift detection |

## When snapshots hurt

| Bad fit | Why |
|---------|-----|
| Entire pages | Huge diffs, CSS noise |
| Components with dates/random IDs | Flaky without mocking |
| Rapidly designed UI | Every design tweak breaks CI |
| Business logic | Assert values, not dumps |

## Discipline for sustainable snapshots

1. **Snapshot the smallest stable unit** — `Alert`, not `CheckoutPage`.
2. **Pair with semantic assertions** — snapshot plus `expect(screen.getByRole(...)).toBeVisible()`.
3. **Forbid blind `-u` in CI** — updates happen locally with reviewed diffs.
4. **Limit file size** — if snap > 50 lines, split or replace with explicit asserts.

```tsx
test("success alert structure", () => {
  render(<Alert type="success" message="Saved" />);
  expect(screen.getByRole("alert")).toHaveClass("alert-success");
  expect(screen.getByText("Saved")).toBeInTheDocument();
  // optional small inline snapshot for icon markup only
});
```

## Visual regression vs DOM snapshots

DOM snapshots ignore CSS from stylesheets in many setups — className changes may not reflect visual truth. **Chromatic / Percy** compare pixels for design systems; use sparingly on component library, not every screen.

## Vitest and Jest snapshot hygiene

```typescript
// vitest.config.ts
test: {
  snapshotFormat: { printBasicPrototype: false },
}
```

Normalize unstable attributes:

```tsx
expect(container.innerHTML.replace(/id="[^"]+"/g, 'id="stable"')).toMatchSnapshot();
```

Prefer mocking **`Date.now`** and UUIDs at module boundary.

## Review workflow

Treat snapshot file changes like logic changes:

- PR description explains why output changed.
- Designer sign-off for visual snapshot repos.
- Reject PRs where snapshot is only change without explanation.

## Migration off snapshot debt

1. Identify top 10 largest snap files.
2. Replace with Testing Library queries for behavior.
3. Keep one golden snapshot per component if markup contract matters externally (email HTML).

Snapshot testing is a **regression camera**, not a substitute for thinking. Point it at stable outputs you would manually verify anyway — and keep the lens narrow enough that when the shutter clicks, someone actually looks at the photo.""",
)

POSTS["testing-test-data-builders"] = (
    {
        "title": "Test Data Builders and Object Mothers",
        "description": "Test data builders create valid test objects with sensible defaults and fluent overrides. Object mothers provide named factory methods for common scenarios. Both reduce test setup boilerplate.",
        "datePublished": "2026-01-14",
        "tags": ["Testing", "Test Patterns", "Quality", "Engineering"],
        "keywords": "test data builder pattern, object mother pattern, test fixtures, factory pattern testing, test object creation, builder vs object mother",
        "faq": [
            {
                "q": "What is the difference between a test builder and an object mother?",
                "a": "A builder provides a fluent API to construct objects with defaults and optional overrides — UserBuilder.withAdmin().build(). An object mother exposes named factory methods for common scenarios — UserMother.adminUser(), UserMother.expiredTrialUser(). Builders scale when combinations explode; mothers stay readable for fixed personas.",
            },
            {
                "q": "Should test data builders share production validation logic?",
                "a": "Builders should create structurally valid objects that satisfy domain invariants, often calling the same constructors or factories as production. Avoid importing heavy production wiring — keep builders in test source. If production validation changes, failing builder tests signal tests need updating.",
            },
            {
                "q": "How do builders help prevent brittle tests?",
                "a": "Centralizing defaults means adding a required field to User updates one builder default instead of 200 tests. Tests override only fields relevant to the scenario — readableArrange sections show intent. Randomized builders (faker) plus fixed seeds combine variety with reproducibility.",
            },
        ],
    },
    r"""Every test file duplicated a twelve-field `User` literal. When `timezone` became required, CI exploded with 400 compile errors. Test data builders consolidate defaults in one place; tests override only what matters for the scenario. **`UserBuilder().withRole("admin").build()`** reads better than anonymous JSON blobs — and documents intent for the next engineer.

## Builder pattern

```typescript
class UserBuilder {
  private data: Partial<User> = {
    id: "user-1",
    email: "test@example.com",
    role: "member",
    timezone: "UTC",
    createdAt: new Date("2026-01-01"),
  };

  withEmail(email: string) {
    this.data.email = email;
    return this;
  }

  withRole(role: Role) {
    this.data.role = role;
    return this;
  }

  build(): User {
    return UserSchema.parse(this.data); // reuse validation
  }
}

// in test
const admin = new UserBuilder().withRole("admin").build();
```

Fluent **`return this`** enables chaining. **`build()`** validates — invalid test data fails at construction, not mysteriously in assertion.

## Object mother pattern

```typescript
export const UserMother = {
  regular: () => new UserBuilder().build(),
  admin: () => new UserBuilder().withRole("admin").build(),
  expiredTrial: () =>
    new UserBuilder()
      .withTrialEndsAt(subDays(new Date(), 1))
      .build(),
};
```

Mothers name **business scenarios** — tests read `UserMother.expiredTrial()` without scanning field lists.

| Pattern | Best for |
|---------|----------|
| Builder | Many optional field combinations |
| Object mother | Fixed personas, readable tests |
| Factory function | Simple objects, few variants |

## Kotlin/Java builders

```kotlin
data class OrderBuilder(
    var id: String = "ord-1",
    var total: BigDecimal = BigDecimal("99.00"),
    var status: Status = Status.PENDING,
) {
    fun build() = Order(id, total, status)
}

@Test
fun refundsPendingOrder() {
    val order = OrderBuilder(status = Status.PENDING).build()
    ...
}
```

## Randomized data with seeds

```typescript
import { faker } from "@faker-js/faker";

faker.seed(12345);

function randomUserBuilder() {
  return new UserBuilder().withEmail(faker.internet.email());
}
```

Seed fixes failure reproduction in CI logs.

## Persistence-aware builders

For integration tests hitting DB:

```typescript
async function persistUser(overrides?: Partial<User>) {
  const user = new UserBuilder(overrides).build();
  return db.users.insert(user).returning();
}
```

Separate **domain builder** from **repository helper** to keep unit tests free of DB.

## Anti-patterns

- Builders that only work with magic IDs conflicting across parallel tests — use UUIDs.
- Shared mutable builder instance across tests — create fresh per test.
- Production code importing test builders — keep in `test/` or `__fixtures__`.
- Over-engineering DSL for three-field structs — simple factory function enough.

## Choosing builder vs mother

Start with factory function. Add builder when overrides multiply. Add object mother when same five personas repeat across suite.

Test data builders are documentation of valid domain states. Invest once; every test arranges faster and breaks less when the model evolves.""",
)

POSTS["testing-test-doubles-mocks-stubs"] = (
    {
        "title": "Mocks, Stubs, and Fakes",
        "description": "Test doubles explained: mocks vs stubs vs fakes vs spies, when to use each, mock overuse pitfalls, and testing without mocking the universe.",
        "datePublished": "2026-01-18",
        "tags": ["Testing", "Software Engineering", "Quality", "Architecture"],
        "keywords": "mocks stubs fakes, test doubles, Mockito, mock overuse, dependency injection testing, spy vs mock",
        "faq": [
            {
                "q": "What is the difference between a mock and a stub?",
                "a": "A stub returns canned responses to indirect inputs — you configure getUser(1) to return Alice. A mock verifies behavior — it asserts sendEmail was called once with orderId 42. Stubs test state/output; mocks test interactions. Overusing mocks couples tests to implementation details.",
            },
            {
                "q": "When should I use a fake instead of a mock?",
                "a": "Use fakes — working in-memory implementations — when behavior matters more than call counts. InMemoryUserRepository supports real query logic; mock repositories return null unless every method stubbed. Fakes enable integration-style tests without infrastructure.",
            },
            {
                "q": "How do I avoid mock-heavy brittle tests?",
                "a": "Test through public APIs with real collaborators where cheap. Mock only boundaries — HTTP clients, clock, random, external payment SDK. Prefer dependency injection over static mocks. If refactoring breaks dozens of mock expectations without behavior change, you mocked too deep.",
            },
        ],
    },
    r"""The test suite had 14 mocks for a function that added two numbers. Every refactor renamed internal methods and shattered mock expectations while user-visible behavior unchanged. Test doubles are tools, not defaults. Knowing when to stub, fake, or mock separates tests that protect refactoring from tests that freeze implementation archaeology.

## Taxonomy (Meszaros)

| Double | Purpose |
|--------|---------|
| Dummy | Fills parameter, never used |
| Stub | Canned answers to calls |
| Spy | Records calls for later assert |
| Mock | Pre-programmed expectations on behavior |
| Fake | Working simplified implementation |

## Stub example

```typescript
const paymentStub: PaymentGateway = {
  charge: async () => ({ status: "ok", id: "ch_123" }),
};

const result = await checkoutService.complete(order, paymentStub);
expect(result.paid).toBe(true);
```

No verification of `charge` call count — only output matters.

## Mock example (Vitest)

```typescript
const emailMock = vi.fn().mockResolvedValue(undefined);
const service = new OrderService(emailMock);

await service.placeOrder(order);

expect(emailMock).toHaveBeenCalledOnce();
expect(emailMock).toHaveBeenCalledWith(
  expect.objectContaining({ to: "buyer@example.com" })
);
```

Mocks assert **collaboration** — appropriate when side effect is the outcome (send email, charge card).

## Fake example

```typescript
class FakeUserRepo implements UserRepository {
  private users = new Map<string, User>();
  async save(user: User) { this.users.set(user.id, user); }
  async findById(id: string) { return this.users.get(id) ?? null; }
}

test("creates profile on signup", async () => {
  const repo = new FakeUserRepo();
  const service = new SignupService(repo);
  await service.signup({ email: "a@b.com" });
  expect(await repo.findById(expect.any(String))).toMatchObject({ email: "a@b.com" });
});
```

Fake supports multiple operations without configuring every method — scales better than deep mocks for domain logic.

## Mockito (Java) spies

```java
List<String> list = spy(new ArrayList<>());
list.add("one");
verify(list).add("one");
```

Spy wraps real object — partial mocking. Use sparingly; often signals class too big.

## What to mock at boundaries

Mock:

- External HTTP APIs
- System clock (`Clock.fixed`)
- UUID.random
- Message queues you do not own

Do not mock:

- Value objects
- Every repository in unit test — use fake
- Framework internals (React hooks) — test via UI

## MSW as stub boundary

```typescript
import { setupServer } from "msw/node";
import { http, HttpResponse } from "msw";

const server = setupServer(
  http.get("/api/user", () => HttpResponse.json({ id: "1", name: "Ada" }))
);

beforeAll(() => server.listen());
afterAll(() => server.close());
```

Network stub keeps components real while controlling data.

## Mock smell checklist

- Test fails when private method renamed — mocked too deep.
- More setup than assertion — missing fake or slice too wide.
- Identical mock setup copy-pasted — extract mother/builder.
- Cannot read test without opening mock file — simplify.

## Architecture enabler

Dependency injection without service locator makes doubles trivial:

```typescript
export function createApp(deps: { payments: PaymentGateway; clock: Clock }) {
  return new App(deps);
}
```

Production wires Stripe; tests wire stub.

Choose the **simplest double that proves the behavior**. Stubs for outputs, fakes for domain persistence, mocks for irreversible side effects — not for every object in the call graph.""",
)

POSTS["testing-unit-vs-integration-balance"] = (
    {
        "title": "Balancing Unit and Integration Tests",
        "description": "Finding the right unit vs integration test balance: testing pyramid critique, social tests, test boundaries, ROI by layer, and team-specific ratios.",
        "datePublished": "2026-01-22",
        "tags": ["Testing", "Software Engineering", "Architecture", "Quality"],
        "keywords": "unit vs integration tests, testing pyramid, testing trophy, test balance, integration test ROI, microservice testing strategy",
        "faq": [
            {
                "q": "Is the testing pyramid still valid?",
                "a": "The pyramid — many unit, fewer integration, few E2E — remains directionally correct but oversimplifies. Modern guidance (testing trophy, testing honeycomb) emphasizes integration tests with real databases and contract tests between services. The right ratio depends on architecture: functional core with imperative shell favors unit tests; CRUD microservices need integration coverage.",
            },
            {
                "q": "How do I decide what belongs in an integration test?",
                "a": "Integration tests verify wiring you cannot trust to unit tests alone — SQL queries, transaction boundaries, middleware ordering, serialization across process boundaries. One integration test per repository or API handler catches schema drift; duplicate twenty unit tests with mocked JDBC that never ran SQL.",
            },
            {
                "q": "What ratio of unit to integration tests should we target?",
                "a": "Do not target a global ratio — track confidence and CI time. Healthy teams often land 60–75% unit, 20–35% integration, 5–10% E2E for backend services, with frontend heavier on component tests. Measure escaped defects and flaky test rate; adjust layers that fail in production vs CI.",
            },
        ],
    },
    r"""We had 3,000 unit tests and zero that hit Postgres. Schema migration dropped a column; all tests green; production 500 on login. The pyramid poster on the wall said "mock the database." The poster was wrong for our architecture. Unit vs integration balance is not a moral question about purity — it is ROI on **where bugs actually live** in your system.

## Pyramid, trophy, honeycomb

**Pyramid:** many fast unit tests at base, fewer service tests, few UI E2E.

**Trophy (Kent C. Dodds):** emphasize integration via Testing Library — user behavior with real components, mock network not DOM.

**Honeycomb (microservices):** contract tests between services, limited E2E, solid integration at boundaries.

```
        / E2E \
       /-------\
      / Integr. \
     /-----------\
    /    Unit     \
```

Your shape depends on:

| Architecture | Emphasis |
|--------------|----------|
| Rich domain logic | Unit on pure functions |
| DB-heavy CRUD | Integration with real DB |
| Microservices | Contract + selective E2E |
| Frontend SPA | Component + MSW integration |

## Functional core, imperative shell

Push logic into pure functions — unit test without mocks:

```typescript
export function applyDiscount(subtotal: number, rules: Rule[]): number {
  return rules.reduce((total, rule) => rule.apply(total), subtotal);
}
```

Shell (DB, HTTP) gets thin integration tests:

```typescript
test("order repo persists line items", async () => {
  const db = await testDb();
  const repo = new OrderRepo(db);
  const id = await repo.create(sampleOrder());
  expect(await repo.findById(id)).toMatchObject({ status: "pending" });
});
```

## Testcontainers pattern

```typescript
const postgres = await new PostgreSqlContainer().start();
const pool = new Pool({ connectionString: postgres.getConnectionUri() });
afterAll(() => postgres.stop());
```

Real Postgres in CI — catches constraint and index bugs. Slower than H2; worth it for Postgres-specific SQL.

## When unit tests lie

- ORM query never executed — mock returned fixture.
- JSON serialization roundtrip untested — field rename silent.
- Auth middleware order wrong — unit tested handlers only.
- Race conditions — single-threaded unit fantasy.

One integration test per critical path often cheaper than ten mocked units.

## CI time budgeting

| Layer | Target time (indicative) |
|-------|--------------------------|
| Unit | < 3 min |
| Integration | < 10 min |
| E2E | < 20 min nightly |

Parallelize integration; use schema migrations once per suite.

## Social / approval tests

Snapshot golden files for complex reporting output — borderline integration. Useful for invoice PDF metadata, not every endpoint.

## Metrics that matter

Track:

- Production bugs that unit tests would not catch (tag in postmortem)
- Flaky test rate by layer
- Mean time to fix broken CI by layer

Adjust balance when integration escapes dominate.

## Anti-patterns

- **Ice cream cone** — many E2E, no unit — slow, flaky.
- **Mock universe** — every layer mocked — tests pass, system fails.
- **Ratio policing** — "must be 80% unit" — ignores risk.

Balance unit and integration tests by **fault domain**, not folklore. Mock at system boundaries; run real SQL for anything that touches migrations; keep pure logic in fast unit tests that document business rules.""",
)
