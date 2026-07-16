---
title: "Background Tasks with WorkManager in Flutter"
slug: "flutter-workmanager-background-tasks"
description: "workmanager schedules deferrable background work on Android and iOS within OS limits. Sync, uploads, and cleanup without killing battery."
datePublished: "2025-04-04"
dateModified: "2025-04-04"
tags: ["Flutter", "Dart", "Background", "Mobile"]
keywords: "workmanager Flutter, background tasks Flutter, Android WorkManager, iOS BGTaskScheduler, deferrable work mobile"
faq:
  - q: "Can WorkManager run code every minute?"
    a: "No. Mobile OS throttles background work for battery life. Android WorkManager honors constraints and minimum intervals; iOS BGTaskScheduler grants sparse execution windows. Design for eventual consistency, not real-time polling."
  - q: "WorkManager vs isolate vs foreground service?"
    a: "WorkManager for deferrable maintenance—sync, cleanup, retry uploads. Foreground service with notification for user-visible long tasks like music or navigation. Root isolate dies with app; background handlers are separate entry points with limits."
  - q: "Does workmanager work when app is killed?"
    a: "Android can restart app in background to run registered tasks meeting constraints. iOS is stricter—schedule BGAppRefreshTask via plugin mapping. Test on real devices; simulators lie about background behavior."
---

Users assumed "sync runs in background" meant instant. iOS gave us four execution windows per day if we were lucky. `workmanager` does not bypass OS policy—it wraps Android WorkManager and iOS background APIs so Dart code registers tasks with constraints instead of hacking raw platform channels.

## Setup

```yaml
dependencies:
  workmanager: ^0.5.2
```

Initialize in `main`:

```dart
@pragma('vm:entry-point')
void callbackDispatcher() {
  Workmanager().executeTask((task, inputData) async {
    WidgetsFlutterBinding.ensureInitialized();
    switch (task) {
      case 'syncInbox':
        await SyncService.run();
        return true;
      default:
        return false;
    }
  });
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Workmanager().initialize(callbackDispatcher);
  runApp(const MyApp());
}
```

`@pragma('vm:entry-point')` prevents tree shaking from removing the entry point.

## Registering periodic work

```dart
await Workmanager().registerPeriodicTask(
  'inbox-sync',
  'syncInbox',
  frequency: const Duration(hours: 6),
  constraints: Constraints(
    networkType: NetworkType.connected,
    requiresBatteryNotLow: true,
  ),
  existingWorkPolicy: ExistingWorkPolicy.keep,
);
```

`frequency` is a minimum—OS may delay further. Do not schedule aggressive intervals.

## One-off tasks

```dart
await Workmanager().registerOneOffTask(
  'upload-retry-${uploadId}',
  'retryUpload',
  inputData: {'uploadId': uploadId},
  constraints: Constraints(networkType: NetworkType.unmetered),
);
```

Retry failed uploads when on Wi-Fi.

## iOS configuration

Add to `Info.plist`:

```xml
<key>UIBackgroundModes</key>
<array>
  <string>fetch</string>
  <string>processing</string>
</array>
```

Register BGTask identifiers per plugin docs. Apple review rejects apps declaring background modes without legitimate use—document sync behavior in review notes.

## Android configuration

WorkManager handles most Android versions. For expedited work on Android 12+, check plugin support for `setExpedited` equivalents when user expects near-immediate retry after they tap "Retry later."

Avoid duplicate work IDs—use `ExistingWorkPolicy.replace` when updating schedules.

## What belongs in background tasks

Good:

- Incremental inbox sync
- Cache pruning
- Analytics batch upload
- Prefetch non-critical content

Bad:

- Real-time chat delivery (use FCM)
- GPS tracking (foreground service)
- UI updates (impossible from background isolate)

Keep tasks idempotent—OS may retry.

## Debugging

```dart
Workmanager().registerOneOffTask(
  'debug-sync',
  'syncInbox',
  initialDelay: const Duration(seconds: 10),
);
```

Use Android `adb shell cmd jobscheduler` and iOS Xcode background task debugger. Log start/end to remote logging with task name.

