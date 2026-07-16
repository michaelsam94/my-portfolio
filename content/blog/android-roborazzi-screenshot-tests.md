---
title: "Roborazzi: Screenshot Tests on the JVM"
slug: "android-roborazzi-screenshot-tests"
description: "Roborazzi captures Compose and View screenshots on the JVM without an emulator. Set up golden images, handle font rendering differences, and integrate with CI for fast visual regression tests."
datePublished: "2024-08-06"
dateModified: "2024-08-06"
tags: ["Android", "Testing", "Compose", "Roborazzi"]
keywords: "Roborazzi, screenshot testing, Compose visual regression, JVM Android tests, golden images, Paparazzi alternative"
faq:
  - q: "How is Roborazzi different from Paparazzi?"
    a: "Both run screenshot tests on the JVM without a device or emulator. Roborazzi is maintained by Taku Semba and integrates tightly with AndroidX Test and Compose, using Robolectric's rendering pipeline. Paparazzi uses its own layoutlib fork. Roborazzi tends to track newer Compose versions quickly and supports compare-on-CI workflows with dedicated Gradle tasks."
  - q: "Why do screenshot tests fail on CI but pass locally?"
    a: "Font rendering, anti-aliasing, and locale defaults differ between macOS, Linux, and Windows JVM hosts. Roborazzi records golden images on one platform and compares pixel-by-pixel, so a Linux CI runner often rejects images recorded on a Mac. Fix this by recording goldens on the same OS as CI, or use Roborazzi's tolerance options for minor pixel drift."
  - q: "Can Roborazzi test Compose and traditional Views?"
    a: "Yes. Use captureRoboImage on Compose via ComposeTestRule, or RoborazziRule for Activities and Fragments. Hybrid apps can screenshot individual composables in isolation and full Activity layouts in integration-style tests."
---

Visual regressions slip through unit tests. A padding change, a Material theme token update, or a font scale edge case won't fail `assertIsDisplayed()`, but users see a broken layout immediately. Screenshot tests catch those diffs. Roborazzi lets you capture and compare UI images on the JVM — no emulator boot, no flaky Espresso idling — which makes visual regression practical enough to run on every PR.

## Why JVM screenshots

Instrumented screenshot tests on an emulator take 30–90 seconds per module and fight animation timing, system UI, and API-level skin differences. JVM-based tools render layouts through Robolectric's shadow framework in-process. A typical Roborazzi test completes in under two seconds.

I've migrated teams from manual QA screenshot checklists to Roborazzi and cut visual regression discovery time from "found in staging" to "failed in CI on the PR that introduced it."

## Setup

Add to your module's `build.gradle.kts`:

```kotlin
plugins {
    id("io.github.takahirom.roborazzi")
}

roborazzi {
    outputDir.set(file("src/test/resources/roborazzi"))
}

dependencies {
    testImplementation("io.github.takahirom.roborazzi:roborazzi:1.*")
    testImplementation("io.github.takahirom.roborazzi:roborazzi-compose:1.*")
    testImplementation("io.github.takahirom.roborazzi:roborazzi-junit-rule:1.*")
}
```

Use a consistent Robolectric SDK level — I default to `@Config(sdk = [33])` unless testing API-specific behavior.

## Compose screenshot test

```kotlin
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [33], qualifiers = "w400dp-h800dp-normal-long-notround-any-420dpi-keyshidden-nonav")
class ProfileCardScreenshotTest {

    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun profileCard_defaultState() {
        composeRule.setContent {
            MyAppTheme {
                ProfileCard(
                    name = "Alex Chen",
                    subtitle = "Staff Engineer",
                    avatarUrl = null
                )
            }
        }
        composeRule.onRoot()
            .captureRoboImage("screenshots/profile_card_default.png")
    }
}
```

`@GraphicsMode(NATIVE)` uses the real Android graphics pipeline instead of Robolectric's legacy software renderer, which matters for Compose blur, gradients, and vector drawables.

## Activity-level tests

For screens with navigation or ViewModel wiring, use `RoborazziRule`:

```kotlin
@RunWith(AndroidJUnit4::class)
class SettingsActivityTest {

    @get:Rule
    val roborazziRule = RoborazziRule(
        activityScenarioRule = ActivityScenarioRule(SettingsActivity::class.java),
        captureRoot = CaptureRoot.onRoot()
    )

    @Test
    fun settingsScreen() {
        onView(withId(R.id.settings_list)).check(matches(isDisplayed()))
        roborazziRule.captureRoboImage("screenshots/settings_activity.png")
    }
}
```

