---
title: "Custom Gestures in Compose with pointerInput"
slug: "compose-gesture-detection-pointerinput"
description: "Build custom gestures in Jetpack Compose with pointerInput: detectDragGestures, awaitPointerEventScope, consuming events, and getting the keys right."
datePublished: "2024-09-10"
dateModified: "2024-09-10"
tags: ["Android", "Jetpack Compose", "Gestures", "UI"]
keywords: "pointerInput, Compose gestures, detectDragGestures, awaitPointerEventScope, awaitFirstDown, Compose custom gesture"
faq:
  - q: "How do custom gestures work in Jetpack Compose?"
    a: "You attach a Modifier.pointerInput block and use gesture detectors like detectDragGestures, detectTapGestures, or the low-level awaitPointerEventScope loop to read raw pointer events. Inside these you decide when to consume an event, which stops parents and siblings from also handling it, giving you full control over drag, tap, and multi-touch behavior."
  - q: "What is the key parameter in pointerInput for?"
    a: "The pointerInput key controls when the gesture coroutine restarts. If you capture a value inside the block, that value is frozen at the time the block launched, so you must pass it as a key or the gesture will use a stale value. Passing Unit means it never restarts; pass any state the gesture logic depends on so it relaunches when that state changes."
  - q: "When should I consume a pointer event in Compose?"
    a: "Consume an event with change.consume() once your gesture has claimed the pointer, so ancestors and siblings stop reacting to it. Consuming during a drag prevents a parent scroll container from stealing the gesture. Do not consume events you did not handle, or you will break scrolling and clicks for other components."
---

Custom gestures in Compose start and end with `Modifier.pointerInput`. Inside that block you either use a ready-made detector — `detectTapGestures`, `detectDragGestures`, `detectTransformGestures` — or drop into the raw `awaitPointerEventScope` loop when you need behavior the detectors don't cover. The two things that separate working gesture code from mysteriously broken gesture code are getting the `pointerInput` *key* right and knowing exactly when to *consume* an event. I've debugged both failures more times than I'd like, so let me make them concrete.

## The detectors cover most cases

Before hand-rolling anything, know that the built-in detectors handle the vast majority of real needs. Drag with velocity, tap variants (tap, double-tap, long-press), and pinch/rotate/pan are all one function call.

```kotlin
Modifier.pointerInput(Unit) {
    detectDragGestures(
        onDragStart = { offset -> /* pointer down */ },
        onDrag = { change, dragAmount ->
            change.consume()
            offsetX += dragAmount.x
            offsetY += dragAmount.y
        },
        onDragEnd = { /* released */ },
    )
}
```

`detectTapGestures` similarly gives you `onTap`, `onDoubleTap`, `onLongPress`, and `onPress` (which suspends so you can await release for press-and-hold effects). Reach for these first; the raw loop is for when they genuinely can't express what you need.

## The key parameter is not optional thinking

`pointerInput(key)` launches a coroutine that runs your gesture logic. That coroutine captures whatever variables are in scope *at launch time* and does not see later changes unless the coroutine restarts. It restarts only when a key changes. So if your gesture logic depends on some state, that state must be a key — otherwise you get a stale-closure bug where the gesture behaves as if the value never changed.

```kotlin
// BUG: gesture always uses the isEnabled value from first composition
Modifier.pointerInput(Unit) {
    detectTapGestures { if (isEnabled) doThing() }
}

// CORRECT: relaunch when isEnabled changes
Modifier.pointerInput(isEnabled) {
    detectTapGestures { if (isEnabled) doThing() }
}
```

