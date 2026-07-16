---
title: "WorkManager for Reliable Background Work"
slug: "workmanager-reliable-background-work"
description: "How WorkManager guarantees Android background tasks survive process death, Doze, and reboots — constraints, chaining, expedited work, and the failure modes to avoid."
datePublished: "2026-04-20"
dateModified: "2026-04-20"
tags: ["Android", "WorkManager", "Kotlin", "Background Work"]
keywords: "WorkManager, Android background tasks, deferred work, background jobs, Android scheduling, constraints, expedited work"
faq:
  - q: "When should I use WorkManager instead of coroutines or a Service?"
    a: "Use WorkManager for deferrable work that must survive app death and reboots — uploads, syncs, log shipping. Use plain coroutines for work tied to a visible screen, and a foreground service only for ongoing user-visible tasks like navigation or media playback."
  - q: "Does WorkManager run immediately?"
    a: "No. Normal work is deferrable and the system batches it to save battery, so it may run minutes later. If you need it soon, use expedited work with setExpedited(), but even that is subject to system quotas."
  - q: "Does WorkManager work survive a reboot?"
    a: "Yes. WorkManager persists work requests in a Room database, so enqueued work is rescheduled after a reboot or process death. That persistence is the main reason to choose it over AlarmManager or a bare coroutine."
---

Every Android app eventually needs to do something the user isn't watching: upload a photo after a flaky connection recovers, sync a local database, ship analytics, refresh a token. The naive version — fire a coroutine and hope — works in the emulator and fails in the field, because the process gets killed, the network drops, or the device enters Doze. **WorkManager** is Android's answer for deferrable, guaranteed background work, and after shipping it across fintech and EV-charging apps I still reach for it first whenever "this must eventually happen" is the requirement.

The core promise is simple: you enqueue a request, WorkManager persists it to disk, and it runs your work when the constraints are met — even across process death and reboots. You give up control over *exactly when* in exchange for a guarantee that it *will* run.

## The mental model: deferrable and guaranteed

WorkManager is not a scheduler for "run this right now." It is for work that is **deferrable** (the system may batch it to save battery) but **guaranteed** (it survives the app being killed). If your work is tied to a visible screen, use a coroutine scoped to the ViewModel instead. If it's an ongoing user-visible task like turn-by-turn navigation, that's a foreground service. WorkManager sits in the middle: important, but patient.

Under the hood it picks the right execution engine for the OS version — `JobScheduler` on modern Android, with fallbacks — and stores every request in a Room database. That persistence is the whole point. `AlarmManager` and a bare coroutine both forget everything the moment the process dies.

## A Worker with constraints

Here's an upload worker that only runs on an unmetered network with the battery not low:

```kotlin
class UploadWorker(
    context: Context,
    params: WorkerParameters,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val fileUri = inputData.getString("file_uri")
            ?: return Result.failure()

        return try {
            api.upload(fileUri)
            Result.success()
        } catch (e: IOException) {
            // Transient — ask WorkManager to retry with backoff.
            if (runAttemptCount < 3) Result.retry() else Result.failure()
        }
    }
}

val request = OneTimeWorkRequestBuilder<UploadWorker>()
    .setConstraints(
        Constraints.Builder()
            .setRequiredNetworkType(NetworkType.UNMETERED)
            .setRequiresBatteryNotLow(true)
            .build()
    )
    .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
    .setInputData(workDataOf("file_uri" to uri.toString()))
    .build()

WorkManager.getInstance(context).enqueue(request)
```

Three details separate a toy from something that behaves in production. The **`Result` you return is a contract**: `success` and `failure` are terminal, `retry` re-enqueues with your backoff policy. The **backoff criteria** matter because a server hiccup shouldn't hammer the endpoint — exponential from 30 seconds is a sane default. And `runAttemptCount` lets you cap retries so a permanently-bad input doesn't retry forever.

## Constraints are the feature

The reason WorkManager beats hand-rolled scheduling is the constraint system. You declare the conditions and the OS enforces them without you writing a single `BroadcastReceiver` for connectivity:

| Constraint | Typical use |
| --- | --- |
| `NetworkType.UNMETERED` | Large uploads, media sync |
| `NetworkType.CONNECTED` | Any API call |
| `setRequiresCharging(true)` | Heavy CPU work, ML jobs |
| `setRequiresBatteryNotLow(true)` | Non-urgent sync |
| `setRequiresDeviceIdle(true)` | Maintenance, cleanup |

