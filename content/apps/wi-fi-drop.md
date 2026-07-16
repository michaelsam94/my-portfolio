---
title: "Wi-Fi Drop"
slug: "wi-fi-drop"
kind: "app"
category: "Utility"
packageId: "com.michael.wifidrop"
playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.wifidrop"
githubUrl: "https://github.com/michaelsam94/Wi-Fi-Drop"
image: "https://play-lh.googleusercontent.com/WR7vIT2bkXYUVFpWg-ATiFxEsBznNsoBS-qryrs00VG-QQG0lx6_6pnuYkf1kzB-MPAfSf3o_0aYbkukRZBT"
description: "Ad-free Android file transfer over local Wi-Fi. Send photos, videos, documents, and folders nearby with live progress or Web Share via QR — no ads, no cloud account."
source: "readme"
thin: false
primaryKeyword: "ad-free Wi-Fi file transfer Android"
keywords: "ad-free file transfer Android, no ads Wi-Fi share, local Wi-Fi file sharing, transfer files without cloud, nearby file transfer Android, Web Share QR download, offline file sharing app, send folder over Wi-Fi, ad free AirDrop alternative Android"
---

Wi-Fi Drop is a free, ad-free Android app for sharing photos, videos, documents, and folders between devices on the same Wi-Fi network — no cloud upload and no account required.

**Ad-free:** Completely ad-free — no ads, no trackers, no sponsored clutter.

Share photos, videos, documents, and folders between devices on the same Wi-Fi network—no cloud upload, no account required.

**Package:** `com.michael.wifidrop` · **Privacy policy:** [Wi-FiDrop-pv](https://github.com/michaelsam94/Wi-FiDrop-pv)

## Features

- **Send** — pick files or folder trees, discover nearby receivers, transfer with live speed and progress
- **Receive** — advertise a display name and accept incoming transfers to `Downloads/Wifi-Drop`
- **Web Share** — host files on a built-in local server; download via QR code or browser URL
- **History** — local log of sent and received transfers with sizes and timestamps

## Tech stack

| Layer | Tools |
|-------|-------|
| UI | Jetpack Compose, Material 3 |
| Architecture | ViewModel, Room, Kotlin Coroutines |
| Networking | Ktor (local HTTP server), NSD/mDNS discovery |
| Other | ZXing (QR codes), Apache Commons Compress (folder zips) |

## Play Store assets

```bash

JAVA_HOME=/path/to/jdk-17 ./gradlew generatePlayStoreAssets --no-configuration-cache

```

## Tests

```bash
# Unit tests (Play Store screenshot tests excluded)
./gradlew testDebugUnitTest

# Regenerate Play Store screenshots only
./gradlew generatePlayStoreAssets --no-configuration-cache
```

## Permissions

| Permission | Why |
|------------|-----|
| Location / Nearby Wi-Fi devices | Required by Android for local network peer discovery |
| Storage / Media read | Pick files to send; save received files |

## Project layout

```
app/src/main/java/com/michael/wifidrop/
├── feature/          # Send, Receive, History screens + ViewModels
├── core/             # Domain, data, network, storage
├── di/               # AppContainer
└── ui/theme/         # Material 3 theme

```

## Contact

Questions or feedback: [support@wifidrop.app](mailto:support@wifidrop.app)
