---
title: "Macrobenchmark: Measuring Real Android Performance"
slug: "android-macrobenchmark-profiling"
description: "Use Macrobenchmark to measure real Android performance: startup timing, frame/jank stats, and CI regression gates that catch slowdowns before users feel them."
datePublished: "2026-03-17"
dateModified: "2026-03-17"
tags: ["Android", "Performance", "Testing"]
keywords: "Macrobenchmark, Android benchmarking, frame timing, startup benchmark, jank stats, performance regression"
faq:
  - q: "What is Android Macrobenchmark?"
    a: "Macrobenchmark is a Jetpack library that measures the performance of your app as a whole — cold/warm/hot startup, scrolling frame timing, and jank — by driving a release-like build on a real device or emulator and collecting system-level metrics. Unlike Microbenchmark, which times small pieces of code in isolation, Macrobenchmark measures end-user-visible interactions the way a user actually experiences them."
  - q: "What's the difference between Macrobenchmark and Microbenchmark?"
    a: "Microbenchmark measures a single function or tight loop running in your app's process, ideal for algorithmic hot paths. Macrobenchmark measures whole user journeys — launch the app, scroll a list — from a separate test process against a non-debuggable build, capturing startup time and frame metrics. Use Microbenchmark for code-level optimization and Macrobenchmark for the interactions users notice."
  - q: "Why must you benchmark a release build, not debug?"
    a: "A debuggable build disables ART optimizations, adds runtime checks, and runs unoptimized code, so its timings bear little relationship to what users get. Macrobenchmark requires a non-debuggable, profileable build so measurements reflect the real, optimized runtime. Benchmarking a debug build produces numbers that are both slower and misleadingly noisy, leading you to optimize the wrong things."
---

You cannot optimize what you don't measure, and on Android most teams "measure" performance by opening the app and going "feels fine." Macrobenchmark replaces that gut check with numbers. It's a Jetpack library that drives a release-like build of your app on a real device — launching it, scrolling a list, running whatever journey you script — and captures system-level metrics like startup time and frame duration, with statistical output you can gate a CI pipeline on. It's the tool that turns "I think startup got slower" into "P50 cold start regressed from 480 ms to 610 ms on this commit."

I've used Macrobenchmark both to find regressions and, more usefully, to prove that an optimization actually did something. Plenty of "performance improvements" turn out to be noise once you measure them properly. Here's how to set it up so the numbers mean something.

## Macro vs Micro: measure the right layer

Jetpack has two benchmark libraries, and picking wrong wastes your time:

- **Microbenchmark** times a small chunk of code — a parsing routine, a sort — running inside your app's process, looped thousands of times. Use it for algorithmic hot paths.
- **Macrobenchmark** measures whole interactions — cold start, scrolling — from a *separate* test process against a non-debuggable build. Use it for what users actually perceive.

Startup slowness and jank are macro concerns; a slow JSON parse is a micro concern. Reaching for Microbenchmark to "measure startup" gives you a number that has nothing to do with the user's launch experience, because startup involves process creation, class loading, and rendering that a micro loop never touches.

## The non-negotiable: benchmark a real build

The most important setup detail: **you must benchmark a non-debuggable, profileable build.** A debug build disables ART optimizations and adds instrumentation, so its numbers are slow, noisy, and unrelated to production. Macrobenchmark enforces this by requiring a `profileable` variant:

```xml
<!-- In the app you're benchmarking, in the release-like variant manifest -->
<application>
    <profileable android:shell="true" tools:targetApi="29" />
</application>
```

Then a startup benchmark looks like this:

```kotlin
@RunWith(AndroidJUnit4::class)
class StartupBenchmark {
    @get:Rule val benchmarkRule = MacrobenchmarkRule()

    @Test
    fun coldStartup() = benchmarkRule.measureRepeated(
        packageName = "com.example.app",
        metrics = listOf(StartupTimingMetric()),
        iterations = 10,
        startupMode = StartupMode.COLD,
    ) {
        pressHome()
        startActivityAndWait()
    }
}
```

