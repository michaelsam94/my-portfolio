---
title: "Compose Multiplatform: Sharing UI Across Platforms"
slug: "compose-multiplatform-shared-ui"
description: "A field guide to Compose Multiplatform for shared UI across Android, iOS, and desktop — what to share, how iOS interop works, and where the sharp edges still are."
datePublished: "2026-03-27"
dateModified: "2026-03-27"
tags: ["Compose Multiplatform", "Kotlin", "iOS", "Cross-Platform"]
keywords: "Compose Multiplatform, CMP, shared UI, Compose iOS, cross-platform UI, Kotlin UI, Kotlin Multiplatform"
faq:
  - q: "Is Compose Multiplatform production-ready on iOS?"
    a: "Yes — Compose Multiplatform for iOS reached stable in 2025, and it renders through Skia via a Metal-backed surface. It is production-ready for most app UI, though deeply platform-specific screens and heavy native interop still deserve careful testing on real devices."
  - q: "What's the difference between Kotlin Multiplatform and Compose Multiplatform?"
    a: "Kotlin Multiplatform (KMP) shares non-UI code — business logic, networking, data layers. Compose Multiplatform builds on KMP to also share the UI layer using Jetpack Compose. You can use KMP without CMP, but CMP always runs on top of KMP."
  - q: "Can I mix Compose Multiplatform with native SwiftUI or UIKit?"
    a: "Yes. On iOS you can embed a Compose UI inside a UIViewController and, going the other way, host UIKit or SwiftUI views inside Compose via UIKitView and UIKitViewController interop. Most teams share the bulk of screens and drop to native for a few."
---

The pitch for Compose Multiplatform (CMP) is simple: write your UI once in Kotlin and Jetpack Compose, then run it on Android, iOS, desktop, and web. After a decade shipping Android and leading cross-platform work, I treat that pitch with the skepticism it deserves — "write once, run anywhere" has burned mobile teams before. But CMP is a genuinely different proposition than the JavaScript-bridge frameworks, because on Android it *is* the native UI toolkit, and on iOS it renders the same Compose tree through Skia. This post is about what to actually share, how the iOS story holds up, and the sharp edges that are still real in 2026.

## What Compose Multiplatform actually is

CMP is JetBrains' extension of Google's Jetpack Compose to non-Android targets, sitting on top of [Kotlin Multiplatform](https://blog.michaelsam94.com/kotlin-multiplatform-production-guide/). The mental model that keeps teams sane: KMP shares your logic, CMP shares your UI. You can adopt KMP alone — a shared `data` and `domain` module feeding separate native UIs — and many teams should start exactly there before committing to shared UI.

On Android, CMP compiles to the same Jetpack Compose you already ship; there is no translation layer. On iOS, the Compose runtime draws to a Skia canvas backed by a Metal surface inside a `UIViewController`. On desktop it runs on the JVM with Skia; on web it targets WebAssembly with a canvas renderer. The important consequence: your UI looks pixel-identical across platforms because the same renderer draws it — which is both the feature and, occasionally, the problem.

## What to share, and what to leave native

The decision I keep coming back to is *share the boring, keep the special native*. Concretely, on real projects:

- **Share:** design-system components, list screens, forms, settings, detail screens, most navigation. This is the 80% that is genuinely identical business UI.
- **Keep native or interop:** maps, camera, deeply platform-idiomatic navigation, complex text editing, biometrics UI, and anything where an OS update changes behavior overnight.

```kotlin
// commonMain — one composable, both platforms
@Composable
fun ChargerCard(charger: Charger, onClick: () -> Unit) {
    Card(onClick = onClick, modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Text(charger.name, style = MaterialTheme.typography.titleMedium)
            Text("${charger.availableConnectors} available",
                style = MaterialTheme.typography.bodyMedium)
        }
    }
}
```

For platform-specific pieces, `expect`/`actual` is the workhorse. Declare the contract in `commonMain` and implement it per target:

```kotlin
// commonMain
@Composable expect fun MapView(location: LatLng, modifier: Modifier)

// androidMain
@Composable actual fun MapView(location: LatLng, modifier: Modifier) {
    AndroidView(factory = { MapViewImpl(it) }, modifier = modifier)
}

// iosMain — bridge to MapKit via UIKitViewController
```

## The iOS interop story

The question every skeptic asks: what about iOS look-and-feel? CMP ships a Material design system that works everywhere, and there is also a Cupertino-flavored component set for teams that want iOS-native affordances. In practice I've shipped with Material-3 styling across both platforms and users didn't blink — the areas that matter most are scroll physics and text, both of which CMP handles well now.

Where it counts is interop. Embedding Compose in an existing iOS app is a `ComposeUIViewController`:

```kotlin
// iosMain
fun MainViewController(): UIViewController =
    ComposeUIViewController { App() }
```

Then in Swift you present it like any other view controller, which makes incremental adoption realistic — you don't rewrite the iOS app, you slot Compose screens in one at a time. Going the other direction, `UIKitView` and `UIKitViewController` let you host a native `MKMapView` or a SwiftUI view inside a Compose layout. That two-way door is what makes CMP pragmatic rather than all-or-nothing.

## Sharp edges I still budget for

Honesty matters more than enthusiasm here. Things that still cost time in 2026:

| Area | Reality |
| --- | --- |
| iOS text input | Much improved, but complex IME and autofill still need device testing |
| Accessibility | Works, but audit VoiceOver behavior explicitly — it's not free |
| App size | CMP adds a few MB to the iOS binary from the Skia/runtime payload |
| Debug tooling | Android tooling is first-class; iOS debugging leans on Xcode + logs |
| Ecosystem | Fewer ready-made components than pure SwiftUI; you build more yourself |

None of these are dealbreakers, but they're the difference between a demo and a shipped app. Budget real device-testing time on iOS specifically — the "it renders identically" promise means bugs are usually logic or interop, not rendering, which actually makes them easier to reason about.

## How I'd start today

If I were greenfielding a cross-platform app now, the sequence would be: stand up a KMP project with a shared `data`/`domain` layer first, prove the networking and persistence work on both platforms, then introduce a shared `ui` module for the highest-duplication screens. Resist sharing navigation on day one; get a few leaf screens solid, measure the iOS build and binary, and expand from there. If your team is Android-heavy, this leverages skills you already have — the Compose knowledge transfers completely, which for a Kotlin shop is the real cost saving. Pair it with what you learn about state management from the [Riverpod vs Bloc discussion](https://blog.michaelsam94.com/flutter-riverpod-state-management/) if you're also weighing Flutter.

Compose Multiplatform isn't magic and it isn't "write once, forget." It's a very good way for a Kotlin team to ship the same UI to Android and iOS while keeping a native escape hatch for the parts that deserve one.

## Resources

- [Compose Multiplatform overview](https://www.jetbrains.com/compose-multiplatform/)
- [Compose Multiplatform documentation](https://www.jetbrains.com/help/kotlin-multiplatform-dev/compose-multiplatform.html)
- [Kotlin Multiplatform docs](https://kotlinlang.org/docs/multiplatform.html)
- [Jetpack Compose](https://developer.android.com/jetpack/compose)
- [iOS integration guide](https://www.jetbrains.com/help/kotlin-multiplatform-dev/compose-swiftui-integration.html)
- [KMP samples on GitHub](https://github.com/JetBrains/compose-multiplatform)

*Weighing Compose Multiplatform for a cross-platform build? [Get in touch](https://michaelsam94.com/) — I've shipped it in production.*
