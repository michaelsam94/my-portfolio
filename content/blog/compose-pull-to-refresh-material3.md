---
title: "Pull-to-Refresh with Material 3 in Jetpack Compose"
slug: "compose-pull-to-refresh-material3"
description: "Implement pull-to-refresh in Jetpack Compose with the Material 3 PullToRefreshBox: wiring state, custom indicators, and avoiding the double-spinner bug."
datePublished: "2024-09-02"
dateModified: "2024-09-02"
tags: ["Android", "Jetpack Compose", "Material 3", "UI"]
keywords: "Compose pull to refresh, PullToRefreshBox, Material 3 pull to refresh, pullToRefresh modifier, Compose swipe refresh"
faq:
  - q: "How do you add pull-to-refresh in Jetpack Compose?"
    a: "Wrap your scrollable content in a PullToRefreshBox from androidx.compose.material3, passing an isRefreshing boolean and an onRefresh lambda. The box owns the gesture and indicator, so you only manage the refreshing flag in your ViewModel and reset it to false when the network call finishes."
  - q: "Why does my Compose pull-to-refresh show two spinners?"
    a: "You almost always have both a swipe indicator and a separate loading UI reacting to the same state. Drive the pull indicator from a dedicated isRefreshing flag that is only true during a user-initiated refresh, and use a different flag for the initial load, so the two never render at once."
  - q: "Do I still need the Accompanist swipe refresh library?"
    a: "No. Accompanist SwipeRefresh is deprecated. Material 3 ships PullToRefreshBox and a pullToRefresh modifier natively, so remove the Accompanist dependency and migrate to the first-party API, which handles nested scrolling and the Material motion for you."
---

Pull-to-refresh in Jetpack Compose is now a first-party Material 3 component: wrap your list in `PullToRefreshBox`, hand it an `isRefreshing` boolean plus an `onRefresh` callback, and you're done. The days of pulling in Accompanist's `SwipeRefresh` are over — that library is deprecated, and the native `androidx.compose.material3` API handles the gesture, the nested scroll plumbing, and the Material motion out of the box. What's left for you is state management, and that's where most of the bugs actually live.

I've shipped this pattern in three production apps, and the component itself is the easy part. The hard part is the same trap that has plagued swipe-to-refresh since the View days: reconciling the refresh spinner with your other loading states so users don't stare at two spinners at once.

## The minimal wiring

At its core the API is a container that owns the indicator and the gesture. You keep the refreshing flag in your state holder and flip it.

```kotlin
@Composable
fun FeedScreen(viewModel: FeedViewModel = hiltViewModel()) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    PullToRefreshBox(
        isRefreshing = state.isRefreshing,
        onRefresh = viewModel::refresh,
    ) {
        LazyColumn(Modifier.fillMaxSize()) {
            items(state.items, key = { it.id }) { PostRow(it) }
        }
    }
}
```

The `onRefresh` lambda fires when the user completes the pull. Your ViewModel sets `isRefreshing = true`, does the work, and sets it back to `false`. `PullToRefreshBox` watches that boolean and animates the indicator in and out accordingly. Note the scrollable child is required — the box relies on a nested-scroll connection, so putting a non-scrolling `Column` inside it means the gesture never triggers.

## Keep the two loading states separate

Here's the mistake I see in nearly every code review: one `isLoading` flag drives both the full-screen initial spinner *and* the pull indicator. On first load the screen shows a centered progress bar; then when the user pulls to refresh, the same flag flips and you get the pull spinner layered on top of — or fighting with — a re-rendered empty state. It looks broken.

Model them as distinct concepts:

```kotlin
data class FeedUiState(
    val items: List<Post> = emptyList(),
    val isLoading: Boolean = false,     // initial / full-screen
    val isRefreshing: Boolean = false,  // user-initiated pull only
    val error: String? = null,
)
```

In the ViewModel, `refresh()` only ever touches `isRefreshing`:

```kotlin
fun refresh() {
    viewModelScope.launch {
        _uiState.update { it.copy(isRefreshing = true) }
        val result = repository.fetchFeed()
        _uiState.update {
            it.copy(
                items = result.getOrDefault(it.items),
                isRefreshing = false,
                error = result.exceptionOrNull()?.message,
            )
        }
    }
}
```

Because `isRefreshing` is the *only* thing wired to `PullToRefreshBox`, and `isLoading` drives a separate branch of your composable tree, the two can never collide. The initial load shows a skeleton; the pull shows the Material indicator. This separation is the single change that fixes 90% of "double spinner" reports.

