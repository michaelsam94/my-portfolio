---
title: "Hilt Dependency Injection Patterns for Large Apps"
slug: "hilt-dependency-injection-patterns"
description: "Hilt dependency injection patterns for large Android apps: module organization, scopes, qualifiers, testing, and how to keep DI fast in a modularized codebase."
datePublished: "2026-04-15"
dateModified: "2026-04-15"
tags: ["Android", "Hilt", "Dependency Injection", "Architecture"]
keywords: "Hilt, Dagger Hilt, dependency injection Android, Hilt modules, DI patterns, scopes, qualifiers"
faq:
  - q: "What's the difference between Hilt and Dagger?"
    a: "Hilt is a layer on top of Dagger that provides a standard set of components and scopes tied to Android lifecycles, plus generated code that removes most of the boilerplate. You still get Dagger's compile-time correctness and performance, but you write far less wiring."
  - q: "How should I organize Hilt modules in a large app?"
    a: "Organize modules by feature and by layer, install them in the narrowest component that makes sense, and prefer @Binds over @Provides for interface-to-implementation bindings. In a modularized app, each feature module owns its own Hilt modules rather than a single god-module."
  - q: "When should I use a custom Hilt scope?"
    a: "Use built-in scopes (@Singleton, @ActivityRetainedScoped, @ViewModelScoped) for the common cases. Reach for a custom scope only when you have a genuinely bounded lifecycle the built-ins don't model — like a signed-in user session that outlives an Activity but not the process."
---

Dependency injection stops being about "how do I get an instance here" and starts being about architecture once an app gets large and modularized. Hilt is the standard answer on Android, and it's a good one — it wraps Dagger's compile-time safety in a set of components tied to Android lifecycles so you write configuration instead of plumbing. But Hilt in a 40-module app looks nothing like Hilt in a tutorial. These are the patterns that kept DI maintainable and fast as the apps I've worked on grew.

The short version: install bindings in the narrowest component you can, organize modules by feature and layer, use scopes deliberately, and design for testability from the start. Get those right and Hilt fades into the background, which is exactly what a DI framework should do.

## Modules: bind, don't provide, when you can

The most common Hilt module maps an interface to an implementation. Use `@Binds` for that, not `@Provides` — `@Binds` generates less code and is faster to build because Hilt just records the mapping rather than generating a factory that calls your provider:

```kotlin
@Module
@InstallIn(SingletonComponent::class)
abstract class ChargeDataModule {

    @Binds
    abstract fun bindChargeRepository(
        impl: ChargeRepositoryImpl,
    ): ChargeRepository
}
```

Reserve `@Provides` for things you can't `@Binds` — types you don't own (a Retrofit service, an OkHttpClient), or objects that need construction logic:

```kotlin
@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    @Provides
    @Singleton
    fun okHttp(): OkHttpClient = OkHttpClient.Builder()
        .addInterceptor(AuthInterceptor())
        .build()

    @Provides
    @Singleton
    fun chargeApi(client: OkHttpClient): ChargeApi =
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(client)
            .build()
            .create()
}
```

## Install in the narrowest component

`SingletonComponent` is tempting for everything because it always works — but a binding installed there lives for the whole process. For anything tied to a shorter lifecycle, install it where it belongs. This is both a correctness and a memory concern:

| Component | Lifetime | Scope annotation |
| --- | --- | --- |
| `SingletonComponent` | Process | `@Singleton` |
| `ActivityRetainedComponent` | Survives config change | `@ActivityRetainedScoped` |
| `ViewModelComponent` | One ViewModel | `@ViewModelScoped` |
| `ActivityComponent` | One Activity | `@ActivityScoped` |

A repository backing a single feature's ViewModel should be `@ViewModelScoped`, not `@Singleton` — otherwise it and everything it holds stays alive after the user leaves the feature. I've traced more than one memory leak to a "convenient" `@Singleton` that should have been scoped tighter.

## Qualifiers for the "two of the same type" problem

