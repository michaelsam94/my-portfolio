---
title: "Migrating SharedPreferences to DataStore"
slug: "android-datastore-migration-sharedpreferences"
description: "Step-by-step migration from SharedPreferences to Jetpack DataStore: Preferences DataStore, Proto DataStore, dual-read migration, and avoiding the first-read-on-main-thread trap."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Android", "DataStore", "Architecture", "Kotlin"]
keywords: "SharedPreferences to DataStore migration, Preferences DataStore, Proto DataStore, Jetpack DataStore, Android preferences migration"
faq:
  - q: "Why migrate from SharedPreferences to DataStore?"
    a: "SharedPreferences reads synchronously from disk on first access — often on the main thread — causing jank and ANRs. It has no type safety, no transactional API, and no coroutine/Flow support. DataStore provides async reads via Flow, type-safe access, transactional writes, and structured error handling."
  - q: "Should I use Preferences DataStore or Proto DataStore?"
    a: "Use Preferences DataStore as a direct SharedPreferences replacement for key-value settings (theme, flags, tokens). Use Proto DataStore when you need structured typed objects with schema evolution — user profiles, complex config. Preferences DataStore is simpler; Proto DataStore is safer for complex data."
  - q: "How do I migrate without losing existing user data?"
    a: "Use the SharedPreferencesMigration factory when creating your DataStore instance. It reads existing SharedPreferences keys into DataStore on first access. Run dual-read during transition: check DataStore first, fall back to SharedPreferences, then write to DataStore. Remove SharedPreferences reads once migration is confirmed."
---

SharedPreferences is the most common source of main-thread disk I/O in Android apps that don't think they do disk I/O on the main thread. The first `getString()` after process start reads the XML file synchronously — fast on your dev device, 50–200ms on a budget phone under storage pressure, right during Activity creation. DataStore fixes this by design: all reads are async via Flow, writes are transactional, and the API is coroutine-native. I've migrated six apps from SharedPreferences to DataStore; the migration itself is straightforward, but the dual-read transition period and the "which DataStore type?" decision trip up most teams.

## Preferences DataStore setup

Drop-in replacement for key-value preferences:

```kotlin
private val Context.dataStore by preferencesDataStore(name = "settings")

object SettingsKeys {
    val THEME = stringPreferencesKey("theme")
    val NOTIFICATIONS_ENABLED = booleanPreferencesKey("notifications_enabled")
    val LAST_SYNC = longPreferencesKey("last_sync")
}

class SettingsRepository(private val context: Context) {
    val theme: Flow<String> = context.dataStore.data
        .map { prefs -> prefs[SettingsKeys.THEME] ?: "system" }

    suspend fun setTheme(theme: String) {
        context.dataStore.edit { prefs ->
            prefs[SettingsKeys.THEME] = theme
        }
    }
}
```

Collect in ViewModel:

```kotlin
class SettingsViewModel(repo: SettingsRepository) : ViewModel() {
    val theme = repo.theme.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), "system")

    fun setTheme(theme: String) = viewModelScope.launch {
        repo.setTheme(theme)
    }
}
```

No main-thread disk reads. UI updates reactively when data changes.

## Proto DataStore for structured data

When settings aren't flat key-value pairs:

```protobuf
// user_settings.proto
syntax = "proto3";
option java_package = "com.example.app";
option java_multiple_files = true;

message UserSettings {
    string theme = 1;
    bool notifications_enabled = 2;
    int64 last_sync = 3;
    repeated string favorite_ids = 4;
}
```

```kotlin
private val Context.userSettingsStore by dataStore(
    fileName = "user_settings.pb",
    serializer = UserSettingsSerializer
)

class UserSettingsSerializer : Serializer<UserSettings> {
    override val defaultValue = UserSettings.getDefaultInstance()
    override suspend fun readFrom(input: InputStream) = UserSettings.parseFrom(input)
    override suspend fun writeTo(t: UserSettings, output: OutputStream) = t.writeTo(output)
}
```

