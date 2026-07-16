---
title: "Hunting Memory Leaks with LeakCanary"
slug: "android-memory-leaks-leakcanary"
description: "Find and fix Android memory leaks with LeakCanary: read the leak trace, understand the shortest path to GC root, and fix the common Activity and listener leaks."
datePublished: "2024-06-22"
dateModified: "2024-06-22"
tags: ["Android", "Memory", "LeakCanary", "Debugging"]
keywords: "LeakCanary, Android memory leaks, leak trace, GC root, retained instance, Activity leak, OutOfMemoryError"
faq:
  - q: "How does LeakCanary detect a leak?"
    a: "LeakCanary watches objects that should be garbage collected — destroyed Activities, Fragments, ViewModels — using weak references. When one of them stays reachable after it should have been freed, LeakCanary triggers a heap dump, finds the shortest strong reference path from a GC root to the leaked object, and reports it. That shortest path is almost always where your bug lives."
  - q: "Does LeakCanary run in production?"
    a: "The standard leakcanary-android artifact is debug-only and should never ship in release builds because heap dumps are expensive and disruptive. For production signal there's a separate lightweight ObjectWatcher setup you can use to count retained instances without dumping the heap, but the full analyzer belongs in debug and internal builds only."
  - q: "What is the most common cause of Activity leaks?"
    a: "A long-lived object holding a reference to an Activity or its Context. The classic offenders are static fields, singletons that capture a Context, non-static inner classes and anonymous listeners that implicitly hold the outer Activity, and callbacks or handlers you register but never unregister. The Activity gets destroyed on rotation, but something still points at it, so it can't be collected."
---

A memory leak on Android almost never announces itself as an `OutOfMemoryError` — it shows up as an app that gets slower and jankier the longer it runs, then crashes for a user you can't reproduce. LeakCanary is the tool that makes those leaks concrete: it watches objects that should have been garbage collected, and when one lingers, it dumps the heap and hands you the *shortest strong reference path* from a GC root to the leaked object. Ninety percent of the time, reading that path top to bottom tells you exactly which reference to sever. The skill isn't installing it — it's reading the trace.

## Installing it is one line, and that's the point

```kotlin
dependencies {
    debugImplementation("com.squareup.leakcanary:leakcanary-android:2.14")
}
```

No code, no `Application` hook. LeakCanary auto-installs via a ContentProvider in debug builds and starts watching destroyed Activities, Fragments, Fragment views, ViewModels, and Services automatically. Keep it on `debugImplementation` — the full analyzer dumps the heap and freezes the app for a few seconds, which is fine while developing and unacceptable in release.

## What it actually watches

LeakCanary wraps expiring objects in weak references through its `ObjectWatcher`. The lifecycle is:

1. An object that should die is handed to the watcher (e.g. `Activity.onDestroy` runs).
2. LeakCanary waits, then forces a GC.
3. If the weak reference was cleared, great — no leak.
4. If the object is *still reachable*, it's a **retained instance**. After a threshold of retained instances, LeakCanary dumps the heap and analyzes it.

You can watch your own objects too, which I do for anything with a clear lifecycle — presenters, controllers, sessions:

```kotlin
AppWatcher.objectWatcher.expectWeaklyReachable(
    session, "AuthSession should be cleared after logout"
)
```

## Reading the leak trace is the whole skill

Here's a representative trace LeakCanary produces:

```text
┬───
│ GC Root: Global variable in native code
│
├─ com.example.AnalyticsManager class
│    Leaking: NO (a class is never leaking)
│    ↓ static AnalyticsManager.instance
├─ com.example.AnalyticsManager instance
│    Leaking: UNKNOWN
│    ↓ AnalyticsManager.context
├─ com.example.CheckoutActivity instance
│    Leaking: YES (Activity#mDestroyed is true)
```

