---
title: "Swift Export in Kotlin Multiplatform"
slug: "kotlin-multiplatform-swift-export"
description: "Swift export in Kotlin Multiplatform generates real Swift APIs from shared code, skipping the Objective-C bridge that made KMP feel foreign to iOS engineers."
datePublished: "2026-05-01"
dateModified: "2026-05-01"
tags: ["Kotlin", "Kotlin Multiplatform", "iOS", "Interop"]
keywords: "Swift export, Kotlin Multiplatform iOS, KMP Swift interop, direct Swift export, Objective-C bridge"
faq:
  - q: "What is Swift export in Kotlin Multiplatform?"
    a: "Swift export is a mechanism that generates native Swift bindings directly from Kotlin code, rather than routing through an Objective-C header as the traditional KMP framework does. It means iOS consumers see idiomatic Swift types — proper enums, structs where appropriate, and cleaner naming — instead of Objective-C-flavored APIs, which makes shared Kotlin modules feel native to Swift engineers."
  - q: "How is Swift export different from the Objective-C framework KMP already produces?"
    a: "The classic KMP toolchain compiles your shared module into an Objective-C framework, and Swift consumes it through Objective-C interop. That loses Swift-only concepts: Kotlin enums arrive as classes, generics get erased, and nullability is approximate. Swift export skips the Objective-C layer and emits Swift directly, preserving more of the type information Swift developers expect."
  - q: "Is Swift export ready for production use?"
    a: "As of its early releases it is experimental and does not yet cover every Kotlin feature, so coverage gaps exist for things like some generics and coroutine suspend functions. It is production-viable for well-scoped shared modules if you validate the generated surface, but for large existing frameworks you should expect to adopt it incrementally alongside the Objective-C path."
---

Every iOS engineer I've handed a Kotlin Multiplatform framework to has asked the same question within an hour: "why does this enum look like a class, and why is everything an optional?" The answer, historically, was the Objective-C bridge — KMP compiled your shared code into an Objective-C framework, and Swift consumed it through that decades-old interop layer, flattening anything Objective-C couldn't express. Swift export changes that story. It generates Swift bindings directly from your Kotlin, so the shared module arrives on the iOS side looking like Swift a Swift developer would have written.

This matters more than it sounds. The technical case for sharing business logic across Android and iOS has been solid for years; the *adoption* case kept stalling on iOS engineers who found the generated API foreign. Swift export is aimed squarely at that friction.

## What the Objective-C bridge cost you

The old pipeline was Kotlin → Objective-C framework → Swift. Objective-C sat in the middle as the lingua franca, and it couldn't represent several things Swift and Kotlin both have:

- **Enums** became Objective-C classes with static instances, so you lost exhaustive `switch` and associated values.
- **Generics** were largely erased at the boundary, surfacing as `Any`-typed APIs that pushed casting onto the caller.
- **Nullability** was approximate — Objective-C's nullability annotations are looser than Kotlin's, so a lot of non-null Kotlin types arrived as Swift optionals.
- **Naming** carried Objective-C conventions, giving you verbose, prefix-heavy method names that read nothing like Swift.

None of this broke functionality. It broke *feel*, and feel is what determines whether the iOS team embraces or merely tolerates the shared module. I've watched a genuinely well-built shared layer get quietly wrapped in a hand-written Swift adapter by an iOS team just to make it pleasant to call — which defeats a chunk of the point.

## What Swift export produces instead

By emitting Swift directly, the export path preserves the type information the Objective-C layer discarded. A Kotlin enum can map to a Swift enum, nullability comes across more faithfully, and naming follows Swift conventions rather than Objective-C's. Consider a shared Kotlin API:

```kotlin
enum class ChargeState { IDLE, CHARGING, FAULTED }

data class Session(val id: String, val state: ChargeState, val kwhDelivered: Double)

class SessionRepository {
    fun activeSessions(): List<Session> = /* ... */
    fun latest(id: String): Session? = /* ... */
}
```

Through the Objective-C bridge, `ChargeState` arrives as a class, `activeSessions()` returns an untyped array you cast, and `latest` returns an optional that mirrors Kotlin's nullable — but the enum handling alone forces the Swift side into runtime checks. With Swift export, the enum can be a real Swift enum you `switch` over exhaustively, and the API reads the way an iOS engineer expects:

```swift
let repo = SessionRepository()
for session in repo.activeSessions() {
    switch session.state {
    case .charging: show(session.kwhDelivered)
    case .faulted:  showAlert()
    case .idle:     break
    }
}
```

That exhaustive `switch` — with the compiler forcing you to handle every case — is exactly what you lose through Objective-C, and exactly what makes the difference between "usable" and "native."

## The coverage caveat, stated honestly

Swift export is experimental in its early releases, and you should treat it that way. Not every Kotlin feature has a Swift mapping yet. The gaps I'd flag before you commit a large module:

| Feature | Objective-C bridge | Swift export (early) |
| --- | --- | --- |
| Enums | Class with static instances | Native Swift enum |
| Nullability | Approximate | More faithful |
| Naming | Objective-C conventions | Swift conventions |
| Generics | Largely erased | Partial, evolving |
| `suspend` functions | Completion handlers / async | Evolving support |
| Flows | Manual bridging | Manual bridging |

The two rows that matter most for real apps are `suspend` and `Flow`. If your shared surface is coroutine-heavy — and most modern KMP modules are — you'll still be doing some bridging for asynchronous APIs at the boundary. My advice: design the exported surface to be mostly synchronous value-returning functions and typed data, and keep the coroutine orchestration either fully inside the shared module or exposed through a thin, deliberately shaped async API. That's good boundary design regardless of Swift export, and it's the same discipline that keeps a [production Kotlin Multiplatform](https://blog.michaelsam94.com/kotlin-multiplatform-production-guide/) codebase maintainable.

## How I'd adopt it today

Incrementally, and with eyes open. Swift export and the Objective-C framework aren't mutually exclusive during the transition — you can export a well-scoped module through Swift export while keeping larger legacy frameworks on the Objective-C path. Concretely:

1. **Pick a leaf module** with mostly synchronous APIs and value types — a pricing calculator, a validation library, a domain model. Avoid starting with your coroutine-heavy networking layer.
2. **Generate and read the Swift.** Actually open the generated bindings with an iOS engineer in the room. The whole benefit is ergonomics, so review them like you'd review a public API.
3. **Validate the gaps.** Confirm the features you rely on export cleanly. Where they don't, decide whether to reshape the Kotlin API or wrap that piece.
4. **Expand outward** once the workflow is proven, keeping async boundaries deliberate.

## Why this is the unlock KMP needed

The comparison people always want is [Flutter versus Kotlin Multiplatform](https://blog.michaelsam94.com/flutter-vs-kotlin-multiplatform/), and one of Flutter's advantages was always a single, uniform developer experience across platforms. KMP's counter-pitch is "share the logic, keep each platform's native UI and feel" — but that pitch was undercut when the shared logic arrived on iOS feeling un-native. Swift export directly repairs that weak point. It doesn't make KMP a UI framework; it makes the *shared logic* a first-class Swift citizen, which is the exact seam where iOS teams were pushing back.

My take after a decade of cross-platform work: the technology to share code was never really the bottleneck. Team buy-in was, and buy-in follows ergonomics. An iOS engineer who can `switch` over a shared enum and get real Swift types stops seeing the shared module as an Android team's export and starts treating it as a library. That psychological shift is worth more than any single feature on the coverage matrix, and it's why Swift export — experimental warts and all — is the most strategically important thing to land in KMP interop in years.

Start small, validate the generated surface, keep async boundaries clean, and let the iOS team's reaction tell you how far to push it.

## Resources

- [Kotlin Multiplatform Swift export documentation](https://kotlinlang.org/docs/native-swift-export.html)
- [Kotlin/Native Objective-C and Swift interop](https://kotlinlang.org/docs/native-objc-interop.html)
- [Kotlin Multiplatform overview](https://www.jetbrains.com/kotlin-multiplatform/)
- [Kotlin Multiplatform samples](https://github.com/Kotlin/kmp-production-sample)
- [The Kotlin Blog](https://blog.jetbrains.com/kotlin/)
- [Swift language documentation](https://www.swift.org/documentation/)
