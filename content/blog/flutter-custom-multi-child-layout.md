---
title: "CustomMultiChildLayout in Practice"
slug: "flutter-custom-multi-child-layout"
description: "CustomMultiChildLayout lets you position Flutter children relative to each other's sizes without a RenderObject. A practical guide to delegates, layoutChild, and positionChild."
datePublished: "2024-10-16"
dateModified: "2024-10-16"
tags: ["Flutter", "Dart", "UI", "Layout"]
keywords: "CustomMultiChildLayout, MultiChildLayoutDelegate, Flutter custom layout, LayoutId, positionChild, layoutChild"
faq:
  - q: "What is CustomMultiChildLayout used for in Flutter?"
    a: "CustomMultiChildLayout lets you lay out a fixed set of children where each child's position can depend on the sizes of other children, without writing a full RenderObject. You give each child a LayoutId and implement a MultiChildLayoutDelegate that measures and positions them. It sits between Stack (position-only) and a custom RenderObject (full control) in power and complexity."
  - q: "When should I use CustomMultiChildLayout instead of Stack?"
    a: "Use it when one child's position must depend on another child's measured size — for example centering a badge over a dynamically sized card, or placing a label above a bar whose height you only know after layout. A Stack with Positioned works when coordinates are known ahead of time, but it cannot react to sibling sizes. CustomMultiChildLayout gives you that cross-child dependency cheaply."
  - q: "How does layoutChild and positionChild work in a delegate?"
    a: "Inside performLayout you call layoutChild(id, constraints) exactly once per child, which returns that child's Size after laying it out under your constraints. You then call positionChild(id, offset) to place it. The returned sizes let you compute positions that depend on other children, and the delegate's getSize gives the overall size the parent will occupy."
---

`CustomMultiChildLayout` is the tool for when you need to position a set of Flutter widgets relative to each other's *measured sizes* — something a `Stack` can't do because `Positioned` only knows the coordinates you hardcode, not how big a sibling turned out to be. It gives you cross-child layout dependencies (put this label centered above that bar whose height I only learn at layout time) without dropping all the way down to a custom `RenderObject`. It's the middle rung of Flutter's layout ladder, and it's underused because most people jump straight from `Stack` to "I guess I need a RenderObject."

I reach for it maybe once per app — a speedometer with a needle and labels, a chat bubble with a tail anchored to a dynamically sized body, an annotation layer over a chart. Each time, `Stack` couldn't express the size dependency and a full `RenderObject` would've been overkill.

## Where it sits on the ladder

- **`Stack` + `Positioned`** — you know the coordinates in advance. Fast, simple, no size feedback between children.
- **`CustomMultiChildLayout`** — a fixed, known set of children, and positions may depend on siblings' sizes. A delegate does the measuring and placing.
- **Custom [`RenderObject`](https://blog.michaelsam94.com/flutter-render-object-widgets/)** — dynamic child counts, custom hit testing, custom painting, or performance-critical layout. Maximum power, maximum code.

If your case fits the middle, `CustomMultiChildLayout` is dramatically less code than a render object while giving you the size-dependency the `Stack` lacks.

## The two moving parts

You need two things: the `CustomMultiChildLayout` widget with children each tagged by a `LayoutId`, and a `MultiChildLayoutDelegate` that does the actual work.

```dart
CustomMultiChildLayout(
  delegate: _GaugeLayout(),
  children: [
    LayoutId(id: _Slot.dial, child: const Dial()),
    LayoutId(id: _Slot.needle, child: const Needle()),
    LayoutId(id: _Slot.label, child: Text('$speed mph')),
  ],
);

enum _Slot { dial, needle, label }
```

The `id` is how the delegate refers to each child — I use an `enum` rather than raw strings so a typo is a compile error, not a silent no-op.

## Writing the delegate

The delegate overrides two methods. `performLayout(Size size)` receives the overall size available and is where you measure and place each child. `shouldRelayout` tells Flutter when to re-run.

```dart
class _GaugeLayout extends MultiChildLayoutDelegate {
  @override
  void performLayout(Size size) {
    // Lay out the dial to fill available space; capture its size.
    final dialSize = layoutChild(
      _Slot.dial,
      BoxConstraints.tight(size),
    );
    positionChild(_Slot.dial, Offset.zero);

    // Needle: loosely constrained, centered on the dial.
    final needleSize = layoutChild(_Slot.needle, BoxConstraints.loose(size));
    positionChild(
      _Slot.needle,
      Offset(
        (dialSize.width - needleSize.width) / 2,
        (dialSize.height - needleSize.height) / 2,
      ),
    );

    // Label: measured, then placed just below the dial's center.
    final labelSize = layoutChild(_Slot.label, BoxConstraints.loose(size));
    positionChild(
      _Slot.label,
      Offset(
        (size.width - labelSize.width) / 2,
        dialSize.height * 0.62,
      ),
    );
  }

  @override
  bool shouldRelayout(covariant _GaugeLayout oldDelegate) => false;
}
```

The critical rules the framework enforces:

1. **Call `layoutChild(id, constraints)` exactly once per child.** It lays the child out and returns its `Size`. Skip a child and you get an assertion; call it twice and you get an assertion.
2. **`positionChild` places the child** using the offsets you compute — often from sizes you got back from earlier `layoutChild` calls. That's the whole point: the label's position uses `labelSize` and `dialSize` together.
3. Give every child an id that matches a `LayoutId`, or it won't be laid out.

## Sizing the whole thing

By default the `CustomMultiChildLayout` takes the biggest size its constraints allow. To make its own size depend on the children, override `getSize`:

```dart
@override
Size getSize(BoxConstraints constraints) => constraints.constrain(
      const Size(240, 240),
    );
```

If you need the container to size to its children, you can't measure them in `getSize` (children aren't available there), so this is one limitation: the overall size is computed from constraints, not from child sizes. When you truly need "wrap to children," that's the signal you've outgrown this tool and should consider a `RenderObject`.

