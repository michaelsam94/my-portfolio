---
title: "Designing Haptics on Android with VibrationEffect and Composition"
slug: "android-haptics-vibration-effects"
description: "Design great Android haptics with VibrationEffect, primitive composition, HapticFeedbackConstants, and amplitude control that degrades gracefully on older devices."
datePublished: "2024-07-28"
dateModified: "2024-07-28"
tags: ["Android", "Haptics", "UX", "Input"]
keywords: "Android haptics, VibrationEffect, haptic composition, HapticFeedbackConstants, amplitude control vibration, tactile feedback Android"
faq:
  - q: "What is the difference between VibrationEffect and HapticFeedbackConstants?"
    a: "HapticFeedbackConstants are high-level, semantic feedback tokens (like CONFIRM, REJECT, or LONG_PRESS) that you play via View.performHapticFeedback, and the system maps them to a tuned effect for that device. VibrationEffect is the lower-level API where you author the waveform or compose primitives yourself. Prefer the constants for standard interactions and reach for VibrationEffect only when you need a custom feel the semantic set doesn't cover."
  - q: "How do I create custom haptic patterns on Android?"
    a: "Use VibrationEffect.startComposition() to chain primitives like PRIMITIVE_CLICK, PRIMITIVE_TICK, and PRIMITIVE_SPIN, each with a scale and delay, into a single richer effect. On devices that lack composition support, check areAllPrimitivesSupported and fall back to a createWaveform effect or a semantic HapticFeedbackConstant so the interaction still feels intentional."
  - q: "Why do my vibrations feel the same on every device?"
    a: "Older or budget actuators (ERM motors) can only really do on/off buzzes, so amplitude and primitive composition collapse to a coarse rumble. Devices with LRA actuators reproduce nuanced effects. Always query hasAmplitudeControl and getSupportedPrimitives, and design a tiered experience rather than assuming crisp haptics everywhere."
---

Good Android haptics are the difference between a UI that feels alive and one that feels like software. The modern toolkit is three layers: `HapticFeedbackConstants` for standard semantic feedback, `VibrationEffect` composition for custom feel, and hardware capability queries so it all degrades gracefully on cheaper actuators. The single biggest mistake I see is teams calling the deprecated `vibrate(milliseconds)` and shipping the same dumb buzz to a flagship LRA and a budget ERM motor alike. Haptics deserve the same tiering you'd give any capability that varies wildly across the fleet.

## Start semantic: HapticFeedbackConstants

Before you author a single waveform, ask whether the interaction is one the platform already has a tuned feel for. Confirmations, rejections, long-press, gesture thresholds, toggles — these have `HapticFeedbackConstants`, and the OEM has already tuned them for the device's actuator. Playing them means your "confirm" feels like every other confirm on that phone, which is exactly the consistency users subconsciously expect.

```kotlin
// Semantic feedback: the system maps this to a device-tuned effect.
view.performHapticFeedback(HapticFeedbackConstants.CONFIRM)
view.performHapticFeedback(HapticFeedbackConstants.REJECT)
view.performHapticFeedback(HapticFeedbackConstants.GESTURE_START)
```

In Compose the analog is `LocalHapticFeedback` with `HapticFeedbackType`, which is smaller but covers `LongPress` and text-handle moves. For anything the semantic set covers, stop here. You'll get better cross-device behavior than you'd hand-author, for one line of code.

## When to drop to VibrationEffect

You reach for `VibrationEffect` when the semantic set genuinely doesn't have your interaction: a custom slider detent, a game hit, the "thunk" of a card snapping into place, a ramping charge-up. There are two authoring styles.

**Waveforms** define amplitude over time — a list of timings and amplitudes (0–255). Good for buzzes, pulses, and ramps:

```kotlin
val ramp = VibrationEffect.createWaveform(
    longArrayOf(0, 40, 30, 40),      // timings (ms)
    intArrayOf(0, 80, 0, 255),       // amplitudes (0-255)
    -1                                // no repeat
)
vibrator.vibrate(ramp)
```

**Composition** chains tuned *primitives* — `PRIMITIVE_CLICK`, `PRIMITIVE_TICK`, `PRIMITIVE_THUD`, `PRIMITIVE_SPIN`, `PRIMITIVE_QUICK_RISE` — each with a scale and an optional delay. This is where premium feel lives, because primitives are calibrated per-device rather than being raw amplitude:

