---
title: "Flutter Performance: Impeller and Killing Jank"
slug: "flutter-performance-impeller"
description: "A practical guide to Flutter performance: how Impeller ended shader jank, the 16ms frame budget, profiling with DevTools, and the rebuild patterns that cause stutter."
datePublished: "2026-05-10"
dateModified: "2026-05-10"
tags: ["Flutter", "Performance", "Impeller", "Dart"]
keywords: "Flutter performance, Impeller, Flutter jank, Flutter rendering, shader compilation, frame budget, DevTools"
faq:
  - q: "What problem does Impeller solve in Flutter?"
    a: "Impeller eliminates shader compilation jank. The old Skia backend compiled shaders lazily at runtime, causing the first run of an animation to stutter. Impeller precompiles its shaders during the build, so animations are smooth from the very first frame."
  - q: "What is the frame budget in Flutter?"
    a: "On a 60Hz display you have about 16 milliseconds per frame to do all UI and raster work; on a 120Hz display it's about 8ms. Exceeding that budget drops frames, which the user perceives as jank. Profiling is about finding what pushes a frame over budget."
  - q: "How do I profile Flutter performance?"
    a: "Run the app in profile mode (not debug) on a real device and use Flutter DevTools. The performance view shows per-frame UI and raster timings, flags janky frames, and the CPU profiler and rebuild counter help you find expensive widgets and unnecessary rebuilds."
---

Smoothness in a Flutter app comes down to one number: the **frame budget**. On a 60Hz screen you have roughly 16 milliseconds to build, lay out, paint, and rasterize each frame; on a 120Hz screen it's about 8. Blow that budget and the framework drops a frame, and the user feels it as jank even if they can't name it. Flutter performance work is, almost entirely, the discipline of finding what pushes frames over budget and getting it back under. The single biggest structural fix — the end of shader jank — arrived with **Impeller**, and the rest is profiling and rebuild hygiene.

I'll cover what Impeller changed, how to actually profile (most people do it wrong), and the concrete patterns that cause and cure stutter in real apps.

## Impeller: why the first animation used to stutter

For years Flutter's most-reported performance complaint was oddly specific: an animation would stutter the *first* time it ran, then be smooth forever after. The cause was the old Skia backend compiling shaders **lazily at runtime**. The first time a particular visual effect appeared, the GPU shader for it got compiled on the spot, blowing the frame budget for those frames.

**Impeller**, now the default rendering engine on mobile, fixes this by precompiling its shaders **ahead of time** during the build. There's no runtime shader compilation to stall a frame, so animations are smooth from the very first run. If you were carrying workarounds from the Skia era — bundling shader warm-up files (`--bundle-sksl-path`) to pre-warm shaders — you can delete them; they're obsolete under Impeller. This is the change that quietly removed a whole category of bug reports, and it's a big part of why I described Flutter as finally smooth-by-default in [the state of Flutter in 2026](https://blog.michaelsam94.com/state-of-flutter-2026/).

## Profile in profile mode, on a real device

The most common profiling mistake is measuring in debug mode. **Debug mode is not representative** — assertions, no compiler optimizations, and JIT make everything slower and noisier. Always profile with:

```bash
flutter run --profile
```

on a **physical device**, not the emulator, because GPU behavior differs. Then open **Flutter DevTools** and go to the Performance view. What you're looking for:

- The **frame chart** with UI (Dart/build) time and Raster (GPU) time split per frame. A frame is janky when either bar exceeds the budget line.
- **Which side is slow.** Tall UI bars mean your Dart build/layout is expensive — too many rebuilds, heavy `build()` methods. Tall raster bars mean the GPU is struggling — expensive clips, opacity layers, shadows, or overdraw.

That UI-vs-raster split is the first diagnostic question. It tells you whether to fix your widget tree or your painting.

## Rebuilds: the usual UI-side culprit

Most UI-side jank is **unnecessary rebuilds** — Flutter rebuilding large subtrees when only a small part changed. The fixes are mechanical once you see them:

```dart
// Bad: setState at the top rebuilds the whole page every tick.
class _PageState extends State<Page> {
  double _scroll = 0;
  Widget build(BuildContext c) => Column(children: [
    ExpensiveHeader(opacity: 1 - _scroll / 300), // rebuilds constantly
    const HeavyList(),                            // rebuilds for no reason
  ]);
}
```

Three habits fix the majority of it:

- **`const` everywhere you can.** A `const` widget is never rebuilt. It's the cheapest optimization in Flutter and the most skipped.
- **Push state down.** Move the changing state into the smallest widget that needs it so rebuilds are localized, rather than lifting it up and rebuilding the world.
- **Scope listeners.** With Riverpod or Bloc, `select`/`buildWhen` so a widget only rebuilds when the specific field it reads changes — not on every state emission. This mirrors the state-scoping discipline I lean on in [Riverpod vs Bloc](https://blog.michaelsam94.com/riverpod-vs-bloc-2026/).

Turn on the **rebuild counter** in DevTools (or `debugProfileBuildsEnabled`) to see exactly which widgets rebuild and how often. Guessing here wastes hours; the counter tells you in seconds.

## Raster-side jank: what's expensive to paint

When the raster bar is the tall one, the GPU is doing too much. The usual offenders:

| Cost | Cheaper alternative |
| --- | --- |
| `Opacity` widget wrapping a subtree | `Opacity` on a leaf, or `AnimatedOpacity`, or fade at paint time |
| `saveLayer` (clips with anti-alias, blend modes) | Avoid unnecessary clipping; use `borderRadius` on decorations |
| Large blurred shadows / `BackdropFilter` | Smaller blur radius, cache static blurs |
| Overdraw (many stacked opaque layers) | Flatten the tree, remove hidden layers |

`Opacity` and `saveLayer` are the classic traps because they force the engine to render a subtree to an offscreen buffer and composite it — expensive. Wrapping a whole animated section in `Opacity` is a frequent cause of raster jank; applying opacity as low in the tree as possible, or using `AnimatedOpacity` which is optimized, usually clears it.

## Lists and images

Two more high-frequency issues in real apps:

- **Always use builder constructors** (`ListView.builder`, `GridView.builder`) for anything scrollable and non-trivial, so only visible items are built. A `ListView(children: [...])` with hundreds of items builds them all up front.
- **Size and cache images.** Decoding a full-resolution image to display a thumbnail wastes memory and time. Use `cacheWidth`/`cacheHeight` to decode at display size, and a caching image widget for network images. Oversized image decoding is a stealth cause of both jank and out-of-memory issues on lower-end Android devices.

## A repeatable workflow

When someone hands me a "the app feels laggy" report, I run the same loop:

1. Reproduce in `--profile` on a real mid-range device (not a flagship — users aren't all on flagships).
2. Open DevTools Performance, find the janky frames, note UI vs raster.
3. If UI-heavy: turn on the rebuild counter, find the over-rebuilding widget, add `const`, scope the state.
4. If raster-heavy: look for `Opacity`, `saveLayer`, big shadows, overdraw; simplify the painting.
5. Re-measure. Confirm the frame is back under budget rather than assuming the fix worked.

That measure-fix-measure loop is the whole job. Impeller removed the worst systemic cause of jank for free, which means the remaining performance work is almost always in your own widget tree and painting — and it's very findable with the profiler. Flutter gives you excellent tools to see exactly where the milliseconds go; the teams that ship smooth apps are simply the ones who look. If mobile performance under real-world conditions is your concern more broadly, I've written about [handling flaky networks on mobile](https://blog.michaelsam94.com/handling-flaky-networks-mobile/) too.

## Resources

- [Flutter performance best practices](https://docs.flutter.dev/perf/best-practices)
- [Impeller rendering engine](https://docs.flutter.dev/perf/impeller)
- [Using the Performance view in DevTools](https://docs.flutter.dev/tools/devtools/performance)
- [Flutter DevTools overview](https://docs.flutter.dev/tools/devtools/overview)
- [Improving rendering performance](https://docs.flutter.dev/perf/rendering-performance)
- [Dart DevTools CPU profiler](https://docs.flutter.dev/tools/devtools/cpu-profiler)
