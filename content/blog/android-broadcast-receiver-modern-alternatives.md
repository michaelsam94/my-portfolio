---
title: "Modern Alternatives to BroadcastReceivers"
slug: "android-broadcast-receiver-modern-alternatives"
description: "Replace implicit BroadcastReceivers with Flow, WorkManager, callbacks, and explicit broadcasts. What still needs receivers in modern Android and what doesn't."
datePublished: "2026-07-13"
dateModified: "2026-07-13"
tags: ["Android", "Architecture", "WorkManager", "Kotlin"]
keywords: "BroadcastReceiver alternatives, Android implicit broadcast, WorkManager vs BroadcastReceiver, modern Android events, broadcast receiver deprecated"
faq:
  - q: "Are BroadcastReceivers deprecated on Android?"
    a: "Implicit broadcast receivers registered in the manifest are heavily restricted since Android 8 (API 26) and further limited in Android 13+. Explicit broadcasts and dynamically registered receivers still work. Google recommends alternatives — WorkManager, callbacks, Flow, and direct API listeners — for most use cases that previously relied on implicit broadcasts."
  - q: "What should I use instead of a BOOT_COMPLETED receiver?"
    a: "For post-boot initialization, use WorkManager with constraints rather than a BOOT_COMPLETED broadcast receiver. WorkManager survives process death, respects battery optimization, and doesn't require holding a wake lock in a BroadcastReceiver. Register a periodic or one-time worker that runs after boot with NetworkType.CONNECTED or other appropriate constraints."
  - q: "When is a BroadcastReceiver still the right choice?"
    a: "Use dynamically registered receivers for events that happen while your app is in the foreground — USB attach/detach, headphone plug, locale changes during an active session. Use explicit broadcasts for intra-app communication between your own components. Avoid manifest-declared implicit receivers for system events — they're restricted and unreliable on modern Android."
---

If your app still has a manifest-registered `BroadcastReceiver` listening for `CONNECTIVITY_CHANGE` or `BOOT_COMPLETED`, it's probably not working reliably on Android 13+ — and if it is working, it's waking your process in ways that hurt battery and trigger background execution limits. Google has been systematically restricting implicit broadcasts since Android 8, pushing developers toward targeted alternatives. The migration isn't just about removing deprecated APIs; it's about building event handling that survives Doze, respects background limits, and doesn't depend on system-wide broadcasts that OEMs throttle differently.

## What changed

| Android version | Restriction |
|----------------|-------------|
| 8.0 (API 26) | Implicit broadcast receivers can't be declared in manifest (with exceptions) |
| 9.0 (API 28) | `CONNECTIVITY_ACTION` deprecated |
| 10 (API 29) | Background activity starts restricted from receivers |
| 13 (API 33) | `RECEIVER_EXPORTED` / `RECEIVER_NOT_EXPORTED` required for dynamic registration |
| 14 (API 34) | Further restrictions on implicit intent delivery |

The exceptions list (manifest-allowed implicit broadcasts) shrinks every release. Don't build new features on exceptions.

## Migration map

| Old pattern | Modern replacement |
|-------------|-------------------|
| `CONNECTIVITY_CHANGE` | `ConnectivityManager.registerDefaultNetworkCallback()` |
| `BOOT_COMPLETED` | WorkManager one-time/periodic work |
| `ACTION_POWER_CONNECTED` | WorkManager with `setRequiresBatteryNotLow()` or BatteryManager callbacks |
| `LOCALE_CHANGED` | `AppCompatDelegate` + per-activity locale handling |
| `MY_PACKAGE_REPLACED` | WorkManager triggered from `Application.onCreate()` version check |
| Custom app-wide events | SharedFlow / EventBus replacement |
| Download complete | `DownloadManager` callback or WorkManager |

## Network connectivity: NetworkCallback

Replace connectivity broadcasts with a callback registered while your app needs it:

```kotlin
class NetworkMonitor(private val context: Context) {
    private val _isConnected = MutableStateFlow(false)
    val isConnected: StateFlow<Boolean> = _isConnected.asStateFlow()

    private val callback = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) {
            _isConnected.value = true
        }
        override fun onLost(network: Network) {
            _isConnected.value = false
        }
    }

    fun start() {
        val cm = context.getSystemService(ConnectivityManager::class.java)
        cm.registerDefaultNetworkCallback(callback)
    }

    fun stop() {
        context.getSystemService(ConnectivityManager::class.java)
            .unregisterNetworkCallback(callback)
    }
}
```

Register in a lifecycle-aware component — start in `onStart`, stop in `onStop`. Don't register globally in Application; you'll leak callbacks and get events you can't act on in background anyway.

