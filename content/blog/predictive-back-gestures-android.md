---
title: "Predictive Back Gestures: Getting Them Right"
slug: "predictive-back-gestures-android"
description: "A practical guide to Android predictive back gestures: migrating off onBackPressed, using OnBackPressedCallback, and wiring the predictive animation in Compose."
datePublished: "2026-04-03"
dateModified: "2026-07-17"
tags: ["Android", "Jetpack Compose", "Navigation", "UX"]
keywords: "predictive back, Android back gesture, predictive back Compose, back navigation, onBackPressed, OnBackPressedCallback"
faq:
  - q: "What is predictive back on Android?"
    a: "Predictive back is a gesture where a back-swipe shows a preview of where the user is heading — the home screen, the previous app, or the previous screen — before they commit. It requires apps to declare support and to route back handling through the AndroidX back APIs rather than the deprecated onBackPressed."
  - q: "Why is onBackPressed deprecated?"
    a: "onBackPressed can't participate in the predictive animation because it only fires after the gesture commits, with no progress callbacks. The replacement, OnBackPressedCallback via the OnBackPressedDispatcher, exposes start, progress, and cancel events so the system can animate a preview."
  - q: "How do I support predictive back in Jetpack Compose?"
    a: "Use PredictiveBackHandler, which gives you a Flow of back-gesture progress events. You animate your UI as progress advances, then commit on completion or revert on cancel. Navigation libraries that are predictive-back-aware wire much of this for you."
---

Predictive back is one of those platform changes that's easy to ignore until it isn't. The system now wants to show users a preview of where a back-swipe will take them — peeking the home screen, the previous app, or your previous in-app screen — before the gesture commits. To participate, your app has to declare support and route all back handling through the AndroidX back APIs. If you're still calling `onBackPressed()`, predictive back either does nothing or looks broken. This is a guide to getting it right, including the Compose-native `PredictiveBackHandler`.

I migrated a fairly large app off `onBackPressed` for predictive back, and the surprising part wasn't the animation — it was how much stale back-handling logic the migration surfaced. Doing it properly cleaned up a category of navigation bugs I'd been living with.

## Why the old way can't work

`Activity.onBackPressed()` fires exactly once, at the moment the user commits the back action. There's no "the user started swiping and is 40% through" signal, and no "they let go, cancel it." Predictive back needs all three — start, progress, cancel/commit — so it can animate a preview that tracks the user's finger and springs back if they change their mind. That's structurally impossible with a single terminal callback, which is why `onBackPressed` is deprecated.

The replacement is the `OnBackPressedDispatcher` and `OnBackPressedCallback`, which have been around since well before predictive back but are now the *only* way to handle back correctly. Predictive back builds on their newer progress-aware callbacks.

## Step one: declare support and migrate callbacks

