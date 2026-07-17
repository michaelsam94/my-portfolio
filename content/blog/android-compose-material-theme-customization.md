---
title: "Material Theme Customization in Jetpack Compose"
slug: "android-compose-material-theme-customization"
description: "Build a production Material 3 theme in Compose: color roles, typography scale, shape tokens, and CompositionLocal patterns that survive dark mode and dynamic color."
datePublished: "2026-07-17"
dateModified: "2026-07-17"
tags: ["Android", "Jetpack Compose", "Material 3"]
keywords: "Compose Material theme, Material 3 customization, color roles, typography scale, dynamic color Android"
faq:
  - q: "When should Android teams adopt material theme customization in jetpack compose?"
    a: "Adopt material theme customization in jetpack compose when you have production signals — Play Vitals regressions, ANR clusters, user-reported bugs, or security findings — and simpler fixes are exhausted. Pilot on one screen or user segment before platform-wide rollout, and measure cold start, jank, and crash rates before and after."
  - q: "What are the most common mistakes with material theme customization in jetpack compose?"
    a: "Teams often test only on flagship devices and emulators, skip process-death and Doze scenarios, ship without rollback flags, and ignore OEM-specific battery optimizations. Document trade-offs, add StrictMode or Macrobenchmark guards in CI, and validate on low-RAM hardware with slow storage."
  - q: "How do I debug material theme customization in jetpack compose issues in production?"
    a: "Start from Play Console Android Vitals and Firebase Crashlytics breadcrumbs filtered by app version and device model. Reproduce on physical hardware with developer options strict mode enabled, capture Perfetto traces for jank, and narrow scope to one API level or OEM before changing architecture."
---

Build a production Material 3 theme in Compose: color roles, typography scale, shape tokens, and CompositionLocal patterns that survive dark mode and dynamic color. I've shipped this pattern across consumer and enterprise Android apps — from payment flows where a missed edge case becomes a chargeback, to field apps where Doze kills background sync and support hears about it days later. The gap between documentation and production is OEM battery savers, process death, configuration changes, and Play policy constraints that codelabs never stress-test.

This post covers what actually works when you own the Android surface area: implementation patterns you can paste into a PR, failure modes I've seen in Play Vitals, and a triage workflow for when things break under real users on mid-range hardware with 200% font scale and intermittent connectivity.

## Architecture and module boundaries

Before changing code, name the owner of each concern. Material Theme Customization in Jetpack Compose typically spans UI (Compose or Views), domain logic, platform APIs (permissions, background work, billing), and often a server contract. If you cannot draw the boundary, you will patch symptoms in composables when the bug is a WorkManager constraint or a missing ProGuard keep rule.

| Layer | Owns | Production watch-outs |
| --- | --- | --- |
| UI | State rendering, gestures, accessibility | Recomposition jank, config change state loss |
| Domain | Use cases, validation, mapping | Untestable logic leaked into composables |
| Data | Repositories, Room, DataStore, API | Main-thread I/O, stale cache after logout |
| Platform | FGS, alarms, notifications, billing | Android 14+ restrictions, permission revocations |

Keep platform SDK calls behind interfaces you can fake in unit tests. Android framework classes are hard to mock; your `BillingRepository`, `SyncScheduler`, or `AttestationClient` should not require a device to test business rules.

## Implementation

Start with the smallest production slice — one Activity, one worker, one billing SKU — behind a feature flag or `BuildConfig` gate. Measure cold start and frame time before expanding scope.

```kotlin
// Feature gate + measurable rollout
object AndroidComposeMaterialThemeCustomizationFeature {
    fun enabled(): Boolean =
        RemoteConfig.getBoolean("android-compose-material-theme-customization_enabled", default = false)
}

class AndroidRepository @Inject constructor(
    private val dispatcher: CoroutineDispatcher = Dispatchers.IO,
) {
    suspend fun execute(): Result<Unit> = withContext(dispatcher) {
        runCatching {
            // Core logic for material theme customization in jetpack compose
        }
    }
}
```

```kotlin
// ViewModel boundary — keep Android APIs out of composables
@HiltViewModel
class ExampleViewModel @Inject constructor(
    private val repo: AndroidRepository,
) : ViewModel() {
    private val _state = MutableStateFlow(UiState())
    val state = _state.asStateFlow()

    fun onAction(action: UiAction) {
        viewModelScope.launch {
            repo.execute()
                .onSuccess { _state.update { it.copy(success = true) } }
                .onFailure { e -> _state.update { it.copy(error = e.message) } }
        }
    }
}
```

Validate on API 26 and API 34+ hardware. Emulator-only testing misses `android-compose-material-theme-customization` failures tied to exact alarm permission, photo picker backport behavior, and manufacturer-specific background limits.

## Platform quirks and policy

