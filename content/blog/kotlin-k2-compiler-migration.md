---
title: "Migrating to the Kotlin K2 Compiler"
slug: "kotlin-k2-compiler-migration"
description: "Migrating to the Kotlin K2 compiler brings faster builds and a unified frontend, but the payoff depends on plugin support and how you handle new strictness."
datePublished: "2026-04-11"
dateModified: "2026-04-11"
tags: ["Kotlin", "Build", "Android"]
keywords: "Kotlin K2 compiler, K2 migration, Kotlin 2.0, compiler plugins K2, build performance Kotlin"
faq:
  - q: "What is the Kotlin K2 compiler?"
    a: "K2 is the rewritten frontend of the Kotlin compiler that became the default in Kotlin 2.0. The frontend is the part that parses code, resolves references, and does type checking; K2 replaces the old frontend with a faster, more consistent implementation built around a unified semantic model. It compiles faster, produces more predictable diagnostics, and gives compiler plugins a stable foundation to build on."
  - q: "Will migrating to K2 break my build?"
    a: "For most application code the migration is transparent — you bump the Kotlin version and rebuild. Breakage, when it happens, usually comes from two sources: compiler plugins that haven't been updated for K2, and code that relied on old-frontend bugs or looser type inference that K2 now flags correctly. Both are surfaced as clear compile errors rather than silent behavior changes."
  - q: "Do I need to update my compiler plugins for K2?"
    a: "Yes, if you use them. Compiler plugins like KSP, the Compose compiler, kapt replacements, and serialization must be on K2-compatible versions. KSP2 is the K2-aware processor path, and the Compose compiler is now versioned with Kotlin itself. Check each plugin's compatibility before migrating; an out-of-date plugin is the most common blocker."
---

The Kotlin K2 compiler is the biggest thing to happen to the language's tooling in years, and yet for a lot of teams the migration is anticlimactic: bump to Kotlin 2.x, rebuild, done. That's by design. K2 is a rewrite of the compiler *frontend* — the parsing, resolution, and type-checking stage — built around a single consistent semantic model, and the whole point was to make it faster and more predictable without changing what correct Kotlin means. When the migration isn't anticlimactic, it's almost always one of two culprits: a compiler plugin that isn't K2-ready, or code that leaned on quirks of the old frontend.

I've moved a few multi-module Android projects across, and the pattern is consistent enough that I can give you a real playbook rather than "upgrade and hope."

## What K2 actually changes

The frontend is where the compiler figures out what your code *means* — which `foo` a call refers to, what type an expression has, whether the types line up. The old frontend accreted over a decade and had inconsistencies: different code paths reasoned about types slightly differently, which produced occasional weird diagnostics and made compiler plugins hard to write correctly. K2 replaces it with one unified model (the FIR, or frontend intermediate representation).

The benefits that matter in practice:

- **Faster compilation**, especially the analysis phase. On larger modules the frontend speedup is noticeable, and it compounds with the rest of your [build performance work](https://blog.michaelsam94.com/faster-gradle-builds/) — a faster compiler frontend on top of configuration caching and proper module boundaries is real minutes back per day.
- **More consistent type inference and diagnostics.** Fewer "why is the compiler confused here" moments, and error messages that point at the actual problem.
- **A stable platform for compiler plugins**, which is why the Compose compiler, KSP, and others could finally standardize against a real API instead of internal compiler guts.

The backend — the part that emits JVM bytecode, JS, or native — is largely unchanged, so your output behaves the same. This is a frontend story.

## The plugin compatibility gate

This is the migration's real gatekeeper, so check it first. Kotlin compiler plugins hook into the frontend, so a plugin built for the old frontend won't work on K2. The ones almost every Android project uses:

| Plugin | K2 requirement |
| --- | --- |
| Compose compiler | Now versioned with Kotlin; use the matching release |
| KSP | Use KSP2 / a K2-compatible KSP version |
| kotlinx.serialization | K2-compatible plugin version |
| Parcelize | Bundled, K2-ready in modern AGP |
| Any custom/third-party plugin | Verify individually — this is where surprises hide |

My advice: before touching the Kotlin version, make a list of every compiler plugin in your build and confirm each has a K2-compatible release. If you use an obscure or unmaintained compiler plugin, that's your risk item — it may need replacing entirely. This audit takes an hour and prevents the most common failure mode, which is bumping Kotlin and getting a wall of errors from one stale plugin.

## New strictness you may hit

The second source of friction is code that compiled before only because the old frontend was lenient or buggy. K2 tends to be more correct, which occasionally means code that "worked" now doesn't. The categories I've actually encountered:

- **Smart-cast changes.** K2's smart-cast analysis is more precise. In a few spots it smart-casts where the old compiler wouldn't (nice), and in a few it *stops* smart-casting where the old behavior was actually unsound (you add an explicit check or cast).
- **Ambiguous overloads resolved differently.** A handful of overload-resolution edge cases resolve more strictly, surfacing a call that was quietly ambiguous.
- **Stricter nullability at platform boundaries.** Java interop nullability is handled more consistently, so an unannotated Java return you were treating loosely may now warn or error.

Crucially, these show up as **compile errors, not runtime surprises**. That's the good kind of migration pain — the compiler tells you exactly where to look, and the fixes are usually one or two lines. On a mid-sized codebase I hit maybe a dozen such sites, all fixed in an afternoon.

## A staged migration plan

Here's how I sequence it to keep the blast radius small:

1. **Audit plugins.** List every compiler plugin and confirm K2-compatible versions exist. Don't proceed until this is green.
2. **Bump Kotlin and plugins together** in a branch. Update the Kotlin version, the Compose compiler to its matching release, and KSP to KSP2. Half of migration problems are just version-skew between these.
3. **Build and triage errors.** Fix the strictness sites (smart casts, overloads, nullability). Treat each as a small, correct improvement rather than a workaround.
4. **Run the full test suite.** Because the backend is stable, behavior should be identical — a passing suite is strong evidence the migration is clean.
5. **Measure build times.** Compare clean and incremental build times before and after so you can quantify the win and justify the effort to the team.

```kotlin
// build.gradle.kts — the versions that must move in lockstep
plugins {
    kotlin("android") version "2.1.0"
    id("com.google.devtools.ksp") version "2.1.0-1.0.29" // KSP2, tracks Kotlin
    kotlin("plugin.serialization") version "2.1.0"
    kotlin("plugin.compose") version "2.1.0" // Compose compiler versioned with Kotlin
}
```

## The language features you unlock

Migrating isn't only about speed — K2 is the foundation for the newer language features you'll want. Stabilized additions like [Kotlin context parameters](https://blog.michaelsam94.com/kotlin-context-parameters/) and other recent ergonomics land on the K2 frontend, so staying on the old compiler means falling behind on the language itself, not just on build times. That's the strategic argument I make to teams that are tempted to defer: this isn't an optional tune-up you can skip indefinitely, it's the on-ramp to where Kotlin is going. The old frontend is end-of-life.

## Is it worth it?

Unequivocally yes, and the risk is lower than teams fear because the failure modes are loud (compile errors) rather than silent (runtime behavior). The honest costs are the plugin audit and a bounded round of fixing newly-strict code — call it a day or two for a medium project, more only if you're carrying an unmaintained compiler plugin that needs replacing. Against that you get faster builds, better diagnostics, and access to current and future language features.

The one scenario where I'd slow down: if a business-critical build step depends on a third-party compiler plugin with no K2 release and no maintainer. That's not a reason to skip the migration forever — it's a reason to plan the plugin's replacement as part of the migration. Everyone lands on K2 eventually; the teams that do it deliberately, plugin audit first, have the boring successful migration. The ones that bump the version on a Friday and hope are the ones writing the angry postmortems.

## Resources

- [Kotlin K2 compiler migration guide](https://kotlinlang.org/docs/k2-compiler-migration-guide.html)
- [Kotlin 2.0 release notes](https://kotlinlang.org/docs/whatsnew20.html)
- [KSP (Kotlin Symbol Processing)](https://github.com/google/ksp)
- [Compose compiler and Kotlin compatibility](https://developer.android.com/develop/ui/compose/compiler)
- [The Kotlin Blog](https://blog.jetbrains.com/kotlin/)
