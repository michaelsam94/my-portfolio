---
title: "Type-Safe Platform Channels with Pigeon"
slug: "flutter-pigeon-platform-channels"
description: "Pigeon generates type-safe platform channel code for Flutter, killing MethodChannel boilerplate. How it works, a full example, and Pigeon vs FFI."
datePublished: "2026-07-07"
dateModified: "2026-07-07"
tags: ["Flutter", "Dart", "Native Interop"]
keywords: "Pigeon Flutter, platform channels, type-safe channels, method channel, native interop Flutter, FFI vs Pigeon"
faq:
  - q: "What is Pigeon in Flutter?"
    a: "Pigeon is a code generation tool from the Flutter team that produces type-safe platform channel code from a single Dart interface definition. Instead of hand-writing MethodChannel calls with string method names and untyped maps on both the Dart and native sides, you define an API in Dart and Pigeon generates matching Dart, Kotlin/Java, and Swift/Objective-C code that stays in sync."
  - q: "How is Pigeon different from a raw MethodChannel?"
    a: "A raw MethodChannel is stringly-typed: you invoke methods by string name and pass loosely-typed maps, so a typo or a type mismatch fails silently at runtime. Pigeon generates strongly-typed method signatures and data classes on every side, so mismatches become compile errors. It eliminates the serialization boilerplate and keeps the Dart and native contracts guaranteed to match."
  - q: "Should I use Pigeon or FFI for native interop?"
    a: "Use Pigeon when you're calling platform APIs implemented in Kotlin/Java or Swift/Objective-C — the SDK-level, message-passing use case that method channels were built for. Use FFI (dart:ffi) when you're calling into a C or C++ library directly for performance-critical, synchronous work. Pigeon is for platform code; FFI is for native libraries."
---

If you've written more than one Flutter plugin, you've written this bug: a `MethodChannel` where the Dart side invokes `"getBatteryLevel"` and the Kotlin side listens for `"getBattery"`, and nothing complains until a user's screen shows a blank battery indicator. Platform channels are stringly-typed by default — method names are strings, arguments are untyped maps, and the contract between Dart and native lives only in your memory. Pigeon fixes this at the root: you write one Dart interface, run a generator, and get matching, strongly-typed code for Dart, Kotlin/Java, and Swift/Objective-C that literally cannot drift out of sync because it's generated from the same source.

I've replaced hand-rolled channels with Pigeon in every plugin I maintain, and the payoff is boring in the best way — the entire category of "typo in a method name" and "forgot a field in the map" bugs simply stops happening.

## The problem with raw MethodChannel

Here's the traditional approach, and every line of it is a place to make a mistake:

```dart
// Dart side — stringly typed, untyped map
final channel = MethodChannel('com.example/device');
final result = await channel.invokeMethod('getDeviceInfo', {'includeBattery': true});
final model = result['model'] as String;      // hope this key exists
final battery = result['batteryLevel'] as int; // hope it's an int
```

```kotlin
// Kotlin side — must match the strings and map keys by hand
when (call.method) {
    "getDeviceInfo" -> {
        val includeBattery = call.argument<Boolean>("includeBattery") ?: false
        result.success(mapOf("model" to Build.MODEL, "batteryLevel" to level))
    }
}
```

Every string (`"getDeviceInfo"`, `"model"`, `"batteryLevel"`) exists twice, in two languages, with no compiler checking that they agree. Every cast (`as String`, `as int`) is a runtime gamble. Multiply this across a plugin with fifteen methods and the surface area for silent breakage is enormous.

## How Pigeon flips it

With Pigeon, the contract is a single Dart file with data classes and an abstract API, annotated so the generator knows what to emit:

```dart
import 'package:pigeon/pigeon.dart';

class DeviceInfo {
  String? model;
  int? batteryLevel;
}

@HostApi()
abstract class DeviceApi {
  DeviceInfo getDeviceInfo(bool includeBattery);
}
```

You run the generator, pointing it at output paths for each platform:

