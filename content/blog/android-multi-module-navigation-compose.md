---
title: "Multi-Module Navigation with Compose"
slug: "android-multi-module-navigation-compose"
description: "Wire navigation across Android feature modules with Compose Navigation: typed routes, module-owned graphs, deep links, and keeping feature modules independent."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Android", "Jetpack Compose", "Navigation", "Architecture"]
keywords: "multi-module navigation Compose, feature module navigation, Compose Navigation typed routes, modular navigation Android, NavGraphBuilder feature module"
faq:
  - q: "How do you share navigation across Android feature modules?"
    a: "Each feature module exposes a NavGraphBuilder extension function that registers its routes. The app module creates the NavHost and calls each feature's graph function. Feature modules depend on shared route definitions in a core module but not on each other. Navigation arguments use typed route classes with kotlinx.serialization."
  - q: "Should navigation routes be defined in a shared module?"
    a: "Define route string constants or typed route classes in a core:navigation module that all feature modules depend on. This lets features navigate to other features' routes without depending on the feature module itself — only on the route definition. The app module wires the actual composables."
  - q: "How do typed routes work with multi-module navigation?"
    a: "Define @Serializable route classes in the shared module. Each feature module registers composable destinations matching those routes. Navigation uses navController.navigate(route) with type-safe arguments. This replaces string-based routes and catches navigation errors at compile time."
---

Multi-module navigation breaks down the moment `feature-orders` imports `feature-profile` just to navigate to a settings screen. The whole point of feature modules is independence — each compiles, tests, and deploys without knowing about the others. Navigation is the hardest boundary to keep clean because screens need to talk to each other. The pattern that works: shared route definitions in a core module, graph registration functions in each feature module, and a single NavHost in the app module that wires everything together. I've set this up on three modular apps; the typed routes are what prevent "navigate to a screen that doesn't exist" bugs from reaching production.

## Module structure

```
:core:navigation     ← Route definitions (typed routes)
:feature:home        ← HomeNavGraph.kt
:feature:orders      ← OrdersNavGraph.kt
:feature:profile     ← ProfileNavGraph.kt
:app                 ← MainNavHost.kt (wires all graphs)
```

## Typed routes in core module

```kotlin
// core/navigation/Routes.kt
@Serializable object HomeRoute

@Serializable data class OrderDetailRoute(val orderId: String)

@Serializable object ProfileRoute

@Serializable data class SettingsRoute(val section: String? = null)
```

All feature modules depend on `:core:navigation` for route types. No feature module depends on another feature module.

## Feature module graph functions

```kotlin
// feature/orders/OrdersNavGraph.kt
fun NavGraphBuilder.ordersGraph(
    navController: NavController,
    onNavigateToProfile: () -> Unit,
) {
    composable<OrderDetailRoute> { backStackEntry ->
        val route = backStackEntry.toRoute<OrderDetailRoute>()
        OrderDetailScreen(
            orderId = route.orderId,
            onBack = { navController.popBackStack() },
            onViewProfile = onNavigateToProfile,
        )
    }
}
```

Cross-feature navigation uses callbacks, not direct imports:

```kotlin
// feature/orders passes onNavigateToProfile callback
// app module provides the lambda that navigates to ProfileRoute
```

This keeps feature modules decoupled. The app module is the only place that knows how features connect.

## App module NavHost

```kotlin
// app/MainNavHost.kt
@Composable
fun MainNavHost(navController: NavHostController) {
    NavHost(navController, startDestination = HomeRoute) {
        homeGraph(navController)
        ordersGraph(
            navController = navController,
            onNavigateToProfile = { navController.navigate(ProfileRoute) },
        )
        profileGraph(navController)
    }
}
```

Cross-feature navigation callbacks are wired here and only here.

## Navigation with type safety

Register the Kotlin serialization plugin for typed routes:

```kotlin
// app/build.gradle.kts
dependencies {
    implementation(libs.navigation.compose)
    implementation(libs.kotlinx.serialization.json)
}
```

Navigate with type safety:

```kotlin
navController.navigate(OrderDetailRoute(orderId = "4521"))
// NOT: navController.navigate("orders/4521") — error-prone strings
```

## Deep links across modules

Define deep links in the shared route or feature module:

```kotlin
composable<OrderDetailRoute>(
    deepLinks = listOf(
        navDeepLink { uriPattern = "https://example.com/orders/{orderId}" }
    )
) { backStackEntry ->
    val route = backStackEntry.toRoute<OrderDetailRoute>()
    OrderDetailScreen(orderId = route.orderId)
}
```

