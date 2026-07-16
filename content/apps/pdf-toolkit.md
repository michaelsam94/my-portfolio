---
title: "PDF Toolkit"
slug: "pdf-toolkit"
kind: "app"
category: "Document"
packageId: "com.michael.pdftoolkit"
playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.pdftoolkit"
githubUrl: "https://github.com/michaelsam94/PDF-Toolkit"
image: "https://play-lh.googleusercontent.com/ooKhHiR-q_fS7luJcQXETk-tr0HlHSm5x-IsuXu65CvaE8my1FbIEbmX0UCNYduWB0y4kleaqo2PcTV-MEyrgA"
description: "Free ad-free PDF toolkit for Android. Merge PDF, split PDF, sign PDF, and convert Markdown to PDF offline on your device — no ads, no uploads, no account."
source: "readme"
thin: false
primaryKeyword: "ad-free PDF toolkit Android"
keywords: "ad-free PDF tools, no ads PDF app, merge PDF Android, split PDF Android, sign PDF Android, PDF to Markdown, Markdown to PDF, offline PDF editor, privacy PDF toolkit, free PDF tools without ads"
---

PDF Toolkit is a free, completely ad-free Android app for everyday PDF work: merge, split, sign, and convert documents offline on your device so files never leave your phone.

**Ad-free:** Completely ad-free — no ads, no trackers, no sponsored clutter.

Privacy-first Android app for everyday PDF tasks. Merge, split, sign, and convert documents entirely on device — your files never leave your phone or tablet.

**Package:** `com.michael.pdftoolkit`

## Features

- **Home hub** — Recent documents, search, and quick access to every tool
- **Merge PDFs** — Queue multiple files, reorder them, and combine into one document
- **Split PDFs** — Extract custom page ranges into separate PDFs
- **Sign PDFs** — Draw vector signatures, adjust stroke color and width, save reusable signatures, and stamp them onto selected pages
- **Markdown to PDF** — Write or paste Markdown and generate a formatted PDF locally
- **Share & save** — Export completed documents from the app

All processing runs offline. PDF Toolkit does not upload your documents to external servers.

## Tech stack

- Kotlin · Jetpack Compose · Material 3
- Navigation Compose · ViewModel · Room
- PDFBox Android for PDF operations
- Roborazzi for Play Store screenshot generation

## Play Store assets

```bash
./gradlew generatePlayStoreAssets
```

## Project layout

```
├── app/                 Android application module
├── gradle/              Version catalog and wrapper

├── build.gradle.kts     Root Gradle config
└── settings.gradle.kts
```
