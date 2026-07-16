---
title: "Building Wear OS Tiles with Compose"
slug: "android-wearos-compose-tiles"
description: "Wear OS Tiles show glanceable app content outside the watch face. Build TileProviderService with Compose for Tiles, handle click actions, and refresh tiles efficiently on Wear OS 3+."
datePublished: "2024-09-10"
dateModified: "2024-09-10"
tags: ["Android", "Wear OS", "Compose", "Tiles"]
keywords: "Wear OS Tiles, TileProviderService, Compose for Tiles, androidx.wear.tiles, glanceable watch UI"
faq:
  - q: "What is the difference between a Tile and a complication?"
    a: "Complications are small slots rendered inside a watch face by the face designer. Tiles are full swipeable cards in the tile carousel — left of the watch face — with richer layouts and multiple interactive elements. Tiles are better for multi-field summaries; complications for always-visible single metrics."
  - q: "Can I use Compose to build Wear OS Tiles?"
    a: "Yes. Compose for Tiles (androidx.wear.tiles: tiles-compose) lets you define tile layouts declaratively with Compose-style builders that compile to Tile proto layouts. This replaces hand-built LayoutElement trees for most use cases."
  - q: "How do Tiles get refreshed?"
    a: "Tiles refresh when the user swipes to them, on a system schedule, or when your app calls TileService.getUpdater().requestUpdate(). Avoid requesting updates more often than every few minutes unless data is time-critical — excessive refresh impacts battery."
---

Tiles occupy the swipe-left zone on Wear OS — a carousel of app cards users check without launching full apps. A transit tile showing the next two departures, a fitness tile with today's stats, a smart home tile with scene toggles. Before Compose for Tiles, you built layouts by constructing `LayoutElement` protobuf trees by hand. Now you write composable-style Kotlin that reads like the rest of your Wear codebase.

## TileProviderService setup

```kotlin
class TransitTileService : TileService() {

    override fun onTileRequest(requestParams: RequestParams): ListenableFuture<Tile> {
        return Futures.immediateFuture(
            tile(requestParams.deviceConfiguration) {
                TransitTileContent(
                    departures = repository.cachedDepartures()
                )
            }
        )
    }

    override fun onResourcesRequest(requestParams: RequestParams): ListenableFuture<Resources> {
        return Futures.immediateFuture(resources { /* icons */ })
    }
}
```

Manifest registration:

```xml
<service
    android:name=".TransitTileService"
    android:exported="true"
    android:label="@string/tile_transit"
    android:permission="com.google.android.wearable.permission.BIND_TILE_PROVIDER">
    <intent-filter>
        <action android:name="androidx.wear.tiles.action.BIND_TILE_PROVIDER" />
    </intent-filter>
    <meta-data
        android:name="androidx.wear.tiles.PREVIEW"
        android:resource="@drawable/tile_transit_preview" />
</service>
```

Provide a preview drawable — users see it when adding tiles.

## Compose for Tiles layout

```kotlin
fun TransitTileContent(departures: List<Departure>) {
    Column(
        modifier = Modifier.fillMaxWidth().padding(8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text("Next trains", style = TileTypography.titleMedium)
        Spacer(Modifier.height(4.dp))
        departures.take(3).forEach { dep ->
            Row(
                modifier = Modifier.fillMaxWidth().clickable(
                    onClick = Clickable(onClick = launchDeparture(dep.id))
                ),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(dep.line, style = TileTypography.bodyMedium)
                Text("${dep.minutesAway} min", style = TileTypography.bodySmall)
            }
        }
    }
}
```

Click actions use `ActionBuilders` to launch activities or fire requests:

```kotlin
private fun launchDeparture(id: String): Action {
    return ActionBuilders.LaunchAction.Builder()
        .setLaunchTarget(
            ActionBuilders.AndroidActivity.Builder()
                .setClassName(DepartureDetailActivity::class.java.name)
                .setPackageName(context.packageName)
                .build()
        )
        .build()
}
```

## Data freshness

Tiles should render from cache synchronously in `onTileRequest` — no network calls on the binder thread:

```kotlin
override fun onTileRequest(requestParams: RequestParams): ListenableFuture<Tile> {
    val data = cache.getDepartures() // in-memory or DataStore snapshot
    if (data.isStale()) {
        scope.launch { repository.refreshDepartures() }
    }
    return Futures.immediateFuture(tile { TransitTileContent(data.items) })
}
```

