---
title: "Trimming Dependencies with Dependency Analysis"
slug: "gradle-dependency-analysis-plugin"
description: "Use Gradle Dependency Analysis Plugin to find unused, misdeclared, and redundant dependencies in Android and JVM projects — with actionable advice and CI integration."
datePublished: "2025-06-01"
dateModified: "2025-06-01"
tags: ["Android", "Gradle", "Build", "Performance"]
keywords: "Gradle Dependency Analysis Plugin, unused dependencies Android, misdeclared dependencies, buildHealth, dependency trimming, Gradle build optimization"
faq:
  - q: "What does the Dependency Analysis Plugin detect?"
    a: "It flags dependencies declared in build files but never referenced in source (unused), dependencies used in code but not declared (misdeclared — often pulled in transitively), and redundant declarations where a dependency is already available through another path. It also identifies ABI (api vs implementation) misuse in Android library modules."
  - q: "Should I remove every dependency the plugin marks as unused?"
    a: "Not blindly. Some dependencies are used only at runtime (annotation processors, reflection, service loaders) or only in tests. Review each finding, check for runtime-only usage, and run your test suite after removal. The plugin supports advice filters and suppressions for known exceptions."
  - q: "How do I run dependency analysis in CI?"
    a: "Add `./gradlew buildHealth` or `./gradlew computeAdvice` to your CI pipeline. Fail the build on new violations by comparing against a baseline or using the plugin's auto-fix mode with review. Many teams run it weekly on main and block PRs that add misdeclared dependencies."
---

A 40-module Android project I inherited had 1,200 declared dependencies. After running Dependency Analysis Plugin for an afternoon, we removed 180 lines of dead weight, fixed 60 misdeclared deps that were masking transitive leaks, and cut configuration-cache invalidation on unrelated module changes. None of that showed up in `./gradlew dependencies` — the tree looked fine. The problem was *what you declared vs what you actually used*, and that's exactly what this plugin surfaces.

## What the plugin actually checks