## Alternatives

- **firebase_messaging** data messages for server-triggered wake
- **background_fetch** for iOS-specific patterns
- **android_alarm_manager_plus** for time-critical Android alarms (strict API limits)

Pick WorkManager when you need cross-platform deferrable work with constraint API.

## Input data limits

Pass small `inputData` maps—large payloads belong in local DB keyed by ID referenced from inputData.

## Battery-aware constraints

```dart
constraints: Constraints(
  requiresBatteryNotLow: true,
  requiresStorageNotLow: true,
),
```

Respect user battery saver mode—sync can wait.

## Debugging iOS background

Xcode → Debug → Simulate Background Fetch. Log task execution to os_log with subsystem filter in Console.app.

## Duplicate registration

Calling `registerPeriodicTask` with same uniqueName replaces schedule—document uniqueName scheme (`sync-inbox-v2`) when changing task logic.


## Coordinating with FCM and foreground work

Background handlers and FCM data messages overlap—pick one owner per sync pipeline. If FCM wakes the app for high-priority inbox sync, WorkManager handles retry when FCM delivery fails or device is offline for hours. Document the matrix in your runbook so on-call engineers know which subsystem should have run.

Foreground services on Android remain appropriate for user-visible long uploads—WorkManager tasks get killed without notification on some OEM skins if they exceed time limits. Split large uploads into chunked WorkManager jobs with progress persisted in SQLite so retry resumes mid-file.

## Observability

Log structured fields from the background entry point: task name, attempt count, inputData keys (never secrets), duration_ms, outcome. Ship logs to your backend on debug builds only; production should aggregate success/failure rates per task type in analytics.

Correlate WorkManager execution with user reports of stale data—if sync task success rate drops under 95% on a specific OEM, investigate battery optimization whitelisting flows in app settings.

## User-facing settings

Expose "Background sync" toggle wired to canceling periodic tasks and skipping registration on next launch. GDPR and platform policies increasingly expect user control over background network activity—honor system battery saver by checking `BatteryState` before expensive sync if not already enforced by constraints.

## Testing checklist before release

- Register task, kill app, verify execution on physical Android device (not emulator-only)
- iOS: simulate background fetch, verify BGTask identifier matches Info.plist
- Upgrade path: app update does not duplicate periodic registrations
- Logout clears scheduled tasks: `Workmanager().cancelAll()`

## Expedited work

Android expedited jobs quota limited—use for user-tapped Retry Now only, not bulk sync; exhaust quota and WorkManager degrades to normal priority silently.

## Rollout guidance

Background sync policy changes communicated release notes when frequency or constraints tightened—users noticing stale data submit reviews; proactive note reduces one-star accusations app broken when OS throttling working as designed.

## Team practices

Shipping Flutter Workmanager Background Tasks in production taught our team that documentation beats hero demos. We wrote runbooks covering failure modes, on-call steps, and rollback triggers before the second release, not after the first outage.

When reviewing PRs touching Flutter Workmanager Background Tasks, we ask for measurable outcomes: latency, crash rate, or support ticket volume—not subjective feels faster. If metrics are unavailable, the PR includes a DevTools trace or load test snippet proving the change.

Onboarding engineers paste a checklist into their first Flutter Workmanager Background Tasks PR description: environment setup verified, tests added or updated, accessibility spot-checked, and release notes drafted for user-visible changes.

We keep a living FAQ in the repo wiki for Flutter Workmanager Background Tasks questions repeated in Slack more than twice. FAQ entries link to source files and Slack threads, reducing tribal knowledge and repeated explanations in code review.

## Resources

- [workmanager package](https://pub.dev/packages/workmanager)
- [Android WorkManager guide](https://developer.android.com/develop/background-work/background-tasks/persistent/getting-started)
- [iOS BGTaskScheduler](https://developer.apple.com/documentation/backgroundtasks)
- [Flutter background execution limits](https://docs.flutter.dev/packages-and-plugins/background-processes)
- [Doze and App Standby (Android)](https://developer.android.com/training/monitoring-device-state/doze-standby)
