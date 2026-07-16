---
title: "Faster App Init with the App Startup Library"
slug: "android-app-startup-library"
description: "Use the App Startup library to speed up Android cold start: replace ContentProvider init hacks with ordered initializers, and lazy-load the rest."
datePublished: "2026-06-21"
dateModified: "2026-06-21"
tags: ["Android", "Performance", "Startup"]
keywords: "App Startup library, initializer, ContentProvider init, Android cold start, startup performance"
faq:
  - q: "What is the App Startup library?"
    a: "The App Startup library is a Jetpack library that gives components a single, ordered way to initialize at app launch without each one shipping its own ContentProvider. You implement the Initializer interface, declare dependencies between initializers, and the library runs them in the correct order behind one shared ContentProvider. It reduces the hidden startup cost caused by many libraries each registering their own provider."
  - q: "Why are multiple ContentProviders bad for startup?"
    a: "Every ContentProvider declared in a manifest is instantiated and has onCreate called during application startup, before your first frame, and this happens serially on the main thread. Libraries historically abused ContentProviders as an automatic init hook, so an app pulling in a dozen such libraries pays a dozen provider creations at cold start. App Startup collapses those into one provider so you pay that cost once."
  - q: "Does App Startup support lazy initialization?"
    a: "Yes. You can mark an initializer as manual by removing its automatic entry from the manifest merge, then call AppInitializer.getInstance(context).initializeComponent(...) only when the feature is first needed. This lets you keep heavy or rarely used components out of the critical startup path and initialize them on demand instead."
---

Cold start is where users form their first, unforgiving impression of an app, and a surprising amount of that time is spent before your code even runs — in the parade of `ContentProvider.onCreate()` calls that libraries quietly register to initialize themselves. The App Startup library exists to fix exactly that. It replaces the "every library ships its own provider" pattern with a single shared `ContentProvider` that runs a set of ordered `Initializer` implementations, so you pay one provider cost instead of a dozen and you control the order and timing of initialization.

I've profiled cold starts where third-party providers accounted for a genuinely embarrassing slice of time-to-first-frame. App Startup won't make a slow SDK fast, but it removes the structural tax of provider proliferation and gives you a clean lever to defer the heavy stuff. Here's how to use it well.

## The problem: ContentProvider as an init hook

Here's the trick libraries use, and why it's expensive. A `ContentProvider` declared in the manifest is created — and its `onCreate` invoked — automatically during `Application` startup, before your first activity draws. So a library adds an invisible provider whose only job is to grab a `Context` and initialize itself:

```xml
<!-- What a library sneaks into your merged manifest -->
<provider
    android:name="com.somelib.SomeLibInitProvider"
    android:authorities="${applicationId}.somelib-init"
    android:exported="false" />
```

Multiply that by every analytics SDK, image loader, crash reporter, and DI framework in your dependency graph, and cold start runs a serial gauntlet of provider creations on the main thread — each one costing object allocation, class loading, and whatever work the library front-loads. None of it is visible in your code, which is what makes it so easy to miss until you open a trace.

## The fix: one provider, ordered initializers

App Startup gives you a single `InitializationProvider` and a typed interface. You implement `Initializer<T>`, and if one component needs another to run first, you declare that dependency explicitly:

```kotlin
class LoggerInitializer : Initializer<Logger> {
    override fun create(context: Context): Logger =
        Logger.configure(context).also { AppLog.instance = it }

    override fun dependencies(): List<Class<out Initializer<*>>> = emptyList()
}

class AnalyticsInitializer : Initializer<Analytics> {
    override fun create(context: Context): Analytics {
        // Logger is guaranteed initialized first because we depend on it
        return Analytics.start(context, AppLog.instance)
    }

    override fun dependencies() =
        listOf(LoggerInitializer::class.java)
}
```

You register the ones you want to run automatically in the manifest, all under the library's shared provider:

```xml
<provider
    android:name="androidx.startup.InitializationProvider"
    android:authorities="${applicationId}.androidx-startup"
    android:exported="false"
    tools:node="merge">
    <meta-data
        android:name="com.example.AnalyticsInitializer"
        android:value="androidx.startup" />
</provider>
```

Because `AnalyticsInitializer` depends on `LoggerInitializer`, you only list the leaf — App Startup walks the dependency graph and runs `LoggerInitializer` first. The ordering is a real feature: the old provider approach gave you no control over sequence, so init-order bugs between libraries were a coin flip.

## The bigger win: lazy initialization

Consolidating providers is nice, but the setting that actually moves the startup number is *not* initializing things at startup at all. App Startup lets you keep an initializer out of the automatic path and run it on demand. You mark the dependency's metadata entry to be removed from the merge, then initialize it lazily when the feature is first touched:

```kotlin
// Nothing runs at cold start for this one; call it when the feature opens
val analytics = AppInitializer.getInstance(context)
    .initializeComponent(AnalyticsInitializer::class.java)
```

This is the mindset shift I push on every startup review: **the fastest initialization is the one that doesn't happen before first frame.** Ask of every initializer, "does the first screen need this?" A crash reporter, yes — initialize early. A recommendation-engine SDK the user reaches on tab three? Defer it. Cold start is a budget, and lazy init is how you stop spending it on things nobody sees yet.

## App Startup vs the alternatives

App Startup isn't the only way to organize init. Where it fits:

| Approach | Runs when | Ordering | Best for |
| --- | --- | --- | --- |
| Per-library ContentProvider | Auto, at startup | None | Legacy libraries (avoid adding more) |
| Application.onCreate() | At startup, your code | Manual | A few app-owned, must-run tasks |
| App Startup (auto) | At startup, one provider | Declared graph | Consolidating library init with order |
| App Startup (lazy) | On first use | Declared graph | Deferring non-critical components |

For a small app, a handful of calls in `Application.onCreate()` is perfectly fine — don't add a library to initialize two things. App Startup earns its place when you have many components, real ordering constraints, or a library you're authoring that wants a clean init hook without inflicting yet another provider on consumers.

## Measure, don't guess

The honest caveat: App Startup organizes initialization; it doesn't magically make a heavy SDK cheap. The real gains come from *removing* work from the critical path, and you can only find that work by profiling. Capture a startup trace, look at what runs before your first frame, and attack the biggest costs — often that means moving a couple of initializers to lazy and pushing genuinely deferrable work to a background dispatcher after first frame.

App Startup is one tool in the cold-start toolbox, and it composes with the others. It pairs especially well with [baseline profiles for Android startup](https://blog.michaelsam94.com/baseline-profiles-android-startup/), which speed up the code that *does* run during launch by pre-compiling the hot paths — App Startup reduces how much runs, baseline profiles make what remains faster. And keeping init off the main thread ties directly into avoiding the main-thread stalls I cover in [killing ANRs and Android jank](https://blog.michaelsam94.com/killing-anrs-android-jank/); an initializer doing disk or network I/O synchronously at startup is both a slow cold start and a latent ANR.

My default stance: adopt App Startup when provider count or init ordering is a real problem, be ruthless about marking components lazy, and always validate against a trace rather than intuition. Startup performance is unglamorous, measured in milliseconds, and absolutely worth it — those milliseconds are the first thing every user feels.

## Resources

- [App Startup — official documentation](https://developer.android.com/topic/libraries/app-startup)
- [App Startup on GitHub (source)](https://github.com/androidx/androidx/tree/androidx-main/startup)
- [App startup time — performance guide](https://developer.android.com/topic/performance/vitals/launch-time)
- [Inspect app startup with tracing](https://developer.android.com/topic/performance/tracing)
- [ContentProvider reference](https://developer.android.com/reference/android/content/ContentProvider)
