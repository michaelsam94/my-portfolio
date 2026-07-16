---
title: "When to Actually Reach for derivedStateOf"
slug: "compose-derivedstateof-when-to-use"
description: "derivedStateOf in Compose: when it prevents wasted recomposition, when it's pointless overhead, and how it differs from remember(key) and plain computed values."
datePublished: "2024-08-31"
dateModified: "2024-08-31"
tags: ["Android", "Jetpack Compose", "Kotlin"]
keywords: "derivedStateOf, Compose derived state, recomposition optimization, remember key vs derivedStateOf, scroll state, snapshotFlow"
faq:
  - q: "What does derivedStateOf do in Jetpack Compose?"
    a: "derivedStateOf creates a State object whose value is computed from other State reads, and it only notifies readers when the computed result actually changes, not every time an input changes. It's useful when a frequently-changing state feeds a derived value that changes rarely, like a scroll offset that many pixels feed into a single boolean 'show the scroll-to-top button'. Downstream composables recompose only on the boolean flip, not on every scroll pixel."
  - q: "When should I NOT use derivedStateOf?"
    a: "Don't use it when the derivation changes as often as its inputs, because then it adds bookkeeping overhead with no recomposition savings. It's also the wrong tool when the transformation depends on a parameter rather than other State; that's a job for remember(key). Overusing derivedStateOf everywhere as a supposed optimization usually makes code harder to read without measurably improving performance."
  - q: "What's the difference between derivedStateOf and remember with keys?"
    a: "remember(key) recomputes when a key changes and is driven by recomposition, while derivedStateOf tracks State reads inside its calculation and recomputes lazily, emitting a new value only when the result differs. Use remember(key) to cache a computation against explicit inputs, and derivedStateOf when a high-frequency State should be distilled into a lower-frequency derived State to cut recomposition. They solve related but distinct problems."
---

`derivedStateOf` earns its place in exactly one situation: when a state that changes *frequently* feeds a value that changes *rarely*, and you want the readers of that value to recompose only when the result actually flips. The canonical example is a scroll: the scroll offset updates on every frame you drag, but "should I show the scroll-to-top button?" is a boolean that changes maybe twice in that whole gesture. If you compute that boolean inline, every composable reading it recomposes on every scroll pixel. `derivedStateOf` collapses the high-frequency input into a low-frequency output, so downstream recomposition happens only on the two transitions that matter.

That's the whole justification. The problem is people scatter `derivedStateOf` everywhere as a vague "optimization," where it adds overhead and confusion without saving a single recomposition. Let me draw the line precisely.

## The case it's built for

```kotlin
val listState = rememberLazyListState()

val showScrollToTop by remember {
    derivedStateOf { listState.firstVisibleItemIndex > 0 }
}

if (showScrollToTop) {
    ScrollToTopButton(onClick = { /* ... */ })
}
```

`firstVisibleItemIndex` changes constantly during a fling. But `showScrollToTop` is a boolean that changes only when you cross the boundary between item 0 and item 1. `derivedStateOf` re-runs its calculation whenever an input State changes, *but only publishes a new value — and only recomposes readers — when the boolean result differs from before.* So the `ScrollToTopButton` block recomposes twice per scroll session instead of sixty times a second. That's a real, measurable win.

Note the `remember` wrapper: `derivedStateOf` itself must be remembered, or you'd allocate a new derived state every recomposition and lose the caching. `remember { derivedStateOf { ... } }` is the correct incantation.

## The case where it's pointless

Now the mistake. If the derived value changes just as often as its input, `derivedStateOf` buys you nothing but bookkeeping:

```kotlin
// Pointless: fullName changes exactly when first or last changes.
val fullName by remember {
    derivedStateOf { "$firstName $lastName" }
}

// Just write it inline.
val fullName = "$firstName $lastName"
```

