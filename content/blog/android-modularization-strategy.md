---
title: "A Pragmatic Android Modularization Strategy"
slug: "android-modularization-strategy"
description: "Modularize Android apps pragmatically: module types, dependency rules, feature modules, and incremental extraction without stopping feature development."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Android", "Architecture", "Gradle", "Modularization"]
keywords: "Android modularization, multi-module Android, feature modules Android, Android module architecture, Gradle modules Android"
faq:
  - q: "When should I modularize my Android app?"
    a: "Modularize when build times exceed 2–3 minutes for incremental changes, when multiple teams work on the same codebase, or when you need feature isolation for testing and deployment. Don't modularize a solo-developer app with 10 screens — the overhead isn't worth it until you feel the pain of a monolith."
  - q: "What module types should an Android app have?"
    a: "Typical structure: :app (shell), :core:ui (shared composables/theme), :core:data (networking, database), :core:domain (models, interfaces), and :feature:* modules (one per feature area). Each feature module depends on core modules but not on other feature modules."
  - q: "How do I modularize without stopping feature development?"
    a: "Extract one module per sprint. Start with the most isolated feature or the most reused code (design system, networking). Keep the app compiling after each extraction. Use api vs implementation dependencies to control visibility. Don't extract everything upfront — incremental extraction over 2–3 months is normal."
---

Modularization is the refactor everyone agrees they need and nobody wants to do — because the typical approach is "stop everything, split into 20 modules, fix 400 import errors, merge in 3 weeks." The pragmatic approach extracts one module at a time, keeps the app shipping, and stops when build times and team boundaries are solved — not when you hit some theoretical ideal module count. I've modularized apps from monolith to 15 modules incrementally (one extraction per sprint) and seen build times drop 60%. I've also seen a "big bang" modularization branch abandoned after 6 weeks. The difference is entirely about incrementalism.

## Module types

```
:app                    ← Application shell, navigation, DI root
:core:model             ← Data classes, domain models
:core:network           ← API client, interceptors
:core:database          ← Room/SQLDelight
:core:ui                ← Theme, shared composables, design system
:core:common            ← Utilities, extensions
:feature:auth           ← Login, registration
:feature:home           ← Home screen
:feature:orders         ← Order list, detail
:feature:settings       ← Settings, profile
```

Dependency rules:

```
:app → :feature:* → :core:* → :core:model
:feature:A ✗→ :feature:B    (feature modules never depend on each other)
:core:model → nothing        (models depend on nothing)
```

Enforce with Gradle dependency analysis or module dependency graphs in CI.

## Start with core:model

Extract data models first — they have the fewest dependencies:

```kotlin
// settings.gradle.kts
include(":core:model")

// core/model/build.gradle.kts
plugins {
    id("com.android.library")
    kotlin("android")
}

dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.7.1")
}
```

Move all data classes, enums, and domain models. Every other module will depend on this.

## Extract core:network

```kotlin
// core/network/build.gradle.kts
dependencies {
    api(project(":core:model"))
    implementation(libs.retrofit)
    implementation(libs.okhttp)
}
```

Use `api` for `:core:model` if network module exposes models in its public API. Use `implementation` for Retrofit/OkHttp — consumers shouldn't see those.

## Extract core:ui (design system)

Shared theme, composables, and resources:

```kotlin
// core/ui/build.gradle.kts
dependencies {
    api(platform(libs.compose.bom))
    api(libs.compose.ui)
    api(libs.compose.material3)
    api(libs.compose.ui.tooling.preview)
}
```

```kotlin
// core/ui/theme/AppTheme.kt
@Composable
fun AppTheme(content: @Composable () -> Unit) { /* ... */ }

// core/ui/components/AppButton.kt
@Composable
fun AppButton(text: String, onClick: () -> Unit) { /* ... */ }
```

Every feature module depends on `:core:ui` for consistent design.

## Extract feature modules

One feature at a time, starting with the most isolated:

```kotlin
// feature/orders/build.gradle.kts
plugins {
    id("com.android.library")
    kotlin("android")
    id("com.google.dagger.hilt.android")
}

dependencies {
    implementation(project(":core:model"))
    implementation(project(":core:network"))
    implementation(project(":core:ui"))
    implementation(project(":core:database"))
}
```

Move the feature's screens, ViewModels, and navigation routes. The feature module exposes a navigation entry point:

```kotlin
// feature/orders/OrdersNavigation.kt
fun NavGraphBuilder.ordersGraph(navController: NavController) {
    composable("orders") { OrdersScreen() }
    composable("orders/{id}") { OrderDetailScreen() }
}
```

The app module wires feature graphs together:

```kotlin
// app/MainNavHost.kt
NavHost(navController, startDestination = "home") {
    homeGraph(navController)
    ordersGraph(navController)
    settingsGraph(navController)
}
```

## api vs implementation

Control what's visible across module boundaries:

```kotlin
// core/network/build.gradle.kts
dependencies {
    api(project(":core:model"))        // consumers see models
    implementation(libs.retrofit)       // consumers DON'T see Retrofit
}
```

If a feature module needs Retrofit directly (it shouldn't), use `api`. Otherwise `implementation` hides transitive dependencies — faster compilation and cleaner boundaries.

## Build time wins

Modularization pays off when Gradle can skip unchanged modules:

| Change in | Recompiles |
|-----------|-----------|
| :feature:orders | :feature:orders, :app |
| :core:model | everything (it's a leaf everyone depends on) |
| :core:ui | :core:ui, all features, :app |
| :feature:settings only | :feature:settings, :app |

Keep `:core:model` stable — changes there cascade everywhere. Keep feature modules isolated — changes stay local.

Enable parallel compilation:

```properties
# gradle.properties
org.gradle.parallel=true
org.gradle.caching=true
kotlin.incremental=true
```

## Feature module isolation with Hilt

Each feature module has its own Hilt module:

```kotlin
// feature/orders/OrdersModule.kt
@Module
@InstallIn(ViewModelComponent::class)
abstract class OrdersModule {
    @Binds abstract fun bindOrdersRepo(impl: OrdersRepositoryImpl): OrdersRepository
}
```

Cross-feature communication goes through interfaces in `:core:domain`, not direct imports. Use [multibindings](https://blog.michaelsam94.com/android-hilt-multibindings/) for plugin-style contributions.

## When to stop modularizing

Not every app needs 20 modules. Stop when:
- Incremental builds are under 30 seconds
- Teams can work on features without merge conflicts
- Feature modules compile and test independently

A 5-module app (:app, :core, :feature:a, :feature:b, :feature:c) is fine for a 2-person team. Don't over-module to 15 for a 3-screen app.

For larger apps, combine with [multi-module navigation](https://blog.michaelsam94.com/android-multi-module-navigation-compose/) and [convention plugins](https://blog.michaelsam94.com/gradle-convention-plugins/) to keep Gradle configs DRY.

## Common production mistakes

Teams get modularization strategy wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping modularization strategy on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Debugging and triage workflow

When modularization strategy misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Guide to Android app modularization](https://developer.android.com/topic/modularization)
- [Now in Android — reference modular app](https://github.com/android/nowinandroid)
- [Gradle dependency types (api vs implementation)](https://docs.gradle.org/current/userguide/java_library_plugin.html)
- [Gradle convention plugins](https://blog.michaelsam94.com/gradle-convention-plugins/)
- [Multi-module navigation with Compose](https://blog.michaelsam94.com/android-multi-module-navigation-compose/)
