---
title: "Custom RenderObjects and CustomPaint in Flutter"
slug: "flutter-custom-renderobjects-paint"
description: "When widgets aren't enough: using CustomPaint and custom RenderObjects in Flutter, the layout and paint protocol, hit testing, and when each fits."
datePublished: "2026-05-16"
dateModified: "2026-05-16"
tags: ["Flutter", "Dart", "Performance", "UI"]
keywords: "Flutter RenderObject, CustomPaint, custom rendering Flutter, layout protocol, paint canvas Flutter"
faq:
  - q: "What is a RenderObject in Flutter?"
    a: "A RenderObject is the low-level object that actually performs layout, painting, and hit testing in Flutter's rendering pipeline. Widgets are lightweight configuration; elements manage the tree; but RenderObjects do the real geometric work — measuring constraints, positioning children, and drawing to the canvas. Most apps never touch them directly, but they are what every widget ultimately produces."
  - q: "When should I use CustomPaint instead of a custom RenderObject?"
    a: "Use CustomPaint when you only need to draw — charts, gauges, signatures, decorative shapes — with no custom child layout. It hands you a Canvas and a size and stays out of the way. Reach for a custom RenderObject when you need to control how children are measured and positioned, implement a bespoke layout algorithm, or do custom hit testing."
  - q: "Is CustomPaint expensive for performance?"
    a: "CustomPaint itself is cheap; the cost is entirely in what your paint method does and how often it runs. The key optimizations are implementing shouldRepaint correctly so you only repaint when inputs change, and using RepaintBoundary to isolate frequently-animating painters from the rest of the tree. A poorly-gated painter that repaints every frame is where the cost hides."
---

Flutter's widget catalog covers a huge amount of ground, but every UI engineer eventually hits the wall: a radial gauge, a waveform, a custom chart, a node graph, a signature pad — something the built-in widgets can't express by composition alone. That's where you drop below widgets into `CustomPaint` and, one level deeper, custom `RenderObject`s. A `RenderObject` is the thing that actually measures, positions, and draws pixels in Flutter's rendering pipeline; `CustomPaint` is a friendly door into it that hands you a `Canvas` and a size. Knowing when to open which door is what separates "I fought the framework" from "I drew exactly what I wanted in fifty lines."

I reach for this layer a few times a year, usually for data visualization or a bespoke interactive control. It's less scary than its reputation, but it does demand that you understand the pipeline instead of pattern-matching on Stack Overflow.

## The three-tree pipeline

Flutter maintains three parallel trees, and understanding the split is the whole foundation. **Widgets** are immutable configuration — cheap to rebuild constantly. **Elements** are the mutable middle layer that manages lifecycle and mounts widgets to render objects. **RenderObjects** are the heavyweight layer that does layout, painting, and hit testing, and they persist across rebuilds.

