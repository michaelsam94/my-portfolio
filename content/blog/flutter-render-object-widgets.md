---
title: "When to Write a RenderObject Widget in Flutter"
slug: "flutter-render-object-widgets"
description: "Most Flutter UI never needs a RenderObject. Here's when custom layout and painting justify dropping below the widget layer, and how RenderBox layout actually works."
datePublished: "2024-10-15"
dateModified: "2024-10-15"
tags: ["Flutter", "Dart", "UI", "Architecture"]
keywords: "Flutter RenderObject, RenderBox, custom layout Flutter, LeafRenderObjectWidget, performLayout, constraints go down sizes go up"
faq:
  - q: "When should I write a custom RenderObject in Flutter?"
    a: "Write a custom RenderObject only when you need layout or painting behavior that cannot be composed from existing widgets, and when performance demands avoiding the overhead of deeply nested widgets. Most bespoke visuals are better done with CustomPaint or CustomMultiChildLayout. Reach for a RenderObject when you need full control over how children are measured, positioned, hit-tested, and painted together — for example a specialized chart layout or a physics-based container."
  - q: "What is the difference between a Widget, an Element, and a RenderObject?"
    a: "A Widget is an immutable configuration description; an Element is the mutable instantiation that tracks position in the tree and manages lifecycle; a RenderObject is the object that actually does layout, painting, and hit testing. Widgets are cheap and rebuilt often, Elements are reused across rebuilds, and RenderObjects hold the expensive geometry. Custom RenderObjects let you plug directly into that bottom layer."
  - q: "What does 'constraints go down, sizes go up' mean in Flutter layout?"
    a: "It describes Flutter's single-pass layout: a parent passes BoxConstraints down to each child, the child chooses a size within those constraints and reports it back up, and then the parent positions the child. A RenderObject participates by reading its constraints in performLayout, sizing its children, setting its own size, and recording child offsets. Understanding this protocol is the prerequisite for writing correct custom layout."
---

Writing a custom `RenderObject` in Flutter is the right call far less often than people think. Ninety-plus percent of "custom" UI is better built by composing existing widgets, and most bespoke drawing belongs in `CustomPaint`. You drop to a `RenderObject` only when you need genuine control over how multiple children are measured, positioned, hit-tested, and painted *together* — and when the widget-composition version is either impossible or measurably too slow. This post is as much about *not* writing one as about how to when you must.

I've written maybe a handful of production `RenderObject`s in years of Flutter — a specialized timeline layout, a chart axis system — and every one earned its place by doing something the widget layer genuinely couldn't. I've also reviewed plenty that should have been a `Stack` and a `CustomPaint`. Knowing the difference saves weeks.

## The three trees

Flutter runs three parallel trees, and understanding them tells you where a `RenderObject` sits:

- **Widgets** are immutable configuration. They're cheap and thrown away and rebuilt constantly.
- **Elements** are the mutable glue. They persist across rebuilds, hold the tree position, and manage lifecycle.
- **RenderObjects** do the real work: layout, painting, hit testing. They hold the expensive geometry and are updated in place, not rebuilt.

When you write `Container` or `Padding`, you're producing widgets that ultimately configure render objects like `RenderPadding`. Writing a custom `RenderObject` means creating one of these bottom-layer workers yourself and exposing it through a thin widget wrapper.

## The layout protocol you must internalize

Flutter layout is a single pass with one rule: **constraints go down, sizes go up, parent sets position.** A parent hands each child a `BoxConstraints` (min/max width and height). The child picks a `Size` within those constraints and returns it. The parent then decides *where* to place the child. That's it — no multi-pass reflow, which is why Flutter layout is fast.

A `RenderBox` (the box-model `RenderObject`) participates by overriding `performLayout`:

```dart
class RenderSquareBox extends RenderBox {
  @override
  void performLayout() {
    // Read my constraints, choose a size, report it.
    final side = constraints.constrainWidth(
      constraints.hasBoundedWidth ? constraints.maxWidth : 100,
    );
    size = constraints.constrain(Size(side, side));
  }

  @override
  void paint(PaintingContext context, Offset offset) {
    final rect = offset & size;
    context.canvas.drawRect(rect, Paint()..color = const Color(0xFF3366FF));
  }
}
```

