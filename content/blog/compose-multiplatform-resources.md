---
title: "Resources and Localization in Compose Multiplatform"
slug: "compose-multiplatform-resources"
description: "Compose Multiplatform resources: sharing strings, images, and fonts across Android, iOS, desktop, and web, plus localization, plurals, and the gotchas."
datePublished: "2026-02-23"
dateModified: "2026-02-23"
tags: ["Kotlin Multiplatform", "Jetpack Compose", "Localization"]
keywords: "Compose Multiplatform resources, compose-resources, shared strings, multiplatform assets, i18n CMP"
faq:
  - q: "What is the compose-resources library?"
    a: "compose-resources is the official Compose Multiplatform library for bundling and accessing shared resources — strings, images, fonts, and raw files — from common Kotlin code across Android, iOS, desktop, and web. It generates a type-safe Res accessor so you reference resources by compiled identifier instead of raw strings, and it handles platform-specific packaging under the hood."
  - q: "How does localization work in Compose Multiplatform?"
    a: "You place translated strings in per-locale values folders (values-fr, values-ar, and so on) inside your commonMain resources, exactly like Android's structure. At runtime the library resolves the active locale and returns the matching string via stringResource(). Plurals, formatted arguments, and right-to-left languages are all supported from shared code."
  - q: "Can I share images and fonts across platforms with Compose Multiplatform?"
    a: "Yes. Drawable images, custom fonts, and arbitrary files placed in the shared resources directory are accessible from common code through generated accessors like painterResource() and Font(). The library packages them appropriately for each target, so one asset set serves Android, iOS, desktop, and web without per-platform duplication."
---

The promise of Compose Multiplatform falls apart fast if you can't share your resources. UI code that compiles once but needs per-platform copies of every string, icon, and font isn't really shared — it's shared logic wrapped around duplicated assets. Compose Multiplatform resources, delivered through the `compose-resources` library, close that gap: you put strings, images, fonts, and files in one place in `commonMain`, and a generated `Res` object gives you type-safe access from shared code that runs on Android, iOS, desktop, and web.

I've shipped this across a couple of KMP apps, and the resource story matured a lot faster than I expected. It borrows Android's mental model almost wholesale, which means most Android developers are productive on day one — but there are enough platform-specific edges to be worth mapping out before you commit.

## Where resources live

Everything goes under a `composeResources` directory in your shared module, organized by type:

```
commonMain/
  composeResources/
    drawable/
      logo.xml
      empty_state.png
    font/
      inter_regular.ttf
    values/
      strings.xml
    values-ar/
      strings.xml
    files/
      onboarding.json
```

If you've done Android development, this is immediately familiar — `drawable`, `font`, `values`, and locale-qualified variants. The build generates a `Res` class exposing each entry, so a renamed or deleted resource becomes a compile error instead of a runtime crash. That single property — compile-time safety across four platforms — is the reason to use the library rather than hand-rolling per-platform loaders.

## Reading resources in common code

Accessors are `@Composable` and suspend-aware because loading an asset can be async on some targets. Strings, drawables, and fonts each have a matching function:

```kotlin
Text(text = stringResource(Res.string.welcome_title))

Image(
    painter = painterResource(Res.drawable.logo),
    contentDescription = null,
)

val inter = FontFamily(
    Font(Res.font.inter_regular, weight = FontWeight.Normal),
)
```

The generated identifiers (`Res.string.welcome_title`) are the whole point. No stringly-typed `"welcome_title"` lookups, no chance of referencing a resource that only exists on one platform. It's the same type-safety argument I make for shared data in [a shared data layer with Room and KMP](https://blog.michaelsam94.com/shared-data-layer-room-kmp/) — push correctness into the compiler wherever the toolchain lets you.

## Localization that actually scales

Translations live in locale-qualified `values` folders, and `stringResource` resolves the active locale automatically. Formatted arguments and plurals both work from shared code:

