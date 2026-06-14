---
title: "Photo Optimizer"
slug: "photo-optimizer"
kind: "app"
category: "Media"
packageId: "com.michael.photo.optimizer"
playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.photo.optimizer"
githubUrl: "https://github.com/michaelsam94/Photo-Optimizer"
image: "https://play-lh.googleusercontent.com/X8prc76-bR0nI8-pxxinWNqE_hW9YLJZjuFbE_gxn5PPdczgrVs7x0VfN0kCiJyXmFJfb7UocXRFPlRq19oYIw"
description: "Photo compression and optimization tool for reducing image size while preserving quality."
source: "readme"
thin: false
---

An offline, privacy-first Android app for batch photo compression, EXIF metadata removal, and duplicate detection. Your photos never leave your device.

**Package:** `com.michael.photo.optimizer` · **Min SDK:** 24 · **Target SDK:** 36

## Features

- **Batch compression** — WebP (lossy or lossless), JPEG, or PNG with quality slider or target max file size
- **Before/after preview** — draggable split slider to compare results before saving
- **EXIF stripping** — remove GPS, camera, and timestamp metadata in one tap or as a standalone pass
- **Duplicate finder** — group same-size files and compare content hashes, then review and delete redundant copies
- **Flexible output** — keep originals intact; write optimized copies beside them or to a separate folder
- **Background processing** — larger batches run via WorkManager
- **Offline-first** — no account, no cloud uploads; processing uses local Android storage APIs only

## Screenshots

```bash

./gradlew generatePlayStoreAssets

```

## Tech stack

- Kotlin · Jetpack Compose · Material 3
- Navigation Compose · ViewModel · DataStore Preferences
- WorkManager · ExifInterface
- Roborazzi + Robolectric for Play Store screenshot tests

## Tests

```bash
# Unit tests (screenshot tests excluded by default)
./gradlew testDebugUnitTest

# Play Store screenshot generation
./gradlew generatePlayStoreAssets
```

## Privacy

Photo Optimizer reads and writes photos only through storage permissions you grant. See the companion privacy policy site in [PhotoOptimizer-pv](https://github.com/michaelsam94/Photo-Optimizer) (sibling repo) for Play Store compliance.
