---
title: "Understanding the Kotlin/Native Memory Model"
slug: "kotlin-native-memory-model"
description: "A clear guide to the Kotlin/Native memory model: how the new memory manager works, what changed from the old freezing model, and how to avoid leaks on iOS."
datePublished: "2024-09-23"
dateModified: "2024-09-23"
tags: ["Kotlin", "Kotlin Multiplatform", "Kotlin/Native", "iOS"]
keywords: "Kotlin Native memory model, new memory manager, Kotlin freeze, Kotlin Native garbage collection, KMP memory leaks iOS"
faq:
  - q: "Do I still need to freeze objects in Kotlin/Native?"
    a: "No. The freezing model was removed with the new memory manager, which became the default and is now the only supported model. You can share mutable objects between threads without freezing, and the old freeze()/ensureNeverFrozen() APIs are deprecated. If you're reading a tutorial that tells you to freeze objects, it predates the new memory manager."
  - q: "How does garbage collection work in Kotlin/Native?"
    a: "Kotlin/Native uses a tracing garbage collector — a stop-the-world mark phase with concurrent sweeping in recent versions — rather than pure reference counting. It integrates with Objective-C/Swift ARC at the interop boundary so objects crossing between Kotlin and Swift are managed correctly. You generally don't tune it, but you can observe GC behavior through runtime logging when diagnosing pauses."
  - q: "Why does my Kotlin object leak when used from Swift?"
    a: "The most common cause is a retain cycle across the interop boundary — a Kotlin object holding a Swift closure that captures the Swift object holding the Kotlin object. Break the cycle with weak references on the Swift side, just as you would in pure Swift. Long-lived Kotlin singletons capturing UI callbacks are the usual culprit."
---

If you learned Kotlin/Native before 2021, most of what you know about its memory model is now wrong — and that's good news. The old model, with its infamous object *freezing* and thread-confined mutability, was the single biggest source of friction in Kotlin Multiplatform. `InvalidMutabilityException` at runtime, `freeze()` calls scattered defensively through shared code, and coroutines that couldn't cross threads without ceremony. The **new memory manager** removed all of that. Understanding what changed — and the small number of things you still have to think about — is what keeps iOS-side KMP code correct.

## The old model, briefly, so the change makes sense

The original Kotlin/Native memory model enforced a hard rule: an object was either mutable and confined to one thread, or *frozen* (deeply immutable) and shareable across threads. Sharing a mutable object between threads threw at runtime. This made shared state and multithreaded coroutines genuinely painful — you'd `freeze()` things to share them, then get bitten when frozen state couldn't be updated. Whole libraries existed to work around it. It was a defensible design for safety, but it leaked its complexity into every developer's day.

## The new memory manager: share mutable state freely

The new memory manager, now the default and only supported model, drops the freezing requirement entirely. You can share mutable objects across threads the same way you would on the JVM. Concurrency is managed with the normal tools — coroutines, atomics, locks — not with a special immutability regime.

```kotlin
// This used to require freezing and would throw at runtime pre-new-MM.
// Now it just works.
class Counter { var value: Int = 0 }

suspend fun bump(counter: Counter) = withContext(Dispatchers.Default) {
    counter.value++   // mutable object, background thread — fine now
}
```