```bash
dart run pigeon \
  --input pigeons/device_api.dart \
  --dart_out lib/device_api.g.dart \
  --kotlin_out android/src/main/kotlin/DeviceApi.g.kt \
  --swift_out ios/Runner/DeviceApi.g.swift
```

Now the Dart side calls a real typed method, `DeviceApi().getDeviceInfo(true)`, returning a real `DeviceInfo` object — no maps, no casts. The Kotlin side implements a generated interface with a typed signature; forget a method or get a type wrong and the Kotlin compiler stops you. The `.g` files are the enforced contract.

## HostApi vs FlutterApi

Pigeon models the two directions of communication explicitly, which is clearer than raw channels ever were:

| Annotation | Direction | Use case |
|---|---|---|
| `@HostApi()` | Dart → native | Flutter calls a platform API (get battery, start scan) |
| `@FlutterApi()` | Native → Dart | Platform pushes to Flutter (sensor event, callback) |

Most plugins are mostly `@HostApi`. But when native code needs to *call into* Dart — say a Bluetooth stack delivering a connection event — `@FlutterApi` generates the reverse-direction typed calls. Being forced to name the direction up front produces cleaner API design than the free-for-all of a bidirectional method channel where anyone can send anything. For event streams specifically, this pairs well with the kind of hardware integration I described in [Flutter for embedded and IoT](https://blog.michaelsam94.com/flutter-embedded-iot/), where a native sensor pipeline pushes structured events up to the Dart UI.

## Async, errors, and the edges

Real interop isn't just fire-and-forget. Pigeon handles async natively — mark a method `@async` and the native side gets a callback to complete later, while Dart still `await`s a normal `Future`:

```dart
@HostApi()
abstract class ScannerApi {
  @async
  List<String> scanNetworks();
}
```

Error handling is the part people underestimate. When the native side throws, Pigeon surfaces it as a `PlatformException` on the Dart side — but the message quality is entirely up to how you throw it natively. Throw a bare exception and Dart gets a useless stack; throw a `FlutterError` with a real code and message and the Dart side can actually branch on it. I always define an explicit error contract, because "something failed in native land" is the worst debugging experience in mobile.

One honest limitation: Pigeon supports a fixed set of types (primitives, lists, maps, and your declared data classes). It's not for shipping arbitrary objects across the boundary. That constraint is a feature — it keeps the wire format simple and the generated code predictable — but you'll occasionally reshape a native type into a Pigeon-friendly data class, and that's the intended workflow, not a workaround.

## Pigeon vs FFI: pick the right tool

The two native-interop mechanisms in Flutter solve different problems, and conflating them causes pain:

- **Pigeon / platform channels** — asynchronous message passing to *platform SDK code* written in Kotlin/Java or Swift/Objective-C. Camera, Bluetooth, notifications, anything that touches the Android/iOS SDK.
- **FFI (`dart:ffi`)** — direct, synchronous calls into a *C/C++ library*. Image processing, crypto, an existing native codebase, latency-critical loops.

If you need to call the platform's Kotlin/Swift APIs, Pigeon. If you need to call a C library fast and synchronously, FFI. I go deeper on the second path in [Dart FFI and native interop](https://blog.michaelsam94.com/dart-ffi-native-interop/), including where FFI's lack of a message boundary is exactly what you want and where it becomes a footgun.

My verdict: for anything that used to be a `MethodChannel`, Pigeon should be the default in 2026. The one-time cost is adding a generator step to your build; the ongoing benefit is that your Dart-to-native contract is compiler-checked in three languages at once. I can't think of a plugin I'd start today with hand-written channels — the boilerplate it removes was never adding value, only bugs.

## Resources

- [Pigeon package on pub.dev](https://pub.dev/packages/pigeon)
- [Flutter platform channels documentation](https://docs.flutter.dev/platform-integration/platform-channels)
- [Flutter plugin development guide](https://docs.flutter.dev/packages-and-plugins/developing-packages)
- [dart:ffi documentation](https://dart.dev/interop/c-interop)
- [Pigeon source on GitHub](https://github.com/flutter/packages/tree/main/packages/pigeon)
