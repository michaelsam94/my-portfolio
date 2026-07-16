---
title: "EdgeFlow"
slug: "edgeflow"
kind: "app"
category: "Utility"
packageId: "com.michael.edgeflow"
playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.edgeflow"
githubUrl: "https://github.com/michaelsam94/EdgeFlow"
image: "https://play-lh.googleusercontent.com/sr97xuvu3ACSIZ3ZGBy1CH5ozS0TIoZ8x97NWIIzjl8NwE1fxBefCNXuOJHiEitx4beHGioS47oDUNhAFP8G8A"
description: "Ad-free Android edge gesture helper. Turn left/right screen edges into one-handed shortcut zones for Back, Home, notifications, media, and more — no ads in your gesture flow."
source: "readme"
thin: false
primaryKeyword: "ad-free edge gestures Android"
keywords: "ad-free edge gestures, no ads navigation gestures Android, one-handed shortcuts Android, edge swipe menu, accessibility gesture helper, circular shortcut menu, quick settings edge actions, gesture control without ads"
---

EdgeFlow is an ad-free Android gesture helper that turns the left and right screen edges into configurable one-handed action zones for navigation, notifications, media, and more.

**Ad-free:** Completely ad-free — no ads, no trackers, no sponsored clutter.

EdgeFlow is an Android gesture helper that turns the left and right screen edges into configurable
one-handed action zones. It is designed for Android users who want faster access to navigation,
notifications, media controls, volume controls, screenshots, accessibility shortcuts, and app launchers.

## Project Overview

EdgeFlow displays subtle edge handles and uses an accessibility service to turn hold-and-swipe gestures
into system actions. The app ships with six fixed edge zones, five circular-menu slots per zone, local
settings storage, and generated Google Play graphics.

No hosted demo is configured. The app must be installed on an Android device or emulator to try the
gesture and accessibility-service workflow.

## Key Features

- ⚡ Six ergonomic edge zones split across the left and right screen edges.
- 🎛️ Five-action circular menus for each edge zone, with 30 default shortcuts.
- 🧭 Accessibility-service actions for Back, Home, Recents, notifications, quick settings, and more.
- 🎨 Adjustable visual handles with color, width, transparency, and touch-feedback controls.
- 📳 Optional haptic feedback for gesture arming and action execution.
- 🗃️ Local Room persistence for zones, menu items, and recent gesture activity.
- 🧪 Robolectric and Roborazzi tests for app behavior and Play Store assets.
- 🖼️ Generated Google Play screenshots, app icon, feature graphic, and listing copy.

## Architecture Overview

### Components And Layers

`MainActivity` hosts the Jetpack Compose setup, permission flow, settings screens, simulator view, and
zone customization UI. It observes repository state and guides the user toward overlay and accessibility
permissions.

`EdgeOverlayService` is the accessibility service declared in `AndroidManifest.xml`. It creates the edge
overlays, recognizes hold-and-swipe gestures, renders the circular menu, and executes the selected Android
action.

`EdgeFlowRepository` is the state boundary for the app. It stores zone and menu data in Room and persists
visual or feedback preferences in `SharedPreferences`.

### Request And Data Flow

1. The user grants display-over-other-apps and accessibility permissions.
2. The accessibility service creates edge handles based on repository settings.
3. A hold-and-swipe resolves the touched zone and opens the zone's five-item circular menu.
4. Releasing over a menu item executes the selected action and records a local activity entry.
5. Compose screens observe repository flows so settings and activity stay current.

### Design Patterns

EdgeFlow uses repository-based state access, Room DAOs, Kotlin sealed classes for gesture actions,
Compose state collection, and service-owned system-action execution. The UI configures behavior while the
accessibility service owns runtime overlay and action work.

## Tech Stack & Libraries

