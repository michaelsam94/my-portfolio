---
title: "Java 8+ APIs via Desugaring"
slug: "android-desugaring-java-time"
description: "Use java.time, streams, and Java 8+ APIs on older Android versions with core library desugaring. Setup, supported APIs, and pitfalls with minSdk below 26."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Android", "Java", "Gradle", "Kotlin"]
keywords: "Android desugaring, core library desugaring, java.time Android, Java 8 APIs Android, desugar JDK libs"
faq:
  - q: "What is core library desugaring on Android?"
    a: "Core library desugaring rewrites Java 8+ platform APIs (java.time, streams, Optional, etc.) to work on Android versions below API 26, where these APIs aren't natively available. The desugaring library provides backported implementations that are bundled into your APK."
  - q: "Which Java APIs can be desugared on Android?"
    a: "java.time (Instant, LocalDate, ZonedDateTime, Duration, etc.), java.util.stream, java.util.function, Optional, and newer collections APIs. Not everything is supported — java.nio.file and some concurrent APIs are unavailable. Check the desugaring library release notes for the current supported set."
  - q: "Does desugaring increase APK size?"
    a: "Yes, modestly — typically 100–300KB for java.time alone. The desugaring library includes only the classes your app actually references (via R8 shrinking). For most apps the size cost is far outweighed by the developer productivity gain of using java.time instead of ThreeTenABP or Joda-Time."
---

If you're still using Joda-Time or ThreeTenABP in 2026, desugaring means you can stop. Core library desugaring backports `java.time`, streams, and other Java 8+ APIs to API 21+ devices, letting you write standard Java/Kotlin code without platform version checks. I've migrated four codebases off Joda-Time to `java.time` via desugaring; the API is cleaner, the timezone handling is better, and the migration was mostly mechanical. The setup is three lines in Gradle — the gotchas are knowing what's supported and not mixing desugared APIs with legacy date libraries.

## Enable desugaring

```kotlin
android {
    compileOptions {
        isCoreLibraryDesugaringEnabled = true
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.2")
}
```

That's it. Use `java.time` anywhere in your codebase:

```kotlin
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter

val now = Instant.now()
val date = LocalDate.now(ZoneId.of("America/Chicago"))
val formatted = DateTimeFormatter.ISO_LOCAL_DATE.format(date)
```

Works on API 21+. No `@RequiresApi` checks needed.

## What you can use

Commonly desugared APIs:

| Package | Examples | Notes |
|---------|----------|-------|
| `java.time` | Instant, LocalDate, ZonedDateTime, Duration, Period | Full JSR-310 |
| `java.util.stream` | Stream, Collectors, IntStream | Collection operations |
| `java.util.function` | Function, Predicate, Consumer | Functional interfaces |
| `java.util` | Optional, Map.entry() | |
| `java.nio` | ByteBuffer (partial) | Not full NIO |

