---
title: "Structured Concurrency: Job vs SupervisorJob"
slug: "kotlin-structured-concurrency-supervisorjob"
description: "How structured concurrency ties coroutine lifetimes to scopes, and why Job propagates failure to siblings while SupervisorJob isolates it. When to use each."
datePublished: "2024-06-08"
dateModified: "2024-06-08"
tags: ["Kotlin", "Coroutines", "Concurrency"]
keywords: "structured concurrency, Job vs SupervisorJob, coroutineScope supervisorScope, coroutine failure propagation, CoroutineScope"
faq:
  - q: "What is structured concurrency in Kotlin?"
    a: "Structured concurrency means every coroutine belongs to a scope with a parent Job, and the scope won't complete until all its child coroutines finish. This guarantees no coroutine is orphaned or leaked, cancellation flows from parent to children automatically, and failures propagate predictably. It turns concurrency from a loose collection of background tasks into a tree with well-defined lifetimes."
  - q: "What is the difference between Job and SupervisorJob?"
    a: "With a regular Job, a failure in one child cancels the parent and therefore all sibling coroutines. With a SupervisorJob, a child's failure is isolated: it does not cancel the parent or siblings, so the other children keep running. Choose Job when the children form an all-or-nothing unit, and SupervisorJob when children are independent tasks that should fail independently."
  - q: "When should I use supervisorScope over coroutineScope?"
    a: "Use coroutineScope when you launch several coroutines that together form one operation, so if any fails the whole thing should fail and cancel the rest. Use supervisorScope when you launch independent children — say, loading several unrelated widgets — where one failing shouldn't take down the others. supervisorScope lets each child fail without cancelling its siblings."
---

Structured concurrency is the rule that every coroutine lives inside a scope, and that scope refuses to finish until all its children do. This is what makes Kotlin coroutines safe by default: you can't accidentally leak a background task, because a task's lifetime is bounded by the scope that launched it, and cancelling the scope cancels every child. The one decision that trips people up is what happens when a child *fails* — and that's exactly the difference between a regular `Job` (failure cancels everyone) and a `SupervisorJob` (failure stays local). Pick the wrong one and either an isolated error takes down your whole screen, or a critical failure gets silently ignored while dependent work keeps running on bad data.

I think of a scope as a small contract: "these coroutines belong together, and here's what happens if one of them dies." Getting that contract right is most of what separates coroutine code that's easy to reason about from the kind that leaks tasks and swallows errors.

## The tree: scopes, jobs, and lifetimes

Every `CoroutineScope` has a `Job` in its context, and every coroutine you `launch` or `async` becomes a child of that `Job`. This parent-child linkage does three things automatically:

- The parent scope's `Job` doesn't complete until all children complete.
- Cancelling the parent cancels all children (and their children, recursively).
- A child's failure, by default, cancels the parent — which cancels the siblings.

```kotlin
coroutineScope {              // creates a scope; suspends until all children done
    launch { taskA() }
    launch { taskB() }
}                             // only returns here once BOTH finish
```

