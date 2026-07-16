---
title: "Testing with Riverpod Overrides"
slug: "flutter-riverpod-testing-overrides"
description: "ProviderScope overrides fake dependencies in widget and unit tests. Patterns for repositories, clocks, and platform services without global singletons."
datePublished: "2025-03-08"
dateModified: "2025-03-08"
tags: ["Flutter", "Dart", "Riverpod", "Testing"]
keywords: "Riverpod testing overrides, ProviderContainer test, overrideWithValue, widget test Riverpod, mock provider Flutter"
faq:
  - q: "ProviderContainer vs ProviderScope in tests?"
    a: "Use ProviderContainer for pure unit tests of notifiers and providers without widgets. Wrap widgets in ProviderScope with overrides for widget tests. Both accept the same override API."
  - q: "How do I override async providers?"
    a: "Use overrideWith((ref) async => fakeValue) or overrideWithValue(AsyncData(fake)) depending on provider type. For AsyncNotifier, override the notifier class with a test subclass or mock API dependency instead of the notifier itself."
  - q: "Do overrides leak between tests?"
    a: "ProviderContainer must be disposed after each test—call container.dispose() in tearDown. ProviderScope creates a new scope per pumpWidget if you rebuild the tree; still avoid static containers shared across tests."
---

Riverpod's best testing feature is not Mocktail—it is `overrides`. Inject fakes at the provider boundary and the production widget tree runs unchanged. I stopped wrapping repositories in `InheritedWidget` test doubles once overrides clicked.

## Unit test with ProviderContainer

```dart
void main() {
  late ProviderContainer container;
  late FakeOrderApi fakeApi;

  setUp(() {
    fakeApi = FakeOrderApi();
    container = ProviderContainer(
      overrides: [
        orderApiProvider.overrideWithValue(fakeApi),
      ],
    );
  });

  tearDown(() => container.dispose());

  test('orderNotifier loads orders', () async {
    fakeApi.orders = [Order(id: '1')];

    final orders = await container.read(orderListProvider.future);
    expect(orders, hasLength(1));
  });
}
```

`overrideWithValue` for simple singletons; `overrideWith` when the provider computes from `ref`.

## Widget test with ProviderScope

```dart
testWidgets('shows orders', (tester) async {
  final fakeApi = FakeOrderApi()..orders = [Order(id: '1', total: 10)];

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        orderApiProvider.overrideWithValue(fakeApi),
      ],
      child: const MaterialApp(home: OrdersScreen()),
    ),
  );

  await tester.pumpAndSettle();
  expect(find.text('Order #1'), findsOneWidget);
});
```

Production `OrdersScreen` uses `ref.watch(orderListProvider)`—no test-only constructor parameters.

## Overriding Notifier implementations

Prefer overriding dependencies over notifiers:

```dart
// good
authRepositoryProvider.overrideWithValue(FakeAuthRepository(loggedIn: true))

// brittle
authNotifierProvider.overrideWith(() => TestAuthNotifier())
```

If you must override a notifier:

```dart
@riverpod
class Auth extends _$Auth {
  @override
  AuthState build() => AuthState.guest();
}

class TestAuth extends Auth {
  @override
  AuthState build() => AuthState.authenticated(userId: 'test');
}

overrides: [
  authProvider.overrideWith(() => TestAuth()),
]
```

## Async and Stream overrides

```dart
streamProvider.overrideWith((ref) => Stream.value([1, 2, 3])),

futureProvider.overrideWith((ref) async => 'fixed'),
```

For error paths:

```dart
orderApiProvider.overrideWithValue(ThrowingOrderApi()),
```

## Fake clock and environment

```dart
@riverpod
DateTime now(NowRef ref) => DateTime.now();

// test
overrides: [
  nowProvider.overrideWithValue(DateTime(2025, 3, 8, 12)),
]
```

Deterministic timestamps fix flaky relative-time assertions.

## Listening in tests

```dart
container.listen(
  cartProvider,
  (prev, next) => log.add(next),
  fireImmediately: true,
);
```

Verify side effects without widget tree.

## Unimplemented provider bootstrap

```dart
@Riverpod(keepAlive: true)
SharedPreferences sharedPreferences(SharedPreferencesRef ref) {
  throw UnimplementedError();
}

// main.dart production override
// tests:
sharedPreferencesProvider.overrideWithValue(
  FakeSharedPreferences(),
),
```

Pattern for plugins initialized in `main`.

## Integration test caution

