---
title: "Feature Flags on Android"
slug: "android-feature-flags-implementation"
description: "Implement feature flags on Android: Remote Config, local overrides, flag-driven architecture, debug menus, and safe rollout patterns for mobile."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Android", "Feature Flags", "Architecture", "Firebase"]
keywords: "Android feature flags, feature toggles mobile, Remote Config feature flags, Android flag-driven development, feature flag architecture"
faq:
  - q: "How do you implement feature flags on Android?"
    a: "Define flags in Firebase Remote Config or a dedicated feature flag service, fetch at app start, cache locally, and gate UI and behavior behind flag checks. Use a FeatureFlags abstraction in your codebase so the source (Remote Config, local override, default) is swappable. Never scatter raw Remote Config calls through ViewModels."
  - q: "Where should feature flag checks live in the architecture?"
    a: "Check flags at the navigation/routing layer for showing or hiding screens, and in ViewModels or use cases for behavior changes. Avoid checking flags in Composables or XML layouts directly — centralize in a FeatureFlags repository that exposes Flow<Boolean> for reactive UI updates."
  - q: "How do you test feature flag combinations?"
    a: "Provide a debug-only override mechanism (debug menu or test rule) that sets flags without Remote Config. In unit tests, inject a FakeFeatureFlags implementation. Test both enabled and disabled states for every flagged feature — untested flag combinations ship broken."
---

Feature flags on mobile aren't the same as web feature flags. You can't flip a flag and instantly change behavior for all users — some are on app version 2.1, some on 3.0, and some haven't fetched Remote Config since yesterday. Mobile feature flags gate code paths that ship in the APK; the flag controls activation, not existence. I've seen flagged features ship broken because nobody tested the `flag=false` path, and I've seen rollouts go smoothly because the team treated every flag as a branch that needs both paths tested. The pattern is simple; the discipline is the hard part.

## Architecture

```
Remote Config / Flag service
        ↓ fetch + cache
FeatureFlagsRepository (single source of truth)
        ↓ Flow<Boolean>
ViewModel / UseCase → UI decision
```

Centralize all flag access:

```kotlin
interface FeatureFlags {
    val newCheckoutEnabled: Flow<Boolean>
    val darkModeDefault: Flow<Boolean>
    fun isEnabled(flag: String): Boolean  // synchronous, cached
}

class FeatureFlagsRepository(
    private val remoteConfig: FirebaseRemoteConfig,
    private val localOverrides: LocalFlagOverrides,
) : FeatureFlags {

    override val newCheckoutEnabled: Flow<Boolean> = callbackFlow {
        val listener = ConfigUpdateListener { fetchAndEmit() }
        remoteConfig.addOnConfigUpdateListener(listener)
        fetchAndEmit()
        awaitClose { /* remove listener */ }
    }.distinctUntilChanged()

    override fun isEnabled(flag: String): Boolean {
        localOverrides.get(flag)?.let { return it }
        return remoteConfig.getBoolean(flag)
    }
}
```

One class, one place to mock in tests, one place to add logging.

## Remote Config integration

```kotlin
class FeatureFlagsRepository(private val remoteConfig: FirebaseRemoteConfig) {
    suspend fun refresh() {
        remoteConfig.fetchAndActivate()
    }

    fun isEnabled(key: String): Boolean = remoteConfig.getBoolean(key)
}
```

Set defaults for offline/first-launch:

```kotlin
remoteConfig.setDefaultsAsync(mapOf(
    "new_checkout_enabled" to false,
    "dark_mode_default" to false,
    "max_upload_size_mb" to 10L,
))
```

Defaults should be the safe/off state. If Remote Config fetch fails, users get the conservative behavior.

## Flag-driven navigation

Gate screens at the router, not inside the screen:

```kotlin
@Composable
fun AppNavHost(flags: FeatureFlags, navController: NavHostController) {
    val newCheckout by flags.newCheckoutEnabled.collectAsStateWithLifecycle(false)

    NavHost(navController, startDestination = "home") {
        composable("home") { HomeScreen() }
        composable("checkout") {
            if (newCheckout) NewCheckoutScreen() else LegacyCheckoutScreen()
        }
    }
}
```

Or conditionally register routes:

```kotlin
if (newCheckout) {
    composable("checkout") { NewCheckoutScreen() }
} else {
    composable("checkout") { LegacyCheckoutScreen() }
}
```

## Debug overrides

Every team needs to toggle flags without a Remote Config publish:

