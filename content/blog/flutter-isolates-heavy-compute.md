---
title: "Isolates for Heavy Compute in Flutter"
slug: "flutter-isolates-heavy-compute"
description: "How to use Flutter isolates for heavy compute: Isolate.run, the compute function, and moving CPU-bound work off the UI thread to keep 60fps jank-free."
datePublished: "2026-03-24"
dateModified: "2026-03-24"
tags: ["Flutter", "Dart", "Performance", "Concurrency"]
keywords: "Flutter isolates, Isolate.run, compute function, background processing Flutter, concurrency Dart, jank free"
faq:
  - q: "What is a Flutter isolate?"
    a: "A Flutter isolate is an independent worker with its own memory heap and event loop that runs Dart code in parallel with the main UI isolate. Isolates don't share mutable state — they communicate by passing messages — which is why they sidestep the data races you'd hit with traditional threads. You reach for one whenever CPU-bound work would otherwise block the main isolate and drop frames."
  - q: "When should I use Isolate.run instead of compute?"
    a: "Use Isolate.run for one-off async computations in modern Flutter; it's the cleaner, Future-based API introduced in Dart 2.19. The older compute function does essentially the same thing and still works, but Isolate.run has better ergonomics and integrates naturally with async/await. For repeated work, spawn a long-lived isolate with a persistent port instead of either helper."
  - q: "Can isolates access the UI or plugins directly?"
    a: "No. Only the main isolate can touch the widget tree, and most platform plugins expect the root isolate binding. A background isolate can do pure Dart computation and return a result, but it can't call setState, rebuild widgets, or reliably use plugins that assume the main isolate. Do the compute in the isolate and apply the result back on the main isolate."
---

The main isolate in a Flutter app has one job that matters above all others: paint a frame every 16 milliseconds. The moment you run a JSON parse over a 5 MB payload, decode an image, or crunch a CSV on that same isolate, you eat into that budget and the UI stutters. Flutter isolates are the fix — separate Dart execution contexts with their own heaps, so CPU-bound work runs truly in parallel and the UI thread stays free to hit 60fps.

I've shipped enough Flutter apps to know that "jank" reports almost never come from Flutter's rendering — they come from someone doing real work on the UI isolate. This is a walk through when isolates earn their keep, the modern APIs (`Isolate.run`, `compute`), and the sharp edges around message passing and plugin access.

## Why the main isolate can't just "do the work"

Dart is single-threaded per isolate. The main isolate runs an event loop that interleaves your code with the framework's frame scheduling. If you hand it a synchronous computation that takes 40ms, nothing else runs for those 40ms — no gesture handling, no animation ticks, no layout. The user sees a frozen screen or a hitch in a scroll.

`async`/`await` does *not* save you here. Awaiting a `Future` yields control back to the event loop, but a purely CPU-bound function has nothing to await — it just runs to completion on the current isolate. Wrapping a tight loop in `Future(() => ...)` still executes on the main isolate. The only way to get real parallelism for Dart code is a separate isolate on a separate thread.

The heuristic I use: if a synchronous operation can exceed ~8ms, measure it, and if it's CPU-bound, move it. Network I/O and disk reads are already asynchronous and don't need an isolate — those don't block the CPU, they just wait.

## Isolate.run: the one-shot workhorse

Since Dart 2.19, `Isolate.run` is the cleanest way to offload a single computation. It spawns an isolate, runs your function, returns the result as a `Future`, and tears the isolate down for you.

```dart
Future<List<Order>> parseOrders(String rawJson) {
  return Isolate.run(() {
    final decoded = jsonDecode(rawJson) as List;
    return decoded
        .map((e) => Order.fromJson(e as Map<String, dynamic>))
        .toList();
  });
}
```

The closure runs on a fresh isolate. Its argument (`rawJson`) is passed across the boundary and the return value is passed back. Because there's no shared memory, the framework copies the data — which brings us to the one cost you must respect.

## The copy cost nobody warns you about

Messages between isolates are *copied*, not shared (with a few zero-copy exceptions like `TransferableTypedData` and, more recently, immutable objects). If you send a 20 MB string to an isolate and get a 20 MB list back, you paid for two serializations plus the compute. Sometimes the copy dwarfs the work you were trying to offload.

Two practical consequences:

- **Send the smallest input and return the smallest output.** If you only need three fields from a huge JSON blob, consider whether the isolate can return just those, not a fat object graph.
- **For large binary data, use `TransferableTypedData`.** It moves a byte buffer between isolates without copying, which matters for image bytes or audio frames.

