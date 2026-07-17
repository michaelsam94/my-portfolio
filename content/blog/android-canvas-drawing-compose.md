---
title: "Custom Drawing with Compose Canvas: Paths, Layers, and Performance"
slug: "android-canvas-drawing-compose"
description: "Draw custom graphics in Jetpack Compose with the Canvas API: DrawScope, paths, gradients, blend modes, and keeping draw off the recomposition path for smooth 60fps."
datePublished: "2024-08-03"
dateModified: "2024-08-03"
tags: ["Android", "Jetpack Compose", "Graphics", "Performance"]
keywords: "Compose Canvas, DrawScope, custom drawing Compose, drawWithCache, Compose Path, Canvas performance Compose"
faq:
  - q: "How do I do custom drawing in Jetpack Compose?"
    a: "Use the Canvas composable or a drawBehind/drawWithContent modifier, which give you a DrawScope with primitives like drawLine, drawPath, drawRect, and drawCircle plus transforms. You draw imperatively inside that scope while the surrounding UI stays declarative, which is ideal for charts, progress indicators, and custom shapes."
  - q: "What is the difference between drawBehind and drawWithCache?"
    a: "drawBehind runs your drawing lambda on every draw pass. drawWithCache lets you allocate and remember expensive objects — Paths, Brushes, Shaders — once and only rebuild them when inputs change, then draw them cheaply each frame. Use drawWithCache whenever you'd otherwise recreate objects inside the draw lambda."
  - q: "How do I keep Compose custom drawing performant?"
    a: "Read animating state inside the draw phase using lambda parameters so drawing updates without triggering recomposition, cache Path and Brush objects with drawWithCache, avoid allocations inside DrawScope, and prefer drawing over stacking many composables for graphics-heavy UI. Profile with the layout inspector and frame metrics to confirm you're not recomposing per frame."
---

Compose's `Canvas` is the escape hatch for anything the standard components can't express — custom charts, progress rings, signature pads, waveform visualizers, game-ish UI. The key insight that separates smooth custom drawing from janky custom drawing is that `DrawScope` runs in the *draw* phase, not the composition phase, and if you're disciplined about keeping state reads and object allocation in the right place, you can animate complex graphics at 60fps without recomposing anything. I've built financial charts and an ink surface on this API, and every performance problem I hit traced back to doing draw-phase work in the composition phase, or vice versa.

## DrawScope: imperative drawing inside declarative UI

The `Canvas` composable (and the `drawBehind`/`drawWithContent` modifiers) hand you a `DrawScope` — a coordinate space with the current size and a set of primitives:

```kotlin
Canvas(modifier = Modifier.size(120.dp)) {
    // 'this' is DrawScope: size, center, and draw* primitives are in scope.
    drawArc(
        color = Color(0xFF3DDC84),
        startAngle = -90f,
        sweepAngle = 270f * progressFraction,
        useCenter = false,
        style = Stroke(width = 12.dp.toPx(), cap = StrokeCap.Round),
    )
}
```

Inside `DrawScope` you have `drawLine`, `drawRect`, `drawRoundRect`, `drawCircle`, `drawArc`, `drawPath`, `drawImage`, and text via `drawText`. You also get transforms (`rotate`, `scale`, `translate`, `clipRect`, `clipPath`) that compose with `withTransform` for grouped operations. It's a genuine 2D drawing API — the same conceptual surface as the classic `android.graphics.Canvas`, but integrated with Compose's state and units (`.toPx()` because DrawScope is in pixels).

## The three phases, and why draw is special

Compose runs composition → layout → draw. Recomposition is expensive; drawing is comparatively cheap. The mistake that kills custom-drawing performance is animating a value that's read during *composition*, so every frame recomposes the composable, re-runs layout, then draws — when all you needed was to redraw.

The fix is to read animating state in the draw phase. When your draw depends on an animation, pass it so the read happens inside the draw lambda:

```kotlin
val sweep by animateFloatAsState(if (done) 1f else 0f, label = "sweep")

// drawBehind's lambda runs in the draw phase; reading `sweep` here
// invalidates only draw, not composition/layout.
Box(Modifier.size(120.dp).drawBehind {
    drawArc(brandGreen, -90f, 270f * sweep, false,
        style = Stroke(12.dp.toPx(), cap = StrokeCap.Round))
})
```

That single discipline — "read animating state inside the draw block" — is the difference between a progress ring that recomposes 60 times a second and one that only redraws. It's the drawing-phase cousin of the lambda-progress trick that keeps [Lottie and other animations](https://blog.michaelsam94.com/android-lottie-compose-animations/) off the recomposition path.

## drawWithCache: allocate once, draw many

Objects like `Path`, `Brush` (gradients), and `PathEffect` are relatively expensive to build. Building them inside a per-frame draw lambda allocates garbage every frame and stutters. `drawWithCache` solves this: the outer block builds and remembers objects, keyed on inputs, and only the inner `onDrawBehind` runs each frame.

```kotlin
Modifier.drawWithCache {
    // Built once, rebuilt only when size changes.
    val gradient = Brush.verticalGradient(
        listOf(Color(0xFF1E88E5), Color(0xFF1565C0)),
        endY = size.height,
    )
    val path = buildChartPath(dataPoints, size)   // expensive
    onDrawBehind {
        drawPath(path, gradient)                    // cheap, every frame
    }
}
```

