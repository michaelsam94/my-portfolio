---
title: "Migrating an Android App to KMP"
slug: "android-kotlin-multiplatform-migration-guide"
description: "A pragmatic guide to migrating an existing Android app to Kotlin Multiplatform: what to share first, module structure, expect/actual, and incremental migration without a rewrite."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Android", "Kotlin Multiplatform", "Architecture", "Migration"]
keywords: "Android to KMP migration, Kotlin Multiplatform migration guide, KMP incremental migration, share code KMP, Android KMP strategy"
faq:
  - q: "Can I migrate an existing Android app to KMP incrementally?"
    a: "Yes — and you should. Don't rewrite. Extract shared logic (networking, repositories, business rules, data models) into a KMP shared module while keeping Android UI in place. Add iOS or other targets later. Each extraction is a small, shippable step that doesn't block feature development."
  - q: "What should I share first in a KMP migration?"
    a: "Start with data models and networking — they're platform-agnostic and high-value. Then repositories and business logic. UI is last (Compose Multiplatform or platform-native). Don't share Android-specific code (Room, ViewModels with SavedStateHandle, Compose with Android-only APIs)."
  - q: "How long does an Android to KMP migration take?"
    a: "Extracting the first shared module (models + API client) takes 1–2 weeks for a medium app. Full business logic sharing takes 1–3 months incrementally. Adding an iOS target with native UI adds another 2–4 months. The key is incremental delivery — each phase ships value without waiting for the full migration."
---

Migrating to Kotlin Multiplatform is not a rewrite — it's a series of extractions. You don't "convert your Android app to KMP." You peel off layers that don't need to be Android-specific — data models, API clients, repositories, business rules — into a shared module, one slice at a time, while the Android app keeps shipping features. I've guided three migrations from "pure Android" to "shared business logic + Android Compose UI + SwiftUI iOS UI." The ones that succeeded extracted bottom-up (data first, UI last) over months. The one that failed tried to rewrite everything into Compose Multiplatform in a single branch that never merged.

## Migration phases

```
Phase 1: Shared models + API client
Phase 2: Repositories + business logic
Phase 3: Platform abstractions (storage, auth, analytics)
Phase 4: Shared UI (optional — Compose Multiplatform)
Phase 5: iOS target (optional — native or CMP)
```

Each phase is independently valuable. Phase 1 alone makes your Android codebase cleaner even without an iOS target.

## Phase 1: Extract shared module

Create the KMP module structure:

```
project/
├── shared/
│   ├── build.gradle.kts
│   └── src/
│       ├── commonMain/kotlin/
│       ├── androidMain/kotlin/
│       └── iosMain/kotlin/
├── app/          (existing Android app)
└── settings.gradle.kts
```

```kotlin
// shared/build.gradle.kts
plugins {
    kotlin("multiplatform")
    kotlin("plugin.serialization")
    id("com.android.library")
}

kotlin {
    androidTarget()
    iosX64(); iosArm64(); iosSimulatorArm64()

    sourceSets {
        commonMain.dependencies {
            implementation("io.ktor:ktor-client-core:2.3.12")
            implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.7.1")
            implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.8.1")
        }
        androidMain.dependencies {
            implementation("io.ktor:ktor-client-okhttp:2.3.12")
        }
        iosMain.dependencies {
            implementation("io.ktor:ktor-client-darwin:2.3.12")
        }
    }
}
```

Move data models first:

```kotlin
// shared/commonMain — was in app module
@Serializable
data class User(val id: String, val name: String, val email: String)

@Serializable
data class Order(val id: String, val userId: String, val total: Double, val status: OrderStatus)

@Serializable
enum class OrderStatus { PENDING, SHIPPED, DELIVERED, CANCELLED }
```

Move the API client:

```kotlin
// shared/commonMain
class ApiClient(private val httpClient: HttpClient) {
    suspend fun getUser(id: String): User =
        httpClient.get("users/$id").body()

    suspend fun getOrders(userId: String): List<Order> =
        httpClient.get("users/$userId/orders").body()
}
```

Android app now depends on `:shared` instead of local models/client.

## Phase 2: Repositories and use cases

```kotlin
// shared/commonMain
class OrderRepository(private val api: ApiClient) {
    suspend fun getOrdersForUser(userId: String): Result<List<Order>> = runCatching {
        api.getOrders(userId)
    }

    fun isOrderCancellable(order: Order): Boolean =
        order.status == OrderStatus.PENDING
}
```