Proto DataStore gives you schema evolution (add fields with defaults), type safety, and atomic read/write of the entire object. Use it when you have nested or list data that would be awkward as flat preference keys.

## Migration from SharedPreferences

DataStore provides a built-in migration factory:

```kotlin
private val Context.dataStore by preferencesDataStore(
    name = "settings",
    produceMigrations = { context ->
        listOf(
            SharedPreferencesMigration(
                context,
                "old_shared_prefs_name",
                keysToMigrate = setOf("theme", "notifications_enabled", "last_sync")
            )
        )
    }
)
```

On first DataStore access, it reads specified keys from the old SharedPreferences file and writes them to DataStore. Keys not listed are left in SharedPreferences for manual cleanup.

## Dual-read transition pattern

For zero-downtime migration in production:

```kotlin
class MigrationSettingsRepository(private val context: Context) {
    private val legacyPrefs = context.getSharedPreferences("settings", Context.MODE_PRIVATE)

    val theme: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[SettingsKeys.THEME]
            ?: legacyPrefs.getString("theme", "system")  // fallback
            ?: "system"
    }

    suspend fun setTheme(theme: String) {
        context.dataStore.edit { it[SettingsKeys.THEME] = theme }
        // Write to both during transition
        legacyPrefs.edit { putString("theme", theme) }.apply()
    }
}
```

After confirming migration via analytics (check DataStore has values for migrated keys), remove SharedPreferences reads and writes. Delete the old SharedPreferences file in a one-time cleanup:

```kotlin
if (!legacyPrefs.getBoolean("datastore_migration_complete", false)) {
    context.deleteSharedPreferences("settings")
    legacyPrefs.edit { putBoolean("datastore_migration_complete", true) }.apply()
}
```

## StrictMode will thank you

If you use [StrictMode](https://blog.michaelsam94.com/android-strictmode-debugging/) in debug builds, SharedPreferences first-read triggers disk-read violations immediately. DataStore eliminates this entire category. Every app I've migrated stopped producing StrictMode disk warnings on startup.

## Common pitfalls

**Creating multiple DataStore instances for the same file.** Use a singleton/delegated property — DataStore throws if you create duplicate instances for the same file name.

**Calling `.first()` on the main thread without care.** DataStore reads are async, but `.first()` in a blocking context still suspends. Always collect from coroutines, not from `onCreate()` synchronously.

**Migrating everything to Proto when Preferences suffices.** If your SharedPreferences had 5 string/boolean keys, use Preferences DataStore. Proto adds protobuf compilation overhead for simple cases.

**Not migrating encrypted SharedPreferences.** If you used EncryptedSharedPreferences, plan a separate migration path — read from encrypted, write to DataStore, with appropriate key management.

## Testing

DataStore provides a test artifact:

```kotlin
@Test
fun themeDefaultsToSystem() = runTest {
    val testDataStore = PreferenceDataStoreFactory.create(
        scope = TestScope(),
        produceFile = { tempFile.newFile() }
    )
    // test against testDataStore
}
```

No SharedPreferences mocking needed — fresh DataStore per test.

Treat production rollout as a measured change: ship with observability, validate rollback, and review metrics 24 hours after deploy — patterns that look obvious in docs fail when skipped under release pressure.

## Common production mistakes

Teams get datastore migration sharedpreferences wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping datastore migration sharedpreferences on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Debugging and triage workflow

When datastore migration sharedpreferences misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [DataStore guide (Android)](https://developer.android.com/topic/libraries/architecture/datastore)
- [Preferences DataStore reference](https://developer.android.com/reference/kotlin/androidx/datastore/preferences/core/package-summary)
- [Proto DataStore guide](https://developer.android.com/topic/libraries/architecture/datastore#proto-datastore)
- [Migrate SharedPreferences to DataStore (codelab)](https://developer.android.com/codelabs/android-preferences-datastore)
- [StrictMode debugging for main-thread I/O](https://blog.michaelsam94.com/android-strictmode-debugging/)
