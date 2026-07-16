---
title: "The Jetpack Compose Animation APIs, Mapped"
slug: "compose-animation-apis-overview"
description: "A practical map of the Jetpack Compose animation APIs: animate*AsState, updateTransition, AnimatedVisibility, Animatable, and when to reach for each one."
datePublished: "2024-09-05"
dateModified: "2024-09-05"
tags: ["Android", "Jetpack Compose", "Animation", "UI"]
keywords: "Compose animation, animateAsState, updateTransition, AnimatedVisibility, Animatable, animateContentSize"
faq:
  - q: "Which Compose animation API should I use for a single value?"
    a: "Use animate*AsState (animateFloatAsState, animateColorAsState, animateDpAsState) when a single value should animate toward a target driven by state. It is declarative and fire-and-forget: you change the target and Compose animates the transition. Reach for Animatable only when you need to launch, cancel, or coordinate the animation manually in a coroutine."
  - q: "What is the difference between updateTransition and animate*AsState?"
    a: "animate*AsState animates one value independently. updateTransition coordinates multiple values off a single state change so they share timing and finish together, and it lets you inspect the transition for tooling and previews. Use a transition when several properties should animate in lockstep from one state to another."
  - q: "When should I use Animatable instead of the higher-level APIs?"
    a: "Use Animatable when you need imperative control: gesture-driven motion, velocity-based fling, cancelling an in-flight animation, or sequencing several animations in a coroutine. The declarative animate*AsState and Transition APIs cover most UI, but drag-and-release and physics interactions need Animatable's snapTo, animateTo, and animateDecay."
---

Compose gives you roughly six animation APIs, and the reason animation confuses newcomers is that several of them can do the same job — but only one is the *right* fit for a given case. The short version: use `animate*AsState` for a single value driven by state, `updateTransition` when multiple values must move together, `AnimatedVisibility` and `AnimatedContent` for enter/exit and content swaps, and drop to `Animatable` only when you need imperative, gesture-driven, or cancellable control. Everything else is a variation on those.

I've watched teams reach for `Animatable` and a `LaunchedEffect` to animate a single color, then wonder why the code is fragile. Ninety percent of UI animation is declarative and should be. Here's the map I hand to people onboarding onto a Compose codebase.

## animate*AsState: one value, fire and forget

This is the workhorse. You have a target value that depends on state, and you want it to animate smoothly whenever the target changes. You don't manage the animation at all — you just declare the target.

```kotlin
val elevation by animateDpAsState(
    targetValue = if (pressed) 8.dp else 2.dp,
    animationSpec = tween(150),
    label = "cardElevation",
)
```

There's a typed variant for the common types: `animateFloatAsState`, `animateColorAsState`, `animateDpAsState`, `animateOffsetAsState`, and `animateValueAsState` for anything with a `TwoWayConverter`. If you're animating exactly one property in response to a state flip, this is the answer. Pass a `label` — it powers the Animation Preview inspector in Android Studio and costs nothing.

## updateTransition: many values, one source of truth

The moment you need *several* properties to animate off the *same* state change — say a card that simultaneously changes color, elevation, and corner radius when selected — independent `animate*AsState` calls drift out of sync and clutter the composable. `updateTransition` fixes this: one transition object, driven by your state, spawns child animations that share timing.

```kotlin
val transition = updateTransition(selected, label = "cardSelection")

val color by transition.animateColor(label = "color") { s ->
    if (s) primaryContainer else surface
}
val corner by transition.animateDp(label = "corner") { s ->
    if (s) 4.dp else 16.dp
}
val scale by transition.animateFloat(label = "scale") { s ->
    if (s) 1.02f else 1f
}
```

The payoff beyond tidiness: the whole transition is inspectable in tooling, you can specify per-property specs off one enum, and everything finishes coherently. Whenever I catch three `animate*AsState` calls keyed on the same boolean, I refactor to a transition.

## AnimatedVisibility and AnimatedContent

For things entering and leaving the composition, `AnimatedVisibility` animates the appearance and disappearance with `enter`/`exit` specs:

```kotlin
AnimatedVisibility(
    visible = isExpanded,
    enter = expandVertically() + fadeIn(),
    exit = shrinkVertically() + fadeOut(),
) {
    DetailPanel()
}
```

When the content itself *changes* — a counter, a swapped screen, a loading→loaded transition — use `AnimatedContent`, which cross-fades between old and new and lets you define directional transitions. It's the subject worth its own deep-dive on [content transitions and AnimatedContent](https://blog.michaelsam94.com/compose-animated-content-transitions/), because the `transitionSpec` and `SizeTransform` details are where it gets interesting.

## animateContentSize: the one-liner that earns its keep

If you only need a container to smoothly resize when its content grows or shrinks — an expandable card, a text field that reveals a helper line — `Modifier.animateContentSize()` is a single modifier that does exactly that. No state, no spec wrangling:

```kotlin
Column(
    Modifier
        .fillMaxWidth()
        .animateContentSize(),
) {
    Text(summary)
    if (expanded) Text(fullBody)
}
```

I reach for this constantly. It's the highest ratio of polish to effort in the whole animation surface.

## Animatable: imperative control when you need it

Everything above is declarative — you set a target, Compose animates. But some interactions are inherently imperative: a draggable sheet that flings on release, a swipe-to-dismiss card, a value you must `snapTo` instantly and then `animateTo` later. That's `Animatable`.

```kotlin
val offsetX = remember { Animatable(0f) }
val scope = rememberCoroutineScope()

Modifier.pointerInput(Unit) {
    detectHorizontalDragGestures(
        onHorizontalDrag = { _, delta ->
            scope.launch { offsetX.snapTo(offsetX.value + delta) }
        },
        onDragEnd = {
            scope.launch { offsetX.animateTo(0f, spring()) }
        },
    )
}
```

`Animatable` gives you `snapTo` (instant), `animateTo` (animated), `animateDecay` (fling with velocity), and cancellation — launching a new `animateTo` cancels the in-flight one, which is exactly what gesture code needs. If you're wiring custom gestures, this pairs naturally with [pointerInput gesture detection](https://blog.michaelsam94.com/compose-gesture-detection-pointerinput/).

## Picking the right one

| You want to... | Use |
| --- | --- |
| Animate one value from state | `animate*AsState` |
| Animate several values in sync | `updateTransition` |
| Animate enter/exit | `AnimatedVisibility` |
| Animate a content swap | `AnimatedContent` |
| Smoothly resize a container | `Modifier.animateContentSize` |
| Gesture / fling / cancellable | `Animatable` |

## Specs matter as much as the API

Whichever API you pick, the `animationSpec` decides how it *feels*. `tween` gives you duration and easing for deterministic motion. `spring` gives you physics — `dampingRatio` and `stiffness` — and it's what makes motion feel natural, because it responds to interruptions gracefully instead of restarting. My default is a `spring` with medium bounce for interactive elements and a short `tween` for state-driven color and elevation. Avoid long durations; anything over ~300ms on a tap response feels sluggish. Motion should confirm an interaction, not delay it.

## What I'd take away

Start declarative and stay there as long as you can. A single value gets `animate*AsState`; several coordinated values get `updateTransition`; appearance and content swaps get `AnimatedVisibility` and `AnimatedContent`; a resizing container gets `animateContentSize`. Only drop to `Animatable` when the interaction is genuinely imperative — gestures, flings, cancellation. Match the spec to the feel, keep durations short, and always pass a `label` so the tooling can help you. Knowing which of the six to reach for is most of the skill; the APIs themselves are small.

## Resources

- [Animations in Compose (Android developers)](https://developer.android.com/develop/ui/compose/animation/introduction)
- [Choose an animation API](https://developer.android.com/develop/ui/compose/animation/choose-api)
- [Value-based animations (animate*AsState, Transition)](https://developer.android.com/develop/ui/compose/animation/value-based)
- [Customize animations and specs](https://developer.android.com/develop/ui/compose/animation/customize)
