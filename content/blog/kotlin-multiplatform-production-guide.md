---
title: "Kotlin Multiplatform in Production: A 2026 Guide"
slug: "kotlin-multiplatform-production-guide"
description: "A practical 2026 guide to Kotlin Multiplatform in production: what to share, expect/actual, the iOS story, testing, CI, and the pitfalls that actually bite teams."
datePublished: "2026-03-23"
dateModified: "2026-03-23"
tags: ["Kotlin Multiplatform", "Android", "iOS", "Architecture"]
keywords: "Kotlin Multiplatform, KMP, shared business logic, KMP production, cross-platform Kotlin, expect actual"
faq:
  - q: "Is Kotlin Multiplatform production-ready in 2026?"
    a: "Yes. KMP is stable and used in production by many large apps to share business logic, networking, and data layers across Android and iOS. The shared-logic-with-native-UI model is mature; sharing UI via Compose Multiplatform is also viable but a separate decision."
  - q: "What should you share in a Kotlin Multiplatform project?"
    a: "Share the layers that are pure logic and change together across platforms: networking, serialization, data/repository layer, business rules, and validation. Keep UI native per platform unless you deliberately adopt Compose Multiplatform. This maximizes reuse while keeping platform-native feel."
  - q: "How does expect/actual work in Kotlin Multiplatform?"
    a: "You declare an 'expect' API in common code and provide platform-specific 'actual' implementations per target. It's the mechanism for accessing platform features — like secure storage or system APIs — from shared code without leaking platform details into your business logic."
---

The question I get most from teams eyeing Kotlin Multiplatform isn't "does it work" — it clearly does, and has for years now — it's "what will actually hurt when we put it in production." I've shipped KMP in real apps, and the answer is that the technology is the easy part. The hard parts are drawing the sharing boundary correctly, the iOS integration seams, and CI. Get those right and KMP is a genuine multiplier; get them wrong and you've built a shared library nobody wants to touch.

This is a pragmatic 2026 guide: what to share, how the platform seams work, and the pitfalls that bite in practice.

## Share logic, keep UI a deliberate choice

