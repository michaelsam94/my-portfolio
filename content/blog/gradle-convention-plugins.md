---
title: "Taming Gradle with Convention Plugins"
slug: "gradle-convention-plugins"
description: "Use Gradle convention plugins to remove build-script duplication across modules: buildSrc vs build-logic, version catalogs, and consistent config in multi-module Android."
datePublished: "2024-08-07"
dateModified: "2024-08-07"
tags: ["Android", "Gradle", "Build", "Architecture"]
keywords: "Gradle convention plugins, build-logic, buildSrc convention plugin, multi-module Gradle, precompiled script plugin, version catalog"
faq:
  - q: "What is a Gradle convention plugin?"
    a: "A convention plugin is a plugin you write yourself that bundles a set of build configuration — applied plugins, compiler options, common dependencies, and shared settings — so each module can apply one plugin instead of repeating the same script. It centralizes conventions across a multi-module project so every module is configured identically and changes happen in one place."
  - q: "Should I use buildSrc or an included build-logic build for convention plugins?"
    a: "Prefer a composite build (an included build named build-logic) over buildSrc for larger projects. buildSrc invalidates the whole build when it changes and is implicitly on every classpath, whereas an included build-logic module is more isolated, gives finer control over what depends on it, and avoids some cache invalidation. buildSrc is fine for tiny projects."
  - q: "How do convention plugins work with version catalogs?"
    a: "Convention plugins can read the version catalog to apply dependencies and plugin versions consistently. You reference the catalog from the plugin code (via the extensions or a generated accessor) so a single libs.versions.toml drives both your module build files and your convention plugins, keeping versions defined in exactly one place."
---

If you have more than a handful of Gradle modules and each one repeats the same `android { }` block, the same `compileOptions`, the same test dependencies, you have a maintenance bomb waiting to go off. Convention plugins defuse it: you write a plugin that encapsulates a *convention* — "this is what an Android library module looks like here" — and every module applies that one plugin instead of copy-pasting fifty lines. I've migrated a 60-module app from duplicated build scripts to convention plugins, and the payoff wasn't just less code; it was being able to change the Kotlin compiler args or bump the target SDK for the whole repo by editing a single file.

## The problem: build-script drift

In a multi-module project without conventions, each `build.gradle.kts` tends to accumulate the same boilerplate:

```kotlin
plugins {
    id("com.android.library")
    id("org.jetbrains.kotlin.android")
}
android {
    compileSdk = 34
    defaultConfig { minSdk = 24 }
    compileOptions { /* java version */ }
    buildFeatures { compose = true }
}
dependencies { /* the same test + compose deps everywhere */ }
```

Multiply by 40 modules and every SDK bump, every compiler flag, every new lint rule is a 40-file change — and inevitably three modules drift because someone forgot one. Build-script drift is a real source of "works in module A, breaks in module B" bugs, and it makes onboarding painful because there's no single answer to "how is a module configured here?"

## What a convention plugin actually is

A convention plugin is just a `Plugin<Project>` you author that applies and configures other plugins. Instead of each module knowing the details, the module says "I am an Android library" and the plugin knows what that means:

```kotlin
// build-logic/convention/.../AndroidLibraryConventionPlugin.kt
class AndroidLibraryConventionPlugin : Plugin<Project> {
    override fun apply(target: Project) = with(target) {
        with(pluginManager) {
            apply("com.android.library")
            apply("org.jetbrains.kotlin.android")
        }
        extensions.configure<LibraryExtension> {
            compileSdk = 34
            defaultConfig { minSdk = 24 }
            // shared compileOptions, lint, etc.
        }
        dependencies {
            add("testImplementation", libs.findLibrary("junit").get())
        }
    }
}
```

Register it with an id in the plugin's build file, and a module's script collapses to:

```kotlin
plugins {
    id("myapp.android.library")
}
```

That's the whole idea. The knowledge of *how* an Android library is built lives in one Kotlin class; modules just declare *what* they are.

## build-logic vs buildSrc

