---
title: "Wear OS Complications, End to End"
slug: "android-wearos-complications"
description: "Build Wear OS complications from ComplicationProviderService through Watch Face Format slots. Handle update requests, battery-friendly refresh schedules, and testing on emulators and devices."
datePublished: "2024-09-05"
dateModified: "2024-09-05"
tags: ["Android", "Wear OS", "Complications", "Watch Face"]
keywords: "Wear OS complications, ComplicationProviderService, Watch Face Format, complication data source, Wear OS watch face"
faq:
  - q: "What is a complication on Wear OS?"
    a: "A complication is a small data slot on a watch face showing app data — weather, next calendar event, step count, or battery level. Your app implements ComplicationProviderService and responds to update requests from the watch face with ComplicationData (text, icons, tap actions)."
  - q: "How often can complications update?"
    a: "Watch faces request updates on their schedule, not yours. You declare supported update frequencies (static, periodic) in ComplicationProviderService metadata. Aggressive refresh drains battery and Google may throttle your provider. Use minimum necessary frequency and push updates via ComplicationDataSourceUpdateRequester when data changes significantly."
  - q: "Do I need a watch face to publish a complication?"
    a: "No. Any app can expose a complication data source that users add to third-party or system watch faces. You need a ComplicationProviderService, proper manifest entries, and a supported complication type (SHORT_TEXT, RANGED_VALUE, etc.)."
---

Watch face real estate is tiny and contested. Users pick watch faces partly based on which complications are available — a fitness app that exposes today's workout as a tappable SHORT_TEXT slot stays visible all day without opening the app. Complications are the distribution channel for glanceable data on Wear OS, and implementing them correctly means respecting battery, update contracts, and the Watch Face Format slot types introduced in Wear OS 4+.

## Architecture overview

```
Watch Face  →  requests update  →  ComplicationProviderService
                                         ↓
                                  ComplicationData (text/icon/tap)
                                         ↓
Watch Face  ←  renders slot    ←  provider response
```

Your service never draws the UI — you supply structured data and the watch face renders it in its style.

## ComplicationProviderService

```kotlin
class NextEventComplicationService : ComplicationDataSourceService() {

    override fun onComplicationRequest(
        request: ComplicationRequest,
        listener: ComplicationDataSourceService.ComplicationRequestListener
    ) {
        scope.launch {
            val event = calendarRepository.nextEvent()
            val data = if (event != null) {
                ShortTextComplicationData.Builder(
                    text = PlainComplicationText.Builder(event.title).build(),
                    contentDescription = PlainComplicationText.Builder(
                        "Next event: ${event.title}"
                    ).build()
                )
                    .setTapAction(launchPendingIntent(event.id))
                    .build()
            } else {
                NoDataComplicationData()
            }
            listener.onComplicationData(data)
        }
    }

    override fun getPreviewData(type: ComplicationType): ComplicationData {
        return ShortTextComplicationData.Builder(
            text = PlainComplicationText.Builder("Team standup").build(),
            contentDescription = PlainComplicationText.Builder("Preview").build()
        ).build()
    }
}
```

Register in the manifest:

```xml
<service
    android:name=".NextEventComplicationService"
    android:exported="true"
    android:label="@string/complication_next_event"
    android:permission="com.google.android.wearable.permission.BIND_COMPLICATION_PROVIDER">
    <intent-filter>
        <action android:name="androidx.wear.watchface.complications.datasource.ComplicationDataSourceService" />
    </intent-filter>
    <meta-data
        android:name="androidx.wear.watchface.complications.datasource.ComplicationDataSourceService"
        android:resource="@xml/complication_config" />
</service>
```

## Complication config XML

```xml
<!-- res/xml/complication_config.xml -->
<complication-data-source
    xmlns:android="http://schemas.android.com/apk/res/android"
    android:updatePeriodMillis="1800000"
    android:supportedTypes="SHORT_TEXT,LONG_TEXT" />
```

`updatePeriodMillis` of 1,800,000 (30 minutes) is reasonable for calendar data. Don't set `0` unless you have a strong reason — the system treats it as "as fast as possible."

## Supported complication types

| Type | Use case | Example |
|------|----------|---------|
| SHORT_TEXT | Single value | "72°", "8,432 steps" |
| LONG_TEXT | Two-line | Event title + time |
| RANGED_VALUE | Progress | Goal 60% complete |
| SMALL_IMAGE | Icon | Weather condition |
| MONochromatic_IMAGE | Themed icon | App shortcut |
| GOAL_PROGRESS | Ring fill | Daily step goal |

