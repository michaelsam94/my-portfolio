---
title: "Lifecycle-Aware Components Beyond ViewModel"
slug: "android-lifecycle-aware-components"
description: "Build lifecycle-aware components beyond ViewModel: DefaultLifecycleObserver, LifecycleService, repeatOnLifecycle, and avoiding leaks in Android architecture."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Android", "Architecture", "Lifecycle", "Kotlin"]
keywords: "Android lifecycle aware components, DefaultLifecycleObserver, repeatOnLifecycle, LifecycleService, lifecycle-aware architecture Android"
faq:
  - q: "What are lifecycle-aware components in Android?"
    a: "Lifecycle-aware components observe Android lifecycle events (onStart, onStop, onDestroy) and start/stop work automatically. ViewModel, LiveData, and LifecycleService are built-in examples. You can create custom components by implementing DefaultLifecycleObserver or LifecycleEventObserver to bind any resource or operation to lifecycle state."
  - q: "What is repeatOnLifecycle and why should I use it?"
    a: "repeatOnLifecycle is a coroutine builder that starts a block when the lifecycle reaches a target state (e.g., STARTED) and cancels it when the lifecycle drops below that state. It prevents collecting Flows when the UI isn't visible, avoiding wasted work and crashes from updating destroyed views."
  - q: "When should I use LifecycleService instead of a regular Service?"
    a: "Use LifecycleService when you need a bound or started Service that exposes lifecycle events to observers — useful for long-running foreground services where UI components need to observe service state. For most background work, prefer WorkManager over Services entirely."
---

ViewModel isn't the only thing that should respect lifecycle — but it's the only thing most teams think about. Every resource that outlives an Activity's visible window is a leak or wasted work waiting to happen: location updates firing while the app is backgrounded, Flow collectors pushing UI updates to a destroyed Fragment, camera sessions holding the sensor open, network callbacks registered in Application and never unregistered. Lifecycle-aware components bind start/stop to lifecycle state so you can't forget cleanup. The APIs have been stable for years; the gap is applying them beyond ViewModel.

## DefaultLifecycleObserver

Bind any object's lifecycle to an Activity or Fragment:

```kotlin
class LocationTracker(
    private val fusedClient: FusedLocationProviderClient
) : DefaultLifecycleObserver {

    private var callback: LocationCallback? = null

    override fun onStart(owner: LifecycleOwner) {
        callback = LocationCallback { result ->
            _location.value = result.lastLocation
        }
        fusedClient.requestLocationUpdates(request, callback!!, Looper.getMainLooper())
    }

    override fun onStop(owner: LifecycleOwner) {
        callback?.let { fusedClient.removeLocationUpdates(it) }
        callback = null
    }
}

// In Activity
override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    lifecycle.addObserver(locationTracker)
}
```

Location updates start when the Activity is visible, stop when it's not. No manual cleanup in onDestroy.

## repeatOnLifecycle for Flow collection

The correct way to collect Flows in UI — replaces `lifecycleScope.launch { flow.collect {} }`:

```kotlin
class OrdersFragment : Fragment() {
    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        viewLifecycleOwner.lifecycleScope.launch {
            viewLifecycleOwner.repeatOnLifecycle(Lifecycle.State.STARTED) {
                viewModel.orders.collect { orders ->
                    adapter.submitList(orders)
                }
            }
        }
    }
}
```

In Compose, use `collectAsStateWithLifecycle()`:

```kotlin
@Composable
fun OrdersScreen(viewModel: OrdersViewModel = hiltViewModel()) {
    val orders by viewModel.orders.collectAsStateWithLifecycle()
    // Automatically stops collecting when composable leaves composition
    // or lifecycle drops below STARTED
}
```

Without `repeatOnLifecycle`, Flow collection continues in background, wasting CPU and potentially crashing on UI updates.

## Lifecycle-aware coroutine scope

For components that aren't ViewModels but need scoped coroutines:

```kotlin
class SyncManager : DefaultLifecycleObserver {
    private var scope: CoroutineScope? = null

    override fun onStart(owner: LifecycleOwner) {
        scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
        scope?.launch { syncData() }
    }

    override fun onStop(owner: LifecycleOwner) {
        scope?.cancel()
        scope = null
    }
}
```

Or use `lifecycleScope` / `viewLifecycleOwner.lifecycleScope` directly in Activities and Fragments — these are already lifecycle-aware and cancel on destroy.

## ProcessLifecycleOwner for app-level awareness

Detect foreground/background at the application level:

```kotlin
class MyApp : Application(), DefaultLifecycleObserver {
    val isInForeground = MutableStateFlow(false)

    override fun onCreate() {
        super.onCreate()
        ProcessLifecycleOwner.get().lifecycle.addObserver(this)
    }

    override fun onStart(owner: LifecycleOwner) { isInForeground.value = true }
    override fun onStop(owner: LifecycleOwner) { isInForeground.value = false }
}
```

Use for: pausing/resuming analytics, deferring non-critical sync, adjusting polling frequency. Don't use for UI decisions — use Activity/Fragment lifecycle for that.

