---
title: "Working with Dart Streams"
slug: "dart-async-streams-patterns"
description: "Master Dart Stream patterns for Flutter and server code: broadcast vs single-subscription, async* generators, StreamController, and error handling."
datePublished: "2025-06-11"
dateModified: "2025-06-11"
tags: ["Flutter", "Dart"]
keywords: "Dart streams, async generator, StreamController, broadcast stream, Flutter StreamBuilder, stream patterns"
faq:
  - q: "What is the difference between single-subscription and broadcast streams?"
    a: "Single-subscription streams allow one listener—typical for file reads, HTTP response bodies, and IO. Broadcast streams support multiple listeners—UI events, WebSocket fan-out. Listening twice to single-subscription throws; convert with asBroadcastStream() only when replay behavior is acceptable."
  - q: "When should I use async* vs StreamController?"
    a: "Use async* generator functions for straightforward producer logic—timers, mapped sequences, chunked reads. Use StreamController when bridging callback APIs (platform channels, socket.onData) or when multiple manual add calls happen from disparate sources. Always close controllers in dispose."
  - q: "How do I handle stream errors in Flutter?"
    a: "Listen with onError callback or await for await with try/catch inside loop. StreamBuilder shows ConnectionState.waiting but not errors unless stream emits via Stream.error—use RxDart onErrorReturn or map errors to AsyncSnapshot-compatible states. Cancel subscriptions in dispose to prevent memory leaks."
---

Streams are Dart's async sequences—events over time instead of one Future value. Flutter exposes them everywhere: `StreamBuilder`, BLoC streams, Firebase snapshots, WebSocket feeds. Misunderstanding single-subscription vs broadcast causes "Stream has already been listened to" crashes; missing `cancel()` causes leaks. The patterns are small but non-negotiable in production async code.

## Creating streams with async*

```dart
Stream<int> countStream(int max) async* {
  for (var i = 1; i <= max; i++) {
    await Future.delayed(const Duration(seconds: 1));
    yield i;
  }
}

void main() async {
  await for (final n in countStream(5)) {
    print(n);
  }
}
```

`async*` functions return streams; `yield` emits events; `yield*` delegates to nested stream.

## StreamController for callback bridges

```dart
class SensorRepository {
  final _controller = StreamController<double>.broadcast();
  Stream<double> get readings => _controller.stream;

  void _onPlatformData(double value) {
    if (!_controller.isClosed) {
      _controller.add(value);
    }
  }

  void dispose() => _controller.close();
}
```

Broadcast for multiple UI listeners. Single-subscription controller for one consumer pipeline.

## Transforming streams

```dart
Stream<String> lines = file
    .openRead()
    .transform(utf8.decoder)
    .transform(const LineSplitter());

final debouncedSearch = queryController.stream
    .distinct()
    .debounceTime(const Duration(milliseconds: 300))
    .switchMap((q) => searchApi(q)); // rxdart
```

Core library: `map`, `where`, `expand`, `take`, `skip`, `asyncMap`, `asyncExpand`.

## Error and completion

```dart
stream.listen(
  (data) => print(data),
  onError: (e, st) => logger.severe('stream failed', e, st),
  onDone: () => print('complete'),
  cancelOnError: false,
);

// Or propagate
stream.handleError((e) => fallbackValue);
```

Uncaught stream errors become zone errors—always handle or transform.

## Flutter StreamBuilder

```dart
StreamBuilder<List<Message>>(
  stream: chatRepo.messages,
  initialData: const [],
  builder: (context, snapshot) {
    if (snapshot.hasError) {
      return ErrorView(snapshot.error!);
    }
    if (!snapshot.hasData) {
      return const LoadingIndicator();
    }
    return MessageList(snapshot.data!);
  },
)
```

`initialData` avoids null flash on first frame.

## Subscription lifecycle

```dart
class _MyWidgetState extends State<MyWidget> {
  StreamSubscription? _sub;

  @override
  void initState() {
    super.initState();
    _sub = repo.events.listen(_handleEvent);
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }
}
```

Or use `StreamBuilder` / `ref.listen` (Riverpod) to manage lifecycle.

## Single-subscription pitfall

```dart
final stream = fetchData(); // single-subscription
stream.listen(print);
stream.listen(print); // StateError!
```

Fix: cache broadcast conversion once:

```dart
final stream = fetchData().asBroadcastStream(
  onListen: (sub) => /* setup */,
  onCancel: (sub) => /* teardown when no listeners */,
);
```

Or call factory per listener.

## StreamSubscription patterns in production

Beyond basic cancel-in-dispose, production apps need pause/resume, error recovery, and backpressure awareness:

```dart
class EventProcessor {
  StreamSubscription<Event>? _sub;
  bool _paused = false;

  void start(Stream<Event> events) {
    _sub?.cancel();
    _sub = events.listen(
      _handle,
      onError: _onError,
      cancelOnError: false, // keep listening after errors
    );
  }

  void pauseProcessing() {
    _sub?.pause();
    _paused = true;
  }

  void resumeProcessing() {
    _sub?.resume();
    _paused = false;
  }

  Future<void> _onError(Object e, StackTrace st) async {
    logger.severe('Event stream error', e, st);
    await Future.delayed(const Duration(seconds: 5));
    if (!_paused) resumeProcessing(); // auto-recover
  }

  void dispose() => _sub?.cancel();
}
```

