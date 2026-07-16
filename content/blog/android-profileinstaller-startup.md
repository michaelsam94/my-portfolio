---
title: "ProfileInstaller and Startup Performance"
slug: "android-profileinstaller-startup"
description: "How ProfileInstaller applies Baseline Profiles for faster Android startup, why profiles sometimes don't kick in, and how to verify AOT compilation actually happened."
datePublished: "2024-10-01"
dateModified: "2024-10-01"
tags: ["Android", "Performance", "Jetpack Compose", "Startup"]
keywords: "ProfileInstaller, Android startup performance, Baseline Profile applied, cold start Android, dexopt profile, profileinstaller verify"
faq:
  - q: "What does ProfileInstaller do?"
    a: "ProfileInstaller is a Jetpack library that installs your app's bundled Baseline Profile into the system so the Android runtime can compile those hot paths ahead of time. On devices and app-store setups where Cloud Profiles or install-time compilation don't apply the profile automatically, ProfileInstaller ensures it gets written and picked up by background dexopt. Without it, a shipped Baseline Profile may never actually be applied on some devices."
  - q: "Why isn't my Baseline Profile improving startup?"
    a: "Common causes are the profile not being applied yet (compilation happens in the background after install, not instantly), measuring on a debuggable build, or the profile not matching the actual startup code paths. Verify with a Macrobenchmark using CompilationMode.Partition or by checking the profile installation result, and always measure a release build. A profile that exists in the APK isn't the same as a profile the runtime has compiled."
  - q: "Do I need ProfileInstaller if I use the Baseline Profile Gradle plugin?"
    a: "The Baseline Profile Gradle plugin adds the ProfileInstaller dependency for you as part of setup, so in a properly configured project it's already there. You rarely interact with it directly, but it's the runtime component that actually gets the profile into a state the ART runtime uses. Knowing it exists matters when you're debugging why a profile isn't taking effect."
---

You can generate a perfect Baseline Profile and ship it in your APK, and it can still do absolutely nothing for your users. That's the part teams miss: a profile *in the app* isn't a profile the runtime has *applied*. The bridge between the two is **ProfileInstaller**, a small Jetpack library that gets your bundled profile into a state Android's ahead-of-time compiler will actually use. Understanding this link is what separates "we added Baseline Profiles" from "our cold start actually got faster" — and it's where I've spent a fair amount of time explaining why a profile that clearly exists isn't showing up in the numbers.

## The chain from profile to fast startup

Getting startup speedup from a profile is a chain, and every link has to hold:

1. **Generate** a Baseline Profile that captures real startup/first-scroll hot paths (covered in [generating Baseline Profiles in CI](https://blog.michaelsam94.com/android-baseline-profiles-ci/)).
2. **Bundle** it into the APK/AAB as an asset.
3. **Install/apply** it on the device so ART knows those paths should be AOT-compiled.
4. **Compile** — background `dexopt` compiles the profiled code ahead of time.
5. **Benefit** — the next cold start runs compiled code on the critical path instead of interpreting/JIT-ing it.

ProfileInstaller owns step 3. On many devices and distribution paths the profile is applied automatically (Play Cloud Profiles, install-time compilation), but that coverage isn't universal — older devices, sideloaded builds, and certain install flows don't apply the bundled profile on their own. ProfileInstaller ensures it happens regardless, which is why it's the safety net that makes profiles reliable across your whole install base.

## Why the profile doesn't apply instantly

The most confusing behavior: you install the app, launch it, and startup is *not* faster. That's often correct and expected. Compilation of the profiled paths happens in the **background after install**, not synchronously on first launch. ART schedules `dexopt` to run — often when the device is idle/charging — and only after that runs do you see the AOT benefit. So measuring cold start immediately after a fresh install can show no improvement even when everything is wired correctly.

This is exactly why manual "install and feel it" testing is unreliable for profiles. You need to either force compilation or measure through a benchmark that controls compilation state.

## Verifying it actually worked

Don't take it on faith. Two reliable checks:

**Check the installation result at runtime.** ProfileInstaller reports whether it wrote the profile. Surfacing this in a debug build tells you the profile at least reached the device correctly.

**Measure with a Macrobenchmark controlling compilation.** This is the definitive test — compare startup under different `CompilationMode`s:

```kotlin
@Test
fun startupNoCompilation() = benchmark(CompilationMode.None())

@Test
fun startupWithBaselineProfile() = benchmark(CompilationMode.Partial(BaselineProfileMode.Require))

private fun benchmark(mode: CompilationMode) = benchmarkRule.measureRepeated(
    packageName = "com.example.app",
    metrics = listOf(StartupTimingMetric()),
    compilationMode = mode,
    iterations = 10,
    startupMode = StartupMode.COLD,
) {
    startActivityAndWait()
}
```

`CompilationMode.Partial(BaselineProfileMode.Require)` forces the profile to be applied before measuring and *fails* if it can't be — so a passing run with better numbers is proof the profile both exists and helps. If `Require` fails, your profile isn't being found; that's the bug, not the performance.

## Common reasons startup doesn't improve

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| No improvement right after install | Background compile hasn't run yet | Measure via Macrobenchmark, not by feel |
| `BaselineProfileMode.Require` fails | Profile not bundled/found | Recheck plugin setup and variant |
| Measuring on debug build | Debuggable disables optimizations | Always benchmark a release-like build |
| Profile helps startup but not scroll | Generator didn't scroll | Exercise first-scroll in the generator |
| Improvement smaller than expected | Profile stale vs current code | Regenerate; automate it in CI |

The recurring theme: measure the right build (release), the right way (benchmark with controlled compilation), at the right time (after compilation, not before). Get any of those wrong and you'll conclude profiles "don't work" when they do.

## Do you touch ProfileInstaller directly?

Mostly no. The Baseline Profile Gradle plugin pulls in ProfileInstaller as part of standard setup, so in a properly configured project the dependency is already present and doing its job quietly. You *should* know it's there, because when you're debugging "why isn't this profile applied," ProfileInstaller is the component responsible for step 3 — and confirming it ran (or forcing it via `Require` in a benchmark) is how you localize the failure. In practice I only reach for it explicitly when diagnosing profile application on a specific problematic device.

## Startup is more than profiles

Profiles remove JIT warm-up, but they won't save a startup that does too much work. If your `Application.onCreate` synchronously initializes ten SDKs, no amount of AOT compilation fixes that — you're just running heavy code faster. Profiles pair with the usual startup hygiene: defer non-critical initialization (Jetpack Startup / lazy init), keep the first frame's work minimal, and avoid main-thread I/O. The profile makes the *necessary* work fast; trimming *unnecessary* work is a separate, equally important lever. The [coroutine patterns](https://blog.michaelsam94.com/kotlin-coroutines-flow-patterns/) for moving work off the main thread are part of that same startup discipline.

## What I'd take away

A Baseline Profile shipped in your APK does nothing until it's applied, and ProfileInstaller is the link that ensures it gets applied across the devices where automatic mechanisms don't cover you. Compilation happens in the background after install, so don't judge profiles by feel right after installing — measure with a release build and a Macrobenchmark using `CompilationMode.Partial(BaselineProfileMode.Require)`, which proves the profile is both present and effective. When startup still lags, check the whole chain and remember profiles speed up the work you do; they don't excuse doing too much of it. Wire generation into CI, verify with benchmarks, and the startup win becomes something you can prove rather than hope for.

## Resources

- [ProfileInstaller library](https://developer.android.com/jetpack/androidx/releases/profileinstaller)
- [Baseline Profiles overview](https://developer.android.com/topic/performance/baselineprofiles/overview)
- [Macrobenchmark and CompilationMode](https://developer.android.com/topic/performance/benchmarking/macrobenchmark-overview)
- [App startup time](https://developer.android.com/topic/performance/vitals/launch-time)
- [App Startup library](https://developer.android.com/topic/libraries/app-startup)
