---
title: "Handling the Notification Runtime Permission on Android"
slug: "android-notification-runtime-permission"
description: "How to request POST_NOTIFICATIONS on Android 13+ without wrecking opt-in rates: timing, rationale UI, targeting behavior, and the pre-33 fallback that trips teams up."
datePublished: "2024-07-08"
dateModified: "2024-07-08"
tags: ["Android", "Kotlin", "Permissions", "Notifications"]
keywords: "POST_NOTIFICATIONS, notification runtime permission, Android 13 notifications, notification opt-in, shouldShowRequestPermissionRationale"
faq:
  - q: "Do I need POST_NOTIFICATIONS if my app targets below API 33?"
    a: "You still need to handle it, but the system prompts differently. If your app targets below 33 and runs on Android 13+, the OS shows the permission dialog itself the first time you create a notification channel or post a notification. You get less control over timing, so targeting 33+ and requesting deliberately is almost always the better experience."
  - q: "Why do my notifications silently fail on Android 13?"
    a: "Because the user never granted POST_NOTIFICATIONS, or explicitly denied it, and your code posts anyway. NotificationManagerCompat.areNotificationsEnabled() returns false in that state and the post is dropped with no exception. Always check that flag before relying on a notification, and treat a denial as a real product state, not an error."
  - q: "Can I re-ask for the notification permission after a denial?"
    a: "Once the user denies twice (or picks deny on the one-time system dialog), Android stops showing the system prompt entirely and shouldShowRequestPermissionRationale returns false. At that point your only path is a custom screen that deep-links into system notification settings; you cannot force the OS dialog to reappear."
---

The notification runtime permission is the single easiest way to tank your re-engagement metrics, and most teams do it by asking on the first launch screen before the user knows what the app even does. Since Android 13 (API 33), `POST_NOTIFICATIONS` is a runtime permission like camera or location — you have to request it, the user can say no, and once they've said no twice you don't get another system prompt. Treating it as a throwaway checkbox is how you end up with 30% opt-in when you could have 70%.

I've shipped this migration on a couple of production apps, and the mechanics are simple. What's hard is the product judgment around *when* you ask and *what you do* when the answer is no.

## The runtime request itself

Declare the permission in your manifest and request it through the standard Activity Result API. Nothing exotic here:

```kotlin
private val requestPermission = registerForActivityResult(
    ActivityResultContracts.RequestPermission()
) { granted ->
    if (granted) enableRichNotifications()
    else recordDenial()
}

fun askForNotifications() {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
    when {
        ContextCompat.checkSelfPermission(this, POST_NOTIFICATIONS) == PERMISSION_GRANTED ->
            enableRichNotifications()
        shouldShowRequestPermissionRationale(POST_NOTIFICATIONS) ->
            showRationaleSheet()   // explain, then launch on confirm
        else ->
            requestPermission.launch(POST_NOTIFICATIONS)
    }
}
```

The `Build.VERSION` guard matters: on Android 12 and below the permission doesn't exist, notifications are on by default, and calling this path is meaningless. Gate everything on `TIRAMISU`.

## The targeting trap nobody reads about

Here's the part that surprises people. What happens on an Android 13 device depends on your `targetSdkVersion`:

- **Target 33+:** the system *never* prompts on its own. You are fully responsible for calling `requestPermission`. If you forget, your app can post notifications forever and none of them ever show, because nobody was ever asked.
- **Target below 33:** the OS shows its own dialog the first time you create a notification channel or post a notification. You get free prompting, but at a moment you didn't choose — often mid-onboarding, which is the worst possible time.

Neither default is what you want. The right move is to bump your target to 33+ and control the timing yourself. Relying on the pre-33 automatic dialog just means the system asks at a random moment and you eat the low conversion.

## Ask in context, never on launch

The biggest lever on opt-in rate is *when* you ask. A cold prompt on first launch, before any value has been delivered, is a reflexive "no." Ask at the moment the notification is obviously useful:

1. A chat app asks right after the user sends their first message ("want a ping when they reply?").
2. A delivery app asks after an order is placed, not during signup.
3. A finance app asks when the user sets up an alert, tying the permission to a feature they just opted into.

The pattern is the same one I use for [any sensitive Android permission](https://blog.michaelsam94.com/android-notification-runtime-permission/): pair the request with a self-explaining action so the system dialog confirms a decision the user has already mentally made.

## Rationale, and the point of no return

`shouldShowRequestPermissionRationale` returns true only in a narrow window — after one denial but before the second. Use it to show a short custom sheet explaining what you'll send *before* re-launching the system dialog. Keep it honest and specific ("shipping updates and delivery alerts," not "important news").

Once the user denies the second time, the state is terminal from your code's perspective:

- `shouldShowRequestPermissionRationale` returns false.
- `requestPermission.launch()` returns immediately with a denial and no dialog appears.

At that point you cannot re-summon the OS prompt. Your only recourse is a custom in-app screen that deep-links to the app's notification settings:

```kotlin
val intent = Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).apply {
    putExtra(Settings.EXTRA_APP_PACKAGE, packageName)
}
startActivity(intent)
```

Don't nag toward this. Surface it gently the next time the user tries to enable a feature that depends on notifications, so the ask is still contextual.

## Always check before you post

Independent of the permission flow, a granted permission can still be revoked, and channels can be disabled individually. Before you rely on a notification for anything important, check:

```kotlin
val enabled = NotificationManagerCompat.from(context).areNotificationsEnabled()
```

If notifications are off, a posted notification is silently dropped — no exception, no callback. For genuinely critical flows (a security code, a driver's next pickup), you need a fallback path that doesn't assume the notification landed. I've debugged more than one "the notification never arrived" ticket that turned out to be a disabled channel, not a delivery bug.

## Channels still matter

The runtime permission gates whether you can post *at all*; notification channels still govern *how* each category behaves once you can. Create your channels early (they're cheap and idempotent), give each a clear user-facing name, and let users mute a category they dislike instead of revoking the whole permission. A well-segmented set of channels is your insurance against an all-or-nothing opt-out — a user who'd disable everything might just mute "promotions" and keep "order updates."

## What I'd take away

Bump your target to 33+ so *you* decide when the prompt appears, and then ask in context, right after the user does something that makes the notification obviously valuable. Use the rationale window for a short, specific explanation, and accept that a second denial is final — route those users to a settings deep-link instead of trying to force the dialog. Check `areNotificationsEnabled()` before trusting any critical notification, and lean on channels so users can mute categories instead of nuking the whole permission. Get the timing right and opt-in stops being a compliance checkbox and becomes a real product win.

## Resources

- [Notification runtime permission (Android)](https://developer.android.com/develop/ui/views/notifications/notification-permission)
- [Request runtime permissions](https://developer.android.com/training/permissions/requesting)
- [Create and manage notification channels](https://developer.android.com/develop/ui/views/notifications/channels)
- [NotificationManagerCompat reference](https://developer.android.com/reference/androidx/core/app/NotificationManagerCompat)
- [Activity Result APIs](https://developer.android.com/training/basics/intents/result)
