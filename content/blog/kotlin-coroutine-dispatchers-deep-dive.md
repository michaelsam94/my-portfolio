---
title: "Kotlin Coroutine Dispatchers, Explained Properly"
slug: "kotlin-coroutine-dispatchers-deep-dive"
description: "What Kotlin coroutine dispatchers actually do: Default vs IO vs Main, thread pools, limitedParallelism, and why withContext for CPU work is usually a mistake."
datePublished: "2024-06-09"
dateModified: "2024-06-09"
tags: ["Kotlin", "Coroutines", "Performance"]
keywords: "Kotlin dispatchers, Dispatchers.IO Default Main, withContext, limitedParallelism, coroutine thread pool, dispatcher confinement"
faq:
  - q: "What is the difference between Dispatchers.Default and Dispatchers.IO?"
    a: "Dispatchers.Default is sized to the number of CPU cores and is meant for CPU-intensive work like sorting or parsing, where more threads than cores would only add contention. Dispatchers.IO is sized much larger (default 64+) because IO work spends most of its time blocked waiting, so many threads can be in flight without saturating the CPU. They share the same underlying thread pool but enforce different parallelism limits."
  - q: "Do I need withContext(Dispatchers.IO) around Retrofit or Room calls?"
    a: "Usually no. Modern suspend-based libraries like Retrofit and Room already dispatch their blocking work to an appropriate pool internally, so wrapping their suspend functions in withContext(Dispatchers.IO) is redundant. You need withContext(Dispatchers.IO) only when you call genuinely blocking APIs yourself, such as raw file IO or a blocking JDBC driver."
  - q: "What does limitedParallelism do?"
    a: "limitedParallelism creates a view of a dispatcher that caps how many coroutines run concurrently on it, without spawning a new thread pool. It replaces the old pattern of newFixedThreadPoolContext for rate-limiting, letting you bound concurrency to a resource — say, at most 4 concurrent calls to a fragile API — while still sharing threads with the parent dispatcher."
---

A Kotlin dispatcher decides *which thread* a coroutine runs on, and the three you'll use — `Default`, `IO`, and `Main` — differ almost entirely in how many threads they're willing to spend. `Default` is sized to your CPU cores for compute-bound work, `IO` is sized large (64+ threads) for work that spends its time blocked waiting, and `Main` is the single UI thread. Pick the dispatcher that matches the *nature* of the work — CPU-bound, blocking-IO-bound, or UI — and coroutines schedule efficiently. Pick reflexively and you either starve the CPU pool with blocking calls or waste threads on work that never blocks.

Most dispatcher confusion comes from treating them as interchangeable labels. They're not; they encode a resource model. Once you see `Default` as "as many threads as cores, because more won't help compute" and `IO` as "many threads, because blocked threads don't use the CPU," almost every choice becomes obvious.

## The three dispatchers and what they're for

```kotlin
Dispatchers.Main     // the UI thread — touch views/Compose here only
Dispatchers.Default  // CPU-bound work — parsing, sorting, image processing
Dispatchers.IO       // blocking IO — files, sockets, blocking DB drivers
Dispatchers.Unconfined // rarely — starts in caller's thread, don't use casually
```

`Default` is capped at the number of CPU cores (minimum 2). The logic: if the work is pure computation, running more threads than cores just adds context-switching overhead without doing more work in parallel. `IO` defaults to 64 threads (or more if you have more cores). The logic there is the inverse: IO-bound work spends most of its wall-clock time *blocked*, holding a thread but not using the CPU, so you can have dozens in flight at once without saturating anything. The subtle bit: `Default` and `IO` share the same underlying pool of threads — `IO` just permits more of them to be active. Switching between them doesn't always mean an actual thread handoff.

## The mistake: withContext(IO) for CPU work

The single most common dispatcher error I review is wrapping CPU-bound work in `Dispatchers.IO`:

```kotlin
// WRONG: heavy parsing is CPU work, not IO
val result = withContext(Dispatchers.IO) {
    parseAndTransform(hugeJson)   // no blocking IO here — it's all CPU
}
```

Nothing here blocks on IO; it's all computation. Running it on `IO` lets up to 64 of these run at once, which oversubscribes the CPU and *slows everything down* under load — you get more threads fighting for the same cores. The right dispatcher is `Default`, which caps parallelism at core count so compute-bound tasks don't thrash:

```kotlin
val result = withContext(Dispatchers.Default) {
    parseAndTransform(hugeJson)   // CPU-bound → Default
}
```

