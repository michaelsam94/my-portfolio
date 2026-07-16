---
title: "Compose Performance: Stability, Recomposition, and Metrics"
slug: "compose-performance-stability-recomposition"
description: "Fix Jetpack Compose performance for real: understand stability and skippable functions, read compiler metrics, tame recomposition, and use derivedStateOf correctly."
datePublished: "2026-04-18"
dateModified: "2026-04-18"
tags: ["Android", "Jetpack Compose", "Performance", "Kotlin"]
keywords: "Compose performance, recomposition, stability, Compose compiler metrics, skippable functions, derivedStateOf, Compose optimization"
faq:
  - q: "What makes a Composable skippable?"
    a: "A composable is skippable when all its parameters are stable — the Compose compiler can prove they haven't changed, so it skips re-executing the function. Unstable parameters (like a plain List or a class the compiler can't inspect) make it non-skippable, so it recomposes every time its parent does."
  - q: "How do I read Compose compiler metrics?"
    a: "Enable the compiler metrics and reports flags in your Gradle build, then build the app. The compiler emits CSV and text files listing which composables are skippable and restartable and which classes are stable or unstable — that's your ground truth for what to fix, instead of guessing."
  - q: "When should I use derivedStateOf?"
    a: "Use derivedStateOf when you compute a value from other state but only care when the derived result changes, not every time the inputs do — the classic case is deriving a boolean like 'is scrolled past the top' from a continuously-changing scroll offset, so downstream code only recomposes when the boolean flips."
---

Compose performance problems almost always come down to one question: is this composable doing work it didn't need to do? The runtime re-invokes — recomposes — composables whose inputs changed. When that scoping breaks down, you get a screen that recomposes far more than it should, and it feels janky even though no single frame is obviously wrong. The fix isn't guesswork; Compose ships tooling that tells you exactly which composables are skippable and which types are stable. This is how I use stability, the compiler metrics, and `derivedStateOf` to make real Compose screens fast.

I've written before about the broad lessons from a decade of [Jetpack Compose migrations](https://blog.michaelsam94.com/jetpack-compose-lessons-10-years-android/); this goes a level deeper into the performance mechanics specifically, because that's where teams lose the most time optimizing the wrong thing.

## Skippable and restartable: the two words that matter

The compiler classifies your composables. Two properties decide whether recomposition stays cheap:

- **Restartable** — Compose can re-invoke this composable on its own without re-running its parent. Most `@Composable` functions are.
- **Skippable** — Compose can *skip* re-invoking it when its parameters are unchanged. This only happens when **every parameter is stable**.

A non-skippable composable recomposes every time its parent does, dragging its subtree along. So the performance goal is simple to state: keep the composables in your hot paths skippable. And a composable is skippable only if its parameters are stable — which is why stability is the whole ballgame.

## What "stable" actually means

Compose considers a type stable if it can guarantee that when the type reports "I'm equal," the composable can trust it and skip. Stable types include primitives, `String`, function types, and `data class`es whose properties are all stable. The traps:

- A plain `List<T>` is **unstable** — the compiler can't prove the underlying list won't mutate, so it assumes it changed every time.
- A class from a module the Compose compiler doesn't process (a domain model in a pure-Kotlin module) is treated as unstable.
- A `var` in a data class makes it unstable unless it's a Compose `State`.

```kotlin
// Unstable: List makes the whole param unstable → not skippable.
data class FeedUiState(val items: List<Charger>)

// Stable: immutable collection the compiler trusts.
data class FeedUiState(val items: ImmutableList<Charger>)
```

The single highest-leverage fix on real screens is swapping `List` for `kotlinx.collections.immutable`'s `ImmutableList`/`PersistentList`. On one feed screen I traced constant recomposition to exactly this — a `data class` holding a `List` made the whole feed recompose on every unrelated state emission. Wrapping it as `ImmutableList` made it skippable and the recompositions dropped off a cliff.

## Read the metrics — stop guessing

