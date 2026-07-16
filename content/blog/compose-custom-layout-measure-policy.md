---
title: "Writing a Custom Compose Layout"
slug: "compose-custom-layout-measure-policy"
description: "Build custom Compose layouts with Layout composable: measure policies, placement, intrinsic measurements, and when BoxWithConstraints is not enough."
datePublished: "2025-03-25"
dateModified: "2025-03-25"
tags: ["Android", "Compose"]
keywords: "Compose custom layout, Layout composable, measure policy, placement, intrinsic measurements"
faq:
  - q: "When should I write a custom Layout instead of using Row or Column?"
    a: "Write a custom Layout when child positioning depends on measured sizes of siblings in non-linear ways—overlapping cards, radial menus, flow layouts with custom break rules, or charts mapping data to coordinates. If Row, Column, Box, and FlowRow cover your case with modifiers, use them—custom layouts cost maintenance and must handle RTL and accessibility."
  - q: "What are the two phases of Compose layout?"
    a: "Measure phase: parent passes constraints down, children return Placeable sizes. Placement phase: parent positions Placeables within its own bounds. Constraints are min/max width and height; children must choose a size within those bounds. Placement uses x/y offsets relative to the parent layout node."
  - q: "How do intrinsic measurements work?"
    a: "Intrinsics answer 'how big would this child be if given unbounded space in one axis?' Custom layouts implementing LayoutModifier or providing intrinsic methods enable scrollable containers and parent-driven sizing. Override minIntrinsicWidth, maxIntrinsicHeight, etc., when your layout participates in scroll or nested sizing negotiations."
---

`Row` and `Column` cover ninety percent of layouts. The other ten percent—children that overlap based on measured height, a badge anchored to arbitrary points on a card, a chart plotting y-values against x-positions—need the `Layout` composable. Custom layout is where Compose stops feeling like flexbox and starts feeling like a retained-mode UI toolkit with explicit measure and place passes.

## The Layout composable skeleton

```kotlin
@Composable
fun SimpleOverlapLayout(
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    Layout(
        content = content,
        modifier = modifier,
    ) { measurables, constraints ->
        val placeables = measurables.map { measurable ->
            measurable.measure(constraints)
        }
        val width = placeables.maxOfOrNull { it.width } ?: 0
        val height = placeables.maxOfOrNull { it.height } ?: 0
        layout(width, height) {
            var y = 0
            placeables.forEach { placeable ->
                placeable.placeRelative(x = 0, y = y)
                y += placeable.height / 2  // intentional overlap
            }
        }
    }
}
```

Three callbacks matter:

1. **measurables** — children not yet measured
2. **constraints** — `minWidth`, `maxWidth`, `minHeight`, `maxHeight` from parent
3. **layout(width, height) { }** — report own size and place children

Use `placeRelative` instead of `place` for RTL-aware horizontal positioning.

## Constraints in practice

Constraints are not pixel requests—they are allowed ranges. A child receiving `maxWidth = 400` may choose any width from `minWidth` to 400.

```kotlin
// Force child to exactly parent's max width
val childConstraints = constraints.copy(
    minWidth = constraints.maxWidth,
    maxWidth = constraints.maxWidth,
)
```

When measuring multiple children that share horizontal space, partition constraints:

```kotlin
val halfMax = constraints.maxWidth / 2
val left = measurables[0].measure(
    constraints.copy(maxWidth = halfMax)
)
val right = measurables[1].measure(
    constraints.copy(maxWidth = constraints.maxWidth - left.width)
)
```

## Custom measure policy with LayoutModifier

For reusable layout behavior as a modifier:

```kotlin
fun Modifier.alignToBaselineOf(anchor: () -> Int) = this.then(
    object : LayoutModifier {
        override fun MeasureScope.measure(
            measurable: Measurable,
            constraints: Constraints,
        ): MeasureResult {
            val placeable = measurable.measure(constraints)
            val baselineOffset = anchor()
            return layout(placeable.width, placeable.height) {
                placeable.place(0, baselineOffset - placeable.height)
            }
        }
    }
)
```

`LayoutModifier` wraps a single child—good for offset, padding-like, or alignment tweaks without a full multi-child `Layout`.

## Flow layout example

