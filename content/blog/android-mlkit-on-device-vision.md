---
title: "On-Device Vision with ML Kit"
slug: "android-mlkit-on-device-vision"
description: "Run computer vision on-device with ML Kit: which APIs are free and offline, bundled vs Play Services models, feeding CameraX frames, and when to reach for a custom model."
datePublished: "2024-07-18"
dateModified: "2024-07-18"
tags: ["Android", "Kotlin", "ML Kit", "Computer Vision"]
keywords: "ML Kit on-device vision, ML Kit Android, InputImage, bundled vs unbundled model, on-device machine learning Android"
faq:
  - q: "Is ML Kit on-device vision free and offline?"
    a: "The on-device vision APIs — barcode scanning, text recognition, face detection, image labeling, object detection, pose detection — are free and run entirely on the device with no network call. Some ML Kit features have cloud variants that cost money and need connectivity, but the on-device base tier is free and works offline, which is why it's a strong default for privacy-sensitive features."
  - q: "What is the difference between bundled and unbundled ML Kit models?"
    a: "Bundled models ship inside your APK, so they're available on first launch at the cost of a larger download. Unbundled (Play Services) models are downloaded on demand through Google Play Services, keeping your APK small but requiring a download before first use and a Play Services dependency. Choose bundled for instant availability, unbundled to minimize app size."
  - q: "Can I use a custom TensorFlow Lite model with ML Kit?"
    a: "Yes. ML Kit supports custom TensorFlow Lite models for image labeling and object detection, so you can train a domain-specific classifier and run it through the same ML Kit pipeline you use for the built-in models. This gives you ML Kit's camera integration and lifecycle handling while running your own model."
  - q: "How do I feed CameraX frames to ML Kit?"
    a: "Wrap the frame in an InputImage using InputImage.fromMediaImage, passing the ImageProxy's underlying image and its rotationDegrees. Then call the detector's process() method and close the ImageProxy in the task's completion listener, not before, so ML Kit finishes reading the buffer."
---

ML Kit is the pragmatic answer to "I need computer vision in my Android app and I don't want to run a server or ship a 200MB model." Its on-device vision APIs — barcode scanning, text recognition, face detection, image labeling, object detection and tracking, pose detection — are free, run entirely offline, and are fast enough for real-time use on mid-range hardware. Before you reach for a custom TensorFlow Lite pipeline or a cloud vision API, ML Kit's built-ins solve a surprising fraction of real product needs.

I've shipped features on top of several of these APIs. The value isn't just the models — it's that ML Kit handles the annoying glue between the camera and inference, which is where most homegrown vision code goes wrong.

## What you get for free, on-device

The base on-device tier costs nothing and never touches the network:

- **Barcode scanning** — [fast, robust, many formats](https://blog.michaelsam94.com/android-barcode-scanning-mlkit/).
- **Text recognition (OCR)** — [Latin and several script packs](https://blog.michaelsam94.com/android-text-recognition-mlkit-ocr/).
- **Face detection** — bounding boxes, landmarks, classification (smiling, eyes open).
- **Image labeling** — general-purpose "what's in this image" tags.
- **Object detection and tracking** — locate and track objects across frames.
- **Pose detection** — skeletal keypoints for fitness and AR.

Offline and free matters beyond cost: it means these features work on a plane, in a warehouse basement, and without shipping user images to a server — a real privacy win you can put in your store listing.

## Bundled vs unbundled: the size trade-off

Each model comes in two delivery modes, and picking wrong annoys either your download numbers or your first-run experience:

| | Bundled | Unbundled (Play Services) |
|---|---|---|
| Model lives | Inside your APK | Downloaded via Play Services |
| First use | Instant | Needs a one-time download |
| APK size | Larger | Smaller |
| Dependency | Self-contained | Requires Play Services |

I default to **unbundled** to keep the APK lean, and trigger the model download early (e.g. during onboarding) so it's ready before the user hits the feature. Choose **bundled** when the feature is core to first launch and you can't tolerate a download gap — or when you target devices without Play Services.

## The InputImage bridge

Everything in ML Kit vision takes an `InputImage`. The critical case is a live camera frame, where rotation and buffer lifecycle are the whole story:

```kotlin
@OptIn(ExperimentalGetImage::class)
private fun analyze(proxy: ImageProxy) {
    val mediaImage = proxy.image ?: run { proxy.close(); return }
    val input = InputImage.fromMediaImage(mediaImage, proxy.imageInfo.rotationDegrees)

    detector.process(input)
        .addOnSuccessListener { result -> handle(result) }
        .addOnFailureListener { e -> log(e) }
        .addOnCompleteListener { proxy.close() }   // close AFTER ML Kit finishes
}
```

Two things I'll die on: pass `rotationDegrees` or the model reads a sideways world and detects nothing, and close the `ImageProxy` in `addOnCompleteListener` — not synchronously — because closing while ML Kit still reads the buffer corrupts the frame. This exact ordering bug accounts for most "ML Kit works on stills but not on the camera" reports. Pair this with a [CameraX ImageAnalysis pipeline](https://blog.michaelsam94.com/android-camerax-image-analysis/) using `KEEP_ONLY_LATEST` backpressure and you have a solid real-time loop.

## A minimal detector setup

Object detection in streaming mode, as an example:

```kotlin
val options = ObjectDetectorOptions.Builder()
    .setDetectorMode(ObjectDetectorOptions.STREAM_MODE)
    .enableClassification()
    .build()

val detector = ObjectDetection.getClient(options)
```

`STREAM_MODE` optimizes for low latency and tracks objects across frames with stable IDs, which is what you want for a live viewfinder. `SINGLE_IMAGE_MODE` is for one-shot analysis of a photo. Using the wrong mode is a quiet performance regression.

## When to go custom

ML Kit's built-in image labeling knows generic categories. When you need "which of *our* 40 product SKUs is this," train a custom TensorFlow Lite classifier and run it through ML Kit's custom-model path — you keep ML Kit's camera integration and lifecycle handling but swap in your own model. That's the sweet spot before you graduate to a full custom inference stack: domain-specific accuracy without rebuilding the plumbing.

## Performance notes from the field

- **Throttle.** You rarely need 30fps inference. Run detection at 5–10fps for most features; it feels instant and keeps the phone cool, and thermal throttling of the camera is a real cause of *worse* frame rates.
- **One detector instance.** Create the client once and reuse it; don't build a detector per frame.
- **Close it.** Call `detector.close()` when done to free native resources.
- **Downscale.** Feed a 720p analysis stream, not 4K — the models don't need the resolution and the extra pixels just cost latency.

## What I'd take away

ML Kit's on-device vision APIs are free, offline, and good enough that they should be your first stop before custom models or cloud APIs. Choose unbundled models to keep your APK small and pre-download them before the feature is used; bridge camera frames through `InputImage.fromMediaImage` with the correct `rotationDegrees`, and close the `ImageProxy` only after `process()` completes. Use streaming mode for live features, throttle inference to the frame rate you actually need, and reach for a custom TensorFlow Lite model through ML Kit's own pipeline when the built-in labels aren't specific enough. That combination gets you production vision without a server or a research team.

Profile ML Kit on low-end devices from your user analytics tail — on-device inference that runs in 200ms on Pixel 7 can take 800ms on budget hardware.

## Resources

- [ML Kit for Android](https://developers.google.com/ml-kit)
- [ML Kit vision APIs](https://developers.google.com/ml-kit/vision)
- [InputImage reference](https://developers.google.com/ml-kit/reference/android/com/google/mlkit/vision/common/InputImage)
- [Object detection and tracking](https://developers.google.com/ml-kit/vision/object-detection/android)
- [Use a custom TensorFlow Lite model](https://developers.google.com/ml-kit/custom-models)
