---
title: "Custom Scroll Physics in Flutter"
slug: "flutter-custom-scroll-physics"
description: "Custom ScrollPhysics in Flutter controls friction, fling, and snapping. How to subclass ScrollPhysics for paging, snap-to-item, and platform-consistent scroll feel."
datePublished: "2024-10-14"
dateModified: "2024-10-14"
tags: ["Flutter", "Dart", "UI", "Animation"]
keywords: "Flutter ScrollPhysics, custom scroll physics, snap to item Flutter, PageScrollPhysics, BouncingScrollPhysics, createBallisticSimulation"
faq:
  - q: "What does ScrollPhysics control in Flutter?"
    a: "ScrollPhysics determines how a scroll view responds to user input and momentum — the friction while dragging, whether it overscrolls with a bounce or a glow, how far a fling carries, and whether it settles onto specific offsets. It does not control what is scrolled or how items are laid out; it only shapes the feel of the motion. You swap it via the physics parameter on any scrollable."
  - q: "How do I make a list snap to items in Flutter?"
    a: "Subclass ScrollPhysics and override createBallisticSimulation to return a simulation that targets the nearest item boundary at the end of a fling or drag. PageScrollPhysics already does this for full-viewport pages, so for full-page snapping you just set physics: PageScrollPhysics(). For custom item sizes you compute the nearest multiple of your item extent and animate to it."
  - q: "What is the difference between BouncingScrollPhysics and ClampingScrollPhysics?"
    a: "BouncingScrollPhysics is the iOS-style behavior where content overscrolls past the edge and springs back. ClampingScrollPhysics is the Android-style behavior where the content stops hard at the edge and shows a stretch or glow indicator. By default Flutter picks per platform, but you can force either, or compose them onto AlwaysScrollableScrollPhysics to keep scrolling enabled even when content fits."
---

`ScrollPhysics` is the Flutter class that decides how scrolling *feels* — the drag friction, whether the edge bounces or clamps, how far a fling coasts, and whether the list settles onto specific offsets. It's a separate concern from what you scroll (slivers, lists) and how items lay out; physics only shapes the motion. Most apps never touch it, and most apps are right not to. But when you need snap-to-item paging, a carousel that locks onto cards, or scroll behavior that matches a specific platform, subclassing `ScrollPhysics` is the correct, surprisingly small amount of code.

I've watched teams reinvent snapping with `NotificationListener` hacks and post-fling `animateTo` calls that fight the user's finger and stutter. Doing it through physics instead means the snapping is part of the *momentum simulation*, so it feels native because it literally uses the same machinery.

## The built-in physics you already have

Before subclassing, know the stock options, because composition covers a lot:

- **`BouncingScrollPhysics`** — iOS-style overscroll with spring-back.
- **`ClampingScrollPhysics`** — Android-style hard stop with a stretch/glow.
- **`AlwaysScrollableScrollPhysics`** — keeps scrolling enabled even when content fits the viewport (needed for pull-to-refresh on short lists).
- **`NeverScrollableScrollPhysics`** — disables user scrolling (for a list driven programmatically or nested inside another scrollable).
- **`PageScrollPhysics`** — snaps to full-viewport pages; what `PageView` uses.
- **`RangeMaintainingScrollPhysics`** — keeps your scroll position sensible when content resizes.

These compose via `applyTo`. `AlwaysScrollableScrollPhysics(parent: BouncingScrollPhysics())` means "always scrollable, and bounce at the edges." Physics chain like decorators, so you rarely start from scratch.

## How physics actually works

Two overrides carry most of the behavior:

- **`applyPhysicsToUserOffset`** shapes the response while the finger is down — this is where overscroll resistance lives (drag past the edge and it moves less than your finger).
- **`createBallisticSimulation`** runs when the finger lifts. It returns a `Simulation` describing the deceleration curve. Return `null` and the scroll just stops; return a spring or friction simulation and it coasts or bounces. This is the hook for snapping.

The `ScrollMetrics` passed to these methods tell you everything about the current state: `pixels` (current offset), `minScrollExtent`, `maxScrollExtent`, `viewportDimension`. That's enough to compute where you *want* to land.

## Snap-to-item physics

Here's the pattern for a carousel that locks onto fixed-width cards. The idea: at the end of a fling, compute the nearest item boundary and return a spring simulation toward it.

