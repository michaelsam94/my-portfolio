---
title: "Media3 MediaSession and Background Playback"
slug: "android-media3-media-session"
description: "Set up a Media3 MediaSession and MediaSessionService for reliable background audio: the notification, MediaController, audio focus, and surviving process death."
datePublished: "2024-07-13"
dateModified: "2024-07-13"
tags: ["Android", "Kotlin", "Media3", "Background Work"]
keywords: "Media3 MediaSession, MediaSessionService, background playback Android, MediaController, media notification Media3"
faq:
  - q: "What is the difference between MediaSession and MediaSessionService in Media3?"
    a: "MediaSession is the object that wraps your Player and exposes playback state, metadata, and transport controls to external clients. MediaSessionService is the foreground service that hosts one or more MediaSessions so playback continues when your UI is gone. You use the session for control and the service for lifecycle — together they give you background audio with a system media notification."
  - q: "Do I need a foreground service for background audio in Media3?"
    a: "Yes. Continuous audio playback while the app is backgrounded requires a foreground service with the mediaPlayback service type, which is exactly what MediaSessionService provides. The service publishes a media-style notification that satisfies the foreground-service requirement and gives users transport controls."
  - q: "How does MediaController connect to a MediaSession?"
    a: "MediaController is built asynchronously against a SessionToken that points at your MediaSessionService. Once connected it implements the same Player interface as the underlying player, so your UI calls play, pause, and seek on the controller and those commands travel over IPC to the session. This decouples your UI from the service's lifecycle."
---

Background audio on Android used to be a swamp of `MediaSessionCompat`, a foreground service you hand-rolled, and a notification you assembled by hand. Media3 replaces all of it with two collaborating pieces: a `MediaSession` that wraps your `Player`, and a `MediaSessionService` that hosts the session so playback survives your UI being gone. Get these two right and the system media notification, lock-screen controls, Android Auto, and Wear surfaces all read from the same source of truth.

I'll walk through the setup that actually holds up in production — not just "audio plays," but audio that keeps playing correctly through backgrounding, audio focus changes, and process death.

## The two pieces and why both exist

The split maps cleanly onto responsibilities:

- **`MediaSession`** is the control surface. It wraps the `Player`, publishes playback state and metadata, and accepts transport commands from any connected controller — your own UI, the system notification, Bluetooth headset buttons, Assistant.
- **`MediaSessionService`** is the lifecycle host. It's a foreground service (type `mediaPlayback`) that keeps the process alive while audio plays and turns the session into a media notification automatically.

Your UI never touches the service's `Player` directly. It connects with a `MediaController`, which speaks the same `Player` interface but marshals calls over IPC to the session. That decoupling is the whole point: the service owns playback, the UI is just one of many possible controllers.

## The service

```kotlin
class PlaybackService : MediaSessionService() {
    private var session: MediaSession? = null

    override fun onCreate() {
        super.onCreate()
        val player = ExoPlayer.Builder(this)
            .setAudioAttributes(AudioAttributes.DEFAULT, /* handleAudioFocus = */ true)
            .setHandleAudioBecomingNoisy(true)
            .build()
        session = MediaSession.Builder(this, player).build()
    }

    override fun onGetSession(info: MediaSession.ControllerInfo) = session

    override fun onTaskRemoved(rootIntent: Intent?) {
        val player = session?.player ?: return
        if (!player.playWhenReady || player.mediaItemCount == 0) {
            stopSelf()
        }
    }

    override fun onDestroy() {
        session?.run { player.release(); release() }
        session = null
        super.onDestroy()
    }
}
```

Two flags earn their keep in the builder. `handleAudioFocus = true` makes the player request focus, duck for notifications, and pause on a phone call automatically — behavior users expect and that's miserable to reimplement. `setHandleAudioBecomingNoisy(true)` pauses when headphones are unplugged, so your track doesn't suddenly blast from the phone speaker on a train.

Register it with the foreground service type in the manifest:

```xml
<service
    android:name=".PlaybackService"
    android:foregroundServiceType="mediaPlayback"
    android:exported="true">
    <intent-filter>
        <action android:name="androidx.media3.session.MediaSessionService"/>
    </intent-filter>
</service>
```

## The notification comes for free

This is the biggest quality-of-life win over the old world. `MediaSessionService` generates the media-style notification from the session's current `MediaItem` metadata and playback state — title, artist, artwork, play/pause/skip. You don't build a `Notification` at all in the common case. If you need custom command buttons, you provide them via a `MediaNotification.Provider` or custom session commands, but the default covers most audio apps.

Because it derives from the session, the notification, lock screen, and any [Android Auto surface](https://blog.michaelsam94.com/android-auto-app-development/) stay in sync automatically. One state, many views.

## Connecting the UI

Your Activity or Compose screen builds a controller against the service's token:

```kotlin
val token = SessionToken(context, ComponentName(context, PlaybackService::class.java))
val controllerFuture = MediaController.Builder(context, token).buildAsync()

controllerFuture.addListener({
    val controller = controllerFuture.get()
    controller.setMediaItems(playlist)
    controller.prepare()
    controller.play()
}, MoreExecutors.directExecutor())
```

The controller *is* a `Player`, so your UI observes `Player.Listener` callbacks for position, buffering, and item transitions exactly as if it held the player locally. Release the controller (`MediaController.releaseFuture`) in your UI's teardown so you don't leak the connection.

## The things that bite in production

A checklist from shipping this:

1. **Release order.** Always release the `Player` before the `MediaSession`, and null your references. Reversed order or a leaked player is the classic Media3 memory leak.
2. **`onTaskRemoved`.** Decide your behavior when the user swipes the app away. Music apps often keep playing; a video app usually stops. Handle it explicitly or you'll get inconsistent behavior across OEMs.
3. **Process death.** If the system kills your service under memory pressure, playback stops. For resume-after-kill, persist the current item and position and restore on reconnect — the OS won't do it for you.
4. **Notification permission.** On Android 13+ the media notification needs [`POST_NOTIFICATIONS`](https://blog.michaelsam94.com/android-notification-runtime-permission/). Request it or your foreground service notification may not appear.
5. **Playlist vs single item.** Feed the player a full `MediaItem` list so skip-next/prev work from the notification without you wiring anything.

## What I'd take away

Model background audio as a `MediaSession` wrapping the `Player` plus a `MediaSessionService` hosting it, and let the service generate the media notification for you. Turn on `handleAudioFocus` and `handleAudioBecomingNoisy` so the player behaves like users expect, connect your UI through a `MediaController` rather than reaching into the service, and be deliberate about release order, `onTaskRemoved`, and restoring state after process death. That's the setup that keeps audio playing correctly with the screen off, through a phone call, and after a swipe-away — which is the entire job of a media app.

## Common production mistakes

Teams get media3 media session wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping media3 media session on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Resources

- [Background playback with MediaSessionService](https://developer.android.com/media/media3/session/background-playback)
- [Control and advertise playback with MediaSession](https://developer.android.com/media/media3/session/control-playback)
- [Media3 session guide](https://developer.android.com/media/media3/session)
- [Foreground service types](https://developer.android.com/develop/background-work/services/fg-service-types)
- [Media3 overview](https://developer.android.com/media/media3)
