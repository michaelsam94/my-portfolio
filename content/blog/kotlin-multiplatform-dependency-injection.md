---
title: "Dependency Injection in KMP"
slug: "kotlin-multiplatform-dependency-injection"
description: "Dependency injection patterns for Kotlin Multiplatform: Koin, KMP DI frameworks, manual composition root, and scoping ViewModels across Android and iOS."
datePublished: "2025-12-19"
dateModified: "2025-12-19"
tags: ["Android", "Kotlin"]
keywords: "KMP dependency injection, Koin multiplatform, KMP DI, ViewModel injection, composition root, expect actual DI"
faq:
  - q: "Does Hilt work in Kotlin Multiplatform shared code?"
    a: "No. Hilt is Android/JVM-specific and relies on annotation processing tied to Android components. Shared KMP code should use Koin, kotlin-inject, Metro, or manual constructor injection with a platform-provided composition root."
  - q: "What is the simplest DI approach for small KMP projects?"
    a: "Constructor injection plus a single AppGraph object in commonMain that wires interfaces to implementations. Platform entry points call AppGraph.init with platform modules for dispatchers, database drivers, and HTTP engines."
  - q: "How do I inject platform ViewModels on Android and iOS?"
    a: "Define ViewModels or presenters in commonMain with shared use cases injected. Android uses androidx ViewModel with a KMP-friendly factory; iOS uses helpers that expose StateFlow or wraps shared logic in observable objects from Swift."
---

Dagger graphs don't compile in `commonMain`. That single fact drives every DI decision in Kotlin Multiplatform. Teams that copy-paste Hilt modules into shared code hit a wall; teams that pick a KMP-native approach wire once and ship Android and iOS from the same graph.

Dependency injection in KMP means **constructor injection in shared code** and a **composition root** that differs per platform only where it must—dispatchers, SQLite drivers, keychain storage.

## Manual graph (works everywhere)

```kotlin
// commonMain
object AppGraph {
    lateinit var config: PlatformConfig
        private set

    fun init(config: PlatformConfig) {
        this.config = config
    }

    private val httpClient by lazy { createHttpClient(config) }
    val userRepository: UserRepository by lazy {
        UserRepositoryImpl(httpClient, config.userStore)
    }
    val loginUseCase by lazy { LoginUseCase(userRepository) }
}

interface PlatformConfig {
    val userStore: UserStore
    val ioDispatcher: CoroutineDispatcher
}
```

```kotlin
// androidMain
class AndroidPlatformConfig(
    override val userStore: UserStore,
    override val ioDispatcher: CoroutineDispatcher = Dispatchers.IO
) : PlatformConfig

// Application.onCreate
AppGraph.init(AndroidPlatformConfig(DataStoreUserStore(context)))
```

```kotlin
// iosMain — called from Swift app init
fun initKmp() {
    AppGraph.init(IosPlatformConfig(IosUserStore()))
}
```

Explicit, testable, zero magic.

## Koin for KMP

Koin supports multiplatform modules:

```kotlin
// commonMain
val sharedModule = module {
    single<UserRepository> { UserRepositoryImpl(get(), get()) }
    factory { LoginUseCase(get()) }
    single { createHttpClient(get()) }
}

// androidMain
val androidModule = module {
    single<UserStore> { DataStoreUserStore(androidContext()) }
    viewModel { LoginViewModel(get()) }
}

// startKoin in Application
startKoin {
    modules(sharedModule, androidModule)
}
```

iOS starts Koin from `MainViewController` setup with `iosModule`.

Koin trades compile-time validation for runtime resolution—acceptable for many apps, less so for large teams wanting graph verification.

## kotlin-inject and Metro

Compile-time DI alternatives exist for KMP with varying maturity. **kotlin-inject** generates dependency graphs without reflection. **Metro** (Zac Sweers) targets similar ergonomics to Dagger for Kotlin. Evaluate based on team familiarity and build time tolerance.

## Scoping and lifecycle

| Scope | KMP pattern |
|-------|-------------|
| Singleton | `single` in Koin or lazy val in AppGraph |
| Activity/Screen | ViewModel scope on Android; iOS holder per screen |
| Request | Factory creating new instance per call |

Shared ViewModels:

```kotlin
class LoginViewModel(private val loginUseCase: LoginUseCase) : ViewModel() {
    // commonMain if using androidx.lifecycle ViewModel in KMP
}
```

Use `lifecycle-viewmodel-compose` multiplatform artifacts where available.

## Testing

Replace modules in tests:

```kotlin
@Test
fun login() = runTest {
    val fakeRepo = FakeUserRepository()
    val useCase = LoginUseCase(fakeRepo)
    assertTrue(useCase("a@b.c", "pass").isSuccess)
}
```

Koin: `startKoin { modules(testModule) }` with overrides.

## Anti-patterns

- Service locator `AppGraph.userRepository` scattered in Composables—pass via parameters or ViewModel
- Platform SDK imports in commonMain
- Different DI frameworks per platform for the same interfaces

Pick one graph definition in commonMain; platforms only supply `PlatformModule`.

## Testing with swapped modules

```kotlin
// commonTest
class FakeUserRepository : UserRepository { /* ... */ }

@Test
fun loginUseCase() {
    val useCase = LoginUseCase(FakeUserRepository())
}
```

Keep fakes in commonTest; platform tests only for SQLite/Keychain integrations.


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


## Common questions from reviewers

Reviewers and auditors often ask whether this approach scales with team growth and whether it fails safely. Answer explicitly in your design doc: what happens when dependencies are down, when credentials expire, and when traffic doubles overnight. Prefer defaults that deny or degrade gracefully over defaults that fail open. Document known limits (throughput ceilings, supported versions, regions) in the same place operators look during incidents—avoid scattering critical constraints across Slack threads.


## Version and compatibility notes

Pin library and control-plane versions in production manifests; track upstream release notes quarterly. Run upgrade drills in non-production before bumping minor versions that touch serialization, auth, or CRD schemas. Keep a compatibility matrix in your internal wiki listing supported Kubernetes, broker, and SDK versions validated together.

## Resources

- [Koin multiplatform documentation](https://insert-koin.io/docs/reference/koin-mp/kmp/) — module setup per target
- [Kotlin Multiplatform project structure](https://kotlinlang.org/docs/multiplatform-discover-project.html) — where DI fits
- [kotlin-inject GitHub](https://github.com/evant/kotlin-inject) — compile-time alternative
- [AndroidX ViewModel KMP](https://developer.android.com/kotlin/multiplatform/viewmodel) — sharing ViewModels across platforms
