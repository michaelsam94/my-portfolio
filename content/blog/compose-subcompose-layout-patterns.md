---
title: "SubcomposeLayout Patterns and Costs"
slug: "compose-subcompose-layout-patterns"
description: "Use SubcomposeLayout when child composition depends on parent size—and understand the performance trade-offs vs standard Layout."
datePublished: "2025-04-12"
dateModified: "2025-04-12"
tags: ["Android", "Compose"]
keywords: "SubcomposeLayout, Compose layout performance, measure before compose, custom layout, recomposition cost"
faq:
  - q: "When do I need SubcomposeLayout instead of Layout?"
    a: "Use SubcomposeLayout when you must compose different child content based on measured sizes or constraints—text that switches layout at width breakpoints, measuring text before placing icons, or slots whose composables depend on available space. Standard Layout receives already-composed measurables; SubcomposeLayout composes children during the measure pass."
  - q: "Why is SubcomposeLayout slower than Layout?"
    a: "SubcomposeLayout can trigger composition inside measure, which may cause extra subcomposition passes and skip layout caching optimizations. Misuse causes measure-compose-measure loops. Use it only when child set truly depends on parent dimensions; otherwise prefer Layout with pre-composed children."
  - q: "What is a common SubcomposeLayout use case?"
    a: "BoxWithConstraints is built on SubcomposeLayout—it recomposes children when max width/height changes. Custom variants include responsive toolbars that show icons or overflow menu based on measured row width, and TextField decoration that adapts label placement after measuring input width."
---

`Layout` assumes children exist before measurement begins. Sometimes you need the opposite: decide *what* to compose based on *how much space* you have. That is `SubcomposeLayout`—composition inside the measure pass. It solves real problems and creates real performance traps. I reach for it when `BoxWithConstraints` is not flexible enough, then profile to confirm I am not composing on every scroll frame.

## Standard Layout vs SubcomposeLayout

```kotlin
// Layout: children composed before measure
Layout(content = { ChildA(); ChildB() }) { measurables, constraints ->
    // measurables already exist
}

// SubcomposeLayout: compose during measure
SubcomposeLayout { constraints ->
    val placeable = subcompose("slot") { ResponsiveChild(maxWidth = constraints.maxWidth) }
        .first()
        .measure(constraints)
    layout(placeable.width, placeable.height) {
        placeable.place(0, 0)
    }
}
```

`subcompose(slotId) { }` creates a composition scoped to a slot key. Reusing slot IDs stabilizes identity across passes.

## Responsive text truncation example

Show full title or truncated with ellipsis based on available width after measuring action buttons:

```kotlin
@Composable
fun AdaptiveTitleBar(
    title: String,
    actions: @Composable () -> Unit,
    modifier: Modifier = Modifier,
) {
    SubcomposeLayout(modifier = modifier) { constraints ->
        val actionPlaceables = subcompose("actions") { actions() }
            .map { it.measure(Constraints()) }
        val actionsWidth = actionPlaceables.sumOf { it.width }
        val titleMaxWidth = (constraints.maxWidth - actionsWidth).coerceAtLeast(0)

        val titlePlaceable = subcompose("title") {
            Text(
                text = title,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.widthIn(max = with(LocalDensity.current) { titleMaxWidth.toDp() }),
            )
        }.first().measure(Constraints(maxWidth = titleMaxWidth))

        val height = maxOf(titlePlaceable.height, actionPlaceables.maxOfOrNull { it.height } ?: 0)
        layout(constraints.maxWidth, height) {
            titlePlaceable.placeRelative(0, 0)
            var x = constraints.maxWidth - actionsWidth
            actionPlaceables.forEach { placeable ->
                placeable.placeRelative(x, 0)
                x += placeable.width
            }
        }
    }
}
```

Standard `Layout` cannot defer title composition until action widths are known without measuring actions as separate pre-composed children in two passes manually—SubcomposeLayout makes the two-pass pattern explicit.

## BoxWithConstraints under the hood

```kotlin
@Composable
fun BoxWithConstraints(
    modifier: Modifier = Modifier,
    content: @Composable BoxWithConstraintsScope.() -> Unit,
) {
    SubcomposeLayout(modifier) { constraints ->
        val scope = BoxWithConstraintsScopeImpl(/* min/max from constraints */)
        val measurable = subcompose("content") { scope.content() }.first()
        val placeable = measurable.measure(constraints)
        layout(placeable.width, placeable.height) {
            placeable.place(0, 0)
        }
    }
}
```

Every `BoxWithConstraints` recomposes its content when constraints change—avoid wrapping large subtrees; place the constraint boundary as low as possible in the tree.

## Slot keys and stability

Use stable, descriptive slot keys—not indices that shift:

```kotlin
subcompose("leadingIcon") { Icon() }
subcompose("label") { Text(label) }
subcompose("trailing") { trailingContent() }
```

Changing slot keys between passes discards composition state and triggers full recompose of that slot.

## Performance guidelines

