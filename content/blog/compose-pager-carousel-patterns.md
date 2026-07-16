---
title: "Building Pagers and Carousels in Compose"
slug: "compose-pager-carousel-patterns"
description: "Implement pagers, image carousels, and onboarding flows with HorizontalPager, page indicators, auto-scroll, and nested scrolling patterns."
datePublished: "2025-04-09"
dateModified: "2025-04-09"
tags: ["Android", "Compose"]
keywords: "Compose HorizontalPager, carousel, page indicator, PagerState, onboarding pager, infinite scroll pager"
faq:
  - q: "What is the difference between HorizontalPager and LazyRow for carousels?"
    a: "HorizontalPager snaps one page to fill the viewport—ideal for onboarding, image galleries, and tab-like full-screen pages. LazyRow scrolls continuously with variable item widths—better for peek-a-boo card strips. Pager provides page count semantics, programmatic animateScrollToPage, and off-screen page limit control."
  - q: "How do I add page dots to a pager?"
    a: "Read pagerState.currentPage and pageOffsetFraction to animate indicator selection. Use Accompanist PagerIndicator or a Row of animated dots scaled by proximity to current page. Sync indicator clicks with coroutineScope.launch { pagerState.animateScrollToPage(index) }."
  - q: "How do I implement infinite looping carousels?"
    a: "Use a large virtual page count (e.g., Int.MAX_VALUE / 2) with page % realItemCount for content mapping, starting at a middle index. On scroll settle, silently jump without animation if near boundaries. Alternatively, duplicate first/last items and jump on edge—simpler but less smooth."
---

Product marketing loves carousels; engineers love to hate them. In Compose, the right primitive for full-page snapping carousels is `HorizontalPager` from Foundation— not a horizontally scrolled LazyRow with snap fling hacked on afterward. Pager state drives indicators, auto-advance, and coordinated parallax. Get the state model right and the rest is polish.

## Basic HorizontalPager

```kotlin
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun ImageCarousel(
    images: List<ImageUrl>,
    modifier: Modifier = Modifier,
) {
    val pagerState = rememberPagerState(pageCount = { images.size })

    Column(modifier) {
        HorizontalPager(
            state = pagerState,
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(16f / 9f),
        ) { page ->
            AsyncImage(
                model = images[page],
                contentDescription = null,
                modifier = Modifier.fillMaxSize(),
                contentScale = ContentScale.Crop,
            )
        }

        PageIndicator(
            pageCount = images.size,
            currentPage = pagerState.currentPage,
            currentPageOffsetFraction = pagerState.currentPageOffsetFraction,
            onPageClick = { index ->
                // launch from remembered coroutineScope
            },
        )
    }
}
```

`pageCount` as lambda supports dynamic list sizes without recreating state incorrectly.

## Animated page indicator

```kotlin
@Composable
fun PageIndicator(
    pageCount: Int,
    currentPage: Int,
    currentPageOffsetFraction: Float,
    onPageClick: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    val position = currentPage + currentPageOffsetFraction
    Row(
        modifier = modifier.padding(8.dp),
        horizontalArrangement = Arrangement.Center,
    ) {
        repeat(pageCount) { index ->
            val distance = abs(position - index).coerceAtMost(1f)
            val size = 8.dp + (1f - distance) * 4.dp
            Box(
                modifier = Modifier
                    .padding(4.dp)
                    .size(size)
                    .clip(CircleShape)
                    .background(
                        if (distance < 0.5f) Color.White
                        else Color.White.copy(alpha = 0.4f),
                    )
                    .clickable { onPageClick(index) },
            )
        }
    }
}
```

## Auto-advancing carousel

```kotlin
LaunchedEffect(pagerState) {
    while (true) {
        delay(4000)
        val next = (pagerState.currentPage + 1) % pagerState.pageCount
        pagerState.animateScrollToPage(next)
    }
}
```

Pause auto-scroll when user interacts:

```kotlin
var userInteracting by remember { mutableStateOf(false) }

HorizontalPager(
    state = pagerState,
    modifier = Modifier.pointerInput(Unit) {
        detectDragGestures(
            onDragStart = { userInteracting = true },
            onDragEnd = { userInteracting = false },
            onDragCancel = { userInteracting = false },
            onDrag = { _, _ -> },
        )
    },
) { /* pages */ }

LaunchedEffect(pagerState, userInteracting) {
    if (userInteracting) return@LaunchedEffect
    // auto advance loop
}
```

## Peek carousel with page spacing

Show adjacent page edges:

```kotlin
HorizontalPager(
    state = pagerState,
    contentPadding = PaddingValues(horizontal = 32.dp),
    pageSpacing = 16.dp,
    pageSize = PageSize.Fixed(280.dp),
) { page -> Card { /* content */ } }
```

`PageSize.Fixed` or `PageSize.Fill` controls viewport fill behavior.

## Nested vertical scroll in pages

Each page may contain a LazyColumn—use nested scroll or disable parent pager swipe when child scrolls:

```kotlin
HorizontalPager(
    state = pagerState,
    userScrollEnabled = !innerListScrolling,
) { /* page with LazyColumn reporting scroll state */ }
```