There are two homes for this code, and the choice matters at scale.

- **`buildSrc`** is the classic spot. It's implicitly on every project's build classpath and easy to start with. The downside: a change to anything in `buildSrc` invalidates the entire build's configuration and can bust caches broadly, which hurts on big repos.
- **An included build named `build-logic`** (a composite build, wired via `includeBuild("build-logic")` in `settings.gradle.kts`) is more isolated. It's a real Gradle build that produces plugins, you control precisely which projects consume it, and it plays better with the build cache and [configuration cache](https://blog.michaelsam94.com/gradle-configuration-cache/).

For anything beyond a toy project I use `build-logic`. It's the pattern the Now in Android sample popularized, and the isolation is worth the small extra setup. `buildSrc` is fine for a single-module or two-module repo where the invalidation cost is irrelevant.

## Compose the conventions, don't monolith them

The trap is writing one giant `AndroidConventionPlugin` that tries to configure everything. Better to make small, composable plugins and layer them:

- `myapp.android.library` — base Android library config.
- `myapp.android.library.compose` — applies the library plugin *and* adds Compose setup.
- `myapp.android.feature` — feature-module conventions (navigation, common feature deps) on top of the library plugin.
- `myapp.jvm.library` — pure Kotlin/JVM modules with no Android.
- `myapp.android.hilt` / `myapp.android.test` — opt-in slices.

A feature module then reads like a description of itself:

```kotlin
plugins {
    id("myapp.android.feature")
    id("myapp.android.library.compose")
    id("myapp.android.hilt")
}
```

Each plugin does one job; modules mix them. This mirrors the same [modularization discipline](https://blog.michaelsam94.com/android-modularization-strategy/) you apply to the app itself — small, focused units you combine — applied to the build logic.

## Wire in the version catalog

Convention plugins and version catalogs are a natural pair: the catalog is the single source of versions, and the plugin applies them so modules don't hardcode anything. Inside `build-logic` you access the catalog via the `VersionCatalogsExtension`:

```kotlin
val libs = extensions.getByType<VersionCatalogsExtension>().named("libs")
dependencies {
    add("implementation", libs.findLibrary("kotlinx.coroutines.core").get())
}
```

Now a coroutines bump is one line in `libs.versions.toml`, and it flows to every module through the convention plugin. Versions live in exactly one place, plugin ids and their versions included.

## What you get, concretely

After migrating, the wins showed up fast:

1. **Global changes are one-file changes.** Target SDK bump, new compiler arg, new lint baseline — edit the plugin, done everywhere.
2. **No drift.** Every module of a given type is provably configured identically because they share the same code path.
3. **Readable module files.** A module's `build.gradle.kts` becomes a short declaration of identity plus its unique dependencies — you can actually see what's special about it.
4. **Faster onboarding.** "How do I make a new feature module?" has a one-line answer.

The cost is real but small: a little upfront Kotlin, and developers need to know the conventions exist rather than reading everything inline. Document the available plugin ids in a README next to `build-logic` so nobody reinvents a convention that already exists.

## What I'd take away

Convention plugins turn Gradle from a pile of duplicated scripts into a small, typed system where modules declare what they are and shared logic lives in one place. Put that logic in an included `build-logic` build rather than `buildSrc` for anything non-trivial, keep the plugins small and composable instead of one monolith, and drive all versions through a single version catalog the plugins read. Do that and repo-wide build changes stop being 40-file chores and drift-induced "works here, breaks there" bugs largely disappear.

## Resources

- [Sharing build logic with convention plugins (Gradle)](https://docs.gradle.org/current/userguide/sharing_build_logic_between_subprojects.html)
- [Developing custom Gradle plugins](https://docs.gradle.org/current/userguide/custom_plugins.html)
- [Gradle version catalogs](https://docs.gradle.org/current/userguide/platforms.html)
- [Now in Android — build-logic conventions](https://github.com/android/nowinandroid/tree/main/build-logic)
- [Composite builds](https://docs.gradle.org/current/userguide/composite_builds.html)
