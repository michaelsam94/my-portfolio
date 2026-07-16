---
title: "Tracing Recomposition in Production"
slug: "android-tracing-composition-recomposition"
description: "How to trace Jetpack Compose recomposition in production: composition tracing, recomposition counts in Layout Inspector, and finding the recompositions that cost frames."
datePublished: "2024-10-02"
dateModified: "2024-10-02"
tags: ["Android", "Jetpack Compose", "Performance", "Profiling"]
keywords: "Compose recomposition tracing, composition tracing, recomposition count, Layout Inspector recomposition, Compose performance, Perfetto Compose"
faq:
  - q: "How do I see which composables are recomposing too much?"
    a: "Use the Layout Inspector's recomposition counts to see how many times each composable has recomposed and how many recompositions were skipped. A composable recomposing far more than the data behind it changes is a red flag. For frame-level timing, enable composition tracing and inspect the trace in Android Studio or Perfetto to see recomposition work on the timeline."
  - q: "What is composition tracing in Jetpack Compose?"
    a: "Composition tracing adds named trace sections for individual composable functions to a system trace, so you can see exactly which composables ran during a frame and how long they took. You enable it by adding the runtime-tracing dependency and capturing a system trace; without it, composables show up as generic work. It's the tool for connecting a janky frame to the specific recomposition that caused it."
  - q: "Does recomposition always cause performance problems?"
    a: "No — recomposition is normal and cheap when composables are skippable and only run when their inputs change. Problems arise when composables recompose unnecessarily due to unstable parameters, or when an expensive composable recomposes on every frame. The goal isn't zero recomposition; it's ensuring recomposition happens only when needed and stays off the expensive paths."
---

Recomposition is Compose working as designed — but recomposition that fires when nothing meaningful changed, or that lands on an expensive composable every frame, is where jank comes from. The hard part in production isn't knowing recomposition exists; it's finding *which* composables are recomposing too much and whether it actually costs frames. Guessing is worthless here. I've watched teams "optimize" a composable that recomposed twice while the real culprit recomposed 400 times a second off-screen. You need to trace it, and Compose now has decent tools for exactly that.

## First, reset the intuition

Recomposition is not inherently bad. A skippable composable that only re-runs when its inputs change is cheap and correct. The problems are specific:

- A composable recomposes far **more often than its data changes** — usually because a parameter is unstable, so Compose can't skip it.
- An **expensive** composable (heavy layout, allocation, work in the composition) recomposes on a hot path like scroll or animation.

So the goal isn't "eliminate recomposition." It's "make composables skippable, and keep expensive ones off the frequently-recomposing paths." Tracing tells you where you're violating that.

## Recomposition counts in Layout Inspector

The fastest first look is the **Layout Inspector's recomposition counts**. Connect to a running debug build, and it annotates the composable tree with two numbers per node: how many times it **recomposed** and how many recompositions were **skipped**.

How to read it:

- **High recompose count, low skip count** on a node whose data rarely changes → it's not skippable. Something is making Compose re-run it — usually an unstable parameter or a lambda allocated fresh each time.
- **High skip count** → Compose is correctly skipping; that's the system working.
- Watch the counts *while you interact*. Scroll, type, animate — and see which nodes spike. A node whose counter climbs during an unrelated interaction is recomposing for reasons it shouldn't.

This is the triage step: it points you at suspects. It doesn't tell you the *frame cost* — that's the next tool.

## Composition tracing for frame-level truth

Layout Inspector tells you *how often*; **composition tracing** tells you *how long* and *when*, on the actual frame timeline. By default, composables show up as generic work in a system trace. Composition tracing adds named trace sections for individual composable functions, so a captured trace shows "this frame spent 6ms in `ProductCard` recomposition."

Enable it by adding the runtime tracing dependency:

```kotlin
// build.gradle.kts (debug/benchmark)
implementation("androidx.compose.runtime:runtime-tracing:1.6.0")
```

Then capture a **system trace** (Android Studio profiler or `Perfetto`) while reproducing the jank. In the trace you'll see composable-named sections on the main thread timeline. Now you can answer the question that matters: *did this recomposition actually land inside a frame that dropped?* A composable recomposing 200 times is fine if each is 0.05ms and off the critical path; it's a bug if one lands mid-scroll costing 8ms.

## The workflow I use

Putting the tools in order, because using them out of order wastes time:

1. **Reproduce the jank** on a real device (mid-range, release-like build). Emulators lie about performance.
2. **Layout Inspector recomposition counts** to find composables recomposing disproportionately to their data. Note the suspects.
3. **Composition tracing + system trace** to confirm which suspects actually cost frame time during the janky interaction.
4. **Fix the cause** — usually stability, not restructuring:
   - Unstable parameters → make the data class stable (immutable, stable types) or wrap it.
   - Lambdas allocated per-recomposition → hoist or `remember` them.
   - Expensive work in composition → move it out (`remember`, `derivedStateOf`, or off the composition entirely).
5. **Re-measure.** Confirm the counts dropped *and* the frame cost went away. Both, not one.

The fixes themselves are the stability rules from [Compose performance and recomposition](https://blog.michaelsam94.com/compose-performance-stability-recomposition/) — this article is about *finding* the offenders, which is the half people skip.

## Measuring in a benchmark, not by feel

For anything you want to track over time, wrap the interaction in a **Macrobenchmark** capturing `FrameTimingMetric`. This gives you frame durations (including the ugly P95/P99 tail) for a defined journey — scroll the feed, open a screen — so recomposition regressions show up as numbers in CI rather than as a user complaint months later.

```kotlin
@Test
fun scrollFeed() = benchmarkRule.measureRepeated(
    packageName = "com.example.app",
    metrics = listOf(FrameTimingMetric()),
    iterations = 10,
    startupMode = StartupMode.WARM,
) {
    startActivityAndWait()
    device.findObject(By.res("feed")).fling(Direction.DOWN)
}
```

Composition tracing tells you *why* a frame was slow in a single session; a frame-timing benchmark tells you *whether it's getting worse* over releases. You want both — the diagnostic and the guardrail.

## A note on production vs debug

Recomposition counts and full composition tracing rely on debuggable/instrumented builds and add overhead, so you don't leave them on in shipped releases. The "production" part of tracing recomposition means reproducing *production-like* conditions — real devices, release-optimized code paths where possible, realistic data volumes — not literally profiling end users. For genuine field signal, lean on frame-timing metrics via benchmarks and Play Console's stability/performance data, then reproduce and trace locally.

## What I'd take away

Chasing recomposition without tracing is guesswork, and Compose gives you two tools that answer different questions: Layout Inspector recomposition counts show *how often* each composable recomposes and skips, and composition tracing shows *how long* and *where* on the frame timeline. Use counts to find suspects, use tracing to confirm which ones actually cost frames, fix the underlying stability issues, then re-measure both the counts and the frame time. Back it with a frame-timing Macrobenchmark so regressions surface in CI. Recomposition isn't the enemy — unnecessary or expensive recomposition on hot paths is, and now you can prove which is which.

## Resources

- [Compose performance — recomposition tracing](https://developer.android.com/develop/ui/compose/tooling/tracing)
- [Debug recomposition with Layout Inspector](https://developer.android.com/develop/ui/compose/tooling/layout-inspector)
- [Compose stability and skippability](https://developer.android.com/develop/ui/compose/performance/stability)
- [Macrobenchmark FrameTimingMetric](https://developer.android.com/topic/performance/benchmarking/macrobenchmark-overview)
- [Perfetto system tracing](https://perfetto.dev/docs/)
