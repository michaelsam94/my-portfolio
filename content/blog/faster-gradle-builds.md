---
title: "Faster Gradle Builds: Version Catalogs and Caching"
slug: "faster-gradle-builds"
description: "Practical ways to speed up Android Gradle builds: version catalogs, remote and configuration cache, KSP over KAPT, and module splits — measured with Build Scan."
datePublished: "2026-04-06"
dateModified: "2026-04-09"
tags: ["Android", "Gradle", "Build Performance", "Kotlin"]
keywords: "Gradle build performance, version catalogs, build cache, Gradle configuration cache, faster builds, KSP, modularization"
faq:
  - q: "What is the single biggest win for Gradle build speed?"
    a: "For most Android projects it's enabling the configuration cache and the build cache together, then replacing KAPT with KSP. Those three changes routinely cut incremental build times by a large margin with minimal code changes."
  - q: "What are Gradle version catalogs and do they speed up builds?"
    a: "Version catalogs centralize dependency versions in a libs.versions.toml file. They don't directly speed up compilation, but they eliminate version drift across modules, which prevents redundant dependency resolution and makes multi-module builds more cacheable and maintainable."
  - q: "Is KSP really faster than KAPT?"
    a: "Yes, significantly. KAPT generates Java stubs and runs annotation processing through the Java compiler, which is slow. KSP processes Kotlin symbols directly, and libraries like Room and Hilt that support KSP build noticeably faster after migrating."
---

There's a point in every growing Android project where the build becomes the bottleneck of the whole team. A two-minute incremental build doesn't sound bad until you multiply it by every developer, every change, every day — that's real hours of engineers watching a progress bar. The good news is that most of the slowness is fixable with configuration changes, not heroic refactors. These are the Gradle changes that gave me the biggest **build performance** wins on real multi-module Android apps — including [Compose migration](https://blog.michaelsam94.com/migrating-xml-to-compose/) work where modular boundaries matter — roughly in order of effort-to-payoff.

## Turn on the caches you already paid for

Gradle ships two caches that many projects leave off. Enable both in `gradle.properties`:

```properties
org.gradle.caching=true
org.gradle.configuration-cache=true
org.gradle.parallel=true
org.gradle.jvmargs=-Xmx4g -XX:+UseParallelGC
```

The **build cache** stores task outputs keyed by their inputs, so a task whose inputs haven't changed is fetched from cache instead of re-run — locally, and across machines/CI if you wire up a remote cache. The **configuration cache** caches the result of the configuration phase itself, which on a large multi-module build can be several seconds of every single invocation. Enabling configuration caching turned "every build pays a fixed tax before doing anything" into "the tax is paid once."

Configuration caching is stricter — it will fail builds that read state at the wrong time or reference `Project` at execution time — so expect to fix a few plugins or custom tasks. It's worth it. A remote build cache on CI meant developers pulling a fresh branch downloaded compiled outputs instead of rebuilding them, cutting cold builds dramatically.

## Version catalogs: one source of truth for versions

A **version catalog** centralizes every dependency and version in `gradle/libs.versions.toml`:

```toml
[versions]
kotlin = "2.1.0"
compose-bom = "2025.06.00"
room = "2.7.0"

[libraries]
room-runtime = { module = "androidx.room:room-runtime", version.ref = "room" }
room-compiler = { module = "androidx.room:room-compiler", version.ref = "room" }
compose-bom = { module = "androidx.compose:compose-bom", version.ref = "compose-bom" }

[plugins]
ksp = { id = "com.google.devtools.ksp", version = "2.1.0-1.0.29" }
```

Modules then reference `libs.room.runtime` with IDE autocomplete and type safety. Catalogs don't compile code faster on their own, but they **eliminate version drift** across modules — the situation where module A pulls Room 2.6 and module B pulls 2.7, forcing Gradle to resolve conflicts and defeating cache reuse. In a large project, consistent versions are a prerequisite for the caches above to actually hit. They also make upgrades a one-line change instead of a find-and-replace across 40 build files.

