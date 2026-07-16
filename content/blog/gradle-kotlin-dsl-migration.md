---
title: "Migrating Gradle to the Kotlin DSL"
slug: "gradle-kotlin-dsl-migration"
description: "Migrate Gradle build scripts from Groovy to the Kotlin DSL: type-safe accessors, version catalogs, common conversion pitfalls, and a low-risk incremental strategy."
datePublished: "2024-08-12"
dateModified: "2024-08-12"
tags: ["Gradle", "Kotlin", "Build", "Android"]
keywords: "Gradle Kotlin DSL migration, build.gradle.kts, Groovy to Kotlin Gradle, type-safe accessors, settings.gradle.kts, version catalog"
faq:
  - q: "Is the Gradle Kotlin DSL worth migrating to from Groovy?"
    a: "For most Android and Kotlin projects, yes. The Kotlin DSL gives you type safety, IDE auto-completion, refactoring, and click-through navigation into plugin APIs, which catches build-script errors at edit time instead of at build time. The trade-offs are slightly slower first-time script compilation and a stricter syntax, but the tooling gains usually outweigh them for teams already writing Kotlin."
  - q: "Can I mix Groovy and Kotlin DSL build files in one project?"
    a: "Yes. Gradle lets each module choose build.gradle (Groovy) or build.gradle.kts (Kotlin) independently, so you can migrate module by module. This makes an incremental migration safe: convert the settings file and one leaf module first, verify, then work outward rather than rewriting every script at once."
  - q: "What breaks most often when converting Groovy Gradle scripts to Kotlin?"
    a: "The frequent breakages are string quoting (Kotlin requires double quotes), method-call syntax needing parentheses and named arguments, property assignment using = instead of space syntax, and dynamic Groovy features that don't exist in Kotlin. Task configuration also differs — you often need tasks.named or the typed configure APIs instead of Groovy's dynamic task access."
---

Migrating Gradle build scripts to the Kotlin DSL trades Groovy's forgiving dynamism for type safety, real autocomplete, and click-through navigation into plugin APIs — and for a team already writing Kotlin all day, that trade is almost always worth it. The single best decision I made doing this on a multi-module app was to migrate *incrementally*, one module at a time, because Gradle happily mixes `build.gradle` and `build.gradle.kts` in the same project. Big-bang rewrites of every script at once are how you spend a weekend bisecting a broken build. Convert the settings file and a leaf module, verify, and work outward.

## Why bother

Groovy build scripts are convenient until they're not. They fail at *build* time with stringly-typed errors, offer weak IDE help, and let typos slip through as silent no-ops (a misspelled Groovy method often just gets swallowed). The Kotlin DSL flips that:

- **Type safety and autocomplete.** The IDE knows `android { }` is a `BaseAppModuleExtension` and completes its members. Typos are compile errors in the script, caught as you type.
- **Navigation and refactoring.** Ctrl-click from `implementation(...)` into the actual API. Rename a helper and the IDE updates call sites.
- **Consistency.** Your build is Kotlin like the rest of the codebase, so convention-plugin logic and build scripts share a language and mental model.

The costs are honest but modest: Kotlin scripts compile a bit slower the first time (mitigated by caching), and the syntax is stricter, which is exactly what surfaces the errors Groovy hid.

## The incremental strategy

The migration order that minimizes risk:

1. **`settings.gradle` → `settings.gradle.kts` first.** It's small, high-leverage, and establishes the version catalog and module includes in Kotlin.
2. **Introduce a version catalog** (`libs.versions.toml`) if you don't have one. Doing this alongside the DSL migration means each converted module immediately references `libs.` accessors instead of hardcoded strings, so you clean up dependency declarations once.
3. **Convert a leaf module** (one with no dependents) to `build.gradle.kts`, build, and run its tests. Prove the pattern on something low-blast-radius.
4. **Work outward**, module by module, verifying after each. Because mixed DSLs coexist, the project stays green throughout.
5. **Root `build.gradle` last**, once modules are done, and move shared logic into [convention plugins](https://blog.michaelsam94.com/gradle-convention-plugins/) rather than `allprojects`/`subprojects` blocks while you're in there.

This ordering means you're never more than one module away from a working build.

## The conversions that trip people up

Most breakages are mechanical syntax differences. The recurring ones:

- **Quotes.** Groovy allows single quotes; Kotlin requires double quotes for strings. `id 'com.android.application'` becomes `id("com.android.application")`.
- **Parentheses.** Kotlin needs them on method calls: `implementation project(':core')` → `implementation(project(":core"))`.
- **Property assignment.** Groovy's space-assignment becomes `=`: `compileSdk 34` → `compileSdk = 34`.
- **Named arguments for maps.** Groovy map args become Kotlin named args: `manifestPlaceholders = [key: "value"]` → `manifestPlaceholders["key"] = "value"` or the typed equivalent.
- **Task access.** Groovy's dynamic `someTask { }` becomes `tasks.named("someTask") { }` or, better, a typed `tasks.withType<Test>().configureEach { }`. This is the biggest conceptual shift — the Kotlin DSL favors the typed, lazy task-configuration APIs over dynamic lookup.

Here's a representative before/after for an app module header:

```kotlin
// build.gradle.kts
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.example.app"
    compileSdk = 34
    defaultConfig {
        applicationId = "com.example.app"
        minSdk = 24
        targetSdk = 34
    }
}

dependencies {
    implementation(project(":core"))
    implementation(libs.androidx.core.ktx)   // version catalog accessor
    testImplementation(libs.junit)
}
```

## Type-safe accessors and the catalog

The payoff that makes the DSL genuinely nicer than Groovy is *type-safe accessors*. After a version catalog is set up, `libs.androidx.core.ktx` is a generated, autocompleted accessor — misspell it and the script won't compile. Same for plugin aliases (`alias(libs.plugins.android.application)`). Extensions from applied plugins get accessors too, so `android { }` and `kotlin { }` are strongly typed. This is where "the build catches my mistakes" becomes real, versus Groovy where a wrong dependency coordinate is just a runtime resolution failure.

One caveat: accessors are generated from the plugins applied *in that script*, so an extension configured before its plugin is applied won't have an accessor. Apply plugins in the `plugins { }` block at the top and the accessors appear.

## Gotchas beyond syntax

- **`buildSrc`/`build-logic` in Kotlin.** If you write convention plugins in Kotlin, they and your `.kts` scripts share types cleanly — another reason to migrate the whole build to Kotlin rather than straddling.
- **Script compilation caching.** The first Kotlin-DSL build compiles scripts; keep the Gradle daemon and build caches on so this isn't paid repeatedly.
- **Some plugins expose Groovy-friendly dynamic config** that maps awkwardly to Kotlin. When a Kotlin equivalent isn't obvious, the plugin's docs usually show the `.kts` form; if not, the typed `configure<TheExtension> { }` escape hatch works.

## What I'd take away

Migrate to the Kotlin DSL for the type safety, autocomplete, and navigation — the build starts catching mistakes at edit time instead of at run time. Do it incrementally: settings file first, add a version catalog, convert leaf modules outward, root and convention plugins last, leaning on the fact that Groovy and Kotlin scripts coexist so the project never breaks. Expect mechanical fixes around quotes, parentheses, `=` assignment, and typed task configuration, and lean into version-catalog accessors, which are where the DSL stops being merely equivalent to Groovy and becomes clearly better.

## Resources

- [Gradle Kotlin DSL primer](https://docs.gradle.org/current/userguide/kotlin_dsl.html)
- [Migrating build logic from Groovy to Kotlin](https://docs.gradle.org/current/userguide/migrating_from_groovy_to_kotlin_dsl.html)
- [Version catalogs](https://docs.gradle.org/current/userguide/platforms.html)
- [Migrate your build configuration to Kotlin (Android)](https://developer.android.com/build/migrate-to-kotlin-dsl)
- [Task configuration avoidance](https://docs.gradle.org/current/userguide/task_configuration_avoidance.html)
