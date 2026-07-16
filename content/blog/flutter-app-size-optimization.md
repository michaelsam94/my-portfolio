---
title: "Shrinking Flutter App Size"
slug: "flutter-app-size-optimization"
description: "Measure and reduce Flutter APK/IPA size: tree shaking, deferred loading, asset compression, ABI splits, and the build flags that actually move the needle."
datePublished: "2024-09-16"
dateModified: "2024-09-16"
tags: ["Flutter", "Dart"]
keywords: "Flutter app size, APK size reduction, tree shaking, deferred components, --split-per-abi, app bundle optimization"
faq:
  - q: "What is a reasonable Flutter app size?"
    a: "A minimal Flutter APK often lands at 15–20 MB per ABI after optimization; unoptimized debug builds can exceed 100 MB. iOS IPAs are typically 25–40 MB download size for medium-complexity apps. Compare against competitors in your category—utilities should stay under 30 MB; games with assets will be larger."
  - q: "How do I measure Flutter app size accurately?"
    a: "Run flutter build apk --analyze-size or flutter build appbundle --analyze-size to generate a JSON breakdown by package, font, and asset. Use the DevTools app size tool to visualize. Never optimize based on debug build size—always profile release builds with obfuscation enabled."
  - q: "Does removing unused packages reduce Flutter app size?"
    a: "Yes, significantly. Tree shaking removes unused Dart code in release builds, but native code bundled by plugins stays unless you remove the dependency. Audit pubspec.yaml quarterly—each plugin may add hundreds of KB to several MB of native libraries."
---

Google Play warned us about app size affecting install conversion. Our Flutter APK was 48 MB. After a focused optimization sprint—ABI splits, font subsetting, and dropping two unused SDKs—we shipped a 19 MB per-ABI download. None of it required rewriting features. Flutter app size is mostly packaging decisions you make at build time, not runtime performance tuning.

## Measure before cutting

Generate a size analysis report:

```bash
flutter build apk --release --analyze-size --target-platform android-arm64
```

Open the output JSON in DevTools → App Size tool. You'll see breakdowns by:

- **Package** — which Dart libraries dominate
- **Font** — often 1–3 MB if you ship full Noto/Roboto families
- **Asset** — images, Lottie, Rive files
- **Native lib** — `libflutter.so` plus plugin `.so` files

Baseline first. Screenshot the treemap. Every optimization should show measurable delta.

## Dart code: tree shaking and deferred loading

Release builds tree-shake unused Dart automatically. Verify you're building release:

```bash
flutter build apk --release --obfuscate --split-debug-info=build/debug-info
```

**Deferred components** (Android dynamic feature modules) load code on demand:

```dart
import 'package:my_app/heavy_feature.dart' deferred as heavy;

Future<void> openHeavyFeature() async {
  await heavy.loadLibrary();
  heavy.showFeature();
}
```

Configure in `deferred-components` section of `pubspec.yaml`. Useful for admin panels, AR modules, or regional features most users never touch.

Remove dead dependencies from `pubspec.yaml`. Run `dart pub deps` and question anything not imported.

## Android-specific optimizations

**Split per ABI** — don't ship x86 + arm64 + armeabi-v7a in one fat APK:

```bash
flutter build apk --release --split-per-abi
```

Users download only their architecture—typically 40% smaller than universal APK.

**App Bundle (AAB)** — Play Store generates optimized splits automatically:

```bash
flutter build appbundle --release
```

Enable `android:extractNativeLibs="false"` in manifest for Android 6+ to reduce install size (requires uncompressed native libs in AAB).

**Shrink native libs** — in `android/app/build.gradle`:

```gradle
android {
    buildTypes {
        release {
            ndk {
                debugSymbolLevel 'SYMBOL_TABLE'
            }
        }
    }
}
```

Strip unused ABIs in `defaultConfig`:

```gradle
ndk {
    abiFilters 'armeabi-v7a', 'arm64-v8a'
}
```

Drop x86 unless you target emulators in production (you don't).

## iOS-specific optimizations

Build with size report:

```bash
flutter build ipa --release --analyze-size
```

**Bitcode** is deprecated; focus on asset catalogs and thinning. App Store Connect shows per-device-variant sizes after upload.

Remove unused **entitlements** and **frameworks** from Xcode project. Each plugin may embed static libraries—audit `Podfile` and remove pods you don't need.

## Asset optimization

Assets often account for 30–50% of app size:

| Asset type | Action |
|------------|--------|
| PNG screenshots | Convert to WebP (Android), HEIC where supported |
| SVG icons | Prefer vector; compile to font icon sets for repeated glyphs |
| Lottie JSON | Run lottie-optimizer, remove hidden layers |
| Audio | Use AAC at appropriate bitrate |

Use resolution-aware assets—don't ship 4x images for 1x displays:

```yaml
flutter:
  assets:
    - path: assets/images/
      variants:
        - resolution: 1.5x
        - resolution: 2.0x
        - resolution: 3.0x
```

**Font subsetting** with `google_fonts` downloads at runtime (trade-off: network) or subset locally:

```dart
GoogleFonts.config.allowRuntimeFetching = false;
```

Ship only weights you use—Regular + Bold, not nine weights.

## Plugin audit

Each plugin adds native code. Before adding `some_heavy_sdk`:

1. Check APK diff after adding (`--analyze-size` before/after).
2. Prefer pure-Dart alternatives when native features aren't needed.
3. Use **conditional imports** for platform-specific heavy code.

I removed an analytics SDK we weren't calling—saved 2.1 MB overnight.

### CI size regression gates

Add a CI step that fails if APK size grows more than 5%:

```bash
flutter build apk --release --split-per-abi --target-platform android-arm64
SIZE=$(stat -f%z build/app/outputs/flutter-apk/app-arm64-v8a-release.apk)
echo "APK size: $SIZE bytes"
# Compare against baseline.json threshold
```

Track size per release in a spreadsheet or Datadog metric. Regressions caught in PR review, not after Play Console warnings.

### ProGuard and R8 for Android

Enable minification in release builds:

```gradle
buildTypes {
    release {
        minifyEnabled true
        shrinkResources true
        proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
    }
}
```

Keep ProGuard rules for plugins using reflection—Flutter embedding and Gson-style serializers need keep rules. Test release builds on device after enabling; minification breaks plugins that don't ship consumer ProGuard files.

Compare APK Analyzer output before/after adding each new plugin in PR description—make size cost visible at review time.

Review pubspec fonts block—each bundled TTF adds weight. google_fonts fetching at runtime trades install size for first-open latency; document offline behavior when CDN unreachable. iOS App Thinning reduces download size automatically but CI analyze-size still guides development decisions.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

Measure APK size per ABI split in CI — universal APKs hide 40% size bloat from bundling all native architectures.

## Resources

- [Flutter App Size Documentation](https://docs.flutter.dev/perf/app-size)
- [Deferred Components Guide](https://docs.flutter.dev/perf/deferred-components)
- [Android App Bundle Documentation](https://developer.android.com/guide/app-bundle)
- [DevTools App Size Tool](https://docs.flutter.dev/tools/devtools/app-size)
- [Apple Reducing App Size](https://developer.apple.com/documentation/xcode/reducing-your-app-s-size)