The single most important decision is the sharing boundary. The reliable, high-ROI answer is to share everything *below* the UI: networking, serialization, the [data/repository layer](https://blog.michaelsam94.com/shared-data-layer-room-kmp/), business rules, validation, and the domain model. These are the layers that (a) contain the bugs you'd hate to fix twice and (b) genuinely should behave identically on Android and iOS.

UI is a separate call. You can keep native UI — Compose on Android, SwiftUI on iOS — consuming a shared ViewModel/presentation layer, which is the safest default and what most large production KMP apps do. Or you can go further with [Compose Multiplatform](https://blog.michaelsam94.com/compose-multiplatform-shared-ui/) and share the UI too. Both are viable in 2026; the difference is how much platform-native feel and per-platform flexibility you're willing to trade for more reuse. My default: share logic aggressively, share UI only when the team is bought in and the app's UI is not deeply platform-idiomatic.

## expect/actual: the platform seam

When shared code needs something platform-specific — secure storage, the current locale, a system clock — you use `expect`/`actual`. You declare the API once in common code and implement it per target.

```kotlin
// commonMain
expect class KeyValueStore() {
    fun putString(key: String, value: String)
    fun getString(key: String): String?
}

// androidMain
actual class KeyValueStore actual constructor() {
    private val prefs = /* EncryptedSharedPreferences */
    actual fun putString(key: String, value: String) { prefs.edit().putString(key, value).apply() }
    actual fun getString(key: String) = prefs.getString(key, null)
}

// iosMain — backed by the iOS Keychain
actual class KeyValueStore actual constructor() {
    actual fun putString(key: String, value: String) { /* Keychain */ }
    actual fun getString(key: String): String? { /* Keychain */ }
}
```

A practical refinement: don't reach for `expect`/`actual` for everything. For many cases a plain `interface` in common code with platform implementations injected at the app boundary is cleaner and more testable than the language-level mechanism. I reserve `expect`/`actual` for genuinely leaf-level platform access and use interfaces + DI for the rest. That keeps shared code honest about its dependencies — the same discipline behind [android security and keystore storage](https://blog.michaelsam94.com/android-security-keystore-encrypted-storage/) applies here, since the secure-storage `actual` is exactly where you must not cut corners.

## The iOS reality

This is where teams underestimate the effort. Kotlin compiles to a native framework consumed by Swift, and the integration has real ergonomics to manage:

- **API surface for Swift.** Kotlin features don't all map cleanly to Swift. Suspend functions, sealed hierarchies, and generics can surface awkwardly. Keep the *public* API of your shared module deliberately Swift-friendly — simple types, clear async boundaries — even if the internals use full Kotlin.
- **Coroutines across the boundary.** Suspend functions bridge to Swift as completion handlers or async/await depending on setup; decide your concurrency contract early. A shared `Flow` consumed from SwiftUI needs a small wrapper to feel native.
- **Build integration.** You'll wire the framework into Xcode (direct integration, CocoaPods, or SPM). Whichever you pick, own it — iOS developers should be able to build the app without becoming Gradle experts, and that's a documentation and tooling investment, not an afterthought.

The teams that succeed treat the iOS side as a first-class consumer with its own developer experience, not as an appendage to the Android build.

## Testing and CI

The best part of KMP is that shared logic gets tested *once* in `commonTest` and that coverage protects both platforms. Lean into it: put your business rules, mappers, and repository logic behind interfaces and test them in common code with no platform dependencies. That's where the reuse dividend is largest.

CI needs both worlds, though. A realistic pipeline:

| Stage | Runs on | Purpose |
|---|---|---|
| Common + Android unit tests | Linux runner | Fast, covers shared logic |
| Android assemble + instrumented | Linux / emulator | Android app |
| iOS framework build + tests | macOS runner | Catch Swift-interop breaks |
| iOS app build | macOS runner | Full integration |

The thing that catches teams out is skimping on the macOS side. A change that compiles fine for Android can break the iOS framework's Swift-facing API, and you only find out when an iOS dev pulls. Build the iOS framework in CI on every PR — it's the cheapest insurance against a broken shared module. This is standard [fast CI/CD](https://blog.michaelsam94.com/fast-cicd-pipelines/) hygiene, just doubled.

## Pitfalls that actually bite

From production, in rough order of how often they cause pain:

- **Over-sharing too early.** Forcing a shared abstraction before you understand both platforms' needs produces a leaky, `expect`/`actual`-riddled mess. Start by sharing the clearly-common core; expand the boundary as confidence grows.
- **Leaking platform types into common code.** A `java.time` or `NSDate` sneaking into `commonMain` breaks the whole point. Use multiplatform libraries (`kotlinx-datetime`, `kotlinx-serialization`, Ktor) and keep common code platform-agnostic.
- **Ignoring binary size and build time on iOS.** The Kotlin framework adds to app size and build time; budget for it and measure, don't assume.
- **Treating iOS devs as second-class.** If the shared module is painful to consume from Swift, iOS developers will route around it, and your reuse evaporates. Invest in the Swift-facing API.

## Would I choose it again?

For an app that needs to ship on both Android and iOS with logic that must behave identically — payments, sync, domain rules — yes, without hesitation. Sharing the data and business layers eliminated a whole category of "the two apps disagree" bugs and cut the maintenance surface meaningfully. The framework is stable and the ecosystem (Ktor, SQLDelight, kotlinx libraries) is mature.

The caveat is honest: KMP rewards teams that treat both platforms as first-class and draw the sharing boundary with discipline. It punishes teams that expect "write once, run everywhere" magic. Share the logic, respect the platforms, build iOS in CI from day one — do that and KMP is one of the better architectural bets available in 2026. If you're weighing it against the alternative, my comparison of [Flutter vs Kotlin Multiplatform](https://blog.michaelsam94.com/flutter-vs-kotlin-multiplatform/) goes deeper on the tradeoffs.

## Resources

- [Kotlin Multiplatform documentation](https://kotlinlang.org/docs/multiplatform.html)
- [Kotlin Multiplatform development guide](https://www.jetbrains.com/help/kotlin-multiplatform-dev/get-started.html)
- [expect/actual declarations](https://kotlinlang.org/docs/multiplatform-expect-actual.html)
- [Ktor multiplatform client](https://ktor.io/docs/client-create-multiplatform-application.html)
- [kotlinx.serialization](https://github.com/Kotlin/kotlinx.serialization)
- [The Kotlin Blog](https://blog.jetbrains.com/kotlin/)