Android ViewModel becomes thin:

```kotlin
// app module — Android-specific
@HiltViewModel
class OrdersViewModel @Inject constructor(
    private val repository: OrderRepository  // from shared module
) : ViewModel() {
    val orders = flow { emit(repository.getOrdersForUser(userId)) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())
}
```

Business logic tests move to `shared/commonTest` — run on JVM without Android:

```kotlin
// shared/commonTest
@Test
fun cancellableOnlyForPending() {
    val repo = OrderRepository(FakeApiClient())
    assertTrue(repo.isOrderCancellable(Order("1", "u1", 10.0, OrderStatus.PENDING)))
    assertFalse(repo.isOrderCancellable(Order("2", "u1", 10.0, OrderStatus.SHIPPED)))
}
```

## Phase 3: Platform abstractions

For code that differs by platform, use [expect/actual](https://blog.michaelsam94.com/kotlin-multiplatform-expect-actual-patterns/):

```kotlin
// commonMain
expect class SecureStorage {
    suspend fun save(key: String, value: String)
    suspend fun load(key: String): String?
}

// androidMain
actual class SecureStorage(private val context: Context) {
    private val prefs = EncryptedSharedPreferences.create(/* ... */)
    actual suspend fun save(key: String, value: String) { prefs.edit { putString(key, value) } }
    actual actual suspend fun load(key: String): String? = prefs.getString(key, null)
}

// iosMain
actual class SecureStorage {
    actual suspend fun save(key: String, value: String) { /* Keychain */ }
    actual suspend fun load(key: String): String? { /* Keychain */ }
}
```

Abstract: storage, auth tokens, analytics, platform info, file paths. Don't abstract: UI, lifecycle, platform notifications (keep in app modules).

## What NOT to share (yet)

| Keep in Android module | Why |
|------------------------|-----|
| ViewModels with SavedStateHandle | Android lifecycle |
| Compose UI (Android-specific APIs) | Platform UI framework |
| Room database (directly) | Use SQLDelight in shared instead |
| WorkManager jobs | Android-specific scheduling |
| Hilt modules | Android DI; use Koin in shared |
| Navigation | Platform-specific |

For database sharing, migrate Room to [SQLDelight in KMP](https://blog.michaelsam94.com/kotlin-multiplatform-sqldelight/) as a separate step.

## Gradle configuration tips

Wire the shared module into the existing app:

```kotlin
// settings.gradle.kts
include(":shared", ":app")

// app/build.gradle.kts
dependencies {
    implementation(project(":shared"))
}
```

Use a shared version catalog for dependency alignment between modules. Keep AGP and Kotlin versions compatible with your KMP plugin version — check the [KMP compatibility table](https://kotlinlang.org/docs/multiplatform-compatibility-guide.html).

## iOS target (when ready)

Adding iOS doesn't require sharing UI:

```
shared (business logic)
├── app (Android — Compose UI)
└── iosApp (iOS — SwiftUI, calls shared via SKIE/Swift export)
```

Use [Swift interop](https://blog.michaelsam94.com/kotlin-multiplatform-swiftui-interop/) to call shared code from SwiftUI. The iOS app is a thin UI shell over shared repositories.

## Migration anti-patterns

**Big-bang rewrite.** Extracting one module per sprint is sustainable. A 6-month migration branch is not.

**Sharing too early.** Don't abstract platform code "just in case." Abstract when you have a second platform target confirmed.

**Moving ViewModels to shared.** ViewModels tie to lifecycle. Keep them in platform modules; share the repository/use case layer below.

**Ignoring test migration.** The biggest win from KMP is testing business logic on JVM. If you don't move tests to `commonTest`, you're sharing code without sharing test coverage.

## Common production mistakes

Teams get kotlin multiplatform migration guide wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping kotlin multiplatform migration guide on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Resources

- [Kotlin Multiplatform documentation](https://kotlinlang.org/docs/multiplatform.html)
- [KMP compatibility guide](https://kotlinlang.org/docs/multiplatform-compatibility-guide.html)
- [expect/actual patterns](https://blog.michaelsam94.com/kotlin-multiplatform-expect-actual-patterns/)
- [SQLDelight in KMP projects](https://blog.michaelsam94.com/kotlin-multiplatform-sqldelight/)
- [KMP production guide](https://blog.michaelsam94.com/kotlin-multiplatform-production-guide/)
