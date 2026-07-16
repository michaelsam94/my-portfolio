---
title: "Integrating with Health Connect"
slug: "android-health-connect-integration"
description: "Integrate Android Health Connect: permissions, reading and writing health records, data types, background sync, and privacy requirements for health apps."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Android", "Health Connect", "Privacy", "Integration"]
keywords: "Health Connect Android, Health Connect API, Android health data, Health Connect permissions, health records Android"
faq:
  - q: "What is Health Connect on Android?"
    a: "Health Connect is Android's centralized health and fitness data platform. It provides a unified API for reading and writing health records (steps, heart rate, sleep, nutrition, etc.) and acts as a permission-controlled datastore that apps share data through, replacing direct access to Google Fit and siloed health databases."
  - q: "How do Health Connect permissions work?"
    a: "Health Connect uses granular per-data-type permissions (read/write separately for steps, heart rate, sleep, etc.). Users grant permissions through the Health Connect permission UI, not standard Android runtime permissions. Your app declares required permissions in the manifest and requests them at runtime via the Health Connect permission contract."
  - q: "Do I need Health Connect or can I use Google Fit directly?"
    a: "Google Fit APIs are deprecated in favor of Health Connect. New apps should integrate with Health Connect directly. If your app currently reads from Google Fit, migrate to Health Connect — it provides the same data with better privacy controls and is the platform Google is investing in."
---

Health Connect is Android's bet on health data not being locked in silos — steps in one app, sleep in another, heart rate in a third, none talking to each other. It provides a unified datastore with granular permissions: users choose exactly which data types each app can read or write. Building a fitness app, wellness tracker, or medical integration in 2026 means Health Connect, not Google Fit (deprecated) or proprietary SDKs. The API is clean; the complexity is in permission UX, background sync policies, and the privacy requirements Google enforces during Health Connect app review.

## Setup

```kotlin
dependencies {
    implementation("androidx.health.connect:connect-client:1.1.0")
}
```

```xml
<!-- AndroidManifest.xml -->
<uses-permission android:name="android.permission.health.READ_STEPS" />
<uses-permission android:name="android.permission.health.WRITE_STEPS" />
<uses-permission android:name="android.permission.health.READ_HEART_RATE" />

<!-- Required for Health Connect to discover your app -->
<activity android:name=".PermissionsActivity" android:exported="true">
    <intent-filter>
        <action android:name="androidx.health.ACTION_SHOW_PERMISSIONS_RATIONALE" />
    </intent-filter>
</activity>

<activity-alias
    android:name="ViewPermissionUsageActivity"
    android:exported="true"
    android:targetActivity=".PermissionsActivity"
    android:permission="android.permission.START_VIEW_PERMISSION_USAGE">
    <intent-filter>
        <action android:name="android.intent.action.VIEW_PERMISSION_USAGE" />
        <category android:name="android.intent.category.HEALTH_PERMISSIONS" />
    </intent-filter>
</activity-alias>
```

The activity-alias for `VIEW_PERMISSION_USAGE` is required — Health Connect app review checks for it.

## Checking availability and permissions

```kotlin
class HealthConnectManager(private val context: Context) {
    private val client = HealthConnectClient.getOrCreate(context)

    suspend fun isAvailable(): Boolean {
        return HealthConnectClient.getSdkStatus(context) == HealthConnectClient.SDK_AVAILABLE
    }

    suspend fun hasAllPermissions(permissions: Set<String>): Boolean {
        val granted = client.permissionController.getGrantedPermissions()
        return permissions.all { it in granted }
    }

    fun permissionLauncher(
        activity: ComponentActivity,
        onResult: (Boolean) -> Unit
    ): ActivityResultLauncher<Set<String>> {
        return activity.registerForActivityResult(
            PermissionController.createRequestPermissionResultContract()
        ) { granted ->
            onResult(granted.containsAll(requiredPermissions))
        }
    }
}
```

Request permissions with rationale:

```kotlin
if (!healthConnect.hasAllPermissions(requiredPermissions)) {
    if (shouldShowRationale) {
        showRationaleDialog {
            permissionLauncher.launch(requiredPermissions)
        }
    } else {
        permissionLauncher.launch(requiredPermissions)
    }
}
```

## Reading health records

```kotlin
suspend fun readTodaySteps(): Long {
    val now = Instant.now()
    val startOfDay = now.atZone(ZoneId.systemDefault()).toLocalDate()
        .atStartOfDay(ZoneId.systemDefault()).toInstant()

    val response = client.readRecords(
        ReadRecordsRequest(
            recordType = StepsRecord::class,
            timeRangeFilter = TimeRangeFilter.between(startOfDay, now),
        )
    )
    return response.records.sumOf { it.count }
}
```

Available record types include: `StepsRecord`, `HeartRateRecord`, `SleepSessionRecord`, `WeightRecord`, `NutritionRecord`, `DistanceRecord`, `ActiveCaloriesBurnedRecord`, and more. Check the [Health Connect data types reference](https://developer.android.com/reference/kotlin/androidx/health/connect/client/records/package-summary) for the full list.

## Writing records

```kotlin
suspend fun writeSteps(count: Long, startTime: Instant, endTime: Instant) {
    val record = StepsRecord(
        count = count,
        startTime = startTime,
        endTime = endTime,
        startZoneOffset = ZoneOffset.systemDefault().rules.getOffset(startTime),
        endZoneOffset = ZoneOffset.systemDefault().rules.getOffset(endTime),
    )
    client.insertRecords(listOf(record))
}
```

Always include zone offsets — Health Connect requires them for temporal records.

## Background sync with changes token

For efficient background reads without polling:

```kotlin
suspend fun syncChanges() {
    var changesToken = prefs.getString("changes_token", null)

    val changes = client.getChanges(
        ChangesTokenRequest(changesToken ?: "")
    )

    for (change in changes.changes) {
        when (change) {
            is UpsertionChange -> handleNewRecord(change.record)
            is DeletionChange -> handleDeletedRecord(change.recordId)
        }
    }

    prefs.edit { putString("changes_token", changes.nextChangesToken) }
}
```

Run via WorkManager on a periodic schedule. Much more efficient than full re-reads.

## Privacy requirements

Health Connect apps go through additional review:

- **Data use disclosure** — clearly explain what health data you read/write and why
- **Minimum permissions** — request only what you need
- **No selling health data** — Google policy prohibits it
- **Encryption in transit and at rest** for any health data you store on your servers
- **Permission rationale activity** — required manifest entries above

Build the privacy policy link into your permission request flow. Health Connect review rejects apps with vague data use descriptions.

## Health Connect vs platform sensors

Health Connect is a data aggregation layer, not a sensor API. To read live sensor data (real-time heart rate during a workout), use the Android Sensor API or Health Services API directly, then write results to Health Connect for other apps to access.

```
Sensors/Health Services → your app processes → write to Health Connect → other apps read
```

## Permission and data minimization

Request only Health Connect permissions your feature needs:

```kotlin
val permissions = setOf(
    HealthPermission.getReadPermission(StepsRecord::class),
    HealthPermission.getReadPermission(HeartRateRecord::class),
)
```

Background reads require explicit user grant. Show in-app rationale before system permission dialog — Health Connect denial is hard to reverse.

## Common production mistakes

Teams get health connect integration wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping health connect integration on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Debugging and triage workflow

When health connect integration misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Health Connect documentation](https://developer.android.com/health-and-fitness/guides/health-connect)
- [Health Connect data types](https://developer.android.com/reference/kotlin/androidx/health/connect/client/records/package-summary)
- [Health Connect permission model](https://developer.android.com/health-and-fitness/guides/health-connect/develop/get-started)
- [Migrate from Google Fit to Health Connect](https://developer.android.com/health-and-fitness/guides/health-connect/migrate/fit)
- [Health Services API for wearables](https://developer.android.com/training/wearables/health-services)
