---
title: "Speeding Builds with the Gradle Configuration Cache"
slug: "gradle-configuration-cache"
description: "Enable the Gradle configuration cache to skip the configuration phase and speed up builds: how it works, common incompatibilities, and how to make tasks compliant."
datePublished: "2024-08-10"
dateModified: "2024-08-10"
tags: ["Gradle", "Build", "Performance", "Android"]
keywords: "Gradle configuration cache, configuration phase, configuration cache incompatible, Gradle build speed, project isolation, task configuration avoidance"
faq:
  - q: "What does the Gradle configuration cache do?"
    a: "The configuration cache serializes the result of the configuration phase — the task graph and all configured task state — so subsequent builds with the same inputs skip configuration entirely and jump straight to execution. It's distinct from the build cache, which caches task outputs; the configuration cache caches the work of figuring out what to run."
  - q: "Why is my build incompatible with the configuration cache?"
    a: "The most common causes are tasks that read Project at execution time, use of Task.project during execution, reading system properties or environment variables outside the supported providers, and shared mutable state between tasks. Gradle reports each problem with a link; the fix is usually to inject values via providers and value sources at configuration time instead of reaching for Project later."
  - q: "Is the configuration cache safe to enable in production builds?"
    a: "Yes, once your build is compatible. Gradle validates the cache against its inputs and re-runs configuration when they change, so stale configuration isn't served. Start with a warning mode to surface problems, fix them, then turn it on by default in gradle.properties for both local and CI builds."
---

The Gradle configuration cache attacks a cost most teams don't even measure: the *configuration phase*, where Gradle evaluates every build script and builds the task graph before a single task runs. On a big multi-module Android project that phase can take several seconds on every invocation — even `./gradlew help`. The configuration cache serializes the result of that phase and reuses it, so repeat builds skip straight to execution. When I enabled it on a ~50 module project, incremental builds dropped noticeably and, more importantly, the "Gradle sits there configuring" pause before anything happened largely vanished. The catch is that it demands your build follow the rules, and legacy build logic usually breaks them somewhere.

## Configuration cache vs build cache

These get conflated constantly, so pin them down:

- The **build cache** caches *task outputs* — the results of running tasks (compiled classes, etc.).
- The **configuration cache** caches the *configuration phase* — the computed task graph and configured task state, i.e. the work of deciding *what* to run and with what settings.

They're complementary and independent. Build cache saves you executing tasks; configuration cache saves you configuring them. You want both on. This post is about the second, which is often the bigger surprise because people forget configuration costs anything at all until they see it disappear.

## How it works

When enabled, Gradle:

1. Runs the configuration phase once, then **serializes** the task graph and all the task state to a cache entry keyed on the build's configuration inputs (build scripts, `gradle.properties`, environment values you declared, requested tasks).
2. On the next compatible invocation, **deserializes** that graph and skips configuration entirely, going straight to execution.
3. **Invalidates** the entry automatically when any declared input changes, so you never run stale configuration.

A pleasant side effect: because the cache requires tasks to declare their inputs cleanly and forbids cross-task coupling, enabling it tends to make your build *more parallelizable*, since Gradle can safely run more tasks concurrently once they're properly isolated.

## Turning it on

Start in warning mode so problems surface without failing the build:

```properties
# gradle.properties
org.gradle.configuration-cache=true
org.gradle.configuration-cache.problems=warn
```

Run a build, read the HTML report Gradle generates listing every incompatibility with a link to the cause, fix them, then flip `problems` back to `fail` (the default) so regressions can't sneak in. Do this incrementally — fix a batch, re-run, repeat — rather than trying to fix everything blind.

## The incompatibilities you'll hit

The rules exist because a serialized configuration can't hold a live reference to things that only make sense during a running build. The offenders, roughly in order of how often I hit them:

- **Reading `Project` at execution time.** A task action (`doLast { ... }`) that touches `project` is the classic violation — configuration is cached, but `Project` isn't available then. Capture what you need at configuration time into a `@Input` property or a provider.
- **`Task.project` during execution.** Same problem, same fix.
- **Reading env vars / system properties / files ad hoc.** Reading `System.getenv(...)` directly makes the value invisible to the cache's input tracking. Use `providers.environmentVariable(...)`, `providers.systemProperty(...)`, and `ValueSource` so Gradle knows about the input and can invalidate correctly.
- **Shared mutable state between tasks.** Tasks writing to a shared object break isolation. Pass data through inputs/outputs, not shared globals.

The mental model shift is: do all the "reaching out to the world" at configuration time through providers, and make task *execution* a pure function of its declared inputs. That's the same discipline that makes tasks cacheable for the [remote build cache](https://blog.michaelsam94.com/gradle-build-cache-remote/) — the two features reward the same good hygiene.

## Making a custom task compliant

Concretely, the fix pattern for a task that read `project` at execution time:

```kotlin
// Before: reads project at execution — configuration-cache incompatible.
abstract class BadTask : DefaultTask() {
    @TaskAction fun run() {
        val v = project.version                 // NOT allowed at execution
        logger.lifecycle("building $v")
    }
}

// After: capture inputs at configuration time via providers.
abstract class GoodTask : DefaultTask() {
    @get:Input abstract val version: Property<String>
    @TaskAction fun run() {
        logger.lifecycle("building ${version.get()}")   // pure over inputs
    }
}
// wiring: tasks.register<GoodTask>("x") { version.set(project.provider { project.version.toString() }) }
```

The task no longer touches `Project` when it runs; the value was captured into a property during configuration. This shape — abstract properties, injected providers, no `Project` at execution — is what compliant Gradle tasks look like going forward.

## Project isolation is the next step

The configuration cache pairs with **project isolation**, an evolving feature that isolates each project's configuration from others so Gradle can configure projects in parallel and cache them more granularly. Cross-project configuration (`subprojects { }`, reaching into `project(":other")` at configuration time) is the enemy of both. Moving shared setup into [convention plugins](https://blog.michaelsam94.com/gradle-convention-plugins/) instead of `allprojects`/`subprojects` blocks is the migration that unlocks isolation and keeps the configuration cache happy. If you're modularizing anyway, do this together.

## The payoff and the gotchas

What you get: configuration time effectively drops to near zero on cache hits, the pre-execution pause disappears, and builds parallelize better. What to watch:

- **First run is not faster** — it has to configure and serialize. The wins are on subsequent runs.
- **IDE sync** may still configure; the cache helps command-line and CI invocations most.
- **Plugins matter.** A third-party plugin that isn't cache-compatible can block you; most mainstream ones (AGP, Kotlin) are compatible in current versions, but check your plugin set.

## What I'd take away

The configuration cache eliminates a cost most teams don't realize they're paying — the configuration phase on every single build — by serializing the task graph and reusing it. Enable it in warning mode, work through Gradle's problem report, and fix incompatibilities by capturing inputs through providers at configuration time and making task execution a pure function of declared inputs. Move shared setup into convention plugins to enable project isolation, keep it on in CI so regressions fail fast, and combine it with the remote build cache for the full build-speed effect.

## Resources

- [Configuration cache (Gradle docs)](https://docs.gradle.org/current/userguide/configuration_cache.html)
- [Configuration cache requirements and troubleshooting](https://docs.gradle.org/current/userguide/configuration_cache.html#config_cache:requirements)
- [Project isolation](https://docs.gradle.org/current/userguide/isolated_projects.html)
- [Using providers and lazy configuration](https://docs.gradle.org/current/userguide/lazy_configuration.html)
- [Optimize your build (Android)](https://developer.android.com/build/optimize-your-build)
