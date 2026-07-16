---
title: "Android TV UIs with Compose for TV"
slug: "android-tv-leanback-compose"
description: "Compose for TV replaces Leanback fragments with declarative Kotlin UI. Build focus-aware rows, details screens, and navigation with TvMaterial3, D-Pad support, and proper back-stack handling."
datePublished: "2024-08-31"
dateModified: "2024-08-31"
tags: ["Android", "Compose", "Android TV", "Leanback"]
keywords: "Compose for TV, Android TV UI, TvMaterial3, Leanback migration, D-Pad focus, TV navigation Compose"
faq:
  - q: "Should I start a new Android TV app with Leanback or Compose for TV?"
    a: "Start new projects with Compose for TV (androidx.tv:tv-material). Leanback is in maintenance mode — Google recommends Compose for TV for new development. Existing Leanback apps can migrate screen-by-screen since both can coexist in the same Activity during transition."
  - q: "How does focus work differently on TV?"
    a: "TV apps have no touch input — every interactive element must be focusable and show a visible focus indicator. Compose for TV provides TvLazyRow, TvLazyColumn, and focusRestorer modifiers that handle D-Pad traversal. Missing focus order is the number-one TV UX bug."
  - q: "Can Compose for TV apps run on Google TV and Fire TV?"
    a: "Yes, on devices with Android TV OS or Fire OS that support the required API level (typically API 21+). Test on physical remotes — emulator D-Pad behavior misses edge cases with focus trapping and long-press. Declare android.software.leanback in the manifest and provide a banner icon."
---

Ten-foot UI is a different design problem. Users navigate with a D-Pad, focus rings must be obvious from across the room, and scrolling lists need momentum that feels natural without touch. For years, Android TV meant Leanback fragments — `BrowseSupportFragment`, `DetailsSupportFragment`, `VerticalGridView` — with XML themes and adapter boilerplate. Compose for TV brings the same declarative model as mobile Compose, with TV-specific components that handle focus traversal out of the box.

## Dependencies

```kotlin
dependencies {
    implementation("androidx.tv:tv-material:1.0.0")
    implementation("androidx.tv:tv-foundation:1.0.0")
    implementation("androidx.navigation:navigation-compose:2.7.*")
}
```

Use `TvMaterial3` theme, not standard Material3 — TV typography and spacing scales differ.

## Browse screen pattern

The classic TV home screen: hero row, category rows, horizontal scrolling cards.

```kotlin
@Composable
fun BrowseScreen(
    rows: List<ContentRow>,
    onItemClick: (ContentItem) -> Unit
) {
    TvLazyColumn(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(20.dp)
    ) {
        item {
            HeroBanner(item = rows.first().items.first())
        }
        items(rows) { row ->
            ContentRowSection(
                title = row.title,
                items = row.items,
                onItemClick = onItemClick
            )
        }
    }
}

@Composable
fun ContentRowSection(
    title: String,
    items: List<ContentItem>,
    onItemClick: (ContentItem) -> Unit
) {
    Column {
        Text(text = title, style = MaterialTheme.typography.headlineSmall)
        TvLazyRow(
            horizontalArrangement = Arrangement.spacedBy(16.dp),
            contentPadding = PaddingValues(horizontal = 48.dp)
        ) {
            items(items, key = { it.id }) { item ->
                ContentCard(
                    item = item,
                    onClick = { onItemClick(item) },
                    modifier = Modifier
                        .width(180.dp)
                        .height(270.dp)
                )
            }
        }
    }
}
```

`TvLazyRow` and `TvLazyColumn` manage focus restoration when rows scroll off-screen and back — standard `LazyRow` does not.

## Focus and selection

```kotlin
@Composable
fun ContentCard(
    item: ContentItem,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    var isFocused by remember { mutableStateOf(false) }

    Card(
        onClick = onClick,
        modifier = modifier
            .onFocusChanged { isFocused = it.isFocused }
            .border(
                width = if (isFocused) 3.dp else 0.dp,
                color = MaterialTheme.colorScheme.primary,
                shape = CardDefaults.shape
            )
            .scale(if (isFocused) 1.08f else 1f)
    ) {
        AsyncImage(
            model = item.posterUrl,
            contentDescription = item.title,
            modifier = Modifier.fillMaxSize()
        )
    }
}
```

Scale-on-focus is standard TV affordance. Keep animation duration under 150ms — sluggish focus feedback feels broken on a remote.

## Details screen

