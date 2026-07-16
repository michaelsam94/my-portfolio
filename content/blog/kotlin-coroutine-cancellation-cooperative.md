---
title: "Cooperative Cancellation in Kotlin Coroutines"
slug: "kotlin-coroutine-cancellation-cooperative"
description: "Kotlin coroutine cancellation is cooperative: code must check for it to stop. How isActive, ensureActive, and NonCancellable work, and the traps that leak work."
datePublished: "2024-06-06"
dateModified: "2024-06-06"
tags: ["Kotlin", "Coroutines", "Concurrency"]
keywords: "Kotlin coroutine cancellation, cooperative cancellation, CancellationException, ensureActive, isActive, NonCancellable"
faq:
  - q: "Why is Kotlin coroutine cancellation cooperative?"
    a: "Cancellation sets a flag on the coroutine's Job rather than forcibly killing the thread, so the coroutine keeps running until it reaches a point that checks for cancellation. All suspending functions in kotlinx.coroutines check automatically, but a tight CPU loop with no suspension will run to completion regardless. Cooperative cancellation avoids the corruption risks of forcibly interrupting code mid-operation."
  - q: "How do I make a CPU-bound coroutine cancellable?"
    a: "Insert a cancellation check inside the loop with ensureActive(), which throws CancellationException if cancelled, or guard the loop with while (isActive). You can also call yield(), which both checks for cancellation and gives other coroutines a turn. Without one of these, a busy loop ignores cancellation entirely."
  - q: "Why should I not catch CancellationException?"
    a: "Cancellation is signalled by throwing CancellationException, and coroutines rely on it propagating up to actually stop. If you catch it in a broad try/catch and swallow it, the coroutine keeps running as if nothing happened, defeating cancellation. Always rethrow it, or catch only the specific exceptions you mean to handle."
---

Cancelling a Kotlin coroutine doesn't stop it — it *asks* it to stop. Cancellation flips a flag on the coroutine's `Job`, and the coroutine only actually halts when its code reaches a point that checks that flag. Every suspending function in `kotlinx.coroutines` checks automatically, so most code cancels promptly without you doing anything. But a coroutine that's grinding through a CPU-bound loop with no suspension points will happily ignore the cancellation and run to completion, burning work you asked it to abandon. Understanding this "cooperative" model is the difference between coroutines that clean up instantly and ones that leak work after the user has moved on.

The design is deliberate. Forcibly killing a coroutine mid-operation — the `Thread.stop()` approach — risks leaving shared state half-mutated and locks held. Cooperative cancellation trades a small amount of your attention for the guarantee that code stops at a *safe* point, never mid-statement. Once you internalize that, the traps become obvious.

## What cancellation actually is

`cancel()` on a `Job` throws a `CancellationException` inside the coroutine at its next suspension point. That exception propagates up like any other, running `finally` blocks on the way, until the coroutine unwinds. The key facts:

- Suspending functions from the library (`delay`, `withContext`, `emit`, channel ops) all check on entry and throw if cancelled.
- `CancellationException` is *special*: the machinery treats it as normal cancellation, not a failure, so it doesn't crash the parent scope.
- A cancelled coroutine's `Job` moves to "cancelling," runs cleanup, then "cancelled."

```kotlin
val job = launch {
    repeat(1000) { i ->
        delay(100)          // checks for cancellation, throws if cancelled
        println("tick $i")
    }
}
delay(350)
job.cancel()               // requests cancellation
job.join()                 // waits for it to actually finish
```

Here cancellation is prompt because `delay` is a suspension point that checks. Replace `delay` with a blocking `Thread.sleep` or heavy computation and the picture changes entirely.

## The CPU-bound trap

This is the bug I see most: a loop that does real work with no suspension point never cancels.

```kotlin
// BROKEN: ignores cancellation, runs all 1_000_000 iterations
val job = launch(Dispatchers.Default) {
    var sum = 0L
    for (i in 0..1_000_000) {
        sum += heavyCompute(i)   // no suspension, no cancellation check
    }
}
job.cancel()  // sets the flag... and the loop keeps going anyway
```

`cancel()` sets the flag, but nothing ever reads it, so the loop finishes regardless. The fix is to check cooperatively inside the loop. Three ways, in rough order of preference:

```kotlin
// 1. ensureActive() — throws CancellationException if cancelled. Cheapest.
for (i in 0..1_000_000) {
    ensureActive()
    sum += heavyCompute(i)
}

// 2. while (isActive) — check the boolean and exit gracefully.
var i = 0
while (isActive && i <= 1_000_000) { sum += heavyCompute(i++); }

// 3. yield() — checks AND lets other coroutines run. Slightly costlier.
for (i in 0..1_000_000) {
    yield()
    sum += heavyCompute(i)
}
```

