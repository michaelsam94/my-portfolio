---
title: "Implicit vs Explicit Animations in Flutter"
slug: "flutter-implicit-explicit-animations"
description: "Implicit vs explicit animations in Flutter: when AnimatedContainer is enough and when you need an AnimationController. A practical rule for picking the right approach."
datePublished: "2024-10-17"
dateModified: "2024-10-17"
tags: ["Flutter", "Dart", "Animation", "UI"]
keywords: "Flutter implicit animations, explicit animations, AnimatedContainer, AnimationController, TweenAnimationBuilder, AnimatedBuilder"
faq:
  - q: "What is the difference between implicit and explicit animations in Flutter?"
    a: "Implicit animations animate automatically when a value changes — you set a new target on a widget like AnimatedContainer and Flutter tweens to it over a duration, no controller required. Explicit animations are driven by an AnimationController you create and manage, giving you control over play, pause, reverse, repeat, and coordination of multiple animations. Implicit is for fire-and-forget state transitions; explicit is for anything you need to orchestrate."
  - q: "When should I use an AnimationController instead of AnimatedContainer?"
    a: "Use an AnimationController when you need to control the animation's lifecycle — replay, reverse, loop, chain multiple animations, or drive several properties from one timeline — or when the animation is continuous like a spinner. Use AnimatedContainer and other implicit widgets when a value simply changes and you want a smooth transition to the new state with no manual control. Most UI polish is implicit; complex choreography is explicit."
  - q: "Are implicit animations less performant than explicit ones?"
    a: "No, they use the same underlying animation and ticker machinery, so raw performance is comparable. The difference is control and expressiveness, not speed. Implicit animations can actually be more efficient to write and less error-prone because Flutter manages the controller lifecycle for you, avoiding leaked tickers from forgotten dispose calls."
---

The rule I give every Flutter developer is simple: reach for **implicit animations** first, and only escalate to **explicit** ones when you need to control the animation's lifecycle. Implicit animations — `AnimatedContainer`, `AnimatedOpacity`, `AnimatedPadding` and friends — tween automatically when a value changes, with no controller to manage. Explicit animations, driven by an `AnimationController`, are what you use when you need to replay, reverse, loop, or coordinate multiple properties on one timeline. Ninety percent of the polish in a good app is implicit; the flashy choreography is the other ten.

I've reviewed a lot of Flutter animation code, and the most common mistake by far is reaching for an `AnimationController` — with all its lifecycle boilerplate and leak potential — for something an `AnimatedContainer` would have done in three lines. The second most common is the reverse: trying to fake a looping or reversible animation with implicit widgets and state flags, when a controller is the clean answer.

## Implicit: change a value, get a transition

Implicit animation widgets take a `duration` and a `curve`, and whenever one of their animatable properties changes between builds, they smoothly interpolate to the new value. No controller, no `TickerProvider`, no `dispose`.

```dart
AnimatedContainer(
  duration: const Duration(milliseconds: 300),
  curve: Curves.easeOutCubic,
  width: expanded ? 320 : 160,
  height: expanded ? 200 : 120,
  decoration: BoxDecoration(
    color: expanded ? Colors.indigo : Colors.blueGrey,
    borderRadius: BorderRadius.circular(expanded ? 24 : 12),
  ),
);
```

Flip `expanded` in `setState`, and the size, color, and corner radius all animate to their new values at once. That's the entire mental model: describe the target state, and the widget animates *to* it. The family is broad — `AnimatedOpacity`, `AnimatedAlign`, `AnimatedPositioned` (inside a `Stack`), `AnimatedDefaultTextStyle`, `AnimatedSwitcher` for swapping children, `AnimatedCrossFade` for two-child transitions.

For a one-off custom property that no built-in animates, `TweenAnimationBuilder` gives you implicit behavior for anything:

```dart
TweenAnimationBuilder<double>(
  tween: Tween(begin: 0, end: rating),
  duration: const Duration(milliseconds: 400),
  builder: (context, value, child) => StarRow(value: value),
);
```

Change `end` and it tweens from the current value — implicit animation for arbitrary data, still no controller.

## Explicit: you hold the timeline

When you need to *drive* the animation rather than just declare a target, you create an `AnimationController`. It's a `Ticker`-backed value that runs from 0 to 1 over a duration and gives you `forward()`, `reverse()`, `repeat()`, `stop()`, and status callbacks.

