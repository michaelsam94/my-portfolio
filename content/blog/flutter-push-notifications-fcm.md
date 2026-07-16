---
title: "Push Notifications with FCM in Flutter"
slug: "flutter-push-notifications-fcm"
description: "Firebase Cloud Messaging in Flutter covers foreground, background, and terminated states. Token management, channels on Android, and deep link routing."
datePublished: "2025-02-09"
dateModified: "2025-02-09"
tags: ["Flutter", "Dart", "Firebase", "Mobile"]
keywords: "FCM Flutter, Firebase push notifications, flutter firebase_messaging, notification deep link, Android notification channel"
faq:
  - q: "Why do notifications work in foreground but not when the app is killed?"
    a: "Background and terminated delivery require platform setup: iOS notification capabilities and APNs key in Firebase, Android default notification channel and high-priority data messages handled in a top-level background handler. Missing any piece silently drops notifications."
  - q: "Should I use data messages or notification messages?"
    a: "Notification messages are displayed by the system when the app is backgrounded—simple but less control. Data messages deliver payload to your code always—required for custom routing and silent sync. Many apps send both: notification for display, data for routing metadata."
  - q: "How do I get a reliable FCM token?"
    a: "Call FirebaseMessaging.instance.getToken() after permission grant and listen to onTokenRefresh. Persist token to your backend with user ID. Tokens rotate on reinstall and sometimes on app update—never treat them as permanent identifiers."
---

Push notifications look easy until QA reports: "Tap works from notification tray but not cold start." FCM handles transport; your Flutter app still owns permissions, token lifecycle, background isolates, and navigation when the user taps a payload at 6 AM with the app swiped away.

This walkthrough uses `firebase_messaging` with current FlutterFire setup for Android and iOS.

## Project setup

Add Firebase to Flutter with FlutterFire CLI:

```bash
flutterfire configure
```

Dependencies:

```yaml
dependencies:
  firebase_core: ^3.0.0
  firebase_messaging: ^15.0.0
```

Initialize before runApp:

```dart
void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );
  await PushNotificationService.init();
  runApp(const MyApp());
}
```

## Permissions and token

```dart
class PushNotificationService {
  static final _messaging = FirebaseMessaging.instance;

  static Future<void> init() async {
    final settings = await _messaging.requestPermission(
      alert: true,
      badge: true,
      sound: true,
    );

    if (settings.authorizationStatus == AuthorizationStatus.authorized) {
      final token = await _messaging.getToken();
      if (token != null) await Api.registerDeviceToken(token);
    }

    _messaging.onTokenRefresh.listen(Api.registerDeviceToken);
  }
}
```

iOS requires explicit permission; Android 13+ needs `POST_NOTIFICATIONS` runtime permission—request via `permission_handler` or Firebase's flow before expecting delivery.

## Foreground presentation

FCM does not show heads-up notifications while app is foreground unless you handle `onMessage`:

```dart
FirebaseMessaging.onMessage.listen((RemoteMessage message) {
  final notification = message.notification;
  if (notification != null) {
    localNotifications.show(
      id: notification.hashCode,
      title: notification.title,
      body: notification.body,
      payload: jsonEncode(message.data),
    );
  }
});
```

Pair with `flutter_local_notifications` for consistent UI when foregrounded.

## Background and terminated handlers

Register a top-level function—must be outside classes:

```dart
@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  await Firebase.initializeApp();
  // lightweight work only—no UI
  await syncInboxFromPush(message.data);
}

void main() async {
  ...
  FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);
}
```

Background handlers run in a separate isolate with tight time limits. Do not navigate or show dialogs there.

## Tap routing and deep links

```dart
Future<void> setupInteractedMessage() async {
  final initial = await FirebaseMessaging.instance.getInitialMessage();
  if (initial != null) _handleMessage(initial);

  FirebaseMessaging.onMessageOpenedApp.listen(_handleMessage);
}

void _handleMessage(RemoteMessage message) {
  final route = message.data['route'];
  if (route != null) router.go(route);
}
```

`getInitialMessage` covers terminated-state taps; `onMessageOpenedApp` covers background. Test all three states explicitly—CI will not catch routing bugs.

## Android notification channels

Create channels before displaying notifications on Android 8+:

```dart
const channel = AndroidNotificationChannel(
  'orders',
  'Order updates',
  description: 'Shipment and delivery alerts',
  importance: Importance.high,
);

await flutterLocalNotificationsPlugin
    .resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>()
    ?.createNotificationChannel(channel);
```

