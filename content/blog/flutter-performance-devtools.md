---
title: "Profiling Flutter with DevTools"
slug: "flutter-performance-devtools"
description: "DevTools shows where frame time goes—layout, build, raster, shader compilation. How to profile jank, memory leaks, and network overhead in real apps."
datePublished: "2025-01-31"
dateModified: "2025-01-31"
tags: ["Flutter", "Dart", "Performance", "Mobile"]
keywords: "Flutter DevTools profiling, Flutter performance overlay, timeline Flutter, memory DevTools, shader compilation jank"
faq:
  - q: "What is a good frame budget in Flutter?"
    a: "At 60 Hz you have 16.67 ms per frame; at 120 Hz, 8.33 ms. Total frame time includes UI thread (build/layout) and raster thread (paint). Either thread exceeding budget causes jank. DevTools splits them so you know which to optimize."
  - q: "Why does my app jank only on first scroll?"
    a: "Often shader compilation or lazy widget initialization. Check the Performance overlay for raster spikes and DevTools for shader events. Warm up shaders with SKSL warm-up files or pre-build expensive widgets off-screen in debug."
  - q: "Can I use DevTools on release builds?"
    a: "Full DevTools requires debug or profile mode. Profile mode is closest to release performance while still exposing the timeline. Use profile builds for meaningful frame metrics; debug mode includes extra checks that skew timing."
---

The product manager said scrolling felt "sticky." The frame counter showed solid 60 FPS. Then I opened DevTools, enabled the performance timeline, and watched the raster thread spike to 28 ms every time a blurred header entered the viewport. The UI thread was fine; I was optimizing the wrong thread. DevTools is how you stop guessing.

Flutter DevTools is a browser-based suite bundled with the SDK: Performance, CPU Profiler, Memory, Network, and Inspector. Connect it to a running app in debug or profile mode and you get frame charts, allocation tracking, and widget rebuild stats that the in-app performance overlay alone does not explain.

## Launching DevTools

```bash
flutter run --profile
# in another terminal
dart devtools
```

Or use VS Code / Android Studio Flutter commands: "Open DevTools" while the app runs. Profile mode disables most debug assertions but keeps the service protocol—use it for performance work.

## Reading the Performance tab

Record a timeline while reproducing jank—scroll the suspect list, open the heavy screen, animate the transition.

Each frame shows:

- **Build** — widget rebuild cost on UI isolate
- **Layout** — constraint propagation
- **Paint** — layer recording
- **Raster** — GPU work on raster thread

Red bars mean budget exceeded. Click a slow frame to see stack samples: which widget's `build` ran, which `RenderObject` layout thrashed.

Look for:

- Long `build()` chains from missing `const` or overly broad `setState`
- Expensive `LayoutBuilder` inside lists
- `BackdropFilter` and blur on large areas (raster killers)

## Performance overlay in the app

Enable during development:

```dart
MaterialApp(
  showPerformanceOverlay: true,
  ...
);
```

Green bars under 16 ms are good. Watch for green UI bars paired with red raster bars—that pattern screams "simplify painting, not widgets."

## CPU Profiler for hot Dart code

Switch to CPU Profiler, sample while executing the slow interaction, read the call tree. Sort by self time to find JSON parsing, image decode in Dart, or synchronous file I/O on the UI isolate.

Move heavy work to isolates or `compute()`. Cache decoded images. The profiler tells you *what* function; your architecture fix determines *where* it runs.

## Memory tab and leaks

Take a heap snapshot before and after navigating away from a screen ten times. Filter by class; if `MyHeavyScreenState` instances grow without bound, you leaked a `StreamSubscription` or `AnimationController`.

Use "Track allocations" during the navigation loop, then diff snapshots. DevTools links retaining paths—follow them to the static callback or undisposed listener.

## Network and size debugging

The Network tab logs HTTP from Dart's `HttpClient` and some package integrations. Pair with the App Size tool:

```bash
flutter build apk --analyze-size
```

Find oversized assets and tree-shaken-but-still-large dependencies before they ship.

## Shader compilation jank

First-run stutter on complex gradients or blurs is often driver shader compilation. Capture timeline events labeled shader. Mitigations:

- Reduce visual effects on first paint
- Ship `FragmentProgram` warm-up or SKSL warm-up file (advanced, platform-specific)
- Replace expensive effects with pre-rendered assets where acceptable

## Workflow I use on every perf bug

1. Reproduce in **profile** mode on a mid-tier device, not the flagship on your desk.
2. Record timeline for 5–10 seconds of the bad interaction.
3. Identify UI vs raster bottleneck from frame chart.
4. If UI: Inspector rebuild stats, add `const`, split widgets, check unnecessary listeners.
5. If raster: RepaintBoundary, simpler clips, fewer opacity layers.
6. Re-record to prove the fix—numbers, not vibes.

## Network profiling in practice

DevTools Network tab shows Dart-level HTTP when using compatible clients. Pair with Charles or Proxyman for TLS-level inspection when debugging certificate pinning. Log correlation IDs in app and match timeline spans if using OpenTelemetry.

For image-heavy screens, check decoded image cache in Memory tab—oversized network images decoded to full resolution waste RAM even if displayed small.

## Jank reproduction checklist

When PM reports jank:

1. Identify device model and refresh rate (60 vs 120 Hz)
2. Reproduce in profile mode, not debug
3. Record 10s timeline during interaction
4. Note UI vs raster thread offender
5. Apply one fix, re-record—avoid changing five things at once

Common fixes by thread:

- **UI thread**: split widgets, const, provider select, move JSON parse off UI isolate
- **Raster**: RepaintBoundary, simplify clips, reduce blur/backdrop filters

## CI performance regression gates

Integrate `flutter drive` or integration benchmarks on key flows in CI—compare frame build times against baseline on consistent hardware (self-hosted Mac mini or Firebase Test Lab with pinned device). DevTools is local; CI needs scripted metrics.

Track APK/IPA size each release—`flutter build apk --analyze-size` in CI artifact.

## Working with Impeller

Impeller changes shader compilation profile—first-frame jank may differ from Skia. When users upgrade Flutter SDK, re-profile hero animations and custom painters. Enable Impeller per platform flags in current Flutter docs and compare timeline side by side.

## Teaching the team

Record a 15-minute internal demo: open DevTools, show rainbow repaint mode, walk one real jank fix. Docs alone rarely stick—live profiling on your app's worst screen does.


## Timeline export

Export timeline trace share with teammates—DevTools saves `.json` trace for async debugging of jank reports from beta users if integrated with performance overlay screenshot.

## Memory leaks from streams

Memory tab diff snapshots when leaving screen—StreamSubscription on provider not cancelled shows retaining path to closed route State.

## CPU vs GPU bound

If CPU profiler clean but jank persists, suspect GPU/raster—do not optimize Dart code further; switch to repaint isolation or simpler effects.

## Field profiling

Profile mode on real device in field via internal beta flag—QA enables performance overlay, records video for engineering triage.

## Resources

- [Flutter DevTools documentation](https://docs.flutter.dev/tools/devtools)
- [Flutter performance profiling](https://docs.flutter.dev/perf/ui-performance)
- [Improving rendering performance](https://docs.flutter.dev/perf/rendering-performance)
- [dart devtools package](https://pub.dev/packages/devtools)
- [Flutter performance FAQ](https://docs.flutter.dev/perf/faq)
