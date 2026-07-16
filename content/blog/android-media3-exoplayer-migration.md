---
title: "Migrating from ExoPlayer to Media3 Without Regressions"
slug: "android-media3-exoplayer-migration"
description: "A practical guide to migrating from the legacy ExoPlayer to AndroidX Media3: package mapping, the migration script, MediaSession changes, and what to verify."
datePublished: "2024-07-12"
dateModified: "2024-07-12"
tags: ["Android", "Kotlin", "Media3", "ExoPlayer"]
keywords: "ExoPlayer to Media3 migration, androidx.media3, Media3 migration script, ExoPlayer deprecated, Media3 MediaSession"
faq:
  - q: "Is ExoPlayer discontinued in favor of Media3?"
    a: "Yes. The standalone com.google.android.exoplayer2 library is deprecated and no longer receiving updates; all new development happens in androidx.media3. The Media3 ExoPlayer module is the same engine under a new package name, so migrating is mostly a package and API rename rather than a rewrite, but you must migrate to keep getting fixes and new format support."
  - q: "Does Media3 require rewriting my player code?"
    a: "Mostly no. The core ExoPlayer APIs map almost one-to-one to their Media3 equivalents, and Google ships a migration script that rewrites package names automatically. The real work is in the MediaSession and playback-notification layer, which was redesigned, plus any custom components you wrote against internal APIs that changed."
  - q: "What replaces MediaSessionConnector in Media3?"
    a: "Media3's androidx.media3.session.MediaSession replaces both the old MediaSessionCompat plus MediaSessionConnector combination. A single MediaSession now wraps the Player directly and handles transport controls, metadata, and the media notification through MediaSessionService, so you delete a lot of glue code that used to bridge the player to the session."
---

If you're still on `com.google.android.exoplayer2`, you're on a dead branch: the standalone ExoPlayer is deprecated and all development moved to AndroidX Media3 under `androidx.media3`. The good news is that Media3's ExoPlayer *is* the same playback engine — the migration is overwhelmingly a package rename, not a rewrite. The part that takes real effort is the session and notification layer, which was genuinely redesigned.

I migrated a media app with a custom notification, cast support, and offline downloads. Here's the order of operations that kept it boring, which is exactly what you want from a media migration.

## Understand what actually changed

Three buckets, in increasing order of pain:

- **Package renames (trivial):** `com.google.android.exoplayer2.*` becomes `androidx.media3.*`. `SimpleExoPlayer` is now just `ExoPlayer`. `MediaItem`, `Player`, `TrackSelector` — same concepts, new import.
- **Session redesign (moderate):** the old `MediaSessionCompat` + `MediaSessionConnector` combo is replaced by a single `androidx.media3.session.MediaSession` that wraps the `Player` directly. This deletes glue code but changes your architecture.
- **Notification and service (moderate):** `PlayerNotificationManager` gives way to `MediaSessionService` (or `MediaLibraryService` for browsable content), which produces the notification for you from the session.

If you never used `MediaSessionConnector` or a background service, your migration is essentially the first bucket and you'll be done in an afternoon.

## Run the migration script first

Google ships a script that mechanically rewrites the package names across your codebase. Run it before touching anything by hand:

```bash
# From the media3 repo tooling
./media3-migration.sh -p /path/to/your/project -l -c -x -m
```

It handles the imports, the `SimpleExoPlayer` → `ExoPlayer` rename, and dependency coordinates in Gradle. It won't fix the session layer — that's intentional, because that part needs human judgment — but it clears the mechanical 80% so you can focus on the interesting 20%. Commit the script's output as its own commit so the mechanical changes are separable from your real edits in review.

## The dependencies

Media3 is modular. Pull only what you use:

```kotlin
implementation("androidx.media3:media3-exoplayer:1.x.x")
implementation("androidx.media3:media3-ui:1.x.x")
implementation("androidx.media3:media3-session:1.x.x")
// optional, as needed:
implementation("androidx.media3:media3-exoplayer-dash:1.x.x")
implementation("androidx.media3:media3-exoplayer-hls:1.x.x")
implementation("androidx.media3:media3-datasource-okhttp:1.x.x")
```

Keep every `media3-*` artifact on the *same version*. Mismatched Media3 modules produce cryptic runtime crashes that look like format bugs but are actually version skew.

## Rewiring the session

This is the substantive change. The old world had a `Player`, a `MediaSessionCompat`, and a `MediaSessionConnector` bridging them. The new world collapses that: a `MediaSession` wraps the player directly, and a `MediaSessionService` hosts it for background playback.

```kotlin
class PlaybackService : MediaSessionService() {
    private var mediaSession: MediaSession? = null

    override fun onCreate() {
        super.onCreate()
        val player = ExoPlayer.Builder(this).build()
        mediaSession = MediaSession.Builder(this, player).build()
    }

    override fun onGetSession(controllerInfo: MediaSession.ControllerInfo) =
        mediaSession

    override fun onDestroy() {
        mediaSession?.run { player.release(); release() }
        mediaSession = null
        super.onDestroy()
    }
}
```

The service now generates the media notification automatically from the session's metadata and playback state — you delete your hand-built `PlayerNotificationManager` setup. Your UI (an Activity or a Compose screen) connects with a `MediaController`, which talks to the session over IPC and gives you the same `Player` interface remotely. This is a cleaner model, and it's the same session your media notification, Android Auto, and Wear surfaces all read from — get it right once and those [background playback surfaces](https://blog.michaelsam94.com/android-media3-media-session/) come nearly for free.

## What to verify after migrating

A media pipeline has a lot of edges. My regression checklist:

1. **Adaptive streaming** — DASH and HLS still select the right renditions; ABR ladders behave.
2. **DRM** — Widevine sessions acquire and release; offline licenses still valid.
3. **Background playback** — audio continues with screen off; the notification shows correct art and controls.
4. **Audio focus** — ducking on notification sounds, pausing on a phone call, resuming after.
5. **Offline downloads** — the `DownloadManager` migration; existing downloads still play.
6. **Track selection** — subtitles and audio-language switching.
7. **Cast** — if you use it, the Cast extension moved to Media3 too.

Run these on a real device, with the screen off, on a metered network. Media bugs love the exact conditions your dev loop doesn't cover.

## What I'd take away

Media3 is not a new player — it's ExoPlayer with a better session model and a stable AndroidX home. Let the migration script do the mechanical package rename in its own commit, keep all `media3-*` modules on one version, and spend your real effort collapsing the old `MediaSessionCompat` + `MediaSessionConnector` glue into a single `MediaSession` hosted by `MediaSessionService`. Then run a proper regression pass over streaming, DRM, background playback, and downloads on real hardware. Do it in that order and the migration is tedious rather than scary — which, for the thing that plays your users' media, is the goal.

## Common production mistakes

Teams get media3 exoplayer migration wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping media3 exoplayer migration on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Resources

- [Migrating to Media3 (Android)](https://developer.android.com/media/media3/exoplayer/migration-guide)
- [Media3 overview](https://developer.android.com/media/media3)
- [MediaSession and MediaController](https://developer.android.com/media/media3/session/control-playback)
- [Background playback with MediaSessionService](https://developer.android.com/media/media3/session/background-playback)
- [Media3 release notes](https://developer.android.com/jetpack/androidx/releases/media3)
