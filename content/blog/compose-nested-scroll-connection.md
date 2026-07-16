---
title: "Coordinated Scrolling with NestedScroll"
slug: "compose-nested-scroll-connection"
description: "Connect collapsing toolbars, pull-to-refresh, and nested LazyColumns using NestedScrollConnection and Modifier.nestedScroll in Jetpack Compose."
datePublished: "2025-04-06"
dateModified: "2025-04-06"
tags: ["Android", "Compose"]
keywords: "Compose nested scroll, NestedScrollConnection, collapsing toolbar, coordinated scrolling, nested LazyColumn"
faq:
  - q: "What problem does NestedScrollConnection solve?"
    a: "When scrollable composables nest—a LazyColumn inside another LazyColumn, or a list under a collapsing header—child scrolls consume all delta first and the parent never moves. NestedScrollConnection lets children dispatch unconsumed scroll to parents and parents pre-consume before children, enabling coordinated motion like toolbar collapse and overscroll effects."
  - q: "What is the difference between onPreScroll and onPostScroll?"
    a: "onPreScroll runs before the child scrolls—parents steal delta first, useful for collapsing headers that should shrink before list content scrolls. onPostScroll runs after the child scrolls with remaining delta—useful for stretch overscroll or moving a parent when the child hits its edge."
  - q: "Does Material3 Scaffold handle nested scroll automatically?"
    a: "TopAppBar with scrollBehavior using enterAlways or exitUntilCollapsed modes wires NestedScrollConnection internally via Modifier.nestedScroll. Custom layouts outside Material must implement their own connection or reuse Material's TopAppBarScrollBehavior connection object."
---

The collapsing toolbar that sticks halfway, the outer scroll that never gives way to the inner list, the pull-to-refresh that fights the LazyColumn—these are nested scroll bugs. Compose does not bubble scroll events like Android View's nested scrolling parent/child negotiation by default. You opt in with `Modifier.nestedScroll` and a `NestedScrollConnection` that defines who consumes how much of each drag delta.

## Nested scroll dispatch order

For each scroll event:

1. Parent `onPreScroll` — parent may consume delta before child sees it
2. Child scrolls with remaining delta
3. Parent `onPostScroll` — parent consumes what child left over

```kotlin
interface NestedScrollConnection {
    fun onPreScroll(available: Offset, source: NestedScrollSource): Offset = Offset.Zero
    fun onPostScroll(consumed: Offset, available: Offset, source: NestedScrollSource): Offset = Offset.Zero
    suspend fun onPreFling(available: Velocity): Velocity = Velocity.Zero
    suspend fun onPostFling(consumed: Velocity, available: Velocity): Velocity = Velocity.Zero
}
```

Return the amount you consumed from `available`—Compose subtracts it before passing downstream.

## Collapsing header pattern

Track header height offset in state, consume vertical pre-scroll:

```kotlin
class CollapsingHeaderConnection(
    private val headerHeightPx: Float,
    private val offset: MutableFloatState,
) : NestedScrollConnection {

    override fun onPreScroll(available: Offset, source: NestedScrollSource): Offset {
        val delta = available.y
        val newOffset = (offset.floatValue + delta).coerceIn(-headerHeightPx, 0f)
        val consumed = newOffset - offset.floatValue
        offset.floatValue = newOffset
        return Offset(0f, consumed)
    }
}

@Composable
fun CollapsingScreen() {
    val headerHeight = 200.dp
    val headerHeightPx = with(LocalDensity.current) { headerHeight.toPx() }
    val headerOffset = remember { mutableFloatStateOf(0f) }
    val connection = remember {
        CollapsingHeaderConnection(headerHeightPx, headerOffset)
    }

    Box(Modifier.nestedScroll(connection)) {
        LazyColumn(Modifier.fillMaxSize()) {
            item { Spacer(Modifier.height(headerHeight)) }
            items(100) { Text("Item $it", Modifier.padding(16.dp)) }
        }
        Header(
            modifier = Modifier
                .height(headerHeight)
                .offset { IntOffset(0, headerOffset.floatValue.roundToInt()) },
        )
    }
}
```

Header collapses on pre-scroll before list items move—Material's `TopAppBarScrollBehavior` implements the same contract.

## Material3 TopAppBar integration

```kotlin
val scrollBehavior = TopAppBarDefaults.exitUntilCollapsedScrollBehavior()

Scaffold(
    modifier = Modifier.nestedScroll(scrollBehavior.nestedScrollConnection),
    topBar = {
        LargeTopAppBar(
            title = { Text("Title") },
            scrollBehavior = scrollBehavior,
        )
    },
) { padding ->
    LazyColumn(contentPadding = padding) {
        items(items) { /* ... */ }
    }
}
```

`exitUntilCollapsedScrollBehavior` keeps the small title visible; `enterAlwaysScrollBehavior` hides the entire bar on scroll down.

## Nested LazyColumns (anti-pattern fix)

Two vertical LazyColumns nested without nested scroll means the inner list captures all gestures. Fixes:

1. **Single LazyColumn** with multiple item types (header sections + inner content as items—not nested lazy lists)
2. **Height-constrained inner list** with `Modifier.height(fixedHeight)` so inner list scrolls independently
3. **Custom NestedScrollConnection** passing overscroll at edges to parent

