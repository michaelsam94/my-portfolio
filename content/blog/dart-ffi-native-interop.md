---
title: "Dart FFI for Native Interop"
slug: "dart-ffi-native-interop"
description: "A hands-on guide to Dart FFI for native interop: calling C libraries from Flutter, generating bindings with ffigen, memory ownership, and threading pitfalls."
datePublished: "2026-05-23"
dateModified: "2026-05-23"
tags: ["Flutter", "Dart", "Native Interop", "Performance"]
keywords: "Dart FFI, native interop Dart, C interop Flutter, ffigen, native bindings, foreign function interface"
faq:
  - q: "What is Dart FFI?"
    a: "Dart FFI (foreign function interface) is a built-in mechanism for calling native C code directly from Dart, without a platform channel or plugin round-trip. You load a shared library, describe the C function signatures with Dart types, and invoke them synchronously in-process. It's how Flutter apps reuse existing C/C++ libraries — codecs, crypto, ML kernels, database engines — with near-native call overhead."
  - q: "When should I use FFI instead of a platform channel?"
    a: "Use FFI when you need to call a C/C++ library and want synchronous, low-overhead calls that run on the same isolate — image processing, cryptography, or any compute-heavy native routine. Use a platform channel when you need to talk to platform SDKs (camera, Bluetooth, Android/iOS APIs written in Kotlin/Swift) rather than a C ABI. FFI is for C interop; channels are for platform-service interop."
  - q: "Does Dart FFI work across all Flutter platforms?"
    a: "FFI works wherever you can ship and load a native library: Android, iOS, macOS, Windows, and Linux. It does not work on the web, since there's no native shared library to bind to — web builds compile to JavaScript/WASM and use different interop. If you need one codebase across mobile, desktop, and web, gate the FFI paths and provide a web fallback."
---

Sometimes the fastest path to a feature is a C library that already solves the problem — a battle-tested crypto implementation, an image codec, a physics engine, an embedded database. Dart FFI is how you call that code directly from Flutter: you load the shared library, map the C function signatures to Dart types, and invoke them in-process with call overhead measured in nanoseconds, not the milliseconds a platform channel round-trip can cost.

I reach for FFI when the alternative is either reimplementing a mature C library in Dart (slow to write, easy to get subtly wrong) or paying serialization cost across a channel for something that should be a plain function call. Below is the practical shape of it: the low-level API, generating bindings with `ffigen`, and the memory and threading traps that separate a working demo from a stable production integration.

## The low-level mechanics

At its core, FFI is three moves: open a dynamic library, look up a symbol, and describe its signature so Dart can marshal arguments. Here's the canonical example — calling a C function that adds two integers:

```dart
import 'dart:ffi';
import 'dart:io';

typedef NativeAdd = Int32 Function(Int32 a, Int32 b);
typedef DartAdd = int Function(int a, int b);

final dylib = DynamicLibrary.open(
  Platform.isAndroid ? 'libnative_add.so' : 'native_add.framework/native_add',
);

final add = dylib.lookupFunction<NativeAdd, DartAdd>('native_add');

void main() {
  print(add(40, 2)); // 42
}
```

Note the two typedefs. `NativeAdd` uses FFI's native types (`Int32`) to describe the C ABI; `DartAdd` uses idiomatic Dart types (`int`) for the call site. `lookupFunction` bridges them. Get this mapping wrong — say, `Int32` where the C side expects `Int64` — and you get silent corruption, not a compile error. The type discipline here is unforgiving, which is exactly why you rarely write it by hand.

## Let ffigen write the bindings

Hand-writing FFI typedefs for a real library with hundreds of functions and nested structs is a recipe for subtle bugs. `ffigen` parses your C header with libclang and generates the Dart bindings for you. You point it at the header and configure output in `pubspec.yaml` or a dedicated config:

```yaml
# ffigen.yaml
name: NativeCryptoBindings
description: Bindings for libnativecrypto
output: 'lib/src/crypto_bindings.dart'
headers:
  entry-points:
    - 'native/include/crypto.h'
  include-directives:
    - '**crypto.h'
```

