---
title: "Kotlin Coroutines and Flow: Patterns That Scale"
seoTitle: "Scalable Kotlin Coroutines and Flow Patterns for Android"
slug: "kotlin-coroutines-flow-patterns"
description: "Production Kotlin coroutine and Flow patterns for Android — structured concurrency, StateFlow, SharedFlow events, retry with backoff, and testing without leaks."
datePublished: "2026-04-06"
dateModified: "2026-04-06"
tags: ["Kotlin", "Coroutines", "Flow", "Android"]
keywords: "Kotlin coroutines patterns, Flow Android, StateFlow ViewModel, structured concurrency, sharedFlow, coroutine testing, Kotlin Flow retry"
faq:
  - q: "What is structured concurrency in Kotlin coroutines?"
    a: "Structured concurrency ties every coroutine to a scope with a lifecycle — typically viewModelScope or a supervised job. When the scope cancels, all child coroutines cancel, preventing leaks and orphaned work after the user leaves a screen."
  - q: "When should I use StateFlow vs SharedFlow in Android?"
    a: "StateFlow holds the latest UI state and replays one value to new collectors — use it for screen state. SharedFlow emits one-off events like snackbars or navigation signals where replay would cause duplicate handling."
  - q: "How do I test Kotlin Flow without flaky tests?"
    a: "Use kotlinx-coroutines-test with runTest and Turbine to assert emissions in order. Inject TestDispatcher, avoid delay-based waits, and never use GlobalScope in code under test."
---

Coroutines and Flow are the default async stack on Android in 2026 — but "default" doesn't mean "automatically correct." I've debugged production incidents where an uncancelled collector kept polling OCPP chargers after logout, where a `SharedFlow` replayed navigation events on rotation, and where `flowOn` was applied in the wrong place so UI updates happened off the main thread. The patterns below are what I standardize on teams shipping at scale.

## Structured concurrency at the boundaries

Every coroutine belongs to a scope that outlives it. On Android that's `viewModelScope`, `lifecycleScope`, or a use-case scope you inject — never `GlobalScope`.

```kotlin
class ChargerDetailViewModel @Inject constructor(
    private val observeCharger: ObserveChargerUseCase,
    private val startSession: StartSessionUseCase,
) : ViewModel() {

    private val _uiState = MutableStateFlow(ChargerDetailUiState())
    val uiState: StateFlow<ChargerDetailUiState> = _uiState.asStateFlow()

    fun load(chargerId: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true) }
            observeCharger(chargerId)
                .catch { e -> _uiState.update { it.copy(error = e.message, isLoading = false) } }
                .collect { charger ->
                    _uiState.update { it.copy(charger = charger, isLoading = false) }
                }
        }
    }
}
```

When the ViewModel clears, `viewModelScope` cancels — the collector stops, the WebSocket closes, the polling job dies. If you spawn work outside that scope, you own the leak.

For parallel work with failure isolation, use `supervisorScope`:

```kotlin
suspend fun syncAllSites(sites: List<Site>) = supervisorScope {
    sites.map { site ->
        async { syncSite(site) } // one failure won't cancel siblings
    }.awaitAll()
}
```

## StateFlow for UI state, SharedFlow for events

The split I enforce in code review:

| Type | Use for | Replay? |
| --- | --- | --- |
| `StateFlow` | Screen state, form fields, loading flags | Yes — always has current value |
| `SharedFlow` | Snackbars, one-shot navigation, analytics pings | No replay (or explicit replay=0) |

```kotlin
private val _events = MutableSharedFlow<UiEvent>(extraBufferCapacity = 1)
val events: SharedFlow<UiEvent> = _events.asSharedFlow()

fun onStartClicked() {
    viewModelScope.launch {
        startSession(chargerId)
            .onSuccess { _events.emit(UiEvent.SessionStarted) }
            .onFailure { _events.emit(UiEvent.ShowError(it.message)) }
    }
}
```

Collect events in the UI with `LaunchedEffect` or `collectLatest` in a side-effect channel — not in the same collector as state, or rotation replays stale events.

```kotlin
LaunchedEffect(Unit) {
    viewModel.events.collect { event ->
        when (event) {
            is UiEvent.ShowError -> snackbarHostState.showSnackbar(event.message)
            UiEvent.SessionStarted -> onNavigateToSession()
        }
    }
}
```

## Flow operators that belong in the domain layer

Keep mapping and filtering out of composables and ViewModels when they're business rules:

