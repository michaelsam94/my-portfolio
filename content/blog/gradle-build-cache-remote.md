---
title: "Remote Gradle Build Cache for Teams"
slug: "gradle-build-cache-remote"
description: "Set up a remote Gradle build cache to share task outputs across your team and CI: how it works, cacheability rules, hit-rate tuning, and avoiding poisoned caches."
datePublished: "2024-08-09"
dateModified: "2024-08-09"
tags: ["Gradle", "Build", "DevOps", "CI"]
keywords: "Gradle remote build cache, build cache node, task output cache, Gradle cache hit rate, cacheable task, CI build cache"
faq:
  - q: "How does the Gradle remote build cache work?"
    a: "Gradle computes a hash of every cacheable task's inputs — source files, classpath, arguments, environment — and uses it as a key. When a task runs, its outputs are stored under that key in a shared remote cache; when any machine later runs a task with the same key, Gradle downloads the outputs instead of executing the task. This lets CI populate a cache that developers reuse and vice versa."
  - q: "Why is my Gradle build cache hit rate low?"
    a: "Low hit rates usually come from unstable task inputs: absolute paths, timestamps, environment variables, or volatile generated files that change the cache key even when the real inputs didn't. Non-cacheable custom tasks, different JDK or Gradle versions across machines, and unnecessary configuration differences also break sharing. Use build scans to find which tasks miss and why."
  - q: "Is it safe to let developers write to the remote build cache?"
    a: "Generally you let CI write to the remote cache and developers read-only, so a misconfigured or malicious local environment can't poison shared outputs. If developers push, ensure reproducible inputs and consider signing or trust boundaries. A poisoned cache serves wrong outputs to everyone, so restricting writes to trusted CI is the safer default."
---

A remote Gradle build cache lets your whole team and CI reuse each other's task outputs, so nobody rebuilds what someone else already built. The mechanism is simple to state: Gradle hashes each cacheable task's inputs into a key, stores the outputs under that key remotely, and on a match anywhere downloads the outputs instead of re-running the task. Done right, a fresh checkout or a CI job that would take ten minutes finishes in two because most of the work is a cache download. I've stood this up for a team where CI populated the cache and developers pulled from it, and the median local build dropped by more than half — but only after fixing the input-stability problems that were quietly wrecking the hit rate.

## Local cache vs remote cache

Gradle has a *local* build cache (on each machine, on by default when caching is enabled) and a *remote* cache (a shared HTTP node everyone talks to). The local cache saves you re-running tasks across your own builds; the remote cache is where the team leverage is, because it shares outputs across people and CI.

Enable both in `gradle.properties` / `settings.gradle.kts`:

```kotlin
// settings.gradle.kts
buildCache {
    local { isEnabled = true }
    remote<HttpBuildCache> {
        url = uri("https://cache.internal.example.com/cache/")
        isPush = System.getenv("CI") == "true"   // only CI writes
        credentials {
            username = System.getenv("CACHE_USER")
            password = System.getenv("CACHE_PASS")
        }
    }
}
```

```properties
# gradle.properties
org.gradle.caching=true
```

The `isPush = CI` line is the single most important policy decision here, and I'll come back to why.

## How the cache key is computed

Understanding the key is the whole game, because everything about hit rate flows from it. For each cacheable task, Gradle hashes:

- The task's **inputs** — source files' content, input properties, arguments.
- The **classpath** — every dependency and plugin on the task's classpath.
- The **task implementation** — the plugin/class code itself.

If two invocations produce the same hash, the outputs are interchangeable. The corollary is brutal: *any* input that varies when the real work didn't — an absolute path baked into an argument, a timestamp, a hostname, an environment variable read at configuration time — changes the key and turns a hit into a miss. Most "the cache doesn't work" complaints are actually "my task inputs are unstable."

## Getting a high hit rate

The practical work is making inputs stable and reproducible:

1. **Pin the toolchain.** Everyone and CI must use the same JDK and Gradle version. A different JDK changes bytecode and classpaths and busts keys. Use Gradle toolchains and the wrapper to enforce this.
2. **Kill absolute paths.** Tasks that embed the checkout path in outputs or arguments never match across machines. Use relative-path sensitivity and Gradle's path normalization.
3. **Normalize volatile inputs.** Strip timestamps and build numbers out of inputs that feed cacheable tasks; use `@Input`/`@InputFiles` with appropriate normalization on custom tasks.
4. **Make custom tasks cacheable and correct.** Mark them `@CacheableTask` and declare *all* inputs and outputs honestly. An under-declared input gives you wrong outputs; an over-declared one gives you misses.
5. **Measure with build scans.** Don't guess. A build scan shows per-task cache hits/misses and *why* a task was not cacheable or missed. That's how you find the one task dragging your rate down.

The ordering matters: fix the toolchain and paths first, because they invalidate everything downstream.

## The poisoned-cache risk

A shared cache serves outputs to everyone, which means a wrong output propagates. If a machine with a subtly broken environment pushes bad outputs under a key, every other machine happily downloads garbage — and it's maddening to debug because "it builds on a clean machine" and yet everyone's builds are wrong.

The standard mitigation is a trust boundary: **CI writes, developers read.** CI runs in a controlled, reproducible environment, so its outputs are trustworthy; developers pull those and only write to their *local* cache. That's what the `isPush = CI` line above enforces. If you do let developers push to remote, you need genuine confidence in input reproducibility and probably a way to invalidate ranges of the cache when something slips through. For most teams, CI-writes-only is the right default and eliminates the poisoning class entirely.

## Cache node and retention

The remote cache itself can be Gradle's built-in cache node, Develocity, or any HTTP backend that speaks the protocol. Whatever you pick, plan for:

- **Retention/eviction.** Caches grow forever otherwise. LRU eviction with a size cap is typical; old keys stop being useful after dependencies move on.
- **Locality.** Put the node close to CI and developers (network-wise). Downloading outputs over a slow link can be slower than rebuilding — the cache only wins when the transfer beats the computation.
- **Auth and TLS.** It's your build outputs; protect the endpoint.

## How it fits the broader build-speed story

Remote caching is one leg of a three-legged stool for fast Gradle builds. The others are the [configuration cache](https://blog.michaelsam94.com/gradle-configuration-cache/) (which caches the *configuration* phase, orthogonal to the task-output caching here) and good [modularization](https://blog.michaelsam94.com/android-modularization-strategy/) (so a change in one module doesn't invalidate the world). The build cache gives you the most when your project is well-modularized: small, well-bounded modules mean a change busts a few task keys, not the whole graph, so the cache keeps most outputs valid.

## What I'd take away

A remote build cache shares task outputs across your team and CI, and it works because Gradle keys outputs on a hash of task inputs. The wins are real — often halving fresh-build times — but they're gated entirely on input stability: pin the JDK and Gradle version, eliminate absolute paths and timestamps, declare custom-task inputs honestly, and use build scans to hunt down misses. Restrict remote writes to trusted CI to avoid poisoning the shared cache, plan retention and locality for the node, and pair caching with configuration caching and solid modularization to get the full effect.

## Resources

- [Gradle build cache (official docs)](https://docs.gradle.org/current/userguide/build_cache.html)
- [Build cache use cases and node setup](https://docs.gradle.org/current/userguide/build_cache_use_cases.html)
- [Cacheable tasks and task input normalization](https://docs.gradle.org/current/userguide/build_cache_concepts.html)
- [Gradle build scans](https://scans.gradle.com/)
- [Optimize build performance (Android)](https://developer.android.com/build/optimize-your-build)
