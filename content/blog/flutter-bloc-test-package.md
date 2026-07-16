---
title: "Testing BLoCs with bloc_test"
slug: "flutter-bloc-test-package"
description: "Master bloc_test: expect, seed, wait, skip, verify, and errors—plus testing event transformers, concurrent events, and Equatable state pitfalls."
datePublished: "2024-09-28"
dateModified: "2024-09-28"
tags: ["Flutter", "Dart"]
keywords: "bloc_test package, Flutter blocTest, BLoC unit testing, test event transformer, emit matcher"
faq:
  - q: "What is bloc_test in Flutter?"
    a: "bloc_test is the official companion package to flutter_bloc that provides blocTest—a declarative test function handling Bloc/Cubit lifecycle, stream subscription, async timing, and ordered state verification. It replaces manual expectLater boilerplate and produces clearer failure messages when emission order doesn't match."
  - q: "How do I test async Bloc events with bloc_test?"
    a: "Use the wait parameter to pause before assertions, allowing debounce timers and Future.delayed logic to complete. Combine with skip to ignore intermediate emissions you don't care about. For event transformers like debounce or throttle, set wait to slightly exceed the transformer duration."
  - q: "Why does blocTest fail with extra emissions?"
    a: "Common causes: initial state emitted on listen (use expect with skip: 1 or seed to override), Equatable states comparing equal when you expected distinct emissions, or async events still processing after act completes—increase wait. Use expect with a predicate function when emission count varies."
---

Manual Bloc testing with `expectLater` and stream controllers gets ugly fast—especially with debounced search, concurrent pagination, and error recovery flows. The `bloc_test` package exists because the Bloc authors wrote the same boilerplate fifty times and extracted it. If you're testing Blocs without `blocTest`, you're fighting the framework instead of your actual bugs.

## Installation and basics

```yaml
dev_dependencies:
  bloc_test: ^9.1.7
```

Minimal test:

```dart
blocTest<CounterCubit, int>(
  'increment emits [1]',
  build: () => CounterCubit(),
  act: (cubit) => cubit.increment(),
  expect: () => [1],
);
```

`build` creates a fresh instance per test. `act` runs after subscription. `expect` defines the exact emission sequence post-initial-state.

## Initial state and seed

By default, `blocTest` subscribes and may capture the initial state emission. Control this explicitly:

```dart
blocTest<CartBloc, CartState>(
  'starts from seeded loaded state',
  seed: () => CartState.loaded(items: [itemA]),
  build: () => CartBloc(mockRepo),
  act: (bloc) => bloc.add(RemoveItem(itemA.id)),
  expect: () => [CartState.loaded(items: [])],
);
```

`seed` replaces the Bloc's initial state before `act`. Use it whenever testing mid-lifecycle scenarios without calling setup methods first.

## wait, skip, and timing

Async Blocs need time to finish:

```dart
blocTest<SearchBloc, SearchState>(
  'debounces rapid queries',
  build: () => SearchBloc(repo)..add(const SearchStarted()),
  act: (bloc) async {
    bloc.add(const QueryChanged('a'));
    bloc.add(const QueryChanged('ab'));
    bloc.add(const QueryChanged('abc'));
  },
  wait: const Duration(milliseconds: 350),
  expect: () => [
    SearchState.loading(),
    isA<SearchStateLoaded>(),
  ],
);
```

- **`wait`** — delays assertion after `act` completes.
- **`skip: n`** — ignores first n emissions when verifying the rest.
- **`expect`** items can be matchers: `isA<T>()`, `predicate((s) => s.items.length == 3)`.

For `bloc_concurrency` transformers:

```dart
// restartable() — only latest event matters
blocTest<FeedBloc, FeedState>(
  'cancels stale fetch on refresh',
  act: (b) {
    b.add(FetchPage(1));
    b.add(FetchPage(1)); // duplicate rapid refresh
  },
  wait: const Duration(milliseconds: 100),
  expect: () => [
    FeedState.loading(),
    FeedState.loaded(page: 1),
  ],
);
```

## verify and errors

Assert side effects beyond emissions:

