---
title: "Profiling App Startup with Perfetto"
slug: "android-startup-tracing-perfetto"
description: "Profile Android app startup with Perfetto: capture a system trace, read the startup slice, and find the threads and locks that push cold start past 500ms."
datePublished: "2024-06-19"
dateModified: "2024-06-19"
tags: ["Android", "Performance", "Perfetto", "App Startup"]
keywords: "Perfetto app startup, Android startup tracing, system trace, cold start, reportFullyDrawn, main thread contention"
faq:
  - q: "What does Perfetto show that the Android Studio profiler doesn't?"
    a: "Perfetto captures a system-wide trace, so you see every thread, binder call, lock contention, and kernel scheduling event alongside your app's slices. The Studio CPU profiler is app-scoped and heavier; Perfetto is closer to the metal and shows why your main thread was descheduled, not just what it ran. For startup work, that system view is usually what tells you the real cause."
  - q: "How do I measure cold start time accurately?"
    a: "Use the reported 'Time to initial display' from the Perfetto startup slice, which spans process fork to the first frame. For a truthful number, force a cold start by killing the process and clearing it from recents, disable JIT warmup effects by running several iterations, and pair the trace with a Macrobenchmark run so you get a distribution rather than one lucky sample."
  - q: "What is reportFullyDrawn and why does it matter?"
    a: "reportFullyDrawn tells the framework when your screen is actually usable, not just when the first frame drew. Startup often looks fast because a skeleton painted, but data is still loading. Calling reportFullyDrawn after the real content is on screen gives you a Time to Full Display metric that reflects what users experience."
---

Cold start is where users decide whether your app feels fast, and Perfetto is the tool that tells you the truth about it. When I inherit an app that "feels sluggish to open," the first thing I do is capture a Perfetto system trace of a cold start, because it shows every thread, binder transaction, and lock the process touched between fork and first frame — not just the slices your own code emitted. Android Studio's profiler is fine for narrowing down a hot method, but startup problems are almost always about *contention and ordering* across the whole system, and that's exactly what a system trace exposes.

## Capture a trace that actually represents a cold start

The trap is measuring a warm start and thinking you fixed something. A real cold start means the process doesn't exist yet. My routine:

1. Force-stop the app and swipe it out of recents, or run `adb shell am force-stop <pkg>`.
2. Start recording — either from the on-device System Tracing quick-settings tile, or with `record_android_trace` from the Perfetto repo, or `adb shell perfetto` with a config.
3. Launch the app with `adb shell am start-activity -W <pkg>/<activity>` so `am` prints the displayed time as a sanity check.
4. Stop recording once the first screen is interactive, and open the trace at `ui.perfetto.dev`.

