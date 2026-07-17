---
title: "Dependency Injection with Koin on Android"
slug: "android-dependency-injection-koin"
description: "Set up Koin for dependency injection on Android: modules, scopes, ViewModel injection, testing with KoinTest, and when Koin beats Hilt."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Android", "Kotlin", "Dependency Injection", "Architecture"]
keywords: "Koin Android, Koin dependency injection, Koin vs Hilt, Koin ViewModel, Koin modules Android"
faq:
  - q: "What is Koin and how does it differ from Hilt?"
    a: "Koin is a lightweight DI framework for Kotlin using DSL and resolution by type, with no annotation processing or code generation. Hilt is Google's DI built on Dagger with compile-time validation and Android-specific scopes. Koin is faster to set up and has zero compile overhead; Hilt catches dependency errors at compile time and integrates deeply with Android lifecycle."
  - q: "When should I choose Koin over Hilt?"
    a: "Choose Koin for Kotlin Multiplatform projects (shared DI across Android and iOS), prototypes, or teams that prefer pure Kotlin DSL over annotations. Choose Hilt for large Android-only apps where compile-time safety, AssistedInject, and deep Android integration (WorkManager, Compose) matter."
  - q: "How do I inject ViewModels with Koin?"
    a: "Define ViewModels in a Koin module using viewModel { } or viewModelOf(::MyViewModel). Inject in Activities/Fragments with by viewModel() delegate, or in Compose with koinViewModel(). Koin automatically scopes ViewModels to the lifecycle owner."
---

Koin is what you reach for when Dagger's annotation processing feels like overkill — or when you need dependency injection that works identically on Android, iOS, and backend KMP modules. It's pure Kotlin DSL: define modules, declare how to construct things, resolve by type at runtime. No `@Inject`, no `@Component`, no kapt/ksp code generation. The trade-off is real: Koin catches missing dependencies at runtime, not compile time. I've used Koin on KMP projects where Hilt can't go, and Hilt on large Android apps where compile-time graphs save hours of debugging. Pick based on your constraints, not ideology.

## Setup

```kotlin
// Application.onCreate()
startKoin {
    androidContext(this@MyApp)
    modules(appModule, networkModule, databaseModule)
}
```

Dependencies:

```kotlin
dependencies {
    implementation("io.insert-koin:koin-android:3.5.6")
    implementation("io.insert-koin:koin-androidx-compose:3.5.6")
}
```

## Defining modules

```kotlin
val networkModule = module {
    single { HttpClientFactory.create() }
    single { ApiService(get()) }
}

val databaseModule = module {
    single { AppDatabase.build(androidContext()) }
    single { get<AppDatabase>().userDao() }
}

val appModule = module {
    single<UserRepository> { UserRepositoryImpl(get(), get()) }
    viewModel { UserViewModel(get()) }
    viewModel { params -> DetailViewModel(id = params.get(), repo = get()) }
}
```

| Declaration | Scope | Created |
|-------------|-------|---------|
| `single { }` | Application | Once |
| `factory { }` | None | Every injection |
| `viewModel { }` | ViewModelStore | Per ViewModel instance |

## Injection in Activities and Fragments

```kotlin
class UserActivity : AppCompatActivity() {
    private val viewModel: UserViewModel by viewModel()
    private val analytics: Analytics by inject()
}
```

## Injection in Compose

```kotlin
@Composable
fun UserScreen(viewModel: UserViewModel = koinViewModel()) {
    val users by viewModel.users.collectAsStateWithLifecycle()
    // ...
}
```

For parameterized ViewModels:

```kotlin
@Composable
fun DetailScreen(itemId: String, vm: DetailViewModel = koinViewModel { parametersOf(itemId) })
```

## Scopes

Koin supports custom scopes for lifecycle-bound dependencies:

```kotlin
val activityModule = module {
    scope<MainActivity> {
        scoped { SessionManager() }
        viewModel { MainViewModel(get()) }
    }
}

class MainActivity : AppCompatActivity() {
    private val scope = activityScope<MainActivity>()
    private val session: SessionManager by scope.inject()
}
```

For most apps, `single` + `viewModel` covers 90% of cases. Custom scopes are for session-bound or activity-bound objects that shouldn't live as singletons.

## KMP shared modules

Koin's killer feature for multiplatform:

```kotlin
// sharedModule — commonMain
val sharedModule = module {
    single { UserRepository(get()) }
    single<UserApi> { UserApiImpl(get()) }
}

// androidMain — adds platform deps
val androidModule = module {
    single { DatabaseDriverFactory(androidContext()) }
}

// iosMain
val iosModule = module {
    single { DatabaseDriverFactory() }
}
```

Same module definitions, platform-specific bindings. This is why Koin dominates KMP DI while Hilt is Android-only.

## Testing

```kotlin
class UserViewModelTest : KoinTest {
    @get:Rule
    val koinTestRule = KoinTestRule.create {
        modules(testModule)
    }

    private val testModule = module {
        single<UserRepository> { FakeUserRepository() }
        viewModel { UserViewModel(get()) }
    }

    @Test
    fun loadsUsers() = runTest {
        val vm: UserViewModel by inject()
        vm.loadUsers()
        assertEquals(2, vm.users.value.size)
    }
}
```

Override modules in tests without touching production code.

## Koin vs Hilt decision matrix

| Factor | Koin | Hilt |
|--------|------|------|
| Setup time | Minutes | Hours (first time) |
| Compile time | Zero overhead | kapt/ksp processing |
| Error detection | Runtime | Compile time |
| KMP support | Native | Android only |
| Android integration | Good | Deep (WorkManager, etc.) |
| Learning curve | Low (Kotlin DSL) | High (Dagger concepts) |
| Ecosystem | Smaller | Google-backed |

