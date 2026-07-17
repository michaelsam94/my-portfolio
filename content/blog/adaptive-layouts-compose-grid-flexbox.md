---
title: "Adaptive Layouts in Compose: Grid, FlexBox, MediaQuery"
slug: "adaptive-layouts-compose-grid-flexbox"
description: "Build adaptive layouts in Jetpack Compose using window size classes, Grid, FlexBox, and MediaQuery-style APIs. Responsive UI for phones, foldables, and tablets."
datePublished: "2026-03-16"
dateModified: "2026-03-16"
tags: ["Android", "Jetpack Compose", "Adaptive UI", "Foldables"]
keywords: "Compose Grid, Compose adaptive layout, MediaQuery Compose, FlexBox Compose, responsive Compose, foldables"
faq:
  - q: "How do you build adaptive layouts in Jetpack Compose?"
    a: "Drive layout decisions from window size classes rather than hardcoded device checks. Use WindowSizeClass to pick between compact, medium, and expanded layouts, and use grid and flex primitives to reflow content. This keeps one composable responsive across phones, foldables, and tablets."
  - q: "What is the difference between window size class and screen size?"
    a: "Screen size is the raw pixel dimension; window size class is a semantic bucket (compact, medium, expanded) based on the available window, not the physical display. Size classes are what you should branch on, because they handle split-screen, foldables, and resizable windows correctly."
  - q: "Should I use a Grid or a FlexBox layout in Compose?"
    a: "Use a grid when you want items aligned to consistent rows and columns, like a photo gallery. Use a flex-style layout when items have varying sizes and should wrap and fill available space fluidly, like chips or tags. Many adaptive screens use both."
---

The fastest way to build a layout that breaks on a foldable is to branch on `if (isTablet)`. I've inherited more than one codebase that did exactly that, and every one of them shipped broken split-screen and multi-window experiences. Adaptive layouts in Compose start from a different premise: you don't care what the *device* is, you care how much *window* you've been given right now — which changes when the user unfolds, rotates, or drags your app into split-screen.

Compose has grown a solid set of tools for this: window size classes to decide *what* layout to show, and grid and flex primitives to decide *how* content reflows within it. Used together they let one composable serve a phone, a foldable, and a tablet without device sniffing.

## Branch on window size class, never on device

The foundation is `WindowSizeClass`, which buckets the current window into `Compact`, `Medium`, and `Expanded` on each axis. This is the Compose analog of CSS media queries, and it's the only correct thing to branch on, because it reflects the *available window* — respecting split-screen, foldables, and desktop windowing — not the physical panel.

```kotlin
@Composable
fun AdaptiveScreen(windowSizeClass: WindowSizeClass) {
    when (windowSizeClass.widthSizeClass) {
        WindowWidthSizeClass.Compact ->
            SinglePaneList()                 // phone portrait
        WindowWidthSizeClass.Medium ->
            SinglePaneList(columns = 2)      // foldable / small tablet
        WindowWidthSizeClass.Expanded ->
            ListDetailPane()                 // tablet / desktop: two panes
    }
}
```

The rule of thumb: use width classes to switch *navigation and pane structure* (single pane vs list-detail), and use the layout primitives below to reflow content *within* a pane. For the canonical patterns — list-detail, supporting-pane — the `androidx.compose.material3.adaptive` library gives you scaffolds so you don't hand-roll them.

## Grid: aligned rows and columns

`LazyVerticalGrid` handles the classic responsive-gallery case. The key is `GridCells.Adaptive`, which sizes the number of columns to the available width instead of you picking a fixed count per breakpoint:

```kotlin
LazyVerticalGrid(
    columns = GridCells.Adaptive(minSize = 160.dp),
    contentPadding = PaddingValues(16.dp),
    horizontalArrangement = Arrangement.spacedBy(12.dp),
    verticalArrangement = Arrangement.spacedBy(12.dp),
) {
    items(photos, key = { it.id }) { PhotoCell(it) }
}
```

