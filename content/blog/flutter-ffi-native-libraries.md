---
title: "Calling C Libraries with dart:ffi"
slug: "flutter-ffi-native-libraries"
description: "Integrate native C libraries in Flutter via dart:ffi: loading dylibs, struct marshalling, memory ownership, and binding generation with ffigen."
datePublished: "2024-11-06"
dateModified: "2024-11-06"
tags: ["Flutter", "Dart"]
keywords: "Flutter FFI, dart:ffi, ffigen, native library Flutter, C interop Dart"
faq:
  - q: "What is dart:ffi in Flutter?"
    a: "dart:ffi is Dart's foreign function interface for calling C ABI functions from Dart without platform channels. It loads native shared libraries (.so, .dylib, .dll) and invokes functions with near-native performance. Use FFI for compute-heavy C/C++ libraries; use platform channels for OS APIs and UI integration."
  - q: "When should I use FFI instead of platform channels?"
    a: "FFI suits calling existing C libraries—crypto, compression, signal processing, game engines—where marshalling overhead of platform channels would hurt. Platform channels suit Android/iOS SDKs, permissions, and anything requiring Kotlin/Swift glue without a C API."
  - q: "How do I generate Dart FFI bindings?"
    a: "Use ffigen to parse C header files and generate Dart binding classes with correct struct layouts and function signatures. Manual binding works for small APIs; ffigen scales to large libraries and reduces struct alignment bugs that crash at runtime."
---

We needed AES-256 encryption matching our server implementation—available only as a battle-tested C library, not a Dart package. Platform channels would serialize every buffer across the JNI bridge. `dart:ffi` let us call `encrypt()` directly on `Uint8List` bytes with microsecond overhead. FFI isn't beginner territory—you own memory lifetimes—but when you need native speed or existing C code, it's the right tool.

## Minimal FFI example

```dart
import 'dart:ffi';
import 'dart:io';
import 'package:ffi/ffi.dart';

typedef NativeAdd = Int32 Function(Int32 a, Int32 b);
typedef DartAdd = int Function(int a, int b);

void main() {
  final lib = DynamicLibrary.open(_libPath());
  final add = lib.lookupFunction<NativeAdd, DartAdd>('add');
  print(add(40, 2)); // 42
}

String _libPath() {
  if (Platform.isMacOS) return 'libnative_add.dylib';
  if (Platform.isLinux) return 'libnative_add.so';
  if (Platform.isWindows) return 'native_add.dll';
  if (Platform.isAndroid) return 'libnative_add.so';
  if (Platform.isIOS) return 'native_add.framework/native_add';
  throw UnsupportedError('Unknown platform');
}
```

C source (`native_add.c`):

```c
#include <stdint.h>
int32_t add(int32_t a, int32_t b) { return a + b; }
```

Compile per platform and bundle in `android/src/main/jniLibs/`, `ios/Frameworks/`, etc.

## Structs and pointers

```dart
final class Point extends Struct {
  @Double()
  external double x;
  @Double()
  external double y;
}

typedef NativeDistance = Double Function(Pointer<Point> a, Pointer<Point> b);
typedef DartDistance = double Function(Pointer<Point> a, Pointer<Point> b);

double distance(Point a, Point b) {
  final lib = _openLib();
  final dist = lib.lookupFunction<NativeDistance, DartDistance>('distance');
  return dist(a.toNative(), b.toNative());
}
```

Allocate with `calloc` from `package:ffi`:

```dart
final p = calloc<Point>();
p.ref.x = 1.0;
p.ref.y = 2.0;
// use p
calloc.free(p); // MUST free native memory
```

Leaks in FFI crash the process eventually—always free in `finally` blocks.

## Passing strings and arrays

```dart
final input = 'hello'.toNativeUtf8();
try {
  final result = nativeProcessString(input);
  final output = result.toDartString();
} finally {
  calloc.free(input);
}
```

