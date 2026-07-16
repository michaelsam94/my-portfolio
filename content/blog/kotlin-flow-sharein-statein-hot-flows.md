---
title: "Hot Flows in Kotlin: shareIn vs stateIn"
slug: "kotlin-flow-sharein-statein-hot-flows"
description: "shareIn vs stateIn for turning cold Kotlin flows hot: sharing strategies, replay, and the WhileSubscribed timeout that prevents leaks and redundant work."
datePublished: "2024-06-05"
dateModified: "2024-06-05"
tags: ["Kotlin", "Coroutines", "Android"]
keywords: "shareIn stateIn, hot flow, SharingStarted, WhileSubscribed, StateFlow SharedFlow, cold flow to hot"
faq:
  - q: "What is the difference between shareIn and stateIn?"
    a: "shareIn converts a cold flow into a hot SharedFlow, letting you configure replay count and buffering, and it has no notion of a current value. stateIn converts a cold flow into a hot StateFlow, which always holds exactly one current value, requires an initial value, and conflates updates. Use stateIn for state a UI reads on demand and shareIn for event streams where you control replay."
  - q: "What does SharingStarted.WhileSubscribed do?"
    a: "WhileSubscribed starts the upstream flow when the first subscriber appears and stops it when the last one leaves. The optional stopTimeoutMillis keeps the upstream alive briefly after the last subscriber disappears, so a short configuration change like a screen rotation doesn't tear down and restart the flow. This is the standard choice for Android to avoid leaks and redundant restarts."
  - q: "Why does converting a cold flow to hot matter?"
    a: "A cold flow re-runs its producer for every collector, so two observers of the same database query trigger two queries. Making it hot with shareIn or stateIn runs the producer once and multicasts the result to all collectors, eliminating the duplicated upstream work. It also lets late subscribers receive a replayed value instead of nothing."
---

If two parts of your app collect the same cold `Flow`, the producer runs twice — two database reads, two network calls, two of everything upstream. `shareIn` and `stateIn` are the operators that fix this by turning a cold flow hot: the upstream runs once and its emissions are multicast to every collector. The choice between them comes down to one question — does this stream represent *state* (a current value someone reads on demand) or *events* (a series you react to as they arrive)? State wants `stateIn`; events want `shareIn`.

I've debugged more than one screen that fired duplicate network requests because a `ViewModel` exposed a raw cold flow and two collectors subscribed. The fix is almost always a single operator, but picking the wrong one — or the wrong sharing strategy — trades a duplicate-request bug for a subtler leak or a stale-data bug. So it's worth understanding what each actually does.

## Cold vs hot, in one example

A cold flow's block runs from scratch per collector:

```kotlin
val prices: Flow<Price> = flow {
    println("opening socket")   // runs once PER collector
    emitAll(priceSocket())
}
```

Two collectors, two sockets, two "opening socket" logs. Making it hot fixes that:

```kotlin
val prices: SharedFlow<Price> = flow {
    println("opening socket")   // runs once, TOTAL, while subscribed
    emitAll(priceSocket())
}.shareIn(scope, SharingStarted.WhileSubscribed(5_000))
```

Now the flow block runs once regardless of collector count, and everyone shares the same socket. That's the entire point of "hot": the producer's lifecycle is decoupled from any single collector.

## stateIn: for state with a current value

`stateIn` produces a `StateFlow`, which always has a `.value`. It requires an `initialValue` because a `StateFlow` can never be empty — there's always a current value to read, even before the upstream emits.

```kotlin
val uiState: StateFlow<UiState> =
    repository.observeUser()
        .map { UiState.Loaded(it) }
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(5_000),
            initialValue = UiState.Loading,
        )
```

This is the canonical Android `ViewModel` pattern. The UI collects `uiState`; before the repository emits, collectors see `Loading`; after, they see the latest `Loaded`. Two properties define `StateFlow`'s behavior: it's *conflated* (slow collectors skip intermediate values and only see the latest) and it *deduplicates* using `equals` (emitting a value equal to the current one produces nothing downstream). For UI state that's exactly right — you want the freshest state, and re-emitting an identical state to trigger a recomposition is wasted work. It pairs directly with the [recomposition and stability concerns](https://blog.michaelsam94.com/kotlin-immutable-collections-kotlinx/) that make Compose UIs fast.