I once "optimized" an image pipeline by moving decode into an isolate and made it *slower*, because I was shipping raw decoded pixel buffers back and forth. Measuring the boundary cost, not just the compute, is the difference between a real win and cargo-culting.

## compute vs Isolate.run vs a long-lived isolate

There are three tools, and they're not interchangeable.

| Approach | Best for | Cost |
|---|---|---|
| `compute()` | One-off work, older codebases | Spawns + tears down an isolate each call |
| `Isolate.run()` | One-off work, modern Flutter | Same lifecycle, nicer API |
| Long-lived isolate + `SendPort` | Repeated/streaming work | You manage lifecycle and ports |

`compute` and `Isolate.run` both pay the spawn cost every call. Spawning an isolate isn't free — it's on the order of a couple of milliseconds — so calling `Isolate.run` in a tight loop or per-frame is an anti-pattern. When you have a stream of work (say, parsing rows as they arrive, or a physics tick), spawn one isolate and keep it alive.

## A persistent isolate for repeated work

When work recurs, set up a two-way channel and keep the isolate warm:

```dart
class ParserWorker {
  late final SendPort _toWorker;
  final _ready = Completer<void>();

  Future<void> start() async {
    final fromWorker = ReceivePort();
    await Isolate.spawn(_entry, fromWorker.sendPort);
    fromWorker.listen((msg) {
      if (msg is SendPort) {
        _toWorker = msg;
        _ready.complete();
      }
    });
    return _ready.future;
  }

  static void _entry(SendPort mainPort) {
    final inbox = ReceivePort();
    mainPort.send(inbox.sendPort);
    inbox.listen((msg) {
      final (String raw, SendPort reply) = msg as (String, SendPort);
      reply.send(jsonDecode(raw));
    });
  }
}
```

This is more ceremony, but it amortizes the spawn cost across thousands of messages. For anything happening more than a few times a second, it's worth it.

If you're already auditing rendering performance, isolates pair naturally with the work covered in [Flutter performance and the Impeller renderer](https://blog.michaelsam94.com/flutter-performance-impeller/) — offloading compute frees the raster and UI threads that Impeller depends on to keep frames smooth.

## The rules: no UI, watch your plugins

The hard boundary: a background isolate cannot touch the widget tree or call `setState`. Compute the result, return it, and apply it on the main isolate. Plugins are the subtler trap — many rely on the root isolate's `BinaryMessenger`, so calling them from a spawned isolate either fails or behaves unpredictably. Dart added `BackgroundIsolateBinaryMessenger` to let some plugins work off the main isolate, but treat it as opt-in per plugin, not a default assumption.

Keep background isolates pure: data in, computed data out, no framework calls. That discipline also keeps them testable — a pure function is trivial to unit test without a widget harness. This same "keep the heavy work isolated and deterministic" mindset shows up when you build [custom RenderObjects and painting](https://blog.michaelsam94.com/flutter-custom-renderobjects-paint/), where you want expensive layout math predictable and off the critical path.

## When not to reach for an isolate

Isolates are not a general concurrency hammer. If the work is I/O-bound, `async`/`await` on the main isolate is already correct and lighter. If the work is trivial (parsing a 2 KB response), the spawn and copy overhead will cost more than you save. And if you find yourself passing enormous object graphs back and forth, step back — sometimes the right fix is a streaming parser or doing the work incrementally across frames with a scheduler, not brute-forcing it onto another thread.

My rule of thumb after years of this: profile first with the DevTools timeline, confirm the jank is CPU-bound Dart on the UI isolate, then offload the specific hot function — not the whole feature. Isolates are a scalpel, not a bulldozer, and treating them that way keeps your app both fast and comprehensible.

## Resources

- [Flutter — concurrency and isolates](https://docs.flutter.dev/perf/isolates)
- [Dart — concurrency documentation](https://dart.dev/language/concurrency)
- [Isolate.run API reference](https://api.dart.dev/stable/dart-isolate/Isolate/run.html)
- [Flutter compute function reference](https://api.flutter.dev/flutter/foundation/compute-constant.html)
- [Dart isolates library](https://api.dart.dev/stable/dart-isolate/dart-isolate-library.html)
- [Flutter DevTools performance view](https://docs.flutter.dev/tools/devtools/performance)