```dart
class Spinner extends StatefulWidget {
  const Spinner({super.key});
  @override
  State<Spinner> createState() => _SpinnerState();
}

class _SpinnerState extends State<Spinner>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(seconds: 1),
  )..repeat();

  @override
  void dispose() {
    _c.dispose(); // non-negotiable — a leaked ticker runs forever
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => RotationTransition(
        turns: _c,
        child: const Icon(Icons.refresh),
      );
}
```

Three things define the explicit workflow: the `TickerProvider` (`SingleTickerProviderStateMixin` for one controller, `TickerProviderStateMixin` for several), the `dispose` call that prevents a leaked ticker from burning battery forever, and the transition/builder widget that turns the 0→1 value into visible motion.

## Curves and Tweens layer on top

A controller is linear 0→1. You shape it with a `Tween` (to map 0→1 onto a value range) and a `CurvedAnimation` (to apply easing):

```dart
late final Animation<double> _slide = Tween(begin: -1.0, end: 0.0).animate(
  CurvedAnimation(parent: _c, curve: Curves.easeOutBack),
);
```

Now `_slide` runs from -1 to 0 with an overshoot ease. Drive several such animations from the *same* controller and they stay perfectly in sync — that's the real reason to go explicit: coordinated, multi-property choreography on one timeline. When it grows into full sequences with staggered intervals, that's its own discipline I cover in [AnimationController patterns that scale](https://blog.michaelsam94.com/flutter-animation-controller-patterns/).

## AnimatedBuilder vs the transition widgets

To rebuild only the animating part (not the whole widget), wrap it in `AnimatedBuilder` or one of the specialized `*Transition` widgets (`FadeTransition`, `ScaleTransition`, `SlideTransition`, `RotationTransition`). Pass a `child` to keep the static subtree out of the rebuild:

```dart
AnimatedBuilder(
  animation: _c,
  builder: (context, child) => Opacity(opacity: _c.value, child: child),
  child: const ExpensiveWidget(), // built once, not every frame
);
```

That `child` optimization matters: without it, `ExpensiveWidget` rebuilds 60 times a second for no reason.

## The decision rule

| Situation | Use |
|---|---|
| A value changes and you want a smooth transition | Implicit (`AnimatedContainer`, `AnimatedOpacity`, ...) |
| Custom property, still fire-and-forget | `TweenAnimationBuilder` |
| Continuous motion (spinner, pulse) | Explicit + `repeat()` |
| Reverse / replay on demand | Explicit |
| Multiple properties on one synced timeline | Explicit + multiple `Tween`s |
| Gesture-driven scrubbing | Explicit (drive controller `.value` from the gesture) |

If you can't answer "do I need to control playback?" with a clear yes, you want implicit.

## Performance and pitfalls

Implicit and explicit share the same ticker machinery, so neither is inherently faster; the wins come from scope. Always pass a `child` to builders to avoid rebuilding static subtrees, keep animations off the layout path where you can (animate `Transform`/`Opacity` rather than causing relayout), and *always* dispose controllers. The single most common production bug I see is a forgotten `dispose` leaking a ticker that quietly keeps the app awake. For screen-to-screen motion you generally want neither of these directly — that's [Hero animations](https://blog.michaelsam94.com/flutter-hero-animations-advanced/) — and for designer-authored interactive motion, [Rive](https://blog.michaelsam94.com/flutter-rive-interactive-animations/) is often the better tool than either.

## What I'd take away

Default to implicit animations: they cover most UI polish with almost no code and no lifecycle to leak. Escalate to an explicit `AnimationController` only when you need to control playback — loop, reverse, replay, scrub — or coordinate several properties on one synchronized timeline. Layer `Tween` and `CurvedAnimation` for range and easing, use `child` in your builders to keep rebuilds tight, and never forget to dispose. Pick the smallest tool that expresses the motion, and your animation code stays boring in the best way.

## Resources

- [Introduction to animations (Flutter docs)](https://docs.flutter.dev/ui/animations)
- [Implicit animations (Flutter docs)](https://docs.flutter.dev/ui/animations/implicit-animations)
- [Animations tutorial (Flutter docs)](https://docs.flutter.dev/ui/animations/tutorial)
- [AnimationController API reference](https://api.flutter.dev/flutter/animation/AnimationController-class.html)
- [Curves catalog](https://api.flutter.dev/flutter/animation/Curves-class.html)