That conflation is also a trap if you misuse it. If your "state" is really a stream of discrete events — navigation commands, snackbar triggers — `stateIn`'s dedup and conflation will silently drop events. Two identical "show error" events become one; a fast burst gets collapsed. That's when you want `shareIn`.

## shareIn: for events and configurable replay

`shareIn` produces a `SharedFlow` and gives you explicit control over replay and buffering, with no concept of a "current value."

```kotlin
val events: SharedFlow<AppEvent> =
    eventSource()
        .shareIn(
            scope = appScope,
            started = SharingStarted.Eagerly,
            replay = 0,   // new subscribers get nothing from the past
        )
```

`replay = 0` means a subscriber only sees events emitted *after* it subscribes — correct for one-shot events you don't want redelivered. `replay = 1` caches the last value for late subscribers, approximating `StateFlow` but without dedup or an initial value. Because there's no `equals`-based conflation, `shareIn` faithfully delivers every emission (subject to the buffer), which is what you need for events where "two identical ones" is meaningfully different from "one."

The mental split I use: `stateIn` answers "what is the current value?"; `shareIn` answers "what has happened?" Getting this wrong is the single most common Flow bug I review.

## SharingStarted: the strategy that prevents leaks

Both operators take a `SharingStarted` that decides *when* the upstream runs. The three options:

| Strategy | Upstream starts | Upstream stops | Use for |
|---|---|---|---|
| `Eagerly` | immediately, at creation | never (until scope dies) | always-on app-wide streams |
| `Lazily` | on first subscriber | never | start-once, keep-forever |
| `WhileSubscribed(t)` | on first subscriber | `t` ms after last leaves | almost all UI state |

`WhileSubscribed(5_000)` is the default advice for Android for a specific reason: a screen rotation unsubscribes and resubscribes within milliseconds. Without the timeout, the upstream would tear down and cold-restart on every rotation — re-running your query or reconnecting your socket. The 5-second grace window lets a configuration change pass without restarting the flow, while still stopping work when the user actually navigates away. Set it to `0` and you get restart-on-rotation; use `Eagerly` and the flow keeps running with the screen closed, which leaks a socket or a wakelock. Five seconds is the sweet spot that survives config changes without keeping work alive indefinitely.

```kotlin
// Survives rotation, stops ~5s after the screen truly closes.
.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), initial)
```

## The scope matters as much as the operator

Both operators take a `CoroutineScope`, and that scope owns the shared flow's lifetime. Get it wrong and neither the sharing strategy nor the operator saves you. Use `viewModelScope` for screen-scoped state so it dies with the `ViewModel`; use an application-scoped coroutine only for genuinely app-wide streams. Sharing into a scope that outlives the data is how you leak the upstream forever, which connects to the broader discipline of [structured concurrency and job hierarchies](https://blog.michaelsam94.com/kotlin-structured-concurrency-supervisorjob/) — the scope isn't a detail, it's the thing that guarantees cleanup.

## A decision checklist

When you're staring at a cold flow deciding how to make it hot:

1. Does a collector need a value *right now*, even before the first emission? → `stateIn` (it forces an initial value for exactly this).
2. Is re-delivering an identical value pointless (UI state)? → `stateIn`'s conflation and dedup are correct.
3. Is every emission distinct and meaningful, even duplicates (events)? → `shareIn` with `replay = 0`.
4. Do late subscribers need the last event? → `shareIn` with `replay = 1`.
5. Is this UI-scoped? → `WhileSubscribed(5_000)`. App-wide and always needed? → `Eagerly`.

The failure I see most is reaching for `stateIn` reflexively because it looks like the "modern" choice, then wondering why one-off events vanish. State and events are different shapes; the operator you pick should match the shape. Get the pairing right — state to `stateIn`, events to `shareIn`, `WhileSubscribed` for anything a screen touches — and you eliminate duplicate upstream work without introducing leaks or dropped events.

## Resources

- [StateFlow and SharedFlow — Kotlin coroutines guide](https://kotlinlang.org/docs/flow.html#stateflow-and-sharedflow)
- [shareIn / stateIn — kotlinx.coroutines API](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines.flow/share-in.html)
- [Things to know about Flow's shareIn and stateIn (Manuel Vivo)](https://medium.com/androiddevelopers/things-to-know-about-flows-sharein-and-statein-operators-20e6ccb2bc74)
- [StateFlow and SharedFlow on Android (developer.android.com)](https://developer.android.com/kotlin/flow/stateflow-and-sharedflow)
