---
title: "KMP with CocoaPods and Swift Package Manager"
slug: "kotlin-multiplatform-cocoapods-spm"
description: "How to ship a Kotlin Multiplatform framework to iOS via CocoaPods or Swift Package Manager: the tradeoffs, setup, and the integration that scales best."
datePublished: "2024-09-21"
dateModified: "2024-09-21"
tags: ["Kotlin", "Kotlin Multiplatform", "iOS", "Android"]
keywords: "KMP CocoaPods, Kotlin Multiplatform SPM, XCFramework, Kotlin iOS framework, kotlin cocoapods plugin"
faq:
  - q: "Should I use CocoaPods or Swift Package Manager for a KMP framework?"
    a: "If your iOS app is already on SPM and your KMP module has no transitive Pod dependencies, ship an XCFramework consumed via SPM — it's the direction Apple and the tooling are converging on. Use the CocoaPods integration when your shared module needs to pull in Objective-C or C Pods, since the CocoaPods plugin resolves those cinterop dependencies for you. Many teams start on CocoaPods for convenience and migrate to a prebuilt XCFramework once the framework stabilizes."
  - q: "What is an XCFramework and why does KMP produce one?"
    a: "An XCFramework is Apple's bundle format that packages a binary for multiple architectures and platforms — device arm64, simulator arm64, and simulator x86_64 — in one artifact. KMP produces one so a single framework works on real devices and simulators without slicing. Both the SPM and CocoaPods paths ultimately hand Xcode an XCFramework."
  - q: "Why is my Kotlin framework huge or slow to build for iOS?"
    a: "Debug frameworks are large because they include full debug info and aren't optimized; that's expected. For CI and release, build the release XCFramework and consider producing it once and caching it rather than rebuilding on every iOS build. Linking the framework statically vs dynamically also changes app size and launch cost, so measure both."
---

Getting Kotlin Multiplatform code into an iOS app comes down to one question: how does Xcode consume the framework the Kotlin compiler produces? There are two supported answers — the CocoaPods integration built into the Kotlin Gradle plugin, and shipping an XCFramework consumed through Swift Package Manager. I've shipped both, and the choice is less about religion and more about what your shared module *depends on* and where your iOS team already lives.

The short version: if your shared module needs Objective-C Pods, use CocoaPods. If it's self-contained and your iOS app is on SPM, build an XCFramework and consume it through a Swift package. Everything else is detail — but the detail is where builds break, so let me walk through both.

## What the Kotlin compiler actually gives you

Whatever integration you pick, the underlying artifact is a `.framework` per architecture, and for real distribution an **XCFramework** that bundles device and simulator slices together. Xcode can't consume a raw multi-arch `.framework` cleanly for both device and simulator; the XCFramework format exists precisely to carry `ios-arm64` and `ios-arm64_x86_64-simulator` in one package. So no matter the path, you're feeding Xcode an XCFramework. CocoaPods and SPM are just two delivery mechanisms for it.

## CocoaPods: convenient, and mandatory for Pod dependencies

The `kotlin("native.cocoapods")` plugin generates a podspec for your shared module and wires it into your iOS project's `Podfile`. The reason to use it isn't laziness — it's that if your Kotlin code needs to `cinterop` with an Objective-C Pod (say a vendor SDK distributed only as a Pod), the CocoaPods plugin is what resolves and links that dependency.

```kotlin
kotlin {
    cocoapods {
        version = "1.0.0"
        summary = "Shared KMP module"
        homepage = "https://example.com"
        ios.deploymentTarget = "15.0"
        framework {
            baseName = "Shared"
            isStatic = true
        }
        // pull an Objective-C Pod into cinterop
        pod("FirebaseAnalytics") {
            version = "~> 10.0"
        }
    }
}
```

On the iOS side, your `Podfile` references the generated podspec by path, and `pod install` links it. The tradeoff: you've now coupled your iOS build to CocoaPods and its `pod install` step, which many iOS teams are actively trying to leave. And every iOS engineer building the app rebuilds the Kotlin framework from source unless you cache it.

## SPM: the direction of travel

If your shared module has no Pod dependencies, the cleaner long-term path is to build the XCFramework yourself and distribute it as a binary target in a Swift package. You produce the artifact with a Gradle task and reference it from a `Package.swift`.

```kotlin
// build.gradle.kts
kotlin {
    val xcf = XCFramework("Shared")
    listOf(iosArm64(), iosSimulatorArm64()).forEach {
        it.binaries.framework {
            baseName = "Shared"
            xcf.add(this)
        }
    }
}
```

Then a Swift package points at the built (or hosted) XCFramework:

```swift
// Package.swift
.binaryTarget(
    name: "Shared",
    path: "./build/XCFrameworks/release/Shared.xcframework"
)
```

Two things make this scale. First, the iOS app depends on a *binary*, so iOS engineers who never touch Kotlin don't rebuild it — they consume a prebuilt artifact, which is a huge CI and local-build win. Second, you can host the XCFramework (with a checksum) and version it like any other dependency, decoupling the iOS release cadence from the Kotlin build. The cost is that *you* now own the build-and-publish step, which is where a bit of CI plumbing earns its keep — the same discipline as [generating build artifacts reliably in CI](https://blog.michaelsam94.com/android-baseline-profiles-ci/).

## Static vs dynamic, and why it matters

Both paths let you choose `isStatic = true` or dynamic linking, and it's not a throwaway flag. A static framework links into the app binary — fewer dylibs to load, faster launch, but the code is duplicated if multiple modules embed it. A dynamic framework is loaded at runtime and shared, at some launch cost. For a single shared module consumed by one app, static is usually the right default. Measure app size and cold launch both ways before you commit; I've seen a switch to static shave measurable milliseconds off launch on older devices.

## A decision table

| Situation | Use |
| --- | --- |
| Shared module depends on Objective-C Pods | CocoaPods integration |
| iOS app already fully on SPM, self-contained shared module | XCFramework + SPM |
| iOS engineers rarely touch Kotlin | Prebuilt XCFramework (SPM), cache the binary |
| Rapid early iteration, one repo | CocoaPods for convenience, migrate later |
| Distributing to multiple app teams | Hosted, versioned XCFramework |

## The migration path I recommend

Start wherever gets you moving — often CocoaPods, because it's the least Gradle-and-Xcode plumbing up front. But architect as if you'll move to a prebuilt XCFramework: keep the shared module free of Pod dependencies where you can, keep the public API surface small and Swift-friendly, and script the XCFramework build early even if you don't distribute it yet. When the shared module stabilizes and iOS build times start hurting because everyone rebuilds Kotlin, flipping to a hosted binary XCFramework consumed via SPM is a contained change rather than a rewrite.

The framework format is the same underneath; you're really choosing who builds it and how often. Push that toward "built once, consumed as a binary" and iOS builds stay fast as the team grows.

Pin Kotlin Native version to Xcode compatibility matrix — KMP iOS builds break on every major Xcode release without alignment.

## Resources

- [Kotlin Multiplatform — CocoaPods overview and setup](https://kotlinlang.org/docs/native-cocoapods.html)
- [Building a multiplatform library for XCFramework](https://kotlinlang.org/docs/multiplatform-build-native-binaries.html)
- [Apple — Creating a Swift package with an XCFramework](https://developer.apple.com/documentation/xcode/creating-a-multi-platform-binary-framework-bundle)
- [Kotlin/Native interop with Swift/Objective-C](https://kotlinlang.org/docs/native-objc-interop.html)
