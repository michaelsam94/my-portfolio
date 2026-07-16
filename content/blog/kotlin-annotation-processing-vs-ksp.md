---
title: "KAPT vs KSP: Why You Should Migrate"
slug: "kotlin-annotation-processing-vs-ksp"
description: "Compare KAPT and KSP for Kotlin annotation processing: build speed, symbol accuracy, migration steps from Room and Moshi, and when KAPT still lingers."
datePublished: "2025-11-13"
dateModified: "2025-11-13"
tags: ["Android", "Kotlin"]
keywords: "KAPT, KSP, Kotlin Symbol Processing, annotation processor migration, Room KSP, build performance"
faq:
  - q: "Is KSP a drop-in replacement for KAPT?"
    a: "Not always. KSP understands Kotlin directly and exposes a different API for processor authors. Libraries must ship KSP-compatible processors—Room, Moshi, and Hilt support KSP, but older or Java-only processors may still require KAPT. You can run KSP and KAPT together during migration, but the goal is to drop KAPT entirely."
  - q: "How much faster are KSP builds compared to KAPT?"
    a: "Teams typically report 1.5x to 2x faster annotation processing modules, with larger projects seeing more because KAPT generates stub Java sources and runs javac. Exact gains depend on module count and processor workload. The bigger win is incremental correctness—KSP avoids stub-related full recompiles."
  - q: "What breaks most often during KAPT to KSP migration?"
    a: "Processors that relied on Java-only type information or Element APIs need KSP rewrites if you maintain custom processors. For consumers, misconfigured processor arguments and missing ksp() dependencies are common. Room needs the ksp plugin and schema export path updated; generated code lands under build/generated/ksp instead of kapt."
---

Our Android monorepo's `:feature:checkout` module spent 47 seconds in `kaptKotlin` on every clean build—mostly regenerating Room DAOs and Dagger factories from Java stubs that existed only because KAPT couldn't read Kotlin types natively. Switching that module to KSP cut annotation processing to 19 seconds and eliminated an entire stub-generation pass. If you're still on KAPT in 2025, you're paying a tax on every CI run for historical reasons, not technical ones.

**KAPT (Kotlin Annotation Processing Tool)** compiles Kotlin to Java stubs, then feeds them to Java annotation processors. It works, but it's indirect. **KSP (Kotlin Symbol Processing)** reads Kotlin AST directly, generates Kotlin-friendly code, and integrates with Kotlin's incremental compilation.

## How the pipelines differ

KAPT path:

```
Kotlin sources → stub .java files → javac + processors → generated code → Kotlin compile
```

KSP path:

```
Kotlin sources → KSP processors → generated Kotlin/Java → compile
```

No stub layer means fewer files, less invalidation, and processors see actual nullability, default parameters, and visibility.

Enable KSP:

```kotlin
// build.gradle.kts
plugins {
    id("com.google.devtools.ksp") version "2.0.21-1.0.28"
}

dependencies {
    ksp("androidx.room:room-compiler:2.6.1")
    // NOT kapt(...)
}
```

Remove the matching `kapt` dependency when the processor supports KSP exclusively.

## Migrating Room

Room first-class supports KSP:

```kotlin
plugins {
    id("com.google.devtools.ksp")
}

android {
    defaultConfig {
        ksp {
            arg("room.schemaLocation", "$projectDir/schemas")
            arg("room.incremental", "true")
        }
    }
}

dependencies {
    implementation("androidx.room:room-runtime:2.6.1")
    ksp("androidx.room:room-compiler:2.6.1")
}
```

Generated sources appear in `build/generated/ksp/<variant>/kotlin`. Update `.gitignore` if you ignored kapt paths but commit nothing from build—schema export directory stays the same.

Verify DAO queries compile—KSP catches more Kotlin-specific errors at processing time than KAPT stubs sometimes masked.

## Migrating Dagger and Hilt

Hilt supports KSP starting with recent AGP/Kotlin pairings:

```kotlin
plugins {
    id("com.google.devtools.ksp")
    id("com.google.dagger.hilt.android")
}

dependencies {
    ksp("com.google.dagger:hilt-compiler:2.52")
    ksp("androidx.hilt:hilt-compiler:1.2.0") // for @HiltViewModel etc.
}
```

