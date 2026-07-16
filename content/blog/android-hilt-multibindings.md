---
title: "Multibindings and Plugins with Hilt"
slug: "android-hilt-multibindings"
description: "Use Hilt multibindings for plugin architectures: @IntoSet, @IntoMap, @ElementsIntoSet, and building extensible Android apps with Dagger multibindings."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Android", "Hilt", "Dependency Injection", "Architecture"]
keywords: "Hilt multibindings, Dagger IntoSet IntoMap, plugin architecture Android, Hilt extensible modules, multibindings Dagger"
faq:
  - q: "What are Dagger multibindings?"
    a: "Multibindings let multiple @Provides/@Binds methods contribute to a single collection (Set or Map) that Dagger assembles at compile time. Use @IntoSet to add elements to a Set, @IntoMap with @StringKey/@ClassKey to add entries to a Map. The consumer injects Set<Interface> or Map<Key, Interface> and gets all contributions."
  - q: "When should I use multibindings in an Android app?"
    a: "Use multibindings for plugin architectures where features contribute handlers, formatters, or interceptors without the core module knowing about them. Examples: payment method handlers, analytics event loggers, navigation destinations, and initialization tasks. Each feature module contributes its implementation; the app module collects them."
  - q: "How do multibindings work with Hilt modules across Gradle modules?"
    a: "Each feature module defines its own @Module with @IntoSet or @IntoMap contributions. Hilt aggregates all modules installed in the same component at compile time. The app module injects the combined Set or Map. Feature modules don't depend on each other — they depend only on the shared interface."
---

Multibindings are how you build plugin architectures in Hilt without the core module importing every feature module. Instead of a giant `when` statement that knows about every payment handler, analytics logger, or navigation destination, each feature module contributes its implementation to a shared `Set` or `Map`, and the app collects them at compile time. I've used this pattern for payment method plugins (Stripe, PayPal, Google Pay each in their own module), analytics providers, and app initialization tasks. The core module defines the interface; feature modules contribute implementations; Hilt wires the collection.

## Set multibindings

Multiple modules contribute to a `Set<Interface>`:

```kotlin
// core module — defines the interface
interface PaymentHandler {
    val providerId: String
    suspend fun processPayment(amount: Cents): PaymentResult
}

// feature-stripe module
@Module
@InstallIn(SingletonComponent::class)
abstract class StripeModule {
    @Binds
    @IntoSet
    abstract fun bindStripeHandler(impl: StripePaymentHandler): PaymentHandler
}

// feature-paypal module
@Module
@InstallIn(SingletonComponent::class)
abstract class PayPalModule {
    @Binds
    @IntoSet
    abstract fun bindPayPalHandler(impl: PayPalPaymentHandler): PaymentHandler
}

// app module — consumes the set
class PaymentCoordinator @Inject constructor(
    private val handlers: Set<@JvmSuppressWildcards PaymentHandler>
) {
    fun getHandler(providerId: String): PaymentHandler =
        handlers.first { it.providerId == providerId }
}
```

Adding a new payment method = adding a new module with one `@Binds @IntoSet` method. Zero changes to existing code.

## Map multibindings

When you need keyed lookup:

```kotlin
@Module
@InstallIn(SingletonComponent::class)
abstract class AnalyticsModule {
    @Binds
    @IntoMap
    @StringKey("firebase")
    abstract fun bindFirebase(impl: FirebaseAnalyticsProvider): AnalyticsProvider

    @Binds
    @IntoMap
    @StringKey("amplitude")
    abstract fun bindAmplitude(impl: AmplitudeAnalyticsProvider): AnalyticsProvider
}

class AnalyticsDispatcher @Inject constructor(
    private val providers: Map<String, @JvmSuppressWildcards AnalyticsProvider>
) {
    fun track(event: String, props: Map<String, Any>) {
        providers.values.forEach { it.track(event, props) }
    }
}
```

Use `@ClassKey` for type-based lookup:

```kotlin
@Binds @IntoMap @ClassKey(StepsRecord::class)
abstract fun bindStepsFormatter(impl: StepsFormatter): HealthDataFormatter
```

## Initialization plugins

A common pattern — each module contributes startup tasks:

```kotlin
interface AppInitializer {
    val priority: Int  // lower = earlier
    suspend fun initialize()
}

@Module
@InstallIn(SingletonComponent::class)
abstract class InitializerModule {
    @Binds @IntoSet
    abstract fun bindAnalyticsInit(impl: AnalyticsInitializer): AppInitializer

    @Binds @IntoSet
    abstract fun bindDatabaseInit(impl: DatabaseInitializer): AppInitializer

    @Binds @IntoSet
    abstract fun bindConfigInit(impl: RemoteConfigInitializer): AppInitializer
}

class AppStartup @Inject constructor(
    private val initializers: Set<@JvmSuppressWildcards AppInitializer>
) {
    suspend fun initializeAll() {
        initializers.sortedBy { it.priority }.forEach { it.initialize() }
    }
}
```

Each feature module owns its initialization. The app module runs them in priority order. No `Application.onCreate()` sprawl.

## Qualifiers for disambiguation

When multiple implementations of the same type exist outside multibindings:

```kotlin
@Qualifier
@Retention(AnnotationRetention.BINARY)
annotation class IoDispatcher

@Qualifier
@Retention(AnnotationRetention.BINARY)
annotation class MainDispatcher

@Module
@InstallIn(SingletonComponent::class)
object DispatcherModule {
    @Provides @IoDispatcher
    fun provideIo(): CoroutineDispatcher = Dispatchers.IO

    @Provides @MainDispatcher
    fun provideMain(): CoroutineDispatcher = Dispatchers.Main
}
```

Qualifiers and multibindings solve different problems. Use qualifiers for "which one" (two Dispatchers). Use multibindings for "all of them" (all PaymentHandlers).

## Modularization enabler

Multibindings shine in multi-module architectures:

```
:app (collects everything)
├── :core (interfaces + coordinator)
├── :feature-payments-stripe (@IntoSet contribution)
├── :feature-payments-paypal (@IntoSet contribution)
├── :feature-analytics-firebase (@IntoSet contribution)
└── :feature-analytics-amplitude (@IntoSet contribution)
```

Feature modules depend on `:core` interfaces only. They don't depend on each other. The app module depends on all feature modules. Hilt aggregates at compile time.

This pairs directly with [modularization strategy](https://blog.michaelsam94.com/android-modularization-strategy/) — multibindings are the DI glue between modules.

## Testing

Replace the entire set in tests:

```kotlin
@Module
@TestInstallIn(components = [SingletonComponent::class], replaces = [StripeModule::class, PayPalModule::class])
abstract class FakePaymentModule {
    @Binds @IntoSet
    abstract fun bindFake(impl: FakePaymentHandler): PaymentHandler
}
```

Or inject fakes directly without Hilt:

```kotlin
val coordinator = PaymentCoordinator(setOf(FakeStripeHandler(), FakePayPalHandler()))
```

## Common pitfalls

**Ordering assumptions.** `Set` iteration order is undefined unless you use `@ElementsIntoSet` with explicit ordering or sort by priority. Don't rely on module compilation order.

**Duplicate keys in maps.** Dagger fails at compile time if two modules contribute the same `@StringKey` — this is a feature, not a bug.

**Forgetting `@JvmSuppressWildcards`.** Kotlin's `Set<PaymentHandler>` needs `@JvmSuppressWildcards` on the injection site for Java interop. Dagger handles this, but ktlint may flag it.

**Over-using multibindings.** A set of 3 items that never changes doesn't need multibindings — a simple module with `@Provides fun provideHandlers(): Set<Handler>` is clearer. Multibindings pay off at 4+ contributors across modules.

## Multibindings into Set

```kotlin
@IntoSet
@Binds
abstract fun bindAnalytics(impl: FirebaseAnalytics): AnalyticsProvider
```

Inject `Set<AnalyticsProvider>` — iterate all implementations. Order not guaranteed — use `@IntoMap` with `@StringKey` when order or lookup needed.

## Common production mistakes

Teams get hilt multibindings wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping hilt multibindings on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Debugging and triage workflow

When hilt multibindings misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Dagger multibindings documentation](https://dagger.dev/dev-guide/multibindings.html)
- [Hilt module documentation](https://developer.android.com/training/dependency-injection/hilt-android)
- [Hilt dependency injection patterns](https://blog.michaelsam94.com/hilt-dependency-injection-patterns/)
- [Android modularization strategy](https://blog.michaelsam94.com/android-modularization-strategy/)
- [Assisted injection with Hilt](https://blog.michaelsam94.com/android-hilt-assisted-injection/)
