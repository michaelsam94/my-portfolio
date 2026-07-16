---
title: "Screenshot Testing with Paparazzi"
slug: "android-screenshot-testing-paparazzi"
description: "Screenshot test Android UIs with Paparazzi on the JVM: setup, recording golden images, CI integration, and handling flaky visual tests."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Android", "Testing", "Jetpack Compose", "CI"]
keywords: "Paparazzi screenshot testing, Android visual regression tests, JVM screenshot tests, Paparazzi Compose, golden image testing Android"
faq:
  - q: "What is Paparazzi for Android testing?"
    a: "Paparazzi renders Android layouts and Compose UI on the JVM without an emulator or device. It captures screenshots as golden images and compares future renders against them to detect visual regressions. Tests run in seconds on any machine — no AVD required."
  - q: "How is Paparazzi different from emulator screenshot tests?"
    a: "Paparazzi runs on the JVM using Android resource loading and layout inflation without a real Android runtime. It's faster (milliseconds per test vs seconds on emulator) and runs in standard JVM test tasks. Emulator tests are needed for interactions; Paparazzi is for visual regression of static UI states."
  - q: "How do you update Paparazzi golden images?"
    a: "Run ./gradlew recordPaparazziDebug to regenerate all golden images after intentional UI changes. Review the diffs in git before committing. In CI, verifyPaparazziDebug compares renders against committed golden images and fails on any pixel difference."
---

Paparazzi screenshot tests run on the JVM in milliseconds, need no emulator, and catch visual regressions that unit tests miss — a button that's 4px misaligned, a theme color that changed, text that's clipped after a font update. I've added Paparazzi to Compose projects and watched it catch UI breaks that slipped through code review because "the logic is correct" but the layout shifted. The setup takes an afternoon; the ongoing cost is reviewing golden image diffs in PRs, which is exactly the kind of review that should be automated.

## Setup

```kotlin
// app/build.gradle.kts
plugins {
    id("app.cash.paparazzi") version "1.3.4"
}

dependencies {
    testImplementation(libs.paparazzi)
}
```

```kotlin
// gradle/libs.versions.toml
paparazzi = { module = "app.cash.paparazzi:paparazzi", version = "1.3.4" }
```

No emulator, no device, no Android instrumentation test runner. Pure JVM `test` task.

## Basic screenshot test

```kotlin
class HomeScreenTest {
    @get:Rule
    val paparazzi = Paparazzi()

    @Test
    fun homeScreen_default() {
        paparazzi.snapshot {
            AppTheme {
                HomeScreen(
                    uiState = HomeUiState(
                        greeting = "Good morning",
                        items = previewItems,
                    )
                )
            }
        }
    }
}
```

Paparazzi renders the Composable, captures a PNG, and compares against the golden image in `src/test/snapshots/`.

## Recording golden images

First run or after intentional UI changes:

```bash
./gradlew recordPaparazziDebug
```

This generates/updates PNG files in `src/test/snapshots/images/`. Commit them to git.

CI verification:

```bash
./gradlew verifyPaparazziDebug
```

Fails if any render differs from the golden image. Diffs are saved to `src/test/snapshots/delta/` for review.

## Testing multiple states

```kotlin
@Test
fun homeScreen_loading() {
    paparazzi.snapshot {
        AppTheme { HomeScreen(uiState = HomeUiState(isLoading = true)) }
    }
}

@Test
fun homeScreen_empty() {
    paparazzi.snapshot {
        AppTheme { HomeScreen(uiState = HomeUiState(items = emptyList())) }
    }
}

@Test
fun homeScreen_error() {
    paparazzi.snapshot {
        AppTheme { HomeScreen(uiState = HomeUiState(error = "Network error")) }
    }
}
```

Test every visually distinct state: loading, empty, error, populated, edge cases (long text, many items).

## Device config variations

Test across screen sizes and themes:

```kotlin
@Test
fun homeScreen_darkMode() {
    paparazzi.unsafeUpdateConfig(
        paparazzi.context.resources.configuration.apply {
            uiMode = Configuration.UI_MODE_NIGHT_YES
        }
    )
    paparazzi.snapshot {
        AppTheme(darkTheme = true) { HomeScreen(uiState = previewState) }
    }
}
```

Or use parameterized tests for width/height combinations.

## CI integration

```yaml
# GitHub Actions
- name: Verify screenshots
  run: ./gradlew verifyPaparazziDebug

- name: Upload diffs on failure
  if: failure()
  uses: actions/upload-artifact@v4
  with:
    name: paparazzi-diffs
    path: "**/snapshots/delta/"
```