Combine them freely. A photo backup app I worked on used `UNMETERED` + charging + idle so it only ran overnight on Wi-Fi — battery complaints went to essentially zero because nothing woke the device on cellular.

## Unique work: the deduplication trap

The single most common WorkManager bug I see in code review is duplicate work. A user pulls-to-refresh three times and you enqueue three syncs. Use **unique work** to collapse them:

```kotlin
WorkManager.getInstance(context).enqueueUniquePeriodicWork(
    "sync",
    ExistingPeriodicWorkPolicy.KEEP, // don't restart if already scheduled
    PeriodicWorkRequestBuilder<SyncWorker>(6, TimeUnit.HOURS).build(),
)
```

For one-time work, `ExistingWorkPolicy.KEEP`, `REPLACE`, or `APPEND` control what happens when a request with the same name already exists. `KEEP` is what you almost always want for a periodic sync — enqueue it on every app start and trust WorkManager to ignore the duplicates.

Note periodic work has a **minimum interval of 15 minutes**, and the exact timing drifts because the system batches. If you need tighter timing, you're in foreground-service territory, not WorkManager.

## Expedited work and foreground service

When work genuinely needs to start soon — sending a message the user just tapped — use expedited work. WorkManager will run it promptly and, on older APIs, promote it to a foreground service:

```kotlin
val request = OneTimeWorkRequestBuilder<SendMessageWorker>()
    .setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)
    .build()
```

Inside the worker, implement `getForegroundInfo()` to supply the notification. Be honest with yourself about quotas: expedited work draws from a system budget, so it is not a loophole to make everything urgent. Abuse it and the system starts running your "expedited" work as normal deferred work anyway.

## Chaining and observing

Real pipelines have steps: compress, then upload, then clean up. WorkManager chains them and passes output data between stages:

```kotlin
WorkManager.getInstance(context)
    .beginWith(compressRequest)
    .then(uploadRequest)
    .then(cleanupRequest)
    .enqueue()
```

If any node returns `failure`, the chain stops and downstream work is cancelled. You can observe progress with `getWorkInfoByIdFlow(id)` and surface it in the UI via a `StateFlow`, which pairs naturally with the unidirectional data flow I described in [Jetpack Compose lessons from 10 years of Android](https://blog.michaelsam94.com/jetpack-compose-lessons-10-years-android/).

## Failure modes that bite

- **Assuming immediate execution.** Deferred work can run minutes later. Design the UX around "queued," not "done."
- **Doing UI work in the worker.** Workers run on a background thread with no guaranteed UI. Post results through your data layer.
- **Ignoring OEM battery managers.** Aggressive vendors (some Chinese OEMs are notorious) kill background work harder than stock Android. Test on real devices and point users to battery-optimization exemptions when the feature is critical.
- **Leaking dependencies.** Prefer a `WorkerFactory` (or Hilt's `@HiltWorker`) to inject your API client rather than reaching for globals.
- **Over-broad constraints.** Requiring charging *and* idle *and* unmetered can mean work never runs on a phone that's rarely plugged in. Loosen constraints until the guarantee is real.

WorkManager isn't glamorous, and that's the point. Enqueue the work, declare the constraints, return the right `Result`, and let the platform handle the rest across reboots, Doze, and process death. When background reliability matters — and in mobile it always eventually does — this is the boring, correct default. If you're wiring it into a larger app, it slots cleanly alongside the patterns I use for [handling flaky networks on mobile](https://blog.michaelsam94.com/handling-flaky-networks-mobile/).

## Resources

- [WorkManager — Android developer guide](https://developer.android.com/develop/background-work/background-tasks/persistent)
- [Define work requests](https://developer.android.com/develop/background-work/background-tasks/persistent/getting-started/define-work)
- [WorkManager constraints reference](https://developer.android.com/reference/androidx/work/Constraints)
- [Guide to background work](https://developer.android.com/develop/background-work/background-tasks)
- [Kotlin coroutines guide](https://kotlinlang.org/docs/coroutines-guide.html)
- [Hilt and WorkManager integration](https://developer.android.com/training/dependency-injection/hilt-jetpack#workmanager)