`pointerInput(Unit)` is fine — even preferable — when the block reads only stable references (a `remember`ed `Animatable`, a lambda you don't recreate). But the moment the logic branches on changing state, that state belongs in the key. This single rule accounts for most "my gesture ignores the new value" reports.

## Consuming events: who wins the pointer

A touch travels through a tree of potentially interested handlers — your draggable card sits inside a scrollable list inside a pager. Compose resolves conflicts through *consumption*: when a handler calls `change.consume()`, it signals "I've claimed this pointer," and other handlers see it as consumed and back off.

The practical rules:

- **Consume once you've committed** to the gesture. In a drag, consume in `onDrag` so the parent scroll container doesn't also scroll.
- **Don't consume what you didn't handle.** If you consume every down event "just in case," you break taps and scrolls for everything underneath.
- **Check `isConsumed`** in the raw loop before acting, so you cooperate with handlers that ran first.

Getting this wrong is why "my custom drag also scrolls the list" happens — you didn't consume, so both reacted.

## The raw loop for full control

When you need something the detectors don't offer — a custom swipe-to-reveal with thresholds, a gesture that behaves differently after a delay, multi-pointer logic — use `awaitPointerEventScope`:

```kotlin
Modifier.pointerInput(Unit) {
    awaitPointerEventScope {
        while (true) {
            val down = awaitFirstDown(requireUnconsumed = true)
            var totalDrag = 0f
            do {
                val event = awaitPointerEvent()
                val change = event.changes.first()
                totalDrag += change.positionChange().x
                if (totalDrag > touchSlop) {
                    change.consume()
                    // now we own the gesture
                }
            } while (event.changes.any { it.pressed })
            // pointer up: decide based on totalDrag
        }
    }
}
```

The pattern is: `awaitFirstDown` to detect the touch, loop with `awaitPointerEvent` to track movement, apply your own touch slop before committing, and consume once you commit. `requireUnconsumed = true` on the down means you only start if nobody upstream already claimed it. This loop is verbose but it's the full expressive power of the gesture system — everything the detectors do is built on top of it.

## Respect touch slop

A tap that moves two pixels shouldn't register as a drag; that's what *touch slop* is for — the small movement threshold before a drag "starts." The detectors apply it automatically. In the raw loop you apply it yourself using `viewConfiguration.touchSlop`, as in the example above. Skipping slop makes your gesture feel twitchy, firing drags on what the user intended as taps. It's a small detail that has an outsized effect on how solid the interaction feels.

## Coordinating with Animatable

Gesture code that produces motion almost always pairs with `Animatable` for the release behavior — snap back, fling, settle. You `snapTo` during the drag and `animateTo`/`animateDecay` on release, which cancels cleanly if a new gesture starts. That combination, covered in the [Compose animation API overview](https://blog.michaelsam94.com/compose-animation-apis-overview/), is the standard shape of interactive motion: raw pointer events feed positions in, `Animatable` produces smooth motion out.

## A decision guide

| Need | Use |
| --- | --- |
| Tap / double-tap / long-press | `detectTapGestures` |
| Drag with velocity | `detectDragGestures` |
| Pinch / zoom / rotate / pan | `detectTransformGestures` |
| Thresholds, multi-touch logic, custom | `awaitPointerEventScope` loop |
| Simple clicks | `Modifier.clickable` (not `pointerInput`) |

Note the last row: for a plain click, use `Modifier.clickable`, which also handles accessibility, ripple, and focus. Don't reimplement clicks with `pointerInput` — you'll lose all of that.

## What I'd take away

`pointerInput` is the gateway to every gesture in Compose, but you should exhaust the built-in detectors before writing a raw loop. When you do write custom logic, two disciplines dominate correctness: put any changing state the gesture depends on into the `pointerInput` key so you don't capture stale values, and consume events precisely — after you commit, never for events you didn't handle — so you cooperate with scroll containers and siblings. Apply touch slop for a solid feel, pair the raw positions with `Animatable` for release motion, and leave plain clicks to `Modifier.clickable`. Nail the key and the consumption model and gestures stop being mysterious.

## Resources

- [Handle user input / gestures in Compose](https://developer.android.com/develop/ui/compose/touch-input/pointer-input)
- [Drag, swipe, and fling](https://developer.android.com/develop/ui/compose/touch-input/pointer-input/drag-swipe-fling)
- [Understand gestures](https://developer.android.com/develop/ui/compose/touch-input/pointer-input/understand-gestures)
- [pointerInput API reference](https://developer.android.com/reference/kotlin/androidx/compose/ui/input/pointer/package-summary)
