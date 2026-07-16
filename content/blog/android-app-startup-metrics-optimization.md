---
title: "Optimizing Cold, Warm, and Hot Starts"
slug: "android-app-startup-metrics-optimization"
description: "Measure and optimize Android cold, warm, and hot app starts: Startup Timing Metric, Baseline Profiles, lazy initialization, and the fixes that actually move TTID."
datePublished: "2026-07-11"
dateModified: "2026-07-11"
tags: ["Android", "Performance", "Startup", "Baseline Profiles"]
keywords: "Android app startup optimization, cold start warm start, TTID time to initial display, app startup metrics, Android launch time"
faq:
  - q: "What is the difference between cold, warm, and hot starts on Android?"
    a: "Cold start: app process doesn't exist — slowest, full Application.onCreate and Activity creation. Warm start: process exists but Activity was destroyed — skips process init but recreates Activity. Hot start: Activity still in back stack — fastest, just brings existing Activity to foreground. Optimize cold start first; it's what users experience after force-stop or reboot."
  - q: "What is TTID and TTFD?"
    a: "TTID (Time to Initial Display) measures from launch intent to first frame drawn. TTFD (Time to Full Display) measures until the app is fully interactive with all async content loaded. Google Play vitals tracks both. TTID is the metric users feel; TTFD captures when lazy-loaded content finishes."
  - q: "What gives the biggest cold start improvement?"
    a: "Baseline Profiles typically deliver 20–30% cold start improvement with minimal code changes. After that, defer non-critical initialization out of Application.onCreate, use App Startup library for dependency ordering, and profile with Perfetto to find the actual bottleneck — it's usually a specific SDK init, not 'the JVM is slow.'"
---

Cold start is the first impression — and the metric Google Play vitals publishes publicly. Users don't care whether your warm start is fast; they care about the three seconds staring at a splash screen after tapping your icon from the launcher. I've profiled startup on dozens of apps, and the pattern is always the same: 60% of cold start time is initialization nobody needed before the first frame, 20% is layout inflation, and the rest is actual work. Baseline Profiles and lazy init fix the first bucket; the others need targeted profiling.

## The three start types

```
Cold:  Process dead → Zygote fork → Application.onCreate → Activity → first frame
Warm:  Process alive → Activity.onCreate → first frame  
Hot:   Activity in memory → onResume → visible
```

Play vitals and Android Vitals report cold and warm startup times separately. Focus on cold — it's the worst case and the published number.

## Measuring accurately

Use `Activity.reportFullyDrawn()` for TTFD:

```kotlin
class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        lifecycleScope.launch {
            loadInitialContent()
            reportFullyDrawn()  // TTFD marker
        }
    }
}
```