## LifecycleService

For foreground services that expose state to bound UI:

```kotlin
class MusicPlaybackService : LifecycleService() {
    private val _playbackState = MutableLiveData<PlaybackState>()
    val playbackState: LiveData<PlaybackState> = _playbackState

    override fun onCreate() {
        super.onCreate()
        lifecycle.addObserver(playbackLifecycleObserver)
    }
}

// In Activity
lifecycle.addObserver(object : DefaultLifecycleObserver {
    override fun onStart(owner: LifecycleOwner) {
        service.playbackState.observe(owner) { state -> updateUI(state) }
    }
})
```

LifecycleService lets bound Activities observe service LiveData/Flow with automatic cleanup. For most background work though, [WorkManager is the better choice](https://blog.michaelsam94.com/android-workmanager-vs-jobscheduler/) — LifecycleService is for user-visible ongoing operations (music, navigation, fitness tracking).

## Common lifecycle leaks

| Leak pattern | Fix |
|-------------|-----|
| Flow collected in `lifecycleScope.launch` without repeatOnLifecycle | Use `repeatOnLifecycle(STARTED)` |
| Listener registered in onCreate, not unregistered | Use DefaultLifecycleObserver or register in onStart/unregister in onStop |
| Callback registered on singleton/Application | Scope to ProcessLifecycleOwner or use WeakReference |
| Coroutine in ViewModel outliving need | Use viewModelScope (already lifecycle-aware) |
| ContentObserver on own provider | Use Room Flow instead |

## Lifecycle in modular architectures

In multi-module apps, expose lifecycle-aware interfaces from feature modules:

```kotlin
// feature module
interface FeatureLifecycleObserver : DefaultLifecycleObserver

// app module
class FeatureManager @Inject constructor(
    private val observers: Set<@JvmSuppressWildcards FeatureLifecycleObserver>
) {
    fun attach(lifecycle: Lifecycle) {
        observers.forEach { lifecycle.addObserver(it) }
    }
}
```

Each feature module contributes its lifecycle observer via [Hilt multibindings](https://blog.michaelsam94.com/android-hilt-multibindings/). The app module attaches them to the Activity lifecycle.

## ProcessLifecycleOwner for app-wide state

Detect foreground/background at application level:

```kotlin
ProcessLifecycleOwner.get().lifecycle.addObserver(object : DefaultLifecycleObserver {
    override fun onStart(owner: LifecycleOwner) {
        analytics.track("app_foreground")
        syncManager.resumePeriodicSync()
    }
    override fun onStop(owner: LifecycleOwner) {
        analytics.track("app_background")
        syncManager.pausePeriodicSync()
    }
})
```

`onStop` fires ~700ms after last activity stops — not instant. Don't use for security-sensitive "user left app" logic; use `ActivityLifecycleCallbacks` with activity count.

## Lifecycle in Compose

```kotlin
@Composable
fun OrderTracker(viewModel: OrderViewModel = hiltViewModel()) {
    val lifecycleOwner = LocalLifecycleOwner.current
    LaunchedEffect(lifecycleOwner) {
        lifecycleOwner.lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) {
            viewModel.trackActiveOrders().collect { orders -> /* update UI */ }
        }
    }
}
```

Prefer `LifecycleEventEffect` (Compose 1.7+) for one-shot events:

```kotlin
LifecycleEventEffect(Lifecycle.Event.ON_RESUME) {
    viewModel.refreshIfStale()
}
```

## Testing lifecycle behavior

Use `LifecycleRegistry` in unit tests:

```kotlin
@Test
fun pausesSyncOnStop() {
    val registry = LifecycleRegistry(lifecycleOwner)
    val observer = SyncLifecycleObserver(syncManager)
    registry.addObserver(observer)
    registry.handleLifecycleEvent(Lifecycle.Event.ON_STOP)
    verify(syncManager).pause()
}
```

Robolectric provides full lifecycle for instrumented-style tests without emulator.

Pair with [Android WorkManager vs JobScheduler](https://blog.michaelsam94.com/android-workmanager-vs-jobscheduler/) for deferrable work that shouldn't tie to Activity lifecycle.

## Common production mistakes

Teams get lifecycle aware components wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping lifecycle aware components on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Resources

- [Handling lifecycles with lifecycle-aware components](https://developer.android.com/topic/libraries/architecture/lifecycle)
- [repeatOnLifecycle API reference](https://developer.android.com/reference/kotlin/androidx/lifecycle/package-summary#repeatOnLifecycle(androidx.lifecycle.Lifecycle,androidx.lifecycle.Lifecycle.State,kotlin.coroutines.SuspendFunction0))
- [LifecycleService reference](https://developer.android.com/reference/androidx/lifecycle/LifecycleService)
- [ProcessLifecycleOwner documentation](https://developer.android.com/reference/android/arch/lifecycle/ProcessLifecycleOwner)
- [Surviving process death with SavedStateHandle](https://blog.michaelsam94.com/android-savedstatehandle-process-death/)
