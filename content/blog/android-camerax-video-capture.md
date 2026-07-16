---
title: "Video Capture with CameraX Done Right"
slug: "android-camerax-video-capture"
description: "Record video with CameraX VideoCapture and Recorder: quality selection, audio permission handling, pause/resume, storage with MediaStore, and handling recording events."
datePublished: "2024-07-16"
dateModified: "2024-07-16"
tags: ["Android", "Kotlin", "CameraX", "Video"]
keywords: "CameraX VideoCapture, Recorder CameraX, record video Android, QualitySelector, MediaStoreOutputOptions"
faq:
  - q: "How do I select video quality in CameraX?"
    a: "Use a QualitySelector on the Recorder. You can request a specific Quality like UHD, FHD, HD, or SD, or provide a prioritized fallback list so CameraX picks the best supported option. Always query QualitySelector for the camera's supported qualities first, because not every device supports every resolution and a hard request for UHD can fail silently."
  - q: "Does CameraX VideoCapture record audio automatically?"
    a: "No — you must call withAudioEnabled() when starting the recording and hold the RECORD_AUDIO runtime permission. If the permission is missing, start the recording without audio rather than crashing, and reflect the muted state in your UI. Audio is opt-in per recording, not a global setting."
  - q: "Can I record video and run image analysis at the same time with CameraX?"
    a: "It depends on the device's supported use case combinations. Preview plus VideoCapture is broadly supported, but binding Preview, VideoCapture, and ImageAnalysis together simultaneously is not guaranteed on all hardware and may throw. Check the combination against the device or degrade gracefully rather than assuming three concurrent streams."
---

CameraX's `VideoCapture` use case, built on the `Recorder`, is the modern way to record video on Android without hand-managing `MediaRecorder` state machines. The parts that actually trip people up aren't the recording call itself — they're quality selection across wildly varied hardware, audio-permission handling, listening to recording events, and writing the file somewhere scoped storage approves of. Here's how I wire it so it works on a cheap phone and a flagship alike.

## Bind VideoCapture to the lifecycle

`VideoCapture` wraps a `Recorder`, and the `Recorder` carries your quality preferences:

```kotlin
val qualitySelector = QualitySelector.fromOrderedList(
    listOf(Quality.FHD, Quality.HD, Quality.SD),
    FallbackStrategy.lowerQualityOrHigherThan(Quality.SD)
)

val recorder = Recorder.Builder()
    .setQualitySelector(qualitySelector)
    .build()

val videoCapture = VideoCapture.withOutput(recorder)

cameraProvider.bindToLifecycle(
    lifecycleOwner, CameraSelector.DEFAULT_BACK_CAMERA, preview, videoCapture
)
```

The ordered-list plus fallback pattern matters. A hard `Quality.UHD` request fails on devices that can't do 4K. The list says "prefer FHD, then HD, then SD," and the fallback strategy handles the gaps. Before offering a resolution in your UI, query what's actually supported:

```kotlin
val supported = QualitySelector.getSupportedQualities(cameraInfo)
```

Only show the user options the hardware can deliver. Presenting "4K" on a phone that can't do it is a bug report waiting to happen.

## Where the file goes

Use `MediaStoreOutputOptions` so the recording lands in the shared media collection under scoped storage — no legacy `WRITE_EXTERNAL_STORAGE`, and it shows up in the gallery automatically:

```kotlin
val name = "VID_${System.currentTimeMillis()}.mp4"
val contentValues = ContentValues().apply {
    put(MediaStore.Video.Media.DISPLAY_NAME, name)
    put(MediaStore.Video.Media.MIME_TYPE, "video/mp4")
    put(MediaStore.Video.Media.RELATIVE_PATH, "Movies/MyApp")
}

val outputOptions = MediaStoreOutputOptions.Builder(
    contentResolver, MediaStore.Video.Media.EXTERNAL_CONTENT_URI
).setContentValues(contentValues).build()
```

`RELATIVE_PATH` puts your videos in a tidy app-named subfolder. If you need an app-private file instead (not visible in the gallery), use `FileOutputOptions` pointed at your own directory. Pick based on whether the user should see the video in their gallery.

## Starting, and the audio decision

Audio is opt-in per recording and requires the `RECORD_AUDIO` runtime permission. The graceful pattern is to record *without* audio if the permission isn't granted rather than crashing or blocking the recording:

```kotlin
val pending = videoCapture.output
    .prepareRecording(context, outputOptions)
    .apply {
        if (hasAudioPermission()) withAudioEnabled()
    }

recording = pending.start(ContextCompat.getMainExecutor(context)) { event ->
    when (event) {
        is VideoRecordEvent.Start -> updateUi(recording = true)
        is VideoRecordEvent.Status -> showDuration(event.recordingStats)
        is VideoRecordEvent.Finalize -> {
            if (event.hasError()) handleError(event.error)
            else onSaved(event.outputResults.outputUri)
            updateUi(recording = false)
        }
    }
}
```

Note the events. `Start` confirms recording began, `Status` streams duration and byte count (drive your timer and a storage-remaining check off this), and `Finalize` is where the file is actually complete — only there is the URI valid and only there do you learn about errors like the disk filling up. Don't assume `start()` returning means the file exists; wait for `Finalize`.

## Pause, resume, and the lifecycle gotchas

The `Recording` handle supports `pause()`, `resume()`, and `stop()`. A few things I learned the hard way:

1. **Stop on lifecycle stop.** If your Activity stops mid-recording, finalize the recording — don't leave it dangling, or you get a truncated file and a leaked recorder.
2. **One active recording.** Track your `Recording` reference and guard against starting a second while one is active.
3. **Storage checks.** Use the byte count from `Status` events to stop gracefully before you hit a `Finalize` error from a full disk. Users would rather get a slightly short clip than a corrupt one.
4. **Orientation.** Set target rotation on the `VideoCapture` from the display rotation so the recorded file plays upright.

## Can you record and analyze at once?

A frequent ask: run [live image analysis](https://blog.michaelsam94.com/android-camerax-image-analysis/) while recording. Sometimes. `Preview` + `VideoCapture` is broadly supported, but adding `ImageAnalysis` as a third concurrent stream depends on the device's supported use-case combinations and may throw on binding. Don't assume it — check, and degrade to two streams (drop analysis while recording) on hardware that refuses three. Building a feature that only works on flagships is a support nightmare.

## What I'd take away

CameraX makes video recording tractable, but the resilience is in the edges: build your `QualitySelector` as a prioritized list with a fallback and only offer resolutions the camera actually supports, write through `MediaStoreOutputOptions` for scoped-storage-friendly files, treat audio as an opt-in that degrades to muted when permission is missing, and drive your UI and error handling off `VideoRecordEvent` — especially `Finalize`, which is the only point the file is truly done. Handle lifecycle stops, one-recording-at-a-time, and storage limits, and don't assume three concurrent camera streams. That's the difference between a demo and a recorder people trust with a moment they can't recapture.

## Common production mistakes

Teams get camerax video capture wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping camerax video capture on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Resources

- [Capture video (CameraX)](https://developer.android.com/media/camera/camerax/video-capture)
- [QualitySelector reference](https://developer.android.com/reference/androidx/camera/video/QualitySelector)
- [MediaStoreOutputOptions reference](https://developer.android.com/reference/androidx/camera/video/MediaStoreOutputOptions)
- [Access media files with MediaStore](https://developer.android.com/training/data-storage/shared/media)
- [CameraX use case combinations](https://developer.android.com/media/camera/camerax/architecture)