A simplified horizontal flow that wraps to new rows:

```kotlin
@Composable
fun FlowLayout(
    modifier: Modifier = Modifier,
    horizontalSpacing: Dp = 8.dp,
    verticalSpacing: Dp = 8.dp,
    content: @Composable () -> Unit,
) {
    Layout(content = content, modifier = modifier) { measurables, constraints ->
        val hGap = horizontalSpacing.roundToPx()
        val vGap = verticalSpacing.roundToPx()
        val rows = mutableListOf<List<Placeable>>()
        var currentRow = mutableListOf<Placeable>()
        var rowWidth = 0
        var maxRowWidth = 0

        measurables.forEach { measurable ->
            val placeable = measurable.measure(constraints.copy(minWidth = 0, minHeight = 0))
            if (rowWidth + placeable.width > constraints.maxWidth && currentRow.isNotEmpty()) {
                rows.add(currentRow)
                maxRowWidth = max(maxRowWidth, rowWidth - hGap)
                currentRow = mutableListOf()
                rowWidth = 0
            }
            currentRow.add(placeable)
            rowWidth += placeable.width + hGap
        }
        if (currentRow.isNotEmpty()) {
            rows.add(currentRow)
            maxRowWidth = max(maxRowWidth, rowWidth - hGap)
        }

        val height = rows.sumOf { row -> row.maxOf { it.height } } +
            (rows.size - 1).coerceAtLeast(0) * vGap

        layout(maxRowWidth.coerceIn(constraints.minWidth, constraints.maxWidth), height) {
            var y = 0
            rows.forEach { row ->
                var x = 0
                val rowHeight = row.maxOf { it.height }
                row.forEach { placeable ->
                    placeable.placeRelative(x, y)
                    x += placeable.width + hGap
                }
                y += rowHeight + vGap
            }
        }
    }
}
```

Compose 1.4+ ships `FlowRow` and `FlowColumn`—check androidx before maintaining custom flow code.

## Intrinsics for scroll and parent sizing

Parent composables like `LazyRow` query child intrinsics. If your custom layout affects scroll extent, implement:

```kotlin
override fun minIntrinsicHeight(width: Int): Int { /* ... */ }
override fun maxIntrinsicWidth(height: Int): Int { /* ... */ }
```

Without intrinsics, nested scroll or `height(IntrinsicSize.Min)` may measure incorrectly.

## Debugging layout

Enable Compose layout inspector in Android Studio. Log constraints and sizes during development:

```kotlin
layout(width, height) {
    placeables.forEachIndexed { i, p ->
        Log.d("CustomLayout", "child $i: ${p.width}x${p.height}")
        p.placeRelative(0, 0)
    }
}
```

Recomposition loops often trace to reading size during composition instead of in the layout lambda—keep layout math in `Layout { }`, not in `@Composable` body.

## Performance notes

Custom layouts run on every recomposition that affects children. Avoid expensive work in measure—cache calculations keyed on measurable count and constraints if needed.

Prefer `SubcomposeLayout` only when child composition depends on parent size (see separate article)—standard `Layout` is cheaper.

## Custom Layout measure policy

```kotlin
fun Modifier.customGrid(columns: Int) = layout { measurables, constraints ->
    val cellWidth = constraints.maxWidth / columns
    val placeables = measurables.map { it.measure(constraints.copy(maxWidth = cellWidth)) }
    // place placeables...
}
```

Measure pass must be pure — no state reads that change between measure and layout. Use `measurable.measure()` not child composable calls.

## Common production mistakes

Teams get custom layout measure policy wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Compose UI work on custom layout measure policy janks when recomposition scope is too wide, `remember` keys omit stable inputs, and semantics for TalkBack are added only after QA finds focus traps.

## Debugging and triage workflow

When custom layout measure policy misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Compose layout basics](https://developer.android.com/jetpack/compose/layouts/basics)
- [Custom layouts guide](https://developer.android.com/jetpack/compose/layouts/custom)
- [Constraints and measure policy](https://developer.android.com/reference/kotlin/androidx/compose/ui/unit/Constraints)
- [LayoutModifier reference](https://developer.android.com/reference/kotlin/androidx/compose/ui/layout/LayoutModifier)