Read it as a chain of "who holds whom." The **GC root** at the top is why the whole chain is alive. The **leaking object** at the bottom is what should have died. The reference that *shouldn't exist* is somewhere in between, and LeakCanary even highlights the suspect with `Leaking: UNKNOWN` transitioning to `YES`. In this trace, the story is unambiguous: a static `AnalyticsManager.instance` (a singleton) captured an `Activity` as its `context`, so the destroyed `CheckoutActivity` can never be collected. The fix is to pass `applicationContext`, not the Activity.

## The leaks I find over and over

Almost every leak I've chased reduces to one of these:

- **Singletons holding an Activity Context.** Pass `applicationContext` to anything that outlives a screen. If a singleton genuinely needs a themed/UI Context, it probably shouldn't be a singleton.
- **Unregistered listeners and callbacks.** You register a `BroadcastReceiver`, `LocationListener`, `SensorEventListener`, or a library callback in `onStart`/`onResume` and forget to unregister in the mirror lifecycle method. The framework keeps a strong reference and drags your Activity along.
- **Anonymous inner classes capturing `this`.** An anonymous `Runnable`, `Handler` callback, or click listener implicitly holds the outer Activity. If that object outlives the Activity (posted with a long delay, stored in a long-lived collection), the Activity leaks.
- **Long-running background work with a UI reference.** A coroutine or thread that holds a view or Activity and runs past `onDestroy`. Scope coroutines to `viewModelScope` or `lifecycleScope` so cancellation is automatic.
- **`Handler` and delayed messages.** `handler.postDelayed(runnable, 60_000)` from an Activity keeps it alive for a minute. Remove callbacks in `onDestroy` or use a lifecycle-aware alternative.

## Fixing, not silencing

The temptation when a trace involves framework or library internals is to add it to `LeakCanary.config` ignore lists. Resist that unless you've confirmed it's a known platform leak (there are a few genuine ones — `InputMethodManager` has historically held Views). For your own code, the fixes are mechanical once the path is clear:

```kotlin
// Leaks: anonymous listener captures the Activity, never removed.
sensorManager.registerListener(object : SensorEventListener {
    override fun onSensorChanged(e: SensorEvent) { updateUi(e) } // holds Activity
    override fun onAccuracyChanged(s: Sensor, a: Int) {}
}, sensor, SensorManager.SENSOR_DELAY_UI)

// Fixed: keep a reference, unregister in the mirror lifecycle callback.
private val listener = object : SensorEventListener { /* ... */ }
override fun onStart() { sensorManager.registerListener(listener, sensor, DELAY_UI) }
override fun onStop()  { sensorManager.unregisterListener(listener) }
```

The `onStart`/`onStop` symmetry is the discipline that prevents most listener leaks. Register and unregister in mirrored callbacks, every time.

## Production signal without the heap dump

You don't want the full analyzer in release, but you *do* want to know if retained-instance counts spike in the field. LeakCanary's underlying `ObjectWatcher` (from the `leakcanary-object-watcher-android` artifact) is cheap enough to keep on and report a count of retained-but-not-collected objects to your analytics. That won't tell you the path, but a rising retained count on a specific screen is a strong hint to reproduce it in a debug build and let the full analyzer draw the trace.

Memory leaks compound with every other performance problem — a heap full of leaked bitmaps means more GC pauses, which shows up as [jank you'll see in JankStats](https://blog.michaelsam94.com/android-jank-frame-metrics-jankstats/) and slower [cold starts under memory pressure](https://blog.michaelsam94.com/android-startup-tracing-perfetto/). Fixing leaks is one of the cheapest wins for overall smoothness. LeakCanary's real gift is that it turns "the app degrades over time" — the hardest class of bug to reproduce — into a stack trace pointing at the exact reference to delete.

## Resources

- [LeakCanary documentation](https://square.github.io/leakcanary/)
- [LeakCanary fundamentals — how it works](https://square.github.io/leakcanary/fundamentals-how-leakcanary-works/)
- [Manage your app's memory (Android)](https://developer.android.com/topic/performance/memory)
- [Overview of Android memory management](https://developer.android.com/topic/performance/memory-overview)
- [Inspect the Java heap with Memory Profiler](https://developer.android.com/studio/profile/memory-profiler)
