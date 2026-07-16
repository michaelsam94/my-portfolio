---
title: "Real-Time Blur on Android with RenderEffect"
slug: "android-render-effect-blur"
description: "Implement real-time blur on Android with RenderEffect and Compose graphicsLayer: hardware-accelerated BlurEffect, performance costs, and fallbacks for pre-Android 12."
datePublished: "2024-08-06"
dateModified: "2024-08-06"
tags: ["Android", "Jetpack Compose", "Graphics", "Performance"]
keywords: "Android RenderEffect blur, BlurEffect Compose, real time blur Android, Modifier.blur, hardware blur Android, frosted glass Android"
faq:
  - q: "How do I blur a view or composable on Android?"
    a: "On Android 12+ use RenderEffect.createBlurEffect for Views, or the Modifier.blur / graphicsLayer renderEffect APIs in Compose, which apply a hardware-accelerated Gaussian blur on the GPU. These run in real time because the blur happens on a render node rather than in software, unlike the old RenderScript approach."
  - q: "Why is my RenderScript blur slow or deprecated?"
    a: "RenderScript was deprecated because it ran blur largely on the CPU or through a compatibility path, making real-time blur expensive and janky. RenderEffect replaces it with a GPU-accelerated blur backed by the render pipeline, so blurring on scroll or animation is feasible on Android 12 and above."
  - q: "How do I blur backgrounds on devices older than Android 12?"
    a: "RenderEffect blur is API 31+, so on older devices fall back to a pre-blurred static asset, a translucent scrim instead of a live blur, or a downscaled bitmap blur used sparingly. Design the effect to degrade to a solid or translucent surface rather than attempting expensive live blur on unsupported hardware."
---

Real-time blur on Android finally became practical with `RenderEffect` on Android 12 (API 31), which runs a Gaussian blur on the GPU instead of the CPU-bound `RenderScript` path everyone suffered with before. In Compose it's exposed two ways — `Modifier.blur` for the simple case and `graphicsLayer { renderEffect = BlurEffect(...) }` for control — and in the View world it's `View.setRenderEffect(RenderEffect.createBlurEffect(...))`. The honest catch: it's API 31+, so any production use needs a deliberate fallback story for older devices. I've shipped frosted-glass sheets and blurred-behind dialogs with this, and the whole trick is knowing it's cheap on the GPU but not free, and planning the pre-12 path up front.

## Why RenderScript had to go

For years, "blur this background" meant `RenderScript` with `ScriptIntrinsicBlur`: allocate bitmaps, copy pixels, run the intrinsic, copy back. It worked, but it was expensive enough that live blur (blurring while content scrolled or animated) stuttered on anything but flagships, and it was awkward to keep in sync with a changing view. Google deprecated RenderScript, and the replacement is `RenderEffect`, which attaches the blur to the *render node* — the same GPU-backed layer that draws the content — so the blur is part of the hardware render pass rather than a separate software round-trip.

The practical upshot: blur that used to be a "capture a frame and blur it occasionally" hack is now something you can leave on continuously.

## The Compose APIs

The quick path is `Modifier.blur`:

```kotlin
Image(
    painter = wallpaper,
    contentDescription = null,
    modifier = Modifier
        .fillMaxSize()
        .blur(radius = 16.dp, edgeTreatment = BlurredEdgeTreatment.Rectangle),
)
```

`BlurredEdgeTreatment` matters: `Rectangle` clips the blur to bounds (sharp edges, good for a full-screen background), while `Unbounded` lets the blur bleed past edges (good for a blurred element floating over content). Getting this wrong gives you either a hard seam or unexpected fuzzy overflow.

