---
title: "Doze, App Standby, and Battery Buckets Explained"
slug: "android-doze-app-standby-buckets"
description: "How Doze mode and App Standby buckets throttle background work on Android, what each restriction bucket allows, and how to design sync that survives them."
datePublished: "2024-07-10"
dateModified: "2024-07-10"
tags: ["Android", "Kotlin", "Background Work", "Performance"]
keywords: "Doze mode, App Standby buckets, Android battery optimization, background restrictions, WorkManager Doze"
faq:
  - q: "What is the difference between Doze and App Standby?"
    a: "Doze is device-wide: when the screen is off and the device is stationary and unplugged, the whole system enters low-power windows that defer background work and network access for every app. App Standby is per-app: the system sorts each app into a usage bucket and throttles that specific app's jobs and alarms based on how recently the user interacted with it. Doze is about the device state, buckets are about the individual app."
  - q: "How do I test Doze mode during development?"
    a: "Use adb to force it. Run 'adb shell dumpsys deviceidle force-idle' to push the device into Doze and 'adb shell dumpsys deviceidle unforce' to leave it. For App Standby, 'adb shell am set-standby-bucket <package> restricted' lets you simulate the worst bucket. Testing against forced Doze catches the deferred-work bugs that never appear on a plugged-in test device."
  - q: "Does WorkManager work during Doze?"
    a: "Yes — WorkManager schedules through JobScheduler, which is Doze-aware, so your work runs during the periodic maintenance windows rather than being dropped. It won't run at an exact instant during a deep Doze period, but it will run, and it respects constraints like network and charging. For anything that tolerates a delay, WorkManager is the right tool precisely because it cooperates with Doze instead of fighting it."
---

If your background sync works perfectly in testing and then users complain it "stops overnight," you've met Doze. Doze mode and App Standby are Android's two battery-saving mechanisms that throttle background work, and they operate on different axes: Doze restricts *the whole device* when it's idle, while App Standby restricts *individual apps* based on how often they're used. Understanding both is the difference between sync that quietly degrades and sync you can reason about.

I've spent real time chasing "it only fails on the user's device" bugs that all traced back to these systems. Once you internalize the model, they stop being mysterious and start being a spec you design against.

## Doze: the device goes to sleep

When a device is unplugged, screen off, and stationary for a while, it enters Doze. In Doze the system batches deferred work into periodic **maintenance windows** that grow further apart the longer the device stays idle — a few minutes at first, then tens of minutes, then hours. Between windows:

- Network access is suspended for background apps.
- Wakelocks are ignored.
- Standard `AlarmManager` alarms are deferred to the next window.
- Jobs and syncs are deferred.

There's also a lighter "Doze on the go" that kicks in when the device is moving (in a pocket) but the screen is off — same idea, shallower restrictions. The mental model: the device isn't dead, it's checking its inbox on a schedule that gets lazier the longer nobody touches it.

The escape hatches are deliberately narrow. High-priority FCM messages still get through for genuinely time-sensitive pushes. `setExactAndAllowWhileIdle` and `setAndAllowWhileIdle` can fire during Doze but are rate-limited. Foreground services are exempt while running. Everything else waits for a maintenance window.

## App Standby: per-app buckets

Doze is about the device; App Standby is about *your app specifically*. The system continuously sorts each app into a bucket based on recency and frequency of use, and the bucket determines how aggressively that app's jobs and alarms are throttled:

| Bucket | Roughly means | Job/alarm treatment |
|---|---|---|
| Active | In use right now | No restrictions |
| Working set | Used regularly | Mild deferral |
| Frequent | Used often, not daily | More deferral, capped |
| Rare | Rarely used | Heavy deferral, strict caps |
| Restricted | Misbehaving / almost never used | Once-a-day job window, tight limits |

The `restricted` bucket is the one that hurts: an app there might get a single job execution window every 24 hours. Apps land there by being ignored by the user *or* by triggering the system's abuse heuristics (excessive wakeups, long background wakelocks). The lesson is that being a good background citizen literally keeps you in a better bucket.

## Why your alarms drift

Combine the two and the behavior falls out. A plain periodic alarm on a rarely-used app, on a device deep in Doze, can be delayed by hours — Doze defers it to a maintenance window, and the app's bucket caps how often those windows serve it. This is exactly why [exact alarms on Android 14](https://blog.michaelsam94.com/android-exact-alarms-android-14/) require a special permission: piercing this system is a privilege, not a default.

