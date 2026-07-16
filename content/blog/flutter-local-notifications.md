---
title: "Local Notifications Across Platforms"
slug: "flutter-local-notifications"
description: "Schedule and display local notifications in Flutter with flutter_local_notifications: channels, permissions, foreground handling, and iOS/Android differences."
datePublished: "2024-12-24"
dateModified: "2024-12-24"
tags: ["Flutter", "Dart"]
keywords: "Flutter local notifications, flutter_local_notifications, notification channels Android, iOS notifications Flutter"
faq:
  - q: "How do I show local notifications in Flutter?"
    a: "Use flutter_local_notifications package: initialize with platform settings, request permissions on iOS and Android 13+, create notification channels on Android, then call show for immediate or zonedSchedule for timed notifications. Handle tap callbacks via onDidReceiveNotificationResponse to navigate to relevant screens."
  - q: "Why do Flutter notifications not appear on Android?"
    a: "Common causes: missing POST_NOTIFICATIONS permission on Android 13+, notification channel not created or set to IMPORTANCE_NONE, battery optimization killing scheduled alarms, or app in foreground without foreground notification display configured. Verify channel importance and test on physical device—not all emulators render notifications reliably."
  - q: "How do I schedule notifications in Flutter?"
    a: "Use zonedSchedule with tz package for timezone-aware scheduling, or periodically reschedule on app launch for recurring reminders. Android 12+ exact alarms require SCHEDULE_EXACT_ALARM permission. iOS requires user permission for alerts; provisional notifications available for quiet delivery."
---

Reminder notifications were the feature—except on Android 13 where nothing appeared because we never requested `POST_NOTIFICATIONS`, and on iOS where scheduled alarms fired an hour early because someone used `DateTime.now()` instead of timezone-aware `TZDateTime`. Local notifications touch permissions, channels, platform-specific initialization, and navigation on tap. One package (`flutter_local_notifications`) covers most cases; the platform differences still bite teams who only test one OS.

## Setup

```yaml
dependencies:
  flutter_local_notifications: ^17.2.3
  timezone: ^0.9.4
  flutter_timezone: ^3.0.1
```

Initialize in `main()`:

```dart
final notificationsPlugin = FlutterLocalNotificationsPlugin();

Future<void> initNotifications() async {
  const androidSettings = AndroidInitializationSettings('@mipmap/ic_launcher');
  const iosSettings = DarwinInitializationSettings(
    requestAlertPermission: false,
    requestBadgePermission: false,
    requestSoundPermission: false,
  );

  await notificationsPlugin.initialize(
    const InitializationSettings(
      android: androidSettings,
      iOS: iosSettings,
    ),
    onDidReceiveNotificationResponse: _onNotificationTap,
  );

  await _createAndroidChannels();
  await _requestPermissions();
}

void _onNotificationTap(NotificationResponse response) {
  final payload = response.payload;
  if (payload != null) {
    router.go('/reminders/$payload');
  }
}
```

## Android notification channels

Required since Android 8—users control channel settings:

```dart
Future<void> _createAndroidChannels() async {
  const channel = AndroidNotificationChannel(
    'reminders',
    'Reminders',
    description: 'Medication and task reminders',
    importance: Importance.high,
  );

  await notificationsPlugin
      .resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin>()
      ?.createNotificationChannel(channel);
}
```

Match `channel id` in every notification on that channel.

## Permissions

**Android 13+ (API 33):**

```xml
<!-- AndroidManifest.xml -->
<uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>
```

```dart
final android = notificationsPlugin.resolvePlatformSpecificImplementation<
    AndroidFlutterLocalNotificationsPlugin>();
await android?.requestNotificationsPermission();
```

**iOS:**

```dart
final ios = notificationsPlugin.resolvePlatformSpecificImplementation<
    IOSFlutterLocalNotificationsPlugin>();
await ios?.requestPermissions(alert: true, badge: true, sound: true);
```

Request contextually—after user creates first reminder, not on cold launch.

## Show immediate notification

