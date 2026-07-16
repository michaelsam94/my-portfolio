---
title: "AnimationController Patterns That Scale in Flutter"
slug: "flutter-animation-controller-patterns"
description: "Staggered sequences, reusable controllers, and gesture-driven animation in Flutter. Patterns for managing AnimationController lifecycles without leaks or spaghetti."
datePublished: "2024-10-19"
dateModified: "2024-10-19"
tags: ["Flutter", "Dart", "Animation", "Architecture"]
keywords: "Flutter AnimationController, staggered animation, Interval Flutter, gesture driven animation, TickerProviderStateMixin, animation lifecycle"
faq:
  - q: "How do I create a staggered animation in Flutter?"
    a: "Drive several animations from a single AnimationController and give each one an Interval curve that occupies a different slice of the 0-to-1 timeline. For example one element animates over the interval 0.0-0.5 and the next over 0.4-1.0, producing overlapping, staggered motion from one controller. This keeps everything synchronized and avoids juggling multiple controllers and their timings."
  - q: "Should I use one AnimationController for multiple animations?"
    a: "Yes, when the animations belong to the same logical sequence or need to stay synchronized, drive them all from one controller using different Tweens and Interval curves. Use separate controllers only when animations are truly independent — different durations, different triggers, different lifecycles. Fewer controllers means fewer tickers to manage and dispose, and tighter synchronization."
  - q: "How do I make an animation follow a drag gesture in Flutter?"
    a: "Set the AnimationController's value directly from the gesture's delta instead of calling forward or reverse — for example update controller.value as the user drags a sheet. On release, call fling with the gesture velocity or animateTo a snap point so the motion continues naturally. This gives you interruptible, physics-aware, gesture-driven animation."
---

Once a Flutter animation grows past a single fade, the hard part stops being the animation and becomes managing `AnimationController` lifecycles: how many controllers, who ticks them, when they dispose, and how you keep a multi-element sequence synchronized. The patterns that scale come down to a few disciplines — drive related animations from one controller with `Interval`s, use the right `TickerProvider` mixin, and treat gesture-driven motion as setting the controller's value directly rather than playing it. Get these right and complex choreography stays maintainable; get them wrong and you get leaked tickers, timing drift, and a `dispose` method you're afraid to touch.