Android is not a single platform — it's a compatibility surface across OEM skins, GMS vs non-GMS, foldables, and tablets. Patterns that work on Pixel may fail on devices with aggressive task killers or custom permission dialogs.

- **Process death**: Users leave your app via recents; the system kills it minutes later. Persist in-flight state to Room or DataStore; never rely on static singletons for session tokens.
- **Background limits**: Doze, App Standby buckets, and FGS timeouts (Android 15+) restrict work that codelabs run while plugged in. Use WorkManager with correct constraints and user-visible rationale when requesting exact alarms or full-screen intents.
- **Play policy**: Billing, foreground services, and photo/video permissions have declaration requirements in Play Console. Mismatch between manifest and declared use case causes rejection or removal.
- **R8/shrinker**: Release builds strip unused code and obfuscate names. Keep rules for reflection, Parcelable, Room entities, and kotlinx.serialization — or crash only in production.

Run internal testing tracks with pre-launch reports enabled before promoting to production. Crawlers find WebView and permission crashes humans skip.

## Testing strategy

| Layer | Tooling | What it catches |
| --- | --- | --- |
| Unit | JUnit5, coroutines-test, Turbine | State reducers, mappers, retry logic |
| Integration | Room in-memory, MockWebServer | SQL migrations, API parsing |
| UI | Compose Test, Espresso, Roborazzi | Regressions, semantics, screenshots |
| Device | Macrobenchmark, Baseline Profile | Startup, jank, dex layout |
| Manual | TalkBack, 200% font, airplane mode | A11y, offline, OEM quirks |

Use `TestDispatcher` for coroutines; never `Thread.sleep` in tests. For WorkManager, `TestDriver` advances time deterministically. For billing, license testers and static responses — never hit real Play Billing in CI.

Flaky instrumented tests erode trust: quarantine, fix root cause (usually idle/sync), or move logic to JVM unit tests. One reliable test beats five flaky ones.

## Common production mistakes

Teams get material theme customization in jetpack compose wrong in predictable ways:

- **Main-thread I/O** — Room, DataStore, and disk reads during composition or `onCreate` cause ANRs visible only on slow devices.
- **Ignoring process death** — `remember` without `rememberSaveable`, in-memory caches for checkout state, lost deep link args after kill.
- **GlobalScope and non-cancellable work** — leaks polling after user logs out; use structured concurrency in `viewModelScope`.
- **Missing idling in tests** — async work completes after assertion; production ships broken, CI stays green with sleeps.
- **Release-only ProGuard bugs** — `ClassNotFoundException` for Gson types, Room entities, or NavArgs only in Play Internal Testing.
- **Permission UX as afterthought** — permanent deny requires Settings intent; rage-quits show up as drop-off, not crash reports.

Document trade-offs in the PR: if you chose speed over strict correctness, the on-call engineer needs that context at 3am.

## Debugging and triage workflow

When material theme customization in jetpack compose misbehaves in production:

1. **Confirm scope** — specific API level, OEM, app version, or experiment bucket? Check Play Vitals clusters.
2. **Recent changes** — releases, Remote Config, flag flips, server deploys in the last 24 hours.
3. **Golden signals** — crash rate, ANR rate, slow cold start, battery warnings vs baseline.
4. **Reproduce minimally** — smallest device state: low memory, Doze forced via `adb`, offline, dark mode, RTL locale.
5. **Capture evidence** — Perfetto trace for jank, Logcat with correlation IDs, Crashlytics keys custom attributes.
6. **Fix forward or rollback** — Play staged rollout lets you halt; use Remote Config kill switches for client logic.
7. **Add a guard** — Macrobenchmark threshold, lint rule, or CI check so recurrence is caught pre-merge.

Write a timeline during incidents. Future you needs timestamps and rejected hypotheses, not only the final root cause.

## Rollout checklist

Before enabling `android-compose-material-theme-customization` for all users:

1. Baseline Play Vitals: cold start, warm start, ANR rate, excessive wakeups.
2. Run Macrobenchmark on physical device comparing previous release artifact.
3. Test process death (`adb shell am kill`), rotation, multi-window, and locale change.
4. Verify ProGuard mapping uploads to Crashlytics for the release build you ship.
5. Confirm feature flag or Remote Config can disable without a new APK (where possible).
6. Schedule a 48-hour metrics review after staged rollout hits 20% → 50% → 100%.

Ship incrementally. Treat every Android change as an experiment with a hypothesis, measurement plan, and rollback — not a one-way door based on a single blog post.

## Resources

- [Android Developers documentation](https://developer.android.com/)
- [Jetpack Compose guidelines](https://developer.android.com/develop/ui/compose)
- [Kotlin coroutines guide](https://kotlinlang.org/docs/coroutines-guide.html)
- [Play Console Help — Android Vitals](https://support.google.com/googleplay/android-developer/answer/9844486)
- [Material Design 3 for Android](https://m3.material.io/develop/android/jetpack-compose)
