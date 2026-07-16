---
title: "Jetpack Compose: Lessons From 10 Years in Android"
slug: "jetpack-compose-lessons-10-years-android"
description: "Hard-won Jetpack Compose lessons from migrating production Android apps off XML: recomposition, state hoisting, stability, and Clean Architecture boundaries."
datePublished: "2026-06-08"
dateModified: "2026-06-08"
tags: ["Android", "Jetpack Compose", "Kotlin", "Clean Architecture"]
keywords: "Jetpack Compose, Compose recomposition, state hoisting, Compose performance, Android Clean Architecture, Kotlin UI"
faq:
  - q: "What are the most common Jetpack Compose performance mistakes?"
    a: "Unstable parameters, reading state too high in the tree, and unkeyed lists cause unnecessary recomposition. Stable models and state hoisting keep recomposition scoped and cheap."
  - q: "Is it worth migrating an XML Android app to Jetpack Compose?"
    a: "For actively developed apps, yes. Compose reduces UI boilerplate and speeds iteration, but migrate screen by screen behind Clean Architecture boundaries rather than all at once."
  - q: "How does Clean Architecture help a Compose migration?"
    a: "Separating UI, domain, and data layers means you can swap the XML view layer for Compose without touching business logic, which keeps the migration incremental and safe."
---

I shipped my first Android app on XML layouts and `findViewById`. A decade later I lead Compose migrations on production apps with hundreds of thousands of users. The framework is a genuine leap — but it punishes habits carried over from the View system. These are the lessons that mattered most when moving real apps, not toy demos, to Jetpack Compose.

## Recomposition is the whole game

The View system taught us to think in terms of "find the view, mutate it." Compose inverts that: you describe UI as a function of state, and the runtime *recomposes* — re-invokes — composables whose inputs changed. Everything good or bad about Compose performance flows from how well you control that.

The trap is invisible work. A composable that reads a frequently-changing value rebuilds on every change, and if it sits high in the tree it drags its children with it. The fix is almost always **reading state as low as possible**:

```kotlin
// Bad: the whole screen recomposes every frame the scroll offset changes.
@Composable
fun Screen(scroll: ScrollState) {
    Header(alpha = 1f - scroll.value / 600f)
    Content()
}

// Good: defer the read so only Header recomposes.
@Composable
fun Screen(scroll: ScrollState) {
    Header(alpha = { 1f - scroll.value / 600f })
    Content()
}
```

Passing a lambda instead of a value defers the `scroll.value` read into `Header`, so `Content` never recomposes on scroll. Deferred reads — lambdas, `derivedStateOf`, `Modifier.layout` with a lambda — are the single most important Compose performance technique, and the least obvious coming from XML.

## State hoisting is an architecture decision, not a style

"Hoist your state" gets repeated until it sounds like a lint rule. It is actually a boundary decision. A composable should be **stateless and told what to show**, with state living at the lowest common ancestor that needs it. The payoff is concrete: stateless composables are trivially previewable, testable, and reusable.

```kotlin
@Composable
fun SearchBar(
    query: String,
    onQueryChange: (String) -> Unit,
) { /* no remember here — pure function of inputs */ }
```

The discipline that made this stick on large screens was pairing it with a single state holder per screen — a `ViewModel` exposing one immutable `UiState` via `StateFlow`. The composable collects it with `collectAsStateWithLifecycle()` and renders. One source of truth, one direction of data flow. This is also where Compose meets Clean Architecture cleanly: the ViewModel depends on use cases, the composable depends only on `UiState`, and the UI layer knows nothing about repositories or the network.

## Stability: the silent recomposition tax

Compose skips recomposing a composable when it can prove its parameters are unchanged — but only for **stable** types. Pass an unstable type (a plain `List`, a class from a module Compose can't see into) and Compose conservatively assumes it changed every time, silently defeating skipping.

Two fixes carried most of the weight on real migrations:

- Use **immutable collections** (`kotlinx.collections.immutable`'s `ImmutableList`) or mark data classes that the compiler can't infer as stable with `@Immutable` / `@Stable`.
- Enable the **Compose compiler metrics** to find the offenders instead of guessing. Pointing the compiler reports at our hottest screen revealed a `data class` holding a `List` that was making an entire feed recompose on every emission. Wrapping it as `ImmutableList` cut recompositions dramatically.

If your Compose screen feels mysteriously janky, generate the stability report before you optimize anything. Measure, don't guess.

## `remember` the right thing, for the right lifetime

`remember` caches across recompositions; `rememberSaveable` survives configuration change and process death. Getting these wrong produces two classic bugs: expensive objects rebuilt every recomposition, or form input that vanishes on rotation. The rule I teach:

- Derive, don't store, when you can: `derivedStateOf` for values computed from other state.
- `remember(key)` so the cache invalidates when its inputs change — a stale `remember` is worse than none.
- `rememberSaveable` for anything the user would be angry to lose on rotation.

## Interop is a feature, not a failure

The most pragmatic lesson: you don't have to migrate everything at once. `AndroidView` hosts a legacy custom View inside Compose, and `ComposeView` drops Compose into an XML screen. On a large app, I migrated screen-by-screen behind feature flags over several releases rather than attempting a big-bang rewrite. Shipping continuously beat purity every time, and crash-free rates stayed at 99.9% through the transition because nothing changed wholesale.

## What actually improved

Across these migrations the wins were measurable: less UI code, dramatically fewer "view out of sync with state" bugs (the entire class of `findViewById` nullability and inconsistent-state defects disappears), faster feature delivery once the team internalized unidirectional data flow, and ANR rates held below 0.1% because heavy work stayed off the composition.

## The short version

- Optimize recomposition first; defer state reads with lambdas and `derivedStateOf`.
- Hoist state to one holder per screen; render from a single immutable `UiState`.
- Watch stability — use immutable collections and read the compiler metrics.
- Match `remember` lifetime to intent; prefer derived state over stored state.
- Migrate incrementally with `AndroidView` / `ComposeView`; ship the whole way.

Compose rewards you for thinking in state and data flow. Ten years in, the biggest shift isn't the API — it's that the UI layer finally became something you can reason about.

## Resources

- [Jetpack Compose documentation](https://developer.android.com/jetpack/compose)
- [Compose performance best practices](https://developer.android.com/develop/ui/compose/performance)
- [Compose compiler stability configuration](https://developer.android.com/develop/ui/compose/performance/stability)
- [Migrating to Compose](https://developer.android.com/develop/ui/compose/migrate)
- [Compose side-effects](https://developer.android.com/develop/ui/compose/side-effects)

*Migrating an Android codebase to Compose and want experienced help? [Let's talk](/#contact).*
