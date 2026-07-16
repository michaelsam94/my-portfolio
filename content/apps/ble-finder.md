---
title: "BLE Finder"
slug: "ble-finder"
kind: "app"
category: "Developer"
packageId: "com.michael.blefinder"
playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.blefinder"
githubUrl: "https://github.com/michaelsam94/BLE-Finder"
image: "https://play-lh.googleusercontent.com/J7JKnuE6S8AatKuyMXl5O5cCsrY7oU7y2FtUmC-Xv-8bIk54aB3dlX4Fs8O94A_uN7B0poRjcrIQC_TUaxbdgew"
description: "Ad-free BLE scanner for Android. Find nearby Bluetooth Low Energy devices with RSSI radar, hot/cold proximity, and optional audio pings — no ads while you track peripherals."
source: "readme"
thin: false
primaryKeyword: "ad-free BLE scanner Android"
keywords: "ad-free BLE scanner, no ads Bluetooth finder, Bluetooth Low Energy radar, find earbuds by RSSI, BLE device tracker Android, proximity beep BLE, scan BLE advertisements, locate tracker tags without ads"
---

BLE Finder is an ad-free Android app that scans nearby Bluetooth Low Energy devices and turns RSSI changes into a radar-style hot/cold tracking experience with optional audio pings.

**Ad-free:** Completely ad-free — no ads, no trackers, no sponsored clutter.

BLE Finder is an Android app for finding nearby Bluetooth Low Energy devices by turning raw RSSI signal changes into a
radar-style tracking experience. It is built for people trying to locate wearables, earbuds, styluses, trackers, and
other BLE peripherals using visual hot/cold feedback and optional audio pings. No hosted demo is configured because the
primary artifact is a mobile app.

## Project Overview

The app scans nearby BLE advertisements, filters and sorts discovered devices, and lets the user focus on one target at a
time. It estimates proximity from RSSI, smooths noisy signal changes, keeps local scan logs in Room, and includes Play
Store-ready assets plus a separate privacy policy site for publication support.

## Key Features

- 📡 Low-latency BLE scanning with Android permission handling for modern Bluetooth APIs.
- 🎯 Radar tracking screen with RSSI-based hot, warm, and cold proximity states.
- 🔊 Optional audio ping feedback that changes frequency and interval as signal strength improves.
- 🧭 Device filtering and sorting by type, signal strength, advertised name, and last-seen time.
- 🗃️ Local Room database for tracked devices and scan-history logs.
- 🧹 Log retention controls with purge support for old scan entries.
- 🧪 JVM, Robolectric, Compose UI, and Roborazzi screenshot tests.
- 🛒 Generated Google Play graphics, phone screenshots, tablet screenshots, and listing copy.

## Architecture Overview

The project follows a lightweight clean-architecture layout. Compose screens render state and delegate actions to
ViewModels, ViewModels call domain use cases, and use cases depend on repository interfaces. Data implementations wrap
Android Bluetooth scanning, Room DAOs, and AudioTrack-based audio feedback.

Scan flow: the user grants Bluetooth/location permissions, `BleScanner` starts a low-latency BLE scan, scan results are
converted into `BleDevice` models, the UI filters/sorts them, and tracking screens calculate smoothed RSSI and estimated
distance for a selected MAC address.

Design patterns used here include repository interfaces, use-case classes, manual dependency injection through
`AppContainer`, Kotlin Flow for asynchronous scan streams, and immutable UI state collected by Compose.

## Tech Stack & Libraries

