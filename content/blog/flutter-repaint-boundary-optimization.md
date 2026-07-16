---
title: "Optimizing Repaints with RepaintBoundary"
slug: "flutter-repaint-boundary-optimization"
description: "RepaintBoundary isolates paint layers so sibling animations do not force full-screen repaints. When to wrap, when to skip, and how to verify in DevTools."
datePublished: "2025-02-15"
dateModified: "2025-02-15"
tags: ["Flutter", "Dart", "Performance", "Mobile"]
keywords: "RepaintBoundary Flutter, Flutter repaint optimization, layer isolation Flutter, raster thread performance, debug repaint rainbow"
faq:
  - q: "Does RepaintBoundary always improve performance?"
    a: "No. Each boundary creates a separate compositing layer with memory cost. Wrapping every widget adds overhead without benefit. Use boundaries where profiling shows frequent repaints of a small subtree while siblings stay static."
  - q: "What is the difference between rebuild and repaint?"
    a: "Rebuild runs build() and may update layout. Repaint records new display lists and rasterizes pixels. A widget can repaint without rebuilding if a sibling triggers layer invalidation. RepaintBoundary limits repaint propagation, not build()."
  - q: "How do I see what is repainting?"
    a: "Enable debugRepaintRainbowEnabled in debug builds—each repaint tints widgets a different color. In DevTools Performance tab, watch raster thread time while toggling the rainbow to confirm boundaries work."
---

The loading spinner sat in the corner. The entire dashboard flashed rainbow colors in debug repaint mode every rotation frame—not just the spinner. One `RepaintBoundary` around the animated icon dropped raster time from 11 ms to 2 ms because the GPU stopped re-compositing four chart layers that had not changed.

`RepaintBoundary` tells Flutter's rendering pipeline to cache a subtree as a separate layer. When something outside the boundary repaints, cached content reuses prior raster output. When content inside repaints, invalidation stays contained.

## Basic usage

```dart
Column(
  children: [
    RepaintBoundary(
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, child) {
          return Transform.rotate(
            angle: _controller.value * 2 * pi,
            child: child,
          );
        },
        child: const Icon(Icons.sync, size: 48),
      ),
    ),
    const _StaticDashboardCharts(),
  ],
)
```

The charts skip raster work while the icon animates.

## When to add a boundary

Good candidates:

- Continuous animations (spinners, pulsing badges, marquee text)
- `CustomPainter` widgets updating frequently
- Video or texture regions adjacent to static UI
- Complex static headers above scrolling animated content

Poor candidates:

- Entire screens by default—memory bloat, minimal gain if whole screen animates anyway
- Widgets that repaint every frame together—boundary adds layer cost without isolation
- Tiny cheap widgets—overhead exceeds savings

## Relationship to ListView performance

List items with embedded animations should each get a boundary:

```dart
ListView.builder(
  itemBuilder: (context, index) {
    return RepaintBoundary(
      child: FeedCard(item: items[index]),
    );
  },
)
```

Scroll itself still invalidates visible items; boundaries prevent one card's GIF progress bar from repainting neighbors off-screen... partially. Combine with `cacheExtent` tuning—boundaries are not a scroll perf silver bullet.

## PictureRecorder and CustomPainter

Custom painters that repaint often benefit:

```dart
class WaveformPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) { ... }

  @override
  bool shouldRepaint(covariant WaveformPainter old) =>
      old.samples != samples;
}

RepaintBoundary(
  child: CustomPaint(
    painter: WaveformPainter(samples: data),
    size: Size.infinite,
  ),
)
```

Pair with tight `shouldRepaint` logic—false positives still repaint inside the boundary.

## Verify with debug tools

```dart
import 'package:flutter/rendering.dart';

void main() {
  debugRepaintRainbowEnabled = true;
  runApp(const MyApp());
}
```

Flashy colors = repaint that frame. After adding boundaries, static siblings should stop flashing.

Profile mode + DevTools: compare raster bar height before and after. Numbers beat rainbow guessing.

## vs Opacity and Clip

