---
title: "Product Flavors and Build Variants"
slug: "android-build-variants-flavors"
description: "Configure Android product flavors and build variants: dimension design, flavor-specific resources, BuildConfig fields, and keeping multi-flavor projects maintainable."
datePublished: "2026-07-14"
dateModified: "2026-07-14"
tags: ["Android", "Gradle", "Build", "Architecture"]
keywords: "Android product flavors, build variants Gradle, flavorDimensions, BuildConfig flavors, Android multi-flavor setup"
faq:
  - q: "What is the difference between a build type and a product flavor?"
    a: "Build types (debug, release) control how the app is built — minification, debuggability, signing. Product flavors (free, pro, enterprise) control what the app contains — features, branding, API endpoints. A build variant is the combination of one build type and one flavor (e.g., proRelease, freeDebug)."
  - q: "How many flavor dimensions should an app have?"
    a: "Use one dimension for most apps (tier: free/pro). Add a second dimension only when flavors vary on independent axes (e.g., tier × region). More than two dimensions creates a combinatorial explosion of variants that's hard to test and maintain. If you have 12+ variants, consider dynamic feature modules or runtime configuration instead."
  - q: "How do I share code between flavors?"
    a: "Put shared code in main/. Put flavor-specific code in src/<flavorName>/. Use flavor-specific source sets only for code that genuinely differs — API keys via BuildConfig, branding via resources, feature flags via flavor-specific modules. Avoid duplicating entire classes per flavor; use interfaces in main with flavor-specific implementations."
---

Product flavors are Gradle's answer to "we need three versions of this app" — free and pro, white-label clients, staging and production endpoints — without maintaining three separate codebases. Done well, flavors isolate the 5% that differs and share the 95% that doesn't. Done badly, you get four copies of every ViewModel with slightly different API URLs and a CI matrix that takes an hour. I've refactored flavor setups that had grown to 16 variants (2 tiers × 2 regions × 2 environments × 2 build types) down to 4 by moving environment config to runtime and region to resource overlays. The goal is the minimum number of variants that satisfy actual product requirements.

## Build types vs flavors vs variants

```
Build Type (debug/release)  ×  Product Flavor (free/pro)  =  Build Variant
         release              ×         pro                =    proRelease
         debug                ×         free               =    freeDebug
```

Build types control compilation behavior. Flavors control product behavior. Variants are what you build, test, and ship.

## Basic flavor setup

```kotlin
android {
    flavorDimensions += "tier"

    productFlavors {
        create("free") {
            dimension = "tier"
            applicationIdSuffix = ".free"
            versionNameSuffix = "-free"
            buildConfigField("Boolean", "PREMIUM", "false")
            buildConfigField("String", "API_BASE", "\"https://api.example.com/v1/\"")
        }
        create("pro") {
            dimension = "tier"
            buildConfigField("Boolean", "PREMIUM", "true")
            buildConfigField("String", "API_BASE", "\"https://api.example.com/v1/\"")
        }
    }
}
```

Access in code:

```kotlin
if (BuildConfig.PREMIUM) {
    showPremiumFeatures()
}
```

## Source set organization

```
src/
├── main/           # Shared code and resources
├── free/
│   ├── java/       # Free-only implementations
│   └── res/        # Free branding
├── pro/
│   ├── java/
│   └── res/
├── release/        # Release-only (ProGuard rules, etc.)
└── debug/          # Debug-only (leak canary, strict mode)
```

Gradle merges source sets: `proRelease` gets `main` + `pro` + `release`. Files in flavor source sets override main.

Use this pattern for flavor-specific implementations:

```kotlin
// main/BillingManager.kt — interface
interface BillingManager {
    fun purchase(sku: String)
}

// free/BillingManagerImpl.kt
class BillingManagerImpl : BillingManager {
    override fun purchase(sku: String) { /* show upgrade prompt */ }
}

// pro/BillingManagerImpl.kt
class BillingManagerImpl : BillingManager {
    override fun purchase(sku: String) { /* real Play Billing */ }
}
```

## Multiple dimensions (use sparingly)

```kotlin
flavorDimensions += listOf("tier", "region")

productFlavors {
    create("free") { dimension = "tier" }
    create("pro") { dimension = "tier" }
    create("us") { dimension = "region" }
    create("eu") { dimension = "region" }
}
// Variants: freeUsRelease, proEuDebug, etc. — 2×2×2 = 8 variants
```

Before adding a second dimension, ask: can region be a resource overlay or runtime locale instead? Can environment be a build config field toggled by CI, not a flavor?

## Flavor-specific dependencies

```kotlin
dependencies {
    "proImplementation"(libs.play.billing)
    "freeImplementation"(libs.admob)
}
```

Only the pro flavor gets Play Billing; only free gets ads. Keeps APK size down and avoids shipping ad SDKs to paying users.