Each feature module owns its deep link patterns. The app module's NavHost resolves them.

## ViewModel scoping to routes

ViewModels scoped to the navigation back stack entry survive configuration changes within the route:

```kotlin
composable<OrderDetailRoute> { backStackEntry ->
    val viewModel: OrderDetailViewModel = hiltViewModel(backStackEntry)
    OrderDetailScreen(viewModel)
}
```

See [ViewModel scoping to navigation graphs](https://blog.michaelsam94.com/android-viewmodel-scoping-navigation/) for nested graph scoping patterns.

## Testing navigation

Test feature module navigation in isolation:

```kotlin
@Test
fun ordersGraph_navigatesToDetail() {
    val navController = TestNavHostController(ApplicationProvider.getApplicationContext())
    composeTestRule.setContent {
        navController.setGraph(startDestination = HomeRoute) {
            ordersGraph(navController, onNavigateToProfile = {})
        }
    }
    navController.navigate(OrderDetailRoute("123"))
    composeTestRule.onNodeWithText("Order #123").assertIsDisplayed()
}
```

Each feature module tests its own graph without loading the entire app.

## Deep linking across modules

Type-safe routes make deep links composable across feature modules:

```kotlin
// app module — central deep link handler
NavHost(navController, startDestination = HomeRoute) {
    homeGraph(navController)
    ordersGraph(navController, onNavigateToProfile = { navController.navigate(ProfileRoute(it)) })
    profileGraph(navController)
}

// AndroidManifest.xml — single activity, multiple path patterns
<intent-filter android:autoVerify="true">
    <data android:scheme="https" android:host="app.example.com" android:pathPrefix="/orders" />
</intent-filter>
```

Each feature module declares its own `NavGraphBuilder` extension and path patterns. The app module wires them together — feature modules never import each other directly.

Handle invalid deep link args gracefully:

```kotlin
composable<OrderDetailRoute> { entry ->
    val orderId = entry.toRoute<OrderDetailRoute>().orderId
    if (orderId.isBlank()) {
        InvalidDeepLinkScreen(onNavigateUp = { navController.popBackStack() })
    } else {
        OrderDetailScreen(orderId = orderId)
    }
}
```

## Module dependency rules

Enforce acyclic dependencies with Gradle dependency analysis or custom lint:

```
:app → :feature:* → :core:navigation, :core:ui, :core:data
:feature:orders ↛ :feature:profile  (no cross-feature imports)
```

Navigation interfaces live in `:core:navigation` as route data classes. Feature modules depend on core, not on each other. Cross-feature navigation uses lambda callbacks passed from the app module:

```kotlin
// app module wires cross-feature navigation
ordersGraph(
    navController = navController,
    onNavigateToProfile = { userId -> navController.navigate(ProfileRoute(userId)) }
)
```

## Migration from single-module navigation

Incremental path from monolith NavHost:

1. Extract route data classes to `:core:navigation`
2. Move one feature's composables + ViewModels to `:feature:X`
3. Replace inline composables with `featureXGraph()` extension
4. Repeat per feature; app module shrinks to wiring only
5. Add module isolation tests per feature graph

Don't extract all features at once — migrate one vertical slice (e.g., orders) end-to-end first.

## Failure modes

- **Cross-feature module imports** — circular dependencies; use callback navigation
- **Shared ViewModel across features** — scope to app-level graph, not feature module
- **Deep link routes not in feature module** — broken links when module not loaded
- **Navigation args not type-safe** — runtime crashes on malformed deep links
- **Testing full app for feature nav bugs** — slow tests; isolate per-module graph tests

## Production checklist

- Route data classes in shared `:core:navigation` module
- No direct imports between feature modules
- Cross-feature navigation via app-module callbacks
- Deep link intent filters per feature path prefix
- Invalid deep link args handled with fallback screen
- Each feature module has isolated navigation tests

## Common production mistakes

Teams get multi module navigation compose wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping multi module navigation compose on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Resources

- [Compose Navigation typed routes](https://developer.android.com/guide/navigation/design/type-safety)
- [Navigation with Compose](https://developer.android.com/develop/ui/compose/navigation)
- [Guide to app modularization](https://developer.android.com/topic/modularization)
- [Android modularization strategy](https://blog.michaelsam94.com/android-modularization-strategy/)
- [Navigation 3 Jetpack Compose](https://blog.michaelsam94.com/navigation-3-jetpack-compose/)