Integration tests hitting real backend may use fewer overrides—use environment flavor provider to switch base URL instead of sprinkling `kDebugMode` checks.

## Common mistakes

- Forgetting `container.dispose()` — leaked listeners fail later tests mysteriously.
- Overriding too high in tree—override leaf dependencies for narrower behavior.
- `pumpAndSettle` with infinite animations—cap with timeout or mock animation providers.

## ProviderContainer listeners in tests

```dart
final sub = container.listen(
  orderProvider,
  (prev, next) => events.add(next),
);
addTearDown(sub.close);
```

Verify notifier side effects without pumping widgets.

## Override precedence

Inner `ProviderScope` overrides beat outer for same provider—useful in widget tests embedding subtree with fake deps while rest of app uses defaults (rare).

## Integration tests

`IntegrationTestWidgetsFlutterBinding` with real `ProviderScope` and only network layer faked—middle ground between unit and E2E.

## Debugging missing override

Unstubbed mock returns null → cryptic UI failure. Lint rule or test helper asserting critical providers overridden in `setUp` for widget test files.


## Widget test boilerplate reduction

Extract helper:

```dart
Future<void> pumpApp(WidgetTester tester, Widget child, {List<Override> overrides = const []}) {
  return tester.pumpWidget(
    ProviderScope(
      overrides: overrides,
      child: MaterialApp(home: child),
    ),
  );
}
```

Central place adds `GoRouter`, localization, theme—tests stay focused on overrides relevant to scenario.

## Override vs mock decision tree

- Need verify call count → Mocktail mock at repository
- Need simple in-memory behavior → Fake implementation override
- Need simulate slow network → override FutureProvider with delayed future
- Need error state → override throws or returns Result.Failure

Document in testing guide so new contributors do not mock `BuildContext`.

## Flaky test prevention

`pumpAndSettle` with async providers—use `await tester.pump()` then `await tester.pump(const Duration(seconds: 1))` when timers involved. `ProviderContainer.autoDispose` timing: read provider before pump settles if test expects immediate load.

## Contract tests for providers

Snapshot provider graph for critical features—script greps `ref.watch` dependencies in generated/notifier files to ensure authProvider rebuild triggers documented downstream invalidation.

## AutoDispose in tests

AutoDispose provider may dispose before expectation if no listener—use \`container.listen\` keeping subscription open until assertion completes in unit tests.

## Rollout guidance

Provider override test utilities extracted package `test_support` published path dependency monorepo—apps import consistent pumpApp helper reducing copy paste divergent test harnesses across squads.

## Team practices

Shipping Flutter Riverpod Testing Overrides in production taught our team that documentation beats hero demos. We wrote runbooks covering failure modes, on-call steps, and rollback triggers before the second release, not after the first outage.

When reviewing PRs touching Flutter Riverpod Testing Overrides, we ask for measurable outcomes: latency, crash rate, or support ticket volume—not subjective feels faster. If metrics are unavailable, the PR includes a DevTools trace or load test snippet proving the change.

Onboarding engineers paste a checklist into their first Flutter Riverpod Testing Overrides PR description: environment setup verified, tests added or updated, accessibility spot-checked, and release notes drafted for user-visible changes.

We keep a living FAQ in the repo wiki for Flutter Riverpod Testing Overrides questions repeated in Slack more than twice. FAQ entries link to source files and Slack threads, reducing tribal knowledge and repeated explanations in code review.

Cross-functional review includes design for UX-facing work, security for auth or storage, and platform for native bridges. Flutter Riverpod Testing Overrides spans layers; skipping reviewers recreated bugs we fixed months ago.

Staging soaks 24 hours for risky changes while dashboards watch error rates.canary cohorts internal staff first, then five percent production, then full rollout if crash-free sessions hold within baseline tolerance.

Post-release we schedule a short retro even on smooth launches—what signal caught issues early, what was noise. Flutter Riverpod Testing Overrides improvements compound when feedback loops stay short and blameless.

## Resources

- [Riverpod testing documentation](https://riverpod.dev/docs/essentials/testing)
- [ProviderScope API](https://pub.dev/documentation/flutter_riverpod/latest/flutter_riverpod/ProviderScope-class.html)
- [ProviderContainer API](https://pub.dev/documentation/riverpod/latest/riverpod/ProviderContainer-class.html)
- [Mocktail package](https://pub.dev/packages/mocktail)
- [Flutter widget testing](https://docs.flutter.dev/testing/overview)
