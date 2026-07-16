---
title: "Remote Config Rollout Strategies"
slug: "android-firebase-remote-config-strategies"
description: "Firebase Remote Config rollout strategies for Android: percentage rollouts, audience conditions, real-time updates, caching, and avoiding config-fetch footguns."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Android", "Firebase", "Feature Flags", "DevOps"]
keywords: "Firebase Remote Config Android, Remote Config rollout, percentage rollout Firebase, Remote Config caching, Firebase config strategies"
faq:
  - q: "How often should Remote Config fetch in production?"
    a: "Set minimumFetchIntervalInSeconds to 3600 (1 hour) or higher in production. The default 12-hour fetch interval is fine for most apps. Aggressive fetching (every app open) wastes bandwidth, drains battery, and hits Firebase throttling limits. Use real-time config updates for urgent changes instead of frequent polling."
  - q: "How do percentage rollouts work in Remote Config?"
    a: "Create a condition with a random percentile rule (e.g., 'User in random percentile <= 10') and assign variant values to that condition. Firebase deterministically assigns each user to a percentile bucket based on their instance ID, so the same user always gets the same variant. Increase the percentile threshold to expand the rollout."
  - q: "What happens if Remote Config fetch fails?"
    a: "The app uses cached values from the last successful fetch, falling back to in-app defaults if no cache exists. Design defaults to be the safe/conservative state. Never assume fetch succeeds — first launch, airplane mode, and Firebase outages all result in defaults-only behavior."
---

Remote Config is the most underconfigured Firebase product I see in production apps. Teams fetch on every app open (battery drain, throttling), set no defaults (first launch breaks), or publish config changes expecting instant global effect (cache says otherwise). Used correctly, Remote Config is your rollout control plane — percentage rollouts, audience targeting, kill switches, and A/B experiments — all without an app store release. Used incorrectly, it's a source of "works on my device" bugs that only appear for users who fetched at the wrong time.

## Fetch and activate pattern

```kotlin
class RemoteConfigManager(private val remoteConfig: FirebaseRemoteConfig) {

    init {
        remoteConfig.setConfigSettingsAsync(
            remoteConfigSettings {
                minimumFetchIntervalInSeconds = if (BuildConfig.DEBUG) 0 else 3600
            }
        )
        remoteConfig.setDefaultsAsync(R.xml.remote_config_defaults)
    }

    suspend fun fetchAndActivate(): Boolean {
        return try {
            remoteConfig.fetchAndActivate().await()
        } catch (e: Exception) {
            Log.w("RemoteConfig", "Fetch failed, using cached/defaults", e)
            false
        }
    }
}
```

Call once at app start, not on every screen navigation. Cached values are used until the next successful fetch.

## Defaults are your safety net

```xml
<!-- res/xml/remote_config_defaults.xml -->
<?xml version="1.0" encoding="utf-8"?>
<defaultsMap>
    <entry>
        <key>new_checkout_enabled</key>
        <value>false</value>
    </entry>
    <entry>
        <key>max_items_per_page</key>
        <value>20</value>
    </entry>
    <entry>
        <key>maintenance_mode</key>
        <value>false</value>
    </entry>
</defaultsMap>
```

Defaults = the state when nothing else is available. Always conservative:
- Feature flags: `false`
- Limits: current production values
- Kill switches: `false` (app functional)

## Percentage rollout

In Firebase Console:

1. Create condition: "Random percentile <= 10" (10% of users)
2. Set parameter value for that condition: `new_checkout_enabled = true`
3. Default value remains `false`

Firebase assigns each app instance a stable random percentile. User A always in bucket 7, User B always in bucket 42. Increasing to "<= 25" adds users 11–25 without changing existing assignments.

Expand gradually:

| Day | Percentile | Action |
|-----|-----------|--------|
| 1 | 5% | Internal + canary |
| 3 | 10% | Monitor crash rate |
| 7 | 25% | Monitor key metrics |
| 14 | 50% | Half rollout |
| 21 | 100% | Full rollout, plan flag removal |

## Audience conditions

Target beyond random percentile:

```
Condition: "Beta testers"
  User property: user_type == "beta"

Condition: "Latest version only"
  App version >= 3.2.0

Condition: "US market"
  Country == United States
```

Combine with AND/OR:

```
"Beta testers on latest version"
  user_type == "beta" AND app version >= 3.2.0
```

Set user properties after login:

```kotlin
firebaseAnalytics.setUserProperty("user_type", if (user.isBeta) "beta" else "standard")
```

Conditions evaluate against these properties on next fetch.

## Real-time config updates

For urgent changes (kill switch, critical fix), use real-time listeners instead of waiting for the next fetch interval:

```kotlin
remoteConfig.addOnConfigUpdateListener(object : ConfigUpdateListener {
    override fun onUpdate(configUpdate: ConfigUpdate) {
        if (configUpdate.updatedKeys.contains("maintenance_mode")) {
            remoteConfig.activate()
            handleMaintenanceModeChange()
        }
    }
    override fun onError(error: FirebaseRemoteConfigException) {
        Log.e("RemoteConfig", "Real-time update failed", error)
    }
})
```

Real-time updates push within minutes. Don't rely on them for sub-second changes — they're not a message bus.

## Reading config reactively

Expose config as Flow for UI reactivity:

```kotlin
fun observeBoolean(key: String): Flow<Boolean> = callbackFlow {
    trySend(remoteConfig.getBoolean(key))
    val listener = object : ConfigUpdateListener {
        override fun onUpdate(update: ConfigUpdate) {
            if (key in update.updatedKeys) {
                remoteConfig.activate()
                trySend(remoteConfig.getBoolean(key))
            }
        }
        override fun onError(error: FirebaseRemoteConfigException) {}
    }
    remoteConfig.addOnConfigUpdateListener(listener)
    awaitClose { /* cleanup */ }
}
```

UI updates when config changes without app restart.

## Common footguns

**Fetching in a loop.** One fetch at startup. Period. Background fetch via WorkManager if you need periodic refresh.

**No fetch failure handling.** Always try/catch fetch. Log failures. Monitor fetch success rate.

**Publishing breaking config.** A config change that crashes the app can't be rolled back instantly — cached values persist until next fetch. Test config changes against defaults. Use [feature flags](https://blog.michaelsam94.com/android-feature-flags-implementation/) with safe defaults.

**Stale cache after logout.** User properties change on login/logout. Force a fetch after auth state changes so conditions re-evaluate.

**Testing with production Remote Config.** Use Firebase's debug mode or a separate Firebase project for staging. Never test against production config values.

## Personalization without PII in conditions

Remote Config conditions support user properties set server-side:

```kotlin
// After login — set from your backend, not client guesswork
firebaseAnalytics.setUserProperty("subscription_tier", user.tier)
firebaseAnalytics.setUserProperty("account_age_days", user.ageDays.toString())
```

Never put email or user ID in condition rules visible in Firebase console to non-admin roles. Use hashed segments or tier enums.

## Rollout percentage strategy

```kotlin
// Parameter: new_checkout_enabled, default false
// Condition: App version >= 3.2 AND random percentile <= 10
```

Rollout pattern that works:

1. **0%** — deploy code with flag off, verify no regressions
2. **1%** — internal + random 1%, monitor crash rate 48h
3. **10% → 50% → 100%** — double every 2 days if metrics stable
4. **Remove flag** — after 2 weeks at 100%, delete dead code path

Keep kill switch at 0% rollback ready until flag removed from codebase.

## Analytics integration

Link Remote Config experiments to Firebase Analytics:

```kotlin
remoteConfig.setConfigSettingsAsync(
    remoteConfigSettings {
        minimumFetchIntervalInSeconds = if (BuildConfig.DEBUG) 0 else 3600
    }
)
firebaseAnalytics.logEvent("config_fetch_success", bundleOf("fetch_time_ms" to elapsed))
```

Monitor `config_fetch_failed` event rate — spike means Firebase outage or network issues blocking feature delivery.

Pair with [Android A/B testing Firebase](https://blog.michaelsam94.com/android-a-b-testing-firebase/) when running formal experiments with statistical significance.

## Common production mistakes

Teams get firebase remote config strategies wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping firebase remote config strategies on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Resources

- [Firebase Remote Config documentation](https://firebase.google.com/docs/remote-config)
- [Remote Config parameters and conditions](https://firebase.google.com/docs/remote-config/parameters)
- [Real-time Remote Config updates](https://firebase.google.com/docs/remote-config/propagate-updates-realtime)
- [Feature flags on Android](https://blog.michaelsam94.com/android-feature-flags-implementation/)
- [A/B testing mobile features](https://blog.michaelsam94.com/android-a-b-testing-firebase/)
