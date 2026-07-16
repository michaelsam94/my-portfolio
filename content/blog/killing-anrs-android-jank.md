---
title: "Killing ANRs: Diagnosing Android Jank and Freezes"
slug: "killing-anrs-android-jank"
description: "A field guide to killing ANRs and Android jank: what blocks the main thread, reading ANR traces, StrictMode, frame metrics, and the fixes that actually hold."
datePublished: "2026-04-10"
dateModified: "2026-04-10"
tags: ["Android", "Performance", "Kotlin", "Debugging"]
keywords: "ANR, Android jank, main thread blocking, Android performance, frozen frames, StrictMode, ANR trace"
faq:
  - q: "What causes an ANR on Android?"
    a: "An ANR (Application Not Responding) fires when the main thread is blocked too long — roughly 5 seconds for input events. The usual culprits are disk or network I/O on the main thread, heavy computation, lock contention, or a slow BroadcastReceiver or ContentProvider."
  - q: "How do I read an ANR trace?"
    a: "Find the 'main' thread in the trace and look at the top of its stack — that's what it was doing when it hung. If it's in a lock wait, follow the thread holding the lock. Play Console groups ANRs and often points at the blocking call directly."
  - q: "What's the difference between an ANR and jank?"
    a: "Jank is dropped frames — the UI stutters because a frame took longer than the ~16ms budget at 60Hz. An ANR is the extreme end: the main thread is blocked so long the system offers to kill the app. Both come from doing too much on the main thread; jank is the early warning, ANRs are the failure."
---

An ANR is the loudest thing your app can do to a user: the screen freezes, then the system asks if they want to kill it. Behind every ANR is a main thread that was blocked too long — around 5 seconds for input dispatch. Jank is the same disease in a milder form: individual frames blowing past the ~16ms budget so the UI stutters. Killing ANRs and jank is almost always about one thing — getting work off the main thread — but *finding* the offending work is where the real skill is. This is the diagnostic process I use.

I've triaged ANR spikes in production apps where the Play Console lit up after a release. The pattern repeats: the fix is usually small once you find it, and finding it is a matter of reading traces methodically instead of guessing.

## What actually blocks the main thread

The main (UI) thread does layout, drawing, and input dispatch. Anything else you run on it steals from that budget. The recurring offenders:

- **Disk I/O** — SharedPreferences `apply()` is async, but `commit()`, database queries, and file reads on the main thread block it.
- **Network on main** — rarer now, but a stray synchronous call still happens, especially in legacy code.
- **Heavy computation** — JSON parsing of a big payload, image decoding, sorting large lists.
- **Lock contention** — the main thread waiting on a lock held by a background thread.
- **Slow lifecycle callbacks** — a `BroadcastReceiver.onReceive` or `ContentProvider` doing real work; these have their own tighter ANR timeouts.
- **Binder calls** — synchronous IPC to a slow system service.

## Catch it in development with StrictMode

The cheapest win is making violations *loud* during development so they never reach production. `StrictMode` flags main-thread disk and network access the moment it happens:

```kotlin
if (BuildConfig.DEBUG) {
    StrictMode.setThreadPolicy(
        StrictMode.ThreadPolicy.Builder()
            .detectDiskReads()
            .detectDiskWrites()
            .detectNetwork()
            .penaltyLog()          // or penaltyDeath() to crash on violation
            .build()
    )
}
```

I run `penaltyDeath()` in debug on new projects — a hard crash on a main-thread disk read is annoying exactly once, and then nobody does it again. It catches the class of bug that becomes an ANR on a slow device or a cold disk.

## Reading an ANR trace

When an ANR fires, the system dumps `/data/anr/traces.txt` (surfaced in the Play Console under Android vitals). The method: find the `main` thread, look at the top frame. That's what it was stuck doing.

```
"main" prio=5 tid=1 Blocked
  | state=B
  at com.example.data.PrefStore.readToken(PrefStore.kt:42)
  - waiting to lock <0x0f3a> held by thread 12
  at com.example.MainActivity.onCreate(MainActivity.kt:88)
```

Two things to read here: the main thread is `Blocked` waiting on a lock, and the lock is held by thread 12. So the next step is to find thread 12 in the same trace and see what *it's* doing — that's the real cause. If the main thread's top frame is your own code doing I/O or computation, you've found it directly. Play Console clusters ANRs by this signature, which makes it easy to see which one to fix first by volume.

## Measure jank with frame metrics

Jank rarely produces a trace; you have to measure it. `JankStats` reports frames that missed their deadline, along with state you attach — so you learn *which screen* janks:

```kotlin
val jankStats = JankStats.createAndTrack(window) { frameData ->
    if (frameData.isJank) {
        analytics.log("jank", mapOf(
            "duration_ms" to frameData.frameDurationUiNanos / 1_000_000,
            "states" to frameData.states.joinToString { it.value }
        ))
    }
}
// tag the current screen so jank reports are attributable
stateHolder.putState("screen", "charger_list")
```

For deeper analysis, a Macrobenchmark with `FrameTimingMetric` gives you `frameDurationCpuMs` percentiles across a scripted scroll — that's how you turn "it feels laggy" into "P95 frame time on this list is 34ms." Perfetto/system traces then show *where* those milliseconds went.

## The fixes that hold

Once you've localized the blocking work, the fixes are familiar:

| Problem | Fix |
| --- | --- |
| Disk/DB on main | Move to `Dispatchers.IO` via a coroutine; make DAOs suspend |
| Big JSON parse | Parse off-main with `withContext(Dispatchers.Default)` |
| Heavy list work | Precompute off-main; use stable, keyed lists in Compose |
| Lock contention | Shrink critical sections; avoid holding locks across I/O |
| Slow startup work | Defer with App Startup / lazy init; use a Baseline Profile |
| Image decode | Use an image loader that decodes off-main (Coil) |

The coroutine version of "get off the main thread" is a one-liner once your data layer is suspend-friendly, which is another reason the [coroutines and Flow patterns](https://blog.michaelsam94.com/kotlin-coroutines-flow-patterns/) matter — `withContext(Dispatchers.IO)` around the blocking call, and the main thread is free again. On the Compose side, jank often traces back to recomposition doing too much, which is its own rabbit hole covered in [Compose performance and stability](https://blog.michaelsam94.com/compose-performance-stability-recomposition/).

## Make it a guardrail, not a fire drill

The teams that don't get surprised by ANRs treat main-thread health as a monitored metric: StrictMode in debug, `JankStats` piping to analytics, a Macrobenchmark frame-timing test in CI with a regression threshold, and a habit of watching Android vitals after every release. Keeping ANR rate under Google's bad-behavior threshold (0.47% of daily sessions) isn't just about ratings — it's the difference between an app that feels solid and one that feels broken on the exact low-end devices where most users are.

The mindset shift that helped me most: stop thinking of the main thread as "where my code runs" and start thinking of it as a real-time budget you're renting 16 milliseconds at a time. Everything else follows from protecting that budget.

## Resources

- [ANRs — diagnose and fix](https://developer.android.com/topic/performance/vitals/anr)
- [StrictMode reference](https://developer.android.com/reference/android/os/StrictMode)
- [JankStats library](https://developer.android.com/topic/performance/jankstats)
- [Frame timing and rendering](https://developer.android.com/topic/performance/vitals/render)
- [Capture a system trace with Perfetto](https://developer.android.com/topic/performance/tracing)
- [Android developers blog](https://android-developers.googleblog.com/)

*Fighting an ANR spike after a release? [Let's talk](/#contact) — trace-reading is half the battle.*
