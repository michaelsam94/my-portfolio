---
title: "Implementing In-App Updates on Android"
slug: "android-in-app-updates-api"
description: "Implement Android in-app updates with the Play Core API: choose flexible vs immediate flows, handle download and install states, and prompt users at the right time."
datePublished: "2024-06-28"
dateModified: "2024-06-28"
tags: ["Android", "Play Store", "App Updates", "UX"]
keywords: "in-app updates Android, AppUpdateManager, flexible update, immediate update, update priority, staleness, Play Core"
faq:
  - q: "What is the difference between flexible and immediate in-app updates?"
    a: "A flexible update downloads in the background while the user keeps using the app, then you prompt to restart and install when ready — good for optional improvements. An immediate update takes over the screen with a full-screen flow that blocks use until the update installs, appropriate only for critical fixes the user must take. Most apps should default to flexible and reserve immediate for genuinely breaking issues."
  - q: "How do I decide when to force an immediate update?"
    a: "Use the update priority you set at release time in the Play Console, combined with staleness (how many days the update has been available). A security fix or a change that breaks against your backend justifies high priority and an immediate flow. Everything else should be flexible so you don't interrupt users who are mid-task for a minor version bump."
  - q: "Do in-app updates replace publishing to the Play Store?"
    a: "No. In-app updates just surface an update that's already live on Play from inside your app, using Play's own download and install mechanism. You still publish normally; the API lets you nudge users who haven't auto-updated yet, which matters because a meaningful fraction of users have auto-update disabled or delayed."
---

In-app updates let you prompt a user to update to a version that's already live on Play — without making them find your listing, remember to check, or rely on auto-update being on. A surprising fraction of your install base has auto-update disabled or deferred on metered connections, which means old, buggy, sometimes insecure versions linger in the wild for weeks. The Play Core `AppUpdateManager` closes that gap: it checks whether a newer version is available, and drives either a background *flexible* download or a blocking *immediate* flow. Used with judgment, it dramatically shortens the tail of stale installs. Used badly, it nags users mid-task and tanks your ratings.

## Two flows, two very different UX contracts

- **Flexible** — the update downloads in the background while the user keeps working. When it's ready you show a subtle prompt ("Update ready — restart to apply"). Nothing is interrupted. This should be your default.
- **Immediate** — a full-screen, Play-owned UI takes over and the user cannot use the app until the update installs (or they back out and the app closes). This is a hammer. Reserve it for updates that genuinely must not be skipped: a security fix, or a client that will break against a changed backend.

The mistake I see most is defaulting to immediate "to be safe." That's user-hostile. Someone who opened your app to do one quick thing does not want a forced 20MB download first. Immediate is for the rare release where running the old version is actively harmful.

## Checking for an update

Everything starts with an `appUpdateInfo` check, which tells you availability, which flows are allowed, the priority you set at release, and staleness:

```kotlin
val manager = AppUpdateManagerFactory.create(context)

manager.appUpdateInfo.addOnSuccessListener { info ->
    val available = info.updateAvailability() == UpdateAvailability.UPDATE_AVAILABLE
    val priority = info.updatePriority()                 // 0..5, set at release
    val staleDays = info.clientVersionStalenessDays() ?: 0

    when {
        available && (priority >= 4 || staleDays >= 30) &&
            info.isUpdateTypeAllowed(AppUpdateType.IMMEDIATE) ->
                startImmediate(info)
        available && info.isUpdateTypeAllowed(AppUpdateType.FLEXIBLE) ->
                startFlexible(info)
    }
}
```

The decision logic — *when* to interrupt — is the part that actually matters, and it should be driven by data you control: the **update priority** you assign per release in the Play Console (via the Publishing API), and **staleness** in days. My rough policy: priority 4–5 or a version that's been out 30+ days can escalate to immediate; everything else is flexible; a brand-new low-priority update might not prompt at all on first sight.

## Driving the flexible flow