| Layer | Technology | Version | Purpose |
|---|---:|---:|---|
| Platform | Android SDK | min 24, target 36, compile 36.1 | Native BLE scanning app |
| Language | Kotlin | 2.2.10 | Application source and Gradle DSL |
| Build | Gradle Wrapper | 9.5.1 | Reproducible local builds |
| Build | Android Gradle Plugin | 9.1.1 | Android application packaging |
| UI | Jetpack Compose BOM | 2024.09.00 | Declarative Android UI |
| UI | Material 3 | BOM-managed | App components and theme |
| Navigation | Navigation Compose | 2.8.9 | Screen routing |
| Persistence | Room | 2.7.0 | Local database and DAOs |
| Async | Kotlin Coroutines | 1.10.2 | Flows, scanning, and background work |
| Audio | Android AudioTrack | Android framework | Proximity ping synthesis |
| Networking | OkHttp / Retrofit / Moshi | 4.10.0 / 2.12.0 / 1.15.2 | Available dependencies; no API client is currently wired |
| Testing | JUnit / Robolectric | 4.13.2 / 4.16.1 | Unit and Android resource tests |
| Screenshots | Roborazzi | 1.59.0 | Play Store screenshot and graphic generation |
| Secrets | Maps Platform Secrets Plugin | 2.0.1 | `.env` loading if future secrets are added |

## Configuration

Runtime settings are exposed in the app's Settings screen:

| Setting | Location | Restart required | Description |
|---|---|---:|---|
| Audio Proximity Ping | Settings screen | No | Enables or disables signal-based audio feedback. |
| Scan Mode Optimization | Settings screen | No | UI control for scan behavior tradeoffs. |
| Log Retention Period | Settings screen | No | Selects a retention window from 3 to 30 days. |
| Release signing | `app/build.gradle.kts` and environment variables | Build restart | Configures upload-key signing. |
| App identity | `app/build.gradle.kts` | Rebuild | Defines namespace, application ID, version code, and version name. |
| App display name | `app/src/main/res/values/strings.xml` | Rebuild | Sets the launcher label. |

## Usage / Quick Start

### Run From Android Studio

1. Open the `BLEFinder` folder in Android Studio.
2. Select a physical Android device with Bluetooth enabled.
3. Run the `app` configuration.
4. Grant Bluetooth and location permissions when prompted.
5. Tap **Scan Devices**, then choose a discovered peripheral to open the radar tracker.

### Run From The Terminal

```bash
cd BLEFinder
./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb shell monkey -p com.michael.blefinder 1
```

### Generate Play Store Assets

```bash
cd BLEFinder
./gradlew generatePlayStoreAssets
```

tablet screenshots, and listing copy.

## API Reference

Not applicable. BLE Finder is a local Android application and does not expose an HTTP API, CLI API, SDK, or server
endpoint. Retrofit, OkHttp, and Moshi are present as dependencies, but no repository evidence shows a configured network
API client.

## Testing

Run all JVM unit, Robolectric, and non-screenshot Compose tests:

```bash
./gradlew testDebugUnitTest
```

Run Android instrumented tests on a connected device or emulator:

```bash
./gradlew connectedDebugAndroidTest
```

Regenerate Roborazzi screenshots and Play Store graphics:

```bash
./gradlew generatePlayStoreAssets
```

Test files live under app/src/test/java/com/michael/blefinder/ and
app/src/androidTest/java/com/michael/blefinder/. Existing names use `*Test.kt`, while Play Store screenshot tests are
grouped under app/src/test/java/com/michael/blefinder/playstore/.

Coverage reporting is not configured in the repository.

## Deployment

### Debug Deployment

Use Android Studio or install the Gradle-generated APK directly:

```bash
./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

### Release Build

Set signing credentials, then build the release APK or Android App Bundle:

```bash
export KEYSTORE_PATH="$PWD/my-upload-key.jks"
read -rsp "Store password: " STORE_PASSWORD && export STORE_PASSWORD
read -rsp "Key password: " KEY_PASSWORD && export KEY_PASSWORD

./gradlew assembleRelease
./gradlew bundleRelease
```

Release artifacts are generated under app/build/outputs/. Docker, docker-compose, and backend health checks are not
applicable because this repository builds a native Android app with no server component.

### Privacy Policy Site

The privacy policy lives in the sibling ../BLEFinder-pv/ project and is configured for Netlify static hosting.

```bash
cd ../BLEFinder-pv
python3 -m http.server 8080 --directory .
```
