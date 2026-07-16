---
title: "Optimizing State Management in Flutter with Riverpod"
slug: "flutter-riverpod-state-management"
description: "How I structured Riverpod state for a production Flutter EV-charging app: provider scoping, AsyncNotifier, real-time WebSocket sync, and keeping rebuilds cheap."
datePublished: "2026-06-12"
dateModified: "2026-06-12"
tags: ["Flutter", "Riverpod", "State Management", "Dart"]
keywords: "Flutter Riverpod, Flutter state management, AsyncNotifier, Riverpod best practices, Flutter WebSocket state"
faq:
  - q: "Why use Riverpod instead of Provider for Flutter state management?"
    a: "Riverpod removes Provider's dependency on BuildContext, catches more errors at compile time, and makes provider scoping and testing easier — which matters in a large real-time app."
  - q: "How do you keep Riverpod rebuilds cheap?"
    a: "Scope providers narrowly, use select to watch only the fields a widget needs, and prefer AsyncNotifier for async state so unrelated UI does not rebuild on every update."
  - q: "Is Riverpod a good fit for real-time WebSocket data?"
    a: "Yes. Exposing a WebSocket stream through an AsyncNotifier or StreamProvider lets the UI react to live updates while keeping connection logic isolated and testable."
---

Most Flutter state-management debates stop at "which library." The harder question — the one that actually shows up in production — is *how you shape state once you've picked one*. On an EV-charging platform I built, the app had to track live charger status over a WebSocket, survive flaky connectivity, and stay responsive while a 3D map and a session timer rendered on the same screen. Riverpod made that tractable. Here is how I structured it, and the decisions that mattered.

## Why Riverpod over the alternatives

I reach for Riverpod when an app has **shared, asynchronous, cross-screen state** — exactly the EV case, where charger availability, the active session, and the user's wallet balance are all needed in multiple places and all change independently. Compared with `provider`, Riverpod removes the `BuildContext` dependency for reads, catches provider mistakes at compile time, and makes disposal explicit. Compared with BLoC, it is far less boilerplate for the same testability.

The rule I follow: **Riverpod for app-shared and server-driven state; plain `setState` for genuinely local widget state.** Animations, expand/collapse, form field focus — those never go near a provider. Over-globalizing state is the most common Riverpod mistake I see in code review.

## One notifier per domain, not per screen

The first structural decision is granularity. I split state by *domain*, not by *screen*, so a provider maps to a real-world concept:

```dart
final chargerStatusProvider =
    AsyncNotifierProvider<ChargerStatusNotifier, List<Charger>>(
  ChargerStatusNotifier.new,
);

class ChargerStatusNotifier extends AsyncNotifier<List<Charger>> {
  @override
  Future<List<Charger>> build() async {
    // Initial REST snapshot, then keep it live over the socket.
    final initial = await ref.watch(chargerRepoProvider).fetchAll();
    _subscribe();
    return initial;
  }

  void _subscribe() {
    final socket = ref.watch(socketProvider);
    ref.onDispose(socket.onChargerUpdate.listen(_applyDelta).cancel);
  }

  void _applyDelta(ChargerDelta delta) {
    final current = state.valueOrNull ?? const [];
    state = AsyncData([
      for (final c in current) c.id == delta.id ? c.merge(delta) : c,
    ]);
  }
}
```

Two things make this cheap. First, `AsyncNotifier.build()` gives you loading/error/data for free via `AsyncValue`, so the UI never has to juggle three separate booleans. Second, the socket subscription lives *inside* the notifier and is torn down with `ref.onDispose` — no leaked listeners when the screen is gone.

## Keep rebuilds surgical with `select`

The single biggest performance lever in Riverpod is **selective watching**. A naive `ref.watch(chargerStatusProvider)` rebuilds a widget whenever *any* charger changes. On a list of 200 chargers updating every few seconds, that is a rebuild storm. `select` narrows the subscription to exactly the slice a widget cares about:

```dart
// Rebuilds only when THIS charger's availability flips.
final isAvailable = ref.watch(
  chargerStatusProvider.select(
    (async) => async.valueOrNull
        ?.firstWhere((c) => c.id == chargerId)
        .isAvailable,
  ),
);
```

After moving the charger tiles to `select`, the per-tick rebuild count on the map screen dropped by roughly 90%, and jank on mid-range Android devices disappeared. If you take one thing from this article, take `select`.

## Derived state belongs in providers, not widgets

It is tempting to compute "how many chargers are free near me" inside a `build()` method. Don't. Derived values are themselves state, and Riverpod composes them cleanly:

```dart
final nearbyAvailableCountProvider = Provider<int>((ref) {
  final chargers = ref.watch(chargerStatusProvider).valueOrNull ?? [];
  final origin = ref.watch(userLocationProvider);
  return chargers.where((c) => c.isAvailable && c.within(origin, 5)).length;
});
```

This keeps the calculation testable in isolation, memoized between rebuilds, and reusable across the map badge, the list header, and the home summary — without recomputing three times.

## Treating connectivity as state, not an exception

Real-time apps live and die on reconnection. I model the socket itself as a provider whose lifecycle Riverpod manages, and I expose connection status as its own `StreamProvider` so the UI can show an honest banner instead of silently showing stale data:

```dart
final connectionStateProvider = StreamProvider<SocketState>(
  (ref) => ref.watch(socketProvider).states,
);
```

When the socket drops, the notifier doesn't throw — it flips to a degraded `AsyncData` with a `stale: true` flag, and on reconnect it re-fetches a fresh REST snapshot before resuming deltas. The user sees "Reconnecting…", never a frozen screen. That single pattern eliminated the majority of "the app shows the wrong charger as free" support reports.

## Testing is the payoff

Because every provider is a pure function of its dependencies, tests override the repository and socket with fakes and assert on emitted `AsyncValue`s — no widget pumping required for business logic:

```dart
final container = ProviderContainer(overrides: [
  chargerRepoProvider.overrideWithValue(FakeRepo()),
]);
addTearDown(container.dispose);
```

This is what let the platform ship with around 70% unit coverage on the state layer and zero critical post-launch defects on the mobile side.

## What I'd tell a team adopting Riverpod

- Scope by domain, dispose with `ref.onDispose`, and never leak a subscription.
- `select` is not an optimization you add later — design for it from the start.
- Let `AsyncValue` own loading/error; stop hand-rolling boolean flags.
- Derived data is state — put it in a `Provider`, not a widget body.
- Model connectivity explicitly so the UI can be honest about staleness.

Get those right and Riverpod stops being "a state library" and becomes the backbone that keeps a real-time Flutter app fast, testable, and calm under load.

## Resources

- [Riverpod documentation](https://riverpod.dev/)
- [Flutter state management overview](https://docs.flutter.dev/data-and-backend/state-mgmt/intro)
- [AsyncValue API reference](https://pub.dev/documentation/riverpod/latest/riverpod/AsyncValue-class.html)
- [Riverpod code generation](https://riverpod.dev/docs/concepts/about_code_generation)
- [Testing Riverpod providers](https://riverpod.dev/docs/cookbooks/testing)
- [Flutter performance profiling](https://docs.flutter.dev/perf/ui-performance)

*Building something real-time in Flutter and want a second pair of eyes on the architecture? [Get in touch](/#contact).*
