---
title: "Scoping ViewModels to Navigation Graphs"
slug: "android-viewmodel-scoping-navigation"
description: "Scope ViewModels to navigation graphs in Android: shared ViewModels across destinations, nested nav graphs, Hilt integration, and avoiding stale state."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Android", "Architecture", "Navigation", "Hilt"]
keywords: "ViewModel navigation scope, shared ViewModel navigation graph, nested nav graph ViewModel, hiltViewModel navigation, Navigation Compose ViewModel scope"
faq:
  - q: "How do you share a ViewModel between destinations in a navigation graph?"
    a: "Scope the ViewModel to a parent NavBackStackEntry — typically the nav graph's entry rather than an individual destination's entry. In Compose, pass the parent backStackEntry to hiltViewModel() or viewModel(). All composables within that graph share the same ViewModel instance."
  - q: "What is the default ViewModel scope in Navigation Compose?"
    a: "By default, hiltViewModel() scopes the ViewModel to the current destination's NavBackStackEntry. When the destination is popped, the ViewModel is cleared. To share across destinations, explicitly pass a parent backStackEntry from the nav graph route."
  - q: "When should ViewModels be scoped to the nav graph vs the Activity?"
    a: "Scope to the nav graph when state should persist across related screens (checkout flow, multi-step form) but clear when leaving the flow. Scope to the Activity only for truly global state (user session) — prefer a shared repository or singleton for that instead."
---

By default, every destination in your nav graph gets its own ViewModel — and when you pop that destination, the ViewModel dies with it. That's correct for independent screens but wrong for multi-step flows where a checkout ViewModel needs to survive from cart → shipping → payment → confirmation. Scoping ViewModels to navigation graphs lets related screens share state without passing arguments through every route. The API is a one-line change (`hiltViewModel(parentEntry)` instead of `hiltViewModel()`), but getting the parent entry wrong is the most common navigation bug I see in code review.

## Default scoping (per destination)

```kotlin
composable<CartRoute> {
    val viewModel: CartViewModel = hiltViewModel()  // scoped to CartRoute
    CartScreen(viewModel)
}
// ViewModel cleared when CartRoute is popped
```

Each destination gets its own instance. State doesn't leak between screens — but also doesn't persist when navigating within a flow.

## Shared ViewModel across a flow

Scope to the parent nav graph entry:

```kotlin
navigation<CheckoutGraph>(startDestination = CartRoute) {
    composable<CartRoute> { entry ->
        val parentEntry = remember(entry) {
            navController.getBackStackEntry<CheckoutGraph>()
        }
        val checkoutVm: CheckoutViewModel = hiltViewModel(parentEntry)
        CartScreen(checkoutVm)
    }

    composable<ShippingRoute> { entry ->
        val parentEntry = remember(entry) {
            navController.getBackStackEntry<CheckoutGraph>()
        }
        val checkoutVm: CheckoutViewModel = hiltViewModel(parentEntry)
        ShippingScreen(checkoutVm)
    }

    composable<PaymentRoute> { entry ->
        val parentEntry = remember(entry) {
            navController.getBackStackEntry<CheckoutGraph>()
        }
        val checkoutVm: CheckoutViewModel = hiltViewModel(parentEntry)
        PaymentScreen(checkoutVm)
    }
}
```

All three screens share one `CheckoutViewModel` instance. Cart selections persist when navigating to shipping. ViewModel clears when the entire checkout graph is popped.

## Extract the pattern

Avoid repeating parent entry lookup:

```kotlin
@Composable
inline fun <reified T : Any> NavBackStackEntry.sharedViewModel(
    navController: NavController
): CheckoutViewModel {
    val parentEntry = remember(this) {
        navController.getBackStackEntry<T>()
    }
    return hiltViewModel(parentEntry)
}

// Usage
composable<ShippingRoute> { entry ->
    val vm = entry.sharedViewModel<CheckoutGraph>(navController)
    ShippingScreen(vm)
}
```

## ViewModel holds flow state

```kotlin
@HiltViewModel
class CheckoutViewModel @Inject constructor(
    private val orderRepository: OrderRepository,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {
    var cartItems by savedStateHandle.saveable { mutableStateOf(listOf<CartItem>()) }
    var shippingAddress by savedStateHandle.saveable { mutableStateOf<Address?>(null) }
    var paymentMethod by savedStateHandle.saveable { mutableStateOf<PaymentMethod?>(null) }

    fun submitOrder() = viewModelScope.launch {
        orderRepository.createOrder(cartItems, shippingAddress!!, paymentMethod!!)
    }
}
```