```kotlin
@Composable
fun DetailsScreen(item: ContentItem, onPlay: () -> Unit) {
    Row(modifier = Modifier.fillMaxSize().padding(48.dp)) {
        AsyncImage(
            model = item.posterUrl,
            contentDescription = null,
            modifier = Modifier.width(240.dp).aspectRatio(2f / 3f)
        )
        Spacer(Modifier.width(32.dp))
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(item.title, style = MaterialTheme.typography.displaySmall)
            Text(item.description, maxLines = 4)
            Button(onClick = onPlay) { Text("Play") }
        }
    }
}
```

Place the primary action (Play) first in focus order — TV users expect the top-left focusable element after entering a screen.

## Navigation

Use Navigation Compose with a single Activity:

```kotlin
@Composable
fun TvNavHost() {
    val navController = rememberNavController()
    NavHost(navController, startDestination = "browse") {
        composable("browse") {
            BrowseScreen(
                rows = viewModel.rows,
                onItemClick = { navController.navigate("details/${it.id}") }
            )
        }
        composable("details/{id}") { backStack ->
            DetailsScreen(
                item = viewModel.item(backStack.arguments?.getString("id")!!),
                onPlay = { navController.navigate("player/${backStack.arguments?.getString("id")}") }
            )
        }
    }
}
```

Handle back button with `BackHandler` or Navigation's built-in pop — TV users expect Back to return to the browse grid, not exit the app.

## Manifest requirements

```xml
<uses-feature android:name="android.software.leanback" android:required="true" />
<uses-feature android:name="android.hardware.touchscreen" android:required="false" />

<application android:banner="@drawable/tv_banner">
    <activity android:name=".MainActivity" android:exported="true">
        <intent-filter>
            <action android:name="android.intent.action.MAIN" />
            <category android:name="android.intent.category.LEANBACK_LAUNCHER" />
        </intent-filter>
    </activity>
</application>
```

## Migrating from Leanback

Migrate one fragment at a time. Keep `BrowseSupportFragment` while replacing the details screen with Compose inside a `ComposeView`. Match existing row card dimensions so QA can compare side-by-side. The [Material3 adaptive navigation](https://blog.michaelsam94.com/android-material3-adaptive-navigation/) patterns for large screens share DNA with TV layout — some components reuse across form factors.

## Performance on low-end TV hardware

Android TV sticks and built-in TV SoCs have limited GPU and RAM:

- **Limit recompositions** — stable keys on lazy rows, avoid animating entire grid
- **Image sizing** — request poster art at display resolution, not 4K source
- **Lazy lists** — `TvLazyRow` / `LazyVerticalGrid` with prefetch distance 2–3
- **Avoid heavy blur** — `RenderEffect` blur is expensive on Mali GPUs common in TVs

Profile with Android Studio Profiler on actual hardware — emulator GPU doesn't match TV.

## Content recommendations and rows

TV apps are row-based. Structure ViewModel state for Leanback parity:

```kotlin
data class BrowseUiState(
    val rows: List<ContentRow>,  // "Continue Watching", "Trending", etc.
    val focusedRowIndex: Int = 0,
    val focusedItemIndex: Int = 0,
)

data class ContentRow(
    val id: String,
    val title: String,
    val items: List<MediaItem>,
)
```

Prefetch next row's images when focus enters a row. Cancel in-flight Coil requests when user scrolls quickly — TV remotes generate rapid focus events.

## Google TV and Play Store requirements

Pass [Android TV app quality](https://developer.android.com/docs/quality-guidelines/tv-app-quality) before launch:

- D-pad navigable without touch
- Banner and launcher icon per spec
- Playback uses Media3/ExoPlayer with proper audio focus
- No phone layouts leaked on TV (test with `UI_MODE_TYPE_TELEVISION`)

Rejection for focus traps is common — every interactive element needs visible focus state and logical traversal order.

Pair with [Compose focus management for TV](https://blog.michaelsam94.com/compose-focus-management-tv/) for D-pad navigation patterns.

## Production checklist

- [ ] Tested on rotary and touch input modes via DHU
- [ ] `LEANBACK_LAUNCHER` intent filter and TV banner present
- [ ] Poster images loaded at display resolution, not 4K
- [ ] Back navigation returns to browse grid, not exits app
- [ ] Play Store Auto quality checklist passed before submit

TV form factor testing on a phone emulator misses focus traversal bugs — budget for at least one physical Android TV device or Google TV streamer in your QA lab.

## Resources

- [Compose for TV documentation](https://developer.android.com/training/tv/playback/compose)
- [TvMaterial3 components reference](https://developer.android.com/reference/kotlin/androidx/tv/material3/package-summary)
- [Android TV app quality guidelines](https://developer.android.com/docs/quality-guidelines/tv-app-quality)
- [TV focus system overview](https://developer.android.com/training/tv/get-started/navigation)
- [Leanback to Compose migration guide](https://developer.android.com/training/tv/playback/compose#migrate-from-leanback)
