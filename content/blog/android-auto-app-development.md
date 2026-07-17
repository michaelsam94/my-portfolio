---
title: "Building for Android Auto"
slug: "android-auto-app-development"
description: "Build Android Auto apps with the Android for Cars App Library: supported app types, template constraints, testing on DHU, and design rules for in-car UX."
datePublished: "2026-07-12"
dateModified: "2026-07-12"
tags: ["Android", "Android Auto", "Automotive", "UX"]
keywords: "Android Auto development, Android for Cars App Library, car app templates, DHU desktop head unit, in-car UX Android"
faq:
  - q: "What app types does Android Auto support?"
    a: "Android Auto supports navigation (full custom map), point of interest (lists and details), internet of things (device control), and media apps (via Media3/MediaBrowserService). You cannot port a standard phone UI — all non-navigation apps must use the Android for Cars App Library templates with strict layout and interaction constraints."
  - q: "How do you test Android Auto apps without a car?"
    a: "Use the Desktop Head Unit (DHU) emulator included in the Android SDK. Connect your phone running the debug build via ADB, or run the DHU in standalone mode with an emulator image. Google also provides an Android Auto test suite app for compatibility validation before Play Store submission."
  - q: "What are the main Android Auto design constraints?"
    a: "No custom layouts — use provided templates (List, Grid, Pane, Message, etc.). Maximum item counts per template. No scrolling text, no complex gestures, no keyboard input while driving. All interactions must be completable via rotary controller or voice. Distraction optimization is enforced at the framework level."
---

Android Auto isn't your phone app on a bigger screen. Google enforces template-based UI through the Android for Cars App Library — you pick from a fixed set of layouts, populate them with data, and handle user actions through callbacks. No RecyclerView, no custom Compose, no floating action buttons. I built a POI app for Auto and spent the first week fighting the templates before realizing the constraint is the feature: it forces you to design for glances and voice, which is exactly what driving demands.

## Supported app categories

| Category | Library | Custom UI |
|----------|---------|-----------|
| Navigation | Navigation SDK | Full map control |
| Point of interest | Car App Library | Templates only |
| IoT | Car App Library | Templates only |
| Media | Media3 / MediaBrowser | System-provided media UI |

If your app doesn't fit these categories, it doesn't belong on Auto. Google rejected an early version of a productivity app I consulted on — "task manager" isn't a supported category.

## Project setup

Add the Car App Library dependency:

```kotlin
dependencies {
    implementation("androidx.car.app:app:1.4.0")
    implementation("androidx.car.app:app-projected:1.4.0")  // phone-as-projected
}
```

Declare your car app service in the manifest:

```xml
<service
    android:name=".CarAppService"
    android:exported="true">
    <intent-filter>
        <action android:name="androidx.car.app.CarAppService" />
        <category android:name="androidx.car.app.category.POI" />
    </intent-filter>
    <meta-data
        android:name="androidx.car.app.minCarApiLevel"
        android:value="1" />
</service>
```

Your `CarAppService` creates sessions that host screens:

```kotlin
class CarAppService : SessionCarAppService() {
    override fun createSession(): Session = object : Session() {
        override fun onCreateScreen(intent: Intent): Screen = PlaceListScreen(carContext)
    }
}
```

## Template-based screens

Every screen extends `Screen` and returns a `Template`:

```kotlin
class PlaceListScreen(carContext: CarContext) : Screen(carContext) {
    override fun onGetTemplate(): Template {
        val places = repository.getNearbyPlaces()
        return ListTemplate.Builder()
            .setTitle("Nearby")
            .setHeaderAction(Action.APP_ICON)
            .setSingleList(
                ItemList.Builder().apply {
                    places.forEach { place ->
                        addItem(
                            Row.Builder()
                                .setTitle(place.name)
                                .addText(place.address)
                                .setOnClickListener {
                                    screenManager.push(PlaceDetailScreen(carContext, place))
                                }
                                .build()
                        )
                    }
                }.build()
            )
            .build()
    }
}
```

Available templates: `ListTemplate`, `GridTemplate`, `PaneTemplate`, `MessageTemplate`, `SearchTemplate`, `TabTemplate`, `PlaceListMapTemplate`. Pick the one that fits — you can't combine them freely.

## Navigation apps are different

Navigation apps use the Navigation SDK with full map rendering — a completely separate API surface. If you're building turn-by-turn directions, start with the [Navigation SDK documentation](https://developer.android.com/guide/navigation), not the Car App Library. POI and media apps are simpler; navigation is its own specialization.

## Testing with DHU

Install the Desktop Head Unit from SDK Manager (`Android Auto Desktop Head Unit Emulator`):

