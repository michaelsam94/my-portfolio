---
title: "State Restoration in Flutter: Surviving Process Death"
slug: "flutter-state-restoration"
description: "State restoration in Flutter keeps scroll position, form input, and navigation alive after the OS kills your app. How RestorationMixin and restorationId actually work."
datePublished: "2024-10-09"
dateModified: "2024-10-09"
tags: ["Flutter", "Dart", "State Management", "Mobile"]
keywords: "Flutter state restoration, RestorationMixin, restorationId, RestorableProperty, process death Flutter, RestorationScope"
faq:
  - q: "What is state restoration in Flutter?"
    a: "State restoration is Flutter's mechanism for rebuilding your UI to the state it was in before the operating system killed the app to reclaim memory. It persists a small tree of restorable values keyed by restoration IDs, then replays them when the app is relaunched into the same task. It is distinct from ordinary state management, which only survives while the process is alive."
  - q: "How do I test state restoration on Android?"
    a: "Enable 'Don't keep activities' in developer options, background your app, and reopen it — the activity is destroyed and recreated just like a real low-memory kill. On iOS you can trigger it from Xcode by simulating a memory warning or using the state restoration debugging flow. Do not rely on a normal back-and-return, because that usually keeps the process alive and hides bugs."
  - q: "Is state restoration the same as saving to shared preferences?"
    a: "No. Shared preferences (or any disk store) is for durable user data that should persist across full app restarts and reinstalls. State restoration is for transient UI state — scroll offset, the tab you were on, half-typed text — that only makes sense within a single logical session and is discarded when the user actually closes the app."
---

Flutter state restoration is what lets your app come back exactly where the user left it after the OS silently kills it in the background to free memory. On Android especially, a user can switch to another app, and ten minutes later the system reclaims your process — when they tap back in, they expect the same screen, the same scroll position, the same half-typed message. Without restoration wired up, they get a cold start to your home screen instead, and it feels like the app forgot them.

I've shipped apps that "worked fine" in every test and still got one-star reviews about losing form data. The reason was always the same: the team tested by backgrounding and returning, which keeps the process alive, instead of testing genuine process death. State restoration is the feature that closes that gap, and it's more subtle than most Flutter tutorials admit.

## The problem it actually solves

There are three ways your app can lose state, and only one of them is what restoration targets:

- **Rebuilds** (rotation, theme change): handled by keeping state above the widget that rebuilds. Ordinary `State` survives this.
- **Full restart** (user swipes the app away, reinstall): should *not* restore transient UI — the user chose to leave. Durable data belongs in a database.
- **Process death** (OS kills a backgrounded app for memory): the app object is destroyed, but the OS remembers it was there and relaunches into the same task. This is restoration's job.

That middle-ground case is invisible on a fast dev device with plenty of RAM, which is exactly why it ships broken. The OS serializes a small bundle of your restoration data before it kills you, then hands it back on relaunch.

## Turn it on: RestorationScope and restorationId

Restoration is opt-in and hierarchical. `MaterialApp` exposes a `restorationScopeId`; setting it establishes the root scope. From there, every restorable piece of state needs a `restorationId` that's unique within its scope, forming a stable tree the framework can serialize and replay.

```dart
MaterialApp(
  restorationScopeId: 'app',
  home: const HomePage(),
);
```

Without that root ID, none of the child restoration IDs do anything — a common "why isn't this working" moment. The IDs are the addresses; the framework walks the tree, collects the restorable values at each address, and writes them into a `RestorationBucket`.

## RestorationMixin and RestorableProperty

For your own stateful widgets, the pattern is `RestorationMixin` plus one or more `RestorableProperty` fields. The mixin asks you for a `restorationId` and gives you a `restoreState` hook where you register each property.

```dart
class CounterPage extends StatefulWidget {
  const CounterPage({super.key});
  @override
  State<CounterPage> createState() => _CounterPageState();
}

class _CounterPageState extends State<CounterPage>
    with RestorationMixin {
  final RestorableInt _count = RestorableInt(0);

  @override
  String get restorationId => 'counter_page';

  @override
  void restoreState(RestorationBucket? oldBucket, bool initialRestore) {
    registerForRestoration(_count, 'count');
  }

  @override
  void dispose() {
    _count.dispose();
    super.dispose();
  }

  void _increment() => setState(() => _count.value++);
}
```

