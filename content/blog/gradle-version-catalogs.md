---
title: "Gradle Version Catalogs for Multi-Module Apps"
slug: "gradle-version-catalogs"
description: "Master Gradle version catalogs for multi-module apps: centralize dependencies in libs.versions.toml, use bundles and plugin aliases, and kill version drift."
datePublished: "2026-01-24"
dateModified: "2026-01-24"
tags: ["Android", "Build", "Gradle"]
keywords: "Gradle version catalogs, libs.versions.toml, dependency management Gradle, multi-module build, version bundles"
faq:
  - q: "What are Gradle version catalogs?"
    a: "Gradle version catalogs are a built-in mechanism for declaring your dependency coordinates and versions in one central file, typically gradle/libs.versions.toml, and referencing them across every module through a type-safe generated accessor like libs.androidx.core. They replace scattered hardcoded version strings and ext blocks with a single source of truth that Gradle validates and autocompletes in the IDE."
  - q: "How is a version catalog different from a buildSrc constants file?"
    a: "A buildSrc Dependencies.kt file works but forces a full buildSrc recompilation on any change, which invalidates build caches and slows everyone down. Version catalogs are parsed as data, not compiled code, so editing a version doesn't trigger that cascade. Catalogs also generate type-safe accessors, support bundles and plugin aliases natively, and can be shared or published, which ad-hoc constants files can't do cleanly."
  - q: "What is a dependency bundle in a version catalog?"
    a: "A bundle is a named group of libraries you almost always use together, declared once in the catalog under [bundles]. Instead of listing five Compose dependencies in every module, you declare implementation(libs.bundles.compose) once. Adding a library to the bundle updates every module that uses it, which keeps related dependencies aligned across a large project."
---

If you've ever chased a bug caused by module A pulling `okhttp:4.11` while module B pulled `4.9`, you already understand why Gradle version catalogs exist. A version catalog centralizes every dependency coordinate and version into one file — conventionally `gradle/libs.versions.toml` — and exposes them across all modules through type-safe accessors like `libs.retrofit`. No more hardcoded version strings sprinkled through twenty `build.gradle` files, no more `ext` maps, no more drift. For a multi-module app, this isn't a nicety; it's the difference between dependency management being a background hum and being a recurring firefight.

I moved a fifteen-module Android app onto version catalogs a while back, and the immediate payoff was boring in the best way: one place to bump a version, IDE autocomplete for dependencies, and a build that fails fast if two modules disagree. Let me walk through how they're structured and the patterns that make them actually pay off at scale.

## The anatomy of libs.versions.toml

The file has four sections, and understanding the split is most of the battle:

```toml
[versions]
kotlin = "2.1.0"
compose-bom = "2024.12.01"
retrofit = "2.11.0"
coroutines = "1.9.0"

[libraries]
androidx-core = { module = "androidx.core:core-ktx", version = "1.15.0" }
retrofit = { module = "com.squareup.retrofit2:retrofit", version.ref = "retrofit" }
retrofit-moshi = { module = "com.squareup.retrofit2:converter-moshi", version.ref = "retrofit" }
coroutines-core = { module = "org.jetbrains.kotlinx:kotlinx-coroutines-core", version.ref = "coroutines" }

[bundles]
retrofit = ["retrofit", "retrofit-moshi"]

[plugins]
android-application = { id = "com.android.application", version = "8.7.0" }
kotlin-android = { id = "org.jetbrains.kotlin.android", version.ref = "kotlin" }
```

`[versions]` holds the numbers you reference with `version.ref`. `[libraries]` maps a human name to a coordinate. `[bundles]` groups libraries. `[plugins]` does the same for plugin IDs. The `version.ref` indirection is the important bit — declare `retrofit` once and both the core and converter artifacts stay locked together, which is exactly the kind of coupling you *want* between artifacts from the same release.

## Consuming the catalog in modules

Gradle generates a type-safe accessor (default name `libs`) from the TOML. In any module's build script:

```kotlin
plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
}

dependencies {
    implementation(libs.androidx.core)
    implementation(libs.bundles.retrofit)      // pulls retrofit + moshi converter
    implementation(libs.coroutines.core)
}
```

