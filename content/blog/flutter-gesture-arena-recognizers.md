---
title: "Custom Gesture Recognizers"
slug: "flutter-gesture-arena-recognizers"
description: "Win the Flutter gesture arena: custom Recognizers, RawGestureDetector, pointer routing, and resolving conflicts between scroll, tap, and drag."
datePublished: "2024-11-18"
dateModified: "2024-11-18"
tags: ["Flutter", "Dart"]
keywords: "Flutter gesture arena, custom gesture recognizer, RawGestureDetector, pointer events Flutter, gesture conflict"
faq:
  - q: "What is the gesture arena in Flutter?"
    a: "When multiple gesture recognizers detect the same pointer down event, Flutter holds a gesture arena where recognizers compete. The first to accept or the last remaining wins; losers must reject. This resolves conflicts like a button inside a scroll view—scroll vs tap compete until movement determines the winner."
  - q: "When do I need a custom gesture recognizer?"
    a: "When built-in GestureDetector callbacks don't match your interaction—multi-finger rotation, long-press with movement threshold, drawing signatures, or competing with parent scroll views on specific conditions. Custom recognizers extend GestureRecognizer and participate in the arena explicitly."
  - q: "How do I fix gesture conflicts in Flutter?"
    a: "Use Listener for raw pointer events bypassing the arena, RawGestureDetector with custom recognizer factories, or adjust recognizer priority with team: 'vertical' on pan gestures. ExcludeAbsorbPointer, IgnorePointer, and NotificationListener<OverscrollIndicatorNotification> also help in specific layouts."
---

The map marker wouldn't drag because the `PageView` underneath kept winning the gesture arena. `GestureDetector.onPanUpdate` never fired. Flutter's gesture system is elegant once you understand the arena—multiple recognizers enter on pointer down, one wins after movement thresholds—but opaque until you read the source or build a custom recognizer. That afternoon fixing map drag taught me more about pointer routing than a year of `onTap` handlers.

## How the gesture arena works

1. **PointerDown** — interested recognizers join the arena.
2. **PointerMove** — recognizers declare intent (pan accepted, tap still pending).
3. **Resolution** — one wins; others reject; winner handles remaining events.
4. **PointerUp** — gesture completes or cancels.

`ListView` scroll and child `InkWell` tap compete: small movement → scroll wins; stationary release → tap wins.

Debug arena decisions:

```dart
debugPrintGestureArenaDiagnostics = true;
```

## When GestureDetector isn't enough

`GestureDetector` wraps common recognizers with convenient callbacks. Limits:

- Can't customize win/loss conditions.
- Can't register multiple recognizers of same type with different configs.
- Hard to coordinate simultaneous pan + scale.

Enter `RawGestureDetector`:

```dart
RawGestureDetector(
  gestures: {
    LongPressGestureRecognizer:
        GestureRecognizerFactoryWithHandlers<LongPressGestureRecognizer>(
      () => LongPressGestureRecognizer(duration: const Duration(seconds: 2)),
      (LongPressGestureRecognizer instance) {
        instance.onLongPress = () => debugPrint('Long press!');
      },
    ),
  },
  child: Container(width: 200, height: 200, color: Colors.blue),
)
```

## Custom GestureRecognizer

Double-tap-with-hold recognizer sketch:

```dart
class DoubleTapHoldRecognizer extends OneSequenceGestureRecognizer {
  DoubleTapHoldRecognizer({required this.onDoubleTapHold});

  final VoidCallback onDoubleTapHold;
  int _tapCount = 0;
  Timer? _resetTimer;

  @override
  void addAllowedPointer(PointerDownEvent event) {
    startTrackingPointer(event.pointer);
    _tapCount++;
    _resetTimer?.cancel();
    _resetTimer = Timer(const Duration(milliseconds: 300), () {
      _tapCount = 0;
    });
    if (_tapCount == 2) {
      resolve(GestureDisposition.accepted);
      onDoubleTapHold();
      _tapCount = 0;
    }
  }

  @override
  void handleEvent(PointerEvent event) {
    if (event is PointerUpEvent) {
      stopTrackingPointer(event.pointer);
    }
  }

  @override
  void didStopTrackingLastPointer(int pointer) {}

  @override
  String get debugDescription => 'doubleTapHold';
}
```

Register via `RawGestureDetector` factory map.

## Winning against scroll views

**Horizontal drag inside vertical scroll:**