First, opt in via the manifest (needed on the OS versions where it's still gated):

```xml
<application
    android:enableOnBackInvokedCallback="true"
    ... >
```

Then replace any `onBackPressed` overrides with a callback registered on the dispatcher. In a View-based screen:

```kotlin
val callback = object : OnBackPressedCallback(enabled = true) {
    override fun handleOnBackPressed() {
        // commit: e.g. close the sheet, pop the screen
    }
    override fun handleOnBackProgressed(event: BackEventCompat) {
        // 0f..1f progress — drive a preview animation
    }
    override fun handleOnBackCancelled() {
        // user let go early — revert
    }
}
onBackPressedDispatcher.addCallback(this, callback)
```

The key habit: toggle `callback.isEnabled` based on whether this screen *should* intercept back right now. An always-enabled callback that no longer applies is how you get "back button does nothing" bugs. Enable it only when there's genuinely custom back behavior to run.

## Compose: PredictiveBackHandler

In Compose you rarely touch the dispatcher directly. For simple interception, `BackHandler` still works and is now predictive-back compatible. For the interesting case — animating a preview as the user swipes — reach for `PredictiveBackHandler`, which hands you a `Flow` of progress:

```kotlin
@Composable
fun DismissibleSheet(onDismiss: () -> Unit, content: @Composable () -> Unit) {
    var offset by remember { mutableFloatStateOf(0f) }

    PredictiveBackHandler(enabled = true) { progress: Flow<BackEventCompat> ->
        try {
            progress.collect { event ->
                // event.progress is 0f..1f — scale/translate the sheet
                offset = event.progress * 300f
            }
            onDismiss()          // flow completed = gesture committed
        } catch (e: CancellationException) {
            offset = 0f          // flow cancelled = gesture aborted
        }
    }

    Box(Modifier.offset { IntOffset(0, offset.roundToInt()) }) { content() }
}
```

The pattern is elegant once it clicks: the `try` body runs as the user drags, completing the `Flow` means they committed (so you finish the action), and a `CancellationException` means they let go early (so you revert). No manual start/progress/cancel bookkeeping — structured concurrency handles it, which fits the [coroutines and Flow patterns](https://blog.michaelsam94.com/kotlin-coroutines-flow-patterns/) that already run through Compose.

## Let navigation do the heavy lifting

For screen-to-screen back — the most common case — you usually shouldn't hand-roll the animation at all. Predictive-back-aware navigation handles the cross-screen preview for you, showing the previous destination peeking in as the user swipes. The current generation of Compose navigation, including [Navigation 3](https://blog.michaelsam94.com/navigation-3-jetpack-compose/), is built with this in mind. Your job is mostly to stop fighting it: don't intercept back with a stale callback, keep your back stack honest, and let the nav layer animate transitions.

Where you *do* write custom predictive back is for in-screen dismissals — bottom sheets, expanded cards, search overlays, media viewers — anything that isn't a full navigation pop but should still respond to back with a preview.

## The failure modes to watch

| Symptom | Usual cause |
| --- | --- |
| Back does nothing | An always-enabled callback intercepting with empty logic |
| No preview animation | Still using onBackPressed, or callback lacks progress handling |
| Preview then wrong screen | Back stack out of sync with what the UI shows |
| Janky preview | Heavy work on the main thread during the gesture |
| Double dismiss | Both a callback and navigation handling the same back |

That last one is common when you migrate incrementally: two handlers both fire. Audit your dispatcher registrations and make sure exactly one owns any given back event.

Predictive back is a small feature with an outsized effect on how *finished* an app feels — the peek at the home screen or the previous screen removes the "did I just lose my place?" anxiety. It also forces a healthy discipline: back handling becomes explicit, enabled per state, and centralized in navigation rather than scattered across `onBackPressed` overrides. That cleanup is worth doing even if you didn't care about the animation.

## androidx.activity enablement

enableEdgeToEdge and OnBackPressedDispatcher callback for predictive animation. Predictive back requires Android 13+ with developer option or Android 14+ default.

## Custom animation contract

System scrim reveals previous destination — fragment transitions must not fight system animator. Use BackEvent progress 0.0–1.0 to scrub shared element animation.

## Navigation component integration

NavHost with predictive back needs consistent back stack — deep links pushing duplicate entries break predictive preview.

## Testing with gesture nav

Emulator with gesture navigation; UiAutomator swipe from left edge. Verify no crash when back stack empty.

## Material 3 predictive back scrim

Material components handle scrim opacity when using enableEdgeToEdge — custom Compose screens must animate background reveal manually or use androidx.compose.material3 AdaptiveBackHandler APIs on Android 14.

## Fragment transition compatibility

android:enableOnBackInvokedCallback in manifest for Android 13+. Older FragmentManager popBackStackImmediate fights predictive animation — migrate to Navigation Component 2.7+.

## Compose predictive back

androidx.compose.ui PredictiveBackHandler intercepts back before system animation — use when custom scaffold overlays standard Activity back. Test on Pixel with gesture nav enabled in system settings.

## Analytics for back gesture completion

Track back gesture started vs completed vs cancelled — high cancel rate on payment screen may indicate accidental edge swipe; adjust touchable region or require confirmation on destructive back from checkout.

## androidx.activity 1.8+ APIs

ProgressProviderRegistry registers custom cross-activity animations — needed when single-activity Compose app still uses Activity boundaries for SDK integrations. Test predictive back across Activity hop when third-party SDK starts separate Activity for payment.

## User education for gesture nav

In-app tooltip first launch after Android 14 upgrade explains edge swipe — support tickets drop when predictive preview shows destination user did not expect accidental back from checkout WebView.

## WindowInsets and predictive back

Edge-to-edge plus predictive back requires handling WindowInsets on bottom nav — animation reveals previous content behind gesture; insets not updated causes layout jump when gesture completes.

## Resources

- [Predictive back gesture guide](https://developer.android.com/guide/navigation/custom-back/predictive-back-gesture)
- [PredictiveBackHandler in Compose](https://developer.android.com/develop/ui/compose/system/predictive-back)
- [OnBackPressedDispatcher](https://developer.android.com/reference/androidx/activity/OnBackPressedDispatcher)
- [Add support for the predictive back gesture](https://developer.android.com/guide/navigation/custom-back/predictive-back-gesture#opt-predictive)
- [Android developers blog](https://android-developers.googleblog.com/)
- [Jetpack Compose navigation](https://developer.android.com/jetpack/compose/navigation)

*Modernizing navigation and back handling in a large Android app? [Get in touch](https://michaelsam94.com/).*