```kotlin
// strings.xml
// <string name="items_selected">%1$d items selected</string>
Text(stringResource(Res.string.items_selected, count))

// Plurals resolve by quantity
Text(pluralStringResource(Res.plurals.new_messages, count, count))
```

Plurals matter more than teams expect. English has two forms (one/other); Arabic has six. If you concatenate a number with a hardcoded suffix, you'll produce grammatically broken text in half your target languages. The plurals API pushes that complexity into the resource files where translators can handle it correctly, which is exactly where it belongs.

## Right-to-left and locale overrides

Because I build for the Middle East, RTL is not an afterthought for me. Compose's layout system mirrors automatically when the locale is RTL, and `LocalLayoutDirection` lets you inspect or override it. The traps are the usual ones: hardcoded `start`/`end` padding is fine, but hardcoded `left`/`right` is a bug waiting for an Arabic user, and directional icons (back arrows, chevrons) need mirroring you have to opt into.

For in-app language switching — a feature users in multilingual regions genuinely want — you can override the resolved locale rather than relying solely on the system setting. That decouples app language from device language, which is the behavior most global apps actually need.

## What differs per platform

The abstraction is good, but it isn't perfect, and pretending otherwise wastes your afternoon. Here's the honest breakdown of where platforms diverge:

| Concern | Android | iOS | Desktop | Web |
|---|---|---|---|---|
| Packaging | APK assets | Bundle | Jar/resources | Wasm resource fetch |
| Async loading | Sync-ish | Sync | Sync | Genuinely async |
| Font formats | ttf/otf | ttf/otf | ttf/otf | ttf/otf/woff |
| System locale API | Configuration | NSLocale | JVM Locale | navigator.language |

Web is the outlier: resources are fetched over the network in the Wasm target, so a large image set affects load time in a way it never does on native. Budget your asset sizes for the web target specifically, and consider lazy-loading heavy drawables. On native, loading is effectively instant and you won't notice.

The font situation deserves a specific callout. On the JVM and native targets you can bundle `ttf`/`otf` and be done, but on web, `woff2` is dramatically smaller over the wire, so I keep a web-optimized font variant and let the build pick the right one per target. It's a small amount of configuration that pays back on every page load, and it's the kind of platform-specific tuning that only matters once you're actually shipping the web build to real users rather than just running it in debug.

## Practical gotchas

A few things that cost me time so they don't cost you:

- **Resource generation lag.** After adding a resource, you sometimes need a Gradle sync before the `Res` accessor appears. If the IDE claims `Res.string.foo` doesn't exist, sync before you debug.
- **Large binaries.** The library bundles files into the artifact; don't dump a video into `composeResources` and expect a small app. Use it for genuine app resources, not a CDN replacement.
- **Preview support.** IDE previews resolve `commonMain` resources, but occasionally a platform-specific preview needs the resource present in that source set — worth checking if a preview renders blank.

None of these are dealbreakers. They're the normal texture of a cross-platform toolchain, and they're far cheaper than the per-platform resource duplication they replace. If you're weighing the broader tradeoffs of going multiplatform at all, I laid out the production realities in [the Kotlin Multiplatform production guide](https://blog.michaelsam94.com/kotlin-multiplatform-production-guide/) — the resource system is one of the parts that's genuinely ready.

The short verdict: Compose Multiplatform resources deliver on the shared-asset promise that makes the whole "share the UI" pitch credible. Strings, images, fonts, plurals, and locales from one source set, type-safe, across four platforms. Mind the web target's async loading and asset budget, respect RTL from the start, and it mostly gets out of your way.

## Resources

- [Compose Multiplatform resources documentation](https://www.jetbrains.com/help/kotlin-multiplatform-dev/compose-multiplatform-resources.html)
- [Kotlin Multiplatform documentation](https://kotlinlang.org/docs/multiplatform.html)
- [Compose Multiplatform on GitHub](https://github.com/JetBrains/compose-multiplatform)
- [Android app resources overview](https://developer.android.com/guide/topics/resources/providing-resources)
- [Unicode CLDR plural rules](https://cldr.unicode.org/index/cldr-spec/plural-rules)
