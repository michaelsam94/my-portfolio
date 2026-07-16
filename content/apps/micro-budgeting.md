---
title: "Micro Budgeting"
slug: "micro-budgeting"
kind: "app"
category: "Finance"
packageId: "com.michael.microbudgeting"
playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.microbudgeting"
githubUrl: "https://github.com/michaelsam94/Micro-Budgeting"
image: "https://play-lh.googleusercontent.com/8LLJaE7oILJduEYlilZmwoINxnrrFyUTITDdRsNk6MspnGcFyJPeM9_zE5hKbuxrMsKF4EbS0suMYs4Yc76V"
description: "Ad-free offline budgeting app for Android. Track expenses, category budgets, charts, and encrypted backups — no ads, no bank login, no internet permission."
source: "readme"
thin: false
primaryKeyword: "ad-free offline budget app Android"
keywords: "ad-free expense tracker, no ads budgeting app, offline budget planner Android, category spending tracker, encrypted budget backup, privacy finance app, manual expense log, budget app without ads or bank sync"
---

Micro Budgeting is an ad-free, offline Android expense tracker for logging everyday spending, setting category budgets, and reviewing monthly charts — without accounts, ads, or bank connections.

**Ad-free:** Completely ad-free — no ads, no trackers, no sponsored clutter.

Build status and coverage badges are not shown because this repository does not currently include CI or coverage
configuration.

## Project Overview

Micro Budgeting is an offline Android app for tracking everyday expenses, setting category budgets, and reviewing monthly
spending. It is built for people who want a small personal finance tool without accounts, cloud sync, bank connections, or
internet permission.

The app stores data locally, uses SQLCipher-backed Room storage on real devices, and supports passphrase-protected export

## Key Features

- 🔒 Offline by design: the manifest declares no internet, SMS, contacts, location, camera, or microphone permissions.
- 🧾 Manual expense logging: add amount, category, note, and date for each transaction.
- 🏷️ Category budgets: set spending caps and track remaining budget by category and month.
- 📊 Spending charts: review monthly distribution and budget progress with Compose visualizations.
- 📨 Bank alert parsing: paste transaction alert text manually to extract an amount and suggested category for review.
- 🔐 Encrypted local backups: export and import budget data with passphrase-based AES-GCM encryption.
- 🎨 Store-ready branding: includes launcher icons, a feature graphic, phone screenshots, and tablet screenshots.
- 🧪 Screenshot automation: Roborazzi tests regenerate Play Store assets from deterministic seeded scenes.

## Architecture Overview

### Components And Layers

- `MainActivity` starts the Compose app, enables edge-to-edge drawing, and creates `FinanceViewModel`.
- presentation/ contains tabs, dialogs, charts, bottom navigation, toolbar branding, and UI state rendering.
- domain/ defines `Category`, `Transaction`, `Budget`, `BudgetSummary`, and repository interfaces.
- data/repository/ maps Room entities to domain models and seeds default categories.
- data/local/db/ contains Room entities, DAOs, and SQLCipher database setup.
- `data/sms/SmsParser.kt` parses manually pasted bank alert text; it does not read the device inbox.
- `data/backup/EncryptedBackupSerializer.kt` serializes backup payloads with Moshi and encrypts them with AES-GCM.

### Data Flow

1. A user adds an expense, configures a budget, pastes a bank alert, or imports/exports a backup.
2. Compose UI events call `FinanceViewModel` methods.
3. The ViewModel validates input and delegates persistence work to repository interfaces.
4. Repository implementations write Room entities to the encrypted local database.
5. Room `Flow` streams feed updated categories, transactions, and budgets back to the UI.
6. Backup export serializes local data, encrypts it with a passphrase, and places the encoded payload where the user can
   copy or save it.

### Design Patterns

- MVVM for UI state, user actions, and lifecycle-aware data observation.
- Repository interfaces to separate domain behavior from Room persistence.
- A small dependency container in `AppContainerImpl` for application-level wiring.
- Reactive Kotlin `Flow` streams for month-scoped transaction and budget summaries.
- Test-only fixtures for deterministic Play Store screenshot generation.

## Tech Stack & Libraries