For large Android-only apps with 20+ modules, [Hilt's compile-time safety and multibindings](https://blog.michaelsam94.com/hilt-dependency-injection-patterns/) justify the overhead. For KMP, prototypes, or teams allergic to annotation processors, Koin is the pragmatic choice.

## Common pitfalls

**Missing dependency at runtime.** Koin throws `InstanceCreationException` in production. Mitigate with startup validation in debug builds that resolves all declared types.

**Over-using `single` for stateful objects.** Not everything should be a singleton. Use `factory` for objects with per-use state.

**Module organization sprawl.** One module per layer (network, database, feature) keeps things navigable. A single 500-line module doesn't scale.

## Koin Compose integration

Inject ViewModels and dependencies directly in composables:

```kotlin
@Composable
fun OrderScreen(viewModel: OrderViewModel = koinViewModel()) {
    val orders by viewModel.orders.collectAsStateWithLifecycle()
    OrderList(orders)
}

// Koin module
val featureModule = module {
    viewModel { OrderViewModel(get(), get()) }
    single { OrderRepository(get()) }
}

// Application/onCreate or commonMain
startKoin {
    modules(appModule, networkModule, featureModule)
}
```

`koinViewModel()` scopes ViewModel to navigation destination automatically with Navigation Compose integration.

## Koin on Kotlin Multiplatform

Shared business logic with platform-specific modules:

```kotlin
// commonMain
val sharedModule = module {
    single { UserRepository(get()) }
    factory { GetUserUseCase(get()) }
}

// androidMain
val androidModule = module {
    single<DatabaseDriver> { AndroidDatabaseDriver(context) }
    single { PlatformLogger() }
}

// iosMain
val iosModule = module {
    single<DatabaseDriver> { NativeDatabaseDriver() }
    single { PlatformLogger() }
}
```

KMP DI without Hilt — single DSL across all platforms. Platform modules provide expect/actual implementations.

## Koin testing

Replace modules in tests without Robolectric or instrumented tests:

```kotlin
class OrderViewModelTest : KoinTest {
    @get:Rule
    val koinTestRule = KoinTestRule.create {
        modules(testModule)
    }

    private val testModule = module {
        single { FakeOrderRepository() }
        viewModel { OrderViewModel(get()) }
    }

    @Test
    fun loadOrders_returnsList() = runTest {
        val vm = get<OrderViewModel>()
        vm.loadOrders()
        assertEquals(3, vm.orders.value.size)
    }
}
```

Runtime module swapping in tests — no @Mock annotations or manual constructor injection in test code.

## Failure modes

- **Missing dependency at runtime** — InstanceCreationException in production; validate at startup in debug
- **single scope for stateful objects** — shared mutable state; use factory for per-use instances
- **No startup validation** — missing binding discovered by users, not CI
- **500-line module** — unmaintainable; split by layer/feature
- **Koin on large Android-only app** — runtime errors vs Hilt compile-time safety

## Production checklist

- Modules organized by layer (network, database) and feature
- Startup validation in debug builds resolves all declared types
- factory scope for stateful objects; single for stateless services
- koinViewModel() used in Compose screens
- Test modules replace production modules via KoinTestRule
- KMP: platform-specific modules for expect/actual implementations

## Common production mistakes

Teams get dependency injection koin wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping dependency injection koin on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Module load order in multi-module apps

Feature modules defining duplicate `single {}` bindings crash at startup — namespace qualifiers (`named("auth")`) for colliding types. Koin `checkModules` in JVM test catches graph errors before instrumented run.

## Compose ViewModel scope

`koinViewModel()` in navigation back stack shares store per destination — verify `viewModelStoreOwner` is NavBackStackEntry, not Activity, or screens leak state across tabs.

## Dependency Injection Koin Supplement 0 on Samsung and Pixel divergence

Exercise dependency injection koin supplement 0 on Galaxy A-series and Pixel a-series — emulators hide OEM battery and storage quirks. Capture Macrobenchmark or Firebase trace for the critical path touching dependency; regressions above 8% block release for `android-dependency-injection-koin-supplement-0`.

Document permission and background behavior in internal runbook: what breaks under Doze, what requires foreground service, and what Play policy declarations apply. Support tickets referencing "Dependency Injection Koin Supplement 0" should map to a single runbook section with known workarounds.

## Koin regression gates for Play Vitals

Before promoting `android-dependency-injection-koin-supplement-0` changes past 20% rollout, compare ANR rate, slow cold start, and excessive wakeups against seven-day baseline. Fail rollback review if 0 path shows >5% increase in `slow frames` without documented trade-off approval.

## Field testing dependency with battery saver enabled

Xiaomi and Oppo ship aggressive background killers. After implementing dependency injection koin supplement 0, run 24-hour monkey test on three OEM devices with battery saver enabled. Failures here predict one-star reviews that Crashlytics never captures — especially for 0 flows that assume reliable background delivery.

## Resources

- [Koin documentation](https://insert-koin.io/docs/reference/koin-android/start)
- [Koin for Compose](https://insert-koin.io/docs/reference/koin-android/compose)
- [Koin Kotlin Multiplatform](https://insert-koin.io/docs/reference/koin-multiplatform/multiplatform)
- [Hilt dependency injection patterns](https://blog.michaelsam94.com/hilt-dependency-injection-patterns/)
- [Kotlin Multiplatform expect/actual patterns](https://blog.michaelsam94.com/kotlin-multiplatform-expect-actual-patterns/)