## Designing work that survives

The practical playbook I follow:

1. **Use WorkManager for anything that tolerates delay.** It schedules through JobScheduler, which is Doze- and bucket-aware, so your work runs in maintenance windows instead of being silently dropped. Add constraints (`NetworkType.CONNECTED`, `requiresCharging`) and let the system pick a good moment.
2. **Use high-priority FCM for time-sensitive delivery.** If the user must know *now* (a message, a ride request), don't try to poll through Doze — push it. A high-priority data message wakes the app briefly even in Doze.
3. **Reserve exact alarms for wall-clock events.** Alarm clocks and countdowns, not sync.
4. **Batch and coalesce.** Fewer, larger wakeups keep you out of the abuse heuristics and out of the `restricted` bucket.
5. **Don't beg for exemptions.** `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` exists but Play restricts it to narrow categories, and users distrust it. Design to cooperate instead.

## Testing it for real

You cannot find these bugs on a plugged-in emulator, because charging disables Doze. Force the states with adb:

```bash
# Simulate Doze
adb shell dumpsys deviceidle force-idle
adb shell dumpsys deviceidle unforce

# Force the worst App Standby bucket
adb shell am set-standby-bucket com.your.app restricted
adb shell am get-standby-bucket com.your.app
```

Run your sync flow under forced Doze and the `restricted` bucket, and watch what actually executes. Every serious background bug I've shipped a fix for was reproducible this way and invisible without it.

## What I'd take away

Doze throttles the whole device when it's idle; App Standby throttles your app based on how much the user actually uses it — and they compound. Stop trying to run background work on your own schedule and start cooperating: WorkManager for deferrable jobs, high-priority FCM for truly urgent delivery, exact alarms only for wall-clock events, and batching to stay out of the penalty buckets. Then test against forced Doze and a `restricted` bucket before you ship, because that's the environment a real user's phone lives in overnight.

Log `UsageStatsManager.getAppStandbyBucket()` in beta builds — users in `restricted` bucket are your canary for background sync failures.

Document expected background behavior per standby bucket in your app's troubleshooting guide — support teams otherwise escalate "notifications stopped" as bugs when Android is working as designed.

## Requesting bucket exemption (rarely granted)

`REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` triggers Play policy scrutiny — only for user-visible core use cases (VoIP, active navigation). Agent sync apps should use WorkManager with expedited work sparingly, not whitelist requests.

## Testing bucket transitions

```bash
adb shell am set-standby-bucket com.example.app rare
adb shell cmd jobscheduler run -f com.example.app JOB_ID
```

Verify sync resumes when user opens app (bucket promotion to active). Document expected delay in UX for background-only users.

## Doze App Standby Buckets Supplement 0 on Samsung and Pixel divergence

Exercise doze app standby buckets supplement 0 on Galaxy A-series and Pixel a-series — emulators hide OEM battery and storage quirks. Capture Macrobenchmark or Firebase trace for the critical path touching doze; regressions above 8% block release for `android-doze-app-standby-buckets-supplement-0`.

Document permission and background behavior in internal runbook: what breaks under Doze, what requires foreground service, and what Play policy declarations apply. Support tickets referencing "Doze App Standby Buckets Supplement 0" should map to a single runbook section with known workarounds.

## Buckets regression gates for Play Vitals

Before promoting `android-doze-app-standby-buckets-supplement-0` changes past 20% rollout, compare ANR rate, slow cold start, and excessive wakeups against seven-day baseline. Fail rollback review if 0 path shows >5% increase in `slow frames` without documented trade-off approval.

## Field testing doze with battery saver enabled

Xiaomi and Oppo ship aggressive background killers. After implementing doze app standby buckets supplement 0, run 24-hour monkey test on three OEM devices with battery saver enabled. Failures here predict one-star reviews that Crashlytics never captures — especially for 0 flows that assume reliable background delivery.

## Resources

- [Optimize for Doze and App Standby](https://developer.android.com/training/monitoring-device-state/doze-standby)
- [App Standby buckets](https://developer.android.com/topic/performance/appstandby)
- [Background work overview](https://developer.android.com/develop/background-work/background-tasks)
- [WorkManager getting started](https://developer.android.com/develop/background-work/background-tasks/persistent/getting-started)
- [Power management restrictions](https://developer.android.com/topic/performance/power/power-details)
