---
title: "Analyzing ANR Clusters in Play Vitals"
slug: "android-anr-cluster-analysis-vitals"
description: "A practical method for analyzing ANR clusters in Android Play Vitals: reading ANR stack traces, grouping by root cause, and fixing the main-thread stalls that matter."
datePublished: "2024-10-04"
dateModified: "2024-10-04"
tags: ["Android", "Performance", "Play Vitals", "Debugging"]
keywords: "ANR analysis, Play Vitals ANR, Android ANR clusters, ANR rate, main thread blocked, application not responding"
faq:
  - q: "What counts as an ANR on Android?"
    a: "An ANR (Application Not Responding) fires when the main thread is blocked too long to handle user input or a broadcast — commonly around 5 seconds for input dispatch. The system captures a trace of all threads at that moment and, if the app is distributed on Play, reports it in Android Vitals. ANRs directly hurt your Play Store standing because they're part of the core vitals thresholds."
  - q: "How do I find the root cause of an ANR from its trace?"
    a: "Start with the main thread's stack at the top of the ANR trace — it shows what the main thread was doing when it stalled. If it's blocked on a lock, find which other thread holds that lock; if it's in I/O or a synchronous call, that's your culprit. Group ANRs with similar main-thread frames into clusters so you fix one root cause per cluster rather than chasing individual reports."
  - q: "What ANR rate should I aim for?"
    a: "Google's bad-behavior threshold in Vitals is a user-perceived ANR rate around 0.47%, and exceeding it can affect your app's visibility. Realistically you want to be well under that, ideally below 0.2%, since ANRs cluster and a single bad release can spike the rate. Track the rate per release so a regression is caught before it spreads across your install base."
---

ANRs are the performance failure users feel most viscerally — the app freezes, then Android offers to kill it — and they're the metric Google weighs heavily in Play's core vitals. The trap teams fall into is treating each ANR report as an individual bug. There are thousands of reports; you cannot fix them one at a time. The skill is **clustering**: recognizing that those thousands of reports collapse into a handful of root causes, and fixing the cause behind each cluster. I've turned a scary-looking ANR dashboard into three actual bugs more than once, and the method is repeatable.

## What an ANR trace actually contains

When the main thread can't service input for ~5 seconds, Android snapshots **every thread's stack** and reports it. In Play Vitals you get these aggregated. The single most important thing in the whole trace is the **main thread's top frames** — that's what the UI thread was stuck doing when the watchdog fired. Everything else is context for *why* the main thread was stuck.

Two broad shapes cover most ANRs:

- **The main thread is doing work it shouldn't** — synchronous I/O, a huge JSON parse, a slow Binder/IPC call, database work on the main thread.
- **The main thread is blocked waiting** — parked on a lock (`monitor`/`wait`) that another thread holds, or waiting on a slow synchronous callback.

The first is "you did too much on the main thread." The second is "you serialized the main thread behind something slow." They're diagnosed differently, which is why reading the trace correctly matters.

## Clustering: turn thousands of reports into a few bugs

Play Vitals already groups ANRs by similarity, but the grouping isn't always the *root-cause* grouping you want. My process:

1. **Sort clusters by user-perceived ANR rate**, not raw count. A cluster hitting 0.1% of sessions matters more than one that's cosmetically frequent but rare per-user.
2. **For each cluster, read the aggregated main-thread stack.** Identify the top app frame (skip framework frames) — that's the anchor for the cluster's root cause.
3. **Merge clusters that share a root cause.** Vitals may split one bug across several signatures (different call sites into the same slow method). If three clusters all bottom out in `Database.query` on the main thread, that's *one* bug.
4. **Rank by impact × fixability.** Fix the high-rate, clearly-diagnosable clusters first. A vague native-side stall you can't reproduce goes to the bottom.

The mindset shift is treating clusters as *hypotheses about a root cause* rather than as a list of things to individually close.

## Reading the two ANR shapes

**Main thread doing work.** The top app frame *is* the answer. If you see `readFromDisk`, `SharedPreferences` commit, `Gson.fromJson`, or a `ContentResolver.query` on the main thread, the fix is to move it off — coroutines on a background dispatcher, and don't block on the result.

```text
main (RUNNABLE):
  at com.example.Repo.loadSettings   <-- reading a large file synchronously
  at com.example.MainActivity.onCreate
```

**Main thread blocked on a lock.** The main thread's stack shows `waiting to lock <0x...>` in a `monitor` state. Now you have to find **who holds that lock** — search the other threads in the trace for the one *holding* `0x...`, often doing something slow. The bug isn't the main thread; it's the background thread hogging a shared lock.

