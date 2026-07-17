---
title: "Real-Time Image Analysis with CameraX"
slug: "android-camerax-image-analysis"
description: "Build a real-time CameraX ImageAnalysis pipeline: backpressure strategy, YUV vs RGBA output, frame throttling, and feeding frames to ML Kit without dropping the UI."
datePublished: "2024-07-14"
dateModified: "2024-07-14"
tags: ["Android", "Kotlin", "CameraX", "Computer Vision"]
keywords: "CameraX ImageAnalysis, real-time image analysis Android, ImageProxy, backpressure strategy, CameraX ML Kit"
faq:
  - q: "What backpressure strategy should I use for CameraX ImageAnalysis?"
    a: "For real-time analysis use STRATEGY_KEEP_ONLY_LATEST, which drops intermediate frames and always hands you the newest one. This keeps your analyzer from falling behind and building latency when processing is slower than the camera frame rate. Use STRATEGY_BLOCK_PRODUCER only when you must process every single frame and can tolerate the camera stalling."
  - q: "Why must I call ImageProxy.close() in the analyzer?"
    a: "CameraX uses a small pool of image buffers, and each ImageProxy holds one. If you don't close it, the pool exhausts and the analyzer stops receiving new frames — playback appears to freeze. Always close the ImageProxy when you're done, ideally in a finally block, even if your analysis throws."
  - q: "Should I use YUV_420_888 or RGBA_8888 output from ImageAnalysis?"
    a: "Use YUV_420_888 (the default) when feeding ML Kit or any consumer that accepts YUV, because it avoids a conversion and is what the camera produces natively. Request RGBA_8888 output only when your analysis code specifically needs RGB, since CameraX then does the conversion for you at some CPU cost."
---

The core of any camera feature that "understands" what it sees — a document scanner, a live translator, a barcode reader — is a CameraX `ImageAnalysis` use case delivering frames to your code in real time. The whole game is keeping up: the camera produces frames faster than most analysis can process them, so the difference between a smooth feature and a laggy one is how you handle *backpressure* and buffer lifecycle. Get those two right and everything else is detail.

I've built several live-camera features on CameraX. The mistakes are always the same, and they're always about frame flow, not the analysis itself.

## The three use cases, bound together

CameraX gives you `Preview`, `ImageCapture`, and `ImageAnalysis`. For a live feature you bind `Preview` (what the user sees) and `ImageAnalysis` (what your code sees) to the same lifecycle:

```kotlin
val preview = Preview.Builder().build().also {
    it.setSurfaceProvider(previewView.surfaceProvider)
}

val analysis = ImageAnalysis.Builder()
    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
    .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_YUV_420_888)
    .setTargetResolution(Size(1280, 720))
    .build()
    .also {
        it.setAnalyzer(cameraExecutor) { proxy -> analyze(proxy) }
    }

cameraProvider.bindToLifecycle(
    lifecycleOwner, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis
)
```

Bind to a `LifecycleOwner` and CameraX starts and stops the camera with the lifecycle automatically — no manual open/release, which removes a whole category of camera-leak bugs.

## Backpressure is the whole ballgame

The camera pushes ~30 frames a second. If your analyzer takes 60ms per frame, you can only process ~16 of them. What happens to the other 14? That's the backpressure strategy:

- **`STRATEGY_KEEP_ONLY_LATEST`** (use this): CameraX keeps only the newest frame and drops the rest. Your analyzer always works on fresh data and never builds a backlog. Latency stays flat.
- **`STRATEGY_BLOCK_PRODUCER`**: CameraX blocks until you finish, so you see every frame but the camera stalls and the preview stutters. Only correct when you genuinely must process every frame (rare — usually offline capture, not live).

For anything user-facing, `KEEP_ONLY_LATEST`. Chasing "process every frame" in a live viewfinder is how you get a feature that feels broken.

## Close the ImageProxy or everything freezes

Each frame arrives as an `ImageProxy` backed by one buffer from a small pool. Hold onto it and you starve the pool; the analyzer simply stops getting called and the feature "freezes" with no crash and no log. The fix is disciplined closing:

```kotlin
private fun analyze(proxy: ImageProxy) {
    try {
        val rotation = proxy.imageInfo.rotationDegrees
        // ... run detection on proxy ...
    } finally {
        proxy.close()   // non-negotiable, even on exception
    }
}
```