`measureRepeated` runs the journey `iterations` times, discards warmup, and reports timing distributions — min, median, max — not a single flattering number. Ten iterations is a reasonable floor; run more on a noisy device. The `StartupMode.COLD` matters because cold, warm, and hot start exercise very different code paths, and users mostly feel cold start.

## Measuring jank, not just startup

Startup is the headline, but scrolling smoothness is where apps feel cheap. `FrameTimingMetric` captures frame durations while you drive a scroll, so you can quantify jank instead of squinting at it:

```kotlin
@Test
fun scrollFeed() = benchmarkRule.measureRepeated(
    packageName = "com.example.app",
    metrics = listOf(FrameTimingMetric()),
    iterations = 5,
    setupBlock = { startActivityAndWait() },
) {
    val list = device.findObject(By.res("feed_list"))
    list.setGestureMargin(device.displayWidth / 5)
    repeat(3) { list.fling(Direction.DOWN) }
    device.waitForIdle()
}
```

The output gives you frame duration percentiles. The one to watch is the tail — P95 and P99 frame times — because average frame time hides the occasional 40 ms janky frame that a user's eye catches immediately. A P50 of 8 ms with a P99 of 55 ms is a janky scroll despite the great median. If those tail numbers are ugly, that's your cue to go hunting the main-thread work causing it, which connects directly to the diagnosis work in [killing ANRs and Android jank](https://blog.michaelsam94.com/killing-anrs-android-jank/).

## Reading the numbers like an engineer

A distribution is only useful if you interpret it honestly:

| Metric | What it tells you | Watch for |
| --- | --- | --- |
| `timeToInitialDisplay` | Time to first frame drawn | Cold-start regressions |
| `timeToFullDisplay` | Time until content is actually ready | Deferred content masking slow loads |
| Frame duration P50 | Typical smoothness | Baseline drift over releases |
| Frame duration P99 | Worst-case jank | Occasional stalls users notice |

`timeToFullDisplay` deserves special attention — it's easy to game `timeToInitialDisplay` by drawing an empty shell fast, but users care when the *content* appears. Report `reportFullyDrawn()` at the right moment in your app so this metric reflects reality rather than a hollow first frame. I've seen "startup improvements" that only moved the shell earlier while the real content arrived at the same time; full-display timing exposes that.

## Wiring it into CI as a regression gate

A benchmark you run manually once is a curiosity; a benchmark in CI is a guardrail. Run the suite on a consistent device (a dedicated physical device or a fixed emulator profile — never a shared, thermally-variable CI box) and compare against a baseline. When a PR pushes P50 cold start past a threshold, fail the build and make the author explain the regression before it ships.

Two honesty caveats. First, benchmarks are noisy; small run-to-run variance is normal, so gate on meaningful deltas (say, >10%), not single-millisecond wobble, or you'll drown in flaky failures. Second, device choice dominates results — numbers from a flagship tell you nothing about the budget phone where users actually feel pain, so benchmark on hardware representative of your user base, ideally a mid-to-low-tier device.

Macrobenchmark also pairs naturally with the optimization it measures. When you generate and ship [baseline profiles for Android startup](https://blog.michaelsam94.com/baseline-profiles-android-startup/), Macrobenchmark is exactly how you *prove* they helped — measure cold start with and without the profile applied and put the delta in the PR. That closes the loop: you don't claim a speedup, you demonstrate it with a distribution.

My standing advice: get one startup benchmark and one scroll benchmark running against a profileable build this week, on a representative device, and put them in CI with a generous threshold. You don't need a hundred benchmarks — you need a handful of honest ones guarding the interactions users feel most. Performance work without measurement is just superstition with extra steps.

## Resources

- [Macrobenchmark — official documentation](https://developer.android.com/topic/performance/benchmarking/macrobenchmark-overview)
- [Write a Macrobenchmark](https://developer.android.com/topic/performance/benchmarking/macrobenchmark-instrument)
- [Startup timing metrics](https://developer.android.com/topic/performance/benchmarking/macrobenchmark-metrics)
- [Benchmarking in CI](https://developer.android.com/topic/performance/benchmarking/benchmarking-in-ci)
- [Benchmark library on GitHub](https://github.com/androidx/androidx/tree/androidx-main/benchmark)