Large apps inevitably need two `OkHttpClient`s (one authenticated, one not) or two `CoroutineDispatcher`s. Dagger can't tell them apart by type, so you disambiguate with qualifiers:

```kotlin
@Qualifier annotation class AuthedClient
@Qualifier annotation class IoDispatcher

@Provides @AuthedClient @Singleton
fun authedClient(auth: AuthInterceptor): OkHttpClient = /* ... */

@Provides @IoDispatcher
fun ioDispatcher(): CoroutineDispatcher = Dispatchers.IO
```

Injecting a `@IoDispatcher CoroutineDispatcher` instead of hard-coding `Dispatchers.IO` also makes coroutine code testable — you swap in a test dispatcher — which connects directly to the [coroutines and Flow patterns](https://blog.michaelsam94.com/kotlin-coroutines-flow-patterns/) that dominate a modern data layer.

## Modularization: each feature owns its wiring

In a modularized codebase, resist the single-god-module temptation. Each feature module ships its own Hilt module declaring its bindings, installed in the appropriate component. The app module wires nothing about features it doesn't know about; features are self-contained. This keeps build parallelism healthy — a change to one feature's DI doesn't invalidate everything — which matters a lot for [Gradle build speed](https://blog.michaelsam94.com/faster-gradle-builds/) as the module count climbs.

A pattern that scales well: expose bindings across module boundaries through interfaces in an `:api` module, with the `:impl` module providing the `@Binds`. Consumers depend only on `:api`, so implementation changes don't ripple. That's the same [clean architecture](https://blog.michaelsam94.com/clean-architecture-pragmatically/) boundary thinking applied to DI.

## Testing is where Hilt earns its keep

The whole point of DI is swapping implementations, and Hilt makes test doubles clean. Replace a module for a test with `@TestInstallIn`, or use `@BindValue` for a quick per-test fake:

```kotlin
@HiltAndroidTest
class ChargeFlowTest {
    @get:Rule val hiltRule = HiltAndroidRule(this)

    @BindValue @JvmField
    val repo: ChargeRepository = FakeChargeRepository()

    @Test fun startsSession() { /* drives UI against the fake */ }
}
```

For unit tests, don't even involve Hilt — construct the class under test with constructor injection and pass fakes directly. Constructor injection (annotate the constructor with `@Inject`) is the pattern to default to everywhere precisely because it makes the class usable with *or* without the framework. Field injection should be limited to the few places you don't own construction, like Activities and Fragments.

## The habits that keep it healthy

- Prefer **constructor injection** everywhere; field injection only for framework-created classes.
- Install bindings in the **narrowest component**; audit every `@Singleton`.
- Use `@Binds` for interface→impl, `@Provides` only when you must.
- Give each **feature module** its own Hilt modules; wire across boundaries via `:api` interfaces.
- Inject **dispatchers** and clients via qualifiers so tests can swap them.
- Reach for **custom scopes** rarely — a user-session scope is a legitimate case, most others aren't.

Hilt won't fix a bad architecture, but it will faithfully reflect a good one. When DI starts feeling painful — circular dependencies, giant modules, everything a singleton — it's usually the architecture talking, not the tool. Treat the friction as a signal to look at your boundaries, and the DI setup mostly writes itself.

Use `@ViewModelScoped` for state shared across child fragments — activity-scoped ViewModels leak memory in deep navigation stacks.

## Resources

- [Hilt dependency injection guide](https://developer.android.com/training/dependency-injection/hilt-android)
- [Hilt and Dagger annotations cheat sheet](https://developer.android.com/training/dependency-injection/hilt-cheatsheet)
- [Hilt testing guide](https://developer.android.com/training/dependency-injection/hilt-testing)
- [Dagger documentation](https://dagger.dev/)
- [Modularization guidance](https://developer.android.com/topic/modularization)
- [Android developers blog](https://android-developers.googleblog.com/)

*Untangling DI in a large modular Android app? [Let's talk](/#contact).*
