---
title: "Method Channels vs Pigeon"
slug: "flutter-method-channels-vs-pigeon"
description: "Raw MethodChannel calls work until your platform bridge grows. Pigeon generates type-safe Dart, Kotlin, and Swift glue so you stop debugging serialization by hand."
datePublished: "2025-01-19"
dateModified: "2025-01-19"
tags: ["Flutter", "Dart", "Platform Channels", "Mobile"]
keywords: "Flutter MethodChannel, Pigeon code generation, platform channels Flutter, native interop Dart, type-safe platform API"
faq:
  - q: "Should new Flutter projects use Pigeon instead of MethodChannel?"
    a: "Use Pigeon when you have a stable API surface between Dart and native code—camera controls, SDK wrappers, payment flows. Stick with raw MethodChannel for one-off prototypes or highly dynamic calls where generating code every iteration slows you down."
  - q: "Does Pigeon support async callbacks from native to Dart?"
    a: "Yes. Pigeon supports async methods and event channels for streaming data. You define the contract in a Dart file; the generator produces the boilerplate on both sides. Complex bidirectional flows still need careful threading on Android and iOS."
  - q: "Can I migrate existing MethodChannel code to Pigeon incrementally?"
    a: "Absolutely. Run Pigeon for new APIs alongside legacy channels on different channel names. Migrate one feature at a time, keep integration tests covering both paths during transition, then delete the hand-written serialization when parity is proven."
---

I once spent an afternoon chasing a bug where Android returned an `int` and iOS returned an `NSNumber` that Dart deserialized as a `double`. The MethodChannel itself was fine; the contract was implicit. Nobody had written down the types, so each platform author guessed. Pigeon exists so that class of bug dies in code generation instead of production.

Flutter talks to native code through platform channels. The low-level API is `MethodChannel`: you send a method name and a JSON-like argument map, and hope both sides agree on shape and types. Pigeon is Google's code generator that reads a Dart API definition and emits matching Dart, Java/Kotlin, Objective-C, and Swift stubs. Same wire, fewer surprises.

## MethodChannel: flexible, fragile

The classic pattern:

```dart
const channel = MethodChannel('com.example.app/battery');

Future<int> getBatteryLevel() async {
  final level = await channel.invokeMethod<int>('getBatteryLevel');
  return level ?? -1;
}
```

Android side (Kotlin):

```kotlin
MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "com.example.app/battery")
  .setMethodCallHandler { call, result ->
    when (call.method) {
      "getBatteryLevel" -> result.success(getLevel())
      else -> result.notImplemented()
    }
  }
```

This works for three methods. At thirty, you maintain parallel switch statements, duplicate string constants, and manual null checks. Refactoring a parameter name in Dart does not rename it in Swift. Tests mock channels with fake binary messengers that do not catch type drift.

## Pigeon: contract-first generation

Define the API in `pigeon/api.dart`:

```dart
import 'package:pigeon/pigeon.dart';

class BatteryInfo {
  int? level;
  bool? isCharging;
}

@HostApi()
abstract class BatteryApi {
  BatteryInfo getBatteryInfo();
}
```

Run the generator:

```bash
dart run pigeon --input pigeon/api.dart
```

You get `BatteryApi` in Dart, a Kotlin `BatteryApi` interface, and Swift protocols. Call sites are typed:

```dart
final api = BatteryApi();
final info = await api.getBatteryInfo();
print(info.level);
```

No stringly-typed method names. Rename a field, regenerate, and the compiler fails on every stale reference.

## Choosing between them

| Concern | MethodChannel | Pigeon |
|---------|---------------|--------|
| Setup time | Minutes | Initial pigeon setup + build step |
| Type safety | Runtime | Compile time |
| API size | Small, experimental | Medium to large stable surfaces |
| Custom codecs | Full control | Supported via custom types |
| Team skill | Any Flutter dev | Needs codegen in CI |

Use MethodChannel when you are spiking hardware access in a hackathon. Use Pigeon when the bridge becomes a product surface other teams depend on.

## Event streams and callbacks

Pigeon supports `@EventChannel` for native-to-Dart streams—think location updates or scanner events:

```dart
@EventChannel('location_stream')
abstract class LocationStream {
  LocationEvent streamLocation();
}
```

