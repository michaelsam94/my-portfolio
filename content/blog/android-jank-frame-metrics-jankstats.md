---
title: "Measuring Jank in Production with JankStats"
slug: "android-jank-frame-metrics-jankstats"
description: "Use JankStats to measure Android UI jank in production: track dropped frames, attach state to slow frames, and turn frame timing into an actionable metric."
datePublished: "2024-06-20"
dateModified: "2024-06-20"
tags: ["Android", "Performance", "JankStats", "Jetpack"]
keywords: "JankStats, Android jank, frame metrics, dropped frames, FrameData, jank in production, frame timing"
faq:
  - q: "What is JankStats and how is it different from Macrobenchmark?"
    a: "JankStats is a Jetpack library that reports per-frame timing on real user devices in production, flagging frames that took longer than their deadline. Macrobenchmark measures frame timing in a controlled lab run before release. They're complementary: Macrobenchmark catches regressions pre-ship, JankStats tells you what your actual users experience on their actual devices."
  - q: "How does JankStats know a frame was janky?"
    a: "It reads frame duration from the platform's frame metrics and compares it against a deadline derived from the display's refresh rate, with a multiplier for headroom. A frame that exceeds that deadline is counted as janky. On API 31+ it uses FrameMetrics directly; on older versions it falls back to OnPreDrawListener timing."
  - q: "What should I attach as state to frame data?"
    a: "Attach whatever tells you where the jank happened: the current screen name, the scrolling list identifier, whether an animation or network refresh is in flight. When a frame is janky, that state is included in the FrameData, so your aggregation can say 'the feed scroll on mid-tier devices janks', which is actionable, instead of 'jank exists somewhere'."
---

Jank is invisible in the lab and obvious to users, which is why measuring it in production with JankStats matters more than any local profiling session. JankStats is a small Jetpack library that hooks into the platform's frame-timing signals and reports, on real devices, which frames blew past their deadline — and crucially, lets you attach application state to those slow frames so a dropped frame becomes "the feed scroll janked on a 60Hz mid-tier device" instead of an anonymous statistic. That context is the difference between a number you can act on and a number you ignore.

## Why lab benchmarks aren't enough

I run Macrobenchmark in CI and I still get jank reports from the field. The reason is simple: my test devices are a handful of clean Pixels, and my users are on thousands of SKUs with background apps, thermal throttling, and 60/90/120Hz panels. A frame budget is 16.6ms at 60Hz but 8.3ms at 120Hz, so the *same* rendering work is fine on one device and janky on another. You cannot enumerate that in a lab. JankStats accepts this and measures the population you actually have.

## Wiring it up

JankStats attaches per-window and needs the current lifecycle to know when to track. The minimal setup:

```kotlin
class MainActivity : ComponentActivity() {
    private lateinit var jankStats: JankStats

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        jankStats = JankStats.createAndTrack(window) { frameData ->
            if (frameData.isJank) {
                reporter.log(frameData)   // send to your analytics sink
            }
        }
    }

    override fun onResume() {
        super.onResume()
        jankStats.isTrackingEnabled = true
    }

    override fun onPause() {
        super.onPause()
        jankStats.isTrackingEnabled = false
    }
}
```

The callback fires for every frame. You get a `FrameData` with the frame's start time, duration, whether it was jank, and any state you've attached. Don't log every frame to your backend — that's a firehose. Sample, or only report `isJank` frames plus periodic aggregates.

## The feature that makes it worth it: state

A bare "1.8% of frames janked" tells you nothing about where to look. JankStats lets you push named state onto a `StateHolder` tied to a view, and any janky frame carries the state that was active when it rendered:

```kotlin
val metricsState = PerformanceMetricsState.getHolderForHierarchy(view).state

// When the user opens the feed:
metricsState?.putState("screen", "feed")
// While a specific list is scrolling:
metricsState?.putState("scrolling", "feed_list")
// Remove when the interaction ends:
metricsState?.removeState("scrolling")
```

Now your aggregation can group jank by screen and interaction. In practice this immediately concentrates the problem: I've had reports where 80% of janky frames carried `screen=feed, scrolling=feed_list`, which turned a vague "the app is janky" into "the feed row does too much work in `onBindViewHolder`." That's a fix you can scope in an afternoon.

## How it detects jank under the hood

Understanding the mechanism keeps you from misreading the data:

- On **API 31+**, JankStats reads `FrameMetrics`, which gives real GPU/CPU frame duration reported by the framework.
- On **older APIs**, it falls back to an `OnPreDrawListener` and measures wall-clock frame time, which is coarser but still useful.
- A frame is "jank" when its duration exceeds a **deadline** = frame interval × a headroom multiplier (default around 2x). You can tune the multiplier if your bar is stricter.

Because the deadline derives from the *current* refresh rate, JankStats correctly holds a 120Hz device to a tighter budget. That's the whole point — it measures relative to what the user's display promised, not a fixed 16ms.

## Turning frames into a metric you track

Raw jank events aren't a dashboard. What I actually report:

| Metric | Why it matters |
|---|---|
| % janky frames (per screen) | Headline health per surface |
| % *severe* janky frames (>2 deadlines) | Severe jank hurts far more than borderline |
| Jank rate by device tier / refresh rate | Isolates "mid-tier only" problems |
| Jank rate by app version | Catches regressions after a release |

Segmenting by device tier and refresh rate is what surfaces the real issues, because a p50 across all devices hides the mid-tier disaster. Track it per app version and a jank regression shows up as a step change right after a rollout — the same regression-detection mindset behind [profiling ANRs and jank](https://blog.michaelsam94.com/killing-anrs-android-jank/), just measured continuously on real users.

## When JankStats points at something, go deeper

JankStats tells you *where and how often*, not *why*. Once it fingers a screen, I reproduce the interaction while capturing a [Perfetto trace](https://blog.michaelsam94.com/android-startup-tracing-perfetto/) and read the janky frames' main-thread work directly. The two tools form a loop: JankStats narrows the search space in production, Perfetto explains the mechanism locally, you fix it, and JankStats confirms the field number dropped in the next release.

A few field notes from shipping this:

- **Enable tracking only while resumed.** Frame data from a backgrounded window is noise.
- **Attach state at interaction boundaries and always remove it.** Stale state mislabels later frames.
- **Report a sample plus aggregates, not every frame.** Battery and bandwidth matter; you don't need every green frame.
- **Watch the first few frames after navigation.** They're legitimately heavier; decide whether to exclude them so they don't dominate your jank rate.

The reason I put JankStats in every app I own is that it closes the gap between "our benchmarks are green" and "users say it stutters." Frame timing measured on the devices people actually hold, tagged with the screen they were actually on, is the only jank metric that has ever led me straight to a fix.

## Resources

- [JankStats library overview (Android)](https://developer.android.com/topic/performance/jankstats)
- [FrameMetrics reference](https://developer.android.com/reference/android/view/FrameMetrics)
- [Rendering performance guide](https://developer.android.com/topic/performance/rendering)
- [Frame pacing and refresh rate](https://developer.android.com/games/sdk/frame-pacing)
- [Test frame timing with Macrobenchmark](https://developer.android.com/topic/performance/benchmarking/macrobenchmark-overview)