There's no frequency mismatch here — every input change produces an output change — so the derived state's "only emit when the result differs" machinery never saves a recomposition. It only adds a snapshot observation and an allocation. Inline computation is clearer and no slower. The tell: if you can't articulate "the input changes way more often than the output," you don't need `derivedStateOf`.

## derivedStateOf vs remember(key)

These get conflated constantly. They react to different things:

| | `remember(key)` | `derivedStateOf` |
|---|---|---|
| Recomputes when | a key value changes (recomposition-driven) | a State read inside it changes (snapshot-driven) |
| Emits new value when | key changed | computed result differs from last |
| Best for | caching against explicit inputs | distilling high-freq State into low-freq State |
| Depends on | parameters / arbitrary values | other `State`/`MutableState` |

The decisive question: *is my input a `State`, and does it change far more often than my output?* Yes to both → `derivedStateOf`. If the input is a plain parameter (like a `userId` passed in), that's `remember(userId)` territory — the [remember key](https://blog.michaelsam94.com/compose-remember-keys-pitfalls/) tool, not this one. `derivedStateOf` specifically tracks *snapshot State reads*; it does nothing for a parameter that isn't State-backed.

## A more realistic example: enabling a button

Beyond scroll, the pattern shows up in forms where many fields feed one derived flag:

```kotlin
val canSubmit by remember {
    derivedStateOf {
        email.isValid() && password.length >= 8 && acceptedTerms
    }
}
SubmitButton(enabled = canSubmit)
```

If the user is typing, `email` and `password` change on every keystroke — high frequency. But `canSubmit` is a boolean that flips only when validity crosses a threshold. So the `SubmitButton` recomposes only when its enabled-ness actually changes, not on every character typed. This is a genuine win *if* the button (or a subtree gated on `canSubmit`) is expensive to recompose. If it's a trivial button, honestly, inline is fine — measure before you optimize.

## Pairing it with snapshotFlow

`derivedStateOf` is for driving *recomposition*. When you want to react to a derived value with a *side effect* — log an analytics event when the user scrolls past a threshold, trigger pagination — reach for `snapshotFlow`, which turns State reads into a cold `Flow` you can collect in a `LaunchedEffect`:

```kotlin
LaunchedEffect(listState) {
    snapshotFlow { listState.layoutInfo.visibleItemsInfo.lastOrNull()?.index }
        .distinctUntilChanged()
        .collect { lastVisible -> maybeLoadMore(lastVisible) }
}
```

Same "distill high-frequency State" instinct, different output: `derivedStateOf` → State for recomposition, `snapshotFlow` → Flow for effects. Confusing the two (running a side effect inside `derivedStateOf`, which must be pure) is a real bug — the derivation can run at unexpected times and must have no side effects.

## The rule I apply

Before adding `derivedStateOf`, I ask one question and demand a yes: *does a frequently-changing `State` feed a value that changes rarely, and does something expensive read that value?* If yes, it's the right tool and it genuinely cuts recomposition. If the output changes as often as the input, or the input isn't State, or the reader is cheap — skip it and write the plain expression. It's an optimization for a specific frequency-mismatch shape, not a default wrapper for every computed value. Used precisely it's excellent; used reflexively it's clutter.

## Common production mistakes

Teams get derivedstateof when to use wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Compose UI work on derivedstateof when to use janks when recomposition scope is too wide, `remember` keys omit stable inputs, and semantics for TalkBack are added only after QA finds focus traps.

## Resources

- [derivedStateOf documentation](https://developer.android.com/develop/ui/compose/side-effects#derivedstateof)
- [derivedStateOf API reference](https://developer.android.com/reference/kotlin/androidx/compose/runtime/package-summary#derivedStateOf(kotlin.Function0))
- [snapshotFlow](https://developer.android.com/develop/ui/compose/side-effects#snapshotFlow)
- [Compose performance best practices](https://developer.android.com/develop/ui/compose/performance/bestpractices)
- [State in Compose](https://developer.android.com/develop/ui/compose/state)