This assumes you already know when to reach for an explicit controller at all — if not, start with [implicit vs explicit animations](https://blog.michaelsam94.com/flutter-implicit-explicit-animations/). This post is about the patterns *after* you've committed to explicit control.

## One controller, many animations

The instinct to spin up a controller per animated property is where sequences go wrong. Multiple controllers drift out of sync and multiply the lifecycle you have to manage. The scalable pattern is **one controller as the master timeline**, with each animated property deriving from it via its own `Tween` and `CurvedAnimation`:

```dart
class _CardIntro extends State<CardIntro> with TickerProviderStateMixin {
  late final _c = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 700),
  );

  late final _fade = CurvedAnimation(parent: _c, curve: Curves.easeIn);
  late final _slide = Tween(begin: const Offset(0, 0.15), end: Offset.zero)
      .animate(CurvedAnimation(parent: _c, curve: Curves.easeOutCubic));
  late final _scale = Tween(begin: 0.96, end: 1.0)
      .animate(CurvedAnimation(parent: _c, curve: Curves.easeOut));

  @override
  void initState() {
    super.initState();
    _c.forward();
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }
}
```

Three animations, one timeline, one thing to dispose. They can never desynchronize because they share the same clock.

## Staggering with Interval

For sequential-but-overlapping motion — a list of items cascading in — you don't need multiple controllers or `Future.delayed`. You slice the single 0→1 timeline with `Interval` curves so each element animates during a different window:

```dart
Animation<double> _staggered(int index, int count) {
  final start = (index / count) * 0.6;      // stagger the starts
  final end = start + 0.4;                   // each runs 40% of the timeline
  return CurvedAnimation(
    parent: _c,
    curve: Interval(start, end.clamp(0.0, 1.0), curve: Curves.easeOut),
  );
}
```

Item 0 animates over roughly 0.0–0.4 of the controller's run, item 1 over ~0.12–0.52, and so on — a clean cascade from one `forward()` call. `Interval` is the single most underused tool for choreography; it turns "coordinate five timers" into "carve up one timeline."

## Choosing the ticker mixin

The `vsync` argument wants a `TickerProvider`, and the choice is binary:

- **`SingleTickerProviderStateMixin`** — exactly one controller in this `State`. Slightly cheaper; the framework asserts if you create a second.
- **`TickerProviderStateMixin`** — two or more controllers.

Pick the single variant when you can; it documents intent and catches accidental extra controllers. But if you're following the "one master controller" pattern above, you'll often only need the single mixin even for elaborate sequences, because the elaboration lives in `Interval`s, not extra controllers.

## Gesture-driven animation

The pattern people most often get wrong is tying animation to a drag. The wrong way is to compute a target and call `animateTo` repeatedly during the gesture — it lags the finger and fights interruptions. The right way is to set `controller.value` *directly* from the drag delta, then hand control back to physics on release:

```dart
void _onDragUpdate(DragUpdateDetails d) {
  _c.value -= d.primaryDelta! / _sheetHeight; // track the finger 1:1
}

void _onDragEnd(DragEndDetails d) {
  final v = -d.primaryVelocity! / _sheetHeight;
  if (v.abs() > 1.0) {
    _c.fling(velocity: v); // continue with the throw's momentum
  } else {
    // snap to whichever end is closer
    _c.animateTo(_c.value > 0.5 ? 1.0 : 0.0, curve: Curves.easeOut);
  }
}
```

Because the controller value tracks the finger, the motion is interruptible and physical. `fling` continues the gesture's momentum; `animateTo` snaps when the throw was gentle. This is exactly how bottom sheets and swipe-to-dismiss feel right.

## Reacting to status

Chaining phases — play in, hold, play out, or ping-pong — is done with a status listener, not nested callbacks:

```dart
_c.addStatusListener((status) {
  if (status == AnimationStatus.completed) {
    _c.reverse();
  } else if (status == AnimationStatus.dismissed) {
    _c.forward();
  }
});
```

That's a self-reversing loop. For a bounded number of repeats or a hold in the middle, branch on status and a counter. Keep this logic in the `State`, not scattered through the build method.

## Lifecycle discipline

The recurring production bug is the leaked ticker. Rules I hold to:

1. **Every controller gets disposed** in `dispose()`. A ticker with no dispose keeps the app rendering frames forever, draining battery.
2. **Don't call `forward()`/`repeat()` inside `build`** — build runs many times; start animations in `initState` or in response to events.
3. **Guard against animating a disposed controller** — if an async callback might fire after dispose, check `mounted` before touching the controller.
4. **Reuse, don't recreate.** Creating a controller per build (instead of in `initState`/`late final`) leaks one per rebuild — a nasty, gradual battery and memory drain.

## When to reach for a package

Hand-rolled controllers are right for UI motion you own. But for genuinely complex, designer-authored, interactive animation — state machines, morphing vector art — a controller-and-`Tween` approach becomes unwieldy, and [Rive](https://blog.michaelsam94.com/flutter-rive-interactive-animations/) is the better tool. And for shared-element transitions between routes, use [Hero animations](https://blog.michaelsam94.com/flutter-hero-animations-advanced/) rather than manually coordinating controllers across screens.

## What I'd take away

Drive related motion from a single `AnimationController` and carve the timeline with `Interval`s instead of juggling multiple controllers and timers. Pick `SingleTickerProviderStateMixin` when you can, set `controller.value` directly for gesture-driven animation and `fling` on release, use status listeners for phased sequences, and treat disposing controllers as non-negotiable. These patterns keep complex choreography synchronized, interruptible, and leak-free — which is the whole difference between an animation that ships and one that quietly ruins battery life.

## Resources

- [Staggered animations (Flutter docs)](https://docs.flutter.dev/ui/animations/staggered-animations)
- [AnimationController API reference](https://api.flutter.dev/flutter/animation/AnimationController-class.html)
- [Interval curve API reference](https://api.flutter.dev/flutter/animation/Interval-class.html)
- [TickerProviderStateMixin API reference](https://api.flutter.dev/flutter/widgets/TickerProviderStateMixin-mixin.html)
- [Animations tutorial (Flutter docs)](https://docs.flutter.dev/ui/animations/tutorial)
