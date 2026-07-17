---
title: "Testing Compose UIs With the New v2 Testing APIs"
slug: "testing-compose-uis-v2"
description: "A practical guide to testing Jetpack Compose UIs: the semantics tree, ComposeTestRule, finders and assertions, synchronization, and how to write tests that don't flake."
datePublished: "2026-04-24"
dateModified: "2026-07-17"
tags:
  - "Android"
  - "Jetpack Compose"
  - "Testing"
  - "Kotlin"
keywords: "Compose testing, UI testing Android, Compose test APIs, Compose UI tests, semantics, ComposeTestRule, test tags"
faq:
  - q: "q"
    a: "a"
  - q: "q"
    a: "a"
  - q: "q"
    a: "a"
---

Compose testing looks alien the first time you see it because there are no view IDs to find. Instead of `onView(withId(R.id.button))`, you query a **semantics tree** — a parallel representation of your UI built for accessibility and testing. Once that clicks, Compose tests are more expressive and less flaky than the Espresso tests they replace, precisely because they hook into the framework's own idea of "the UI is idle now."

I've migrated large Espresso suites to Compose testing on production apps, and the tests that survived were the ones that stopped guessing at timing and let the framework synchronize. Here's the model, the API surface worth knowing, and the habits that keep a suite green.

## The semantics tree is your query target

Every composable can contribute **semantics** — properties like text, content description, role, toggle state, and whether it's clickable. Your tests navigate this tree. That's why accessible UIs are also testable UIs: the same content descriptions a screen reader uses are what your finders match against.

When there's no natural semantic to match — a decorative container, an icon among several identical ones — attach an explicit tag:

```kotlin
Button(
    onClick = onSubmit,
    modifier = Modifier.testTag("submit_button"),
) { Text("Submit") }
```

Prefer matching by **user-visible text or content description** where you can, because those tests double as accessibility checks. Reach for `testTag` when the alternative is a brittle match against layout structure.

## The test rule and the three-step rhythm

Every Compose test follows the same shape: set content, find a node, act or assert.

```kotlin
class LoginScreenTest {
    @get:Rule val composeRule = createComposeRule()

    @Test
    fun submitButton_disabledUntilFormValid() {
        composeRule.setContent {
            LoginScreen(state = LoginState(email = "", password = ""))
        }

        composeRule.onNodeWithTag("submit_button").assertIsNotEnabled()

        composeRule.onNodeWithContentDescription("Email")
            .performTextInput("me@example.com")
        composeRule.onNodeWithContentDescription("Password")
            .performTextInput("hunter2")

        composeRule.onNodeWithTag("submit_button").assertIsEnabled()
    }
}
```

`createComposeRule()` runs on the JVM (with Robolectric) and is fast enough to keep in your unit test set. When you need a real Activity — say you're testing navigation or system interactions — swap to `createAndroidComposeRule<MainActivity>()`, which runs instrumented on a device or emulator.

## Finders, assertions, and actions

The API is small and composable. Three families cover almost everything:

| Category | Examples |
| --- | --- |
| Finders | `onNodeWithText`, `onNodeWithContentDescription`, `onNodeWithTag`, `onAllNodes` |
| Assertions | `assertIsDisplayed`, `assertIsEnabled`, `assertTextEquals`, `assertIsSelected` |
| Actions | `performClick`, `performTextInput`, `performScrollTo`, `performTouchInput` |

Matchers compose with boolean operators, which is how you disambiguate when several nodes share text:

```kotlin
composeRule.onNode(
    hasText("Delete") and hasClickAction() and isEnabled()
).performClick()
```

For lists, `onNodeWithText(...).performScrollTo()` brings an off-screen item into view before you act on it — no manual scrolling loops.

## Synchronization: the thing that kills flakiness

The most important idea in Compose testing is **automatic synchronization**. Between each test action, the rule waits until the UI is idle — no pending recompositions, no running animations, no outstanding work registered with the test clock. That's why you should almost never write `Thread.sleep`. It doesn't help and it makes tests slower and flakier.