State survives navigation within the graph and [process death](https://blog.michaelsam94.com/android-savedstatehandle-process-death/) via SavedStateHandle.

## Nested graphs

For deeply nested flows, scope to the nearest meaningful graph:

```
AppNavHost
├── HomeGraph (shared HomeViewModel)
├── CheckoutGraph (shared CheckoutViewModel)
│   ├── CartRoute
│   ├── ShippingRoute
│   └── PaymentRoute
└── ProfileGraph (shared ProfileViewModel)
    ├── ProfileRoute
    └── SettingsRoute
```

Each graph has its own shared ViewModel. Navigating from Checkout to Profile clears CheckoutViewModel (graph popped) but doesn't affect HomeViewModel.

## Multi-module navigation

In [multi-module setups](https://blog.michaelsam94.com/android-multi-module-navigation-compose/), the shared ViewModel class lives in the feature module:

```kotlin
// feature/checkout/CheckoutViewModel.kt
@HiltViewModel
class CheckoutViewModel @Inject constructor(...) : ViewModel()

// feature/checkout/CheckoutNavGraph.kt
composable<CartRoute> { entry ->
    val vm: CheckoutViewModel = hiltViewModel(
        navController.getBackStackEntry<CheckoutGraph>()
    )
    CartScreen(vm)
}
```

The app module doesn't need to know about CheckoutViewModel — it just includes the checkout graph.

## Common mistakes

**Scoping to Activity for everything.** Activity-scoped ViewModels survive all navigation — state from a checkout flow leaks into unrelated screens. Scope to the graph, not the Activity.

**Forgetting `remember` on parent entry lookup.** Without `remember`, you look up the parent entry on every recomposition — wasteful and can cause ViewModel recreation.

**Not clearing graph state on completion.** After order submission, pop the entire checkout graph so the ViewModel clears. Don't leave stale cart items for the next checkout.

## Navigation graph scoping patterns

Three scoping levels for different use cases:

```kotlin
// 1. Route-scoped: ViewModel tied to single screen
composable<DetailRoute> { entry ->
    val vm: DetailViewModel = hiltViewModel(entry)
}

// 2. Nested graph-scoped: shared across flow steps
navigation<CheckoutGraph>(startDestination = CartRoute) {
    composable<CartRoute> { entry ->
        val vm: CheckoutViewModel = hiltViewModel(
            navController.getBackStackEntry<CheckoutGraph>()
        )
    }
    composable<PaymentRoute> { entry ->
        val vm: CheckoutViewModel = hiltViewModel(
            navController.getBackStackEntry<CheckoutGraph>()
        )
    }
}

// 3. Activity-scoped: survives all navigation (use sparingly)
composable<HomeRoute> {
    val vm: SessionViewModel = hiltViewModel(LocalContext.current as ComponentActivity)
}
```

Rule: scope to the smallest graph that needs shared state. Checkout flow → checkout graph. Single screen → route entry.

## SavedStateHandle with navigation args

Navigation args survive process death via SavedStateHandle:

```kotlin
@HiltViewModel
class OrderDetailViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    repository: OrderRepository,
) : ViewModel() {
    private val orderId: String = savedStateHandle["orderId"]
        ?: throw IllegalArgumentException("orderId required")

    val order = repository.getOrder(orderId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)
}
```

Type-safe navigation routes automatically populate SavedStateHandle — no manual argument extraction needed.

## Clearing graph state on flow completion

Pop the entire graph when flow completes to destroy scoped ViewModels:

```kotlin
fun onOrderComplete(navController: NavController) {
    navController.popBackStack<CheckoutGraph>(inclusive = true)
    // CheckoutViewModel destroyed; fresh state on next checkout
}

// Alternative: navigate to success screen outside checkout graph
navController.navigate(OrderSuccessRoute(orderId)) {
    popUpTo<CheckoutGraph> { inclusive = true }
}
```

Without graph pop, cart items and payment state persist for the next checkout session.

## Failure modes

- **Activity-scoped for flow state** — checkout state leaks into unrelated screens
- **Graph not popped on completion** — stale cart/payment data on next flow
- **Parent entry lookup without remember** — ViewModel recreated on recomposition
- **Different graph scopes in same flow** — two CheckoutViewModel instances; state not shared
- **SavedStateHandle args not type-safe** — runtime crash on missing argument

## Production checklist

- ViewModel scoped to smallest necessary navigation graph
- Graph popped (inclusive) on flow completion
- `remember` wraps parent back stack entry lookup
- SavedStateHandle used for navigation args (survives process death)
- Activity scope only for truly global state (session, theme)
- Multi-module: ViewModel in feature module, scoped via graph extension

Scope ViewModels to NavBackStackEntry, not Activity — configuration changes and process death behave differently than activity-scoped state.

When using nested navigation graphs, pass the correct `NavBackStackEntry` from the destination — scoping to the parent graph entry shares ViewModels across sibling screens unintentionally.

## Resources

- [ViewModel scope in Navigation (Android)](https://developer.android.com/topic/libraries/architecture/viewmodel/viewmodel-navgraph)
- [Navigation with Compose](https://developer.android.com/develop/ui/compose/navigation)
- [Hilt ViewModel documentation](https://developer.android.com/training/dependency-injection/hilt-jetpack#viewmodels)
- [Multi-module navigation with Compose](https://blog.michaelsam94.com/android-multi-module-navigation-compose/)
- [SavedStateHandle process death](https://blog.michaelsam94.com/android-savedstatehandle-process-death/)