```dart
GestureDetector(
  onHorizontalDragUpdate: (details) => _handleDrag(details),
  behavior: HitTestBehavior.opaque,
  child: child,
)
```

Pan recognizer with horizontal slop may beat vertical scroll if movement is primarily horizontal.

**Eager recognizer** — accepts immediately:

```dart
class EagerTapRecognizer extends TapGestureRecognizer {
  @override
  void handleTapDown({required PointerDownEvent down}) {
    resolve(GestureDisposition.accepted);
    super.handleTapDown(down: down);
  }
}
```

Use sparingly—breaks scroll if abused.

**Listener for raw pointers** — bypasses arena entirely:

```dart
Listener(
  onPointerDown: (e) => _startDraw(e.localPosition),
  onPointerMove: (e) => _continueDraw(e.localPosition),
  onPointerUp: (e) => _endDraw(),
  child: CustomPaint(painter: signaturePainter),
)
```

Drawing and signature pads typically use `Listener`.

## Multi-touch with ScaleGestureRecognizer

Pinch and rotate:

```dart
GestureDetector(
  onScaleStart: (details) => _baseScale = _currentScale,
  onScaleUpdate: (details) {
    setState(() {
      _currentScale = _baseScale * details.scale;
      _rotation = details.rotation;
    });
  },
  child: Transform.scale(
    scale: _currentScale,
    child: Transform.rotate(angle: _rotation, child: image),
  ),
)
```

`ScaleGestureRecognizer` handles two-pointer arena coordination.

## PointerInterceptor for web

Flutter web overlays HTML elements steal pointer events. `pointer_interceptor` package wraps widgets to capture events before they pass through to DOM underneath.

### Testing gestures

Widget tests:

```dart
testWidgets('drag updates position', (tester) async {
  await tester.pumpWidget(MyDraggable());
  final center = tester.getCenter(find.byType(MyDraggable));
  await tester.dragFrom(center, const Offset(100, 0));
  await tester.pumpAndSettle();
  expect(find.text('Dragged'), findsOneWidget);
});
```

Custom recognizers may need lower-level `TestGesture`:

```dart
final gesture = await tester.startGesture(touch);
await gesture.moveBy(const Offset(50, 0));
await gesture.up();
```

### Debugging checklist

1. Parent absorbing gestures? — check `AbsorbPointer`, `IgnorePointer`.
2. Hit test behavior — `HitTestBehavior.translucent` vs `opaque`.
3. Scrollable ancestor winning? — try `Listener` or custom slop.
4. Web iframe/stacking — `PointerInterceptor`.
5. Arena diagnostics enabled? — read console for winner/loser.

Gesture bugs feel random until you map the arena. Custom recognizers are the escape hatch when defaults pick wrong.

### ScrollConfiguration for physics

Custom scroll behavior affects gesture competition:

```dart
ScrollConfiguration(
  behavior: const MaterialScrollBehavior().copyWith(
    dragDevices: {PointerDeviceKind.touch, PointerDeviceKind.mouse},
  ),
  child: listView,
)
```

Desktop drag-to-scroll changes pan recognizer participation—test map and canvas interactions with mouse, not only touch simulation.

Semantics and gestures interact—ExcludeSemantics on decorative overlays prevents TalkBack capturing gestures meant for parent. Custom recognizers should call resolve(GestureDisposition.rejected) when gesture clearly isn't yours to release arena for siblings faster.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

Schedule a quarterly review of this implementation against current SDK release notes—Flutter and cloud providers ship breaking changes on six-month cadences, and assumptions that held last year may need adjustment. Capture before-and-after metrics when you change configuration so regressions are obvious in retrospect rather than debated from memory.

Version-pin dependencies mentioned here in your pubspec.lock or infrastructure modules, and note the Flutter/Dart SDK constraint your team validated. Upgrading without re-running the verification steps in this article is the most common source of regressions. If something fails after an upgrade, compare release notes first, then your git history for the last known-good configuration.

## Resources

- [GestureRecognizer class](https://api.flutter.dev/flutter/gestures/GestureRecognizer-class.html)
- [RawGestureDetector API](https://api.flutter.dev/flutter/widgets/RawGestureDetector-class.html)
- [Flutter gestures introduction](https://docs.flutter.dev/ui/interactivity/gestures)
- [GestureDetector documentation](https://api.flutter.dev/flutter/widgets/GestureDetector-class.html)
- [pointer_interceptor package](https://pub.dev/packages/pointer_interceptor)