## Passing data into the delegate

Delegates are recreated on rebuild, so pass dynamic values through the constructor and use them in `shouldRelayout`:

```dart
class _GaugeLayout extends MultiChildLayoutDelegate {
  _GaugeLayout({required this.angle});
  final double angle;

  @override
  bool shouldRelayout(covariant _GaugeLayout old) => old.angle != angle;
}
```

`shouldRelayout` returning `false` when nothing changed is a real performance lever — it skips relayout entirely. Return `true` only when a field that affects positioning actually changed. Getting this wrong (always returning `true`) means you relayout every frame; returning `false` when you shouldn't means stale positions.

## When I'd choose something else

- **Just drawing shapes/lines** (no child widgets to position)? Use a [`CustomPainter`](https://blog.michaelsam94.com/flutter-canvas-custom-painter/) — it's for pixels, not child layout.
- **Positions are static**? A `Stack` with `Positioned`/`Align` is simpler and I'd use it.
- **Dynamic child count, custom hit testing, or you're painting *and* laying out children together**? Now it's genuinely a `RenderObject`.

The sweet spot is narrow but real: a *known* set of children whose placement depends on each other's sizes.

## Debugging tips

Turn on `debugPaintSizeEnabled` to see the boxes each child actually got. If a child vanishes, you almost certainly forgot its `layoutChild` call or the `id` doesn't match a `LayoutId`. If positions look off, print the sizes returned by `layoutChild` — the bug is usually an offset computed from the wrong size or before that child was measured. And remember measurement order matters: you can only use a child's size *after* you've called `layoutChild` for it, so order your calls so dependencies come first.

## What I'd take away

`CustomMultiChildLayout` fills the gap between `Stack` and a custom `RenderObject`: use it when a fixed set of children need to be positioned based on each other's measured sizes. Tag children with `LayoutId`s (enums, not strings), call `layoutChild` once per child to get its size, then `positionChild` using those sizes, and gate rework through `shouldRelayout`. It's a fraction of the code of a render object and expresses cross-child size dependencies that `Stack` simply can't — a small, sharp tool worth knowing exists before you over-engineer.

## Resources

- [CustomMultiChildLayout API reference](https://api.flutter.dev/flutter/widgets/CustomMultiChildLayout-class.html)
- [MultiChildLayoutDelegate API reference](https://api.flutter.dev/flutter/rendering/MultiChildLayoutDelegate-class.html)
- [LayoutId API reference](https://api.flutter.dev/flutter/widgets/LayoutId-class.html)
- [Understanding constraints (Flutter docs)](https://docs.flutter.dev/ui/layout/constraints)
- [Layout widgets catalog (Flutter docs)](https://docs.flutter.dev/ui/widgets/layout)