When you genuinely need to wait for a condition — a network result driving state — use `waitUntil`:

```kotlin
composeRule.waitUntil(timeoutMillis = 5_000) {
    composeRule.onAllNodesWithTag("result_row").fetchSemanticsNodes().isNotEmpty()
}
```

For animations, take manual control of the clock rather than sleeping:

```kotlin
composeRule.mainClock.autoAdvance = false
composeRule.onNodeWithTag("fab").performClick()
composeRule.mainClock.advanceTimeBy(300) // step the animation deterministically
composeRule.onNodeWithText("Menu").assertIsDisplayed()
```

Controlling `mainClock` is how you make animation-dependent tests deterministic instead of timing-dependent. This is the single biggest lever for a stable suite.

## Structuring a suite that scales

A few conventions that paid off on large codebases:

- **Test the state, not the pixels.** Because the screens I build render from a single immutable `UiState` (see [my Compose lessons](https://blog.michaelsam94.com/jetpack-compose-lessons-10-years-android/)), most tests just feed a state and assert what renders. That's fast and stable.
- **Keep composables stateless.** A stateless composable is trivially testable — you pass inputs and lambdas and verify output. Hoisted state means you rarely need a ViewModel in a UI test at all.
- **Use screenshot tests for the visual layer.** Semantics tests verify behavior; they don't catch a broken layout. Pair them with a screenshot testing tool (Paparazzi or Roborazzi) so both correctness and appearance are covered.
- **Print the tree when lost.** `composeRule.onRoot().printToLog("TREE")` dumps the semantics tree to logcat, which is how you figure out why a finder matched nothing.
- **Keep tags meaningful and stable.** Treat `testTag` values like a small API; renaming them randomly breaks tests for no reason.

## Where it fits in the pyramid

Compose UI tests are the middle of the testing pyramid — more expensive than pure logic unit tests, cheaper and more reliable than full end-to-end flows. I lean heavily on stateless-composable tests with `createComposeRule` because they run on the JVM in CI in seconds, then keep a thin layer of instrumented tests for the handful of flows that touch real system behavior. If you want the broader philosophy on how much of each to write, I laid it out in [testing pyramid vs trophy](https://blog.michaelsam94.com/testing-pyramid-vs-trophy/).

The framework does the hard part — knowing when the UI is settled — as long as you don't fight it. Match by semantics, let it synchronize, control the clock when you must, and Compose tests become the cheapest confidence you can buy per line.

## Semantics and test tags

Compose UI tests should assert semantics (content description, role) over pixel position. Use `testTag` sparingly — prefer user-visible properties. Synchronization with idling resources prevents flaky interactions; register custom idling for animations and async loads. Robolectric covers logic; device tests cover touch targets and real rendering. Screenshot tests complement semantics tests for visual regressions layout alone won't catch.

## Screenshot and semantics together

Semantics tests catch broken behavior; screenshot tests catch visual regressions Compose semantics miss — gradient backgrounds, padding shifts. Keep screenshot scope to design-system components, not full screens with dynamic timestamps.

## Resources

- [Testing your Compose layout — official guide](https://developer.android.com/develop/ui/compose/testing)
- [Compose testing cheat sheet](https://developer.android.com/develop/ui/compose/testing/testing-cheatsheet)
- [Semantics in Compose](https://developer.android.com/develop/ui/compose/semantics)
- [Synchronization in Compose tests](https://developer.android.com/develop/ui/compose/testing/synchronization)
- [Roborazzi — JVM screenshot testing](https://github.com/takahirom/roborazzi)
- [Robolectric](https://robolectric.org/)

## testing compose uis v2 rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## testing compose uis v2 rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## testing compose uis v2 rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## testing compose uis v2 rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## testing compose uis v2 rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## testing compose uis v2 rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## testing compose uis v2 rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## testing compose uis v2 rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## testing compose uis v2 rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## testing compose uis v2 rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## testing compose uis v2 rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## testing compose uis v2 rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

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

Compose UI tests pay off when semantics are designed alongside UI — not bolted on after release.