The [Dependency Analysis Plugin](https://github.com/autonomousapps/dependency-analysis-android-gradle-plugin) (by Tony D'Anna) analyzes bytecode and source references to build a usage graph. It compares that graph against your `dependencies { }` blocks and produces **advice**:

- **Remove** — declared but never referenced
- **Add** — referenced but missing from declarations (likely coming transitively)
- **Change** — wrong configuration (`api` vs `implementation` vs `compileOnly`)
- **Substitute** — a lighter alternative exists (e.g., `-jvm` artifact instead of full multiplatform)

On Android library modules, getting `api` vs `implementation` wrong leaks dependencies to every downstream consumer, bloating compile classpaths and slowing builds.

## Setting it up

Add to your version catalog and root `build.gradle.kts`:

```kotlin
// gradle/libs.versions.toml
[plugins]
dependency-analysis = { id = "com.autonomousapps.dependency-analysis", version = "2.4.2" }

// build.gradle.kts (root)
plugins {
    alias(libs.plugins.dependency-analysis)
}

dependencyAnalysis {
    issues {
        all {
            onUnusedDependencies {
                severity("fail") // or "warn" while adopting
            }
            onIncorrectConfiguration {
                severity("fail")
            }
        }
    }
}
```

Apply to subprojects or use it at the root — it works on JVM, Android, and Kotlin Multiplatform modules.

## Reading the report

Run:

```bash
./gradlew buildHealth
```

Output lands in `build/reports/dependency-analysis/`. Each finding includes the module, the dependency coordinate, and the reason. A typical misdeclared finding looks like:

```
:feature:checkout
  ADD compileOnly com.squareup.moshi:moshi-kotlin:1.15.1
    because it is used by CheckoutSerializer but not declared
```

A typical unused finding:

```
:core:network
  REMOVE implementation io.reactivex.rxjava3:rxjava:3.1.8
    because it is not used in this project
```

Work module by module. Start with `Remove` advice — lowest risk. Then fix `Add` advice to stop relying on transitive dependencies you don't control.

## Fixing api vs implementation

In Android library modules, if a type from dependency A appears in your public API (function signatures, exposed classes), A must be `api`. Everything else should be `implementation`:

```kotlin
// Before — leaks OkHttp to all consumers
dependencies {
    api("com.squareup.okhttp3:okhttp:4.12.0")
    api("com.squareup.retrofit2:retrofit:2.11.0")
}

// After — only Retrofit interfaces are public
dependencies {
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    api("com.squareup.retrofit2:retrofit:2.11.0")
}
```

Misconfigured `api` is the silent build-time tax in large multi-module repos. Downstream modules compile against classes they never touch.

## Handling false positives

Some dependencies look unused but aren't:

| Case | Fix |
|------|-----|
| Annotation processors (KSP, KAPT) | Already on `ksp`/`kapt` config — usually fine |
| Reflection / ServiceLoader | Add to `dependencyAnalysis.issues { ... exclude(...) }` |
| Runtime-only (R8 keeps) | Suppress with a reason comment in `build.gradle.kts` |
| Test fixtures shared across modules | Check `testFixtures` configuration separately |

The plugin supports per-dependency suppressions:

```kotlin
dependencyAnalysis {
    issues {
        project(":app") {
            onUnusedDependencies {
                exclude("androidx.profileinstaller:profileinstaller")
                because("Required at runtime for Baseline Profiles")
            }
        }
    }
}
```

## CI integration pattern

We run two tasks in CI:

1. **`computeAdvice`** on every PR — posts findings as a comment (via a small script)
2. **`buildHealth`** on main weekly — creates a ticket for new violations

For PRs, fail only on *new* advice compared to a checked-in baseline:

```bash
./gradlew computeAdvice --no-daemon
git diff --exit-code advice.json || echo "New dependency advice — review required"
```

This prevents the "big bang cleanup" that never happens while still stopping drift.

## Expected impact

On a mid-size Android monorepo (20–60 modules), teams typically see:

- 10–20% fewer declared dependencies after the first pass
- Faster incremental builds from smaller compile classpaths
- Fewer surprise version conflicts when transitives become explicit

The plugin won't fix your architecture, but it removes the noise that makes architecture changes harder to see.

## Understanding advice types

The plugin generates specific advice categories:

| Advice | Meaning | Action |
|---|---|---|
| `remove` | Dependency declared but unused | Delete from build.gradle |
| `add-transitive` | Used but only available transitively | Add as direct dependency |
| `change-to-api` | Used in public API surface | Change `implementation` → `api` |
| `change-to-implementation` | Used only internally | Change `api` → `implementation` |
| `unused-processor` | Annotation processor not needed | Remove kapt/ksp processor |

```kotlin
// Before advice: Gson used in public API but declared as implementation
implementation("com.google.code.gson:gson:2.10.1")

// After advice: change-to-api
api("com.google.code.gson:gson:2.10.1")
// Consumers of this module can now use Gson types without declaring it
```

`api` vs `implementation` affects consumer compile classpath size — use `implementation` unless types appear in public API.

## Autocorrect workflow

Apply advice automatically with review:

```bash
# Generate advice report
./gradlew :app:computeAdvice

# Apply safe autocorrects (remove unused, add transitives)
./gradlew :app:fixDependencies

# Review diff before committing
git diff --stat
```

`fixDependencies` applies `remove` and `add-transitive` automatically. `change-to-api`/`change-to-implementation` require manual review — they affect consumer modules.

## Module-level health tracking

```bash
# Build health report across all modules
./gradlew buildHealth

# Output per module:
# :feature:orders — 3 unused, 2 transitives, 1 api/impl mismatch
# :core:network   — clean
# :app            — 8 unused, 5 transitives
```

Track module health over time. Modules with growing unused dependency counts indicate lack of cleanup — address in dedicated cleanup sprints.

## Failure modes

- **Applying all advice without review** — `change-to-api` can break consumer modules
- **Ignoring add-transitive advice** — dependency breaks when upstream removes transitive
- **One-time cleanup, no CI enforcement** — dependency bloat returns within months
- **Not running on feature modules** — core modules clean, feature modules bloated
- **Removing processor that's needed at runtime** — verify before removing kapt processors

## Production checklist

- `computeAdvice` runs on every PR with diff against baseline
- `fixDependencies` applied in dedicated cleanup PRs (not mixed with features)
- `api` vs `implementation` reviewed manually before changing
- `buildHealth` run weekly on main; ticket for new violations
- All modules included (not just `:app`)
- Version catalog used for consistent coordinates across modules

## Resources

- [Dependency Analysis Plugin GitHub](https://github.com/autonomousapps/dependency-analysis-android-gradle-plugin) — documentation, configuration options, and issue tracker
- [Gradle dependency configurations](https://docs.gradle.org/current/userguide/declaring_dependencies.html#sec:dependency-configurations) — official guide to `api`, `implementation`, `compileOnly`
- [Android Gradle Plugin: library dependencies](https://developer.android.com/build/dependencies) — how dependency types affect consumers
- [Gradle Version Catalogs](https://docs.gradle.org/current/userguide/platforms.html) — pair with the plugin for consistent coordinates across modules