**Minimize subcompose calls.** Each slot may compose independently. Prefer one slot with internal Row/Column over five subcompose slots when possible.

**Avoid reading animated state inside subcompose.** Subcomposing during scroll-driven constraint changes recomposes every frame. Pre-compose scroll-independent chrome; animate with placement offsets instead.

**Cache measurements.** If constraints unchanged from last pass, reuse placeables where SubcomposeLayout APIs allow—some custom implementations store `Placeable` in remember keyed by constraints.

**Profile with Layout Inspector.** Watch for excessive subcomposition count in release builds with Macrobenchmark frame timing.

## When Layout suffices

If child set is fixed and only *placement* depends on sizes, use regular `Layout`:

```kotlin
Layout(content = { Title(); Actions() }) { measurables, constraints ->
    val (titleMeasurable, actionsMeasurable) = measurables
    val actionsPlaceable = actionsMeasurable.measure(Constraints())
    val titlePlaceable = titleMeasurable.measure(
        constraints.copy(maxWidth = constraints.maxWidth - actionsPlaceable.width)
    )
    // place...
}
```

Both children compose once regardless of measured widths—cheaper than SubcomposeLayout when responsive content selection is not needed.

## Alternative: intrinsic measurements

Sometimes `Modifier.layout` with intrinsic query avoids SubcomposeLayout:

```kotlin
Modifier.width(intrinsicSize = IntrinsicSize.Min)
```

Intrinsics answer size questions without full subcomposition—try before SubcomposeLayout.

## SubcomposeLayout slot pattern

The core pattern — compose different content based on measured size:

```kotlin
SubcomposeLayout { constraints ->
    // Phase 1: measure main content
    val mainPlaceables = subcompose("main") {
        MainContent()
    }.map { it.measure(constraints) }

    val mainWidth = mainPlaceables.maxOf { it.width }
    val remainingWidth = constraints.maxWidth - mainWidth

    // Phase 2: compose adaptive content based on measurement
    val adaptivePlaceables = subcompose("adaptive") {
        if (remainingWidth > 200.dp.roundToPx()) {
            ExpandedActions()  // full action bar
        } else {
            CompactMenu()      // overflow menu
        }
    }.map { it.measure(Constraints(maxWidth = remainingWidth)) }

    layout(constraints.maxWidth, constraints.maxHeight) {
        var x = 0
        mainPlaceables.forEach { it.place(x, 0); x += it.width }
        adaptivePlaceables.forEach { it.place(x, 0) }
    }
}
```

SubcomposeLayout enables responsive UI that standard Layout can't — content selection depends on measurement results.

## LazySubcomposeLayout for lists

For lazy lists with variable-height items of different types:

```kotlin
// Used internally by LazyGrid for span calculations
// Custom implementation for complex multi-type lists
SubcomposeLayout { constraints ->
    val items = subcompose("items") {
        items.forEach { item ->
            when (item.type) {
                ItemType.HEADER -> HeaderItem(item)
                ItemType.CONTENT -> ContentItem(item)
                ItemType.AD -> AdItem(item)
            }
        }
    }
    // measure and place with type-specific heights
}
```

Prefer standard LazyColumn/LazyGrid when possible — custom LazySubcomposeLayout is complex and error-prone.

## Performance measurement

Profile SubcomposeLayout implementations:

```kotlin
// Enable in debug builds
@OptIn(ExperimentalComposeUiApi::class)
Modifier.onPlaced { coordinates ->
    if (BuildConfig.DEBUG) {
        Log.d("SubcomposeLayout", "subcompose count: ${subcomposeCount}")
    }
}
```

Target: subcompose count equals number of unique slot names, not number of recomposition passes. Count growing on every frame indicates missing cache.

## Failure modes

- **SubcomposeLayout when Layout suffices** — unnecessary double composition cost
- **Unbounded subcompose slots** — slot count grows with list size; memory issue
- **No measurement caching** — re-subcomposes on every frame despite unchanged constraints
- **IntrinsicSize not tried first** — simpler API overlooked for size-query-only cases
- **Complex slot logic untested** — adaptive content selection breaks at specific screen widths

## Production checklist

- IntrinsicSize or standard Layout tried before SubcomposeLayout
- Subcompose slot names fixed and bounded (not per-item dynamic names)
- Measurement results cached when constraints unchanged
- Adaptive content selection tested at boundary widths
- Subcompose count profiled in debug builds
- LazySubcomposeLayout avoided unless standard LazyGrid insufficient

## Resources

- [SubcomposeLayout reference](https://developer.android.com/reference/kotlin/androidx/compose/ui/layout/SubcomposeLayout)
- [SubcomposeLayoutState](https://developer.android.com/reference/kotlin/androidx/compose/ui/layout/SubcomposeLayoutState)
- [Compose layout performance](https://developer.android.com/jetpack/compose/performance)
- [BoxWithConstraints source patterns](https://developer.android.com/reference/kotlin/androidx/compose/foundation/layout/BoxWithConstraints)