Check the [desugar_jdk_libs release notes](https://github.com/google/desugar_jdk_libs/blob/master/CHANGELOG.md) for the latest additions — Google adds APIs regularly.

## What you cannot desugar

- `java.nio.file` — no filesystem NIO on older Android
- `java.lang.invoke` — method handles
- `java.util.concurrent` additions beyond basic support
- Most Java 11+ APIs (var handles, etc.)

For unsupported APIs, use Android-specific alternatives or kotlinx libraries.

## kotlinx-datetime as an alternative

For Kotlin Multiplatform projects, [kotlinx-datetime](https://blog.michaelsam94.com/kotlin-datetime-multiplatform/) works across platforms without desugaring:

```kotlin
// KMP: use kotlinx-datetime
import kotlinx.datetime.Clock
import kotlinx.datetime.TimeZone

// Android-only: java.time via desugaring is fine
import java.time.Instant
```

In KMP shared code, use kotlinx-datetime. In Android-only modules, `java.time` via desugaring is simpler and has better ecosystem support (Room TypeConverters, API serializers).

## Room and java.time

Room supports java.time with TypeConverters:

```kotlin
class Converters {
    @TypeConverter
    fun fromInstant(value: Instant?): Long? = value?.toEpochMilli()

    @TypeConverter
    fun toInstant(value: Long?): Instant? = value?.let { Instant.ofEpochMilli(it) }
}
```

Store as epoch millis or ISO strings in SQLite. Avoid storing formatted date strings — they're impossible to query.

## Migration from Joda-Time / ThreeTenABP

Mechanical replacements:

| Joda-Time | java.time |
|-----------|-----------|
| `DateTime.now()` | `Instant.now()` or `ZonedDateTime.now()` |
| `LocalDate.parse(str)` | `LocalDate.parse(str)` (same!) |
| `date.toDate()` | `Date.from(instant)` |
| `Interval` | `Duration.between(a, b)` |
| `DateTimeZone.forID("UTC")` | `ZoneId.of("UTC")` |

Remove Joda-Time/ThreeTenABP dependencies after migration:

```kotlin
// Remove these
// implementation("joda-time:joda-time:2.x")
// implementation("com.jakewharton.threetenabp:threetenabp:1.x")
```

Search for remaining imports:

```bash
grep -r "org.joda" src/
grep -r "org.threeten" src/
```

## D8/R8 interaction

Desugaring runs before R8 shrinking. R8 removes unused desugared classes, keeping APK impact minimal. If you only use `Instant` and `LocalDate`, you won't bundle the entire java.time package.

Ensure you're on AGP 8.0+ and R8 full mode for best shrinking:

```kotlin
android {
    buildTypes {
        release {
            isMinifyEnabled = true
        }
    }
}
```

## API 26+ native vs desugared

On API 26+ devices, Android provides native java.time. Desugaring uses the native implementation when available and falls back to the backport on older devices. No performance penalty on modern devices.

If your minSdk is 26+, you don't need desugaring for java.time — but enabling it anyway doesn't hurt and keeps your code portable if minSdk drops.

## kotlinx-datetime vs java.time on Android

For Kotlin Multiplatform projects, prefer `kotlinx-datetime` in shared code:

```kotlin
// commonMain
import kotlinx.datetime.Instant

// androidMain — convert at boundary
fun Instant.toJavaInstant(): java.time.Instant =
    java.time.Instant.ofEpochSecond(epochSeconds, nanosecondsOfSecond.toLong())
```

Use java.time directly in Android-only modules when not sharing with iOS. Mixing both in the same layer creates conversion boilerplate — pick one per module boundary.

## Common desugaring pitfalls

| Issue | Symptom | Fix |
|-------|---------|-----|
| Missing desugar dependency | `NoClassDefFoundError: java/time/Instant` on API 24 | Add `desugar_jdk_libs` |
| Wrong AGP version | Desugaring silently skipped | AGP 7.0+ required |
| Instant in Parcelable | Crash on process death | Store epoch millis Long |
| ZoneId everywhere | APK bloat from tz data | Use UTC internally, convert at UI |

Store timestamps as `Long` (epoch millis UTC) in Room — avoids serializer complexity and timezone bugs in SQL queries.

## Testing across API levels

Run instrumented tests on API 24 emulator specifically for date code paths — your API 34 dev device hides desugaring bugs. CI matrix: `{24, 26, 34}` covers backport, native transition, and current.

Pair with [Android DataStore migration](https://blog.michaelsam94.com/android-datastore-migration-sharedpreferences/) when migrating date fields from SharedPreferences strings to typed storage.

## Common production mistakes

Teams get desugaring java time wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping desugaring java time on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## API level minSdk 21 pitfalls

`java.time` desugaring adds method count — monitor dex size after enabling. `Duration` serialization across Gson without module adapters breaks release builds — add explicit TypeAdapter for temporal types in API models.

## ZoneId in offline apps

Ship `tzdata` updates via desugaring library version bumps. Stale zone rules mis-schedule alarms around DST — pin desugar libs version in catalog and upgrade with OS release QA.

## Desugaring Java Time Supplement 0 on Samsung and Pixel divergence

Exercise desugaring java time supplement 0 on Galaxy A-series and Pixel a-series — emulators hide OEM battery and storage quirks. Capture Macrobenchmark or Firebase trace for the critical path touching desugaring; regressions above 8% block release for `android-desugaring-java-time-supplement-0`.

Document permission and background behavior in internal runbook: what breaks under Doze, what requires foreground service, and what Play policy declarations apply. Support tickets referencing "Desugaring Java Time Supplement 0" should map to a single runbook section with known workarounds.

## Time regression gates for Play Vitals

Before promoting `android-desugaring-java-time-supplement-0` changes past 20% rollout, compare ANR rate, slow cold start, and excessive wakeups against seven-day baseline. Fail rollback review if 0 path shows >5% increase in `slow frames` without documented trade-off approval.

## Field testing desugaring with battery saver enabled

Xiaomi and Oppo ship aggressive background killers. After implementing desugaring java time supplement 0, run 24-hour monkey test on three OEM devices with battery saver enabled. Failures here predict one-star reviews that Crashlytics never captures — especially for 0 flows that assume reliable background delivery.

## Resources

- [Java 8+ API desugaring support (Android)](https://developer.android.com/studio/write/java8-support-table)
- [desugar_jdk_libs changelog](https://github.com/google/desugar_jdk_libs/blob/master/CHANGELOG.md)
- [Java time API tutorial (Oracle)](https://docs.oracle.com/javase/tutorial/datetime/)
- [Room TypeConverters reference](https://developer.android.com/reference/androidx/room/TypeConverter)
- [kotlinx-datetime for multiplatform](https://blog.michaelsam94.com/kotlin-datetime-multiplatform/)
