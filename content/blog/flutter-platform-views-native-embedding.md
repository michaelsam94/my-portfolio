---
title: "Embedding Native Views in Flutter"
slug: "flutter-platform-views-native-embedding"
description: "Platform views embed Android and iOS native UI inside Flutter widgets. Hybrid composition, performance trade-offs, and when to use texture mode."
datePublished: "2025-02-03"
dateModified: "2025-02-03"
tags: ["Flutter", "Dart", "Platform Views", "Mobile"]
keywords: "Flutter platform views, UiKitView AndroidView, hybrid composition Flutter, native embedding Flutter, PlatformViewLink"
faq:
  - q: "When should I use a platform view instead of a Flutter widget?"
    a: "Use platform views when you need native controls Flutter does not replicate well—Google Maps, WebView, camera preview, legacy UIKit/Android views—or when SDK vendors ship native-only widgets. Prefer pure Flutter when possible; platform views add composition cost."
  - q: "Why do platform views cause performance issues in lists?"
    a: "Each platform view is a separate native surface composited with Flutter layers. Many simultaneous views multiply GPU and memory overhead. Use lazy creation, limit concurrent views, or snapshot static native content into Flutter textures for scroll-heavy UIs."
  - q: "What is the difference between hybrid composition and texture mode?"
    a: "Hybrid composition interleaves Flutter and native layers in the platform view hierarchy—better touch handling, higher overhead. Texture mode renders native content into a GPU texture Flutter draws—better for many instances, trickier hit testing. Android defaults evolved; check current docs for your target SDK."
---

Google Maps in a Flutter app is not a Dart widget painted on Canvas. It is a real `MapView` or `MKMapView` punched through the Flutter layer stack—a platform view. The first time I embedded a native camera preview inside a `ListView`, frames dropped to 40 FPS with two items on screen. Understanding *how* platform views composite explains why, and which mode fixes it.

Platform views let Flutter display embedded Android `View` or iOS `UIView` instances via `AndroidView` and `UiKitView` widgets (or plugin wrappers like `google_maps_flutter`).

## Basic embedding

Register a factory on the native side, reference it from Dart:

```dart
Widget buildMap() {
  if (Platform.isAndroid) {
    return AndroidView(
      viewType: 'com.example/map_view',
      creationParams: {'zoom': 14},
      creationParamsCodec: const StandardMessageCodec(),
    );
  }
  return UiKitView(
    viewType: 'com.example/map_view',
    creationParams: {'zoom': 14},
    creationParamsCodec: const StandardMessageCodec(),
  );
}
```

Android registers in `MainActivity` or plugin:

```kotlin
flutterEngine.platformViewsController.registry.registerViewFactory(
  "com.example/map_view",
  MapViewFactory()
)
```

iOS registers in `AppDelegate` with a `FlutterPlatformViewFactory`.

## Composition modes and performance

Flutter must blend Skia-rendered content with native surfaces. Two strategies dominate:

**Hybrid composition** — native view sits in the hierarchy under Flutter overlays. Accurate z-order and gestures; expensive with many views or heavy Flutter overlays on top.

**Texture (TLHC on Android)** — native view renders to a texture; Flutter treats it like an image. Cheaper for scrolling lists of small previews; touch routing requires careful configuration.

For a full-screen map with Flutter FABs on top, hybrid is usually correct. For eight thumbnail camera previews in a grid, texture mode or replacing previews with periodic snapshots wins.

## PlatformViewLink for advanced control

`PlatformViewLink` exposes `initSurfaceAndroidView` and surface lifecycle for custom sizing:

```dart
PlatformViewLink(
  viewType: 'com.example/player',
  surfaceFactory: (context, controller) {
    return AndroidViewSurface(
      controller: controller as AndroidViewController,
      gestureRecognizers: const <Factory<OneSequenceGestureRecognizer>>{},
      hitTestBehavior: PlatformViewHitTestBehavior.opaque,
    );
  },
  onCreatePlatformView: (params) {
    return PlatformViewsService.initSurfaceAndroidView(
      id: params.id,
      viewType: 'com.example/player',
      layoutDirection: TextDirection.ltr,
      creationParams: null,
      creationParamsCodec: const StandardMessageCodec(),
    )
      ..addOnPlatformViewCreatedListener(params.onPlatformViewCreated)
      ..create();
  },
)
```

