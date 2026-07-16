---
title: "Stylus and Handwriting Input on Android: Low-Latency Ink and Scribble"
slug: "android-stylus-handwriting-input"
description: "Build stylus and handwriting input on Android with low-latency ink, MotionEvent history, palm rejection, and Scribble handwriting-to-text in text fields."
datePublished: "2024-07-26"
dateModified: "2024-07-26"
tags: ["Android", "Jetpack Compose", "Stylus", "Input"]
keywords: "Android stylus input, handwriting to text Android, low latency ink, Scribble Android, MotionEvent stylus, palm rejection"
faq:
  - q: "How do I reduce latency when drawing with a stylus on Android?"
    a: "Use the low-latency graphics libraries in Jetpack (androidx.graphics.lowlatency) with a front-buffered rendering layer so strokes render ahead of the normal frame pipeline. Also consume the batched historical points inside each MotionEvent instead of only the latest coordinate, and predict the next point with the motion prediction library to hide the last few milliseconds of lag."
  - q: "What is Scribble on Android and how do I support it?"
    a: "Scribble lets users write by hand directly into a text field with a stylus, and the system converts the ink to text. Standard EditText and Compose text fields get it largely for free on Android 14+ when the stylus handwriting feature is enabled, but you should test focus behavior and set the correct input types so the handwriting delegate targets the right field."
  - q: "How do you implement palm rejection for stylus drawing?"
    a: "Branch on MotionEvent.getToolType for each pointer and treat only TOOL_TYPE_STYLUS as drawing input, ignoring TOOL_TYPE_FINGER while a stylus is active. Track pointer IDs so a resting palm reported as a separate finger pointer never starts or corrupts a stroke."
---

If you want stylus input on Android to feel like a real pen, the two things that matter most are latency and palm rejection — and both are solved by APIs most teams never reach for. Low-latency ink comes from the `androidx.graphics.lowlatency` front-buffered rendering layer plus consuming the *historical* points inside each `MotionEvent`, and palm rejection comes from branching on `MotionEvent.getToolType`. Handwriting-to-text is a separate concern handled by Scribble, which text fields get mostly for free on recent Android. I've shipped a note-taking surface built on exactly these pieces, and the difference between "laggy toy" and "feels like paper" is entirely in the input handling, not the UI.

## The latency problem, and where it hides

The default touch pipeline batches input, hands it to your view once per frame, and composites it a frame or two later. For a button that's invisible. For a pen that's tracing a line your eye is following, 40–60ms of lag reads as the ink "chasing" the nib. Users describe it as feeling cheap without being able to say why.

Two levers close most of that gap:

- **Historical samples.** A single `MotionEvent` of type `ACTION_MOVE` usually carries several coordinates, not one — the digitizer samples faster than the display refreshes. If you only read `event.x`/`event.y` you throw away the intermediate points and your stroke looks polygonal and laggy. Walk the history.
- **Front-buffered rendering.** The Jetpack low-latency library lets you draw the *current* stroke straight to a front buffer that skips most of the normal frame pipeline, then commit it to the main scene when the stroke ends.

Here's the historical-sample loop, which is the cheapest win and works even before you adopt front buffering:

```kotlin
override fun onTouchEvent(event: MotionEvent): Boolean {
    if (event.getToolType(0) != MotionEvent.TOOL_TYPE_STYLUS) return false
    when (event.actionMasked) {
        MotionEvent.ACTION_MOVE -> {
            // Replay every batched sample, not just the latest coordinate.
            for (h in 0 until event.historySize) {
                path.lineTo(event.getHistoricalX(h), event.getHistoricalY(h))
            }
            path.lineTo(event.x, event.y)
            invalidate()
        }
    }
    return true
}
```

## Front-buffered rendering for real ink

Once history is in, the next tier is `GLFrontBufferedRenderer` (or the Canvas-based variant). You register a callback that draws the *wet* stroke — the segment being actively drawn — to a front buffer, and a second callback that redraws committed strokes to the double-buffered scene when the gesture completes. The mental model: the front buffer is your scratch layer for the current stroke, the main buffer is the finished drawing.