```text
main (BLOCKED):
  waiting to lock <0x0c3f> held by thread 14
thread-14 (RUNNABLE):
  at com.example.Cache.rebuild        <-- slow work holding the lock main needs
```

This second shape is the one people misread — they "optimize" the main-thread frame that's just *waiting*, and the real fix is shrinking the critical section or removing the lock contention on thread-14.

## Common root causes I keep finding

| Cluster signature | Root cause | Fix direction |
| --- | --- | --- |
| Main thread in file/DB/prefs I/O | Synchronous I/O on UI thread | Move to background dispatcher |
| Main thread `BLOCKED` on lock | Contended lock held by slow bg work | Shrink critical section / avoid shared lock |
| Main thread in Binder transact | Slow IPC / ContentProvider | Async call, cache result |
| ANRs spike at startup | Heavy `Application.onCreate` init | Defer/lazy-init SDKs |
| Main thread in large parse | Big JSON/bitmap on UI thread | Parse off main thread, stream |

Startup ANRs deserve special mention: if your `Application.onCreate` synchronously spins up ten SDKs, a slow device stalls past the threshold before your first screen even shows. That's the same startup-hygiene lever behind [ProfileInstaller and startup performance](https://blog.michaelsam94.com/android-profileinstaller-startup/) — do less on the critical path, and do it asynchronously.

## Reproducing and confirming

An ANR you can't reproduce is hard to confirm fixed. Techniques that help:

- **StrictMode** in debug flags main-thread disk and network reads *before* they become ANRs in the field — it turns "someday a slow phone will ANR here" into an immediate log during development.
- **Slow devices and cold caches.** ANRs cluster on low-end devices and first-launch conditions; test there, not just on your flagship.
- **The `App Exit Info` API** gives you on-device ANR reasons and traces you can capture in your own crash pipeline, complementing Vitals with more context.
- Moving the offending work off the main thread with structured concurrency — the injectable-dispatcher [coroutine patterns](https://blog.michaelsam94.com/kotlin-coroutines-flow-patterns/) make it both correct and testable.

Then **watch the rate per release.** ANR rate is noisy in aggregate but clear per-version: a fix should visibly drop the cluster's rate in the release that ships it. If it doesn't, your hypothesis about the root cause was wrong — back to the trace.

## What I'd take away

ANRs are a clustering problem, not a whack-a-mole of individual reports. Read the main thread's top frames first: either it's doing work it shouldn't (move it off the main thread) or it's blocked on a lock (find and fix the thread holding it). Merge Vitals clusters that share a root cause, prioritize by user-perceived rate times fixability, and confirm each fix by watching that cluster's rate drop in the shipping release. Add StrictMode and slow-device testing to catch main-thread stalls before users do. Handled this way, a thousand-report ANR dashboard becomes three or four real bugs — which is a very fixable number.

## Main thread stack signature clustering

Play Vitals groups ANR by native stack — Kotlin coroutine ANRs often show `BlockingCoroutine` pattern. Symbolicate with R8 mapping; cluster `android.os.MessageQueue.nativePollOnce` with top app frame for actionable owner.

## Input dispatching timeout vs Broadcast ANR

Different remediation: input ANR needs main thread profiling; `BroadcastReceiver` ANR needs goAsync or WorkManager migration. Tag internal ANR repro with type before filing framework bug.

## Anr Cluster Analysis Vitals Supplement 0 on Samsung and Pixel divergence

Exercise anr cluster analysis vitals supplement 0 on Galaxy A-series and Pixel a-series — emulators hide OEM battery and storage quirks. Capture Macrobenchmark or Firebase trace for the critical path touching anr; regressions above 8% block release for `android-anr-cluster-analysis-vitals-supplement-0`.

Document permission and background behavior in internal runbook: what breaks under Doze, what requires foreground service, and what Play policy declarations apply. Support tickets referencing "Anr Cluster Analysis Vitals Supplement 0" should map to a single runbook section with known workarounds.

## Vitals regression gates for Play Vitals

Before promoting `android-anr-cluster-analysis-vitals-supplement-0` changes past 20% rollout, compare ANR rate, slow cold start, and excessive wakeups against seven-day baseline. Fail rollback review if 0 path shows >5% increase in `slow frames` without documented trade-off approval.

## Resources

- [Android Vitals — ANRs](https://developer.android.com/topic/performance/vitals/anr)
- [Diagnose and fix ANRs](https://developer.android.com/topic/performance/anrs/diagnose-and-fix-anrs)
- [ApplicationExitInfo API](https://developer.android.com/reference/android/app/ApplicationExitInfo)
- [StrictMode](https://developer.android.com/reference/android/os/StrictMode)
- [Core vitals thresholds in Play Console](https://support.google.com/googleplay/android-developer/answer/9844486)