For more control — combining blur with other layer transforms — go through `graphicsLayer`, which is the general mechanism the [GraphicsLayer API](https://blog.michaelsam94.com/android-graphics-layer-compose/) provides:

```kotlin
Box(
    Modifier.graphicsLayer {
        renderEffect = BlurEffect(
            radiusX = 20f, radiusY = 20f,
            edgeTreatment = TileMode.Decal,
        )
    }
) { BackgroundContent() }
```

Because it's a `graphicsLayer` property, you can animate the radius (blurring in a scrim as a sheet expands) and combine it with alpha or scale in the same layer.

## Views, if you're not all-Compose

Plenty of apps still have View screens. There the call is direct:

```kotlin
if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
    val blur = RenderEffect.createBlurEffect(24f, 24f, Shader.TileMode.CLAMP)
    backgroundView.setRenderEffect(blur)
} else {
    backgroundView.setRenderEffect(null)   // fall back to a scrim, see below
}
```

`setRenderEffect(null)` removes it. You can also chain effects with `RenderEffect.createChainEffect` (blur then color filter) for tinted frosted glass.

## The frosted-glass pattern

The effect people actually want is usually "frosted glass": a translucent, blurred panel over live content — a bottom sheet, a nav bar over a scrolling feed, a dialog scrim. The recipe:

1. Blur the *background* content (or a snapshot of it), not the panel.
2. Overlay a **semi-transparent tint** on top of the blur — pure blur alone looks muddy; a 30–50% surface tint gives it the glass quality and keeps foreground text legible.
3. Ensure adequate **contrast** for content on the glass. Blur reduces but doesn't guarantee legibility; test with busy backgrounds.

That tint-over-blur combination is what reads as "frosted" rather than "smudged," and it's the step most first attempts skip.

## Performance: cheap, not free

RenderEffect blur runs on the GPU, but it still costs. Things I keep in mind:

- **Radius scales cost.** A larger blur radius samples more; a 40dp blur costs more than 8dp. Use the smallest radius that reads as blurred.
- **It forces an offscreen buffer** sized to the blurred content. Blurring a small sheet is cheap; blurring a full-screen layer every frame during a scroll is the expensive case — profile it on a mid-range device, not just your flagship.
- **Prefer static when you can.** If the blurred content isn't changing (a paused background behind a modal), blur it once rather than re-blurring every frame. Live blur is for when the content genuinely moves.
- **Don't stack blurs.** Nested blurred layers multiply offscreen passes. One blur layer, tinted, is almost always enough.

## The fallback is the real design work

Because `RenderEffect` is API 31+, and depending on your `minSdk` a meaningful slice of users won't have it, decide the degraded experience deliberately:

| Situation | Fallback |
|---|---|
| Pre-Android 12 | Translucent scrim (solid color at ~40–60% alpha) instead of live blur |
| Static background (modal) | Ship or generate a pre-blurred bitmap once |
| Must-have blur look | Downscaled bitmap blur, used sparingly and cached |

The translucent scrim is the pragmatic default. Users on older devices get a clean, legible dimmed background; users on 12+ get the frosted glass. What you must not do is attempt heavy per-frame software blur on old hardware "to be consistent" — you'll tank exactly the devices that can least afford it. Design the effect so its *absence* still looks intentional.

## What I'd take away

Use `RenderEffect` (via `Modifier.blur`, `graphicsLayer` `renderEffect`, or `View.setRenderEffect`) for real-time blur on Android 12+ — it's the GPU-accelerated successor to the deprecated RenderScript path and it's finally fast enough for live use. Keep the radius modest, remember it forces an offscreen buffer so full-screen live blur needs profiling, and blur static content once instead of every frame. Layer a translucent tint over the blur for real frosted glass, and design a clean scrim fallback for pre-12 devices so the effect degrades gracefully instead of janking or vanishing.

## Resources

- [RenderEffect reference (Android)](https://developer.android.com/reference/android/graphics/RenderEffect)
- [Modifier.blur in Compose](https://developer.android.com/reference/kotlin/androidx/compose/ui/draw/package-summary#(androidx.compose.ui.Modifier).blur(androidx.compose.ui.unit.Dp,androidx.compose.ui.draw.BlurredEdgeTreatment))
- [RenderScript migration guidance](https://developer.android.com/guide/topics/renderscript/migrate)
- [Compose graphics modifiers](https://developer.android.com/develop/ui/compose/graphics/draw/modifiers)
- [View.setRenderEffect](https://developer.android.com/reference/android/view/View#setRenderEffect(android.graphics.RenderEffect))
