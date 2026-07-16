---
title: "kotlinx-datetime for Multiplatform Time"
slug: "kotlin-datetime-multiplatform"
description: "Handle dates and times in Kotlin Multiplatform with kotlinx-datetime: Instant, LocalDateTime, time zones, parsing, and avoiding java.time on non-JVM targets."
datePublished: "2025-12-03"
dateModified: "2025-12-03"
tags: ["Android", "Kotlin"]
keywords: "kotlinx-datetime, Kotlin Multiplatform, Instant, TimeZone, LocalDateTime, ISO 8601, multiplatform time"
faq:
  - q: "Why not use java.time on Android and expect/actual elsewhere?"
    a: "java.time works on JVM and Android API 26+ with desugaring, but it does not exist on iOS, JS, or Native without expect/actual wrappers you maintain. kotlinx-datetime provides one API across all KMP targets with consistent parsing and arithmetic."
  - q: "How do I convert kotlinx-datetime Instant to platform types?"
    a: "On JVM use toJavaInstant() extension. On iOS map epoch seconds to NSDate. Keep domain logic in kotlinx-datetime types and convert only at UI or platform integration boundaries."
  - q: "Does kotlinx-datetime handle daylight saving transitions?"
    a: "Yes, when you use TimeZone with LocalDateTime conversions. Arithmetic on Instant is always UTC-safe. Converting LocalDateTime to Instant through a TimeZone applies offset rules including DST gaps and overlaps."
---

Shipping a KMP app that showed meeting times wrong for Helsinki users was not a UI bug—the shared module parsed `"2025-03-30T02:30:00"` as UTC because someone used string concatenation instead of timezone-aware conversion. `java.time` on Android and manual epoch math on iOS diverged. Consolidating on **kotlinx-datetime** fixed one module, one test suite, three platforms.

**kotlinx-datetime** is JetBrains' multiplatform date/time library. It covers instants, civil dates, time zones, and parsing without pulling platform-specific APIs into common code.

## Core types

| Type | Use case |
|------|----------|
| `Instant` | Absolute point on timeline (UTC internally) |
| `LocalDate` | Calendar date without time or zone |
| `LocalDateTime` | Civil date-time without zone |
| `TimeZone` | Rules for offset from UTC |
| `Clock` | Testable source of "now" |

```kotlin
// commonMain
import kotlinx.datetime.*

fun eventStart(): Instant =
    Clock.System.now()

fun formatForUser(instant: Instant, zone: TimeZone): String {
    val local = instant.toLocalDateTime(zone)
    return "${local.date} ${local.hour}:${local.minute.toString().padStart(2, '0')}"
}
```

## Parsing ISO 8601

```kotlin
val instant = Instant.parse("2025-12-03T14:30:00Z")
val localDate = LocalDate.parse("2025-12-03")
val dateTime = LocalDateTime.parse("2025-12-03T14:30:00")
```

For offsets in strings:

```kotlin
val offsetDateTime = "2025-12-03T14:30:00+02:00"
    .let { Instant.parse(it.replace("+02:00", "Z").let { z -> /* use appropriate parser */ }) }
```

Prefer explicit `TimeZone.of("Europe/Helsinki")` when converting local picks to instants:

```kotlin
val zone = TimeZone.of("Europe/Helsinki")
val local = LocalDateTime(2025, 12, 3, 14, 30)
val instant = local.toInstant(zone)
```

## Arithmetic and durations

```kotlin
val tomorrow = Clock.System.now().plus(1, DateTimeUnit.DAY, TimeZone.UTC)
val daysBetween = firstDate.daysUntil(secondDate)
```

Use `DateTimePeriod` for calendar-aware additions (months, years):

```kotlin
val billingCycle = startDate.plus(DateTimePeriod(months = 1))
```

`Duration` from kotlinx covers elapsed time between instants—distinct from `DateTimePeriod`.

## Testing with Clock

Inject a controllable clock:

```kotlin
class FakeClock(var now: Instant) : Clock {
    override fun now(): Instant = now
}

@Test
fun expiry() {
    val clock = FakeClock(Instant.parse("2025-01-01T00:00:00Z"))
    val session = Session(clock, ttlHours = 24)
    clock.now = Instant.parse("2025-01-02T01:00:00Z")
    assertTrue(session.isExpired())
}
```