The payoff is that the wet stroke renders essentially as fast as the panel can push pixels, decoupled from your app's normal rendering. Pair it with the **motion prediction** library (`androidx.input.motionprediction`), which extrapolates where the pen is heading, and you visually erase the last chunk of latency. Prediction is a guess, so you render predicted points on the front buffer only and discard them the instant a real sample arrives — never commit a prediction to the permanent drawing.

## Palm rejection is a tool-type check, not ML

People assume palm rejection needs a heuristic model. On Android it's mostly a branch. Every pointer in a `MotionEvent` reports a tool type, and a resting palm shows up as `TOOL_TYPE_FINGER` (or an unusually large touch major). The rule I use:

1. While any active pointer is `TOOL_TYPE_STYLUS`, ignore all `TOOL_TYPE_FINGER` pointers for drawing.
2. Key strokes by `pointerId` so a palm that lands mid-stroke as a new pointer can't hijack the path.
3. Optionally, when a stylus is present, still let finger gestures do *pan and zoom* — just not draw. Users expect to rest their hand and scroll with a finger.

That third point is the one teams miss. Blanket-ignoring fingers breaks two-finger pan. Route by tool type *and* intent instead of throwing all touch away.

## Pressure, tilt, and orientation

A pen that only records position feels flat. The digitizer also gives you `getPressure`, `getAxisValue(AXIS_TILT)`, and orientation. Map pressure to stroke width and you get natural line weight; map tilt to a shading falloff and you get a passable pencil. Cache a small ring buffer of recent widths and smooth them, because raw pressure is noisy and unsmoothed width makes strokes look ropey. This is the same "smooth the signal before you trust it" discipline that shows up all over UI work, like taming raw gesture velocity.

## Scribble: handwriting straight into text fields

Drawing is one axis; the other is turning handwriting into text. Scribble (stylus handwriting) lets a user write by hand *inside a text field* and the system converts ink to characters. The good news: on Android 14+ with the feature enabled, standard `EditText` and Compose `TextField`/`BasicTextField` support it largely automatically. Your job is mostly to not break it:

- Set correct `inputType` / keyboard options so the handwriting engine knows it's an email, number, or free text.
- Make sure the field is genuinely focusable and not covered by an overlapping touch target that eats the stylus down event.
- For custom editors, wire up the handwriting delegate APIs so writing near the field starts a handwriting session that targets it.

The subtle bug I hit: a decorative `Box` with a click handler sat on top of the text field's hit area, so the stylus-down started a handwriting gesture on the wrong element. Test handwriting entry on *every* field, not just the obvious search box.

## Putting it together

A production stylus surface layers cleanly:

| Concern | API / approach |
|---|---|
| Kill polygonal, laggy strokes | Consume `MotionEvent` history |
| Minimize wet-stroke latency | `GLFrontBufferedRenderer` front buffer |
| Hide residual lag | `androidx.input.motionprediction` |
| Reject palms, keep pan/zoom | Branch on `getToolType`, key by pointer id |
| Natural line weight | Pressure + tilt, smoothed |
| Handwriting to text | Scribble / handwriting delegate |

Structure the code so the input layer is dumb and fast and the document model is separate. When I built this on top of a [Compose canvas drawing surface](https://blog.michaelsam94.com/android-canvas-drawing-compose/), keeping the wet-stroke path independent from the committed drawing model made both the low-latency layer and undo/redo far simpler to reason about.

## What I'd tell my past self

Start with historical samples and tool-type palm rejection — they're an afternoon of work and fix 80% of the "feels cheap" complaints. Add front buffering and prediction only once the basics are solid, because they add real complexity. And test Scribble on hardware with an actual pen; the emulator will lie to you about handwriting sessions and focus. The APIs are all there and stable; the craft is in wiring them together so the pen feels like it's touching glass, not driving a marionette.

## Resources

- [Add stylus support to your app (Android)](https://developer.android.com/develop/ui/views/touch-and-input/stylus-input)
- [Low-latency graphics with front-buffered rendering](https://developer.android.com/develop/ui/views/graphics/low-latency-graphics)
- [Motion prediction library](https://developer.android.com/jetpack/androidx/releases/input)
- [Stylus handwriting (Scribble)](https://developer.android.com/develop/ui/views/touch-and-input/stylus-input/stylus-handwriting)
- [MotionEvent reference](https://developer.android.com/reference/android/view/MotionEvent)