Flexible is the one you'll use 95% of the time. Start it, then observe install state so you can prompt for the restart:

```kotlin
private val listener = InstallStateUpdatedListener { state ->
    when (state.installStatus()) {
        InstallStatus.DOWNLOADING -> {
            val pct = state.bytesDownloaded() * 100 / state.totalBytesToDownload()
            // optionally show quiet progress
        }
        InstallStatus.DOWNLOADED -> showInstallSnackbar()   // prompt to restart
        InstallStatus.FAILED, InstallStatus.CANCELED -> { /* try again later */ }
    }
}

fun startFlexible(info: AppUpdateInfo) {
    manager.registerListener(listener)
    manager.startUpdateFlowForResult(
        info, AppUpdateType.FLEXIBLE, activity, REQ_UPDATE
    )
}

private fun showInstallSnackbar() {
    Snackbar.make(root, "Update ready", Snackbar.LENGTH_INDEFINITE)
        .setAction("Restart") { manager.completeUpdate() }   // installs on restart
        .show()
}
```

Two things people miss. First, after `DOWNLOADED`, nothing installs until you call `completeUpdate()`, which restarts the app — so you *must* surface a prompt or the downloaded update just sits there. Second, unregister the listener when done to avoid leaks. A persistent indefinite snackbar with a "Restart" action is the gold-standard UX: visible, non-blocking, user-controlled.

## Handling the immediate flow correctly

Immediate is simpler to start but has a critical resume requirement. If the user backgrounds the app mid-update, or the flow was already in progress when the activity restarts, you must resume it in `onResume` — otherwise you leave the app in a half-updated, unusable limbo:

```kotlin
override fun onResume() {
    super.onResume()
    manager.appUpdateInfo.addOnSuccessListener { info ->
        if (info.updateAvailability() ==
            UpdateAvailability.DEVELOPER_TRIGGERED_UPDATE_IN_PROGRESS) {
            manager.startUpdateFlowForResult(
                info, AppUpdateType.IMMEDIATE, activity, REQ_UPDATE
            )
        }
    }
}
```

Skip this and testers will report the immediate update "getting stuck" whenever they switch apps mid-flow.

## Where to trigger the check

Don't check on every cold start and prompt instantly — that trains users to reflexively dismiss. Better triggers:

- After the user completes a natural task (finished a purchase, closed a document), not on launch.
- On a cadence — check on start but only *prompt* if the update is high-priority or sufficiently stale.
- Never during onboarding or a first session; let people experience the app before you interrupt them.

This is the same restraint that makes the [in-app review prompt](https://blog.michaelsam94.com/android-in-app-review-api/) effective: timing and frequency decide whether these Play surfaces help or annoy. Both APIs reward patience and punish nagging.

## Test it for real

In-app updates only fully work through Play, so test with **internal app sharing** or an internal testing track — install an older version code, then push a newer one, and exercise both flows including the backgrounded-mid-update case. The `FakeAppUpdateManager` lets you unit-test the state transitions without Play. Don't ship this having only tested the happy path; the interesting bugs are all in the failure, cancellation, and resume states.

Done with restraint, in-app updates are one of the highest-leverage reliability features you can add: they shrink the population running old code, they get security fixes deployed faster, and — critically — they do it using Play's trusted, resumable install machinery rather than anything you have to build. Default to flexible, escalate to immediate only when the old version is genuinely dangerous, and time your prompts around the user's task, not your release schedule.

## Resources

- [Support in-app updates (Android)](https://developer.android.com/guide/playcore/in-app-updates)
- [Flexible and immediate update flows](https://developer.android.com/guide/playcore/in-app-updates/kotlin-java)
- [Set update priority (Publishing API)](https://developer.android.com/guide/playcore/in-app-updates#update-priority)
- [Test in-app updates](https://developer.android.com/guide/playcore/in-app-updates/test)
- [Play Core library overview](https://developer.android.com/guide/playcore)