Avoid `Clock.System.now()` directly in business logic you unit test.

## Platform interop

JVM/Android:

```kotlin
// jvmMain or androidMain
import kotlinx.datetime.toJavaInstant
import java.time.format.DateTimeFormatter

fun Instant.toFormattedString(): String =
    DateTimeFormatter.ISO_INSTANT.format(toJavaInstant())
```

iOS uses similar boundary conversion to `NSDate` in platform code—keep formatting locale-specific strings in UI layers.

## Serialization

With kotlinx.serialization, add a custom serializer or use string ISO format in JSON:

```kotlin
@Serializable
data class Event(
    val id: String,
    @Serializable(with = InstantIsoSerializer::class)
    val startsAt: Instant
)
```

Store and transmit instants in UTC; convert to local only for display.

## Migration from java.time

Map `ZonedDateTime` → `Instant` + `TimeZone`. Map `Period` → `DateTimePeriod`. Watch for nanosecond precision—kotlinx-datetime uses millisecond precision for Instant in current versions.

## kotlinx-datetime vs kotlin.time

`kotlin.time.Duration` measures elapsed time between instants; `DateTimePeriod` handles calendar months/years. Do not add "1 month" as 30 days—use `DateTimePeriod` for billing cycles.

## Locale display

Format dates in UI layer with platform formatters; store/transmit `Instant` only in commonMain.


## What to measure after rollout

Track error rates, tail latency, and resource utilization for two weeks after changes land—most regressions appear under real traffic mixes, not in staging smoke tests. Keep a rollback path documented: feature flags, Helm revision, or Git revert with known good digest. Review on-call pages tied to the topic quarterly; delete alerts that never fire and add thresholds that would have caught your last incident.

Run a short blameless postmortem if production surprised you, even for minor issues. The goal is updating this runbook section with one concrete lesson per quarter so the next engineer inherits context, not just configuration snippets.


## Documentation your team should maintain

Maintain a one-page runbook link from your main service README: prerequisites, owner rotation, last drill date, and known sharp edges. Link to vendor docs in the Resources section below but capture org-specific decisions (CIDR ranges, cluster names, approval gates) in internal docs that stay current. New hires should deploy a safe canary within a week using only that runbook—if they cannot, the doc is incomplete.


## Pre-production checklist

Before promoting to production, walk through this list with someone who was not the primary author—fresh eyes catch assumptions.

- **Staging parity**: The staging environment exercises the same code paths as production, including failure modes you expect to handle (timeouts, retries, partial outages).
- **Observability**: Dashboards and alerts exist for the metrics and log patterns discussed above; on-call knows where to look first.
- **Rollback**: You can revert to the previous known-good state in one documented step without improvising.
- **Access control**: Only the principals that need access have it; audit logs are enabled where the topic touches secrets or infrastructure APIs.
- **Load test**: You have evidence—not intuition—about behavior at expected peak plus headroom.

If any item is "we will do that later," treat it as a release blocker for tier-1 services.


## Common questions from reviewers

Reviewers and auditors often ask whether this approach scales with team growth and whether it fails safely. Answer explicitly in your design doc: what happens when dependencies are down, when credentials expire, and when traffic doubles overnight. Prefer defaults that deny or degrade gracefully over defaults that fail open. Document known limits (throughput ceilings, supported versions, regions) in the same place operators look during incidents—avoid scattering critical constraints across Slack threads.


## Version and compatibility notes

Pin library and control-plane versions in production manifests; track upstream release notes quarterly. Run upgrade drills in non-production before bumping minor versions that touch serialization, auth, or CRD schemas. Keep a compatibility matrix in your internal wiki listing supported Kubernetes, broker, and SDK versions validated together.

## Resources

- [kotlinx-datetime GitHub](https://github.com/Kotlin/kotlinx-datetime) — API reference and release notes
- [Kotlin Multiplatform datetime guide](https://kotlinlang.org/docs/multiplatform/compose-multiplatform.html) — integration with shared modules
- [Time zone database updates](https://www.iana.org/time-zones) — IANA rules underlying TimeZone
- [ISO 8601 standard summary](https://www.iso.org/iso-8601-date-and-time-format.html) — string format conventions
