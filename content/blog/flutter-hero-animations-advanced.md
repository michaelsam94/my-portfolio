---
title: "Advanced Hero Animations in Flutter"
slug: "flutter-hero-animations-advanced"
description: "Beyond the basic Hero: custom flightShuttleBuilder, radius and shape morphs, hero across nested navigators, and the tag pitfalls that break shared-element transitions."
datePublished: "2024-10-20"
dateModified: "2024-10-20"
tags: ["Flutter", "Dart", "Animation", "UI"]
keywords: "Flutter Hero animation, flightShuttleBuilder, shared element transition, hero tag, createRectTween, hero across navigators"
faq:
  - q: "How does a Hero animation work in Flutter?"
    a: "A Hero widget marks a subtree with a tag; when you navigate between two routes that each contain a Hero with the same tag, Flutter animates that element flying from its position and size on the source route to its position and size on the destination route. During the flight the hero is lifted into an overlay above both routes. The rest of each screen transitions normally underneath the flying hero."
  - q: "Why is my Flutter Hero animation not working?"
    a: "The most common causes are mismatched or duplicate tags — both routes must contain exactly one Hero with the same, unique tag — or the destination Hero not being present when the route builds. Wrapping a Hero in something that changes its identity, using the same tag twice on one screen, or navigating with a route that Hero does not observe will all silently disable the flight. Check tags first."
  - q: "How do I customize the transition of a Hero in Flutter?"
    a: "Use flightShuttleBuilder to supply the widget shown mid-flight, which lets you cross-fade between the source and destination widgets or morph shape and style. Use createRectTween to change the flight path, for example a curved arc instead of a straight line. Together these give you full control over how the shared element looks and moves during the transition."
---

A Flutter `Hero` animation flies a shared element — an image, a card, an avatar — from its spot on one screen to its spot on the next, so the two routes feel connected instead of jump-cut. The basics are almost too easy: wrap the widget in a `Hero` with a matching `tag` on both screens and Flutter does the rest. The advanced work is everything the tutorials skip: morphing shape and corner radius mid-flight, cross-fading between two genuinely different widgets, curving the flight path, and making heroes survive nested navigators and lists without tag collisions. That's where shared-element transitions either feel premium or fall apart.

I've shipped hero transitions that got specifically praised in app-store reviews, and every one of them used `flightShuttleBuilder`. The default straight-line, same-widget flight is fine for a photo; it's not enough when the source and destination are shaped differently.

## The model you have to hold

When you push a route, `Hero` looks for a matching `tag` on both the outgoing and incoming routes. If it finds a pair, it **lifts the hero into an overlay** above both screens, animates a `Rect` from the source geometry to the destination geometry, and hides the placeholders in each route until the flight ends. Two consequences fall out of this that explain most bugs:

1. Both routes must contain **exactly one** hero with that tag. Two heroes with the same tag on one screen throws; zero on the destination silently does nothing.
2. The hero is *reparented into an overlay* during flight, so any `InheritedWidget` it depended on (theme, media query) is the overlay's, not the route's. Style that must stay stable should be passed explicitly, not read from context mid-flight.

## Tags: the number-one failure

Tags must be unique per screen and identical across the pair. In a list-to-detail flow, that means the tag has to carry the item's identity:

```dart
// list item
Hero(tag: 'product-${product.id}', child: Thumbnail(product));

// detail screen
Hero(tag: 'product-${product.id}', child: HeroImage(product));
```

Use `'product-42'`, never a constant `'product'`, or a list with ten visible items will have ten heroes sharing one tag and Flutter will throw `There are multiple heroes that share the same tag`. This single mistake accounts for most "hero not working" reports I've debugged.

## flightShuttleBuilder: morphing mid-flight

When the source and destination widgets differ — a square thumbnail becoming a rounded detail header, an icon becoming a full card — you don't want the source widget stretched across the whole flight. `flightShuttleBuilder` lets you supply what's shown *during* the flight, typically a cross-fade:

```dart
Hero(
  tag: 'product-${product.id}',
  flightShuttleBuilder: (context, animation, direction, fromContext, toContext) {
    final toHero = toContext.widget as Hero;
    final fromHero = fromContext.widget as Hero;
    return AnimatedBuilder(
      animation: animation,
      builder: (context, _) {
        final t = animation.value; // 0 -> 1 on push
        return Stack(
          fit: StackFit.expand,
          children: [
            Opacity(opacity: 1 - t, child: fromHero.child),
            Opacity(opacity: t, child: toHero.child),
          ],
        );
      },
    );
  },
  child: Thumbnail(product),
);
```

The `direction` argument (`push` vs `pop`) lets you invert the cross-fade so the reverse transition looks right too. This cross-fade is what makes a shape or content change feel like a morph rather than a stretch. The underlying value-driving here is the same `Animation<double>` machinery from [AnimationController patterns](https://blog.michaelsam94.com/flutter-animation-controller-patterns/) — the framework just hands you the flight's animation.

## Morphing corner radius and shape

A common polish detail: a rounded thumbnail becoming a rectangular header, or a circle avatar becoming a rounded rectangle. Because the shuttle builder gives you the flight `animation`, you can tween the border radius:

```dart
flightShuttleBuilder: (context, animation, dir, from, to) {
  final radius = BorderRadiusTween(
    begin: BorderRadius.circular(40),
    end: BorderRadius.circular(8),
  ).animate(animation);
  return AnimatedBuilder(
    animation: radius,
    builder: (context, _) => ClipRRect(
      borderRadius: radius.value!,
      child: Image.asset(asset, fit: BoxFit.cover),
    ),
  );
};
```

Now the shape interpolates continuously along with the position and size — no visible snap at either end.

## Curving the flight path

By default heroes fly along a straight, linearly-interpolated `Rect`. For a more organic feel — think a card arcing up into place — override `createRectTween` with a `MaterialRectArcTween`, which moves along a curved path:

```dart
Hero(
  tag: 'card-$id',
  createRectTween: (begin, end) =>
      MaterialRectArcTween(begin: begin, end: end),
  child: card,
);
```

Subtle, but it's part of what makes Material's own transitions feel less mechanical than a naive lerp.

## Heroes across nested navigators

In a `StatefulShellRoute` app with per-tab navigators (covered in [shell routes and nested navigation](https://blog.michaelsam94.com/flutter-gorouter-shell-routes/)), heroes only fly within the navigator that owns the transition. A push inside a branch animates fine; but if you need a hero to fly across a *root* navigator push that sits above the shell, make sure the route being pushed is on the navigator that both heroes share. Mismatched navigator ownership is a quieter cousin of the tag bug — the tags match, but the two heroes live under different `Navigator`s, so no pair is found.

## Debugging checklist

When a hero refuses to fly, walk this list in order:

1. **Tags** — identical across the pair, unique on each screen.
2. **Both present** — the destination hero exists when the route first builds (not behind a loading state or a conditional).
3. **Same navigator** — both routes belong to the navigator running the transition.
4. **Not clipped away** — an ancestor `ClipRect` or `Overflow` isn't hiding the hero at the endpoints.
5. **Transition type** — the route is a `PageRoute` Hero observes; some fully custom routes don't trigger hero flights.

## What I'd take away

The basic `Hero` is trivial; the premium feel comes from the details. Namespace your tags with item identity to avoid collisions, use `flightShuttleBuilder` to cross-fade and morph when source and destination genuinely differ, tween border radius and use `MaterialRectArcTween` for shape and path polish, and mind which navigator owns the transition in nested setups. When a hero won't fly, it's almost always tags or a missing destination — check those before anything else. Done well, shared-element transitions are one of the cheapest ways to make a Flutter app feel deliberately crafted.

## Resources

- [Hero animations (Flutter docs)](https://docs.flutter.dev/ui/animations/hero-animations)
- [Hero widget API reference](https://api.flutter.dev/flutter/widgets/Hero-class.html)
- [MaterialRectArcTween API reference](https://api.flutter.dev/flutter/material/MaterialRectArcTween-class.html)
- [HeroController API reference](https://api.flutter.dev/flutter/widgets/HeroController-class.html)
- [Material motion: shared axis and container transform](https://m3.material.io/styles/motion/transitions/transition-patterns)