## Always reset the flag — even on failure

The classic support ticket is "the spinner never goes away." It happens when the network call throws and your `finally` block is missing. The indicator is a pure function of `isRefreshing`, so if you leave it stuck at `true`, it spins forever. Use structured error handling so the flag *always* resets:

```kotlin
fun refresh() {
    viewModelScope.launch {
        _uiState.update { it.copy(isRefreshing = true) }
        try {
            val posts = repository.fetchFeed().getOrThrow()
            _uiState.update { it.copy(items = posts) }
        } catch (e: Exception) {
            _uiState.update { it.copy(error = e.toUserMessage()) }
        } finally {
            _uiState.update { it.copy(isRefreshing = false) }
        }
    }
}
```

Pair this with a minimum-duration trick if your API is fast: a refresh that completes in 80ms makes the indicator flash and feels glitchy. I add a `delay` to floor the perceived duration around 400–500ms so the animation reads as intentional. Users trust a refresh they can see.

## Customizing the indicator

The default indicator is fine, but branded apps usually want their own. `PullToRefreshBox` takes an `indicator` slot, and you have `rememberPullToRefreshState()` to read the pull progress for a fully custom drawing:

```kotlin
val pullState = rememberPullToRefreshState()

PullToRefreshBox(
    isRefreshing = state.isRefreshing,
    onRefresh = viewModel::refresh,
    state = pullState,
    indicator = {
        PullToRefreshDefaults.Indicator(
            state = pullState,
            isRefreshing = state.isRefreshing,
            modifier = Modifier.align(Alignment.TopCenter),
            containerColor = MaterialTheme.colorScheme.primaryContainer,
            color = MaterialTheme.colorScheme.primary,
        )
    },
) { /* content */ }
```

For anything more elaborate than color, read `pullState.distanceFraction` — it goes from 0 to 1 as the user drags past the threshold — and drive your own animation from it. I've used it to scale a logo and cross-fade a tagline, all as a function of that single float. Keep it cheap; this runs on every drag frame.

If you're building custom indicators, the same discipline around cheap recomposition applies as everywhere else in Compose — see [ten years of Compose lessons](https://blog.michaelsam94.com/jetpack-compose-lessons-10-years-android/) for why keeping per-frame work minimal matters.

## The lower-level modifier

`PullToRefreshBox` is a convenience wrapper. When you need the gesture attached to something that isn't a simple box — say a custom scaffold or a screen with a collapsing toolbar — reach for the `Modifier.pullToRefresh` directly:

```kotlin
Box(
    Modifier.pullToRefresh(
        isRefreshing = state.isRefreshing,
        state = pullState,
        onRefresh = viewModel::refresh,
    )
) {
    CollapsingHeaderList(/* ... */)
    PullToRefreshDefaults.Indicator(
        state = pullState,
        isRefreshing = state.isRefreshing,
        modifier = Modifier.align(Alignment.TopCenter),
    )
}
```

This gives you control over indicator placement and lets the gesture coexist with other nested-scroll consumers. The tradeoff is you're now responsible for drawing and positioning the indicator yourself, which is exactly why the box wrapper exists for the common case.

## A quick comparison of the three approaches

| Approach | When to use | You manage |
| --- | --- | --- |
| `PullToRefreshBox` | Standard list/grid screen | `isRefreshing` + `onRefresh` |
| `Modifier.pullToRefresh` | Custom scaffold, collapsing header | Indicator placement + state |
| Accompanist `SwipeRefresh` | Never (deprecated) | Migrate off it |

## What I'd take away

The Material 3 API removed almost all of the ceremony pull-to-refresh used to require. Wrap your scrollable content in `PullToRefreshBox`, drive it from a *dedicated* `isRefreshing` flag that is distinct from your initial-load state, and always reset that flag in a `finally` block so the indicator can't hang. Add a small minimum duration so fast refreshes still feel deliberate, and only drop to `Modifier.pullToRefresh` when your layout is too custom for the box. Get those four things right and pull-to-refresh becomes a non-event — which is exactly what a good refresh gesture should be.

## Resources

- [Material 3 pull-to-refresh (Android developers)](https://developer.android.com/develop/ui/compose/components/pull-to-refresh)
- [PullToRefreshBox API reference](https://developer.android.com/reference/kotlin/androidx/compose/material3/pulltorefresh/package-summary)
- [Material 3 for Compose](https://developer.android.com/develop/ui/compose/designsystems/material3)
- [collectAsStateWithLifecycle](https://developer.android.com/topic/libraries/architecture/compose)