For repeatability, I record several iterations and don't trust a single run. The first launch after install pays one-time costs (dexopt, first-run migrations) you don't want to optimize against. If you want a distribution instead of anecdotes, drive this from a Macrobenchmark `StartupTimingMetric` run — I wrote about that discipline in [profiling with Macrobenchmark](https://blog.michaelsam94.com/android-macrobenchmark-profiling/).

## Read the startup slice first

Perfetto tags app launches with a dedicated **"Android App Startups"** track. Click it and you get the span from process start to first frame, broken into the phases that matter: process fork, `Application.onCreate`, first activity creation, layout inflation, and the first `doFrame`. This single view answers the biggest question — *where did the time go* — before you go spelunking.

The usual offenders, in the order I find them:

- **`Application.onCreate` doing too much.** Every SDK that "initializes itself" on the main thread lands here. Analytics, crash reporting, DI graph construction, feature-flag fetches — they add up to hundreds of milliseconds before your first activity even starts.
- **Synchronous disk or network on the main thread.** A `SharedPreferences` load, a Room query, a config file read. In the trace these show as the main thread blocked in a binder or I/O slice while nothing paints.
- **Layout inflation and overdraw** in the first activity, especially deep view hierarchies or a heavy Compose first composition.

## Find contention, not just CPU

The reason I reach for Perfetto over a sampling profiler is that startup is rarely CPU-bound the whole way through — it's *blocked*. The main thread is runnable but sitting behind a lock, or descheduled while a binder call to `system_server` completes. Perfetto's thread states make this visible: a main-thread slice colored for "uninterruptible sleep" or a long gap where the thread is "runnable but not running" tells a completely different story than a green CPU-bound slice.

Two patterns I look for specifically:

- **Lock contention** on the main thread. Expand the main thread, look for `monitor contention` slices. A background init thread holding a lock the main thread needs will stall your first frame with zero CPU cost — invisible to a naive "which method is hot" analysis.
- **Binder storms.** Dozens of synchronous binder transactions during startup (permission checks, package manager queries, content-provider auto-init) serialize against `system_server`. ContentProvider-based library auto-initialization is a classic cause; consolidating those behind Jetpack App Startup removes the per-library provider overhead.

## Fixes that consistently move the number

Once the trace points at a cause, the fixes are not exotic:

```kotlin
// Defer non-critical SDK init off the startup critical path.
class MyApp : Application() {
    override fun onCreate() {
        super.onCreate()
        criticalInit()               // DI, crash reporting — needed immediately
        lifecycleScope() // conceptual
    }
}

// Better: use androidx.startup and mark heavy work as lazy / background.
class AnalyticsInitializer : Initializer<Unit> {
    override fun create(context: Context) {
        // schedule, don't block
        WorkManager.getInstance(context).enqueue(/* analytics warmup */)
    }
    override fun dependencies() = emptyList<Class<out Initializer<*>>>()
}
```

The principles that repeatedly work: move anything not required for the first frame off `Application.onCreate`; replace synchronous main-thread I/O with a lazy load or a background coroutine that the UI observes; and collapse library ContentProviders into a single App Startup initializer so you pay one provider cost instead of ten. If a library insists on main-thread init and can't be deferred, that's a real cost to weigh in your dependency choices.

## Measure Time to Full Display, not just first frame

A skeleton screen paints fast and lies. The metric that matches user perception is **Time to Full Display (TTFD)**, and you opt into it by calling `reportFullyDrawn()` once the screen shows real content:

```kotlin
override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    setContent { HomeScreen(state) }
    // Once real data is on screen, not just placeholders:
    lifecycleScope.launch {
        state.first { it.isLoaded }
        reportFullyDrawn()
    }
}
```

In the Perfetto startup slice you'll then see both Time to Initial Display and Time to Full Display. Optimizing only the former is how teams ship apps that "open instantly" but sit on a spinner for two seconds — technically fast, actually slow.

## A workflow that scales past one bug

Startup profiling isn't a one-off. The apps that stay fast treat the cold-start trace as a regression signal: capture a baseline, fix the top offender in the trace, re-measure, and lock it in with a Macrobenchmark test in CI so a future SDK bump doesn't quietly re-inflate `Application.onCreate`. Perfetto is where you diagnose; the benchmark is where you keep the win. The same discipline applies to runtime smoothness — the [jank and ANR side of the story](https://blog.michaelsam94.com/killing-anrs-android-jank/) uses the same trace-first, measure-then-fix loop.

The mental shift that matters: startup latency is a *systems* problem, not a method-timing problem. Once you read a cold start as threads, locks, and binder calls racing to produce a frame — instead of a list of slow functions — the fixes become obvious and the number comes down.

## Resources

- [Perfetto — system tracing documentation](https://perfetto.dev/docs/)
- [Inspect app startup with Perfetto (Android)](https://developer.android.com/topic/performance/tracing)
- [App startup time guide](https://developer.android.com/topic/performance/vitals/launch-time)
- [Jetpack App Startup library](https://developer.android.com/topic/libraries/app-startup)
- [Macrobenchmark startup metrics](https://developer.android.com/topic/performance/benchmarking/macrobenchmark-overview)