Run `dart run ffigen --config ffigen.yaml` and you get a typed Dart class wrapping every exported function and struct. This is the workflow I recommend for anything beyond a couple of functions — the generated code is more correct than what you'd type, and it regenerates cleanly when the header changes. Treat the bindings as build artifacts, not hand-maintained source.

## Memory is your problem now

The garbage collector does not manage native memory. The instant you allocate on the native heap, you own the lifecycle, and this is where most FFI bugs live. To pass a string or buffer to C, you allocate, copy, call, and — critically — free.

```dart
import 'package:ffi/ffi.dart';

String processNative(String input) {
  final ptr = input.toNativeUtf8();      // allocates on the native heap
  try {
    final resultPtr = _nativeProcess(ptr);
    return resultPtr.toDartString();
  } finally {
    calloc.free(ptr);                     // you MUST free it
  }
}
```

The `try/finally` is not optional politeness — skip the `free` and you leak on every call. For long-lived native objects, `NativeFinalizer` lets you attach cleanup that runs when the Dart wrapper is collected, but I treat that as a safety net, not the primary strategy. Explicit ownership with `finally` is easier to reason about and audit. The rule I hold teams to: for every native allocation, the freeing code should be visible in the same function.

## Threading and the isolate boundary

By default, FFI calls run synchronously on the calling isolate, which means a long native call **blocks that isolate** exactly like long Dart code would. If the call takes 30ms and you make it on the main isolate, you drop frames — the same failure mode covered in [isolates for heavy compute in Flutter](https://blog.michaelsam94.com/flutter-isolates-heavy-compute/). The fix is the same: run heavy FFI calls on a background isolate, or use `Isolate.run` to offload them.

The subtler issue is native code calling *back* into Dart. Callbacks from C to Dart must be handled carefully — `NativeCallable.isolateLocal` and `NativeCallable.listener` exist precisely because a native thread can't just invoke arbitrary Dart. If your C library calls you back from its own thread pool, you need the async-callback machinery, and getting it wrong produces crashes that are miserable to debug. Read the docs on this before you wire up any callback-heavy library.

## FFI vs platform channels: pick the right door

They solve different problems, and conflating them causes pain.

| Concern | Dart FFI | Platform channel |
|---|---|---|
| Talks to | C/C++ ABI | Kotlin/Swift platform code |
| Call cost | Near-native, synchronous | Serialized, async |
| Best for | Codecs, crypto, DB engines, math | Camera, sensors, OS SDKs |
| Web support | No | No (channels), but MethodChannel has web plugins |

If your goal is to call the Android or iOS *platform* APIs, FFI is the wrong tool — you want the approach in [type-safe platform channels with Pigeon](https://blog.michaelsam94.com/flutter-pigeon-platform-channels/), which generates typed messaging code for Kotlin/Swift. FFI shines when you have a self-contained native library with a C interface and you want to call it like a local function.

## Where FFI really pays off

The highest-leverage FFI use I've shipped was on the embedded side — talking to device SDKs and native protocol stacks where a C library was the only sane interface, the kind of scenario in [Flutter for embedded and IoT](https://blog.michaelsam94.com/flutter-embedded-iot/). Reusing a vendor's proven C driver instead of reimplementing a binary protocol in Dart saved weeks and eliminated a whole class of parsing bugs.

My closing advice: use `ffigen`, never hand-roll bindings for real libraries; make memory ownership explicit and local; keep heavy calls off the main isolate; and write a thin, idiomatic Dart wrapper around the raw bindings so the rest of your app never sees a `Pointer`. Done that way, FFI turns the entire C ecosystem into callable Dart — with the caveat that you've also inherited C's discipline about memory and threads, and the runtime will not remind you politely when you forget.

## Resources

- [Dart — C interop with FFI](https://dart.dev/interop/c-interop)
- [Flutter — binding to native code using FFI](https://docs.flutter.dev/platform-integration/android/c-interop)
- [dart:ffi library reference](https://api.dart.dev/stable/dart-ffi/dart-ffi-library.html)
- [package:ffigen on pub.dev](https://pub.dev/packages/ffigen)
- [package:ffi (allocation helpers)](https://pub.dev/packages/ffi)
- [NativeFinalizer API reference](https://api.dart.dev/stable/dart-ffi/NativeFinalizer-class.html)
