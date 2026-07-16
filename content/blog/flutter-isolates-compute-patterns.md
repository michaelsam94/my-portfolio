---
title: "Isolate Patterns for Heavy Work"
slug: "flutter-isolates-compute-patterns"
description: "Offload CPU-heavy Dart work with isolates: compute, Isolate.run, worker pools, and avoiding jank from JSON parsing, image processing, and encryption."
datePublished: "2024-12-09"
dateModified: "2024-12-09"
tags: ["Flutter", "Dart"]
keywords: "Flutter isolates, compute function, Isolate.run, background processing Flutter, JSON parsing isolate"
faq:
  - q: "When should I use isolates in Flutter?"
    a: "Use isolates for CPU-intensive synchronous work that would block the UI thread longer than one frame—large JSON parsing, image decoding/processing, encryption, compression, complex list sorting. Async IO like HTTP requests does not need isolates; the native side handles waiting without blocking Dart UI."
  - q: "What is the difference between compute and Isolate.run?"
    a: "compute is a convenience wrapper spawning a short-lived isolate for a single callback with one message pass. Isolate.run (Dart 2.19+) provides cleaner async syntax for the same pattern. Both suit one-shot tasks; long-lived worker isolates with SendPort/RceivePort suit repeated heavy work amortizing spawn cost."
  - q: "Can isolates access Flutter widgets or BuildContext?"
    a: "No—isolates have separate memory heaps and cannot access objects from the main isolate except via message passing. Send only serializable data: primitives, typed lists, TransferableTypedData. Platform channels and plugins require RootIsolateToken setup for background isolates."
---

A 15 MB JSON catalog parse on the main isolate dropped frames to 8 FPS during startup. Moving three lines into `compute()` brought it back to 60. Isolates aren't free—spawn costs ~2 ms and copying data has overhead—but they're the correct tool when synchronous CPU work would block `SchedulerBinding` from painting frames. Most Flutter devs under-use isolates for parsing and over-use them for network calls.

## The UI thread problem

Dart on Flutter is single-threaded for UI code. Long synchronous loops block:

```dart
// BAD — blocks UI for seconds
void loadCatalog() {
  final json = await rootBundle.loadString('assets/catalog.json');
  final list = jsonDecode(json) as List; // synchronous parse
  final products = list.map((e) => Product.fromJson(e)).toList();
  setState(() => _products = products);
}
```

`jsonDecode` and `fromJson` run synchronously even inside async functions.

## compute() for one-shot work

Top-level or static function required:

```dart
List<Product> _parseProducts(String jsonString) {
  final list = jsonDecode(jsonString) as List;
  return list.map((e) => Product.fromJson(e as Map<String, dynamic>)).toList();
}

Future<void> loadCatalog() async {
  final json = await rootBundle.loadString('assets/catalog.json');
  final products = await compute(_parseProducts, json);
  setState(() => _products = products);
}
```

`compute` spawns isolate, runs function, returns result, kills isolate.

## Isolate.run (modern syntax)

```dart
Future<List<Product>> parseProductsAsync(String json) {
  return Isolate.run(() {
    final list = jsonDecode(json) as List;
    return list.map((e) => Product.fromJson(e as Map<String, dynamic>)).toList();
  });
}
```

Closures work if they don't capture non-sendable objects from outer scope.

## TransferableTypedData for large binary

Avoid copying large byte arrays:

```dart
Future<Uint8List> processImage(Uint8List input) async {
  final transferable = TransferableTypedData.fromList([input]);
  return Isolate.run(() {
    final data = transferable.materialize().asUint8List();
    // expensive image manipulation
    return processedBytes;
  });
}
```

Zero-copy transfer between isolates for typed data.

## Long-lived worker isolate

Repeated image thumbnails—spawn once:

```dart
class ThumbnailWorker {
  SendPort? _sendPort;
  Isolate? _isolate;

  Future<void> start() async {
    final receivePort = ReceivePort();
    _isolate = await Isolate.spawn(_workerMain, receivePort.sendPort);
    _sendPort = await receivePort.first as SendPort;
  }

  static void _workerMain(SendPort mainSendPort) {
    final port = ReceivePort();
    mainSendPort.send(port.sendPort);

    port.listen((message) {
      final replyPort = message['reply'] as SendPort;
      final bytes = message['bytes'] as Uint8List;
      final thumbnail = _generateThumbnail(bytes);
      replyPort.send(thumbnail);
    });
  }

  Future<Uint8List> process(Uint8List bytes) {
    final completer = Completer<Uint8List>();
    final responsePort = ReceivePort();
    responsePort.listen((result) {
      completer.complete(result as Uint8List);
      responsePort.close();
    });
    _sendPort!.send({'bytes': bytes, 'reply': responsePort.sendPort});
    return completer.future;
  }

  void dispose() => _isolate?.kill();
}
```

Amortizes spawn cost across hundreds of images.

## Plugin access in isolates

If worker needs `path_provider` or similar:

```dart
Future<R> runWithPlugins<R>(Future<R> Function() task) async {
  final token = RootIsolateToken.instance!;
  return Isolate.run(() async {
    BackgroundIsolateBinaryMessenger.ensureInitialized(token);
    return task();
  });
}
```

See background isolates article for full pattern.

### What NOT to isolate

- **HTTP requests** — already async, non-blocking.
- **Small JSON** (< 50 KB) — spawn overhead exceeds parse time.
- **Database reads via Drift** — use Drift's isolate mode or background executor instead of DIY.
- **setState/UI updates** — must happen on main isolate after result returns.

Profile first:

```dart
Timeline.startSync('parse');
final products = parseProducts(json);
Timeline.finishSync();
```

DevTools timeline shows if work exceeds 16 ms budget.

### isolate package pool

For bounded parallelism:

```dart
// conceptual — use package like pool or custom semaphore
final results = await Future.wait(
  chunks.map((chunk) => compute(processChunk, chunk)),
);
```

Don't spawn unbounded isolates—2–4 workers match typical phone core count for CPU tasks.

### Error handling

Isolate errors don't cross to main isolate automatically:

```dart
try {
  final result = await compute(riskyParse, data);
} catch (e, stack) {
  logger.error('Parse failed', e, stack);
}
```

In worker isolates, wrap in try/catch and send error back via SendPort.

### Flutter 3.7+ rendering isolate (experimental awareness)

Picture compilation may move off UI thread in future engine versions—profile before optimizing manually. Your JSON/image isolate work remains valid; don't isolate everything preemptively. DevTools "Performance" overlay shows raster vs UI thread separately from your Dart isolate work.

Cancel long isolate work when user navigates away—use Isolate.kill if spawn-based, or flag check inside loop for compute jobs processing chunks. User expects back button to stop heavy import immediately; orphaned isolates waste CPU and battery.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

Schedule a quarterly review of this implementation against current SDK release notes—Flutter and cloud providers ship breaking changes on six-month cadences, and assumptions that held last year may need adjustment. Capture before-and-after metrics when you change configuration so regressions are obvious in retrospect rather than debated from memory.

Pass primitive data across isolates, not BuildContext — isolate callbacks that touch widgets cause `!_debugLocked` crashes.

## Resources

- [Flutter concurrency and isolates](https://docs.flutter.dev/perf/isolates)
- [compute function](https://api.flutter.dev/flutter/foundation/compute.html)
- [Isolate.run](https://api.flutter.dev/flutter/dart-isolate/Isolate/run.html)
- [TransferableTypedData](https://api.flutter.dev/flutter/dart-typed_data/TransferableTypedData-class.html)
- [Dart isolates tutorial](https://dart.dev/language/concurrency)