```kotlin
class LocalFlagOverrides(context: Context) {
    private val prefs = context.getSharedPreferences("flag_overrides", Context.MODE_PRIVATE)

    fun set(flag: String, value: Boolean) = prefs.edit { putBoolean(flag, value) }
    fun get(flag: String): Boolean? = if (prefs.contains(flag)) prefs.getBoolean(flag, false) else null
    fun clear(flag: String) = prefs.edit { remove(flag) }
}
```

Expose in a debug menu (shake-to-open, tap version 7 times):

```kotlin
if (BuildConfig.DEBUG) {
    DebugFlagScreen(
        flags = listOf("new_checkout_enabled", "dark_mode_default"),
        overrides = localOverrides,
    )
}
```

Check overrides first, Remote Config second, defaults last.

## Testing both paths

```kotlin
class FakeFeatureFlags(
    private val flags: Map<String, Boolean> = emptyMap()
) : FeatureFlags {
    override fun isEnabled(flag: String) = flags[flag] ?: false
    override val newCheckoutEnabled = MutableStateFlow(flags["new_checkout_enabled"] ?: false)
}

@Test
fun checkout_usesNewFlow_whenFlagEnabled() {
    val flags = FakeFeatureFlags(mapOf("new_checkout_enabled" to true))
    val vm = CheckoutViewModel(flags, fakeRepo)
    assertTrue(vm.useNewCheckout)
}

@Test
fun checkout_usesLegacyFlow_whenFlagDisabled() {
    val flags = FakeFeatureFlags(mapOf("new_checkout_enabled" to false))
    val vm = CheckoutViewModel(flags, fakeRepo)
    assertFalse(vm.useNewCheckout)
}
```

Both paths. Every flag. No exceptions.

## Rollout strategy

1. **Deploy with flag off** — code ships but inactive
2. **Internal testing** — override flag on in debug builds
3. **Canary** — Remote Config audience: 5% of users on latest version
4. **Gradual rollout** — 25% → 50% → 100% over days
5. **Monitor** — crash rate, key metrics per flag state
6. **Cleanup** — remove flag and dead code path after 100% stable for 2 weeks

Pair with [A/B testing](https://blog.michaelsam94.com/android-a-b-testing-firebase/) when you need to measure impact, not just control rollout.

## Flag lifecycle hygiene

Flags accumulate. Every flag should have:
- An owner
- A creation date
- A removal deadline (30–60 days after full rollout)
- Both code paths tested in CI

Run a quarterly flag audit. If a flag has been at 100% for 60 days, create a ticket to remove it and the dead code.

Evaluate flags on server for security-sensitive features — client-side flags are toggles in SharedPreferences for motivated users.

## Server-side evaluation for critical flags

```kotlin
interface FeatureFlags {
    suspend fun isEnabled(key: String): Boolean
}

class ServerFeatureFlags(private val api: ConfigApi) : FeatureFlags {
    private val cache = ConcurrentHashMap<String, Pair<Boolean, Long>>()

    override suspend fun isEnabled(key: String): Boolean {
        val cached = cache[key]
        if (cached != null && System.currentTimeMillis() - cached.second < 60_000) {
            return cached.first
        }
        val value = api.getFlags().flags[key] ?: false
        cache[key] = value to System.currentTimeMillis()
        return value
    }
}
```

Payment flows, admin features, and security toggles must be server-evaluated — client flags are UX hints only.

## Flag-driven architecture patterns

| Pattern | Description | When |
|---------|-------------|------|
| Release toggle | Hide incomplete feature | Until ready |
| Experiment toggle | A/B variant | Measure impact |
| Ops toggle | Kill switch | Incident response |
| Permission toggle | Entitlement gate | Plan tier features |

Name flags by purpose: `release_new_checkout` vs `exp_checkout_variant_b` vs `kill_payment_processing`.

Pair with [Firebase Remote Config strategies](https://blog.michaelsam94.com/android-firebase-remote-config-strategies/) for rollout mechanics.

## Common production mistakes

Teams get feature flags implementation wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping feature flags implementation on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Resources

- [Firebase Remote Config documentation](https://firebase.google.com/docs/remote-config)
- [Remote Config rollout strategies](https://blog.michaelsam94.com/android-firebase-remote-config-strategies/)
- [Feature flags and trunk-based development](https://blog.michaelsam94.com/feature-flags-trunk-based-development/)
- [LaunchDarkly mobile SDK](https://docs.launchdarkly.com/sdk/client-side/android)
- [A/B testing mobile features](https://blog.michaelsam94.com/android-a-b-testing-firebase/)