For offline-first sync, combine with [WorkManager](https://blog.michaelsam94.com/android-workmanager-vs-jobscheduler/) constraints:

```kotlin
val syncRequest = OneTimeWorkRequestBuilder<SyncWorker>()
    .setConstraints(Constraints.Builder()
        .setRequiredNetworkType(NetworkType.CONNECTED)
        .build())
    .build()
WorkManager.getInstance(context).enqueue(syncRequest)
```

WorkManager handles "sync when network available" better than a connectivity receiver ever did.

## Boot initialization: WorkManager

```kotlin
class PostBootWorker(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {
    override suspend fun doWork(): Result {
        schedulePeriodicSync()
        refreshConfigCache()
        return Result.success()
    }
}

// Enqueue from Application.onCreate on version change, not BOOT_COMPLETED
if (isFirstRunAfterUpdate()) {
    WorkManager.getInstance(this)
        .enqueueUniqueWork("post_boot", ExistingWorkPolicy.KEEP, postBootRequest)
}
```

If you genuinely need boot-time execution, `BOOT_COMPLETED` is still in the exception list — but WorkManager's `schedule()` persists across reboots and runs when constraints are met, which is almost always what you actually wanted.

## Intra-app events: SharedFlow

Replace local broadcasts between your own components:

```kotlin
// Old: LocalBroadcastManager (deprecated)
// New: application-scoped event bus
object AppEvents {
    private val _orderUpdated = MutableSharedFlow<String>(extraBufferCapacity = 1)
    val orderUpdated: SharedFlow<String> = _orderUpdated.asSharedFlow()

    fun notifyOrderUpdated(orderId: String) {
        _orderUpdated.tryEmit(orderId)
    }
}

// In ViewModel or Repository
AppEvents.orderUpdated.collect { orderId -> refreshOrder(orderId) }
```

Type-safe, lifecycle-aware (collect in coroutineScope), no manifest registration needed.

## When receivers still make sense

**Dynamically registered, foreground-only receivers** for hardware events during active use:

```kotlin
override fun onStart() {
    super.onStart()
    val filter = IntentFilter(UsbManager.ACTION_USB_DEVICE_ATTACHED)
    registerReceiver(usbReceiver, filter, RECEIVER_NOT_EXPORTED)
}

override fun onStop() {
    unregisterReceiver(usbReceiver)
    super.onStop()
}
```

Always specify `RECEIVER_NOT_EXPORTED` (API 33+) unless you explicitly need external apps to send to this receiver.

**Explicit broadcasts** between your own components when IPC is needed and BoundService is overkill — rare in modern apps.

## Audit your manifest

Find remaining receivers:

```bash
grep -r "BroadcastReceiver" app/src/main/AndroidManifest.xml
grep -r "<receiver" app/src/main/AndroidManifest.xml
```

For each one: is it in the exception list? Does it work on API 34? Is there a modern alternative? If yes to the last question, migrate.

Replace implicit broadcasts with WorkManager or Flow — Android 8+ background execution limits kill receivers that worked on API 24.

## Migration decision tree

```
Need to react to system event?
├── App in foreground?
│   ├── Yes → registerReceiver in onStart/onStop
│   └── No → is it in implicit broadcast exception list?
│       ├── Yes → manifest receiver (BOOT_COMPLETED, etc.)
│       └── No → WorkManager or polling JobScheduler
├── Your app's own event?
│   └── SharedFlow / callback / Room Flow
└── Cross-app IPC?
    └── BoundService or explicit broadcast to your package
```

Document every remaining manifest receiver with justification comment — future reviewers delete unexplained receivers.

## BOOT_COMPLETED responsibly

```kotlin
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED) return
        WorkManager.getInstance(context).enqueueUniqueWork(
            "sync-after-boot",
            ExistingWorkPolicy.KEEP,
            OneTimeWorkRequestBuilder<SyncWorker>().build()
        )
    }
}
```

Do heavy work in WorkManager, not in `onReceive` — ANR if boot receiver exceeds 10 seconds.

Pair with [Android WorkManager vs JobScheduler](https://blog.michaelsam94.com/android-workmanager-vs-jobscheduler/) for scheduling after boot and network availability.

## Common production mistakes

Teams get broadcast receiver modern alternatives wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping broadcast receiver modern alternatives on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Resources

- [Broadcasts overview (Android)](https://developer.android.com/develop/background-work/background-tasks/broadcasts)
- [Background execution limits](https://developer.android.com/about/versions/oreo/background)
- [ConnectivityManager.NetworkCallback](https://developer.android.com/reference/android/net/ConnectivityManager.NetworkCallback)
- [WorkManager guide](https://developer.android.com/topic/libraries/architecture/workmanager)
- [Android Doze and App Standby](https://blog.michaelsam94.com/android-doze-app-standby-buckets/)
