---
title: "Doc Scanner Vectorizer"
slug: "doc-scanner-vectorizer"
kind: "app"
category: "Document"
packageId: "com.michael.docscannervectorizer"
playStoreUrl: "https://play.google.com/store/apps/details?id=com.michael.docscannervectorizer"
githubUrl: "https://github.com/michaelsam94/Doc-Scanner-Vectorizer"
image: "https://play-lh.googleusercontent.com/XQI8MGScBd3x0KypFyeilCmgcVZ8u9ikG9xIdxMjmDcyfgobnZPUpUHV8rmk-Jmyw2t33mILKfjokrbsfHb9cA"
description: "Ad-free Android document scanner with perspective correction, paper cleanup filters, scan history, and SVG vector export — no ads, camera-based, privacy-first."
source: "readme"
thin: false
primaryKeyword: "ad-free document scanner Android"
keywords: "ad-free document scanner, no ads PDF scanner Android, scan documents to SVG, vectorize document scan, perspective correct scan, paper cleanup filters, offline document scanner, CameraX document scanner, scan to PNG SVG"
---

Doc Scanner Vectorizer is an ad-free Android document scanner that captures paper pages, cleans them up, saves scan history, and exports SVG vectors — all without ads or unnecessary cloud dependency for core scanning.

**Ad-free:** Completely ad-free — no ads, no trackers, no sponsored clutter.

Native Android document scanner that captures paper pages, applies cleanup filters, saves scan history, and exports SVG vectors.

## App Details

- Package: `com.michael.docscannervectorizer`
- Version: `1.0.2` (`versionCode 3`)
- Minimum SDK: `24`
- Target SDK: `35`
- UI: Jetpack Compose
- Camera: CameraX
- Signing: release AAB uses the archived upload key in ~/Desktop/playstore-keys/Doc-Scanner-Vectorizer/

## Features

- Live document boundary tracking with CameraX
- Manual capture fallback
- Perspective-corrected document scans
- Paper cleanup filters: Original, Grayscale, Monochrome, Shadow Removed, and Magic Color
- Saved scan history with notes
- PNG sharing
- SVG vector export
- Gallery import for existing images

## Play Store Assets

- `app-icon-512.png`
- `feature-graphic.png`
- `phone/*.png`
- `tablet/*.png`
- `listing-descriptions.md`

Regenerate assets:

```bash
JAVA_HOME=/opt/homebrew/Cellar/openjdk@17/17.0.19/libexec/openjdk.jdk/Contents/Home ./gradlew generatePlayStoreAssets --no-configuration-cache

```

## Release Notes

The current release targets API 35 and uses CameraX `1.4.2` with native libraries rebuilt for 16 KB memory page size support. The release bundle is built with Android Gradle Plugin `8.6.1`.

## Secrets

Do not commit signing files or local machine config:

- `key.properties`
- `*.jks`
- `*.keystore`
- `local.properties`

Release signing material is stored separately in the private `playstore-keys` archive.