Preferred: flatten to one LazyColumn. Nested lazy lists break item recycling assumptions and complicate scroll-to-index.

## Pull-to-refresh coordination

Material3 `PullToRefreshBox` wraps content and uses nested scroll for overscroll detection:

```kotlin
PullToRefreshBox(
    isRefreshing = isRefreshing,
    onRefresh = { viewModel.refresh() },
) {
    LazyColumn { /* items */ }
}
```

Custom refresh indicators implement `NestedScrollConnection.onPostScroll` to track pull distance when not using Material wrapper.

## Horizontal nested scroll

Same API applies for horizontal pager + vertical list—return `Offset(consumedX, consumedY)` appropriately. `HorizontalPager` with vertical LazyColumn inside each page typically needs the list to handle vertical delta and pager horizontal only when list is at edge (custom connection or `PagerDefaults` experimental APIs).

## Debugging scroll fights

Log consumed vs available in connection methods during development. Common bug: consuming horizontal delta in a vertical-only handler, blocking pager swipes.

Another bug: multiple `nestedScroll` modifiers on the same chain—order matters; outermost parent connection runs first in pre-scroll.

## Collapsing toolbar implementation

Standard pattern for toolbar that hides on scroll down:

```kotlin
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CollapsingScreen() {
    val scrollBehavior = TopAppBarDefaults.enterAlwaysScrollBehavior()

    Scaffold(
        modifier = Modifier.nestedScroll(scrollBehavior.nestedScrollConnection),
        topBar = {
            LargeTopAppBar(
                title = { Text("Feed") },
                scrollBehavior = scrollBehavior,
            )
        }
    ) { padding ->
        LazyColumn(contentPadding = padding) {
            items(feedItems) { item -> FeedItem(item) }
        }
    }
}
```

`nestedScroll` on Scaffold passes scroll delta to `scrollBehavior.nestedScrollConnection`. Toolbar collapses on scroll down, expands on scroll up.

Scroll behaviors:
- `enterAlwaysScrollBehavior` — toolbar reappears on any upward scroll
- `exitUntilCollapsedScrollBehavior` — toolbar stays collapsed until scroll to top
- `pinnedScrollBehavior` — toolbar never collapses

## Custom NestedScrollConnection

Implement custom scroll coordination:

```kotlin
val connection = remember {
    object : NestedScrollConnection {
        override fun onPreScroll(available: Offset, source: NestedScrollSource): Offset {
            // Parent consumes scroll before child (e.g., collapsing header)
            val consumed = if (available.y < 0 && headerHeight > 0) {
                Offset(0f, available.y.coerceAtLeast(-headerHeight))
            } else Offset.Zero
            headerHeight += consumed.y
            return consumed
        }

        override fun onPostScroll(consumed: Offset, available: Offset, source: NestedScrollSource): Offset {
            // Child didn't consume all scroll — parent takes remainder
            return Offset.Zero
        }
    }
}
```

`onPreScroll`: parent consumes first (toolbar collapse). `onPostScroll`: parent takes overflow (pull-to-refresh overscroll).

## LazyColumn inside LazyColumn anti-pattern

Nested lazy lists break recycling and cause scroll conflicts:

```kotlin
// ❌ Anti-pattern: LazyColumn inside LazyColumn item
LazyColumn {
    item { Header() }
    item {
        LazyColumn {  // inner list — breaks recycling
            items(nestedItems) { NestedItem(it) }
        }
    }
}

// ✅ Preferred: flatten to single LazyColumn
LazyColumn {
    item { Header() }
    items(nestedItems) { NestedItem(it) }
}
```

If nested scrolling is unavoidable, give inner list fixed height: `Modifier.height(400.dp)`.

## Failure modes

- **Nested LazyColumns** — broken recycling; flatten to single list
- **Wrong scroll behavior for UX** — enterAlways vs exitUntilCollapsed confusion
- **nestedScroll on wrong composable** — must be on parent of scrolling content
- **Consuming wrong axis** — vertical handler consuming horizontal delta blocks pager
- **Multiple nestedScroll modifiers** — order matters; outermost runs first

## Production checklist

- Single LazyColumn preferred over nested lazy lists
- nestedScroll modifier on Scaffold/root of scrolling hierarchy
- Scroll behavior chosen to match UX (enterAlways for feeds, exitUntilCollapsed for detail)
- Custom NestedScrollConnection for non-standard coordination
- Pull-to-refresh uses Material3 PullToRefreshBox (handles nested scroll internally)
- Debug: log consumed vs available delta during development

Test nested scroll with TalkBack enabled — custom nested scroll connections often break accessibility scroll actions silently.

## Resources

- [Nested scroll in Compose](https://developer.android.com/jetpack/compose/gestures#nested-scroll)
- [NestedScrollConnection reference](https://developer.android.com/reference/kotlin/androidx/compose/ui/input/nestedscroll/NestedScrollConnection)
- [Material3 TopAppBar scroll behavior](https://developer.android.com/reference/kotlin/androidx/compose/material3/TopAppBarDefaults)
- [Pull to refresh Material3](https://developer.android.com/reference/kotlin/androidx/compose/material3/pulltorefresh/package-summary)