Drop `kotlin-kapt` plugin when no kapt dependencies remain. Mixed modules during migration can use both in different subprojects—avoid both in the same module unless necessary.

## Custom annotation processors

If you maintain in-house processors, KSP's API differs from javax.lang.model:

```kotlin
class MyProcessor(
    private val codeGenerator: CodeGenerator,
    private val logger: KSPLogger
) : SymbolProcessor {
    override fun process(resolver: Resolver): List<KSAnnotated> {
        val symbols = resolver.getSymbolsWithAnnotation("com.example.Bind")
        symbols.filterIsInstance<KSClassDeclaration>().forEach { /* generate */ }
        return emptyList()
    }
}
```

KSP cannot reuse Java Annotation Processing API code verbatim. Budget rewrite time if you own processors.

## When KAPT still hangs around

- Legacy processors without KSP ports
- Libraries generating Java-only code consumed from Java modules (rare in Kotlin-first apps)
- Transitive dependencies pulling kapt transitively—exclude or upgrade

Run `./gradlew :app:kspDebugKotlin --profile` vs kapt equivalent to measure locally before mass migration.

## Migration checklist

1. Upgrade Kotlin, AGP, and processor libraries to KSP-compatible versions
2. Add KSP plugin at root with aligned version string
3. Replace `kapt` with `ksp` per dependency
4. Move processor args from `kapt { arguments { } }` to `ksp { arg() }`
5. Remove `kotlin-kapt` plugin module-by-module
6. Clean build and fix any generated import paths in tests

CI cache keys should include KSP outputs—stale kapt caches cause confusing errors after switching.

## CI cache keys

Include Kotlin version, KSP version, and processor classpath in Gradle cache key—stale KSP output after processor upgrade causes bizarre compile errors in generated sources.

## Incremental builds

KSP `symbol-processing-api` incremental mode requires processors to declare dependencies correctly—if builds are always clean, check processor implements `Incremental` contract.


## What to measure after rollout

Track error rates, tail latency, and resource utilization for two weeks after changes land—most regressions appear under real traffic mixes, not in staging smoke tests. Keep a rollback path documented: feature flags, Helm revision, or Git revert with known good digest. Review on-call pages tied to the topic quarterly; delete alerts that never fire and add thresholds that would have caught your last incident.

Run a short blameless postmortem if production surprised you, even for minor issues. The goal is updating this runbook section with one concrete lesson per quarter so the next engineer inherits context, not just configuration snippets.


## Documentation your team should maintain

Maintain a one-page runbook link from your main service README: prerequisites, owner rotation, last drill date, and known sharp edges. Link to vendor docs in the Resources section below but capture org-specific decisions (CIDR ranges, cluster names, approval gates) in internal docs that stay current. New hires should deploy a safe canary within a week using only that runbook—if they cannot, the doc is incomplete.


## Pre-production checklist

Before promoting to production, walk through this list with someone who was not the primary author—fresh eyes catch assumptions.

- **Staging parity**: The staging environment exercises the same code paths as production, including failure modes you expect to handle (timeouts, retries, partial outages).
- **Observability**: Dashboards and alerts exist for the metrics and log patterns discussed above; on-call knows where to look first.
- **Rollback**: You can revert to the previous known-good state in one documented step without improvising.
- **Access control**: Only the principals that need access have it; audit logs are enabled where the topic touches secrets or infrastructure APIs.
- **Load test**: You have evidence—not intuition—about behavior at expected peak plus headroom.

If any item is "we will do that later," treat it as a release blocker for tier-1 services.


## Resources

- [KSP official documentation](https://kotlinlang.org/docs/ksp-overview.html) — setup, FAQ, and processor authoring
- [KSP quickstart](https://kotlinlang.org/docs/ksp-quickstart.html) — Gradle configuration examples
- [Room KSP support announcement](https://developer.android.com/jetpack/androidx/releases/room#2.5.0) — minimum versions and args
- [Android Gradle Plugin KSP guide](https://developer.android.com/build/migrate-to-ksp) — Google's migration checklist