The generator wires stream handlers on both platforms. You still must respect main-thread rules on iOS and avoid blocking the UI isolate on Android, but the serialization layer is handled.

## CI integration

Add pigeon to `dev_dependencies` and a script in your melos or Makefile target:

```yaml
# pubspec.yaml dev_dependencies
pigeon: ^22.0.0
```

```bash
dart run pigeon \
  --input pigeon/battery_api.dart \
  --dart_out lib/src/generated/battery_api.g.dart \
  --kotlin_out android/app/src/main/kotlin/com/example/BatteryApi.kt \
  --swift_out ios/Runner/BatteryApi.swift
```

Commit generated files or regenerate in CI before analyze—pick one policy and enforce it. Teams that regenerate in CI catch drift; teams that commit generated code review diffs explicitly.

## Migration path from legacy channels

Start with a read-only API—fetch config, read device info—where native calls Dart-less responses. Wire Pigeon alongside the old channel, feature-flag the new path, compare outputs in logging. Once stable, delete the MethodChannel handler and rename nothing on the Dart side because types already match.

## Common pitfalls

**Nullable vs non-nullable.** Pigeon maps Dart nullability to platform optionals. Mismatch nullable `int?` on Dart with non-null Kotlin `Int` only fails at runtime if you skip regeneration.

**Background isolates.** Platform channels must be called on the root isolate unless you register a background messenger. Pigeon does not magically fix isolate rules.

**Version skew in federated plugins.** If you ship a federated plugin, generate Pigeon per platform implementation package, not one mega-file, so Android and web implementations stay isolated.

## Testing platform bridges

Unit-test Dart-side API with generated mocks where possible. Integration tests exercise real channels on device:

```dart
testWidgets('battery level returns int', (tester) async {
  await tester.pumpWidget(const MaterialApp(home: BatteryWidget()));
  await tester.pumpAndSettle();
  expect(find.textContaining('%'), findsOneWidget);
});
```

On Android emulator, stub native implementation in debug builds returning fixed values—speeds CI device farm runs. Document expected thread: most `@HostApi` methods run on platform main thread; long work belongs in native background threads with async callback to Dart.

## Custom types and enums

Pigeon supports enums and data classes:

```dart
enum ScanMode { single, continuous }

class ScanResult {
  String barcode;
  ScanMode mode;
}
```

Regenerate after enum changes—old APK with new Dart causes deserialization mismatch. Version your API: add fields as optional before making them required in next major plugin version.

## Performance considerations

Channels serialize messages across isolate boundary—batch calls when sending high-frequency sensor data instead of 60 Hz single-value invokes. For bulk binary data, consider `StandardMessageCodec` with `Uint8List` or FFI if throughput dominates.

Profile with DevTools timeline during camera preview integration; if platform channel time spikes, move encoding to native side and send compressed buffers.

## Documentation for platform teams

Maintain a one-page contract doc listing each Pigeon API, thread expectations, error codes, and sample Kotlin/Swift snippets. Android and iOS authors implement against generated interfaces—not ad hoc method names—reducing review churn in cross-platform PRs.

## Error propagation

Pigeon async methods surface platform exceptions as Dart `PlatformException`—wrap in domain Result type at repository boundary for consistent UI error handling.

## Null safety across boundary

Optional return types must align—regenerate after Kotlin nullable return changes; Dart side catches mismatch at code gen time if types diverge in definition file.


## Web platform note

Pigeon supports web in some configurations—verify if your plugin targets web; MethodChannel web uses different messaging semantics.

## Synchronous host APIs

Pigeon supports sync calls where platform allows—avoid blocking UI thread on Android; prefer async for network or disk.

## Version lockstep

Pin pigeon generator version in CI with native codegen step—upgrades require coordinated regenerate on all platforms in one PR.

## Resources

- [Pigeon package on pub.dev](https://pub.dev/packages/pigeon)
- [Writing custom platform-specific code (Flutter docs)](https://docs.flutter.dev/platform-integration/platform-channels)
- [Pigeon GitHub repository](https://github.com/flutter/packages/tree/main/packages/pigeon)
- [Flutter platform channel data types](https://docs.flutter.dev/platform-integration/platform-channels#codec)
- [Federated plugin architecture (Flutter docs)](https://docs.flutter.dev/packages-and-plugins/developing-packages#federated-plugins)