## Filtering variants in CI

Don't build all variants in CI if you only ship two:

```kotlin
androidComponents {
    beforeVariants { variantBuilder ->
        if (variantBuilder.flavorName == "free" && variantBuilder.buildType == "release") {
            variantBuilder.enable = false  // don't build freeRelease
        }
    }
}
```

Or use variant filtering in CI scripts to test `proDebug` + `proRelease` only.

## Common mistakes

**Environment as flavor.** `dev`, `staging`, `prod` flavors multiply your matrix. Use build config fields injected by CI:

```kotlin
buildConfigField("String", "API_BASE", "\"${project.findProperty("apiBase") ?: "https://staging.api.com"}\"")
```

**Duplicating entire modules per flavor.** If more than 20% of code differs, consider separate modules with flavor-specific dependencies, not copy-paste source sets.

**Hardcoded flavor checks everywhere.** Centralize:

```kotlin
object AppConfig {
    val isPremium get() = BuildConfig.PREMIUM
    val apiBase get() = BuildConfig.API_BASE
}
```

One place to read flavor config; the rest of the app uses `AppConfig`.

For larger apps, combine flavors with [modularization](https://blog.michaelsam94.com/android-modularization-strategy/) — flavor-specific feature modules that compile only into the variants that need them.

## Product flavor dimensions

Organize flavors by meaningful product dimensions:

```kotlin
// build.gradle.kts
android {
    flavorDimensions += listOf("tier", "market")

    productFlavors {
        create("free") {
            dimension = "tier"
            applicationIdSuffix = ".free"
            buildConfigField("Boolean", "PREMIUM", "false")
        }
        create("pro") {
            dimension = "tier"
            buildConfigField("Boolean", "PREMIUM", "true")
        }
        create("global") {
            dimension = "market"
            buildConfigField("String", "DEFAULT_LOCALE", "\"en\"")
        }
        create("eu") {
            dimension = "market"
            buildConfigField("String", "DEFAULT_LOCALE", "\"en\"")
            buildConfigField("Boolean", "GDPR_MODE", "true")
        }
    }
}
// Variants: freeGlobalDebug, proEuRelease, etc.
```

Two dimensions produce 4 flavor combinations per build type. Keep dimensions independent — tier and market shouldn't overlap.

## Source set hierarchy

Flavor-specific code overrides main source set:

```
src/
├── main/           ← shared by all variants
├── free/           ← free tier only
├── pro/            ← pro tier only
├── eu/             ← EU market only
└── proEu/          ← pro + EU combination only
```

```kotlin
// src/pro/java/com/example/BillingManager.kt
class BillingManager {
    fun purchasePremium() { /* real billing */ }
}

// src/free/java/com/example/BillingManager.kt
class BillingManager {
    fun purchasePremium() { /* show upgrade prompt */ }
}
```

Same class name, different implementation per flavor — no runtime if/else checks scattered through codebase.

## CI variant matrix

Test critical variants in CI without building all combinations:

```yaml
# .github/workflows/android.yml
strategy:
  matrix:
    variant: [freeGlobalDebug, proGlobalDebug, proEuRelease]
steps:
  - run: ./gradlew assemble${{ matrix.variant }}
  - run: ./gradlew test${{ matrix.variant }}UnitTest
```

Test: one debug per tier, one release for primary market. Skip exotic combinations unless they have unique code paths.

## Failure modes

- **Environment as flavor** — dev/staging/prod flavors multiply matrix; use buildConfigField injection
- **Flavor checks scattered in code** — `if (BuildConfig.PREMIUM)` everywhere; centralize in AppConfig
- **Duplicate modules per flavor** — copy-paste source sets; use flavor-specific source files
- **All variants built in CI** — 8+ variants × 2 build types = 16 builds; filter matrix
- **Missing variant-specific testing** — EU flavor GDPR code never tested in CI

## Production checklist

- Flavor dimensions reflect product differences (tier, market), not environment
- Flavor-specific code in source sets, not runtime if/else checks
- AppConfig object centralizes all BuildConfig reads
- CI matrix tests critical variant combinations (not all permutations)
- applicationIdSuffix per flavor for side-by-side installation
- Flavor-specific feature modules for >20% code divergence

## Resources

- [Configure build variants (Android)](https://developer.android.com/build/build-variants)
- [Gradle flavorDimensions reference](https://developer.android.com/reference/tools/gradle-api/com/android/build/api/dsl/ProductFlavor)
- [Configure CI for build variants](https://developer.android.com/build/build-variants#filter-variants)
- [Gradle convention plugins](https://blog.michaelsam94.com/gradle-convention-plugins/)
- [Android modularization strategy](https://blog.michaelsam94.com/android-modularization-strategy/)
