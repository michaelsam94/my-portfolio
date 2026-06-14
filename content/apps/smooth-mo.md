---
title: "Smooth-Mo"
slug: "smooth-mo"
kind: "app"
category: "Utility"
packageId: "com.michael.smoothmo"
playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.smoothmo"
githubUrl: "https://github.com/michaelsam94/Smooth-Mo"
image: "https://play-lh.googleusercontent.com/7vwn0tvOllRw2YhmPAccj8VM1nC4wJ7GWfe-hMGciaA6ktaSStobHetrttfNX376pvg3kq5j75o1DCzhBX7AgQ"
description: "Motion and smoothness utility for tuning or exploring Android device behavior."
source: "readme"
thin: false
---

Smooth-Mo is an Android app for creating smoother slow-motion video exports on device. It helps mobile creators pick a
local video, choose an output frame-rate target, monitor background processing, and preview or share the result. The
repository also includes Google Play listing assets for release preparation.

## Project Overview

Smooth-Mo targets people who want quick mobile video smoothing without sending footage to a remote service. The app uses
Jetpack Compose for the workflow, Room for local job history, Media3 for result preview, and WorkManager foreground work
for longer processing jobs. A sibling `Smooth-Mo-pv` repository in the parent workspace provides the static privacy
policy site used for Google Play and Netlify deployment.

## Key Features

- 🎬 Import local videos through Android's system media picker and content URI flow.
- ⚙️ Configure 60 FPS or 120 FPS output targets before starting a processing job.
- 🐢 Enable 2x to 4x slow-motion mode with timestamp stretching for video samples.
- 🔔 Track foreground WorkManager progress with in-app stages and system notifications.
- 💾 Persist queued, processing, completed, and failed jobs with Room.
- ▶️ Preview completed results with AndroidX Media3 ExoPlayer.
- 📤 Export completed MP4 files into `Movies/SmoothMo` through MediaStore.

## Architecture Overview

The app follows a small clean-architecture layout:

- `presentation` contains Compose screens, navigation, ViewModels, UI state, and share actions.
- `domain` contains video job models, repository contracts, scheduler contracts, and use cases.
- `data` contains Room persistence, metadata extraction, WorkManager scheduling, interpolation hooks, and output writing.
- `play-store` contains release artwork and listing text for Google Play preparation.

Request and data flow:

1. The user picks a video and chooses interpolation settings.
2. `EnqueueJobUseCase` stores a `VideoJob` in Room and schedules unique WorkManager work.
3. `InterpolationWorker` reads the job, updates progress, writes a cache MP4 result, and marks the job complete.
4. The result screen observes Room, previews the output, and exports it to `Movies/SmoothMo` when requested.

Design patterns include repository interfaces, use-case classes, a simple application container, Room type converters,
foreground WorkManager jobs, and Compose state collection through ViewModels.

## Tech Stack & Libraries

| Layer | Technology | Version | Purpose |
| --- | --- | --- | --- |
| Mobile platform | Android SDK | min 24, target 36, compile 36.1 | Native Android runtime |
| Language | Kotlin | 2.2.10 | App implementation |
| Build system | Gradle Wrapper | 9.5.1 | Reproducible local builds |
| Android plugin | Android Gradle Plugin | 9.1.1 | Android module builds |
| UI | Jetpack Compose BOM | 2024.09.00 | Declarative app UI |
| Material UI | Material 3 | BOM-managed | Components and theming |
| Navigation | Navigation Compose | 2.8.9 | Screen routing and deep links |
| Persistence | Room | 2.7.0 | Local video job database |
| Background work | WorkManager KTX | 2.9.1 | Foreground processing jobs |
| Video playback | AndroidX Media3 | 1.10.1 | Result preview playback |
| ML runtime | Google AI Edge LiteRT | 1.4.2 | On-device interpolation model hook |
| Images | Coil Compose | 2.7.0 | Compose image loading support |
| Serialization | Moshi | 1.15.2 | Type conversion and JSON utilities |
| HTTP client | OkHttp / Retrofit | 4.10.0 / 2.12.0 | Available networking stack |
| Unit testing | JUnit | 4.13.2 | JVM tests |
| Android testing | Robolectric | 4.16.1 | Host-side Android tests |
| Screenshot testing | Roborazzi | 1.59.0 | Compose screenshot capture |
| Secrets | Secrets Gradle Plugin | 2.0.1 | Local `.env` value injection |