Notice the naming convention: dashes in the TOML key (`androidx-core`) become dots in the accessor (`libs.androidx.core`). This gives you IDE autocomplete and compile-time validation — mistype a dependency name and the build fails immediately with a clear error, instead of resolving a typo'd string to nothing. That feedback loop alone justifies the migration; I've watched juniors discover dependencies just by typing `libs.` and browsing.

## Bundles: the multi-module force multiplier

Bundles are where catalogs shine in a large project. Compose is the canonical example — every UI module needs the same handful of Compose artifacts:

```toml
[bundles]
compose = [
    "compose-ui",
    "compose-material3",
    "compose-ui-tooling-preview",
    "compose-foundation",
]
```

```kotlin
// In every UI module, one line instead of four:
implementation(platform(libs.compose.bom))
implementation(libs.bundles.compose)
```

Add a new Compose artifact to the bundle once, and every module that uses `libs.bundles.compose` picks it up. In a codebase with a dozen feature modules, that's the difference between a one-line change and a twelve-file find-and-replace. This tidiness compounds with good module boundaries — the cleaner your module graph, the more mechanical dependency management becomes, which is part of why I care so much about structure in [modular monoliths versus microservices](https://blog.michaelsam94.com/modular-monoliths-vs-microservices/): well-drawn boundaries make the wiring boring.

## Why not buildSrc constants?

The pre-catalog convention was a `buildSrc/Dependencies.kt` with `object Versions` and `object Libs`. It worked, and it's why some teams hesitate to migrate. But it has a real cost:

| Aspect | buildSrc constants | Version catalog |
| --- | --- | --- |
| Change impact | Recompiles buildSrc, invalidates cache | Parsed as data, no recompilation |
| Type safety | Manual constants | Generated accessors |
| Bundles | Hand-rolled lists | Native `[bundles]` |
| Plugin versions | Awkward | First-class `[plugins]` |
| Shareable | No clean story | Publishable / importable |

The build-cache point is the one that bites at scale. Because `buildSrc` is compiled code, editing a single version string invalidates the `buildSrc` output and cascades into cache misses across the build. A catalog is *data*, so bumping a version doesn't trigger that recompilation storm. On a large project that difference is felt on every branch switch, and it ties directly into the incremental-build discipline I cover in [faster Gradle builds](https://blog.michaelsam94.com/faster-gradle-builds/) — anything that avoids needless cache invalidation is worth doing.

## Practical patterns and gotchas

A few things I've learned running catalogs in anger:

- **Group related versions with refs.** Anything shipped as a set (Retrofit + its converters, Coroutines core + test) should share a `version.ref`. It prevents the "core is 1.9 but test is 1.8" mismatch class.
- **Reject version ranges.** Pin exact versions in the catalog. The whole point is reproducibility; a dynamic `1.+` reintroduces the drift you're trying to kill.
- **Use the built-in update check.** Rather than eyeballing versions, run a dependency-update task and review the diff deliberately, then bump refs in one commit that's easy to review and revert.
- **Keep one catalog unless you have a reason.** Gradle supports multiple catalogs, but for a single app one `libs` catalog is simpler. Reach for a second, published catalog only when multiple *separate* projects need to share versions.
- **Mind the naming rules.** Catalog aliases can't collide with reserved accessor segments; if `libs.plugins` and a library named `plugins` fight, Gradle will tell you. Name libraries after their purpose, not just their artifact.

The overarching principle: a version catalog turns dependency management from a distributed, error-prone chore into a single reviewable file. In a multi-module app that's not a small win — it removes an entire category of "works on my module" bugs and makes upgrades a deliberate, visible act rather than an archaeology project. If you're still threading version strings through individual build scripts, migrating is one of the highest-leverage build-hygiene changes you can make in an afternoon.

## Resources

- [Gradle version catalogs — official documentation](https://docs.gradle.org/current/userguide/version_catalogs.html)
- [Migrate your build to version catalogs (Android)](https://developer.android.com/build/migrate-to-catalogs)
- [Managing dependencies with Gradle](https://docs.gradle.org/current/userguide/dependency_management.html)
- [The TOML specification](https://toml.io/en/)
- [Gradle build cache](https://docs.gradle.org/current/userguide/build_cache.html)