Byte arrays:

```dart
final bytes = calloc<Uint8>(data.length);
bytes.asTypedList(data.length).setAll(0, data);
try {
  nativeEncrypt(bytes, data.length);
} finally {
  calloc.free(bytes);
}
```

## ffigen for automatic bindings

`pubspec.yaml`:

```yaml
dev_dependencies:
  ffigen: ^14.0.0
```

`ffigen.yaml`:

```yaml
name: NativeCryptoBindings
description: Bindings for libcrypto
output: 'lib/src/crypto_bindings_generated.dart'
headers:
  entry-points:
    - 'native/crypto.h'
```

Generate:

```bash
dart run ffigen --config ffigen.yaml
```

Use generated classes instead of manual `lookupFunction` for large APIs.

## Flutter plugin structure

For reusable FFI plugins:

```
my_crypto/
  lib/my_crypto.dart
  src/
    my_crypto_bindings.dart
  native/
    crypto.c
    CMakeLists.txt
  android/build.gradle    # ndk-build or cmake
  ios/my_crypto.podspec
  pubspec.yaml
```

Flutter 3.16+ supports native assets for bundling libraries via `pubspec.yaml`:

```yaml
flutter:
  assets:
    - path: native/libcrypto.so
      platforms: [android]
```

Or use `flutter_rust_bridge` / `flutter_native_assets` for streamlined bundling.

## Thread safety and isolates

FFI calls block the calling isolate. Heavy C work belongs in background isolates:

```dart
Future<Uint8List> encryptAsync(Uint8List data) {
  return Isolate.run(() => _encryptInIsolate(data));
}
```

Pass `RootIsolateToken` if the C library callbacks into Dart via plugins. C libraries must be thread-safe if called from multiple isolates simultaneously—read the library docs.

### Common pitfalls

1. **Struct alignment** — wrong field order crashes silently. Use ffigen or `@Packed`.
2. **Memory leaks** — every `calloc` needs `free`.
3. **GC moving Dart objects** — pass pointers to pinned `NativeFinalizer` objects, not raw Dart lists, when C retains pointers async.
4. **Debug vs release libs** — ship release `.so` without debug symbols in production.
5. **iOS bitcode/App Store** — build universal frameworks for device + simulator separately.

### FFI vs platform channels decision

| Criterion | FFI | Platform channel |
|-----------|-----|------------------|
| Existing C library | Yes | Wrap in Kotlin/Swift first |
| OS API (camera, GPS) | No | Yes |
| Large binary blobs | Yes | Slow serialization |
| App store review complexity | Medium | Lower |

### CMake integration for Flutter plugins

Native FFI plugins use CMakeLists.txt in linux/windows folders:

```cmake
add_library(crypto SHARED crypto.c)
target_compile_definitions(crypto PRIVATE DART_SHARED_LIB)
```

Run `flutter test` on all desktop targets when shipping FFI—alignment bugs often appear on one architecture only. CI matrix arm64 and x64 for Linux builds.

Sanitize native library inputs—FFI bypasses Dart type safety at boundary; buffer overflows in C remain security risks. Fuzz test native entry points when wrapping third-party C libraries; valgrind on Linux CI catches leaks Dart GC won't manage.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

Schedule a quarterly review of this implementation against current SDK release notes—Flutter and cloud providers ship breaking changes on six-month cadences, and assumptions that held last year may need adjustment. Capture before-and-after metrics when you change configuration so regressions are obvious in retrospect rather than debated from memory.

## Resources

- [dart:ffi documentation](https://dart.dev/interop/c-interop)
- [ffi package (calloc, Utf8)](https://pub.dev/packages/ffi)
- [ffigen package](https://pub.dev/packages/ffigen)
- [Binding to native code (Flutter)](https://docs.flutter.dev/platform-integration/bind-native-code)
- [flutter_native_assets](https://docs.flutter.dev/tools/pubspec#native-assets)