The key mental shift: you stop reading `_count` as a plain field and start treating `_count.value` as the source of truth. The `RestorableInt` handles serialization; you just mutate `.value`. Flutter ships restorable variants for the common primitives (`RestorableInt`, `RestorableString`, `RestorableBool`, `RestorableDouble`, `RestorableEnum`, `RestorableTextEditingController`, `RestorableDateTime`), and you can subclass `RestorableValue` for anything custom that serializes to JSON-compatible primitives.

Note `registerForRestoration` is called from `restoreState`, not `initState`. On the first build `initialRestore` is true and it seeds from defaults; on a real restoration it's false and the bucket already holds the persisted value. `dispose` on each property still matters — restorable properties are `ChangeNotifier`s under the hood.

## Text fields and controllers

The single most requested restoration behavior is "keep what the user typed." Use `RestorableTextEditingController` instead of a raw `TextEditingController`:

```dart
final RestorableTextEditingController _name =
    RestorableTextEditingController();

@override
void restoreState(RestorationBucket? oldBucket, bool initialRestore) {
  registerForRestoration(_name, 'name_field');
}

// in build:
TextField(controller: _name.value);
```

That single change is the difference between a form that survives a memory kill and one that greets the user with empty fields after they spent two minutes filling it out.

## Navigation and scroll restoration

Two of the highest-value wins come nearly for free. `Navigator` restores its route stack when routes are pushed with restoration-aware APIs (`restorablePushNamed`, `restorablePush`) and the pages carry restoration IDs — so a user three screens deep lands back three screens deep. And scrollable widgets restore their offset automatically when you give the scroll view or its `PrimaryScrollController` a `restorationId`:

```dart
ListView.builder(
  restorationId: 'feed_list',
  itemBuilder: (context, i) => FeedTile(items[i]),
  itemCount: items.length,
);
```

For anything driven by declarative routing, the same principle applies at the router layer — which is why I keep navigation state serializable in the first place, a habit that also pays off with [GoRouter for declarative navigation](https://blog.michaelsam94.com/flutter-navigator-2-gorouter/).

## What not to restore

Restoration data is serialized by the OS and has real size limits (Android's `Bundle` is famously small — think tens to low hundreds of KB, and the TransactionTooLargeException lurks if you abuse it). So the discipline is: restore *identifiers and cursors, not payloads*. Store the selected item's ID and re-fetch it; never dump a list of model objects into a restorable property. Store the scroll offset; never store the loaded items. Anything expensive or large is re-derived from your durable data layer on restore. Get this wrong and you trade a cold-start bug for a crash under memory pressure.

## Testing it for real

This is where teams fool themselves. A normal background-and-return keeps the process warm and *hides* every restoration bug. To actually exercise the code path:

1. On Android, enable **Developer options → Don't keep activities**. Now every background genuinely destroys and recreates the activity.
2. Background the app (home button), then reopen from recents.
3. Verify scroll, form input, tab selection, and navigation depth all come back.

On iOS, drive it through Xcode's restoration debugging. Add this to CI where you can via `flutter test` with the restoration testing helpers (`tester.restartAndRestore()` in widget tests), which simulate the serialize-kill-replay cycle deterministically without a device.

## What I'd take away

Treat state restoration as a distinct concern from both rebuild-survival and durable storage. Set a `restorationScopeId` at the root, give every screen and scrollable a stable `restorationId`, wrap transient UI state in `RestorableProperty` values, and store IDs rather than payloads. Then — and this is the part people skip — test with "Don't keep activities" on, because until you do, you have no evidence any of it works. Done right, it's the difference between an app that remembers the user and one that quietly resets them.

## Resources

- [Restore state on Android (Flutter docs)](https://docs.flutter.dev/platform-integration/android/restore-state-android)
- [RestorationMixin API reference](https://api.flutter.dev/flutter/widgets/RestorationMixin-mixin.html)
- [RestorableProperty API reference](https://api.flutter.dev/flutter/widgets/RestorableProperty-class.html)
- [RestorationManager and buckets](https://api.flutter.dev/flutter/services/RestorationManager-class.html)
- [Android: Save UI states](https://developer.android.com/topic/libraries/architecture/saving-states)