| Layer | Technology | Version | Purpose |
|---|---:|---:|---|
| Language | Kotlin | 2.2.10 | Android app implementation |
| Build | Android Gradle Plugin | 9.1.1 | Android build system |
| UI | Jetpack Compose Material 3 | Compose BOM 2024.09.00 | Declarative UI |
| Activity | AndroidX Activity Compose | 1.10.1 | Compose activity entry point |
| Lifecycle | AndroidX Lifecycle | 2.8.7 | ViewModel and lifecycle-aware state |
| Navigation | AndroidX Navigation Compose | 2.8.9 | Available dependency; current UI uses tabs |
| Persistence | Room | 2.7.0 | SQLite abstraction and DAO generation |
| SQLite | AndroidX SQLite | 2.6.2 | SQLite integration |
| Encryption | SQLCipher Android | 4.16.0 | Encrypted local database storage |
| Key Storage | AndroidX Security Crypto | 1.1.0-alpha06 | MasterKey and encrypted preferences |
| JSON | Moshi | 1.15.2 | Backup payload serialization |
| Networking libs | OkHttp / Retrofit | 4.10.0 / 2.12.0 | Present as dependencies, not used for app networking |
| Coroutines | Kotlinx Coroutines | 1.10.2 | Background work and Flow collection |
| Screenshots | Roborazzi | 1.59.0 | Play Store screenshot and feature graphic generation |
| JVM Android tests | Robolectric | 4.16.1 | Local Android runtime tests |
| Unit tests | JUnit | 4.13.2 | Test runner and assertions |

## Configuration

The primary app configuration lives in `app/build.gradle.kts`:

- `namespace`: `com.michael.microbudgeting`
- `applicationId`: `com.michael.microbudgeting`
- `minSdk`: `24`
- `targetSdk`: `36`
- `compileSdk`: `36.1`
- `versionCode`: `5`
- `versionName`: `1.0.3`

Release signing is configured in the `signingConfigs.release` block. Credentials can come from environment variables or
from `key.properties`; keep keystores and passwords out of public repositories.

Theme and brand colors live in:

- `app/src/main/java/com/michael/microbudgeting/ui/theme/Color.kt`
- `app/src/main/java/com/michael/microbudgeting/ui/theme/Theme.kt`
- `app/src/main/res/values/colors.xml`

Gradle restart or sync is required after changing build files, dependency versions, signing settings, or SDK versions.

## Usage / Quick Start

### Build, Install, And Launch

```bash
./gradlew :app:assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb shell monkey -p com.michael.microbudgeting 1
```

### Generate A Signed Release Bundle

Set `STORE_PASSWORD` and `KEY_PASSWORD` in the shell or `key.properties` before running Gradle.

```bash
export KEYSTORE_PATH=/absolute/path/to/my-upload-key.jks
export KEY_ALIAS='upload'
./gradlew :app:bundleRelease
```

The release bundle is written to:

```text
app/build/outputs/bundle/release/app-release.aab
```

### Regenerate Play Store Assets

```bash
./gradlew generatePlayStoreAssets
```

Generated assets are written to:

```text

```

## API Reference

Not applicable. Micro Budgeting is a local Android application and does not expose an HTTP API, SDK, command-line API, or
public service endpoint.

## Testing

### JVM And Robolectric Tests

```bash
./gradlew :app:testDebugUnitTest
```

Test locations:

- app/src/test/java/com/michael/microbudgeting/
- app/src/test/java/com/michael/microbudgeting/playstore/

Naming convention: JVM and Robolectric tests use `*Test.kt`. Play Store screenshot tests are marked with the
`PlayStoreScreenshotTests` JUnit category and are included when screenshot generation is requested.

### Instrumented Tests

```bash
./gradlew :app:connectedDebugAndroidTest
```

Instrumented tests live in app/src/androidTest/.

### Screenshot And Store Asset Tests

```bash
./gradlew generatePlayStoreAssets
```

### Coverage

Not configured. No JaCoCo, Kover, or hosted coverage report is present in this repository.

## Deployment

### Debug APK

```bash
./gradlew :app:assembleDebug
```

Output:

```text
app/build/outputs/apk/debug/app-debug.apk
```

### Release AAB For Google Play

```bash
./gradlew :app:bundleRelease
```

Output:

```text
app/build/outputs/bundle/release/app-release.aab
```

Before uploading to Play Console, confirm:

- `versionCode` is greater than the last uploaded bundle.
- The Play Store app name is `Micro Budgeting`.
- The installed app label is `Micro Budgeting`.

### Docker And Cloud

Not applicable. This repository builds a native Android app and has no Dockerfile, server process, cloud deployment
target, or backend health endpoint.

### Health Check

Not applicable for a server endpoint. For app health, run tests, install the APK on a test device, and verify that the
app launches and can add an expense, parse pasted alert text, and export/import a backup.
