---
title: "Modeling Domains with Kotlin Sealed Interfaces"
slug: "kotlin-sealed-interfaces-domain-modeling"
description: "Sealed interfaces let you model closed domain hierarchies with exhaustive when, flexible multiple inheritance, and no impossible states. Patterns from real code."
datePublished: "2024-06-02"
dateModified: "2024-06-02"
tags: ["Kotlin", "Architecture", "Domain Modeling"]
keywords: "Kotlin sealed interface, sealed class, domain modeling, exhaustive when, algebraic data types, make illegal states unrepresentable"
faq:
  - q: "What is the difference between a sealed class and a sealed interface in Kotlin?"
    a: "A sealed class can hold state and constructor logic but forces single inheritance, so a subtype can extend only one sealed hierarchy. A sealed interface has no constructor and no state, but a type can implement several sealed interfaces at once, letting you model orthogonal categories. In modern Kotlin, prefer sealed interfaces for the top of a hierarchy unless you genuinely need shared stored state."
  - q: "Why do sealed types make when expressions exhaustive?"
    a: "Because the compiler knows the complete set of permitted subtypes at compile time, it can verify that a when covers every case. If you add a new subtype and forget to handle it, the when stops compiling. This turns a whole class of runtime forgot-a-case bugs into compile errors."
  - q: "When should I use a sealed interface over an enum?"
    a: "Use an enum when each case is a simple constant with no per-case data. Use a sealed interface when cases carry different payloads — a Loading state with a progress value, an Error with an exception, a Success with data. Sealed hierarchies are enums that can hold heterogeneous data per case."
---

Sealed interfaces are the tool I reach for first when a value can be exactly one of a known set of shapes, each carrying its own data — a UI state that's either loading, loaded, or failed; a payment result that's either authorized, declined, or requires a challenge. The payoff is that the compiler knows the full set of possibilities, so a `when` over them is *exhaustive*: forget a case and the code stops compiling instead of quietly falling through in production. That single property has caught more real bugs for me than any linter.

The deeper reason I default to sealed interfaces over the older sealed *class* is flexibility. A class forces single inheritance, so a type can belong to only one hierarchy. An interface lets a type participate in several closed hierarchies at once, which turns out to matter more often than you'd expect once you start modeling real domains.

## The core move: make illegal states unrepresentable

Most state bugs come from representations that can express nonsense. The classic offender is the "boolean soup" screen state:

```kotlin
// Every combination is possible, most are nonsense.
data class ScreenState(
    val isLoading: Boolean,
    val data: List<Item>?,
    val error: String?,
)
```

What does `isLoading = true, data = [...], error = "boom"` mean? Nothing coherent — yet the type permits it, so every consumer has to defensively handle the impossible. Compare the sealed version:

```kotlin
sealed interface ScreenState {
    data object Loading : ScreenState
    data class Loaded(val items: List<Item>) : ScreenState
    data class Failed(val message: String) : ScreenState
}
```

Now the only representable states are the three that mean something. `Loaded` *has* items and *has no* error, by construction. There's no "loading with an error" to guard against because you can't build one. This is the whole philosophy in one move: shrink the type until it can only express valid states, and the invalid handling code simply disappears.

## Exhaustiveness is the safety net

Consuming a sealed hierarchy with `when` gives you a compiler-enforced guarantee:

```kotlin
fun render(state: ScreenState) = when (state) {
    ScreenState.Loading    -> showSpinner()
    is ScreenState.Loaded  -> showItems(state.items)
    is ScreenState.Failed  -> showError(state.message)
}
```

No `else` branch. If someone later adds a `ScreenState.Empty`, this `when` fails to compile until it's handled — and so does every other `when` across the codebase. That's the feature: adding a case surfaces every site that needs updating, instead of you hunting for them. I treat a missing `else` on a sealed `when` as a feature, not a smell; adding a catch-all `else` throws away the exhaustiveness check, so I only do it when I genuinely want to ignore future cases.