For a leaf like this you also override `computeDryLayout` (size without side effects, used by intrinsics) and often `hitTestSelf`. The discipline is that `performLayout` must *always* set `size`, and must only size children by calling `child.layout(childConstraints, parentUsesSize: true)`.

## Wiring it to a widget

A `RenderObject` isn't a widget; you expose it through a `RenderObjectWidget` subclass. For a leaf (no children) that's `LeafRenderObjectWidget`; for one child, `SingleChildRenderObjectWidget`; for many, `MultiChildRenderObjectWidget`.

```dart
class SquareBox extends LeafRenderObjectWidget {
  const SquareBox({super.key});

  @override
  RenderSquareBox createRenderObject(BuildContext context) => RenderSquareBox();

  @override
  void updateRenderObject(BuildContext context, RenderSquareBox renderObject) {
    // Push changed widget fields onto the render object here.
  }
}
```

`createRenderObject` builds it once; `updateRenderObject` is called on every rebuild to copy the widget's (immutable) fields onto the (persistent) render object. Forgetting to mark the render object dirty in a setter — `markNeedsLayout()` or `markNeedsPaint()` — is the number-one bug: you change a value and nothing redraws.

## Children and parent data

Multi-child render objects store per-child layout info in `parentData`. You set up a `ContainerRenderObjectMixin` and a custom `ParentData` type to record each child's offset:

```dart
class _MyParentData extends ContainerBoxParentData<RenderBox> {}
```

Then `performLayout` iterates children, lays each one out, and writes its position into `child.parentData.offset`. `paint` walks the same children and paints each at its recorded offset. This is exactly how `Row`, `Column`, and `Stack` work internally.

## When to actually reach for it

Here's my decision list, in order of preference:

1. **Compose widgets.** Can `Stack`, `Row`, `Column`, `Align`, `Flexible`, `Wrap`, `Positioned` express it? If yes, stop here.
2. **`CustomMultiChildLayout`.** Need custom positioning of a known set of children based on each other's sizes? Use a delegate — no `RenderObject` required. I cover this in [CustomMultiChildLayout in practice](https://blog.michaelsam94.com/flutter-custom-multi-child-layout/).
3. **`CustomPaint`.** Purely drawing, no child layout? A [CustomPainter](https://blog.michaelsam94.com/flutter-canvas-custom-painter/) is the right tool.
4. **Custom `RenderObject`.** Only when you need custom *layout of children* combined with custom *painting and hit testing*, or when the composed version is too deep/slow to hit your frame budget.

The performance case is real but narrow: a `RenderObject` collapses what might be a dozen nested widgets into one layout node, which matters when it's rebuilt thousands of times (a chart with many series, a custom scrollable). For a one-off screen, that overhead is noise.

## Testing and debugging

Custom render objects need custom care. Use `debugPaintSizeEnabled = true` to visualize the boxes you're producing, and write golden tests that pump the widget and assert on the rendered pixels. Verify behavior under both bounded and unbounded constraints — a render object that assumes `maxWidth` is finite will throw the infamous "unbounded constraints" error the moment someone drops it in a `Row` or a scroll view. And implement intrinsics (`computeMinIntrinsicWidth` and friends) if your object might be used where intrinsics are queried, or you'll get confusing assertion failures.

## What I'd take away

A custom `RenderObject` is the most powerful and least frequently needed tool in Flutter's UI toolbox. Exhaust composition, `CustomMultiChildLayout`, and `CustomPaint` first. When you do need one, internalize "constraints down, sizes up, parent positions," always set `size` in `performLayout`, remember `markNeedsLayout`/`markNeedsPaint` in your setters, and test against unbounded constraints. Used surgically, it lets you build layout and rendering the widget layer simply can't express — and used indiscriminately, it's a maintenance tax you'll regret.

## Resources

- [Flutter architectural overview: rendering](https://docs.flutter.dev/resources/architectural-overview)
- [RenderBox API reference](https://api.flutter.dev/flutter/rendering/RenderBox-class.html)
- [Understanding constraints (Flutter docs)](https://docs.flutter.dev/ui/layout/constraints)
- [LeafRenderObjectWidget API reference](https://api.flutter.dev/flutter/widgets/LeafRenderObjectWidget-class.html)
- [Flutter's layout: how it works (Flutter Medium)](https://medium.com/flutter/flutter-a-hands-on-look-at-render-objects-8f1a8d9a7f0b)