If you hand the frame to an async consumer (like ML Kit's `process()` which returns a `Task`), close the proxy in the task's completion listener, *not* synchronously — closing while ML Kit still reads the buffer corrupts the frame. This ordering bug is the single most common CameraX + ML Kit defect I see.

## Rotation and format

Two details that silently ruin accuracy:

- **Rotation.** The buffer is not oriented the way the user holds the phone. `proxy.imageInfo.rotationDegrees` tells you how to rotate for upright analysis. ML Kit's `InputImage.fromMediaImage(image, rotationDegrees)` takes it directly — pass it or your detector reads a sideways world and misses everything.
- **Format.** Default output is `YUV_420_888`, which is what the sensor produces and what ML Kit consumes natively — no conversion. Only request `RGBA_8888` if your own code needs RGB, and know CameraX pays a conversion cost to give it to you.

## Throttle when you don't need every frame

Many features don't need 30fps analysis. A document-edge detector at 5fps feels instant and saves battery and heat — and phones throttle the camera when they get hot, so *less* work can mean a *more* stable frame rate. A simple time gate:

```kotlin
private var lastRun = 0L
private val minIntervalMs = 200L   // ~5 fps

private fun analyze(proxy: ImageProxy) {
    val now = SystemClock.elapsedRealtime()
    if (now - lastRun < minIntervalMs) { proxy.close(); return }
    lastRun = now
    try { /* detect */ } finally { proxy.close() }
}
```

Feeding fewer, well-chosen frames to something like [on-device ML Kit vision](https://blog.michaelsam94.com/android-mlkit-on-device-vision/) usually beats hammering it at full frame rate.

## Keep heavy work off the main thread

Pass a dedicated single-thread executor to `setAnalyzer`. The analysis runs there, off the UI thread, so even a slow detector never janks the preview. When you have a result to draw (a bounding box overlay), post *only that small result* back to the main thread — never the frame. Marshaling whole frames to the UI thread is a classic self-inflicted jank source.

## What I'd take away

A real-time CameraX pipeline lives or dies on frame flow, not cleverness. Use `STRATEGY_KEEP_ONLY_LATEST` so you always analyze fresh frames, close every `ImageProxy` (in a `finally`, or after your async consumer finishes) or the feed freezes, honor `rotationDegrees` so your detector sees an upright world, keep the default YUV format when feeding ML Kit, throttle to the frame rate your feature actually needs, and run analysis on a dedicated executor. Nail those and you get a live camera feature that stays smooth, cool, and accurate.

## Common production mistakes

Teams get camerax image analysis wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping camerax image analysis on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## BackpressureStrategy keep-only-latest

MLKit barcode at 30fps analysis chokes on KEEP_EVERY_FRAME — use `STRATEGY_KEEP_ONLY_LATEST` and accept dropped frames. Rotation metadata must match analysis resolution or models see skewed aspect ratios.

## CPU vs GPU delegate

MLKit auto-selects delegate; force CPU on devices with known GPU driver bugs (maintain blocklist from Crashlytics). ImageAnalysis single-thread executor prevents analyzer reentrancy crashes.

## Camerax Image Analysis Supplement 0 on Samsung and Pixel divergence

Exercise camerax image analysis supplement 0 on Galaxy A-series and Pixel a-series — emulators hide OEM battery and storage quirks. Capture Macrobenchmark or Firebase trace for the critical path touching camerax; regressions above 8% block release for `android-camerax-image-analysis-supplement-0`.

Document permission and background behavior in internal runbook: what breaks under Doze, what requires foreground service, and what Play policy declarations apply. Support tickets referencing "Camerax Image Analysis Supplement 0" should map to a single runbook section with known workarounds.

## Analysis regression gates for Play Vitals

Before promoting `android-camerax-image-analysis-supplement-0` changes past 20% rollout, compare ANR rate, slow cold start, and excessive wakeups against seven-day baseline. Fail rollback review if 0 path shows >5% increase in `slow frames` without documented trade-off approval.

## Field testing camerax with battery saver enabled

Xiaomi and Oppo ship aggressive background killers. After implementing camerax image analysis supplement 0, run 24-hour monkey test on three OEM devices with battery saver enabled. Failures here predict one-star reviews that Crashlytics never captures — especially for 0 flows that assume reliable background delivery.

## Resources

- [ImageAnalysis (CameraX)](https://developer.android.com/media/camera/camerax/analyze)
- [CameraX architecture](https://developer.android.com/media/camera/camerax/architecture)
- [CameraX preview](https://developer.android.com/media/camera/camerax/preview)
- [ML Kit with CameraX](https://developers.google.com/ml-kit/vision/image-labeling/android)
- [ImageProxy reference](https://developer.android.com/reference/androidx/camera/core/ImageProxy)