## Recording vs verifying

First run with `-Proborazzi.test.record=true` (or `./gradlew recordRoborazziDebug`) generates golden images. Subsequent `./gradlew verifyRoborazziDebug` compares pixel diffs and fails on mismatch, outputting diff images to `build/roborazzi/reports/`.

On CI:

```yaml
- name: Verify screenshots
  run: ./gradlew verifyRoborazziDebug --no-daemon
- name: Upload diff artifacts
  if: failure()
  uses: actions/upload-artifact@v4
  with:
    name: roborazzi-diffs
    path: "**/build/roborazzi/"
```

Record goldens on Linux if CI runs Ubuntu. Mixing macOS-recorded and Linux-compared goldens is the top cause of flaky screenshot CI.

## Handling dynamic content

Screenshots need deterministic pixels. Replace `Clock.System.now()` with a fixed `Instant`, stub image loaders (Coil's `FakeImageLoaderEngine`), and disable animations:

```kotlin
composeRule.mainClock.autoAdvance = false
composeRule.mainClock.advanceTimeBy(10_000) // settle animations
```

For lists with paging, seed fake repositories with fixed data sets. Never screenshot production API responses.

## When not to use Roborazzi

System-level UI (status bar color on real devices, foldable transitions, TalkBack focus order) still needs on-device tests or manual QA. Roborazzi validates rendering logic and layout, not OEM-specific chrome. Pair it with a small set of [Compose semantics tests](https://blog.michaelsam94.com/compose-testing-semantics-tree/) for accessibility properties screenshots can't see.

## CI integration and diff review

Roborazzi integrates with GitHub Actions for automatic screenshot diff on PR:

```yaml
# .github/workflows/screenshot-test.yml
- name: Run screenshot tests
  run: ./gradlew verifyRoborazziDebug
- name: Upload diff images on failure
  if: failure()
  uses: actions/upload-artifact@v4
  with:
    name: screenshot-diffs
    path: "**/build/outputs/roborazzi/"
```

On failure, diff images show expected vs actual side-by-side. Reviewers approve intentional UI changes by running `./gradlew recordRoborazziDebug` locally and committing updated golden images.

## Multi-module screenshot testing

Each feature module can have its own Roborazzi tests:

```
:feature:orders/src/test/screenshots/OrderListScreenshotTest.kt
:feature:profile/src/test/screenshots/ProfileScreenshotTest.kt
```

Run all module screenshot tests in CI with `./gradlew verifyRoborazziDebug` — Gradle aggregates across modules. Feature teams own their golden images independently.

## Handling flaky screenshot tests

Common flakiness sources and fixes:

| Cause | Fix |
|---|---|
| Animation mid-frame | Use `composeTestRule.mainClock.autoAdvance = false` |
| Font rendering differences | Pin font in `@Config(qualifiers = "fr-rFR")` |
| Time-dependent UI | Inject fixed clock via `@BindValue` |
| Image loading async | Use `composeTestRule.waitForIdle()` before capture |
| SDK version differences | Standardize `@Config(sdk = [33])` across tests |

Disable animations in test via `ComposeUiTestRule` before capture — animated content causes pixel diffs even when layout is correct.

## Failure modes

- **Golden images committed without review** — unintended UI regressions slip through
- **Different SDK versions across modules** — inconsistent rendering in CI vs local
- **Animation not disabled** — flaky diffs on every run
- **No diff artifact on CI failure** — reviewer can't see what changed without local repro
- **Screenshot tests without semantics tests** — layout correct but accessibility broken

## Production checklist

- `./gradlew verifyRoborazziDebug` in CI on every PR
- Diff artifacts uploaded on failure for reviewer inspection
- Animations disabled before screenshot capture
- SDK level standardized across all screenshot tests
- `@GraphicsMode(NATIVE)` for Compose rendering tests
- Golden image updates require explicit `./gradlew recordRoborazziDebug` commit

## Common production mistakes

Teams get roborazzi screenshot tests wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping roborazzi screenshot tests on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Resources

- [Roborazzi GitHub repository](https://github.com/takahirom/roborazzi)
- [Robolectric configuring qualifiers](https://robolectric.org/device-configuration/)
- [AndroidX Compose testing documentation](https://developer.android.com/jetpack/compose/testing)
- [Gradle plugin reference for Roborazzi tasks](https://github.com/takahirom/roborazzi#gradle-tasks)
- [GraphicsMode annotation for Robolectric](https://robolectric.org/blog/2023/04/11/nativerenderer/)