Trigger refresh after background sync:

```kotlin
TileService.getUpdater(context, TransitTileService::class.java)
    .requestUpdate(TransitTileService::class.java)
```

## Tile vs full app UI

| Concern | Full app (Compose) | Tile |
|---------|-------------------|------|
| Layout depth | Unlimited | Keep flat, 2-3 levels |
| Interactions | Full gesture set | Clicks only |
| Refresh | User-driven | System-scheduled |
| Text length | Flexible | Truncate aggressively |

Design tiles as summaries with a tap-through to detail screens. My rule: if it needs scrolling, it belongs in the app, not a tile.

## Testing

Use the Wear OS Tile preview tool in Android Studio (Wear > Tile Preview). Unit test data mapping separately — tile rendering requires the Wear library runtime. Snapshot the proto output if you need regression coverage.

Pair tiles with [complications](https://blog.michaelsam94.com/android-wearos-complications/) for always-visible single metrics and tiles for richer multi-row summaries.

## Tile lifecycle and system constraints

Wear OS manages tile lifecycle aggressively for battery:

- **Active tile** — user is viewing it; refresh allowed
- **Visible carousel** — tile is in the swipe carousel but not focused; limited refresh
- **Inactive** — app should not request updates; system may kill tile process

Request updates sparingly:

```kotlin
// Good: after meaningful data change
fun onSyncComplete() {
    TileService.getUpdater(context, TransitTileService::class.java)
        .requestUpdate(TransitTileService::class.java)
}

// Bad: every minute via AlarmManager
// System will throttle; wastes battery; may get update requests ignored
```

Rule of thumb: request tile update when data meaningfully changes (new departure, workout completed), not on a fixed timer.

## Multiple tiles per app

Apps can provide multiple tile services — one per logical summary:

```xml
<service android:name=".TransitTileService" ... />
<service android:name=".FitnessTileService" ... />
```

Each needs its own preview drawable and label. Users pick which tiles to add from the tile picker. Don't cram unrelated data into one tile — split by user mental model.

## Handling empty and error states

Tiles must render something useful even without data:

```kotlin
fun TransitTileContent(departures: List<Departure>, state: TileDataState) {
    when (state) {
        TileDataState.Loading -> Text("Updating...")
        TileDataState.Empty -> Text("No upcoming departures")
        TileDataState.Error -> Text("Tap to refresh")
        TileDataState.Ready -> DepartureList(departures.take(3))
    }
}
```

Empty state with a tap action to launch the app is better than a blank tile. Error state should trigger refresh on tap, not just show static text.

## Performance on watch hardware

Wear devices have limited CPU and memory:

- **No network in onTileRequest** — always render from cache; refresh async
- **Flat layout hierarchy** — max 2–3 levels deep; deep nesting slows tile rendering
- **Limit text length** — truncate with ellipsis; watch screens are 200–450px
- **Reuse resources** — load icons in `onResourcesRequest`, not per tile request
- **Avoid bitmap scaling** — provide correctly sized drawables

Profile tile rendering with Android Studio's Wear Tile Preview — check layout timing on representative device configurations (round vs square, small vs large).

## Failure modes

- **Network call in onTileRequest** — ANR on binder thread; tile fails to render
- **Excessive refresh requests** — system throttles; tile shows stale data permanently
- **No preview drawable** — tile doesn't appear in picker
- **Missing BIND_TILE_PROVIDER permission** — service not discovered by system
- **Scrolling content in tile** — not supported; content clips silently

## Production checklist

- onTileRequest reads from cache only; async refresh triggered separately
- Preview drawable provided for tile picker
- Empty, loading, and error states designed
- Update requests fired on meaningful data change, not timer
- Layout flat (≤3 levels), text truncated
- Click actions launch appropriate detail screen
- Tested on round and square watch form factors

Wear OS 5+ adds Material 3 styling for tiles — align typography and color with your app's Material theme for visual consistency across phone and watch surfaces.

## Resources

- [Wear OS Tiles guide](https://developer.android.com/training/wearables/tiles)
- [Compose for Tiles documentation](https://developer.android.com/training/wearables/tiles/compose)
- [TileService API reference](https://developer.android.com/reference/androidx/wear/tiles/TileService)
- [Tile layout limits and best practices](https://developer.android.com/training/wearables/tiles/best-practices)
- [Adding tiles to your app (codelab)](https://developer.android.com/codelabs/wear-tiles)