`Opacity` and `ClipRRect` often create layers implicitly—sometimes duplicating what RepaintBoundary would do, sometimes making things worse. Profile after adding visual effects; a boundary around a clipped animated child is common fix for accidental full-screen invalidation from ancestor clips.

## Common mistakes

- Wrapping `ListView` entirely—children still repaint individually; boundary at list root rarely helps scroll jank.
- Expecting boundaries to reduce **build** cost—they do not; use `const` and provider `select` for that.
- Stacking dozens of boundaries in one screen—layer explosion hurts GPU memory on low-end devices.

## Layer count budget

Each RepaintBoundary adds compositing layer. Mobile GPUs handle dozens; hundreds hurt. Audit with Flutter performance overlay "checkerboard offscreen layers" in debug.

Stacking RepaintBoundary + Opacity + ClipRRect creates multiple layers—sometimes one boundary around combined animated subtree beats three boundaries on children.

## AnimatedBuilder child parameter

```dart
AnimatedBuilder(
  animation: animation,
  child: const ExpensiveStaticChild(),
  builder: (context, child) {
    return Transform.scale(scale: animation.value, child: child);
  },
)
```

Child stays const across ticks—animation repaints only transform layer when paired with RepaintBoundary.

## CustomPainter double buffering

For charts updating at 30fps, consider throttling repaint to display refresh rate. `shouldRepaint` returning true every frame without boundary forces full chart repaint—wrap chart canvas.

## Profile on low-end hardware

RepaintBoundary savings show on devices where raster was bottleneck—flagship Mac Chrome misleading for mobile targets. Test on Pixel 4a or equivalent.

## When boundaries fail to help

If entire screen animates (hero transition full bleed), boundary at root does not isolate—optimize animation itself or reduce overlay complexity during transition.


## Interaction with Image.network

Network images decoding trigger repaints—pair `cacheWidth`/`cacheHeight` with RepaintBoundary on list items containing avatars to limit decode and repaint scope.

## DevTools verification workflow

Before/after screenshot same interaction with rainbow enabled—share before/after in PR description for perf fixes; reviewers see evidence without reproducing device lab.

## ListView cacheExtent

Increasing cacheExtent builds off-screen children—more RepaintBoundaries alive; tune cacheExtent and boundary together on parallax feeds.

## Avoid double isolation

Parent and child both with RepaintBoundary rarely needed—profile proves otherwise before stacking.

## Platform views repaint

Platform views repaint outside Flutter layer—RepaintBoundary on Flutter sibling does not isolate native map repaint; understand limit before blaming Flutter boundaries for map jank.

## Rollout guidance

Ship RepaintBoundary perf fixes behind remote config flag `perf_repaint_boundary_v2` enabling 10% canary if change touches hero screen—full rollout after 48 hours crash-free and frame time metric within 5% baseline tolerance monitored Datadog dashboard named in PR.

## Team practices

Shipping Flutter Repaint Boundary Optimization in production taught our team that documentation beats hero demos. We wrote runbooks covering failure modes, on-call steps, and rollback triggers before the second release, not after the first outage.

When reviewing PRs touching Flutter Repaint Boundary Optimization, we ask for measurable outcomes: latency, crash rate, or support ticket volume—not subjective feels faster. If metrics are unavailable, the PR includes a DevTools trace or load test snippet proving the change.

Onboarding engineers paste a checklist into their first Flutter Repaint Boundary Optimization PR description: environment setup verified, tests added or updated, accessibility spot-checked, and release notes drafted for user-visible changes.

We keep a living FAQ in the repo wiki for Flutter Repaint Boundary Optimization questions repeated in Slack more than twice. FAQ entries link to source files and Slack threads, reducing tribal knowledge and repeated explanations in code review.

## Resources

- [RepaintBoundary API reference](https://api.flutter.dev/flutter/widgets/RepaintBoundary-class.html)
- [Flutter rendering pipeline](https://docs.flutter.dev/perf/rendering-performance)
- [Improving rendering performance](https://docs.flutter.dev/perf/rendering-performance)
- [debugRepaintRainbowEnabled](https://api.flutter.dev/flutter/rendering/debugRepaintRainbowEnabled.html)
- [Flutter performance profiling](https://docs.flutter.dev/perf/ui-performance)
