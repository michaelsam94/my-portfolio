---
title: "PrivAI"
slug: "privai"
kind: "app"
category: "AI"
packageId: "com.michael.privai"
playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.privai"
githubUrl: "https://github.com/michaelsam94/PrivAI"
image: "https://play-lh.googleusercontent.com/5sn9vK54oe59VJBs6ELVoyo6U7J8K-P3-42f7XmeMMToP6b8dGM-fP0wJaJ26HUb7nB2F8lk-80gYsb_cjTK6-s"
description: "Privacy-focused AI utility for local-first, safer everyday assistance workflows."
source: "readme"
thin: false
---

**Secure notes, voice transcription, and document OCR — 100% on-device.**

PrivAI is an Android workspace for capturing ideas, transcribing speech, and extracting text from photos. Core processing runs locally on your phone. No account required. No cloud uploads for your content.

## Features

- **Workspace notes** — Create, tag, search, and open detailed note views. Everything stays in a local Room database.
- **Voice transcription** — Record and transcribe speech using the device speech recognizer, processed on-device.
- **Document OCR** — Pick a photo from the system image picker and extract text offline with ML Kit (fast mode) or Tesseract (high-accuracy mode). English and Arabic tessdata are bundled.
- **On-device summaries** — Bullet points, keyword highlights, and simple sentiment hints from local NLP — no API keys needed for basic intelligence.
- **Unified dashboard** — Switch between Notes, Audio Transcripts, and OCR Extracts from one home screen.

## Privacy

| Data | Handling |
|------|----------|
| Notes & transcripts | Stored locally in Room |
| OCR input images | Read only when you pick one; briefly cached in app storage for processing |
| OCR output | Extracted text saved locally; images are not uploaded |
| Summaries | Computed on-device via `LocalTextIntelligence` |
| Accounts / cloud sync | Not used |

## Tech stack

- **UI** — Jetpack Compose, Material 3, Navigation Compose
- **Architecture** — ViewModel, Kotlin Coroutines, StateFlow
- **Storage** — Room, DataStore (OCR preferences)
- **Speech** — Android `SpeechRecognizer` via `AndroidSpeechTranscriber`
- **OCR** — ML Kit Text Recognition, Tesseract4Android
- **Testing** — JUnit, Robolectric, Roborazzi (Play Store screenshots)

## Permissions

| Permission | Purpose |
|------------|---------|
| `RECORD_AUDIO` | Live voice transcription |
| `INTERNET` | Required by some on-device ML libraries; user content is not uploaded |

OCR uses the system photo picker (`GetContent`); no storage or media-library permissions are declared.

## Play Store assets

```bash

./gradlew generatePlayStoreAssets

```

## Tests

```bash
# Unit tests (excludes Play Store screenshot tests)
./gradlew :app:testDebugUnitTest

# Play Store screenshot generation (Roborazzi)
./gradlew generatePlayStoreAssets
```
