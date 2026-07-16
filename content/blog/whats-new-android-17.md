---
title: "What's New in Android 17 for Developers"
slug: "whats-new-android-17"
description: "A developer's read on Android 17: what the new API level changes for behavior, adaptive layouts, background limits, privacy, and what breaks when you bump targetSdk."
datePublished: "2026-05-03"
dateModified: "2026-05-03"
tags: ["Android", "Android 17", "Kotlin", "Mobile"]
keywords: "Android 17, Android 17 features, API 37, Android update, new Android APIs, platform changes, targetSdk"
faq:
  - q: "What is the API level for Android 17?"
    a: "Android 17 corresponds to API level 37. Bumping compileSdk to 37 lets you use the new APIs, but the behavior changes that affect your app only take effect once you raise targetSdk to 37."
  - q: "Do Android 17 behavior changes affect my app before I update targetSdk?"
    a: "Some do. A subset of platform changes apply to all apps regardless of targetSdk, while opt-in behavior changes only activate when you raise targetSdk to 37. Always read both lists in the official behavior-changes docs before shipping."
  - q: "What should I test first when targeting Android 17?"
    a: "Start with edge-to-edge and window insets, background/foreground service restrictions, and any large-screen or adaptive layout behavior. Those are the areas where recent Android releases have most often broken assumptions baked into older apps."
---

Every Android release lands in two buckets for a working developer: the shiny new APIs you *can* adopt, and the behavior changes that happen *to* you whether you like it or not the moment you bump `targetSdk`. Android 17 (API level 37) is no different, and the second bucket is the one that shows up as one-star reviews if you skip the release notes. This is a practitioner's read — what actually changes in day-to-day app work, what to test, and where the sharp edges are — rather than a marketing recap.

The single most important habit hasn't changed: **`compileSdk` unlocks the APIs, `targetSdk` opts you into the behavior.** You can compile against API 37 to use new capabilities while staying on an older `targetSdk`, but you don't inherit the mandatory behavior changes until you raise `targetSdk` to 37. Do that deliberately, with a test pass, not as a reflex.

## Adaptive layouts are now the baseline, not a bonus

The clearest through-line across recent releases and into Android 17 is that **adaptive UI is no longer optional**. Foldables, tablets, desktop windowing, and Chromebooks mean your app runs at sizes and aspect ratios you didn't design for, and the platform increasingly ignores orientation and resize restrictions on large screens. If your app still locks to portrait or assumes a phone-width layout, expect it to be letterboxed or stretched in ways users notice.

The fix is to design around window size classes rather than device types. In Compose that means driving layout from `WindowSizeClass` and using the adaptive navigation components — the same approach I detail in [adaptive layouts with Compose grids and flexbox thinking](https://blog.michaelsam94.com/adaptive-layouts-compose-grid-flexbox/). Treat "phone in portrait" as one configuration among many, not the default the rest degrade from.

```kotlin
val windowSizeClass = calculateWindowSizeClass(activity)
when (windowSizeClass.widthSizeClass) {
    WindowWidthSizeClass.Compact -> BottomNavScaffold()
    else -> NavigationRailScaffold() // tablets, foldables, desktop windows
}
```

## Edge-to-edge and insets, enforced harder

Recent releases pushed edge-to-edge rendering from opt-in to expected, and Android 17 continues tightening it. Apps that don't handle **window insets** correctly get content drawn under the status bar or navigation area. If you haven't already, stop assuming a fixed system bar height and consume insets explicitly. I covered the migration in detail in [edge-to-edge on Android 16](https://blog.michaelsam94.com/edge-to-edge-android-16/), and the guidance holds: use the insets APIs, test with gesture navigation and three-button navigation, and check the camera-cutout areas on real hardware.

## Background and foreground service limits keep tightening

The platform's long march toward battery discipline continues. Expect stricter enforcement around foreground service types, more aggressive limits on what an app can do while cached, and tighter windows for launching activities from the background. Practically, this means:

- Declare accurate **foreground service types** — a mismatch is increasingly a hard failure, not a warning.
- Move deferrable work to `WorkManager` rather than clinging to a service; it's the sanctioned path and it adapts to platform limits for you (see [WorkManager for reliable background work](https://blog.michaelsam94.com/workmanager-reliable-background-work/)).
- Re-test any "wake up and do something" flow — geofencing, sync, alarms — because the timing guarantees drift with each release.

## Privacy: less ambient access, more explicit intent

The privacy trajectory is consistent: give apps the narrowest data access that satisfies the user's intent. Expect more granular permissions, more use of system photo/media pickers instead of broad storage access, and continued nudging toward the Credential Manager and passkeys over bespoke auth. If your app still requests broad storage or location permissions it doesn't strictly need, Android 17 is a good forcing function to narrow them — users see the scope, and reviewers increasingly reject over-broad requests. This lines up with the broader [privacy engineering for mobile](https://blog.michaelsam94.com/privacy-engineering-mobile-gdpr/) direction the whole ecosystem is moving in.

## The compatibility checklist I run

When I take an app to a new `targetSdk`, I work through the same list before shipping:

| Area | What to verify |
| --- | --- |
| Insets / edge-to-edge | No content under system bars, both nav modes |
| Large screens | No forced-portrait letterboxing; multi-window resize works |
| Foreground services | Correct service types declared; no launch failures |
| Permissions | Runtime prompts appear; narrowed scopes still function |
| Predictive back | Back gesture animates and doesn't strand the user |
| 16 KB page sizes | Native libs (`.so`) aligned for devices using larger memory pages |

That last row bites teams with native code: as devices adopt larger memory page sizes, native libraries that assumed 4 KB alignment can fail to load. If you ship NDK code or depend on libraries that do, rebuild and test on a 16 KB device or emulator image.

## How to adopt it sanely

Don't chase the release the week it drops. My sequence:

1. Bump `compileSdk` to 37 and fix deprecations while staying on your current `targetSdk`. This is low-risk and lets you start using new APIs.
2. Read **both** behavior-change lists — the "all apps" one and the "targetSdk 37" one. Note what applies to you.
3. Test against an Android 17 device or emulator with your *current* build to catch the all-apps changes.
4. Raise `targetSdk` to 37 on a branch, run the checklist above, and ship behind a staged rollout so a regression hits 1% of users, not 100%.

Android releases reward teams that treat the upgrade as a small, tested project rather than a version-number bump. The APIs are worth adopting — adaptive UI and the privacy primitives genuinely make apps better — but the behavior changes are what protect your rating. Read the notes, run the checklist, roll out gradually.

## Resources

- [Android releases and platform overview](https://developer.android.com/about/versions)
- [Behavior changes: apps targeting the latest API](https://developer.android.com/about/versions/16/behavior-changes-16)
- [Support 16 KB page sizes](https://developer.android.com/guide/practices/page-sizes)
- [Window size classes and adaptive layouts](https://developer.android.com/develop/ui/compose/layouts/adaptive)
- [Foreground service types](https://developer.android.com/develop/background-work/services/fgs/service-types)
- [Display content edge-to-edge](https://developer.android.com/develop/ui/views/layout/edge-to-edge)