The practical upshot: when you `setState` and rebuild widgets, you're not rebuilding render objects — Flutter diffs and updates them. That's why custom rendering can be fast even in an animated widget: you're mutating a long-lived render object, not recreating it. This is the same efficiency story behind [Impeller and Flutter's rendering performance](https://blog.michaelsam94.com/flutter-performance-impeller/) — the engine works hard to avoid redundant work, and custom render objects let you plug into that machinery directly.

## CustomPaint: the common case

Ninety percent of the time you don't need a custom `RenderObject` at all — you need to draw, and `CustomPaint` with a `CustomPainter` is the tool. You get a `Canvas` and a `Size`, and you draw:

```dart
class GaugePainter extends CustomPainter {
  GaugePainter(this.value);
  final double value; // 0.0 .. 1.0

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final radius = size.shortestSide / 2;
    final track = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 12
      ..color = Colors.grey.shade300;
    final fill = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 12
      ..strokeCap = StrokeCap.round
      ..color = Colors.teal;

    canvas.drawArc(Rect.fromCircle(center: center, radius: radius),
        -pi / 2, 2 * pi, false, track);
    canvas.drawArc(Rect.fromCircle(center: center, radius: radius),
        -pi / 2, 2 * pi * value, false, fill);
  }

  @override
  bool shouldRepaint(GaugePainter old) => old.value != value;
}
```

That `shouldRepaint` is the single most important line for performance. Return `true` only when a visible input changed. Get it wrong — return `true` always — and you repaint every frame regardless of whether anything moved; return `false` when something did change and you get a stale, frozen visual. I've debugged both, and the "always true" version silently eats battery in production.

## When you actually need a RenderObject

Drop to a custom `RenderObject` when `CustomPaint` can't express what you need — specifically, when you need to **lay out children** with custom logic, not just draw. Examples: a flow layout that wraps with custom rules, a chart that positions real child widgets at computed coordinates, a control with genuinely custom hit testing.

The minimal shape is a `RenderBox` subclass that implements `performLayout`, `paint`, and often `hitTest`:

```dart
class RenderTagCloud extends RenderBox
    with ContainerRenderObjectMixin<RenderBox, TagCloudParentData>,
         RenderBoxContainerDefaultsMixin<RenderBox, TagCloudParentData> {

  @override
  void performLayout() {
    var x = 0.0, y = 0.0, rowHeight = 0.0;
    var child = firstChild;
    while (child != null) {
      child.layout(constraints.loosen(), parentUsesSize: true);
      if (x + child.size.width > constraints.maxWidth) {
        x = 0; y += rowHeight; rowHeight = 0;
      }
      (child.parentData as TagCloudParentData).offset = Offset(x, y);
      x += child.size.width;
      rowHeight = max(rowHeight, child.size.height);
      child = childAfter(child);
    }
    size = constraints.constrain(Size(constraints.maxWidth, y + rowHeight));
  }

  @override
  void paint(PaintingContext context, Offset offset) =>
      defaultPaint(context, offset);

  @override
  bool hitTestChildren(BoxHitTestResult result, {required Offset position}) =>
      defaultHitTestChildren(result, position: position);
}
```

The layout protocol is the part people find intimidating, and it's actually a clean contract: **constraints go down, sizes come up, parent sets position.** The parent passes `BoxConstraints` to each child's `layout`, the child picks a `size` within them, and the parent then sets each child's `offset` via its `parentData`. Once that sentence clicks, the whole system stops being mysterious.

## Layout, paint, and hit testing as separate phases

A subtle point that trips people up: layout, paint, and hit testing are distinct passes, and mixing their concerns causes bugs. `performLayout` decides geometry and must not paint. `paint` draws and must not change layout (calling anything that marks needs-layout during paint is a framework error). `hitTest` decides what receives a pointer event and should mirror your paint geometry.

If a custom control looks right but doesn't respond to taps in part of its area, the culprit is almost always a `hitTest` that doesn't match where you painted. Keep the three in sync and the object behaves; let them drift and you get invisible dead zones or ghost taps.

## Performance discipline

Custom rendering is powerful enough to hurt you. Three rules I hold to:

- **Gate repaints.** Correct `shouldRepaint` / `markNeedsPaint` usage is non-negotiable. Repaint only on real change.
- **Isolate with RepaintBoundary.** Wrap a frequently-animating painter in a `RepaintBoundary` so its repaints don't invalidate siblings. This one change often fixes jank in an animated chart.
- **Separate layout from paint invalidation.** Use `markNeedsPaint` when only the visual changed and `markNeedsLayout` only when geometry changed — the latter is far more expensive.

There's overlap in mindset with local widget state here; a painter driven by an animation controller pairs naturally with the lifecycle tools I compared in [Flutter hooks versus StatefulWidget](https://blog.michaelsam94.com/flutter-hooks-vs-stateful/), where `useAnimationController` cleanly feeds a repaint.

My rule of thumb after years of this: start with `CustomPaint`. Only climb down to a full `RenderObject` when you genuinely need custom child layout or hit testing, because you trade a lot of ergonomics for that control. But when you do need it, nothing else in Flutter gives you the same precision — you're drawing and measuring exactly what the engine draws and measures, with no widget abstraction in the way.

## Resources

- [Flutter CustomPaint API documentation](https://api.flutter.dev/flutter/widgets/CustomPaint-class.html)
- [RenderObject API documentation](https://api.flutter.dev/flutter/rendering/RenderObject-class.html)
- [Flutter rendering pipeline (architectural overview)](https://docs.flutter.dev/resources/architectural-overview)
- [Flutter engine architecture](https://github.com/flutter/flutter/wiki/The-Engine-architecture)
- [dart:ui Canvas reference](https://api.flutter.dev/flutter/dart-ui/Canvas-class.html)
