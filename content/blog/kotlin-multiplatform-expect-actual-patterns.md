---
title: "expect/actual Patterns That Scale in Kotlin Multiplatform"
slug: "kotlin-multiplatform-expect-actual-patterns"
description: "How to use Kotlin Multiplatform expect/actual well: when to reach for it, when interfaces beat it, and the patterns that keep platform code from sprawling."
datePublished: "2024-09-20"
dateModified: "2024-09-20"
tags: ["Kotlin", "Kotlin Multiplatform", "Architecture", "Android"]
keywords: "expect actual Kotlin, Kotlin Multiplatform expect actual, KMP platform code, expect class, actual typealias"
faq:
  - q: "When should I use expect/actual instead of an interface?"
    a: "Use expect/actual when the API surface must be identical across platforms and there's exactly one implementation per target, like a platform clock or a UUID generator. Reach for a plain interface with per-platform bindings when you want dependency injection, multiple implementations, or easier testing. In practice most large KMP codebases lean on interfaces for the bulk of their code and keep expect/actual for a small set of true platform primitives."
  - q: "Can expect declarations have default implementations?"
    a: "An expect function cannot have a body, but since Kotlin 1.7+ you can give an expect function a default and only override it on the platforms that need to. You can also express platform variation as an expect typealias pointing at an existing platform type, which avoids writing a wrapper class entirely. Both keep the common code lean."
  - q: "Why does my actual declaration fail to compile with a visibility error?"
    a: "The actual declaration must match the expect signature exactly — same name, parameters, return type, and visibility. A common trap is adding a parameter default on the actual side or changing visibility from internal to public. Keep defaults and annotations on the expect side and mirror the signature precisely on each actual."
---

`expect`/`actual` is the mechanism Kotlin Multiplatform gives you to declare an API in common code and supply a platform-specific implementation per target. It's the first thing everyone learns and, in my experience, the first thing everyone overuses. I've reviewed KMP modules where half the shared code was `expect` declarations, each with three near-identical `actual` bodies, and the whole thing was harder to test than the platform code it replaced. The mechanism is fine — the discipline around it is what scales or doesn't.

The mental model that helped me: `expect`/`actual` is a *compile-time* substitution, resolved when the compiler builds a specific target. It is not dependency injection, it has no runtime polymorphism, and it can't do more than one implementation per platform. Once you internalize that, you stop reaching for it to solve problems it was never meant to solve.

## The three forms, and which one to prefer

There isn't one `expect`/`actual`. There are several, and picking the lightest one that works keeps the code readable.

```kotlin
// common
expect fun currentTimeMillis(): Long

// androidMain
actual fun currentTimeMillis(): Long = System.currentTimeMillis()

// iosMain
import platform.Foundation.NSDate
actual fun currentTimeMillis(): Long =
    (NSDate().timeIntervalSince1970 * 1000).toLong()
```

That's an `expect fun`, and for small platform primitives it's the cleanest option. The next step up is an `expect class`, which you should use sparingly because it forces you to mirror the *entire* class shape on every target. The one I reach for most often is the one people forget exists — the `expect`/`actual typealias`:

```kotlin
// common
expect class PlatformFile

// jvmMain
actual typealias PlatformFile = java.io.File
```

The typealias form lets you point common code at an existing platform type without writing a wrapper. When a mature platform type already does the job, aliasing it beats hand-rolling an `actual class` that just delegates to it.

## Prefer interfaces for anything with logic

Here's the opinion that saves teams the most pain: `expect`/`actual` should wrap *platform primitives*, not *your business logic*. If a thing has branching, state, or anything you'd want to unit test, model it as an interface in common code and provide platform bindings.

```kotlin
// common
interface Analytics {
    fun track(event: String, props: Map<String, Any?>)
}

// common — a factory expect is a lot smaller than an expect class
expect fun createAnalytics(): Analytics
```

Now the common code depends on an *interface* it can fake in tests, and the only `expect` is a tiny factory. The difference matters at scale: interfaces give you constructor injection, multiple implementations (real, fake, no-op for tests), and a seam you can mock. `expect class` gives you none of that — you can't substitute an `actual class` in a test because the compiler already picked it for the target. I've seen teams paint themselves into a corner by putting a stateful cache behind `expect class`, then discover they can't test the common logic in isolation. The same separation-of-concerns instinct that shapes a good [KMP testing strategy](https://blog.michaelsam94.com/kotlin-multiplatform-testing-strategy/) applies here.

## Keep the common signature honest

The signature you write in `expect` is a contract every platform must satisfy *identically*. Two rules keep it from leaking:

1. **Put defaults and annotations on the `expect` side.** If an argument has a default value, declare it in the `expect` and leave it off the `actual`. Doing it the other way around either fails to compile or, worse, silently gives platforms different defaults.
2. **Don't leak platform types into the common signature.** The whole point is that common callers see a common API. If your `expect fun` returns a `java.io.File`, you've broken the abstraction the moment you add an iOS target.

When those rules feel constraining, it's usually a sign the thing should be an interface, not an `expect`.

## A pattern for platform config

A recurring need is per-platform constants and configuration — API base URLs, feature flags defaults, platform names. `expect`/`actual` handles this cleanly without a class:

```kotlin
// common
expect val platformName: String
expect val isDebugBuild: Boolean

// androidMain
actual val platformName: String = "Android ${android.os.Build.VERSION.SDK_INT}"
actual val isDebugBuild: Boolean = BuildConfig.DEBUG
```

Expect properties are underused and perfect for this. They keep configuration in shared code with a single source of truth, while each platform supplies the one value it knows.

## Where it interacts with the build

`expect`/`actual` is resolved per source set, so the structure of your source sets *is* the structure of your platform code. A hierarchical source set — say an `appleMain` shared between `iosMain` and `macosMain` — lets you write one `actual` for all Apple targets instead of copy-pasting. This is one of the biggest quality-of-life wins in modern KMP: put the `actual` at the highest source set that can satisfy it, and let the more specific targets inherit. If your iOS and macOS `actual`s are byte-for-byte identical, they belong in `appleMain`, not duplicated in each.

## What I'd take away

`expect`/`actual` is a scalpel, not a hammer. Use it for genuine platform primitives — clocks, file handles, UUIDs, platform config — and prefer the lightest form: `expect fun` or `expect typealias` over `expect class`. Model anything with logic or state as a common interface with platform bindings so you keep testability and injection. Keep defaults and annotations on the `expect` side, never leak platform types into common signatures, and hoist shared `actual`s into intermediate source sets. Follow that and your shared module stays a shared module — not a pile of parallel platform code wearing a common coat.

## Resources

- [Kotlin Multiplatform — expect and actual declarations](https://kotlinlang.org/docs/multiplatform-expect-actual.html)
- [Hierarchical project structure](https://kotlinlang.org/docs/multiplatform-hierarchy.html)
- [Kotlin Multiplatform overview](https://kotlinlang.org/docs/multiplatform.html)
- [Sharing code in Kotlin Multiplatform](https://kotlinlang.org/docs/multiplatform-share-on-platforms.html)