`ensureActive()` is what I default to inside hot loops: it's a cheap flag read that throws when set, so the loop stops at the top of the next iteration. `yield()` does the same plus a dispatch, so use it when you also want to be a good citizen and not hog the dispatcher — but don't pay for the dispatch if you only need the check. For a tight numeric loop, check every N iterations rather than every one if the check itself shows up in a profile; the flag doesn't change that fast.

## Don't swallow CancellationException

The second classic bug: a broad `catch` that eats the cancellation signal.

```kotlin
// BROKEN: swallows cancellation, coroutine "survives" being cancelled
launch {
    try {
        fetchData()
    } catch (e: Exception) {     // catches CancellationException too!
        log.error("failed", e)   // logs it as an error and continues
    }
}
```

Because cancellation *is* a `CancellationException`, a `catch (e: Exception)` catches it, logs it as if the operation failed, and the coroutine proceeds as though nothing happened. Cancellation is defeated. The rules:

```kotlin
try {
    fetchData()
} catch (e: CancellationException) {
    throw e                       // always rethrow cancellation
} catch (e: IOException) {
    log.error("fetch failed", e)  // handle only what you mean to
}
```

Either rethrow `CancellationException` explicitly, or — better — catch only the specific exceptions you actually handle. A blanket `catch (Exception)` around suspending calls is almost always a latent cancellation bug. This is one of the sharpest differences from ordinary [error handling with Kotlin's Result type](https://blog.michaelsam94.com/kotlin-result-type-error-handling/): in coroutine code, one exception type is not yours to swallow.

## Cleanup: suspending in a cancelled coroutine

Cleanup in `finally` is important, but there's a subtlety: once a coroutine is cancelled, calling a suspending function in its `finally` block throws `CancellationException` immediately — because the coroutine is already cancelled. So a `finally` that tries to `withContext` or `delay` to release a resource will fail before doing the work.

```kotlin
val resource = acquire()
try {
    process(resource)
} finally {
    // This suspending close would throw because we're already cancelled:
    withContext(NonCancellable) {
        resource.closeSuspending()   // runs despite cancellation
    }
}
```

`NonCancellable` is the escape hatch: it creates a context that ignores cancellation, so suspending cleanup completes. Use it *only* for cleanup, and keep it short — it's a deliberate hole in the cancellation guarantee, and holding it around real work reintroduces exactly the "can't stop this" problem you were avoiding. Non-suspending cleanup (closing a file handle, `close()` on a plain resource) needs no special handling; it runs in `finally` normally.

## Timeouts are cancellation

`withTimeout` is cancellation with a deadline — it cancels the block when time runs out and throws `TimeoutCancellationException` (a subclass of `CancellationException`):

```kotlin
val result = withTimeout(2_000) {
    slowNetworkCall()   // cancelled if it exceeds 2s
}
```

If the block ignores cancellation (a CPU loop with no checks), the timeout won't fire on time — same cooperative rule. `withTimeoutOrNull` returns `null` instead of throwing, which is often cleaner for optional work. Everything you know about making loops cancellable applies directly to making timeouts actually work.

## The mental model that keeps you safe

Three rules cover almost every case. First, cancellation is a request, not a kill; your CPU-bound code must check (`ensureActive`, `isActive`, or `yield`) or it won't honor it. Second, `CancellationException` is sacred — rethrow it, never swallow it, and prefer catching specific exceptions over `Exception`. Third, suspending cleanup after cancellation needs `withContext(NonCancellable)`, used sparingly and only for teardown.

Get these right and coroutines cancel crisply: close a screen and its work stops, hit a timeout and the request abandons, and no orphaned computation keeps spinning after the result stops mattering. It all rests on the same foundation as the rest of the model — [structured concurrency](https://blog.michaelsam94.com/kotlin-structured-concurrency-supervisorjob/), where cancelling a parent cancels its children automatically, so most of the time the only cancellation you write is the cooperative check inside your own loops.

## Resources

- [Cancellation and timeouts — Kotlin coroutines guide](https://kotlinlang.org/docs/cancellation-and-timeouts.html)
- [ensureActive / isActive — kotlinx.coroutines API](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines/ensure-active.html)
- [Cancellation in coroutines (Manuel Vivo, Android Developers)](https://medium.com/androiddevelopers/cancellation-in-coroutines-aa6b90163629)
- [NonCancellable — API reference](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines/-non-cancellable/)
