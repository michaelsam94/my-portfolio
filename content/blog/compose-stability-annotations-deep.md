---
title: "Compose Stability: What @Stable and @Immutable Actually Do"
slug: "compose-stability-annotations-deep"
description: "Compose stability explained: how the compiler infers stable vs unstable types, what @Stable and @Immutable promise, and how instability causes needless recomposition."
datePublished: "2024-08-26"
dateModified: "2024-08-26"
tags: ["Android", "Jetpack Compose", "Kotlin"]
keywords: "Compose stability, @Stable, @Immutable, recomposition skipping, stable types, strong skipping mode, compose compiler"
faq:
  - q: "What does @Immutable mean in Jetpack Compose?"
    a: "@Immutable is a promise to the Compose compiler that a type's public properties will never change after construction, so once created its value is fixed forever. Given that promise, Compose can skip recomposing a composable whose @Immutable parameters are equal to the previous ones. It's stronger than @Stable: @Immutable says the object never changes at all, whereas @Stable allows changes as long as Compose is notified through snapshot state."
  - q: "What is the difference between @Stable and @Immutable?"
    a: "@Immutable guarantees the object's properties never change after construction. @Stable is a weaker promise: the object may change, but any change to a property that a composable reads will be signaled to Compose (typically because those properties are backed by snapshot State). Both let the compiler treat the type as stable for skipping, but @Immutable implies stronger constraints, so use @Immutable for truly fixed data and @Stable for observable-but-mutable holders."
  - q: "Why is my composable recomposing when its inputs look unchanged?"
    a: "Usually because at least one parameter is an unstable type, so Compose can't prove the inputs are equal and conservatively recomposes. Common culprits are List/Map interfaces (Compose treats them as potentially mutable), lambdas that capture unstable values, and classes from modules without the Compose compiler. Check the compiler's stability report, switch to immutable collections or stable data classes, and the skipping returns."
---

Compose stability is the property that decides whether a composable can be *skipped* — left untouched during recomposition because Compose can prove its inputs haven't meaningfully changed. When a type is stable, Compose knows two things: that `equals` is meaningful, and that if any public property changes, Compose will be notified. Given those guarantees it can compare a composable's new parameters to the old ones and, if they're equal, skip re-executing it entirely. When a type is *unstable*, Compose can't make that comparison safely, so it conservatively recomposes every time — and that's the source of most "why is this recomposing?" performance mysteries.

`@Stable` and `@Immutable` are how you make promises to the compiler that it can't infer on its own. Misunderstanding them is why people either sprinkle them uselessly or miss the ones that matter. Let me pin down exactly what they mean.

## What "stable" means to the compiler

A type is stable if it satisfies a contract:

- `equals()` is consistent — two instances that are equal now stay equal.
- Whenever a public property changes, composition is notified (this is what snapshot `State` does automatically).
- All public property types are themselves stable.

The Compose compiler *infers* stability for many types automatically. Primitives, `String`, function types, and `data class`es whose properties are all stable-and-`val` come out stable without any annotation. Things go unstable when the compiler can't be sure: a `var` of an unstable type, a property typed as an interface it can't see through, or a class from a module the Compose compiler didn't process.

## The collection trap everyone hits

The single most common instability: `List`, `Map`, `Set`. These are *interfaces*, and Compose can't prove the concrete implementation behind a `List<T>` isn't a `MutableList` someone mutates behind its back. So a parameter typed `List<Item>` is treated as unstable, and the composable never skips — even if you always pass an immutable list.

Two fixes:

```kotlin
// 1) kotlinx.collections.immutable — the compiler knows these are stable
data class UiState(val items: ImmutableList<Item>)

// 2) wrap it and annotate the promise
@Immutable
data class ItemList(val items: List<Item>)
```

I default to `kotlinx.collections.immutable` (`ImmutableList`, `persistentListOf`) because it makes the intent enforceable at the type level rather than relying on a bare annotation promise. Either way, the moment the parameter is a stable collection type, skipping starts working.

## @Immutable: "this never changes"

`@Immutable` is the stronger promise. It tells the compiler that every public property is fixed at construction and will *never* change for the life of the object. A settled config, a piece of loaded content, a value object:

```kotlin
@Immutable
data class Article(
    val id: String,
    val title: String,
    val paragraphs: List<String>,   // fine: we promise it never mutates
)
```

Because the object can never change, Compose can compare by reference or value and skip aggressively. The catch is that it's a *promise the compiler trusts but doesn't verify* — if you lie (that `List` actually gets mutated somewhere), you get stale UI that silently doesn't update, which is a nastier bug than an extra recomposition. Only apply `@Immutable` to types you truly never mutate after construction.

## @Stable: "changes, but I'll tell you"

`@Stable` is the weaker, more common promise: the object *may* change, but any change to a property a composable reads will flow through snapshot state so Compose gets notified. A holder built on `mutableStateOf` is the canonical case:

```kotlin
@Stable
class FormState {
    var email by mutableStateOf("")     // change is observable
    var isValid by mutableStateOf(false)
}
```

Here `email` changes over the object's life, but because it's backed by `State`, Compose observes reads and recomposes exactly the composables that read it. `@Stable` says "trust that all my mutation is observable," which lets the compiler treat the type as stable for skipping while still allowing it to mutate. Use `@Stable` for observable mutable holders; use `@Immutable` for genuinely fixed data.

## Read the stability report before guessing

Don't annotate by vibes. The Compose compiler can emit a stability report telling you exactly which classes it inferred as stable, unstable, or "runtime" (depends on generics), and which composables are skippable. Turn it on via compiler options and read the generated `*-classes.txt` and `*-composables.txt`. You'll see lines like `unstable class UiState` with each offending property flagged. That report converts "I think this recomposes too much" into "this exact field is unstable" — infinitely faster than eyeballing.

This is the diagnostic backbone of the broader [recomposition performance work](https://blog.michaelsam94.com/compose-performance-stability-recomposition/): profile, read the report, fix the unstable type, confirm skipping returned.

## Strong skipping mode changes the calculus

Recent Compose compiler versions ship **strong skipping mode**, and it shifts what you need to annotate. With it enabled, composables with unstable parameters can still be skipped (Compose compares them by instance equality), and lambdas are automatically remembered. In practice this means a lot of the manual `@Stable`/`@Immutable` and `ImmutableList` gymnastics that used to be mandatory are now optional — the compiler handles more cases for you.

But it's not a license to ignore stability. Strong skipping uses *instance* equality for unstable types, so if you allocate a fresh unstable object every recomposition (a common accident), it still won't match and still won't skip. Stable types with real `equals` still skip more reliably. So the annotations matter less than they did, but writing stable data types remains the cleaner path.

## What I actually do

For state I expose to the UI: prefer `data class`es of stable properties, use `kotlinx.collections.immutable` for collections, annotate genuinely-fixed types `@Immutable` and observable holders `@Stable`, and turn on strong skipping mode. Then I verify with the stability report and the layout inspector's recomposition counts rather than trusting that the annotations did what I hoped. The goal isn't to annotate everything — it's to make the types honest so the compiler can skip freely, and to prove it did.

## Resources

- [Compose stability documentation](https://developer.android.com/develop/ui/compose/performance/stability)
- [Fix stability issues](https://developer.android.com/develop/ui/compose/performance/stability/fix)
- [Strong skipping mode](https://developer.android.com/develop/ui/compose/performance/stability/strongskipping)
- [kotlinx.collections.immutable](https://github.com/Kotlin/kotlinx.collections.immutable)
- [@Stable and @Immutable API reference](https://developer.android.com/reference/kotlin/androidx/compose/runtime/Stable)
