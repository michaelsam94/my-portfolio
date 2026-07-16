---
title: "Lottie Animations in Jetpack Compose Without Wrecking Performance"
slug: "android-lottie-compose-animations"
description: "Use Lottie in Jetpack Compose the right way: loading, caching, dynamic properties, controlling playback with progress, and avoiding jank from oversized JSON files."
datePublished: "2024-08-01"
dateModified: "2024-08-01"
tags: ["Android", "Jetpack Compose", "Animation", "Performance"]
keywords: "Lottie Compose, Lottie Android animation, LottieAnimation composable, dynamic properties Lottie, animateLottieComposition, Lottie performance"
faq:
  - q: "How do I play a Lottie animation in Jetpack Compose?"
    a: "Load the composition with rememberLottieComposition using a LottieCompositionSpec (raw resource, asset, URL, or file), then drive playback with animateLottieCompositionAsState and pass both into the LottieAnimation composable. This separates loading, progress, and rendering so you can control looping, speed, and clip range independently."
  - q: "Why is my Lottie animation causing jank?"
    a: "The usual culprits are oversized JSON with many layers, large embedded images, or heavy effects like masks and mattes that force expensive offscreen rendering. Ask the designer to simplify the animation, enable hardware acceleration or caching where appropriate, and avoid running many complex Lottie views simultaneously in a scrolling list."
  - q: "Can I change Lottie colors and text at runtime?"
    a: "Yes. Use dynamic properties with rememberLottieDynamicProperties to override color, opacity, or transform on specific layers matched by a KeyPath, and use text delegates to swap text. This lets one animation file adapt to theme colors or localized strings instead of shipping multiple variants."
---

Lottie in Compose is straightforward to get playing and easy to get wrong on performance. The correct mental model is that a Lottie animation has three separable concerns — *loading* the composition, *driving* its progress, and *rendering* it — and the Compose API (`rememberLottieComposition`, `animateLottieCompositionAsState`, `LottieAnimation`) maps one-to-one onto those. Most jank and most "why won't it loop right" bugs come from conflating them. I've shipped Lottie in onboarding flows, empty states, and success confirmations, and the pattern that keeps it smooth is the same every time: keep the file small, control progress explicitly, and never run heavy compositions in a scrolling list.

## The three-part API

Start by separating loading from playback. `rememberLottieComposition` handles async loading and caching; `animateLottieCompositionAsState` produces a progress float you can control; `LottieAnimation` just renders composition + progress:

```kotlin
@Composable
fun SuccessCheck(modifier: Modifier = Modifier) {
    val composition by rememberLottieComposition(
        LottieCompositionSpec.RawRes(R.raw.success_check)
    )
    val progress by animateLottieCompositionAsState(
        composition,
        iterations = 1,          // play once
        speed = 1.0f,
    )
    LottieAnimation(
        composition = composition,
        progress = { progress },   // lambda avoids recomposing on every frame
        modifier = modifier,
    )
}
```

