---
title: "Building Custom Lazy Layouts in Compose"
slug: "compose-custom-lazy-layouts"
description: "Building custom lazy layouts in Compose uses the LazyLayout API to compose and measure only visible items, letting you create scrolling containers LazyColumn can't."
datePublished: "2026-06-10"
dateModified: "2026-06-10"
tags: ["Android", "Jetpack Compose", "Performance"]
keywords: "custom lazy layout, LazyLayout API, Compose lazy list, item provider, custom scrolling Compose"
faq:
  - q: "What is the LazyLayout API in Jetpack Compose?"
    a: "LazyLayout is the low-level foundation that LazyColumn, LazyRow, and LazyVerticalGrid are built on. It gives you two things: an item provider that describes a large set of items without composing them all, and a measure policy where you decide which items are visible and compose plus measure only those. It lets you build custom scrolling containers with layout behavior the built-in lazy lists don't offer."
  - q: "When should I build a custom lazy layout instead of using LazyColumn?"
    a: "Almost never for standard lists — LazyColumn, LazyRow, LazyVerticalGrid, and LazyVerticalStaggeredGrid cover the vast majority of cases and are heavily optimized. Reach for a custom LazyLayout only when you need a genuinely different layout model: a circular or arc list, a pager with unusual snapping, a timeline, or a canvas-like surface where composing every item would be too expensive."
  - q: "How does a lazy layout avoid composing every item?"
    a: "The item provider exposes an item count and a way to compose an item by index on demand, rather than a pre-built list of composables. In the measure policy you calculate which indices fall in the visible window given the current scroll offset, then call measure only for those. Items scrolled off-screen are disposed, so memory and composition cost track the viewport size, not the dataset size."
---

Ninety-nine times out of a hundred, the right way to build a scrolling list in Compose is `LazyColumn` and you should stop reading. But that hundredth case — a circular menu, an arc of cards, a timeline that isn't a straight vertical run, a pager with snapping the built-ins don't do — is where the `LazyLayout` API earns its place. It's the low-level primitive that `LazyColumn`, `LazyRow`, and the grids are themselves built on, and it gives you the two things that make "lazy" work: an item provider that describes a huge dataset without materializing it, and a measure policy where *you* decide which items are visible and compose only those.

I want to be honest up front about how rarely you need this, because the API is powerful enough that people reach for it when a custom arrangement on a normal `LazyColumn` would have done. But when you genuinely need a novel scrolling model, nothing else gives you both the layout freedom and the laziness.

## What "lazy" actually means

The magic of a lazy list is that a 10,000-item feed doesn't compose 10,000 composables. Only the items in (and just around) the viewport exist at any moment; the rest are a count and a recipe for building item N on demand. As you scroll, items entering the viewport get composed and measured, items leaving get disposed. Memory and composition cost scale with the *viewport*, not the dataset.

`LazyLayout` exposes that machinery directly. You provide:

- An **item provider**: how many items there are, and how to compose the item at a given index (plus optional keys and content types).
- A **measure policy**: given the constraints and the current scroll offset, decide which indices are visible, ask the provider to compose/measure just those, and place them.

Everything `LazyColumn` does — sticky headers, content padding, item animations — is built from these two pieces plus a lot of careful measure-policy code.

## The item provider

The provider is deliberately lazy: it doesn't hold composables, it holds the *ability* to produce them by index.

```kotlin
@OptIn(ExperimentalFoundationApi::class)
private fun arcItemProvider(
    items: List<CardData>,
    itemContent: @Composable (CardData) -> Unit,
) = LazyLayoutItemProvider(
    itemCount = items.size,
    key = { index -> items[index].id },
    contentType = { CardContentType },
    item = { index -> itemContent(items[index]) },
)
```

Stable **keys** matter as much here as in a normal lazy list — they let Compose reuse and correctly animate items when the dataset changes rather than recomposing by position. And **content types** let the subcomposition layer reuse the internal structure of items of the same shape, which is a real performance lever when you scroll fast. Skipping keys is the most common way people make a custom lazy layout that technically works but janks and loses scroll state on updates.

## The measure policy: where the real work lives

The measure policy is the heart of a custom lazy layout, and it's the part with no shortcuts. You get the incoming constraints and the current scroll offset (which you own, typically in a `remember`ed scroll state driven by `scrollable`), and you compute the visible window, measure those items, and place them:

```kotlin
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun ArcLazyRow(items: List<CardData>, state: ArcScrollState, content: @Composable (CardData) -> Unit) {
    val provider = remember(items) { arcItemProvider(items, content) }
    LazyLayout(itemProvider = { provider }) { constraints ->
        val itemWidth = 200
        val firstVisible = (state.offset / itemWidth).toInt().coerceAtLeast(0)
        val visibleCount = (constraints.maxWidth / itemWidth) + 2 // small overscan
        val lastVisible = (firstVisible + visibleCount).coerceAtMost(items.lastIndex)

        val placeables = (firstVisible..lastVisible).map { index ->
            index to measure(index, Constraints.fixedWidth(itemWidth)).first()
        }

        layout(constraints.maxWidth, constraints.maxHeight) {
            placeables.forEach { (index, placeable) ->
                val x = (index * itemWidth) - state.offset.toInt()
                val y = arcYForX(x, constraints.maxHeight) // the custom part
                placeable.place(x, y)
            }
        }
    }
}
```

The two lines that make this a *lazy* layout are the visible-window calculation and the fact that `measure(index, ...)` is only called for indices in that window. Everything outside it is never composed. The `arcYForX` is where your custom model lives — that single function is the difference between a plain row and an arc, and it's why you're using `LazyLayout` instead of `LazyRow` at all.

Note the small **overscan** (`+ 2`): composing a couple of items just outside the viewport avoids a blank edge appearing for one frame during fast scrolls. Too much overscan and you're back to composing more than you need; too little and you flash empty space. It's a tuning knob you set by testing on a real device.

## The performance rules are non-negotiable

A custom lazy layout runs its measure policy every scroll frame, which means it lives squarely in your frame budget. Every discipline from [Compose performance, stability, and recomposition](https://blog.michaelsam94.com/compose-performance-stability-recomposition/) applies with extra force here:

- **No allocation in the measure lambda's hot path.** Building lists and boxing values every frame is how you turn a clever layout into a stuttering one. Cache what you can across frames.
- **Stable item content.** If each item recomposes unnecessarily as you scroll, the laziness saved you nothing. Keep item state stable and hoisted.
- **Cheap visibility math.** The visible-window calculation runs constantly; keep it O(1), not a scan over all items.

I've seen a custom lazy layout that composed only visible items but still dropped frames because its measure policy allocated a fresh list and did trig for every possible index each pass. Laziness at the composition layer doesn't rescue you from waste in the measure layer.

## When to build one — and when not to

The temptation is to build a custom lazy layout for any non-standard arrangement. Resist it. Before writing a measure policy, ask whether the built-ins plus an arrangement or a modifier get you there. A lot of "custom grid" needs are actually met by the standard adaptive tooling — the same ground covered in [adaptive layouts with Compose grids and flexbox-style arrangements](https://blog.michaelsam94.com/adaptive-layouts-compose-grid-flexbox/). `LazyVerticalGrid` with `GridCells.Adaptive`, or a staggered grid, handles far more than people assume.

My genuine bar for reaching for `LazyLayout`:

1. The **layout model itself is different** — items aren't placed in a straight line or a regular grid (arcs, spirals, timelines, physics-driven placement).
2. The dataset is **large enough that laziness is required** — if you'd only ever show 20 items, just use a `Row`/`Column` in a scroll container and skip all this.
3. **No existing lazy component** can be bent to fit with reasonable effort.

Clear all three and `LazyLayout` is the right, and frankly enjoyable, tool. It's one of the few places in Compose where you get to work at the same level as the framework authors, and the result — a bespoke scrolling surface that still only composes what's visible — is genuinely satisfying to ship. Fall short of all three and you've signed up to reimplement scroll state, accessibility, and item animation that `LazyColumn` already gives you for free. Choose deliberately.

## Resources

- [LazyLayout API reference](https://developer.android.com/reference/kotlin/androidx/compose/foundation/lazy/layout/package-summary)
- [Lists and grids in Compose](https://developer.android.com/develop/ui/compose/lists)
- [Custom layouts in Compose](https://developer.android.com/develop/ui/compose/layouts/custom)
- [AndroidX Compose foundation source](https://github.com/androidx/androidx/tree/androidx-main/compose/foundation)
- [Compose performance guidance](https://developer.android.com/develop/ui/compose/performance)
