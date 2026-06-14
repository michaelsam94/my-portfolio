---
title: "DevPocket"
slug: "devpocket"
kind: "app"
category: "Developer"
packageId: "com.michael.devpocket"
playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.devpocket"
githubUrl: "https://github.com/michaelsam94/DevPocket"
image: "https://play-lh.googleusercontent.com/lcTbR-DGu6SblFhlF55jL_Edw99GKjx5cfcpCmmq0FyR8yYsD71zIYeTNFo-BbkV8LhbumbapwyNOeig83VIdjo"
description: "Pocket developer toolkit with small utilities for mobile engineering workflows."
source: "readme"
thin: false
---

Offline-first developer utility for Android: code workspace, formatters, regex playground, JavaScript sandbox, and built-in reference docs. Everything runs on-device with no cloud sync or telemetry.

**Package:** `com.michael.devpocket` · **Min SDK:** 24 · **Target SDK:** 36

## Features

- **Code workspace** — Syntax highlighting for JavaScript, JSON, CSS, HTML, SQL, and Markdown; bracket auto-pairing; adjustable font size; file drawer.
- **Brutal formatter** — Beautify, prettify, or minify JSON, XML, HTML, CSS, and SQL offline.
- **Regex playground** — Test patterns with global, case-insensitive, multiline, and dotAll flags; save match sessions locally.
- **JS & math sandbox** — Run JavaScript and math expressions in a local engine with stdout/stderr; load workspace files into the console.
- **Documentation vault** — Offline reference for JSON, regex, shell/bash, HTML/Markdown, and HTTP status codes.

Data (files, regex sessions, scripts) is stored in a local Room database. No internet connection is required for core features.

## Screenshots

## Privacy

Privacy policy (Netlify-hosted): [DevPocket-pv](https://github.com/michaelsam94/DevPocket-pv)

## Play Store assets

From the project root:

```bash

./gradlew generatePlayStoreAssets

```

Release bundle:

```bash
./gradlew bundleRelease
```

## Tech stack

- Kotlin, Jetpack Compose, Material 3
- Room (local persistence)
- Navigation Compose, ViewModel
- Roborazzi + Robolectric (Play Store screenshot tests)