You don't have to intuit any of this. The Compose compiler emits reports telling you what's skippable and what's stable. Turn them on in Gradle:

```kotlin
// build.gradle.kts (module)
composeCompiler {
    reportsDestination = layout.buildDirectory.dir("compose_reports")
    metricsDestination = layout.buildDirectory.dir("compose_metrics")
}
```

Build the app, then look in the output. You get, among others:

- `*-composables.txt` — each composable marked `restartable skippable` or, damningly, not skippable.
- `*-classes.txt` — each class marked `stable`/`unstable` with the offending field called out.

```
restartable scheme("[androidx.compose...]") fun FeedItem(
  stable charger: Charger
)   // good — skippable

restartable fun Feed(
  unstable state: FeedUiState   // bad — recomposes with parent every time
)
```

That `unstable state` line is a to-do item, not a mystery. Fix the class it points to, rebuild, confirm it flipped to stable. This measure-fix-remeasure loop is the entire discipline — it's the same instinct behind the [ANR and jank diagnostic work](https://blog.michaelsam94.com/killing-anrs-android-jank/): find the real offender before touching anything.

## Diagnose live recomposition counts

Metrics tell you what *could* recompose; you also want to see what *does*. Android Studio's Layout Inspector shows live recomposition counts per composable while you interact — a counter ticking up on a composable that shouldn't be changing is your smoking gun. For automated tracking, a Macrobenchmark scrolling test with frame metrics catches regressions in CI before they ship.

## derivedStateOf: the scroll-offset classic

A frequent self-inflicted wound is reading a rapidly-changing value directly, causing recomposition every frame. The canonical example is a "scroll to top" button that should appear once you've scrolled past the first item:

```kotlin
val showButton by remember {
    derivedStateOf { listState.firstVisibleItemIndex > 0 }
}
```

Without `derivedStateOf`, reading `firstVisibleItemIndex` recomposes on every scroll pixel. With it, `showButton` only produces a new value when the boolean actually flips, so the button's visibility recomposes twice per scroll session instead of hundreds of times. Use it whenever you derive a coarse value from a fine-grained one.

## Defer reads with lambdas

Related technique: pass a lambda instead of a value so the state read happens deep in the tree rather than high up. `Modifier.offset { }`, `Modifier.drawBehind { }`, and graphics-layer lambdas all read state at draw/layout time, skipping composition entirely for animations. A parallax header driven by a lambda-based offset animates smoothly while the content around it never recomposes.

## The workflow that actually fixes things

| Step | Tool |
| --- | --- |
| 1. Suspect a screen | It feels janky on scroll/interaction |
| 2. Confirm what recomposes | Layout Inspector recomposition counts |
| 3. Find the cause | Compose compiler metrics/reports |
| 4. Fix stability | ImmutableList, `@Immutable`, stable models |
| 5. Defer hot reads | Lambdas, `derivedStateOf` |
| 6. Verify | Rebuild metrics + Macrobenchmark in CI |

The mistake I see most is skipping to step 4 or 5 on a hunch and "optimizing" a composable that was never the problem. Compose gives you ground truth — use it. Once a team internalizes this loop, Compose performance stops being folklore and becomes a routine, measurable part of shipping. The framework rewards you for describing UI as a clean function of stable state; the metrics just make it obvious when you've strayed from that.

## Resources

- [Compose performance guidance](https://developer.android.com/develop/ui/compose/performance)
- [Stability in Compose](https://developer.android.com/develop/ui/compose/performance/stability)
- [Compose compiler metrics](https://developer.android.com/develop/ui/compose/performance/stability/diagnose)
- [derivedStateOf and state](https://developer.android.com/develop/ui/compose/side-effects)
- [kotlinx.collections.immutable](https://github.com/Kotlin/kotlinx.collections.immutable)
- [Jetpack Compose](https://developer.android.com/jetpack/compose)

*Chasing recomposition gremlins in a Compose codebase? [Get in touch](https://michaelsam94.com/).*