Practically, this means KMP coroutine code behaves like JVM coroutine code. `Dispatchers.Default` and multithreaded coroutine dispatch work on iOS without freezing gymnastics, which is why modern shared code can use the same [coroutine and Flow patterns](https://blog.michaelsam94.com/kotlin-coroutines-flow-patterns/) across every target instead of a special native dialect.

## What replaced freezing: a tracing GC

Under the hood, Kotlin/Native now uses a **tracing garbage collector**. Earlier it relied heavily on reference counting (which can't reclaim cycles on its own); the modern collector does a tracing mark phase to find live objects and reclaims the rest, including cycles that pure reference counting would leak. Recent versions moved the sweep concurrent to reduce pause times. You don't configure this for normal apps — it's automatic — but knowing it's a *tracing* GC explains why plain reference cycles inside pure Kotlin code no longer leak.

The nuance is the interop boundary. Kotlin/Native integrates with Objective-C/Swift **ARC**: objects that cross between Kotlin and Swift are tracked so neither side frees something the other still holds. That integration is mostly invisible — until you create a cycle that *spans* the boundary.

## The leak that still happens: cross-boundary retain cycles

The GC handles cycles inside Kotlin. ARC handles cycles inside Swift. Neither fully handles a cycle that goes *through* both. The classic shape:

```kotlin
// Kotlin — a long-lived shared singleton
object EventBus {
    private val listeners = mutableListOf<(String) -> Unit>()
    fun subscribe(cb: (String) -> Unit) { listeners += cb }
}
```

```swift
// Swift
class FeedViewModel {
    init() {
        // self captured strongly by the Kotlin-held closure
        EventBus().subscribe { event in self.handle(event) }
    }
}
```

Now `EventBus` (Kotlin, long-lived) holds a closure that strongly captures the Swift `FeedViewModel`, which never gets deallocated. This is a real leak, and it's not a Kotlin bug — it's the same retain-cycle problem you'd have with any long-lived Swift observer. The fix is the Swift one: capture `self` weakly.

```swift
EventBus().subscribe { [weak self] event in self?.handle(event) }
```

The lesson I hammer on in reviews: **treat Kotlin singletons that hold Swift callbacks like any strong reference in ARC.** If the Kotlin side outlives the Swift side and holds a strong capture of it, you leak. Weak-capture on the Swift side, or give the Kotlin side an explicit `unsubscribe`.

## Diagnosing memory issues

A short checklist when iOS memory grows unexpectedly:

1. **Xcode Instruments (Leaks / Allocations).** Because Kotlin objects participate in ARC at the boundary, they show up in Instruments. Look for Kotlin-typed objects that never deallocate.
2. **Check long-lived Kotlin holders.** Singletons, static `object`s, and shared repositories that accumulate listeners or cache entries without eviction.
3. **Look for boundary closures.** Any Kotlin API taking a Swift callback that's stored long-term is a cycle candidate.
4. **Runtime GC logging.** Kotlin/Native can log GC activity, useful for confirming whether growth is uncollected garbage vs a genuine leak (a true leak won't be reclaimed no matter how often GC runs).

## What changed for your code, concretely

| Concern | Old model | New memory manager |
| --- | --- | --- |
| Sharing mutable state across threads | Required `freeze()`, could throw | Just works |
| Multithreaded coroutines on iOS | Painful, restricted | Standard, like JVM |
| Reclaiming reference cycles | Leaked (reference counting) | Reclaimed (tracing GC) |
| `freeze()` / `ensureNeverFrozen()` | Core APIs | Deprecated, no-ops |
| Cross-boundary retain cycles | Existed | Still exist — use weak refs |

## What I'd take away

The Kotlin/Native memory model is no longer a special discipline you fight. Freezing is gone; a tracing GC reclaims cycles inside Kotlin, and ARC integration keeps the interop boundary honest. Write shared concurrency the way you'd write it on the JVM. The one thing that survived is ordinary reference hygiene at the Swift boundary: don't let a long-lived Kotlin object strongly hold a Swift object that should be free to die. Get that right and Kotlin/Native memory management is, for the first time, boring — which is exactly what you want from a memory model.

## Resources

- [Kotlin/Native memory management](https://kotlinlang.org/docs/native-memory-manager.html)
- [Migrating to the new memory manager](https://kotlinlang.org/docs/native-migration-guide.html)
- [Kotlin/Native and Swift/Objective-C interoperability](https://kotlinlang.org/docs/native-objc-interop.html)
- [Apple — Automatic Reference Counting](https://developer.apple.com/library/archive/documentation/Swift/Conceptual/Swift_Programming_Language/AutomaticReferenceCounting.html)
