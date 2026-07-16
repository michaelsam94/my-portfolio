---
title: "Shared Element Transitions in Jetpack Compose"
slug: "compose-shared-element-transitions"
description: "Shared element transitions in Jetpack Compose animate a UI element between screens using SharedTransitionLayout, giving list-to-detail hero animations without hacks."
datePublished: "2026-02-13"
dateModified: "2026-02-13"
tags: ["Android", "Jetpack Compose", "Animation", "UX"]
keywords: "shared element transitions Compose, SharedTransitionLayout, Compose animation, hero transition, bounds transform"
faq:
  - q: "What are shared element transitions in Jetpack Compose?"
    a: "Shared element transitions animate a composable so it appears to move and morph continuously from one screen to another — for example a thumbnail in a list growing into the header image on a detail screen. In Compose you wrap the relevant content in a SharedTransitionLayout and tag matching elements with the same key using Modifier.sharedElement, and the framework interpolates their bounds during the navigation animation."
  - q: "What is the difference between sharedElement and sharedBounds?"
    a: "Modifier.sharedElement is for the same composable content on both screens — the framework morphs its position and size directly. Modifier.sharedBounds is for two different composables that should share a container transform; it animates the bounds while cross-fading the differing content. Use sharedElement for an identical image or icon, and sharedBounds when the source and target look different but occupy a shared conceptual space."
  - q: "Do shared element transitions work with Navigation Compose?"
    a: "Yes. You place the SharedTransitionLayout above your NavHost and use the AnimatedContentScope provided by each composable destination as the animated visibility scope. The shared element keys connect the list destination and the detail destination, so the transition runs as part of the normal navigation animation between them."
---

For years, the honest answer to "can we do the iOS-style photo-grows-into-the-header animation in Compose?" was "sort of, if you're willing to hand-animate offsets and sizes and accept that it'll break on edge cases." Shared element transitions, now a stable part of Jetpack Compose, make that answer a clean "yes." You wrap the content in a `SharedTransitionLayout`, tag the thumbnail in your list and the header image on the detail screen with the same key, and Compose interpolates the element's bounds so it visually flies and morphs from one screen to the other.

It's the kind of feature that seems like polish until you ship it and watch how much more coherent the app feels. A well-done shared element transition tells the user "this detail screen *is* the thing you tapped," which no fade or slide communicates as clearly.

## The mental model

Three pieces make it work, and getting the model right saves a lot of confusion:

- **`SharedTransitionLayout`** sits above the content that transitions — typically above your `NavHost`. It provides a `SharedTransitionScope` that owns the shared-element bookkeeping.
- **`Modifier.sharedElement(...)`** (or `sharedBounds`) marks a composable as a shared element with a **key**. Two composables on different screens with the same key are understood to be the same thing.
- **An `AnimatedVisibilityScope`** — usually the `AnimatedContentScope` from a navigation destination — tells the framework the visibility timeline to animate against.

The key insight: the framework isn't teleporting one composable across screens. Each screen has its *own* composable; they just share a key, and Compose animates the bounds of the outgoing one into the bounds of the incoming one while managing which is drawn on top. Once that clicks, the API stops feeling magical and starts feeling predictable.

## Wiring it into navigation

Here's the shape of a list-to-detail transition built on top of Navigation Compose. The `SharedTransitionLayout` wraps the `NavHost`, and each destination hands its `AnimatedContentScope` down to the shared elements:

```kotlin
SharedTransitionLayout {
    NavHost(navController, startDestination = "list") {
        composable("list") {
            PhotoGrid(
                sharedScope = this@SharedTransitionLayout,
                animatedScope = this@composable,
                onOpen = { id -> navController.navigate("detail/$id") },
            )
        }
        composable("detail/{id}") {
            PhotoDetail(
                sharedScope = this@SharedTransitionLayout,
                animatedScope = this@composable,
            )
        }
    }
}
```

And the shared image itself, tagged with a stable key derived from the item's identity:

```kotlin
with(sharedScope) {
    AsyncImage(
        model = photo.url,
        contentDescription = photo.title,
        modifier = Modifier
            .sharedElement(
                sharedContentState = rememberSharedContentState(key = "photo-${photo.id}"),
                animatedVisibilityScope = animatedScope,
            )
            .fillMaxWidth(),
    )
}
```