Use when plugins need custom gesture recognizer sets or delayed creation until the view scrolls into viewport.

## Gestures and scrolling

Nested scrolling between Flutter `ScrollView` and embedded native scrollers fights over pointers. Pass `gestureRecognizers` to platform views so horizontal map pans win over parent vertical drags:

```dart
AndroidView(
  viewType: 'com.example/map_view',
  gestureRecognizers: <Factory<OneSequenceGestureRecognizer>>{
    Factory<EagerGestureRecognizer>(() => EagerGestureRecognizer()),
  },
)
```

Test on real devices—simulators hide touch conflicts.

## Lifecycle and memory

Dispose native resources when the platform view is destroyed. Camera and WebView leak badly if factories hold static references. Tie native object lifetime to `PlatformView` disposal callbacks.

Avoid rebuilding platform views on every parent `setState`. Give them stable keys and hoist state above unrelated UI.

## Alternatives before reaching for platform views

- **FFI + texture**: render in C/native, ship pixels to `Texture` widget—more work, maximum control.
- **Flutter implementation**: Mapbox GL, video players with pure Dart/OpenGL—check maturity for your use case.
- **Modal native screen**: push full native Activity/ViewController for complex flows, return result to Flutter—simpler than inline embedding.

## Sizing and layout constraints

Platform views participate in Flutter layout like any child—they need bounded constraints. In `ListView`, give explicit height:

```dart
SizedBox(
  height: 200,
  child: AndroidView(viewType: 'map_preview', ...),
)
```

Unbounded height in scrollables throws layout exceptions or renders zero-height native views silently on some platforms.

## Texture hybrid composition on Android

Android Texture Layer Hybrid Composition (TLHC) balances gesture accuracy and performance for many embedded views. Consult current Flutter Android platform view docs for default mode on your `compileSdk`. Switch modes when profiling shows GPU overload vs touch miss rate.

Test on API 21–34 matrix—WebView and Map behavior differs on older devices still in emerging markets.

## Accessibility

Semantic labels on wrapper widgets help TalkBack/VoiceOver describe embedded content Flutter cannot see inside:

```dart
Semantics(
  label: 'Interactive map showing delivery route',
  child: AndroidView(...),
)
```

Native controls inside platform view may expose their own semantics—avoid duplicate focus traps.

## Plugin vs inline factory

Apps embedding one map: use `google_maps_flutter`. Custom native SDK without plugin: register factory in app `MainActivity` during spike, extract to federated plugin when second app needs it.

Document viewType strings as constants shared between Dart and native to prevent typo mismatches.

## Release testing matrix

Platform views fail in goldens and many widget tests—maintain device farm checklist: map pan/zoom, WebView OAuth, camera rotation, dark mode native chrome overlap with Flutter AppBar.


## Hybrid composition migration

When upgrading Flutter SDK, re-test platform views—Android default composition mode changes between releases; release notes flag migration steps.

## Z-order and PlatformViewStack

Overlapping platform views and Flutter widgets require careful ordering—Flutter overlay on map for pins works; complex z-index needs platform-specific tuning.

## Snapshot fallback

For scroll performance, render native view to image once when static—display `Image.memory` in list, tap opens full interactive platform view—product trade-off.

## CI without devices

Platform views skip widget tests—maintain native unit tests on factories in Android/iOS modules validating expected view type registration.

## Unit tests for factories

Android \`PlatformViewFactory\` JVM tests instantiate factory with mock context verifying create returns non-null view—cheap CI signal without Flutter integration test cost.

## Additional release coordination

Platform view heavy releases soak 24 hours on internal dogfood track observing crash-free sessions metric before phased rollout percentage increase. Release notes mention platform view SDK bump explicitly so support searches knowledge base articles updated same day.

## Resources

- [Hosting native Android views (Flutter docs)](https://docs.flutter.dev/platform-integration/android/platform-views)
- [Hosting native iOS views (Flutter docs)](https://docs.flutter.dev/platform-integration/ios/platform-views)
- [PlatformViewLink API](https://api.flutter.dev/flutter/widgets/PlatformViewLink-class.html)
- [google_maps_flutter plugin](https://pub.dev/packages/google_maps_flutter)
- [Flutter platform view performance](https://docs.flutter.dev/platform-integration/platform-views#performance)