| Layer | Technology | Version | Purpose |
| --- | --- | --- | --- |
| Mobile platform | Android Gradle Plugin | 9.1.1 | Android app build system |
| Language | Kotlin | 2.2.10 | App, service, model, and test code |
| UI | Jetpack Compose BOM | 2024.09.00 | Declarative Android UI |
| UI components | Material 3 | BOM-managed | Settings, controls, and app surfaces |
| Persistence | Room | 2.7.0 | Local database for zones, menus, and logs |
| Async | Kotlin coroutines | 1.10.2 | Background repository and service work |
| Lifecycle | AndroidX Lifecycle | 2.8.7 | Lifecycle-aware Compose state collection |
| Networking | Retrofit | 2.12.0 | Available dependency; no active API client is documented |
| Networking | OkHttp | 4.10.0 | Available dependency; no active HTTP flow is documented |
| Serialization | Moshi | 1.15.2 | Available dependency and KSP code generation |
| Screenshots | Roborazzi | 1.59.0 | Play Store screenshot and graphic generation |
| Testing | JUnit | 4.13.2 | JVM unit test framework |
| Testing | Robolectric | 4.16.1 | Android tests on the JVM |
| Secrets | Secrets Gradle Plugin | 2.0.1 | Reads `.env` and `.env.example` |

## Configuration

Android build configuration lives in `app/build.gradle.kts`. It defines package
`com.michael.edgeflow`, min SDK 24, target SDK 36, version code 9, version name `1.0.2`, debug signing,
and release signing.

Dependency and plugin versions are centralized in `gradle/libs.versions.toml`. Runtime user preferences
are stored in `SharedPreferences` under `edgeflow_preferences` and can be changed through the app UI.

Default zones and menu actions are defined in
`app/src/main/java/com/michael/edgeflow/model/DefaultEdgeConfiguration.kt`. Changing these defaults
requires a rebuild and reinstall for fresh installs; existing local data may preserve user edits.

Accessibility-service metadata lives in `app/src/main/res/xml/accessibility_service_config.xml`.
Manifest permissions are declared in `app/src/main/AndroidManifest.xml`.

## Usage / Quick Start

### Run The Android App

Build and install the debug variant:

```bash
./gradlew installDebug
```

Then enable the required device permissions:

```text
Settings > Apps > Special app access > Display over other apps > EdgeFlow
Settings > Accessibility > EdgeFlow Gesture Controller
```

After permissions are enabled, hold on a left or right edge handle, swipe inward, keep holding, and
release over a circular menu item to trigger the selected action.

### Generate Play Store Assets

Regenerate store graphics with the Roborazzi-backed Gradle task:

```bash
./gradlew generatePlayStoreAssets
```

```text

```

### Build A Release APK

Set signing secrets, then assemble the release variant:

```bash
KEYSTORE_PATH=/absolute/path/to/my-upload-key.jks \
STORE_PASSWORD=your-store-password \
KEY_PASSWORD=your-key-password \
./gradlew assembleRelease
```

## API Reference

Not applicable. EdgeFlow is an Android application with a local accessibility service and local Room
database. This repository does not define public HTTP endpoints, a public SDK, or a command-line API.

## Testing

Run JVM unit tests, Robolectric tests, and non-screenshot Compose tests:

```bash
./gradlew testDebugUnitTest
```

Run connected Android tests on an emulator or physical device:

```bash
./gradlew connectedDebugAndroidTest
```

Regenerate Roborazzi Play Store screenshots and graphics:

```bash
./gradlew generatePlayStoreAssets
```

Tests live under app/src/test/java/com/michael/edgeflow/ and
app/src/androidTest/java/com/michael/edgeflow/. Test files use the `*Test.kt` naming convention, with

Coverage reporting is not configured in this repository.

## Deployment

### Android

Debug builds:

```bash
./gradlew assembleDebug
```

Release builds:

```bash
KEYSTORE_PATH=/absolute/path/to/my-upload-key.jks \
STORE_PASSWORD=your-store-password \
KEY_ALIAS=upload \
KEY_PASSWORD=your-key-password \
./gradlew assembleRelease
```

provide a privacy policy URL in Play Console under App content.

Docker and docker-compose are not configured because this is a native Android project.

### Privacy Policy

Not configured in this repository. Google Play still requires a hosted privacy policy URL before release,
but no deployable privacy-policy site is tracked in this app repository.

### Health Check

Not applicable. EdgeFlow is installed locally on Android devices and does not expose a server health
endpoint.