For deeper analysis, use [Perfetto startup tracing](https://blog.michaelsam94.com/android-startup-tracing-perfetto/) or Macrobenchmark:

```kotlin
@Test
fun startupBenchmark() = benchmarkRule.measureRepeated(
    packageName = "com.example.app",
    metrics = listOf(StartupTimingMetric()),
    startupMode = StartupMode.COLD,
) {
    pressHome()
    startActivityAndWait()
}
```

Run on physical devices, not emulators — emulator startup numbers are meaningless for vitals comparison.

## The Application.onCreate audit

Every line in `Application.onCreate()` runs before your first frame. Audit it ruthlessly:

```kotlin
class MyApp : Application() {
    override fun onCreate() {
        super.onCreate()
        // KEEP: crash reporting, strict mode (debug), essential DI graph
        initCrashReporting()

        // DEFER: analytics, SDK init, database warmup, config fetch
        ProcessLifecycleOwner.get().lifecycle.addObserver(object : DefaultLifecycleObserver {
            override fun onStart(owner: LifecycleOwner) {
                owner.lifecycle.removeObserver(this)
                initAnalytics()
                prefetchConfig()
            }
        })
    }
}
```

Move everything non-critical to after first frame. If a SDK doesn't support lazy init, question whether you need it at all.

## App Startup library for dependency ordering

Replace scattered init blocks with declarative initializers:

```kotlin
class AnalyticsInitializer : Initializer<Unit> {
    override fun create(context: Context) {
        Analytics.init(context)
    }
    override fun dependencies() = listOf(CrashReportingInitializer::class.java)
}
```

```xml
<!-- AndroidManifest.xml -->
<provider
    android:name="androidx.startup.InitializationProvider"
    android:authorities="${applicationId}.androidx-startup"
    tools:node="merge">
    <meta-data
        android:name="com.example.AnalyticsInitializer"
        android:value="androidx.startup" />
</provider>
```

App Startup runs initializers in dependency order on a background thread where possible, and avoids duplicate init when multiple components trigger the same library.

## Baseline Profiles

The highest ROI optimization. [Baseline Profiles](https://blog.michaelsam94.com/baseline-profiles-android-startup/) pre-compile hot paths:

```kotlin
// baseline-prof.txt (generated via Macrobenchmark)
HSPLcom/example/app/MainActivity;->onCreate(Landroid/os/Bundle;)V
HSPLcom/example/app/MyApp;->onCreate()V
```

Ship the profile in your APK/AAB. ART pre-compiles these methods at install time. Typical result: 20–30% cold start improvement on mid-range devices, more on low-end.

Generate profiles by running Macrobenchmark with `BaselineProfileMode.Generate` on a representative user flow — launch app, navigate to main screen.

## Content Provider init trap

Many SDKs initialize via ContentProvider in your manifest — before `Application.onCreate()`, on the main thread, with no opt-out. Find them:

```bash
# List all content providers in your merged manifest
./gradlew :app:processReleaseManifest && \
  grep -A2 "ContentProvider" app/build/intermediates/merged_manifests/release/AndroidManifest.xml
```

For SDKs that support it, disable auto-init:

```xml
<meta-data android:name="firebase_analytics_collection_deactivated" android:value="true" />
```

Or use App Startup to replace provider-based init entirely.

## Layout inflation wins

If profiling shows inflation is significant:

- Use `AsyncLayoutInflater` or Compose (no XML inflation)
- Reduce view hierarchy depth — flatten where possible
- Avoid heavy work in custom View constructors
- Use `<merge>` and `<include>` judiciously, not nested deeply

For Compose apps, defer expensive composition:

```kotlin
setContent {
    AppTheme {
        // Show shell immediately
        MainScaffold()
    }
}
```

## Targets and monitoring

| Metric | Good | Needs work | Bad |
|--------|------|------------|-----|
| Cold TTID | <500ms | 500ms–1s | >1s |
| Cold TTFD | <1s | 1–2s | >2s |
| Warm start | <200ms | 200–500ms | >500ms |

Track in Play Console vitals weekly. Set an internal budget: no release ships if cold start p90 regresses >10%.

## Macrobenchmark startup tests

```kotlin
@Test
fun startupCold() = benchmarkRule.measureRepeated {
    pressHome()
    startActivityAndWait()
}
```

Track `timeToInitialDisplay`, `timeToFullDisplay` in CI. Regressions > 10% block merge on critical path changes.

## Common production mistakes

Teams get app startup metrics optimization wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping app startup metrics optimization on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Debugging and triage workflow

When app startup metrics optimization misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [App startup time (Android vitals)](https://developer.android.com/topic/performance/vitals/launch-time)
- [Baseline Profiles guide](https://developer.android.com/topic/performance/baselineprofiles)
- [App Startup library](https://developer.android.com/topic/libraries/app-startup)
- [Macrobenchmark startup tests](https://developer.android.com/topic/performance/benchmarking/macrobenchmark-overview)
- [Profiling startup with Perfetto](https://blog.michaelsam94.com/android-startup-tracing-perfetto/)