Map FCM `android_channel_id` in payload to the same ID server-side.

## iOS specifics

Upload APNs authentication key to Firebase console. Enable Push Notifications and Background Modes (remote notifications) in Xcode. Provisioning profiles must include push capability—TestFlight catches misconfigurations App Store Connect will reject.

## Server payload example

```json
{
  "message": {
    "token": "device_token",
    "notification": {
      "title": "Order shipped",
      "body": "Track package #4821"
    },
    "data": {
      "route": "/orders/4821"
    },
    "android": {
      "priority": "high",
      "notification": { "channel_id": "orders" }
    }
  }
}
```

Keep `data` values strings—FCM requirement.

## Topic and segment targeting

Beyond device tokens, FCM supports topics:

```dart
await FirebaseMessaging.instance.subscribeToTopic('region_eu');
```

Use topics for broadcast alerts; use token targeting for user-specific messages. Unsubscribe on logout to prevent cross-user notification leakage on shared tablets—rare but real in kiosk scenarios.

## Notification channels on Android 13+

Create channels matching user expectations—separate **orders**, **marketing**, and **security** so users disable marketing without muting security alerts. Pass `channel_id` from server payload; keep server-side mapping documented.

Request `POST_NOTIFICATIONS` before subscribing to topics on Android 13+.

## Data-only messages for silent sync

```json
{
  "message": {
    "token": "...",
    "data": { "sync": "inbox" },
    "android": { "priority": "high" }
  }
}
```

Handle in background handler—no system notification shown. Do not perform heavy sync without checking battery and network constraints; defer to WorkManager if work exceeds seconds.

## Analytics and delivery debugging

Firebase console shows delivery funnels. Log `onMessage`, `onMessageOpenedApp`, and token refresh in debug. Production: track notification open rate via analytics event on `_handleMessage`.

## iOS provisional authorization

```dart
await _messaging.requestPermission(provisional: true);
```

Quiet notifications on iOS until user promotes to full alert—product decision, not default for all apps.

## Testing matrix

| State | Test |
|-------|------|
| Foreground | heads-up via local notifications |
| Background | tap opens correct route |
| Terminated | `getInitialMessage` routes correctly |
| Token refresh | backend receives new token |

Use FCM HTTP v1 with service account in staging—never commit keys.


## Permission funnels

Track analytics: prompt shown → granted → denied → settings opened—optimize copy before second prompt; iOS allows one custom pre-prompt before system dialog.

## Badge counts

Sync app icon badge with unread count—clear badge on mark-all-read; iOS `setApplicationIconBadgeNumber` via plugin; Android launcher support varies.

## Collapse key and notification grouping

Android `collapse_key` replaces pending notifications—use for chat messages same sender; FCM docs define limits.

## Multi-device users

Store multiple tokens per user in backend—logout one device removes only that token; account password change invalidates all tokens server-side.

## Provisional metrics

Track iOS provisional authorization conversion to full authorization—product experiment on pre-prompt copy if conversion below target.

## Additional release coordination

Notification payload schema version field allows backend gradual rollout new fields—app ignores unknown keys forward compatible. Backend and mobile release order documented: backend tolerant first, then mobile utilizing new fields, never reverse order causing silent ignore user-visible features.

## Team practices

Shipping Flutter Push Notifications Fcm in production taught our team that documentation beats hero demos. We wrote runbooks covering failure modes, on-call steps, and rollback triggers before the second release, not after the first outage.

When reviewing PRs touching Flutter Push Notifications Fcm, we ask for measurable outcomes: latency, crash rate, or support ticket volume—not subjective feels faster. If metrics are unavailable, the PR includes a DevTools trace or load test snippet proving the change.

Onboarding engineers paste a checklist into their first Flutter Push Notifications Fcm PR description: environment setup verified, tests added or updated, accessibility spot-checked, and release notes drafted for user-visible changes.

We keep a living FAQ in the repo wiki for Flutter Push Notifications Fcm questions repeated in Slack more than twice. FAQ entries link to source files and Slack threads, reducing tribal knowledge and repeated explanations in code review.

## Resources

- [Firebase Cloud Messaging for Flutter](https://firebase.flutter.dev/docs/messaging/overview)
- [firebase_messaging package](https://pub.dev/packages/firebase_messaging)
- [FlutterFire setup](https://firebase.flutter.dev/docs/overview)
- [FCM HTTP v1 API](https://firebase.google.com/docs/cloud-messaging/send-message)
- [flutter_local_notifications](https://pub.dev/packages/flutter_local_notifications)