`coroutineScope` won't return until `taskA` and `taskB` both complete. There's no way to "forget" a coroutine — it's tied to the scope. This is the guarantee that eliminates a whole category of leaks, and it's the reason `GlobalScope` is discouraged: it detaches a coroutine from any structured parent, so nothing owns its lifetime. The same cooperative machinery from [coroutine cancellation](https://blog.michaelsam94.com/kotlin-coroutine-cancellation-cooperative/) is what propagates cancellation down this tree.

## Regular Job: all-or-nothing

With a normal `Job`, children share a fate. If one throws, the exception propagates up to the parent, which cancels itself and therefore all the other children.

```kotlin
coroutineScope {
    launch { loadProfile() }    // if this throws...
    launch { loadOrders() }     // ...this gets cancelled too
    launch { loadSettings() }   // ...and so does this
}
// the whole coroutineScope throws, and none complete normally
```

This is correct when the three loads form *one operation* — say, everything needed to render a screen, where partial data is useless. If the profile can't load, there's no point finishing the orders; fail fast, cancel the rest, surface one error. That's the semantics `coroutineScope` (and a plain `Job`) gives you, and for genuinely coupled work it's exactly what you want.

## SupervisorJob: independent children

A `SupervisorJob` breaks the downward-only failure propagation: a child's failure does *not* cancel the parent or its siblings. Each child fails alone.

```kotlin
supervisorScope {
    launch { loadWeatherWidget() }   // if this throws, it fails alone
    launch { loadNewsWidget() }      // this keeps running
    launch { loadStocksWidget() }    // this too
}
```

This is what you want for a dashboard of independent widgets, a screen where several unrelated sections load in parallel, or any set of tasks where "one failed" shouldn't mean "abandon everything." The weather service being down shouldn't blank out the news.

There's a critical catch with `supervisorScope`: because failures aren't propagated to the parent, an unhandled exception in a `launch` child goes to the `CoroutineExceptionHandler` (or crashes) rather than being rethrown by `supervisorScope`. So you handle errors *per child*:

```kotlin
supervisorScope {
    launch {
        try { loadWeatherWidget() }
        catch (e: Exception) { showWeatherError() }   // handle locally
    }
    launch { loadNewsWidget() }
}
```

With `SupervisorJob`, each child is responsible for its own errors, because the scope won't do it for you. Forgetting this is the classic `SupervisorJob` bug: an isolated failure that no one catches, silently lost.

## async is different: failure vs await

One nuance that bites people: `async` under a supervisor still *stores* the exception and rethrows it when you call `await()`. The supervisor stops it from cancelling siblings, but the error isn't gone — it's waiting in the `Deferred`.

```kotlin
supervisorScope {
    val a = async { mightFail() }
    val b = async { alsoWork() }
    // b is unaffected by a's failure, but:
    val ra = try { a.await() } catch (e: Exception) { fallback() }  // must catch here
    val rb = b.await()
}
```

Under a regular `coroutineScope`, an `async` that fails cancels the scope immediately, even before you `await`. Under `supervisorScope`, the failure is deferred to the `await`. Know which model you're in or the timing of when the exception surfaces will confuse you.

## Choosing, in practice

| Question | Answer → use |
|---|---|
| Do the children form one atomic operation? | Yes → `coroutineScope` / `Job` |
| Should one failure abort the rest? | Yes → `coroutineScope` / `Job` |
| Are the children independent tasks? | Yes → `supervisorScope` / `SupervisorJob` |
| Should one failure leave siblings running? | Yes → `supervisorScope` / `SupervisorJob` |

The Android `viewModelScope` and `lifecycleScope` are built on a `SupervisorJob` for a reason: you don't want one failed background task in a `ViewModel` to tear down every other coroutine the `ViewModel` owns. But *inside* one of those, when you fan out work that's genuinely coupled, you drop into a `coroutineScope` so that unit fails together. Nesting the two — a supervisor at the top for independence, `coroutineScope` blocks inside for atomic sub-operations — is the normal, healthy structure.

## The takeaway

Structured concurrency gives you the leak-free guarantee for free: coroutines are tied to scopes, scopes wait for their children, and cancellation flows down the tree. The one knob you actively choose is failure propagation. Reach for a plain `Job`/`coroutineScope` when children live and die together, and a `SupervisorJob`/`supervisorScope` when they're independent — and in the supervisor case, remember that error handling becomes *your* job, per child, because the scope has deliberately stopped doing it for you. That single distinction, applied deliberately, is what keeps concurrent code both robust against unrelated failures and honest about coupled ones.

## Resources

- [Coroutine context and dispatchers — Kotlin documentation](https://kotlinlang.org/docs/coroutine-context-and-dispatchers.html)
- [Exceptions and supervision — Kotlin coroutines guide](https://kotlinlang.org/docs/exception-handling.html)
- [Structured concurrency (Roman Elizarov)](https://elizarov.medium.com/structured-concurrency-722d765aa952)
- [Coroutines best practices (developer.android.com)](https://developer.android.com/kotlin/coroutines/coroutines-best-practices)