```bash
# Connect phone via USB with USB debugging
adb forward tcp:5277 tcp:5277
~/Library/Android/sdk/extras/google/auto/desktop-head-unit
```

Or run headless for CI (limited — mostly smoke testing):

```bash
./desktop-head-unit --headless
```

Test with both touch and rotary input modes. Many real car head units are rotary-only — if you design for touch, you'll ship broken UX for a large segment.

## Distraction optimization

Google enforces driver distraction rules programmatically:

- Item lists capped (typically 6 items per page with pagination)
- No text input templates while driving (parked mode allows more)
- No video, animation, or scrolling marquees
- Actions must be large touch targets

Use `ParkedOnlyOnClickListener` for actions that require attention:

```kotlin
.setOnClickListener(
    ParkedOnlyOnClickListener.create {
        // Only fires when car is parked
        showComplexSettings()
    }
)
```

## Play Store submission

Before publishing:
1. Run the Android Auto test suite (available in Play Console)
2. Test on DHU with touch and rotary modes
3. Verify your app category matches your manifest declaration
4. Include Auto screenshots in your Play Store listing

Auto apps go through an additional review beyond standard Play review.

## Navigation and session lifecycle

Car apps have strict lifecycle rules — the system kills your app aggressively:

```kotlin
override fun onStop() {
    // Save navigation state — user may return hours later
    sessionStorage.save(currentScreen, scrollPosition)
}

override fun onStart() {
    // Restore or show fresh content if stale > 24h
}
```

`ScreenManager` stack depth is limited. Don't push 10 screens deep — flatten to tab-like navigation where possible. Back always returns to root browse screen.

## Car hardware fragmentation

Test matrix beyond DHU:

| Input | Vehicles | Test focus |
|-------|----------|------------|
| Touch | Newer vehicles | Large targets, swipe vs tap |
| Rotary | BMW, Mazda, older | Focus order, no hover states |
| Hybrid | Many 2024+ models | Both input modes in same app |

Rotary input requires explicit focus — Compose for Auto handles much of this, but custom components need `Modifier.focusable()` and visible focus indicators.

## Media vs messaging vs navigation apps

Template selection depends on category:

- **Media:** `MediaBrowserService` + Media3 session — see [Media3 media session guide](https://blog.michaelsam94.com/android-media3-media-session/)
- **Messaging:** `CarMessagingService` with short replies only when parked
- **Navigation:** Turn-by-turn via Navigation SDK, not custom map in `SurfaceContainer`

Declaring wrong category in manifest causes Play rejection. Match template usage to declared `automotive_app_desc.xml` categories.

## Production checklist

- [ ] Tested on DHU with touch and rotary input
- [ ] `ParkedOnlyOnClickListener` on complex actions
- [ ] Item lists paginated within Google distraction limits
- [ ] Auto app quality checklist passed in Play Console
- [ ] Lifecycle state saved in `onStop` for session restore

Car OEM skins vary font sizes dramatically — test your templates at smallest and largest system font scale before Play submission to avoid truncated action labels.

## Common production mistakes

Teams get auto app development wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping auto app development on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Distraction optimization templates

Media and messaging templates restrict custom UI — attempting full Compose in car screen fails certification. Test on Desktop Head Unit with touch and rotary input profiles; focus order differs from phone TalkBack.

## CarAppService lifecycle

User disconnects phone USB — service killed without warning. Persist navigation session to recover on reconnect; do not assume `onDestroy` equals user exit.

## Auto App Development Supplement 0 on Samsung and Pixel divergence

Exercise auto app development supplement 0 on Galaxy A-series and Pixel a-series — emulators hide OEM battery and storage quirks. Capture Macrobenchmark or Firebase trace for the critical path touching auto; regressions above 8% block release for `android-auto-app-development-supplement-0`.

Document permission and background behavior in internal runbook: what breaks under Doze, what requires foreground service, and what Play policy declarations apply. Support tickets referencing "Auto App Development Supplement 0" should map to a single runbook section with known workarounds.

## Development regression gates for Play Vitals

Before promoting `android-auto-app-development-supplement-0` changes past 20% rollout, compare ANR rate, slow cold start, and excessive wakeups against seven-day baseline. Fail rollback review if 0 path shows >5% increase in `slow frames` without documented trade-off approval.

## Resources

- [Android for Cars App Library guide](https://developer.android.com/training/cars/apps)
- [Car App Library templates reference](https://developer.android.com/reference/androidx/car/app/model/package-summary)
- [Build a point-of-interest app for Android Auto](https://developer.android.com/training/cars/poi)
- [Android Auto app quality guidelines](https://developer.android.com/docs/quality-guidelines/car-app-quality)
- [Media3 for Android Auto](https://blog.michaelsam94.com/android-media3-media-session/)