## Configuration

Android app configuration lives in:

- `app/build.gradle.kts` for package name, SDK versions, signing, Compose, and dependencies.
- `gradle/libs.versions.toml` for dependency and plugin versions.
- `.env` for values read by the Secrets Gradle Plugin.
- `app/src/main/AndroidManifest.xml` for permissions, the launcher activity, deep links, FileProvider, and foreground
  service metadata.

Most Gradle, manifest, dependency, and signing changes require a rebuild. Runtime permission changes may require
uninstalling and reinstalling the app during local testing.

## Usage / Quick Start

### Build and Run the Android App

```bash
./gradlew :app:assembleDebug
./gradlew :app:installDebug
```

After installation, open Smooth-Mo on the device, choose a video, select 60 FPS or 120 FPS, optionally enable slow-motion,
and start processing.

### Run Tests Locally

```bash
./gradlew testDebugUnitTest
```

This runs the JVM, Robolectric, and Roborazzi tests under `app/src/test`.

### Build Store Assets Into a Release Workflow

```bash
ls play-store

```

Use the checked-in feature graphic, app icon, phone screenshots, tablet screenshots, and `listing-descriptions.md` when
preparing the Google Play listing.

## API Reference

Not applicable. Smooth-Mo does not expose a public HTTP API, CLI API, SDK API, or local service endpoint.

The app does define internal Kotlin contracts in `app/src/main/java/com/michael/smoothmo/domain/repository`:

| Contract | Purpose |
| --- | --- |
| `VideoRepository` | Stores, observes, updates, and deletes video jobs. |
| `MediaRepository` | Reads video metadata and exports completed videos to the gallery. |
| `JobScheduler` | Schedules and cancels background processing work. |

Internal deep link:

| Method | URL | Description |
| --- | --- | --- |
| Android intent view | `smoothmo://progress/{jobId}` | Opens the progress screen for a background job notification. |

Parameters: `jobId` is the Room/WorkManager job identifier generated when a job is enqueued.

Errors: invalid or missing job IDs open the progress route without a matching observed job.

## Testing

Unit and host-side Android tests:

```bash
./gradlew testDebugUnitTest
```

Instrumentation tests on a connected device or emulator:

```bash
./gradlew connectedDebugAndroidTest
```

Coverage command: Not configured. The repository does not include a JaCoCo, Kover, or Android coverage task.

Test locations and conventions:

- JVM, Robolectric, and Roborazzi tests live in `app/src/test/java`.
- Instrumented tests live in `app/src/androidTest/java`.
- Existing tests use JUnit 4 and behavior-focused Kotlin test names where helpful.
- Roborazzi screenshot tests write generated captures under the test screenshot output paths.

## Deployment

### Android App

Debug build:

```bash
./gradlew :app:assembleDebug
```

Release build:

```bash
KEYSTORE_PATH=/absolute/path/to/upload-key.jks \
STORE_PASSWORD="$STORE_PASSWORD" \
KEY_PASSWORD="$KEY_PASSWORD" \
./gradlew :app:assembleRelease
```

The release signing config expects key alias `upload`. Store distribution metadata and Play Console app setup are not
fully automated in this repository.

Health check: install the APK, select a short local video, run a processing job, preview the result, export it, and verify
that the output appears under `Movies/SmoothMo`.

### Privacy Policy Site

Not applicable inside this app repository. The static privacy-policy site lives in the sibling `Smooth-Mo-pv` repository
in the parent workspace and can be deployed separately to Netlify.

Docker and docker-compose: Not applicable. No Dockerfile or compose file is present.
