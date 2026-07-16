---
title: "Isolate Groups and Shared Memory"
slug: "dart-isolate-groups-shared-memory"
description: "Understand Dart isolate groups, shared immutable heap objects, transfer messages, and when compute() beats long-lived isolates."
datePublished: "2025-06-17"
dateModified: "2025-06-17"
tags: ["Flutter", "Dart"]
keywords: "Dart isolates, isolate groups, shared memory Dart, compute function, Flutter concurrency, TransferableTypedData"
faq:
  - q: "What is an isolate group in Dart?"
    a: "Isolates spawned from the same root isolate share an isolate group and can share immutable portions of the heap—canonicalized strings, compile-time constants, and read-only assets loaded before spawn. Mutable objects still cannot be shared; communication uses message passing with copy or transfer semantics."
  - q: "How do I pass large binary data between isolates efficiently?"
    a: "Use TransferableTypedData to transfer ownership of byte buffers without copying—the sending isolate loses access after transfer. For JSON or structured data, serialize to Uint8List and transfer, or use Isolate.run (Dart 2.19+) which handles spawn and teardown for one-shot tasks."
  - q: "Should I use compute() or a persistent isolate?"
    a: "Use compute or Isolate.run for occasional heavy work—image decode, JSON parse of large payloads. Use persistent isolates with ReceivePort for steady throughput—background sync, audio processing—where spawn overhead dominates. Flutter compute wraps isolate spawn with platform thread pool considerations."
---

Dart concurrency is isolates, not threads—no shared mutable memory by default, message passing instead of locks. Isolate groups add a nuance: spawned isolates share read-only heap chunks, cutting memory for duplicated constants. Large payload passing still needs `TransferableTypedData` or you copy megabytes per message. Getting this wrong shows up as jank from main-isolate JSON parsing, not mysterious race conditions—because races barely exist.

## Isolate basics

```dart
Future<void> main() async {
  final receivePort = ReceivePort();
  await Isolate.spawn(worker, receivePort.sendPort);
  final sendPort = await receivePort.first as SendPort;
  final response = ReceivePort();
  sendPort.send(['compute', 42, response.sendPort]);
  print(await response.first); // worker result
}

void worker(SendPort mainSendPort) {
  final port = ReceivePort();
  mainSendPort.send(port.sendPort);
  port.listen((message) {
    final op = message[0] as String;
    if (op == 'compute') {
      final n = message[1] as int;
      final reply = message[2] as SendPort;
      reply.send(n * n);
    }
  });
}
```

Messages must be copyable primitives, typed data, or SendPort—objects copy deeply by default.

## Isolate.run for one-shot work

```dart
final result = await Isolate.run(() {
  return heavyComputation(inputData);
});
```

Spawns, runs, returns, kills isolate—cleaner than manual spawn for single tasks. Dart 2.19+.

## Flutter compute

```dart
import 'package:flutter/foundation.dart';

final parsed = await compute(_parseJson, rawBytes);

List<Map<String, dynamic>> _parseJson(Uint8List bytes) {
  return jsonDecode(utf8.decode(bytes)).cast<Map<String, dynamic>>();
}
```

Top-level or static function required—closures cannot cross isolate boundary.

## TransferableTypedData — zero-copy transfer

```dart
void sendLargeBuffer(SendPort port, Uint8List data) {
  final transferable = TransferableTypedData.fromList([data]);
  port.send(transferable);
}

void receiveLargeBuffer(SendPort replyPort, TransferableTypedData transferable) {
  final buffer = transferable.materialize().asUint8List();
  // process buffer — sender's copy invalidated after transfer
  replyPort.send('done');
}
```

Use for image bytes, file chunks, protobuf payloads.

## Shared memory within isolate group

Isolates from `Isolate.spawn` share:

- Immutable canonical strings
- Loaded library symbols and read-only constants
- **Not** mutable objects, GrowableList contents you mutate, or closures capturing mutable state

Spawning many workers does not duplicate entire program heap—savings vs OS processes.

## FFI and isolates

Native code via `dart:ffi` can share pointers across isolates with explicit synchronization—you own thread safety. `NativeCallable` and `Isolate.exit` patterns for background workers returning results.

