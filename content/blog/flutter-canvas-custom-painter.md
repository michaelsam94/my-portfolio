---
title: "Custom Painting with CustomPainter"
slug: "flutter-canvas-custom-painter"
description: "Draw charts, gauges, and custom shapes with CustomPainter: Canvas API, shouldRepaint optimization, RepaintBoundary, and hit testing custom graphics."
datePublished: "2024-10-01"
dateModified: "2024-10-01"
tags: ["Flutter", "Dart"]
keywords: "Flutter CustomPainter, Canvas API, custom paint widget, shouldRepaint, Flutter charts custom"
faq:
  - q: "When should I use CustomPainter in Flutter?"
    a: "Use CustomPainter when built-in widgets can't express your visual—sparkline charts, circular progress gauges, signature pads, custom gradients, or game sprites. If Stack, Container decorations, or CustomClipper suffice, prefer those; CustomPainter trades convenience for full Canvas control and requires manual repaint optimization."
  - q: "What does shouldRepaint do in CustomPainter?"
    a: "shouldRepaint compares the old and new painter delegate and returns true if paint must rerun. Returning true unconditionally causes unnecessary repaints every frame. Return true only when visual data changed—compare colors, paths, or animation values in the delegate."
  - q: "How do I make CustomPainter widgets respond to taps?"
    a: "CustomPaint ignores gestures by default. Wrap in GestureDetector and implement hit testing manually—track shape bounds in the painter or use Path.contains on local coordinates converted from global tap position. For complex shapes, store hit regions in a List<Path> during paint and test against them in onTapDown."
---

Stock charts in our dashboard needed gradient fills under bezier curves, dashed gridlines, and touch crosshairs—none of which `fl_chart` configured cleanly without fighting the library. We dropped to `CustomPainter` and owned every pixel. The Canvas API mirrors HTML5 canvas: paths, paints, transforms, clips. The catch is you're responsible for repaint efficiency and accessibility, which widgets handle for free.

## CustomPaint widget structure

```dart
CustomPaint(
  painter: LineChartPainter(
    dataPoints: values,
    lineColor: Colors.blue,
  ),
  size: Size.infinite, // fills parent constraints
  child: Container(), // optional foreground widget
)
```

Two painter slots:

- **`painter`** — drawn behind child.
- **`foregroundPainter`** — drawn in front of child.

Implement `CustomPainter`:

```dart
class LineChartPainter extends CustomPainter {
  LineChartPainter({required this.dataPoints, required this.lineColor});

  final List<double> dataPoints;
  final Color lineColor;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = lineColor
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke;

    final path = Path();
    for (var i = 0; i < dataPoints.length; i++) {
      final x = i / (dataPoints.length - 1) * size.width;
      final y = size.height - (dataPoints[i] * size.height);
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant LineChartPainter oldDelegate) {
    return oldDelegate.dataPoints != dataPoints ||
        oldDelegate.lineColor != lineColor;
  }
}
```

## Canvas essentials

**Coordinates:** origin top-left, x right, y down.

**Common operations:**

```dart
canvas.drawLine(Offset(0, h), Offset(w, h), gridPaint);
canvas.drawRect(Rect.fromLTWH(x, y, w, h), fillPaint);
canvas.drawCircle(center, radius, paint);
canvas.drawPath(path, paint);

canvas.clipRect(Rect.fromLTWH(0, 0, size.width, size.height));
canvas.save();
canvas.translate(dx, dy);
canvas.rotate(angle);
canvas.restore();
```

**Gradients:**

```dart
final shader = LinearGradient(
  begin: Alignment.topCenter,
  end: Alignment.bottomCenter,
  colors: [Colors.blue.withOpacity(0.3), Colors.transparent],
).createShader(Rect.fromLTWH(0, 0, size.width, size.height));

final fillPaint = Paint()..shader = shader;
canvas.drawPath(areaPath, fillPaint);
```

## shouldRepaint and performance

Bad `shouldRepaint` kills frame rates:

```dart
// WRONG — repaints every frame even when static
bool shouldRepaint(CustomPainter old) => true;

// RIGHT — compare meaningful fields
@override
bool shouldRepaint(covariant GaugePainter old) {
  return old.progress != progress || old.theme != theme;
}
```

Wrap animated painters in `RepaintBoundary` to isolate repaints:

```dart
RepaintBoundary(
  child: CustomPaint(
    painter: AnimatedGaugePainter(progress: animation.value),
    size: const Size(200, 200),
  ),
)
```

For static complex paint, cache to `Picture`:

```dart
Picture? _cachedPicture;

@override
void paint(Canvas canvas, Size size) {
  if (_cachedPicture == null || _size != size) {
    final recorder = PictureRecorder();
    final c = Canvas(recorder);
    _drawStaticGrid(c, size);
    _cachedPicture = recorder.endRecording();
    _size = size;
  }
  canvas.drawPicture(_cachedPicture!);
  _drawDynamicData(canvas, size); // only changing parts
}
```

## Animation integration

Drive painters with `AnimationController`:

```dart
class _GaugeState extends State<Gauge> with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (_, __) => CustomPaint(
        painter: GaugePainter(progress: _controller.value),
        size: const Size(120, 120),
      ),
    );
  }
}
```

Listenable pattern avoids rebuilding parent widgets:

```dart
class GaugePainter extends CustomPainter {
  GaugePainter({required Listenable repaint}) : super(repaint: repaint);
}
```

Pass the `AnimationController` as `repaint`—Flutter repaints when it ticks.

## Hit testing and gestures

```dart
class TappableChart extends StatefulWidget {
  @override
  State<TappableChart> createState() => _TappableChartState();
}

class _TappableChartState extends State<TappableChart> {
  final _painter = InteractiveChartPainter();

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: (details) {
        final box = context.findRenderObject() as RenderBox;
        final local = box.globalToLocal(details.globalPosition);
        final index = _painter.hitTest(local);
        if (index != null) setState(() => _painter.selectedIndex = index);
      },
      child: CustomPaint(painter: _painter, size: Size.infinite),
    );
  }
}
```

Store bar rects during `paint` for accurate hit regions.

## Accessibility

CustomPaint is invisible to screen readers. Wrap with semantics:

```dart
Semantics(
  label: 'Chart showing revenue trend, up 12 percent this month',
  child: CustomPaint(painter: chartPainter),
)
```

Or expose custom values for adjustable charts.

### When to use a chart library instead

CustomPainter shines for one or two bespoke visuals. Reach for `fl_chart`, `syncfusion_flutter_charts`, or `graphic` when you need axes, legends, zoom, and tooltip infrastructure. Building that on raw Canvas is weeks of work.

### LayoutBuilder integration

CustomPaint without explicit size needs bounded constraints from parent:

```dart
LayoutBuilder(
  builder: (context, constraints) {
    return CustomPaint(
      painter: SparklinePainter(data: values),
      size: Size(constraints.maxWidth, 120),
    );
  },
)
```

Unbounded height CustomPaint in Column causes layout exceptions. For responsive charts, pass size into painter and recompute path on didChangeDependencies when MediaQuery size class changes.

RepaintBoundary around static CustomPaint layers in animated screens isolates repaints to moving elements only. Profile with Performance overlay—custom painters repainting every frame without shouldRepaint optimization show as expensive Layer blocks in DevTools timeline.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

Schedule a quarterly review of this implementation against current SDK release notes—Flutter and cloud providers ship breaking changes on six-month cadences, and assumptions that held last year may need adjustment. Capture before-and-after metrics when you change configuration so regressions are obvious in retrospect rather than debated from memory.

## Resources

- [CustomPainter class](https://api.flutter.dev/flutter/rendering/CustomPainter-class.html)
- [Canvas class API](https://api.flutter.dev/flutter/dart-ui/Canvas-class.html)
- [CustomPaint widget](https://api.flutter.dev/flutter/widgets/CustomPaint-class.html)
- [Flutter Custom Paint introduction](https://docs.flutter.dev/ui/layout/custom-paint)
- [RepaintBoundary API](https://api.flutter.dev/flutter/widgets/RepaintBoundary-class.html)