Rule of thumb: if you find yourself constructing a `Path` or `Brush` inside a plain `drawBehind`, move it into `drawWithCache`. Your allocations drop and your frames get consistent.

## Paths, gradients, and blend modes

The expressive power comes from combining these:

- **Paths** build arbitrary shapes with `moveTo`/`lineTo`/`cubicTo`/`quadraticBezierTo`. For charts, build a smooth line with cubic segments; for a signature pad, append points as you receive them.
- **Brushes** give linear, radial, and sweep gradients — pass a `Brush` anywhere a `Color` is accepted.
- **Blend modes** (`drawRect(..., blendMode = BlendMode.Multiply)`) let you do highlights, masks, and lighting effects. They can trigger offscreen compositing, so use them where they matter and profile.
- **Clipping** with `clipPath`/`clipRect` constrains drawing to a region — essential for progress fills and reveal effects.

For a concrete pattern: a donut chart is a series of `drawArc` calls with `Stroke` caps sharing a center; a gradient area chart is a filled `Path` painted with a vertical `Brush`, clipped to the plot area.

## When to draw vs when to compose

Not everything should be a Canvas. The heuristic:

| Use composables | Use Canvas |
|---|---|
| Discrete, interactive elements | Continuous or freeform graphics |
| Text, standard shapes, layouts | Charts, gauges, waveforms, ink |
| A handful of items | Many primitives per frame |
| Accessibility matters per element | Decorative or holistically-described visuals |

The trap is drawing dozens of interactive items on one Canvas and then hand-rolling hit testing and accessibility. If elements need clicks and semantics, they probably want to be composables. If it's a dense visualization, Canvas wins — but then supply a single meaningful `contentDescription` for the whole thing, because individual drawn primitives are invisible to TalkBack.

## Performance checklist

Before shipping graphics-heavy drawing, I run through:

- **No allocations in the hot draw path** — `Path`, `Brush`, `Paint` cached via `drawWithCache`.
- **Animating state read in the draw phase**, not composition.
- **Heavy geometry precomputed** off the frame path when data changes, not every frame.
- **Blend modes and offscreen layers minimized**; verify with GPU overdraw and the profiler.
- **Text drawn via `drawText` with a remembered `TextMeasurer`**, not measured per frame.

## What I'd take away

Compose Canvas is a full 2D drawing API, and using it well is almost entirely about phase discipline: keep object allocation in `drawWithCache`, keep animating reads inside the draw block, and precompute heavy geometry when inputs change rather than per frame. Reach for it when content is continuous or freeform and stick with composables when elements are discrete and interactive. Get the phases right and you can animate rich custom graphics at a steady 60fps; get them wrong and even a simple progress ring will recompose your whole screen into a slideshow.

## Hardware layer for path animation

Animated `drawPath` without `Modifier.graphicsLayer` recomposes entire tree — promote Canvas to layer during stroke animation. Large paths: simplify with `PathMeasure` segments to cap draw calls per frame.

## Touch slop vs draw precision

Stylus apps need `MotionEvent.getHistorical` points for smooth curves — standard drag only samples per frame and looks jagged on 120Hz displays.

## Canvas Drawing Compose Supplement 0 on Samsung and Pixel divergence

Exercise canvas drawing compose supplement 0 on Galaxy A-series and Pixel a-series — emulators hide OEM battery and storage quirks. Capture Macrobenchmark or Firebase trace for the critical path touching canvas; regressions above 8% block release for `android-canvas-drawing-compose-supplement-0`.

Document permission and background behavior in internal runbook: what breaks under Doze, what requires foreground service, and what Play policy declarations apply. Support tickets referencing "Canvas Drawing Compose Supplement 0" should map to a single runbook section with known workarounds.

## Compose regression gates for Play Vitals

Before promoting `android-canvas-drawing-compose-supplement-0` changes past 20% rollout, compare ANR rate, slow cold start, and excessive wakeups against seven-day baseline. Fail rollback review if 0 path shows >5% increase in `slow frames` without documented trade-off approval.

## Field testing canvas with battery saver enabled

Xiaomi and Oppo ship aggressive background killers. After implementing canvas drawing compose supplement 0, run 24-hour monkey test on three OEM devices with battery saver enabled. Failures here predict one-star reviews that Crashlytics never captures — especially for 0 flows that assume reliable background delivery.

## Resources

- [Graphics in Compose — Canvas and DrawScope](https://developer.android.com/develop/ui/compose/graphics/draw/overview)
- [DrawScope reference](https://developer.android.com/reference/kotlin/androidx/compose/ui/graphics/drawscope/DrawScope)
- [Modifier.drawWithCache](https://developer.android.com/reference/kotlin/androidx/compose/ui/draw/package-summary#(androidx.compose.ui.Modifier).drawWithCache(kotlin.Function1))
- [Compose phases (composition, layout, draw)](https://developer.android.com/develop/ui/compose/phases)
- [Brush and gradients in Compose](https://developer.android.com/develop/ui/compose/graphics/draw/brush)