```kotlin
val effect = VibrationEffect.startComposition()
    .addPrimitive(VibrationEffect.Composition.PRIMITIVE_QUICK_RISE, 0.6f)
    .addPrimitive(VibrationEffect.Composition.PRIMITIVE_CLICK, 1.0f, 40)
    .compose()
vibrator.vibrate(effect)
```

## Capability queries are not optional

Here's the part that separates haptics that feel great everywhere from haptics that feel great on *your* test device. Actuators differ enormously:

- **LRA** (linear resonant actuator): fast, crisp, supports amplitude and primitives. Flagships.
- **ERM** (eccentric rotating mass): a spinning weight; slow to start and stop, coarse, effectively on/off. Budget and older phones.

So query before you play:

```kotlin
val hasAmplitude = vibrator.hasAmplitudeControl()
val canCompose = vibrator.areAllPrimitivesSupported(
    VibrationEffect.Composition.PRIMITIVE_CLICK,
    VibrationEffect.Composition.PRIMITIVE_QUICK_RISE,
)
```

Design a fallback ladder: composition if supported, else a hand-tuned waveform if there's amplitude control, else a semantic `HapticFeedbackConstant` or a short single buzz. I keep this behind a small `Haptics` wrapper so call sites say `haptics.play(Feel.CardSnap)` and the tiering lives in one place. That wrapper is also where I gate everything on the user's system haptic setting — respect it, and never vibrate for passive events the user didn't cause.

## Get the manager right

On Android 12+ prefer `VibratorManager` (which can address multiple actuators) over the legacy single `Vibrator`. And every custom effect needs a `VibrationAttributes` usage so the system routes it correctly and respects Do Not Disturb and accessibility settings:

```kotlin
val manager = context.getSystemService(VibratorManager::class.java)
val vibrator = manager.defaultVibrator
vibrator.vibrate(
    effect,
    VibrationAttributes.createForUsage(VibrationAttributes.USAGE_TOUCH)
)
```

Getting `USAGE_TOUCH` vs `USAGE_NOTIFICATION` right matters: a touch-usage effect won't fire when the screen is off, which is exactly what you want for UI feedback and exactly wrong for an alarm.

## Timing is the whole game

The technical APIs are easy; the taste is in *when* and *how strong*. A few rules I've converged on after tuning real products:

- **Tie haptics to a physical event, not a timer.** The click should land the instant the toggle visually flips, not 80ms later. Latency between animation and haptic reads as broken.
- **Under-do it.** A subtle `PRIMITIVE_TICK` for scroll detents beats a strong buzz that makes the phone feel angry. Users notice absence of good haptics less than presence of bad ones.
- **Don't haptic-spam.** Continuous feedback during a drag should be sparse ticks at meaningful thresholds, not a constant motor drone that drains battery and annoys.
- **Match visual weight.** A big destructive confirm can be a firmer `THUD`; a lightweight selection is a whisper `TICK`. Let the haptic's intensity mirror the action's consequence.

Coordinating the haptic with the animation frame is the same discipline as syncing sound and motion — the feedback lands the moment the [gesture-driven animation](https://blog.michaelsam94.com/jetpack-compose-lessons-10-years-android/) commits, so the phone feels like it's physically responding to the pixels.

## What I'd take away

Reach for `HapticFeedbackConstants` first — free, consistent, device-tuned. Drop to `VibrationEffect` composition for custom feel, prefer primitives over raw waveforms, and *always* query `hasAmplitudeControl` and primitive support so a budget ERM phone still gets a deliberate single buzz instead of nothing or garbage. Wrap it all behind one semantic API, respect the user's settings, and tie every effect to the exact frame the interaction commits. Do that and your app joins the small set that feels physical instead of merely animated.

## Resources

- [Haptics design principles (Android)](https://developer.android.com/develop/ui/views/haptics)
- [VibrationEffect reference](https://developer.android.com/reference/android/os/VibrationEffect)
- [Add haptic feedback to events](https://developer.android.com/develop/ui/views/haptics/haptic-feedback)
- [VibratorManager reference](https://developer.android.com/reference/android/os/VibratorManager)
- [Compose HapticFeedback](https://developer.android.com/reference/kotlin/androidx/compose/ui/hapticfeedback/HapticFeedback)