Alternatively, use vertical pager for onboarding (full-screen steps) with only horizontal swipes between chapters.

## Infinite loop implementation

```kotlin
val pageCount = 100_000
val startPage = pageCount / 2
val pagerState = rememberPagerState(
    initialPage = startPage - (startPage % images.size),
    pageCount = { pageCount },
)

HorizontalPager(state = pagerState) { page ->
    val index = page % images.size
    AsyncImage(model = images[index], /* ... */)
}
```

Large virtual count avoids boundary jumps during normal swiping.

## Accessibility

Announce page changes:

```kotlin
LaunchedEffect(pagerState.currentPage) {
    // TalkBack: "Page 2 of 5"
}
```

Ensure swipe alternatives exist—buttons for next/previous for users who cannot swipe.

## Performance

Set `beyondViewportPageCount = 1` to keep one off-screen page composed—balances memory vs swipe smoothness. Heavy pages should lazy-load content in `LaunchedEffect(page)` when page becomes current.

## Pager with TabRow integration

Common pattern: tabs synced with pager:

```kotlin
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun TabbedPager(tabs: List<String>, content: List<@Composable () -> Unit>) {
    val pagerState = rememberPagerState(pageCount = { tabs.size })
    val scope = rememberCoroutineScope()

    Column {
        TabRow(selectedTabIndex = pagerState.currentPage) {
            tabs.forEachIndexed { index, title ->
                Tab(
                    selected = pagerState.currentPage == index,
                    onClick = { scope.launch { pagerState.animateScrollToPage(index) } },
                    text = { Text(title) },
                )
            }
        }
        HorizontalPager(state = pagerState) { page ->
            content[page]()
        }
    }
}
```

For scrollable tabs (many items), use `ScrollableTabRow` instead. Sync tab indicator position with `pagerState.currentPageOffsetFraction` for smooth animation during swipe.

## Onboarding pager pattern

Full-screen onboarding with skip and next buttons:

```kotlin
@Composable
fun OnboardingPager(pages: List<OnboardingPage>, onComplete: () -> Unit) {
    val pagerState = rememberPagerState(pageCount = { pages.size })
    val scope = rememberCoroutineScope()
    val isLastPage = pagerState.currentPage == pages.size - 1

    Box(Modifier.fillMaxSize()) {
        HorizontalPager(state = pagerState, modifier = Modifier.fillMaxSize()) { page ->
            OnboardingScreen(pages[page])
        }

        Row(
            Modifier.align(Alignment.BottomCenter).padding(32.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            TextButton(onClick = onComplete) { Text("Skip") }
            Button(onClick = {
                if (isLastPage) onComplete()
                else scope.launch { pagerState.animateScrollToPage(pagerState.currentPage + 1) }
            }) {
                Text(if (isLastPage) "Get Started" else "Next")
            }
        }
    }
}
```

Save onboarding completion in DataStore — don't show again on next launch.

## Performance tuning

| Parameter | Default | Recommendation |
|---|---|---|
| `beyondViewportPageCount` | 0 | 1 for smooth swipe; 0 for memory-heavy pages |
| `pageSpacing` | 0 | 8–16dp for peek carousels |
| `contentPadding` | 0 | Horizontal padding for peek effect |
| `key` | page index | Stable content key if pages reorder |

Heavy pages (maps, video) should use `beyondViewportPageCount = 0` and lazy-load in `LaunchedEffect(page)`.

## Failure modes

- **Pager state not reset on data change** — item count changes but pager stays on old page index; reset when list size changes
- **Auto-scroll during user interaction** — annoying; pause on drag detection
- **Nested scroll conflict** — vertical LazyColumn inside pager captures vertical scroll; disable pager swipe or use nested scroll connection
- **Infinite loop boundary jump** — visible flicker at virtual page edges; use large virtual count to minimize
- **Missing accessibility alternatives** — swipe-only navigation excludes motor-impaired users; add next/previous buttons

## Production checklist

- Stable keys on pager content for dynamic lists
- Page indicator synced with pagerState
- Auto-scroll paused during user interaction
- Accessibility: page announcements and button alternatives
- beyondViewportPageCount tuned per page weight
- Onboarding completion persisted (don't re-show)
- Nested scroll conflicts tested and resolved

Material3 carousel component wraps HorizontalPager with spec-compliant indicators and motion — prefer it over custom implementations for design system consistency.

## Common production mistakes

Teams get pager carousel patterns wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Compose UI work on pager carousel patterns janks when recomposition scope is too wide, `remember` keys omit stable inputs, and semantics for TalkBack are added only after QA finds focus traps.

## Resources

- [HorizontalPager reference](https://developer.android.com/reference/kotlin/androidx/compose/foundation/pager/HorizontalPager)
- [PagerState documentation](https://developer.android.com/reference/kotlin/androidx/compose/foundation/pager/PagerState)
- [Compose Foundation pager guide](https://developer.android.com/jetpack/compose/layouts/pager)
- [Material3 carousel specs](https://m3.material.io/components/carousel/overview)