Note the smart-casting: inside `is ScreenState.Loaded ->`, `state.items` is accessible because the compiler narrowed the type. That interplay with [Kotlin contracts and smart casts](https://blog.michaelsam94.com/kotlin-contracts-smart-casts/) is what makes consuming these hierarchies feel effortless.

## Why interfaces beat classes for the top of a hierarchy

Here's the case that sold me. Imagine domain events that are orthogonally *auditable* and *retryable* — some are both, some neither:

```kotlin
sealed interface DomainEvent
sealed interface Auditable { val actor: UserId }
sealed interface Retryable { val attempts: Int }

data class PaymentCaptured(
    val orderId: OrderId,
    override val actor: UserId,
) : DomainEvent, Auditable

data class WebhookDelivery(
    val url: String,
    override val attempts: Int,
) : DomainEvent, Retryable

data class RefundIssued(
    override val actor: UserId,
    override val attempts: Int,
) : DomainEvent, Auditable, Retryable
```

`RefundIssued` is a `DomainEvent`, `Auditable`, *and* `Retryable`. With sealed *classes* you couldn't do this — a class extends one parent. Sealed interfaces let a type declare membership in several closed sets, and each set stays exhaustively checkable on its own. You can write a `when` over `Auditable` and the compiler still enforces completeness for that axis. This composition is impossible with the class-only model, and it maps cleanly onto how real domains actually decompose.

## Practical patterns that hold up

A few conventions I've standardized on:

1. **Top the hierarchy with an interface, use `data object` for stateless cases.** `Loading` carries no data, so it's a singleton `data object`, not a `class` with a phantom constructor. `data object` also gives you a sensible `toString`.
2. **Keep the hierarchy in one file or module.** Sealed types permit subtypes only in the same module (and, for non-nested, the same package). Co-locating them makes the closed set obvious to readers.
3. **Model results, not just UI state.** A network call returning `sealed interface ApiResult<out T> { data class Ok<T>(val value: T); data class HttpError(val code: Int); data object Offline }` forces callers to handle the offline and error paths — it pairs naturally with [error handling using Kotlin's Result type](https://blog.michaelsam94.com/kotlin-result-type-error-handling/).
4. **Don't over-nest.** A three-level sealed tree reads worse than a flat one plus a discriminating property. Flatten until the `when` is comfortable.

## Sealed vs enum vs the alternatives

| You have | Use |
|---|---|
| A fixed set of constants, no per-case data | `enum class` |
| A fixed set of cases, each with different data | `sealed interface` |
| A fixed set of cases sharing stored state + logic | `sealed class` |
| Cases spanning multiple orthogonal categories | multiple `sealed interface`s |
| An open, extensible set (plugins) | a plain `interface` (no exhaustiveness) |

The honest boundary: sealed types give you exhaustiveness only because the set is *closed*. The instant you want third parties to add cases — a plugin system, an extensible event bus — you lose that and should use an open interface, accepting that consumers need an `else`. Don't try to have both; the closedness is the entire value.

## What it buys you over time

The real return on sealed interfaces shows up months later, during change. When a product decision adds a new payment outcome or a new screen state, you add the subtype and let the compiler march you through every `when` that now needs it. No grepping, no "did I get them all," no runtime `IllegalStateException` from an unhandled case slipping through review. The domain model becomes a checklist the compiler maintains for you.

That's the mental shift: stop treating the type system as bureaucracy to satisfy and start treating it as a place to encode what's actually true about your domain. Sealed interfaces are the sharpest tool Kotlin gives you for that — closed sets, heterogeneous data, multiple axes, exhaustive handling — and they cost nothing but the discipline to define the shapes up front.

## Resources

- [Sealed classes and interfaces — Kotlin documentation](https://kotlinlang.org/docs/sealed-classes.html)
- [when expressions — Kotlin documentation](https://kotlinlang.org/docs/control-flow.html#when-expression)
- [Data classes and data objects](https://kotlinlang.org/docs/data-classes.html)
- [Making illegal states unrepresentable (Scott Wlaschin)](https://fsharpforfunandprofit.com/posts/designing-with-types-making-illegal-states-unrepresentable/)
