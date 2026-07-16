---
title: "Compose Side Effects Without the Foot-Guns"
slug: "compose-side-effects-launchedeffect"
description: "Compose side effects done right: when to use LaunchedEffect, rememberCoroutineScope, DisposableEffect, SideEffect, and rememberUpdatedState to avoid stale captures and leaks."
datePublished: "2024-08-28"
dateModified: "2024-08-28"
tags: ["Android", "Jetpack Compose", "Kotlin"]
keywords: "LaunchedEffect, Compose side effects, DisposableEffect, rememberCoroutineScope, rememberUpdatedState, SideEffect key"
faq:
  - q: "When should I use LaunchedEffect versus rememberCoroutineScope?"
    a: "Use LaunchedEffect when a coroutine should start as a consequence of composition and be tied to a key, like loading data when an id appears or animating on first display. Use rememberCoroutineScope when you need to launch a coroutine in response to a user event such as a button click, from a non-composable callback. The rule of thumb: LaunchedEffect for composition-driven effects, rememberCoroutineScope for event-driven ones."
  - q: "What does the key parameter of LaunchedEffect do?"
    a: "The key controls the effect's lifecycle: when a key changes, Compose cancels the running coroutine and starts a fresh one, and when the effect leaves composition the coroutine is cancelled. Passing Unit or true means run once and never restart; passing a value like userId means restart whenever that value changes. Choosing the wrong key is the top cause of effects that either never refresh or restart far too often."
  - q: "How do I avoid a stale value captured inside LaunchedEffect?"
    a: "Wrap the changing value in rememberUpdatedState so the effect reads the latest value without restarting. A LaunchedEffect captures its lambdas and variables at launch, so a long-running effect keyed on something stable will keep calling an old callback. rememberUpdatedState keeps a reference that's updated on each recomposition, letting the effect see current values while its key stays fixed."
---

Every side-effect bug I've debugged in Compose comes down to one of three mistakes: running an effect with the wrong key so it either never refreshes or thrashes, capturing a stale value in a long-lived effect, or launching a coroutine from the wrong place so it leaks or fires on every recomposition. Compose's side-effect APIs exist precisely to make effects behave predictably against the recomposition lifecycle — but only if you match the API to the situation. Get the mental model right and this stops being scary.

The core idea: composable functions must be *pure* and can re-run any number of times, so anything that touches the outside world — starting a network call, subscribing to a callback, showing a snackbar — has to be wrapped in an effect handler that Compose controls. Here's each one and when it's the right tool.

## LaunchedEffect: coroutines driven by composition

`LaunchedEffect` runs a suspend block when it enters composition and cancels it when it leaves. Its key(s) decide its lifecycle: change a key and Compose cancels the old coroutine and launches a new one.

```kotlin
LaunchedEffect(userId) {
    // Cancelled + restarted whenever userId changes.
    val profile = repo.loadProfile(userId)
    state = profile
}
```

The **key is the whole game**. `LaunchedEffect(userId)` reloads when the user changes — correct for data loading. `LaunchedEffect(Unit)` runs once for the composable's lifetime and never restarts — correct for a one-time animation or an initial event. The two classic bugs: keying on `Unit` when you needed it to react to a changing input (data never refreshes), or keying on something that changes every recomposition (effect restarts constantly, re-firing your network call). If you find yourself passing a freshly-allocated object as a key, that's the bug.

## rememberUpdatedState: current values inside a stable effect

Sometimes you want an effect that runs *once* but always calls the *latest* callback. The naive version captures the callback at launch and calls a stale one forever:

```kotlin
@Composable
fun AutoDismiss(onTimeout: () -> Unit) {
    val currentOnTimeout by rememberUpdatedState(onTimeout)
    LaunchedEffect(Unit) {           // deliberately runs once
        delay(5000)
        currentOnTimeout()           // calls the latest, not the captured one
    }
}
```

Without `rememberUpdatedState`, if the parent recomposes and passes a new `onTimeout` lambda, this effect would still call the one from five seconds ago. If instead you keyed the effect on `onTimeout`, the timer would reset every recomposition — also wrong. `rememberUpdatedState` threads the needle: stable key, fresh value. It's the fix for a whole category of "why is it calling the old callback" bugs.