The rule: `IO` for work that *waits* (blocked on a socket, disk, or blocking driver); `Default` for work that *computes*. When in doubt, ask "does this thread sit idle waiting for something external, or is it busy calculating?"

## You probably don't need withContext around suspend libraries

The other reflex worth unlearning: wrapping already-suspending library calls.

```kotlin
// REDUNDANT: Retrofit and Room already offload their blocking work
withContext(Dispatchers.IO) {
    api.getUser()   // suspend fun — Retrofit dispatches internally
    dao.insert(user) // suspend fun — Room uses its own executor
}
```

Modern suspend-based libraries — Retrofit, Room, Ktor client — already move their blocking work onto an appropriate pool. Their `suspend` functions are *main-safe*: you can call them from `Dispatchers.Main` and they won't block the UI. Wrapping them in `withContext(Dispatchers.IO)` adds a pointless context switch and signals a misunderstanding of the contract. You only need `withContext(Dispatchers.IO)` when *you* call a genuinely blocking API — raw `File` streams, a blocking JDBC driver, `Thread.sleep`, a legacy SDK. This connects to the earlier point about [Ktorfit and type-safe networking in KMP](https://blog.michaelsam94.com/kotlin-multiplatform-networking-ktorfit/): well-designed suspend APIs handle their own dispatching so callers don't have to.

## withContext vs launch: switching vs starting

`withContext` *switches* the current coroutine's dispatcher for a block and returns its result, suspending until done. It doesn't start a new coroutine. `launch`/`async` *start* a new child coroutine, optionally on a different dispatcher.

```kotlin
suspend fun compute(): Int = withContext(Dispatchers.Default) {
    // same coroutine, now on Default; result comes back to the caller's context
    heavyMath()
}
```

The idiom for a suspend function is to declare *its own* dispatcher internally with `withContext`, so callers don't have to think about threading — the function is main-safe by construction. Push the dispatcher decision *into* the function rather than making every call site remember to wrap it. This is the same "decide once, high up" discipline that keeps larger systems maintainable, echoed in how coroutine scopes are structured under [structured concurrency](https://blog.michaelsam94.com/kotlin-structured-concurrency-supervisorjob/).

## Bounding concurrency with limitedParallelism

Sometimes you need to *cap* how many coroutines hit a resource — a flaky API that falls over past 4 concurrent requests, or a rate limit. The modern tool is `limitedParallelism`, which returns a view of a dispatcher with a concurrency ceiling, sharing the parent's threads rather than allocating a new pool:

```kotlin
private val fragileApiDispatcher = Dispatchers.IO.limitedParallelism(4)

suspend fun callFragileApi() = withContext(fragileApiDispatcher) {
    // at most 4 of these run concurrently, ever
    blockingApiCall()
}
```

This replaces the old `newFixedThreadPoolContext`, which spun up dedicated threads you had to `close`. `limitedParallelism` is cheaper (no new threads, just a limiter) and composes cleanly. I've used it to protect a downstream service that couldn't handle bursts — bounding client concurrency at the dispatcher is far simpler than a semaphore sprinkled through call sites.

## A quick reference

| Work type | Dispatcher | Why |
|---|---|---|
| Update UI / touch Compose state | `Main` | UI must be single-threaded |
| Parse, sort, encode, compute | `Default` | capped at cores — no CPU thrash |
| Blocking file / socket / JDBC | `IO` | large pool — blocked threads are cheap |
| Retrofit / Room / Ktor suspend calls | none | already main-safe, don't wrap |
| Rate-limit a fragile resource | `IO.limitedParallelism(n)` | bound concurrency, share threads |

Dispatchers aren't a decoration you sprinkle for safety — each one encodes a resource trade-off. Match `Default` to computation, `IO` to blocking waits, `Main` to UI, and let well-behaved suspend libraries manage their own threading. Reserve `withContext(IO)` for the blocking APIs you actually call yourself, and use `limitedParallelism` when you need a concurrency ceiling. Get the mapping right and the scheduler does the rest; get it wrong and you'll spend an afternoon wondering why adding threads made everything slower.

## Resources

- [Coroutine context and dispatchers — Kotlin documentation](https://kotlinlang.org/docs/coroutine-context-and-dispatchers.html)
- [Dispatchers API reference](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines/-dispatchers/)
- [Improve app performance with Kotlin coroutines (developer.android.com)](https://developer.android.com/kotlin/coroutines/coroutines-adv)
- [Explicit concurrency limits with limitedParallelism (Roman Elizarov)](https://elizarov.medium.com/reactive-streams-and-kotlin-flows-bfd12772cda4)
