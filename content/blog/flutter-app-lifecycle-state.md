---
title: "Handling App Lifecycle State in Flutter"
slug: "flutter-app-lifecycle-state"
description: "Respond correctly to resumed, paused, and detached states: save drafts, pause timers, refresh tokens, and avoid the background bugs that lose user data."
datePublished: "2024-09-13"
dateModified: "2024-09-13"
tags: ["Flutter", "Dart"]
keywords: "Flutter AppLifecycleState, WidgetsBindingObserver, app lifecycle, background foreground Flutter"
faq:
  - q: "What are the Flutter app lifecycle states?"
    a: "Flutter exposes resumed, inactive, paused, detached, and hidden (added in newer versions). Resumed means the app is visible and interactive. Paused means it's not visible but still in memory. Detached means the engine is being destroyed. Inactive is a transitional state during phone calls or system dialogs."
  - q: "How do I listen to lifecycle changes in Flutter?"
    a: "Mix WidgetsBindingObserver into your State class or a dedicated service, call WidgetsBinding.instance.addObserver in initState, and implement didChangeAppLifecycleState. Remove the observer in dispose to prevent leaks. For global handling, register a singleton observer at app startup."
  - q: "Should I save user data when the app goes to background?"
    a: "Yes for unsaved form input, in-progress edits, and session tokens that may expire while backgrounded. Write to local storage on paused, not on every keystroke. On resumed, refresh stale data from the server and revalidate auth tokens before assuming the session is still valid."
---

Users switch apps constantly. Your Flutter app goes to background mid-form, gets killed by the OS an hour later, and they expect their draft to still be there. I've debugged too many "it lost my work" tickets that traced back to one missing `WidgetsBindingObserver`. Lifecycle handling isn't optional infrastructure—it's the difference between an app that feels reliable and one that gets uninstalled after the second data loss.

## Lifecycle states explained

`AppLifecycleState` values and what they mean in practice:

| State | User experience | Your action |
|-------|-----------------|-------------|
| `resumed` | App visible, interactive | Resume timers, refresh data |
| `inactive` | Transitioning (incoming call, app switcher) | Pause animations, don't persist yet |
| `paused` | App not visible, still in memory | Save state, pause expensive work |
| `hidden` | App hidden but running (desktop/web) | Similar to paused |
| `detached` | Engine shutting down | Final persist, cleanup |

On iOS, background time is limited—roughly 30 seconds of execution after `paused` unless you hold a background task. On Android, the process may survive indefinitely or die under memory pressure with no callback.

## Implementing WidgetsBindingObserver

The standard pattern in a root widget or dedicated service:

```dart
class _AppLifecycleHandlerState extends State<AppLifecycleHandler>
    with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    switch (state) {
      case AppLifecycleState.resumed:
        _onResumed();
      case AppLifecycleState.paused:
        _onPaused();
      case AppLifecycleState.inactive:
      case AppLifecycleState.detached:
      case AppLifecycleState.hidden:
        break;
    }
  }

  Future<void> _onPaused() async {
    await draftRepository.persistPendingDrafts();
    analytics.flush();
    pollingService.stop();
  }

  Future<void> _onResumed() async {
    await authService.refreshTokenIfNeeded();
    pollingService.start();
    ref.invalidate(staleProviders);
  }
}
```

Register once at the app root—multiple observers work, but centralize side effects to avoid duplicate API calls.

## What to do on paused

**Persist unsaved work.** Write drafts to `shared_preferences`, Hive, or Drift—not memory:

```dart
Future<void> saveDraft(ComposeState state) async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.setString('compose_draft', jsonEncode(state.toJson()));
}
```

**Stop expensive operations:** location streams, WebSocket heartbeats, video playback, CPU-heavy isolates.

**Record timestamp** for stale-data detection on resume:

```dart
_lastBackgroundedAt = DateTime.now();
```

## What to do on resumed

**Refresh auth.** Tokens often expire during long background periods:

```dart
if (_lastBackgroundedAt != null &&
    DateTime.now().difference(_lastBackgroundedAt!) > const Duration(minutes: 15)) {
  await authRepository.refreshSession();
}
```

**Invalidate cached data** if background duration exceeds your freshness threshold. Riverpod's `ref.invalidate`, Bloc re-fetch events, or simple `setState` after a network pull.

**Re-subscribe** to streams you cancelled on pause—Firestore listeners, SSE feeds, push notification handlers.

## Platform-specific considerations

**iOS:** Request background modes only when needed (`fetch`, `location`, `audio`). Misdeclared modes cause App Store rejection. Use `UIApplication.beginBackgroundTask` via platform channel for critical saves that exceed the default grace period.

**Android:** Don't rely on `onPause` for guaranteed persistence—use `onStop` semantics via lifecycle. For reliable background work, defer to `workmanager` package.

**Web:** `visibilitychange` events map loosely to lifecycle; test tab switching separately. `hidden` state covers background tabs.

## Testing lifecycle behavior

`TestWidgetsFlutterBinding` supports lifecycle simulation:

```dart
testWidgets('saves draft on pause', (tester) async {
  await tester.pumpWidget(MyApp());
  // Enter text
  await tester.enterText(find.byType(TextField), 'Hello');
  // Simulate background
  tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
  await tester.pumpAndSettle();
  // Verify persistence
  final draft = await draftRepository.loadDraft();
  expect(draft?.text, 'Hello');
});
```

Manual QA: background the app during form entry, force-kill from app switcher, relaunch. Repeat on both platforms.

### Common mistakes

1. **Saving only on dispose** — dispose may never run if OS kills the process.
2. **Restarting timers on inactive** — causes flicker during brief transitions.
3. **Assuming resumed means fresh** — user may return after hours; always check staleness.
4. **Multiple observers duplicating work** — consolidate into one coordinator service.

Get lifecycle right once at the architecture level—every feature benefits without reimplementing background saves.

### Coordinating with push notifications

When a push notification wakes the app briefly, lifecycle may transition inactive → resumed without paused. Don't persist drafts on inactive—wait for paused to avoid excessive disk writes during brief interruptions. Notification taps launching cold start should read pending navigation intent after first frame, not in main() before runApp.

Document lifecycle expectations in feature specs: "Does this feature need refresh on resume?" Most list screens yes; static settings screens maybe not. Centralize refresh policy in a SessionCoordinator rather than per-widget observers.

Web apps should listen to visibilitychange via dart:html or package:web in addition to WidgetsBindingObserver—tab backgrounding differs from mobile paused semantics. PWA install adds standalone display mode lifecycle quirks; test add-to-homescreen flows separately from browser tab.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

## Resources

- [AppLifecycleState enum](https://api.flutter.dev/flutter/dart-ui/AppLifecycleState.html)
- [WidgetsBindingObserver mixin](https://api.flutter.dev/flutter/widgets/WidgetsBindingObserver-class.html)
- [Flutter App Lifecycle documentation](https://docs.flutter.dev/ui/widgets/app-lifecycle)
- [Android Process Lifecycle](https://developer.android.com/topic/libraries/architecture/lifecycle)
- [Apple App Life Cycle (UIKit)](https://developer.apple.com/documentation/uikit/app_and_environment/managing_your_app_s_life_cycle)