`Adaptive(minSize = 160.dp)` says "as many columns as fit, each at least 160dp." A narrow phone gets two columns, a tablet gets five or six — automatically, with no size-class branching for the grid itself. Always pass a stable `key` in `items`; unkeyed grids recompose and re-scroll badly, the same [recomposition](https://blog.michaelsam94.com/compose-performance-stability-recomposition/) pitfall that bites lists.

## FlexBox: fluid wrapping for uneven items

When items vary in width and should wrap to fill the row — filter chips, tags, keyword pills — a grid's fixed cells fight you. That's what `FlowRow` and `FlowColumn` are for. They place children in sequence and wrap to the next line when they run out of room, which is the Compose equivalent of CSS flex-wrap.

```kotlin
FlowRow(
    horizontalArrangement = Arrangement.spacedBy(8.dp),
    verticalArrangement = Arrangement.spacedBy(8.dp),
) {
    filters.forEach { FilterChip(it) }
}
```

Reach for flow layouts whenever content is intrinsically sized and heterogeneous; reach for grid when you want the tidy alignment of consistent cells. Many real screens use both — a flow row of filters above a grid of results.

## The pattern that scales: layout as a function of window

Putting it together, the discipline that keeps adaptive UI maintainable is treating layout as a *pure function of window metrics*, decided at one level, then passed down. Don't sprinkle size checks through leaf composables; resolve the size class near the top and hand children a semantic decision.

| Content type | Primitive | Adapts by |
|---|---|---|
| Pane structure (nav, list-detail) | `WindowSizeClass` + adaptive scaffolds | width size class |
| Uniform cells (gallery, cards) | `LazyVerticalGrid` + `GridCells.Adaptive` | available width |
| Uneven wrapping items (chips) | `FlowRow` / `FlowColumn` | content + width |
| Fully custom | `Layout` / `SubcomposeLayout` | your own logic |

This mirrors the state-hoisting principle from [ten years of Compose lessons](https://blog.michaelsam94.com/jetpack-compose-lessons-10-years-android/): make the decision once, high up, and keep the leaves dumb.

## Foldables and continuity

Foldables add a wrinkle: the window changes *while the app is running* when the user folds or unfolds, and there may be a hinge cutting through your layout. Two things matter. First, because you're already driving layout off window size classes, an unfold naturally re-evaluates and reflows — that's the payoff for not device-sniffing. Second, use `WindowInfoTracker` (from Jetpack WindowManager) to detect fold posture and hinge bounds when you want to do something clever like tabletop mode (content above the fold, controls below). And test state preservation across the fold: `rememberSaveable` for anything the user would hate to lose, since a fold is effectively a configuration change.

## Edge-to-edge and insets

Adaptive layout and system insets go hand in hand. On modern Android, apps draw [edge-to-edge](https://blog.michaelsam94.com/edge-to-edge-android-16/) by default, so your adaptive content must respect `WindowInsets` (status bar, navigation bar, display cutout, IME) or it'll draw under system UI. Apply insets at the scaffold level and let padding flow down; combined with size-class-driven structure, that's what makes a layout feel native on everything from a compact phone to a desktop window.

## BoxWithConstraints: local MediaQuery-style decisions

`WindowSizeClass` answers global questions — single pane or list-detail — but leaf composables often need local reflow without another top-level branch. `BoxWithConstraints` exposes `maxWidth` and `maxHeight` inside a subtree, which is the Compose equivalent of a CSS `@container` or media query scoped to a parent:

```kotlin
@Composable
fun ProductCard(product: Product, modifier: Modifier = Modifier) {
    BoxWithConstraints(modifier) {
        if (maxWidth >= 400.dp) {
            Row(Modifier.fillMaxWidth()) {
                ProductImage(product, Modifier.weight(1f))
                ProductDetails(product, Modifier.weight(1f))
            }
        } else {
            Column {
                ProductImage(product, Modifier.fillMaxWidth())
                ProductDetails(product)
            }
        }
    }
}
```

Use size classes for navigation and pane structure; use `BoxWithConstraints` when the same screen hosts cards or rows that should reflow based on *allocated* width inside a pane — especially in list-detail where the detail pane might be medium-width even on an expanded window. Avoid nesting many `BoxWithConstraints` layers; one local breakpoint per composable is usually enough.

## Typography and spacing that scale with width

Adaptive layout is not only columns and panes. Material 3 typography tokens (`displayLarge`, `titleMedium`, `bodyLarge`) should track window width so headlines do not dominate a phone or shrink on a desktop window. A practical pattern is mapping width size class to a `Typography` override at the theme level:

```kotlin
@Composable
fun AdaptiveTheme(windowSizeClass: WindowSizeClass, content: @Composable () -> Unit) {
    val typography = when (windowSizeClass.widthSizeClass) {
        WindowWidthSizeClass.Compact -> compactTypography()
        WindowWidthSizeClass.Medium -> mediumTypography()
        WindowWidthSizeClass.Expanded -> expandedTypography()
    }
    MaterialTheme(typography = typography, content = content)
}
```

Spacing follows the same rule: 8dp gutters on compact, 16–24dp on expanded. Hardcoding `padding(16.dp)` everywhere makes tablet layouts feel cramped relative to the extra horizontal space you earned by switching to list-detail.

## Testing adaptive behavior without a device farm

You do not need every form factor on your desk. `ComposeTestRule` can inject width and height via `DeviceConfigurationOverride` (AndroidX Compose UI test) or by wrapping content in a sized `Box` in screenshot tests. For each critical screen, assert three configurations: compact portrait (~360dp), medium unfolded (~600dp), and expanded landscape (~840dp+). Verify that list-detail scaffolds show one vs two panes, that `GridCells.Adaptive` produces the expected column count, and that `rememberSaveable` state survives a simulated configuration change. Fold regression tests belong in CI — a broken split-screen layout ships silently otherwise.

## What I'd take away

Stop asking "is this a tablet?" and start asking "how much window do I have?" Branch structure on `WindowSizeClass`, reflow uniform content with `GridCells.Adaptive`, wrap uneven content with `FlowRow`/`FlowColumn`, resolve size decisions high in the tree, and respect insets. That combination gives you a single codebase that behaves correctly across phones, foldables, tablets, split-screen, and desktop windows — without the fragile device checks that break the moment a new form factor ships.

## Resources

- [Support different screen sizes (Android)](https://developer.android.com/develop/ui/compose/layouts/adaptive)
- [Window size classes](https://developer.android.com/develop/ui/compose/layouts/adaptive/use-window-size-classes)
- [LazyVerticalGrid reference](https://developer.android.com/reference/kotlin/androidx/compose/foundation/lazy/grid/package-summary)
- [FlowRow and FlowLayout](https://developer.android.com/develop/ui/compose/layouts/flow)
- [Jetpack WindowManager for foldables](https://developer.android.com/jetpack/androidx/releases/window)