`cancelOnError: false` keeps the subscription alive after errors — critical for long-lived WebSocket feeds where one malformed message shouldn't kill the entire connection.

## Bridging Futures and Streams

Many APIs return `Future` but UI wants `Stream` (progress updates, polling):

```dart
Stream<UploadProgress> uploadWithProgress(File file) async* {
  yield UploadProgress(phase: Phase.starting);

  final request = await _buildRequest(file);
  final response = await request.send();

  await for (final chunk in response.stream) {
    _bytesReceived += chunk.length;
    yield UploadProgress(
      phase: Phase.uploading,
      bytesReceived: _bytesReceived,
      totalBytes: file.lengthSync(),
    );
  }

  yield UploadProgress(phase: Phase.complete);
}
```

`async*` generators are the idiomatic bridge — cleaner than manual `StreamController` for linear async flows.

## Combining streams with Riverpod and BLoC

**Riverpod StreamProvider:**

```dart
@riverpod
Stream<List<Message>> messages(MessagesRef ref) {
  final auth = ref.watch(authProvider);
  return chatRepo.watchMessages(auth.userId);
}
```

Riverpod auto-disposes the stream subscription when no listeners remain. Override in tests:

```dart
container = ProviderContainer(
  overrides: [
    messagesProvider.overrideWith((ref) => Stream.value(testMessages)),
  ],
);
```

**BLoC:** Events map to `Stream` transformations via `async*` or `switchMap` in event handlers. Keep stream subscriptions inside the BLoC, expose only state snapshots to UI.

## Backpressure and buffering

Dart streams don't enforce backpressure by default — a fast producer overwhelms a slow consumer:

```dart
// Unbounded buffer — memory grows if consumer is slow
final controller = StreamController<Event>();

// Bounded buffer — drops oldest or errors when full
final controller = StreamController<Event>(
  onListen: () => _startProducing(),
  onCancel: () => _stopProducing(),
);
```

For high-frequency sensor data, sample or debounce before UI:

```dart
sensorStream
    .sampleTime(const Duration(milliseconds: 100))
    .listen(updateGauge);
```

Use `StreamTransformer` from `dart:async` or RxDart operators for throttling patterns.

## Common failure modes

- **"Stream has already been listened to"** — calling `.listen()` twice on single-subscription stream; use broadcast or factory
- **Memory leak** — subscription not cancelled in `dispose()`; use `StreamBuilder` or framework-managed providers
- **Zone error from unhandled stream error** — always provide `onError` or wrap in `handleError`
- **StreamBuilder stuck on waiting** — stream never emits initial value; use `initialData` or emit empty list first
- **Broadcast stream with no replay** — late listeners miss earlier events; cache last value manually or use `BehaviorSubject` from RxDart
- **Closing controller twice** — check `isClosed` before `add()` and `close()`

## Testing streams thoroughly

Beyond `emitsInOrder`, test timing and cancellation:

```dart
test('debounced search fires once', () async {
  final controller = StreamController<String>();
  final results = <String>[];

  final sub = controller.stream
      .debounceTime(const Duration(milliseconds: 50))
      .listen(results.add);

  controller.add('a');
  controller.add('ab');
  controller.add('abc');
  await Future.delayed(const Duration(milliseconds: 100));

  expect(results, ['abc']);
  await sub.cancel();
  await controller.close();
});

test('subscription cancelled on dispose', () async {
  final controller = StreamController<int>.broadcast();
  late StreamSubscription sub;

  sub = controller.stream.listen((_) {});
  await sub.cancel();

  expect(sub.isPaused, false);
  // Verify no memory leak via controller listener count
});
```

Use `fake_async` for time-dependent stream operators in unit tests.

## Production checklist

- Single-subscription vs broadcast chosen deliberately per stream source
- All subscriptions cancelled in `dispose()` or framework-managed lifecycle
- `onError` handler on every manual `.listen()` call
- `cancelOnError: false` for long-lived feeds that should survive individual errors
- StreamControllers closed in dispose with `isClosed` guard before `add()`
- High-frequency streams debounced/sampled before UI binding
- Stream tests cover error, completion, and cancellation paths

## Resources

```dart
expectLater(
  countStream(3),
  emitsInOrder([1, 2, 3, emitsDone]),
);

await expectLater(
  failingStream(),
  emitsError(isA<FormatException>()),
);
```

`package:test` matchers `emits`, `emitsInOrder`, `neverEmits`.

## Resources

- [Dart asynchronous programming: streams](https://dart.dev/libraries/async/using-streams)
- [Stream class API](https://api.dart.dev/stable/dart-async/Stream-class.html)
- [Flutter StreamBuilder](https://api.flutter.dev/flutter/widgets/StreamBuilder-class.html)
- [RxDart operators](https://pub.dev/documentation/rxdart/latest/)
