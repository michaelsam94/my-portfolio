---
title: "Catching Bugs Early with StrictMode"
slug: "android-strictmode-debugging"
description: "Use Android StrictMode to catch main-thread disk and network I/O, leaked resources, and untagged sockets in development before they become production bugs."
datePublished: "2024-06-23"
dateModified: "2024-06-23"
tags: ["Android", "Debugging", "StrictMode", "Performance"]
keywords: "StrictMode, Android main thread I/O, disk reads on main thread, penaltyDeath, leaked closable, VmPolicy, ThreadPolicy"
faq:
  - q: "What is StrictMode used for?"
    a: "StrictMode is a developer tool that detects things your app does wrong that don't immediately crash — accidental disk or network I/O on the main thread, leaked Closeable resources, unclosed cursors, activity leaks, and untagged network sockets. It surfaces these during development so you fix them before they turn into ANRs or leaks in production."
  - q: "Should StrictMode run in production?"
    a: "Run it aggressively in debug builds, optionally with penaltyDeath to force fixes. In production you should not use penaltyDeath, but you can enable a lenient policy with penaltyLog or a custom penaltyListener to report violations to analytics, so you learn about real-device violations you never hit locally without crashing users."
  - q: "What is the difference between ThreadPolicy and VmPolicy?"
    a: "ThreadPolicy detects per-thread operations, primarily accidental disk and network I/O and slow calls on the main thread. VmPolicy detects process-wide problems like leaked Activities, leaked Closeable objects, unclosed SQLite cursors, and untagged sockets. You typically configure both in Application.onCreate for debug builds."
---

StrictMode is the cheapest bug-prevention tool Android ships, and most teams either never enable it or enable it, get annoyed by the warnings, and turn it off. Both are mistakes. StrictMode catches an entire class of latent bugs — main-thread disk and network I/O, leaked `Closeable` resources, unclosed cursors, activity leaks — the moment they happen in development, long before they surface as an ANR on a user's slow device or a slow memory leak in the field. It's not a profiler you run occasionally; it's a tripwire you leave armed in every debug build.

## The problem it solves

A `SharedPreferences.getString` or a small Room query on the main thread runs in under a millisecond on your flagship dev device. On a budget phone with a slow eMMC chip under memory pressure, that same call can block for 200ms — and if it happens during a touch event, that's a dropped frame or, chained with a few more, an ANR. You will *never* reproduce this locally by hand. StrictMode makes the mistake loud immediately: the first time your code touches disk on the main thread, it fires, regardless of how fast your device is.

## Turning it on

Configure both policies in `Application.onCreate`, gated to debug builds:

```kotlin
class MyApp : Application() {
    override fun onCreate() {
        super.onCreate()
        if (BuildConfig.DEBUG) {
            StrictMode.setThreadPolicy(
                StrictMode.ThreadPolicy.Builder()
                    .detectDiskReads()
                    .detectDiskWrites()
                    .detectNetwork()
                    .detectCustomSlowCalls()
                    .penaltyLog()
                    .penaltyFlashScreen()   // visible feedback on device
                    .build()
            )
            StrictMode.setVmPolicy(
                StrictMode.VmPolicy.Builder()
                    .detectLeakedClosableObjects()
                    .detectLeakedSqlLiteObjects()
                    .detectActivityLeaks()
                    .detectLeakedRegistrationObjects()
                    .penaltyLog()
                    .build()
            )
        }
    }
}
```

`ThreadPolicy` watches the current thread — in practice the main thread — for I/O and slow calls. `VmPolicy` watches the whole process for leaked resources. I start with `penaltyLog()` so every violation prints a full stack trace to Logcat pointing at the exact offending line.

## penaltyDeath is a decision, not a default

The strongest signal is `penaltyDeath()`, which crashes the app on any violation. It sounds brutal, and it's exactly what you want on a *fresh* codebase or a specific policy you've already cleaned up — it makes regressions impossible to ignore because CI or a manual run dies instantly. But dropping `penaltyDeath` onto a legacy app that has hundreds of pre-existing violations just makes the app unusable and gets StrictMode disabled entirely. My approach:

- **New code / clean policies:** `penaltyDeath()` for the specific detectors you've verified are clean (e.g. `detectDiskReads().penaltyDeath()` once you've fixed all main-thread reads).
- **Legacy code:** `penaltyLog()` first, burn down the violations, then promote individual detectors to `penaltyDeath()`.

## The violations you'll actually see

In order of how often they catch real bugs:

- **Disk reads on the main thread.** Almost always the first `SharedPreferences` access (the initial load reads the XML synchronously), a Room/SQLite query not on a background dispatcher, or reading a file in `onCreate`. The `SharedPreferences` first-read is such a common offender that migrating to [DataStore](https://blog.michaelsam94.com/android-datastore-migration-sharedpreferences/), which is async by design, removes a whole category of these.
- **Network on the main thread.** Rarer now that everyone uses coroutines/OkHttp off-thread, but a stray synchronous call in a library init still shows up.
- **Leaked `Closeable` objects.** A `Cursor`, `InputStream`, `FileInputStream`, or OkHttp `Response` body you opened and didn't close. StrictMode reports the *allocation* site, so you see where the un-closed object was created — invaluable.
- **Leaked SQLite cursors.** A query whose cursor was never closed. Use `use { }` or Room, which manages this for you.
- **Activity leaks.** VmPolicy flags a destroyed Activity still reachable, overlapping with what [LeakCanary](https://blog.michaelsam94.com/android-memory-leaks-leakcanary/) reports but with zero extra dependency.

## Scoping short, legitimate work

Occasionally you have a genuinely necessary main-thread read that you've measured and accepted (rare, but it happens during a critical init). Rather than disable the detector globally, suppress it narrowly with `permitDiskReads`:

```kotlin
val old = StrictMode.allowThreadDiskReads()
try {
    // a small, measured, unavoidable read
    val theme = prefs.getString("theme", "system")
} finally {
    StrictMode.setThreadPolicy(old)
}
```

This keeps the policy strict everywhere else while documenting the one place you've consciously allowed a read. If you find yourself doing this a lot, that's a signal your architecture has too much synchronous work on the main thread — fix that, don't paper over it.

## Getting production signal safely

The violations you hit locally are a subset of what real devices hit. On API 28+ you can attach a `penaltyListener` and report violations to analytics from internal or even production builds — without `penaltyDeath`, so nobody crashes:

```kotlin
StrictMode.ThreadPolicy.Builder()
    .detectAll()
    .penaltyListener(mainExecutor) { violation ->
        crashReporter.logNonFatal(violation)   // count, don't crash
    }
    .build()
```

I've caught real main-thread I/O this way that only manifested on specific OEM devices whose background services behaved differently than my test hardware. Treat those reports like the [production jank signal from JankStats](https://blog.michaelsam94.com/android-jank-frame-metrics-jankstats/): a prioritized list of real-device problems you'd never see otherwise.

## The habit that pays off

The teams whose apps stay responsive are the ones that leave StrictMode armed and treat a new violation as a build-breaking event, not a warning to scroll past. It costs nothing at runtime in release (it's off), it requires no ongoing effort once configured, and it converts an entire family of "works on my machine, ANRs in the field" bugs into a stack trace you fix in the minute you wrote them. Enable it, burn down the backlog, promote detectors to `penaltyDeath`, and never look back.

## Resources

- [StrictMode reference (Android)](https://developer.android.com/reference/android/os/StrictMode)
- [ThreadPolicy.Builder reference](https://developer.android.com/reference/android/os/StrictMode.ThreadPolicy.Builder)
- [VmPolicy.Builder reference](https://developer.android.com/reference/android/os/StrictMode.VmPolicy.Builder)
- [Keeping your app responsive (ANRs)](https://developer.android.com/topic/performance/vitals/anr)
- [App startup performance](https://developer.android.com/topic/performance/vitals/launch-time)
