---
title: "Baseline Profiles: Faster Android App Startup"
slug: "baseline-profiles-android-startup"
description: "Baseline Profiles cut Android cold start by pre-compiling hot paths at install — Macrobenchmark setup, profile generation, measurement, and Play Console checks."
datePublished: "2026-04-08"
dateModified: "2026-04-08"
tags: ["Android", "Performance", "Baseline Profiles", "Kotlin"]
keywords: "Baseline Profiles, Android startup time, app startup performance, Macrobenchmark, cold start, ART, ahead-of-time compilation"
faq:
  - q: "What is a Baseline Profile in Android?"
    a: "A Baseline Profile is a list of hot code paths — classes and methods exercised during startup and critical journeys — that ART compiles ahead of time at install. It lets the runtime skip JIT compilation for that code, so the app's first runs are meaningfully faster."
  - q: "How much does a Baseline Profile improve startup?"
    a: "It varies by app, but 20-40% faster cold start is a common, realistic range, with larger gains on lower-end devices. The wins concentrate in startup and the first navigation through key screens, so measure your own app rather than assuming a fixed number."
  - q: "Do I need to write Baseline Profiles by hand?"
    a: "No. You generate them with a Macrobenchmark test that drives your app through startup and critical flows, and the tooling records the hot paths into a profile file that ships with your app. You maintain the journey code, not the raw profile."
---

Android app startup is a compilation problem as much as a code problem. When ART installs your app it doesn't compile everything ahead of time — it interprets and JIT-compiles code as it runs, which means your first launches pay a tax while the runtime figures out what's hot. **Baseline Profiles** cut that tax by telling ART, up front, exactly which classes and methods your startup and critical journeys touch, so they get compiled at install. On real apps that's commonly a 20–40% cold-start improvement, and more on cheaper hardware.

I added Baseline Profiles to an app with a heavy startup path and watched cold start drop from painful to acceptable without changing a line of feature code. It's one of the highest-leverage perf wins available, because you're not optimizing your code — you're optimizing how the runtime treats it.

## Why cold start is slow by default

On a cold start, the app process doesn't exist yet: ART starts, loads your classes, and begins executing bytecode in the interpreter. Frequently-run methods get JIT-compiled on the fly, but that compilation happens *during* your startup, competing with the work the user is waiting for. The result is that the first few launches after install are the slowest, before the profile-guided optimization the runtime does over time kicks in.

A Baseline Profile front-loads that. It's shipped in your APK/AAB, and at install time ART ahead-of-time-compiles the listed methods. So the user's very first launch already benefits from compiled hot paths instead of earning it slowly over days of usage. This complements — doesn't replace — the [ANR and jank work](https://blog.michaelsam94.com/killing-anrs-android-jank/) that keeps the main thread free; profiles make the code faster, jank work keeps it from blocking.

## Setup: the Macrobenchmark module

You generate profiles from a Macrobenchmark test that drives your app. Add the libraries and a benchmark module:

```kotlin
// build.gradle.kts (benchmark module)
plugins {
    id("com.android.test")
    id("androidx.baselineprofile")
}

dependencies {
    implementation("androidx.benchmark:benchmark-macro-junit4:1.3.0")
    implementation("androidx.test.ext:junit:1.2.1")
    implementation("androidx.test.uiautomator:uiautomator:2.3.0")
}
```

Then write a generator that exercises the flows you care about — startup, plus the first screens users hit:

```kotlin
@RunWith(AndroidJUnit4::class)
class BaselineProfileGenerator {
    @get:Rule val rule = BaselineProfileRule()

    @Test
    fun generate() = rule.collect(packageName = "com.example.app") {
        pressHome()
        startActivityAndWait()
        // drive the critical journey so its hot paths are recorded
        device.findObject(By.res("charger_list")).also { it.fling(Direction.DOWN) }
        device.waitForIdle()
    }
}
```

Run it on a physical device or a rooted/AOSP emulator image, and the plugin drops a `baseline-prof.txt` into your app module's `src/main/`. That file ships with the app.

## Measure before you believe it

Never trust a perf change you didn't measure. Use a `MacrobenchmarkRule` startup test comparing compilation modes:

```kotlin
@Test
fun startupWithProfile() = benchmarkRule.measureRepeated(
    packageName = "com.example.app",
    metrics = listOf(StartupTimingMetric()),
    compilationMode = CompilationMode.Partial(),   // uses the baseline profile
    startupMode = StartupMode.COLD,
    iterations = 10,
) {
    pressHome()
    startActivityAndWait()
}
```

Run the same test with `CompilationMode.None()` as a baseline and compare `timeToInitialDisplay`. Numbers I'd expect: a mid-tier device might go from ~900ms to ~600ms time-to-initial-display; a budget device shows a bigger absolute win. If you see *no* difference, something's wrong — usually the profile isn't being applied (check it's in the release build) or your journey didn't cover the hot paths.

## Startup profiles vs full baseline profiles

Android 13+ merges a **startup profile** subset for install-time DexOpt focused on first launch. Mark generator blocks with `includeInStartupProfile = true` for code on the cold-start critical path — Application init, first Activity, home screen Compose tree. Secondary journeys (settings, account) can use separate `collect` calls without the flag so install-time work stays bounded. Pair generated profiles with [Compose performance tuning](https://blog.michaelsam94.com/compose-performance-stability-recomposition/) when startup jank persists after AOT — sometimes the issue is recomposition, not compilation.

| Compilation mode | What it means |
| --- | --- |
| `None` | No AOT — worst case, your true "cold" baseline |
| `Partial` | AOT-compiles the baseline profile — what ships |
| `Full` | AOT-compiles everything — larger, not always faster |

## The traps I've hit

- **Debug builds lie.** Profiles apply to release-style builds. Benchmark against a `release` or `benchmark` build type with minification as shipped, or your numbers are meaningless.
- **Stale journeys.** If your app's startup path changes significantly and you don't regenerate, the profile drifts out of date and covers the wrong methods. Regenerate on meaningful UI/architecture changes, ideally in CI.
- **Over-covering.** Recording deep, rarely-used flows bloats the profile and dilutes the startup win. Focus the generator on startup and the first one or two screens.
- **Forgetting the library profiles.** Big libraries (Compose, your networking stack) ship their own baseline profiles that merge with yours. That's a feature — but it means keeping dependencies current also improves startup.

## Fit it into CI

The mature setup regenerates the profile as part of your release pipeline and fails the build if startup regresses past a threshold. That turns startup performance from a thing someone remembers to check into a guardrail.

Baseline Profiles are close to free money for startup performance: no risky refactor, no behavior change, just telling the runtime what you already know about how your app runs. On a portfolio of apps I've maintained, it's consistently in the top tier of effort-to-impact ratio, especially for the budget devices that make up so much of the global Android install base.

## Resources

- [Baseline Profiles overview](https://developer.android.com/topic/performance/baselineprofiles/overview)
- [Create a Baseline Profile](https://developer.android.com/topic/performance/baselineprofiles/create-baselineprofile)
- [Macrobenchmark guide](https://developer.android.com/topic/performance/benchmarking/macrobenchmark-overview)
- [App startup analysis](https://developer.android.com/topic/performance/vitals/launch-time)
- [Android developers blog](https://android-developers.googleblog.com/)
- [Jetpack Benchmark releases](https://developer.android.com/jetpack/androidx/releases/benchmark)

*Chasing down slow startup on an Android app? [Reach out](https://michaelsam94.com/) — this is one of my favorite problems.*