The key must be **stable and unique per item** — `"photo-${photo.id}"`, not a list index. If you key by index, scrolling reorders things and the transition animates the wrong element into place, which looks worse than no transition at all. This is the single most common mistake I see, and it's the same identity discipline that matters everywhere in Compose lists. It pairs directly with the thinking in [Navigation 3 for Jetpack Compose](https://blog.michaelsam94.com/navigation-3-jetpack-compose/), where destinations are typed state you own — a stable destination argument gives you a natural, stable shared-element key.

## sharedElement vs sharedBounds

Choosing the wrong one of these produces subtly wrong animations, so it's worth being precise:

| Use | When | What it does |
| --- | --- | --- |
| `sharedElement` | Same content on both screens (identical image, icon) | Morphs position and size of one visual |
| `sharedBounds` | Different content sharing a space (a card that becomes a screen) | Animates the container bounds, cross-fades the differing content |

The rule I use: if a user would say "that's literally the same picture," use `sharedElement`. If they'd say "that card opened up into a screen," use `sharedBounds`. The classic container transform — a list card expanding into a full detail layout with a header, body, and actions — is `sharedBounds`, because the *contents* differ even though the bounding box is continuous.

## Tuning the motion

Defaults get you a working transition; taste gets you a good one. The knob that matters most is `boundsTransform`, which controls how the element's bounds interpolate:

```kotlin
val boundsTransform = BoundsTransform { _, _ ->
    spring(
        dampingRatio = Spring.DampingRatioLowBouncy,
        stiffness = Spring.StiffnessMediumLow,
    )
}
```

I lean toward spring-based motion over fixed-duration tweens for these — springs feel physical and handle interruptions gracefully when a user taps back mid-animation. A few practical calibrations from shipping these:

- **Keep it fast.** 300–400ms of perceived motion is plenty. A luxurious 800ms transition is delightful once and irritating by the tenth tap.
- **Match content scaling.** If the thumbnail is `ContentScale.Crop` and the header is `ContentScale.Fit`, the image visibly jumps as scaling changes mid-flight. Use consistent scaling or a `resizeMode` that interpolates cleanly.
- **Handle the placeholder gap.** While the shared element is in flight, its slot on the origin screen is empty. Provide a `placeholderMemoryCacheKey` or a background so you don't flash a hole in the grid.

## The performance and correctness caveats

Shared element transitions do real work per frame — measuring and drawing an element as its bounds change — so they're subject to the same rules as any animation in Compose. If the screens involved are already recomposing more than they should, the transition amplifies the jank. Before adding one to a heavy screen, make sure you've handled the fundamentals covered in [Compose performance, stability, and recomposition](https://blog.michaelsam94.com/compose-performance-stability-recomposition/); a transition layered over an unstable, over-recomposing list will stutter, and users will blame the animation rather than the underlying churn.

Two more honest limitations. First, transitions between elements that differ *a lot* in aspect ratio or content rarely look good no matter how you tune them — sometimes a plain fade is the better design choice, and knowing when *not* to animate is part of the craft. Second, accessibility: a transition is decorative motion, so respect the system "remove animations" setting and make sure the destination is fully usable if the animation is skipped entirely.

## Is it worth adding?

For list-to-detail flows, media galleries, and anything with a clear "this expands into that" relationship, absolutely — it's now a native, stable capability rather than a hack, and it materially raises the perceived quality of an app. The effort is modest once you internalize the scope-plus-key model. Where I'd hold back is decorative transitions between unrelated screens; motion should reinforce a spatial relationship the user already perceives, not manufacture one. Used with that restraint, shared element transitions are one of the highest-leverage polish features in modern Compose.

## Resources

- [Shared element transitions — Android docs](https://developer.android.com/develop/ui/compose/animation/shared-elements)
- [Compose animation overview](https://developer.android.com/develop/ui/compose/animation/introduction)
- [Material motion guidelines](https://m3.material.io/styles/motion/overview)
- [AndroidX Compose animation source](https://github.com/androidx/androidx/tree/androidx-main/compose/animation)
- [Now in Android sample app](https://github.com/android/nowinandroid)
