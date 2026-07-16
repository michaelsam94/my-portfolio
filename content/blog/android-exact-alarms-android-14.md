---
title: "Exact Alarms After Android 14: What Actually Changed"
slug: "android-exact-alarms-android-14"
description: "SCHEDULE_EXACT_ALARM is no longer auto-granted on Android 14. Learn when you qualify for USE_EXACT_ALARM, how to request the permission, and cheaper alternatives."
datePublished: "2024-07-09"
dateModified: "2024-07-09"
tags: ["Android", "Kotlin", "AlarmManager", "Background Work"]
keywords: "exact alarms Android 14, SCHEDULE_EXACT_ALARM, USE_EXACT_ALARM, setExactAndAllowWhileIdle, canScheduleExactAlarms"
faq:
  - q: "Why did my exact alarms stop working on Android 14?"
    a: "On Android 14 (API 34), apps targeting 33+ no longer get SCHEDULE_EXACT_ALARM granted automatically at install. If you relied on that permission being present, canScheduleExactAlarms() now returns false and setExact* calls throw a SecurityException. You either need to qualify for the auto-granted USE_EXACT_ALARM permission or send the user to settings to grant SCHEDULE_EXACT_ALARM."
  - q: "What is the difference between USE_EXACT_ALARM and SCHEDULE_EXACT_ALARM?"
    a: "USE_EXACT_ALARM is auto-granted but restricted to apps whose core function is alarms, timers, or calendar events — Google Play will reject apps that use it without that justification. SCHEDULE_EXACT_ALARM is broader but on Android 13+ is a user-grantable permission you must request via a settings intent, and the user can revoke it. Pick USE_EXACT_ALARM only if you genuinely qualify."
  - q: "Do I need an exact alarm at all?"
    a: "Usually not. Most reminders and periodic sync tolerate a few minutes of drift, which means WorkManager or an inexact alarm is a better fit and avoids the permission entirely. Reserve exact alarms for user-facing time-critical events like an alarm clock, a countdown timer, or a calendar notification that must fire at a precise wall-clock moment."
---

If your reminders quietly stopped firing on time after an Android 14 update, the cause is almost certainly that `SCHEDULE_EXACT_ALARM` is no longer granted automatically. On Android 14 (API 34), apps that target API 33 or higher install *without* that permission, so `AlarmManager.canScheduleExactAlarms()` returns false and every `setExact*` call throws `SecurityException`. This is a deliberate tightening: exact alarms wake the device precisely and defeat batching, so Google made them opt-in.

The fix isn't "add the permission back." It's deciding whether you actually need an exact alarm, and if so, picking the correct permission for your app's category. Getting that wrong gets you either broken alarms or a Play Store rejection.

## First: do you even need exact?

Most scheduling does not need wall-clock precision. Before touching either permission, be honest about tolerance:

- **Periodic sync, cache refresh, upload retries** — use [WorkManager](https://blog.michaelsam94.com/android-doze-app-standby-buckets/). It's Doze-aware, survives reboots, and doesn't need any alarm permission.
- **Reminders that can drift a few minutes** — use `setAndAllowWhileIdle` (inexact). The system batches them for battery, which is fine for "water your plants" but not for "meeting in 5 minutes."
- **Alarm clock, timer, precise calendar event** — this is the genuine exact-alarm case.

If you land in the first two buckets, you're done and you never touch the permission. The teams that get burned are the ones that used exact alarms out of habit for things that tolerate drift.

## The two permissions, and which is yours

There are two permissions and choosing wrong is a real problem:

| Permission | Granted how | Allowed for | Revocable |
|---|---|---|---|
| `USE_EXACT_ALARM` | Auto-granted at install | Only alarm/timer/calendar apps | No |
| `SCHEDULE_EXACT_ALARM` | User grants via settings (API 33+) | General use | Yes |

`USE_EXACT_ALARM` is the convenient one — no runtime dance — but Google Play enforces a policy: if exact alarms are not a *core, user-facing feature* of your app, using it will get your submission rejected. An alarm clock, a cooking timer, a calendar app qualifies. A shopping app that wants a "sale starts now" ping does not.

Everyone else uses `SCHEDULE_EXACT_ALARM`, which on Android 13+ behaves like a special app-access setting the user must toggle.

## Requesting SCHEDULE_EXACT_ALARM properly

You can't request this one with the normal runtime permission dialog. You check the capability and, if missing, send the user to the system settings page:

```kotlin
val am = getSystemService(AlarmManager::class.java)

fun ensureExactAlarms(): Boolean {
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && !am.canScheduleExactAlarms()) {
        startActivity(
            Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM,
                   Uri.parse("package:$packageName"))
        )
        return false
    }
    return true
}
```

Two things people miss. First, always guard the actual scheduling call with `canScheduleExactAlarms()` because the user can revoke it at any time — and revocation resets pending exact alarms. Second, listen for `ACTION_SCHEDULE_EXACT_ALARM_PERMISSION_STATE_CHANGED`; when the permission is granted you should reschedule any alarms that got dropped while it was off.

## Scheduling that survives Doze

Even with permission, a plain `setExact` won't fire in Doze. The call you want for a time-critical event is `setExactAndAllowWhileIdle`, which pierces Doze for a single exact wakeup:

```kotlin
am.setExactAndAllowWhileIdle(
    AlarmManager.RTC_WAKEUP,
    triggerAtMillis,
    pendingIntent
)
```

For an alarm clock specifically, `setAlarmClock()` is even better — it shows the next-alarm icon in the status bar and gets the highest scheduling priority, at the cost of being very visible to the user. Use it for actual alarms, not background chores.

And remember alarms don't survive a reboot. Register a `BOOT_COMPLETED` receiver and re-arm anything pending, or a device restart silently drops every alarm you set.

## A migration checklist

When I moved a reminders feature onto Android 14, the sequence that worked:

1. Audit every `setExact*` call and reclassify each as truly-exact or drift-tolerant.
2. Move the drift-tolerant ones to WorkManager or inexact alarms — this shrank the exact-alarm surface to a handful of genuine cases.
3. For the survivors, add a `canScheduleExactAlarms()` gate and a graceful settings prompt with a clear explanation of why it's needed.
4. Add the boot receiver and the permission-state-changed receiver to re-arm alarms after reboot or re-grant.
5. Decide the permission: we did *not* qualify for `USE_EXACT_ALARM`, so we shipped `SCHEDULE_EXACT_ALARM` with an in-app rationale.

## What I'd take away

Android 14 made exact alarms a privilege you have to earn, and that's a good forcing function. Most of what teams scheduled as "exact" never needed to be — push it to WorkManager and the problem disappears. For the real time-critical cases, pick `USE_EXACT_ALARM` only if alarms are your app's core purpose, otherwise request `SCHEDULE_EXACT_ALARM` through the settings intent, always gate the scheduling call on the current permission state, use `setExactAndAllowWhileIdle` to pierce Doze, and re-arm after reboot. Do that and precise alarms keep working without a policy rejection or a battery complaint.

## Common production mistakes

Teams get exact alarms android 14 wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping exact alarms android 14 on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Resources

- [Schedule alarms (Android)](https://developer.android.com/develop/background-work/services/alarms/schedule)
- [Exact alarm permission behavior changes](https://developer.android.com/about/versions/14/changes/schedule-exact-alarms)
- [AlarmManager reference](https://developer.android.com/reference/android/app/AlarmManager)
- [Guide to background work](https://developer.android.com/develop/background-work/background-tasks)
- [WorkManager overview](https://developer.android.com/develop/background-work/background-tasks/persistent/getting-started)
