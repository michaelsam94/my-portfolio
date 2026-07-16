---
title: "LookaheadScope for Fluid Layout Animations in Compose"
slug: "compose-lookahead-layout-animations"
description: "Use LookaheadScope and animateBounds in Jetpack Compose to animate elements between layout positions and sizes — shared-element style motion without hacks."
datePublished: "2024-09-08"
dateModified: "2024-09-08"
tags: ["Android", "Jetpack Compose", "Animation", "UI"]
keywords: "LookaheadScope, LookaheadLayout, animateBounds, Compose shared element, Compose layout animation, movableContentOf"
faq:
  - q: "What is LookaheadScope in Jetpack Compose?"
    a: "LookaheadScope lets Compose measure where a layout will end up before it is drawn, then animate elements smoothly from their current position and size to that future position and size. It is the foundation for shared-element transitions and fluid layout changes, because it gives children knowledge of their target bounds so they can interpolate toward them instead of snapping."
  - q: "What is the difference between LookaheadScope and animateContentSize?"
    a: "animateContentSize animates a single container resizing in place. LookaheadScope animates elements moving and resizing between fundamentally different layout arrangements — for example an item jumping from a row into a grid, or a thumbnail expanding into a full-screen header. LookaheadScope handles position changes across the tree, not just one container growing."
  - q: "Do I need LookaheadScope for shared-element transitions?"
    a: "The shared-element transition APIs in Compose are built on top of LookaheadScope. SharedTransitionLayout wraps LookaheadScope for the common navigation case, but understanding LookaheadScope helps you build custom fluid animations that the shared-element API does not cover, such as reflowing a toolbar or morphing a list into a grid."
---

`LookaheadScope` is Compose's answer to a hard problem: animating an element as it moves between two genuinely different layout arrangements — a chip jumping from a wrapped row into a selected slot, a thumbnail expanding into a full-screen header, a list morphing into a grid. It works by letting Compose *pre-measure* where each child will land, so instead of the child snapping to its new position on the next frame, it can interpolate from where it is now to where it's going. This "measure the future, then animate toward it" trick is what powers shared-element transitions and every fluid reflow that used to require manual coordinate math.

Most developers meet `LookaheadScope` indirectly through `SharedTransitionLayout`, which wraps it for navigation. But knowing the primitive underneath lets you build motion the high-level API doesn't cover, and that's what I want to walk through.

## Why ordinary layout changes snap

When a layout recomposes into a new arrangement, Compose measures and places children at their new positions immediately — there's no in-between. Change a `Row` to wrap differently or move an item to a new parent and it teleports. `animateContentSize` smooths a single container growing, but it knows nothing about an element that *relocated*. You need something that knows both the "before" and "after" bounds. That's the lookahead pass.

`LookaheadScope` runs an extra measurement pass that computes each child's *target* size and position ahead of the actual placement. Children inside the scope can read the difference between where they are and where they'll be, and animate across it.

## animateBounds: the practical entry point

You rarely wire the lookahead math by hand. The `Modifier.animateBounds` modifier (in the animation library) does the position-and-size interpolation for any child inside a `LookaheadScope`:

```kotlin
LookaheadScope {
    FlowRow {
        items.forEach { item ->
            Chip(
                item,
                modifier = Modifier.animateBounds(
                    lookaheadScope = this@LookaheadScope,
                ),
            )
        }
    }
}
```

Now when the flow reflows — the row wraps differently because an item was added, or a chip changed size — each chip glides to its new spot instead of jumping. The modifier reads the lookahead target bounds and animates position and size together. This alone turns a jarring reflow into something that looks designed.

## Morphing a list into a grid

The classic showcase is toggling between a list and a grid layout for the same items. Without lookahead you'd cross-fade two layouts and lose object continuity. With it, each item physically travels from its list position to its grid position:

```kotlin
LookaheadScope {
    val modifier = Modifier.animateBounds(this@LookaheadScope)
    if (isGrid) {
        LazyVerticalGrid(GridCells.Fixed(2)) {
            items(data, key = { it.id }) { Card(it, modifier) }
        }
    } else {
        LazyColumn {
            items(data, key = { it.id }) { Card(it, modifier) }
        }
    }
}
```

Two things are essential here. Stable `key`s so Compose matches the same item across the two layouts — without keys it can't know that "card 7" in the list is "card 7" in the grid, and the animation falls apart. And the *same modifier instance concept* applied inside each branch, so the item is tracked in both. The result is object permanence: users see the cards rearrange, not a screen replaced.

## movableContentOf: keeping state across the move

When an element moves between two *different composable parents* — not just repositions within one — you also want its internal state (scroll position, animation, playing video) to survive the move rather than reset. That's `movableContentOf`. It lets you declare content once and place it in different slots without it being torn down and recreated.

```kotlin
val hero = remember {
    movableContentOf { HeroImage(url) }
}

LookaheadScope {
    if (expanded) {
        FullScreenHeader { hero() }
    } else {
        ThumbnailRow { hero() }
    }
}
```

Combine `movableContentOf` (state survives the reparenting) with `animateBounds` (position/size animates) and you get a true shared element: same node, same state, smoothly traveling between two totally different layouts. This is exactly the machinery `SharedTransitionLayout` packages up for cross-screen navigation transitions.

## Where the shared-element API fits

For navigation between screens — tapping a list item and having its image expand into the detail screen — reach for `SharedTransitionLayout` and `Modifier.sharedElement`. It's built on `LookaheadScope` and handles the tricky part of matching elements across a `NavHost` destination change. Use the high-level API when the motion crosses a navigation boundary; use raw `LookaheadScope` + `animateBounds` when the reflow happens *within* one screen, where dropping down to the primitive is simpler than shoe-horning navigation semantics in.

| Scenario | Reach for |
| --- | --- |
| Reflow within one screen | `LookaheadScope` + `animateBounds` |
| List ↔ grid toggle | `LookaheadScope` + `animateBounds` + keys |
| Element crossing screens | `SharedTransitionLayout` + `sharedElement` |
| Keep state while moving parents | `movableContentOf` |

## Cost and caveats

The lookahead pass isn't free — it's a second measurement of the subtree inside the scope, every frame the layout is changing. Keep `LookaheadScope` tight around the elements that actually animate rather than wrapping your whole screen. And be honest about scope: lookahead animates *layout*, not arbitrary drawing, so it won't help a canvas-based effect. For value-driven motion you're still better served by the [core animation APIs](https://blog.michaelsam94.com/compose-animation-apis-overview/); lookahead is specifically for elements changing *where and how big* they are across layout arrangements.

One production gotcha: lazy lists recycle, so an item that scrolls off screen and back won't carry an in-flight bounds animation. Lookahead shines for elements that stay composed through the transition. If your morph involves items entering and leaving the composed set, expect the entering ones to appear rather than travel — design the motion around what's actually on screen.

## What I'd take away

`LookaheadScope` gives Compose foresight: it measures where things will be, so elements can animate *to* their future bounds instead of snapping. In practice you reach for `Modifier.animateBounds` inside a scope to make reflows and list-to-grid morphs glide, add stable keys so items are matched across arrangements, and layer in `movableContentOf` when an element must keep its state while changing parents. For cross-screen motion, let `SharedTransitionLayout` do the wrapping. Keep the scope tight for performance, and remember it animates layout, not paint. It's the piece that turns "the UI rearranged" into "the UI moved."

## Resources

- [LookaheadScope API reference](https://developer.android.com/reference/kotlin/androidx/compose/ui/layout/LookaheadScope)
- [Shared element transitions in Compose](https://developer.android.com/develop/ui/compose/animation/shared-elements)
- [Advanced animation and custom layouts](https://developer.android.com/develop/ui/compose/animation/advanced)
- [Compose layout phases](https://developer.android.com/develop/ui/compose/phases)
