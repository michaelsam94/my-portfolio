---
title: "How Compose Snapshot State Actually Works"
slug: "compose-snapshot-state-internals"
description: "Compose snapshot state internals: how the snapshot system gives MVCC-style isolation, tracks reads and writes, powers recomposition, and lets you mutate off the main thread."
datePublished: "2024-09-01"
dateModified: "2024-09-01"
tags: ["Android", "Jetpack Compose", "Kotlin"]
keywords: "Compose snapshot state, snapshot system, mutableStateOf internals, MVCC Compose, read observer, snapshot isolation, recomposition"
faq:
  - q: "What is the snapshot system in Jetpack Compose?"
    a: "The snapshot system is the concurrency and observation mechanism behind Compose state. It works like multiversion concurrency control in a database: each state object can hold multiple versioned records, and a snapshot is an isolated view of state at a point in time. This is what lets Compose observe exactly which state a composable reads, batch writes atomically, and even mutate state safely on a background thread."
  - q: "How does Compose know which composables to recompose?"
    a: "When a composable runs, the snapshot system installs a read observer that records every state object the composable reads. Those reads are associated with that composition scope, so when one of those state objects is later written, Compose knows precisely which scopes are now invalid and schedules only those for recomposition. That read-tracking is why Compose can skip unaffected parts of the tree instead of re-running everything."
  - q: "Can I modify Compose state from a background thread?"
    a: "Yes. Because the snapshot system uses isolated, versioned records, you can take a snapshot on a background thread, mutate state within it, and atomically apply it, and readers on other threads see a consistent view until the apply happens. mutableStateOf is thread-safe for this reason, though you still typically drive UI state from the main thread and use this capability for specific concurrent workloads."
---

The magic trick in Jetpack Compose — that changing a variable automatically updates exactly the right pixels — is not magic. It's a snapshot system that works like multiversion concurrency control (MVCC) in a database, layered with read-tracking. Understanding it turns Compose from a mysterious reactive framework into something with a mechanical model you can reason about: state objects hold *versioned* values, a *snapshot* is an isolated view of all state at a moment, reads are *observed* and attributed to whoever read them, and writes create new versions that get *applied* atomically. Once that clicks, questions like "why did this recompose," "why is my state thread-safe," and "why do I see a consistent value mid-frame" all have straightforward answers.

I'll build the model from the bottom up, because most Compose performance and correctness intuition flows from it.

## State objects hold versioned records

`mutableStateOf(x)` doesn't store a single value. It stores a linked list of *state records*, each tagged with the id of the snapshot that wrote it. When you read `state.value`, you don't get "the value" — you get the value *valid in your current snapshot*, chosen by walking the records for the newest one your snapshot is allowed to see. This is exactly how a MVCC database serves each transaction a consistent view without locking.

The payoff: two snapshots can hold different versions of the same state simultaneously, each internally consistent, without stepping on each other. That's the foundation for both isolation and off-thread mutation.

## A snapshot is an isolated view

A snapshot captures "the state of the world" at an instant. Compose runs work inside snapshots so that everything a computation reads is consistent — even if another thread writes in the middle. Two kinds matter:

- A **read-only snapshot** gives you a frozen, consistent view; writes are forbidden.
- A **mutable snapshot** lets you write; those writes are visible only *inside* that snapshot until you `apply()` them, at which point they become visible globally.

```kotlin
val snapshot = Snapshot.takeMutableSnapshot()
snapshot.enter {
    account.balance -= 100      // visible only inside this snapshot
    account.txns += withdrawal
}
snapshot.apply()                // now atomically visible to everyone
```

Before `apply()`, no other reader sees the half-updated account. After `apply()`, they see *both* changes at once. That atomic, all-or-nothing visibility is why you never observe a torn, half-updated UI state — the same guarantee a database transaction gives you.

## Read tracking: how recomposition targets the right scope

This is the part that makes Compose feel intelligent. When a composable executes, Compose installs a **read observer** on the current snapshot. Every `state.value` read while that observer is active gets recorded and attributed to the current recomposition scope. So Compose builds a precise map: *this scope read state A and state B.*

Later, when someone writes state A, a **write observer** notes it, and the snapshot system tells Compose "state A changed." Compose looks up which scopes read A, marks exactly those invalid, and schedules only them for recomposition. Everything that didn't read A is untouched.

```kotlin
@Composable
fun Counter(state: CounterState) {
    Text("Count: ${state.count}")   // read of state.count recorded for THIS Text scope
    // A composable elsewhere that never reads state.count won't recompose when it changes.
}
```

This is the mechanical truth behind "Compose only recomposes what changed" — and behind the [stability and skipping rules](https://blog.michaelsam94.com/compose-stability-annotations-deep/). It's also why reading state at the *narrowest* scope matters: if you read `state.count` high in the tree and pass it down, the whole subtree is the scope that gets invalidated. Read it low, and only the leaf recomposes. Deferring the read (passing a lambda `() -> Int` instead of the `Int`) is the trick behind performance patterns like `Modifier.offset { }` reading scroll state without recomposing.

## Why your state is thread-safe

Because records are versioned and writes are isolated until applied, you can mutate Compose state from a background thread. A background snapshot mutates its own records; main-thread readers keep seeing the old version until `apply()`. There's no shared mutable value being raced on — there are versioned records and an atomic apply. That's why `mutableStateOf` is safe to write from a coroutine on `Dispatchers.Default`, and why frameworks can do concurrent recomposition experiments on top of it.

In practice you still drive most UI state from the main thread, but this is not because the state isn't thread-safe — it's because your *derivations* and ordering are simpler that way. The capability is there for genuine concurrent workloads.

## The global snapshot and when changes propagate

There's a special "global" snapshot that ordinary main-thread code writes into. Applied changes don't instantly ping observers; the system sends **apply notifications** when snapshots are applied, and Compose's recomposer listens for them to know work is pending. This batching is why setting five state values in a row triggers *one* recomposition pass, not five — they're coalesced and the invalid scopes are recomposed together on the next frame. Understanding this batching explains why you can freely update several states in an event handler without worrying about intermediate recompositions.

## Why any of this matters day to day

You don't call the snapshot API directly often, but the model explains the rules you live by:

- **Read state as low and as late as possible** — the read scope is what gets invalidated, so narrow reads mean narrow recomposition.
- **Only `State` reads are tracked** — mutating a plain `var` or a raw `ArrayList` changes nothing observable, so the UI won't update. Use `mutableStateOf`/`mutableStateListOf`.
- **Writes are atomic per apply** — batch related updates and they present consistently.
- **Off-thread mutation is safe** — the versioning makes it so, if you ever need it.

The snapshot system is the quiet engine under every `remember`, every recomposition, every `derivedStateOf`. Learn it once and the reactive behavior stops being spooky — it's just versioned records, isolated snapshots, and tracked reads, doing exactly what a transactional store would do.

## Resources

- [Compose state documentation](https://developer.android.com/develop/ui/compose/state)
- [Compose runtime: snapshot system (source)](https://cs.android.com/androidx/platform/frameworks/support/+/androidx-main:compose/runtime/runtime/src/commonMain/kotlin/androidx/compose/runtime/snapshots/)
- [Thinking in Compose](https://developer.android.com/develop/ui/compose/mental-model)
- [Compose performance: defer reads](https://developer.android.com/develop/ui/compose/performance/bestpractices#defer-reads)
- [Multiversion concurrency control (overview)](https://en.wikipedia.org/wiki/Multiversion_concurrency_control)