```dart
blocTest<OrderBloc, OrderState>(
  'calls repository on submit',
  build: () {
    when(() => repo.submit(any())).thenAnswer((_) async => orderId);
    return OrderBloc(repo);
  },
  act: (b) => b.add(SubmitOrder(cart)),
  expect: () => [OrderState.submitting(), OrderState.success(orderId)],
  verify: (bloc) {
    verify(() => repo.submit(cart)).called(1);
    verifyNoMoreInteractions(repo);
  },
);
```

Test exceptional flows with `errors`:

```dart
blocTest<UploadBloc, UploadState>(
  'emits failure on upload error',
  act: (b) => b.add(UploadFile(file)),
  errors: () => [isA<UploadException>()], // uncaught bloc errors
  expect: () => [UploadState.failed()],
);
```

Most production Blocs catch exceptions and emit error states—reserve `errors` for Blocs that rethrow or use `BlocObserver` error paths.

## Testing Equatable states

When states extend `Equatable`, distinct emissions with equal props collapse in `blocTest` expectations:

```dart
// BAD: two Loading states with same props — blocTest sees one
expect: () => [Loading(), Loading()], // may fail

// GOOD: add distinguishing fields
class Loading extends Equatable {
  final int attempt;
  const Loading(this.attempt);
  @override
  List<Object?> get props => [attempt];
}

expect: () => [Loading(1), Loading(2)],
```

Or use `expect` predicate:

```dart
expect: () => [
  predicate<SearchState>((s) => s is Loading && s.query == 'a'),
  predicate<SearchState>((s) => s is Loading && s.query == 'ab'),
  isA<Loaded>(),
],
```

## Multi-bloc interactions

Test coordinator Blocs that depend on others by mocking child Blocs or using real instances with mocked repos:

```dart
blocTest<CheckoutBloc, CheckoutState>(
  'requires auth before payment',
  build: () => CheckoutBloc(
    authBloc: AuthBloc(mockAuthRepo)..emit(Authenticated()),
    paymentRepo: mockPaymentRepo,
  ),
  act: (b) => b.add(StartCheckout()),
  expect: () => [
    CheckoutState.processing(),
    CheckoutState.complete(),
  ],
);
```

Prefer testing child Blocs independently; coordinator tests cover wiring only.

### blocTest vs raw stream tests

Use `blocTest` for standard act/expect flows. Drop to manual when:

- Testing `BlocObserver` callbacks globally.
- Verifying no emissions occur (`expect: () => []` works, but explicit `emitsNothing` patterns need careful subscription timing).
- Debugging transformer internals—isolate the transformer unit test separately.

### CI integration

Bloc tests should dominate your test suite count and run under 30 seconds total:

```bash
flutter test test/features/ --coverage
lcov --summary coverage/lcov.info
```

Fail CI if Cubit/Bloc coverage drops below 90%. These tests are cheap insurance against state machine regressions.

### Parameterized blocTest with test groups

Organize large test files by event type and use variables for shared mock setup:

```dart
group('SearchBloc', () {
  late MockSearchRepository repo;
  setUp(() => repo = MockSearchRepository());

  blocTest<SearchBloc, SearchState>(
    'empty query clears results',
    build: () => SearchBloc(repo),
    act: (b) => b.add(const QueryChanged('')),
    expect: () => [const SearchState.initial()],
  );
});
```

When expect sequences vary by platform or timing, use `wait` consistently across the test file—document debounce duration at top as a constant shared with production code to prevent test/production drift.

When testing Blocs with timers, inject fake clock or mock debounce duration via constructor parameter—hardcoded Duration in Bloc makes tests flaky on slow CI runners. Prefer passing Duration config from test to production code for search debounce and polling intervals.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

## Resources

- [bloc_test pub.dev](https://pub.dev/packages/bloc_test)
- [Testing blocs and cubits (bloclibrary.dev)](https://bloclibrary.dev/testing/)
- [bloc_concurrency package](https://pub.dev/packages/bloc_concurrency)
- [Equatable package](https://pub.dev/packages/equatable)
- [flutter_bloc package](https://pub.dev/packages/flutter_bloc)