## Replace KAPT with KSP

If your build still uses **KAPT** for Room, Hilt, Moshi, or similar, this is often the largest single compilation win. KAPT works by generating Java stubs for all your Kotlin and running annotation processing through `javac` — slow and largely redundant. **KSP** (Kotlin Symbol Processing) reads Kotlin symbols directly and skips the stub generation entirely.

```kotlin
plugins {
    alias(libs.plugins.ksp)
}
dependencies {
    ksp(libs.room.compiler) // was: kapt(...)
}
```

Room, Hilt, Moshi, and most modern processors support KSP now. Migrating is usually a matter of swapping `kapt` for `ksp` and removing the `kotlin-kapt` plugin. On one project, moving Room and Hilt off KAPT cut a chunk of time off every build that touched a database or DI change, because those changes no longer triggered the whole KAPT stub dance.

## Modularize — but for the right reason

Splitting a monolithic `app` module into feature and core modules helps builds, but only if done deliberately. The benefit is **parallelism and incrementality**: Gradle builds independent modules in parallel, and a change in one feature module doesn't recompile the others. The failure mode is a tangle of dependencies where every module depends on every other, so a change anywhere invalidates everything — you get the complexity of modules with none of the speedup.

The rule I follow:

- Keep a thin `:app` that wires modules together.
- Split by **feature** (`:feature:checkout`) and **layer** (`:core:network`, `:core:data`).
- Depend on **API modules, not implementation modules**, so changing an implementation detail doesn't recompile consumers. Use `api` vs `implementation` deliberately — `implementation` stops dependencies leaking transitively and keeps the recompilation blast radius small.

Done right, a one-line change in a leaf feature recompiles one small module instead of the whole app.

## Measure, don't guess

Before optimizing, profile. Two tools tell you where the time actually goes:

| Tool | What it shows |
| --- | --- |
| `--scan` (build scan) | Full timeline, cache hits/misses, slow tasks |
| `--profile` | HTML report of task durations per phase |
| Gradle Enterprise/Develocity | Trends across builds and developers |

Run `./gradlew assembleDebug --scan` and read the timeline. I've watched teams "optimize" a task that took 3% of the build while a misconfigured resource-merging step ate 40%. The scan points you at the real offender instead of the one you assumed.

## The habits that keep builds fast

- **Keep the AGP, Gradle, and Kotlin versions current.** Each release ships build-speed improvements; falling years behind leaves free performance on the table.
- **Avoid dynamic versions** (`1.2.+`) — they force resolution on every build and break caching. Catalogs make pinning easy.
- **Don't do work at configuration time.** Custom tasks that read files or run commands during configuration wreck the configuration cache. Move logic into task actions.
- **Use `--offline` locally** when you're not changing dependencies, to skip network checks.
- **Give the daemon enough heap** but not absurd amounts; watch for GC thrashing in the scan.

None of this is glamorous, and that's the point — a fast build is invisible. Turn on the caches, centralize versions in a catalog, get off KAPT, modularize with intent, and profile before you touch anything. Those changes compound, and the payoff is measured in engineer-hours you get back every week. If build reliability in CI is your next concern, I wrote about that in [fast CI/CD pipelines](https://blog.michaelsam94.com/fast-cicd-pipelines/).

## Resources

- [Optimize your build speed — Android guide](https://developer.android.com/build/optimize-your-build)
- [Gradle build cache](https://docs.gradle.org/current/userguide/build_cache.html)
- [Gradle configuration cache](https://docs.gradle.org/current/userguide/configuration_cache.html)
- [Version catalogs](https://docs.gradle.org/current/userguide/version_catalogs.html)
- [Kotlin Symbol Processing (KSP)](https://kotlinlang.org/docs/ksp-overview.html)
- [Build scans / Develocity](https://scans.gradle.com/)