```dart
class SnapScrollPhysics extends ScrollPhysics {
  const SnapScrollPhysics({required this.itemExtent, super.parent});

  final double itemExtent;

  @override
  SnapScrollPhysics applyTo(ScrollPhysics? ancestor) =>
      SnapScrollPhysics(itemExtent: itemExtent, parent: buildParent(ancestor));

  double _target(ScrollMetrics position, double velocity) {
    // Where a normal fling would end...
    final base = position.pixels + velocity * 0.15;
    // ...snapped to the nearest item boundary, clamped to range.
    final index = (base / itemExtent).round();
    return (index * itemExtent)
        .clamp(position.minScrollExtent, position.maxScrollExtent);
  }

  @override
  Simulation? createBallisticSimulation(
      ScrollMetrics position, double velocity) {
    final target = _target(position, velocity);
    if ((target - position.pixels).abs() < precisionErrorTolerance) {
      return null;
    }
    return ScrollSpringSimulation(
      spring, position.pixels, target, velocity,
      tolerance: toleranceFor(position),
    );
  }

  @override
  bool get allowImplicitScrolling => false;
}
```

Attach it with `ListView(physics: const SnapScrollPhysics(itemExtent: 320), ...)`. Because the snap is expressed as the *destination of the ballistic simulation*, the settle uses the same spring the framework uses everywhere — no post-hoc `animateTo`, no fighting the gesture, no visible correction jump.

## Matching platform feel deliberately

Flutter's `ScrollBehavior` picks bouncing on iOS and clamping on Android by default, which is usually what you want. But there are legitimate reasons to override globally — a design system that mandates one feel everywhere, or an embedded webview-like surface. Do it at the `ScrollConfiguration` level rather than sprinkling `physics:` on every list:

```dart
class AppScrollBehavior extends MaterialScrollBehavior {
  @override
  ScrollPhysics getScrollPhysics(BuildContext context) =>
      const BouncingScrollPhysics();
}
```

Wrap your `MaterialApp` with a `scrollBehavior: AppScrollBehavior()` and every scrollable inherits it. Centralizing this beats hunting down individual lists later.

## Where I stop and use PageView

If you want full-viewport paging, don't write custom physics — `PageView` with `PageScrollPhysics` already nails it, including the resistance and snap. Reach for custom `ScrollPhysics` only when the snap targets aren't full pages (fixed-width cards in a horizontal list, sticky sections, magnetic scroll to headers). Knowing when *not* to subclass is half the skill.

## Debugging the feel

Scroll feel is subjective, so measure. Enable the performance overlay (`showPerformanceOverlay: true`) and watch for jank during flings; a stuttering snap usually means you're doing work in a scroll listener instead of in the simulation. Test on a real low-end Android device, not just the simulator — the iOS simulator in particular lies about scroll smoothness. And test with both a slow drag-release and a hard flick, because the velocity term is where snap logic most often gets the target wrong.

Custom physics pairs naturally with custom scroll structure; if you're building elaborate scroll UIs, the layout side lives in [slivers and CustomScrollView](https://blog.michaelsam94.com/flutter-slivers-custom-scroll/), and truly bespoke scrolling widgets sometimes bottom out in a [RenderObject](https://blog.michaelsam94.com/flutter-render-object-widgets/).

## What I'd take away

Reach for the composable built-ins first — bouncing, clamping, always-scrollable, page — and only subclass `ScrollPhysics` when you need snap targets the framework doesn't provide. Put snapping logic in `createBallisticSimulation` by returning a spring toward the computed target, so the settle uses the same simulation machinery as native scrolling and feels right. Centralize platform feel in a `ScrollBehavior`, and always validate on a real low-end device. Get it right and users never notice the physics — which is exactly the point.

## Resources

- [ScrollPhysics API reference](https://api.flutter.dev/flutter/widgets/ScrollPhysics-class.html)
- [Scrolling (Flutter docs)](https://docs.flutter.dev/ui/layout/scrolling)
- [ScrollSpringSimulation API reference](https://api.flutter.dev/flutter/physics/ScrollSpringSimulation-class.html)
- [PageScrollPhysics API reference](https://api.flutter.dev/flutter/widgets/PageScrollPhysics-class.html)
- [ScrollConfiguration and ScrollBehavior](https://api.flutter.dev/flutter/widgets/ScrollConfiguration-class.html)