## rememberCoroutineScope: coroutines driven by events

`LaunchedEffect` is for composition-driven work. When a coroutine should start because the *user did something* — tapped a button, pulled to refresh — you need a scope you can launch into from a regular callback:

```kotlin
val scope = rememberCoroutineScope()
Button(onClick = {
    scope.launch { snackbarHostState.showSnackbar("Saved") }
}) { Text("Save") }
```

You cannot call `LaunchedEffect` from inside an `onClick` — it's a composable, not a function you invoke imperatively. `rememberCoroutineScope` gives you a scope bound to the composition's lifecycle, so coroutines launched from events are cancelled when the composable leaves. Reaching for `LaunchedEffect` where you meant `rememberCoroutineScope` (or vice versa) is the composition-vs-event confusion at the root of many effect bugs.

## DisposableEffect: things that must be cleaned up

When an effect acquires a resource that needs releasing — a listener, a broadcast receiver, a sensor subscription — `DisposableEffect` gives you an `onDispose` block that runs when the effect leaves composition or its key changes:

```kotlin
DisposableEffect(lifecycleOwner) {
    val observer = LifecycleEventObserver { _, event -> handle(event) }
    lifecycleOwner.lifecycle.addObserver(observer)
    onDispose {
        lifecycleOwner.lifecycle.removeObserver(observer)
    }
}
```

The `onDispose` is mandatory and it's where leaks are prevented. Any time you register a callback with something that outlives the composable, this is the tool. Forgetting `DisposableEffect` and registering in a `LaunchedEffect` instead means your listener leaks because there's no symmetric cleanup path.

## SideEffect: publish state to non-Compose code

`SideEffect` runs after *every successful recomposition* and is for pushing Compose state out to an object that isn't Compose-aware — analytics, a third-party controller that needs the current value:

```kotlin
SideEffect {
    analytics.setCurrentScreen(screenName)
}
```

It has no key and no coroutine; it just fires on each committed composition. Use it sparingly and only for cheap, idempotent publishing. It's the wrong tool for anything asynchronous — that's `LaunchedEffect`.

## A quick decision guide

| You want to… | Use |
|---|---|
| Start suspend work when a value appears/changes | `LaunchedEffect(key)` |
| Run once but always call the latest lambda | `LaunchedEffect(Unit)` + `rememberUpdatedState` |
| Launch a coroutine from a click/event | `rememberCoroutineScope` |
| Register something that needs cleanup | `DisposableEffect` |
| Push Compose state to non-Compose code each frame | `SideEffect` |
| Convert a callback/flow into Compose state | `produceState` / `collectAsStateWithLifecycle` |

That last row matters: for consuming a `Flow`, prefer `collectAsStateWithLifecycle` over hand-rolling a `LaunchedEffect` that collects, because it respects the lifecycle and stops collection in the background — the same concern as the broader [Compose recomposition and lifecycle hygiene](https://blog.michaelsam94.com/jetpack-compose-lessons-10-years-android/).

## The rules I hold to

Keep composables pure; every world-touching action goes through an effect handler. Pick the key so the effect's lifecycle matches its meaning — restart when the *thing it depends on* changes, and no more often. Reach for `rememberUpdatedState` the moment a long-lived effect needs a value that changes. Use `DisposableEffect` for anything with a cleanup, and never register listeners in a plain `LaunchedEffect`. Follow those and the foot-guns — stale captures, thrashing effects, leaked listeners — mostly disappear.

## Resources

- [Side effects in Compose](https://developer.android.com/develop/ui/compose/side-effects)
- [Lifecycle of composables](https://developer.android.com/develop/ui/compose/lifecycle)
- [collectAsStateWithLifecycle](https://developer.android.com/reference/kotlin/androidx/lifecycle/compose/package-summary)
- [Kotlin coroutines structured concurrency](https://kotlinlang.org/docs/coroutines-basics.html)
- [Thinking in Compose](https://developer.android.com/develop/ui/compose/mental-model)