One detail that matters for performance: pass `progress` as a lambda (`progress = { progress }`), not a value. The lambda form lets Compose read the animating float in the draw phase and skip recomposition on every frame — the same [deferred-read technique](https://blog.michaelsam94.com/adaptive-layouts-compose-grid-flexbox/) that keeps scroll and gesture animations off the recomposition hot path. Reading it as a plain value recomposes the whole composable 60+ times a second for nothing.

## Loading sources and caching

`LottieCompositionSpec` covers the sources you'll actually use:

- `RawRes` / `Asset` — bundled files, the common case.
- `Url` — remote animations; Lottie caches the parsed composition in memory and can cache the network response.
- `File` / `JsonString` — dynamic or downloaded content.

`rememberLottieComposition` caches by spec, so re-entering a screen doesn't re-parse. For remote animations, be deliberate: a Lottie URL is JSON that must be downloaded and parsed before anything renders, so show a placeholder while `composition` is null and treat a failed load as a normal error state, not a crash. Never block a screen's first paint on a network-loaded animation.

## Controlling playback precisely

The default "loop forever" is rarely what a polished UI wants. `animateLottieCompositionAsState` gives you the knobs:

- `iterations = LottieConstants.IterateForever` for ambient loops, or a fixed count for one-shots.
- `speed` (negative reverses — handy for a toggle that plays a check-mark backward on undo).
- `clipSpec` to play only a segment, e.g. `LottieClipSpec.Progress(0f, 0.5f)` for the "intro" half, then the loop half.
- `restartOnPlay` and `isPlaying` to pause/resume.

A common real requirement is "play intro once, then loop the idle part." Compose that from two clip specs and a state flag rather than shipping two files. For fully manual control — scrubbing an animation with a slider, or syncing it to scroll position — skip `animateLottieCompositionAsState` and feed your own progress float straight into `LottieAnimation`.

## Dynamic properties: one file, many looks

Shipping three color variants of the same animation is a smell. Dynamic properties let you override color, opacity, or transforms on named layers at runtime, so a single file adapts to your theme:

```kotlin
val dynamicProperties = rememberLottieDynamicProperties(
    rememberLottieDynamicProperty(
        property = LottieProperty.COLOR,
        value = MaterialTheme.colorScheme.primary.toArgb(),
        keyPath = arrayOf("Shape Layer 1", "**"),
    )
)
LottieAnimation(composition, { progress }, dynamicProperties = dynamicProperties)
```

The `keyPath` targets layers by name (`"**"` is a wildcard). Get the exact names from the designer or the Lottie preview tools. Text delegates similarly swap strings, which is how you localize an animation with baked-in text without exporting a file per language. This is the feature that turns Lottie from "a canned asset" into "a themeable component."

## Where the performance actually goes

Lottie renders on the CPU by default, drawing vector paths every frame. Cost scales with complexity, and the expensive features are specific:

1. **Masks and mattes** force offscreen buffers and are the number-one jank source. Ask design to avoid them or flatten where possible.
2. **Large embedded raster images** bloat the JSON and memory. Prefer vector shapes; if images are needed, size them to their display resolution.
3. **Layer count.** Hundreds of layers is hundreds of draw operations per frame. A "simple" loading spinner exported carelessly can carry absurd complexity.
4. **Many simultaneous animations.** A list where every row plays a Lottie is death. Play at most a couple on screen; for lists, use a static placeholder and animate only on interaction.

The single highest-leverage fix is upstream: get the designer to export lean files and preview the JSON's layer count before you integrate. A 40KB, low-layer file will outperform any amount of code tuning on a 2MB monster. When I inherited a checkout flow that stuttered, the fix wasn't code — it was re-exporting one confetti animation from 1.8MB to 90KB.

## Practical guardrails

- **Respect reduced-motion.** Users with animation-reduction preferences shouldn't get a bouncing hero loop. Gate ambient animations on the system setting and fall back to a static frame.
- **Don't autoplay off-screen.** Only animate what's visible; pause when the composable leaves composition or the screen is backgrounded to save battery.
- **Pick the right moment.** Lottie earns its weight on emotional beats — success, empty states, onboarding delight — not as decoration on every screen. Overused, it reads as noise and costs frames.

## What I'd take away

Treat Lottie's three concerns separately: load with `rememberLottieComposition`, drive with `animateLottieCompositionAsState` (or your own float), render with `LottieAnimation`, and always pass progress as a lambda to stay off the recomposition path. Use `clipSpec` and iteration counts for precise playback, dynamic properties to theme one file instead of shipping many, and respect reduced-motion. But the real performance work happens in the export: small files, no gratuitous masks, few layers. Get that right and Lottie is a delight; ignore it and it's the reason your onboarding drops frames.

## Resources

- [Lottie for Android and Compose (official docs)](https://airbnb.io/lottie/#/android-compose)
- [LottieFiles — creating and optimizing animations](https://lottiefiles.com/)
- [Compose animation overview (Android)](https://developer.android.com/develop/ui/compose/animation/introduction)
- [Lottie Compose GitHub](https://github.com/airbnb/lottie-android)
- [Reduce motion accessibility (Android)](https://developer.android.com/guide/topics/ui/accessibility)