Paparazzi runs in standard JVM test tasks — no KVM, no emulator, no special CI setup. It runs on macOS, Linux, and Windows identically.

## Handling dynamic content

Paparazzi renders at a fixed point in time, but some UI is inherently dynamic:

- **Dates/times**: inject fixed timestamps in preview/test state
- **Images from network**: use local test drawables, not Coil async loading
- **Animations**: Paparazzi captures static frames — disable animations
- **Random content**: use deterministic preview data

```kotlin
// Bad: renders differently each run
Text("Last updated: ${Instant.now()}")

// Good: fixed in test
Text("Last updated: Jan 15, 2026")
```

## Paparazzi vs Roborazzi

| Feature | Paparazzi | [Roborazzi](https://blog.michaelsam94.com/android-roborazzi-screenshot-tests/) |
|---------|-----------|-------------|
| Rendering engine | Layoutlib (Paparazzi) | Robolectric + Compose |
| Compose support | Yes | Yes (better Compose integration) |
| View system support | XML layouts + Compose | Compose-first |
| Speed | Very fast | Fast |
| Maintainer | Cash App | Taku Semba |

Both run on JVM without emulators. Paparazzi is more mature for XML layouts; Roborazzi has better Compose rendering fidelity. Try both on your project and pick based on render accuracy.

## Review workflow

1. Developer changes UI code
2. CI runs `verifyPaparazziDebug` — fails with diff
3. Developer runs `recordPaparazziDebug` locally
4. Reviews generated PNG diffs in git
5. Commits updated golden images with the UI change PR
6. Reviewer checks both code and screenshot diffs

Treat golden image changes with the same scrutiny as code changes — they're visual contract changes.

## Flaky test prevention

Paparazzi failures that aren't real UI regressions waste review time. Eliminate sources of nondeterminism systematically:

**Fonts:** Paparazzi bundles Roboto, but custom fonts must be declared in test resources. Missing font files fall back silently — text metrics shift by pixels.

**Density and locale:** Lock both in every test:

```kotlin
@Paparazzi(
    deviceConfig = DeviceConfig.NIGHTLY.copy(locale = "en-US"),
)
class CheckoutScreenTest { ... }
```

**Hardware bitmaps:** `Bitmap.Config.HARDWARE` cannot be captured — use software bitmaps in test or `@Preview` composables.

**System bars and insets:** Pass explicit `WindowInsets` in test rather than relying on device defaults that differ between Paparazzi versions.

## Scaling screenshot tests across modules

Monorepo with 40 feature modules — centralize configuration:

```kotlin
// :testing-screenshots module
fun Paparazzi.defaultConfig() = Paparazzi(
    deviceConfig = DeviceConfig.PIXEL_5,
    theme = "android:Theme.Material3.DayNight",
    renderingMode = SessionParams.RenderingMode.SHRINK,
)
```

Run `verifyPaparazzi` only on affected modules in CI using Gradle task graph analysis. Full-suite verify on `main` nightly; PRs verify changed modules only.

Store golden images in git LFS if repo size exceeds 500 MB — but prefer per-module snapshot dirs to limit LFS churn.

## Accessibility and screenshot coverage

Screenshot tests complement but don't replace accessibility testing. Still add:

- Semantic tree assertions for TalkBack labels on critical flows
- Color contrast checks for text-on-background combinations Paparazzi captures but doesn't evaluate

When a golden image changes, ask: "Would this pass WCAG AA?" Visual diff approval is not accessibility approval.

## When Paparazzi isn't enough

Paparazzi renders layoutlib output — not identical to real devices for:

- OpenGL/Canvas custom drawing with GPU shaders
- WebView content
- System UI overlays and edge-to-edge with dynamic scrims

For those cases, add a small Maestro or emulator screenshot suite as a secondary gate, not a replacement. Paparazzi catches 90% of Compose/XML regressions at 1% of the CI cost.

## Production checklist

- [ ] Fixed timestamps in all preview/test composables
- [ ] Custom fonts bundled in `src/test/resources`
- [ ] Golden images reviewed in PR diffs, not auto-approved
- [ ] Per-module verify on affected modules in CI
- [ ] Accessibility semantics tested separately from screenshots

## Resources

- [Paparazzi documentation](https://cashapp.github.io/paparazzi/)
- [Paparazzi GitHub repository](https://github.com/cashapp/paparazzi)
- [Testing Compose UIs](https://developer.android.com/jetpack/compose/testing)
- [Roborazzi screenshot tests](https://blog.michaelsam94.com/android-roborazzi-screenshot-tests/)
- [Compose preview tooling](https://blog.michaelsam94.com/compose-preview-tooling-multipreview/)
