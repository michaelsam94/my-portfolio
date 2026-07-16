---
title: "Play Asset Delivery for Large Games and Media Apps"
slug: "android-play-asset-delivery"
description: "Ship large game and media assets with Play Asset Delivery: install-time, fast-follow, and on-demand asset packs, plus how to fetch and cache them at runtime."
datePublished: "2024-06-26"
dateModified: "2024-06-26"
tags: ["Android", "App Bundle", "Games", "Play Store"]
keywords: "Play Asset Delivery, asset packs, install-time delivery, fast-follow, on-demand assets, AssetPackManager, large games Android"
faq:
  - q: "What is Play Asset Delivery?"
    a: "Play Asset Delivery is Google Play's system for shipping large game and media assets — textures, audio, models — in asset packs inside your Android App Bundle instead of bundling them into the APK or downloading them from your own servers. Play hosts and serves the packs, handles delta patching on updates, and supports install-time, fast-follow, and on-demand delivery modes so you control when each pack arrives."
  - q: "What are the three asset pack delivery modes?"
    a: "Install-time packs are delivered with the app and available immediately, subject to the total install-time size limit. Fast-follow packs download automatically right after install without blocking first launch. On-demand packs download only when your game requests them at runtime, which is ideal for later levels or optional content the player may never reach."
  - q: "Why use Play Asset Delivery instead of my own CDN?"
    a: "Play hosts the assets for free within Play's limits, applies binary delta patching so updates only download changed bytes, and integrates with the install flow so users get a single trusted progress experience. Rolling your own CDN means paying for bandwidth, building your own patching and integrity checks, and managing a second download the user doesn't expect. PAD removes all of that for content that fits its model."
---

Play Asset Delivery (PAD) is how you ship a game with gigabytes of textures and audio without either bloating the APK past Play's limits or building your own download-from-CDN pipeline. Assets live in **asset packs** inside your Android App Bundle, and Google Play hosts them, serves them, and delta-patches them on every update so players only re-download the bytes that changed. I've used PAD to move a 1.4GB game off a fragile custom downloader — the one that failed on flaky connections and had no delta updates — onto Play's infrastructure, which handled patching, resumption, and integrity for free. The win is that you stop maintaining download infrastructure that Play already runs better than you can.

## Why not just put assets in the APK or your own server

Two bad options PAD replaces:

- **Cramming everything into the base APK/bundle.** You hit Play's install-time size ceiling, and every tiny code change forces users to re-download hundreds of MB because the APK is one unit.
- **Downloading from your own CDN after first launch.** Now you own bandwidth costs, resumable downloads, delta patching, integrity verification, retry logic, and a second progress bar users don't trust. That's a lot of undifferentiated infrastructure.

PAD gives you Play-hosted assets, automatic binary diffing on updates, and a delivery model that hooks into the install experience. For content that fits within Play's per-pack and total limits, it's strictly less work.

## The three delivery modes

An asset pack declares one delivery mode, and choosing correctly is the whole design:

| Mode | Arrives | Use for |
|---|---|---|
| **install-time** | With the app, available at first launch | Assets needed immediately (main menu, tutorial, early levels) |
| **fast-follow** | Automatically right after install, no blocking | Content you'll need soon but not in the first seconds |
| **on-demand** | Only when the game requests it at runtime | Later levels, optional modes, high-res texture packs |

The pattern I use for a big game: a small install-time pack for the first playable experience, a fast-follow pack for the next chunk so it's ready by the time the player finishes the tutorial, and on-demand packs for everything beyond — so a player who never reaches level 40 never downloads level 40's assets.

## Declaring an asset pack

Each asset pack is its own Gradle module with an `assets/` directory and a build file naming the delivery mode:

```groovy
// leveldata/build.gradle
plugins { id 'com.android.asset-pack' }

assetPack {
    packName = "level_data"
    dynamicDelivery {
        deliveryType = "on-demand"   // or "install-time" / "fast-follow"
    }
}
```

The base app declares it depends on the pack, and everything ships inside the single `.aab`. No separate upload, no separate hosting.

## Fetching on-demand packs at runtime

On-demand packs use `AssetPackManager`, and like dynamic features, the discipline is treating the fetch as a stateful async operation with progress and failure handling:

```kotlin
val manager = AssetPackManagerFactory.getInstance(context)

manager.registerListener { state ->
    when (state.status()) {
        AssetPackStatus.DOWNLOADING -> {
            val pct = 100.0 * state.bytesDownloaded() / state.totalBytesToDownload()
            updateProgress(pct)
        }
        AssetPackStatus.WAITING_FOR_WIFI ->
            manager.showConfirmationDialog(activity)   // large pack on cellular
        AssetPackStatus.COMPLETED -> {
            val path = manager.getPackLocation("level_data")?.assetsPath()
            loadLevelFrom(path)
        }
        AssetPackStatus.FAILED -> retryOrFallback(state.errorCode())
    }
}

manager.fetch(listOf("level_data"))
```

`WAITING_FOR_WIFI` is PAD's equivalent of the confirmation prompt — a large pack on a metered connection waits until you either get the user's OK or Wi-Fi appears. For a multi-GB game you *want* this; surprising a player with a cellular download is how you earn one-star reviews.

## Getting to the files

After a pack is available, you access its files by path, not through the normal APK asset manager. `getPackLocation(packName)` gives you a directory; for install-time packs you can also read via `AssetManager`. The important runtime caveat: never assume a pack is present. Query `getPackStates` on startup, and gate any code path that touches pack assets behind a confirmed `COMPLETED` state with a fallback (e.g. a "download this content" screen) if it isn't. Loading a texture from a pack that hasn't arrived is a crash, and it's a crash your emulator won't show if you side-loaded everything.

## Texture targeting saves real bandwidth

PAD supports **texture compression format targeting**: you ship ASTC, ETC2, and other formats in the same pack, and Play delivers only the format the device supports. For a texture-heavy game this can halve what a given device downloads, because it never receives the formats it can't use — the same per-device optimization philosophy behind [App Bundle configuration splits](https://blog.michaelsam94.com/android-app-bundle-dynamic-features/), applied to GPU assets.

## Testing and limits

Test with `bundletool` to build and install APK sets locally, and use Play's internal app sharing to exercise real delivery. Watch the limits: install-time packs count against the total install size ceiling, and individual packs have their own maximum size, so very large games split content across multiple on-demand packs. Design your pack boundaries around *when content is needed* and *how big each piece is*, not around your source tree's folder layout.

The mindset shift PAD asks for is the same one dynamic features ask for: content is not guaranteed to be present, so every access is a checked, resumable, user-aware operation. Accept that, let Play own hosting and patching, and you delete an entire category of custom download infrastructure while giving players faster installs and smaller updates.

## Resources

- [About Play Asset Delivery](https://developer.android.com/guide/playcore/asset-delivery)
- [Integrate asset delivery (native and Java)](https://developer.android.com/guide/playcore/asset-delivery/integrate-java)
- [Texture compression format targeting](https://developer.android.com/guide/playcore/asset-delivery/texture-compression)
- [Build and test asset packs with bundletool](https://developer.android.com/tools/bundletool)
- [About Android App Bundles](https://developer.android.com/guide/app-bundle)