```dart
Future<void> showReminderNotification({
  required int id,
  required String title,
  required String body,
  String? payload,
}) async {
  const details = NotificationDetails(
    android: AndroidNotificationDetails(
      'reminders',
      'Reminders',
      channelDescription: 'Task reminders',
      importance: Importance.high,
      priority: Priority.high,
    ),
    iOS: DarwinNotificationDetails(
      presentAlert: true,
      presentBadge: true,
      presentSound: true,
    ),
  );

  await notificationsPlugin.show(id, title, body, details, payload: payload);
}
```

Use stable integer IDs—same ID replaces previous notification.

## Scheduled notifications

Initialize timezone:

```dart
Future<void> initTimezone() async {
  tz.initializeTimeZones();
  final timezone = await FlutterTimezone.getLocalTimezone();
  tz.setLocalLocation(tz.getLocation(timezone));
}
```

Schedule:

```dart
Future<void> scheduleReminder({
  required int id,
  required String title,
  required String body,
  required DateTime scheduledAt,
}) async {
  await notificationsPlugin.zonedSchedule(
    id,
    title,
    body,
    tz.TZDateTime.from(scheduledAt, tz.local),
    const NotificationDetails(
      android: AndroidNotificationDetails('reminders', 'Reminders'),
      iOS: DarwinNotificationDetails(),
    ),
    androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
    uiLocalNotificationDateInterpretation:
        UILocalNotificationDateInterpretation.absoluteTime,
    payload: id.toString(),
  );
}
```

**Android exact alarms** — manifest permission for Android 12+:

```xml
<uses-permission android:name="android.permission.SCHEDULE_EXACT_ALARM"/>
```

Cancel/reschedule:

```dart
await notificationsPlugin.cancel(id);
await notificationsPlugin.cancelAll();
```

## Foreground notifications

When app is foreground, Android may suppress heads-up display. Show in-app banner or configure:

```dart
// Optionally use foreground service for critical ongoing notifications
```

For data sync completion while app open, prefer in-app SnackBar; reserve system notifications for background timing.

### Payload and deep linking

Pass route or entity ID in payload string:

```dart
payload: jsonEncode({'type': 'order', 'id': orderId}),
```

Parse in tap handler and navigate via go_router.

### Testing

- **Android:** physical device, verify channel in system settings.
- **iOS:** real device required for push-style permissions; simulator supports local notifications with limits.
- **Scheduled:** set 1-minute future schedule, background app, wait.

Log pending notifications:

```dart
final pending = await notificationsPlugin.pendingNotificationRequests();
debugPrint('Pending: ${pending.length}');
```

### flutter_local_notifications vs firebase_messaging

| Use case | Package |
|----------|---------|
| Local reminders, alarms | flutter_local_notifications |
| Server push | firebase_messaging |
| Both | Initialize both; FCM foreground handler may call local plugin |

Combine for push that schedules local follow-up reminders offline.

### Notification grouping on Android

Use groupKey for stacked notifications:

```dart
AndroidNotificationDetails(
  'orders', 'Orders',
  groupKey: 'com.example.orders',
  setAsGroupSummary: false,
)
```

Submit summary notification with setAsGroupSummary: true when batch completes—prevents notification shade spam from five separate order updates.

Android notification permission rationale screen before system prompt improves grant rates—users deny less when context explains value. iOS provisional authorization sends quiet notification center delivery without alert permission—good for low-priority re-engagement before asking full alert access.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

Schedule a quarterly review of this implementation against current SDK release notes—Flutter and cloud providers ship breaking changes on six-month cadences, and assumptions that held last year may need adjustment. Capture before-and-after metrics when you change configuration so regressions are obvious in retrospect rather than debated from memory.

Version-pin dependencies mentioned here in your pubspec.lock or infrastructure modules, and note the Flutter/Dart SDK constraint your team validated. Upgrading without re-running the verification steps in this article is the most common source of regressions. If something fails after an upgrade, compare release notes first, then your git history for the last known-good configuration.

Request notification permission in context, not at first launch — iOS denial rates spike when permission asked before value demonstration.

## Resources

- [flutter_local_notifications](https://pub.dev/packages/flutter_local_notifications)
- [Android notification channels](https://developer.android.com/develop/ui/views/notifications/channels)
- [Apple local notifications](https://developer.apple.com/documentation/usernotifications)
- [timezone package](https://pub.dev/packages/timezone)
- [Scheduling notifications readme](https://pub.dev/packages/flutter_local_notifications#scheduling-a-notification)