```kotlin
class ObserveAvailableChargersUseCase(
    private val repository: ChargerRepository,
) {
    operator fun invoke(siteId: String): Flow<List<Charger>> =
        repository.observeChargers(siteId)
            .map { chargers -> chargers.filter { it.status == ChargerStatus.Available } }
            .distinctUntilChanged()
}
```

`distinctUntilChanged()` prevents recompositions when the list content is identical — critical when upstream emits on every database invalidation.

For combining sources:

```kotlin
fun observeDashboard(siteId: String): Flow<DashboardState> =
    combine(
        repository.observeChargers(siteId),
        repository.observeActiveSessions(siteId),
        repository.observeTariff(siteId),
    ) { chargers, sessions, tariff ->
        DashboardState(chargers, sessions, tariff)
    }.flowOn(Dispatchers.Default)
```

Apply `flowOn` **upstream** of operators you want off the main thread — it affects everything above it in the chain, not below.

## Retry, timeout, and backoff

Network Flows need explicit recovery:

```kotlin
fun <T> Flow<T>.retryWithBackoff(
    maxRetries: Int = 3,
    initialDelay: Duration = 1.seconds,
): Flow<T> = retryWhen { cause, attempt ->
    if (cause is IOException && attempt < maxRetries) {
        delay(initialDelay * (attempt + 1))
        true
    } else false
}
```

Pair with `timeout` on user-facing operations:

```kotlin
repository.observeChargerStatus(id)
    .timeout(30.seconds)
    .retryWithBackoff()
    .catch { emit(ChargerStatus.Unknown) }
```

Don't retry indefinitely — OCPP and REST endpoints need caps and circuit breakers at the repository layer.

## cold Flow vs hot Flow — know what you have

- **Cold** (default `flow { }`, repository queries): starts on collect, one collector = one execution unless you `shareIn`.
- **Hot** (`stateIn`, `shareIn`): active independent of collectors — use for expensive upstream shared across screens.

```kotlin
// In repository — share one WebSocket subscription app-wide
private val chargerUpdates = webSocket.messages
    .map { parse(it) }
    .shareIn(appScope, SharingStarted.WhileSubscribed(5_000), replay = 0)
```

`WhileSubscribed(5_000)` stops upstream 5 seconds after the last collector leaves — balances battery and freshness.

## Testing without flakes

```kotlin
@Test
fun `load emits charger`() = runTest {
    val charger = Charger(id = "1", name = "Bay A")
    val useCase = FakeObserveChargerUseCase(charger)

    val viewModel = ChargerDetailViewModel(useCase, fakeStart)
    viewModel.uiState.test {
        viewModel.load("1")
        assertEquals(true, awaitItem().isLoading)
        assertEquals(charger, awaitItem().charger)
        cancelAndIgnoreRemainingEvents()
    }
}
```

Use `StandardTestDispatcher` and `advanceUntilIdle()`. Never `Thread.sleep`. Inject dispatchers so `viewModelScope` runs on the test scheduler.

This testing discipline matters even more in [Kotlin Multiplatform production setups](https://blog.michaelsam94.com/kotlin-multiplatform-production-guide/) where the same Flow logic runs on iOS and Android — common tests catch regressions once.

## Anti-patterns I still see in review

- **`launch { flow.collect {} }` without cancellation handling** — use `collectLatest` when only the latest emission matters (search).
- **Mutating state inside `collect` without synchronization** — prefer `_uiState.update { }`.
- **`Dispatchers.IO` everywhere** — Default is fine for CPU mapping; IO only for blocking I/O.
- **Exposing `MutableStateFlow` publicly** — always `.asStateFlow()`.

## The short version

- Tie work to `viewModelScope`; cancel means stop everything.
- `StateFlow` for state, `SharedFlow` for one-shot events — never mix their semantics.
- Push operators into use cases; use `distinctUntilChanged` before UI.
- Retry with caps; timeout user-facing streams.
- Test with `runTest` and Turbine — no sleeps, no GlobalScope.

Coroutines scale when scope boundaries are obvious and Flow types match their job. Everything else is syntax.

## Resources

- [Coroutines guide](https://kotlinlang.org/docs/coroutines-guide.html)
- [Flow documentation](https://kotlinlang.org/docs/flow.html)
- [Coroutine context and dispatchers](https://kotlinlang.org/docs/coroutine-context-and-dispatchers.html)
- [Testing kotlinx.coroutines](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-test/)
- [Android coroutines best practices](https://developer.android.com/kotlin/coroutines/coroutines-best-practices)

*Hardening async code in a Kotlin Android app? [Get in touch](https://michaelsam94.com/).*