Pick types your data actually fits. Stretching LONG_TEXT into a SHORT_TEXT slot truncates unpredictably across watch faces.

## Pushing updates on data change

When the user completes a workout, don't wait for the periodic refresh:

```kotlin
class WorkoutTracker {
    fun onWorkoutComplete() {
        val requester = ComplicationDataSourceUpdateRequester.create(
            context,
            ComponentName(context, WorkoutComplicationService::class.java)
        )
        requester.requestUpdate(ComplicationType.SHORT_TEXT)
    }
}
```

This tells active watch faces to re-request data immediately for that complication type.

## Tap actions

Complications should deep-link into the relevant app screen:

```kotlin
private fun launchPendingIntent(eventId: String): PendingIntent {
    val intent = Intent(context, EventDetailActivity::class.java)
        .putExtra("event_id", eventId)
        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    return PendingIntent.getActivity(
        context, eventId.hashCode(), intent,
        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
    )
}
```

Use immutable PendingIntents on API 31+.

## Testing

Wear OS emulator supports complication preview in Android Studio's watch face editor. For integration testing:

1. Install your app on a Wear emulator paired with a phone emulator.
2. Long-press watch face → Customize → Complications → select your provider.
3. Verify preview data in the picker matches `getPreviewData()`.

On-device testing catches font scaling and color contrast issues emulators miss — especially for RANGED_VALUE arcs on circular faces.

## Battery and throttling

I've seen complications get throttled after setting `updatePeriodMillis` to 60 seconds for stock prices. The OS batches updates across providers. Design for stale-tolerant UI — show last-known value with a subtle timestamp rather than blocking on network in `onComplicationRequest`. Do network I/O with timeouts under 5 seconds; return `NoDataComplicationData()` on failure.

## Complication types and layout constraints

Each watch face slot supports specific types. Mismatch returns empty slots or crashes in preview:

| Type | Best for | Layout notes |
|------|----------|--------------|
| SHORT_TEXT | Counts, status | 7–9 chars on circular faces |
| LONG_TEXT | Event titles | Truncate with ellipsis |
| RANGED_VALUE | Progress, battery | Min/max required; color obeys face theme |
| SMALL_IMAGE | App icon, weather | Monochrome on some faces |
| MONOOCHROMATIC_IMAGE | Simplified icons | Single-color vector preferred |

Always implement `getPreviewData()` with representative content — users pick complications from the picker preview, not your live data.

## Data caching architecture

Never fetch from network inside `onComplicationRequest` synchronously. Pattern that works:

```
WorkManager periodic sync (15–30 min)
    → Room cache on watch
    → Complication reads cache (< 10 ms)
    → requestUpdate() after sync completes
```

For time-sensitive data (next calendar event), use `updatePeriodMillis` of 15 minutes minimum and push immediate updates via `ComplicationDataSourceUpdateRequester` when the phone app receives a push notification.

## Wear OS 5+ considerations

Google is consolidating watch faces around Watch Face Format (WFF). Complications remain supported via `ComplicationDataSourceService`, but test on:

- **Round vs square** form factors (Pixel Watch vs Galaxy Watch Ultra)
- **Material You** color slots — use `ComplicationText.Builder` with dynamic colors
- **Ambient mode** — provide low-burn complications or hide sensitive data

Pair with [Wear OS Compose Tiles](https://blog.michaelsam94.com/android-wearos-compose-tiles/) for richer glanceable UI beyond complication slot limits.

## Production checklist

- [ ] Network I/O never blocks `onComplicationRequest`
- [ ] `getPreviewData()` matches production layout constraints
- [ ] WorkManager sync with `requestUpdate()` after cache refresh
- [ ] Tested on round and square form factors
- [ ] Stale data shown with timestamp, not loading spinner

## Common production mistakes

Teams get wearos complications wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping wearos complications on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Resources

- [Wear OS complications overview](https://developer.android.com/training/wearables/complications)
- [ComplicationDataSourceService API](https://developer.android.com/reference/androidx/wear/watchface/complications/datasource/ComplicationDataSourceService)
- [Watch Face Format documentation](https://developer.android.com/training/wearables/wff)
- [Complication types reference](https://developer.android.com/reference/androidx/wear/watchface/complications/data/ComplicationType)
- [ComplicationDataSourceUpdateRequester](https://developer.android.com/reference/androidx/wear/watchface/complications/datasource/ComplicationDataSourceUpdateRequester)