Do not pass Pointer objects casually—lifetime bugs crash VM.

## Architecture patterns

**Main isolate** — UI, AnimationController, platform channels

**Worker isolates** — parsing, compression, ML inference

**Long-lived service isolate** — database write queue serializing mutations

```dart
class DbWriteIsolate {
  late SendPort _commands;
  late Isolate _isolate;

  Future<void> init() async {
    final initPort = ReceivePort();
    _isolate = await Isolate.spawn(_entry, initPort.sendPort);
    _commands = await initPort.first as SendPort;
  }

  Future<void> insert(Record r) async {
    final reply = ReceivePort();
    _commands.send([Insert(r), reply.sendPort]);
    await reply.first;
  }
}
```

Single writer avoids SQLite concurrent write locks from multiple isolates.

## Common mistakes

Parsing 5 MB JSON on main isolate before `compute`—pass bytes to isolate, decode there.

Sending huge object graphs copying on every message—transfer or process in worker from source file path.

Spawning isolate per frame—pool workers or batch work.

## Isolate pools for steady throughput

For apps processing many items (image gallery thumbnails, batch sync), pool workers instead of spawning per task:

```dart
class IsolatePool {
  final List<SendPort> _workers = [];
  int _next = 0;

  Future<void> init(int count) async {
    for (var i = 0; i < count; i++) {
      final port = ReceivePort();
      await Isolate.spawn(_workerEntry, port.sendPort);
      _workers.add(await port.first as SendPort);
    }
  }

  Future<T> run<T>(T Function() computation) async {
    final reply = ReceivePort();
    _workers[_next % _workers.length].send([computation, reply.sendPort]);
    _next++;
    return await reply.first as T;
  }
}
```

Pool size = CPU cores - 1 (leave one for main/UI). Reuse isolates across many tasks — amortizes spawn cost.

## Platform channel and isolate interaction

Platform channels must be called from the main isolate — plugins aren't isolate-safe:

```dart
// Wrong: platform channel from compute isolate
final result = await compute((_) {
  return methodChannel.invokeMethod('getData');  // CRASH or hang
}, null);

// Correct: platform call on main, heavy processing in isolate
final rawData = await methodChannel.invokeMethod('getData');
final processed = await compute(processData, rawData);
```

Architecture: main isolate owns all platform channel communication. Worker isolates receive serializable data, return results.

## Memory profiling across isolates

Each isolate has its own heap — memory usage scales with isolate count:

```
Main isolate: UI + state (~50MB)
Worker 1: image processing (~30MB during decode)
Worker 2: JSON parsing (~20MB during parse)
Total: ~100MB peak
```

Monitor with DevTools memory tab. Kill idle worker isolates — don't keep pool larger than needed. `Isolate.kill(immediate: true)` for shutdown.

## Failure modes

- **JSON parsing on main isolate** — UI jank; pass bytes to worker via compute/TransferableTypedData
- **Platform channel from worker isolate** — crash or undefined behavior
- **Deep copy on large messages** — 5MB object graph copied per SendPort.send; use TransferableTypedData
- **Isolate per operation** — spawn overhead dominates; use pool or Isolate.run
- **Mutable state shared between isolates** — impossible by design; use message passing
- **Closure crossing isolate boundary** — must be top-level or static function

## Production checklist

- Heavy computation off main isolate via compute/Isolate.run
- Large binary data transferred via TransferableTypedData
- Platform channels called only from main isolate
- Worker pool sized to CPU cores for steady throughput
- Isolate.run for one-shot tasks, persistent isolates for steady work
- Memory profiled with DevTools during peak load

## Common production mistakes

Teams get isolate groups shared memory wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of isolate groups shared memory fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [Dart isolates documentation](https://dart.dev/language/concurrency)
- [TransferableTypedData API](https://api.dart.dev/stable/dart-typed_data/TransferableTypedData-class.html)
- [Isolate.run](https://api.dart.dev/stable/dart-isolate/Isolate/run.html)
- [Flutter compute function](https://api.flutter.dev/flutter/foundation/compute.html)
