---
title: "Mocking in Dart with Mocktail"
slug: "flutter-mocktail-mocking"
description: "Mocktail gives you null-safe mocks without manual stubs or codegen. How to fake repositories, verify interactions, and keep Flutter tests fast."
datePublished: "2025-01-22"
dateModified: "2025-01-22"
tags: ["Flutter", "Dart", "Testing", "Mobile"]
keywords: "Mocktail Dart, Flutter unit testing mocks, mock repository Flutter, when verify mocktail, fake async testing"
faq:
  - q: "Mocktail vs mockito—which should I use in 2025?"
    a: "Mocktail is the default choice for new Dart 3 projects: no build_runner, no annotation boilerplate, full null-safety. Mockito still appears in legacy codebases with existing @GenerateMocks setup. Migrating is usually mechanical—replace extends Mock with Mocktail's class Mock implements Interface."
  - q: "How do I mock async methods that return Future?"
    a: "Use when(() => repo.fetch()).thenAnswer((_) async => [item]); for success paths and thenThrow for failures. Mocktail stubs return null by default until configured, so always stub Futures explicitly or tests will get unexpected nulls."
  - q: "Can Mocktail mock final classes?"
    a: "No. Dart final classes cannot be implemented or extended by mocks. Wrap the final class behind an interface or use a fake hand-written test double. This is a language constraint, not a Mocktail limitation."
---

The test failed because `UserRepository.fetch()` returned null—not an empty list, not an exception, just null. The mock was never stubbed. Mockito would have yelled at compile time if I had run build_runner last Tuesday. Mocktail yelled at runtime in four milliseconds, and I stubbed the call in one line. That trade-off—speed of authoring over codegen safety—is why most of my Flutter projects reach for Mocktail first.

Mocktail is a mocking library for Dart built for null safety. You create a class that `extends Mock` and `implements` your interface, stub methods with `when`, and assert calls with `verify`. No code generation, no `@GenerateMocks`, no waiting on build_runner between test edits.

## Basic mock setup

```dart
import 'package:mocktail/mocktail.dart';
import 'package:test/test.dart';

class MockUserRepository extends Mock implements UserRepository {}

void main() {
  late MockUserRepository repo;

  setUp(() {
    repo = MockUserRepository();
  });

  test('loads users on init', () async {
    when(() => repo.fetchAll()).thenAnswer((_) async => [
      User(id: '1', name: 'Ada'),
    ]);

    final controller = UserController(repo);
    await controller.load();

    expect(controller.users, hasLength(1));
    verify(() => repo.fetchAll()).called(1);
  });
}
```

`when` registers a stub. Until you stub, mock methods return defaults—null for objects, false for bool, zero for numbers. That catches missing stubs quickly if you assert on results.

## Stubbing patterns that matter

**Argument matchers:**

```dart
when(() => repo.findById(any())).thenAnswer((invocation) async {
  final id = invocation.positionalArguments[0] as String;
  return User(id: id, name: 'Test');
});
```

Register fallback values for custom types used with `any()`:

```dart
setUpAll(() {
  registerFallbackValue(UserQuery.empty());
});
```

Without fallback registration, Mocktail throws when matching custom objects.

**Throwing errors:**

```dart
when(() => repo.fetchAll()).thenThrow(NetworkException('offline'));
```

Use this to test error UI and retry logic in ViewModels without disconnecting Wi-Fi.

**Sequential responses:**

```dart
when(() => repo.fetchAll())
  .thenAnswer((_) async => [])
  .thenAnswer((_) async => [user]);
```

Handy for polling or refresh-after-empty scenarios.

## Fakes vs mocks

Not everything needs verification. A **fake** is a hand-written implementation with simple in-memory behavior:

```dart
class FakeUserRepository implements UserRepository {
  final List<User> _users = [];

  @override
  Future<List<User>> fetchAll() async => List.unmodifiable(_users);

  void seed(User user) => _users.add(user);
}
```

Use fakes when behavior is straightforward and you never verify call counts. Use mocks when you care that `save` was called exactly once with a specific payload.

## Testing Riverpod and Bloc with Mocktail

Inject mocks through constructors or overrides:

```dart
testWidgets('shows error snackbar on failure', (tester) async {
  when(() => repo.fetchAll()).thenThrow(Exception('fail'));

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        userRepositoryProvider.overrideWithValue(repo),
      ],
      child: const MyApp(),
    ),
  );

  await tester.pumpAndSettle();
  expect(find.text('Something went wrong'), findsOneWidget);
});
```

Reset mocks between tests if you reuse instances—`reset(repo)` clears stubs and call history.

## Verification and anti-patterns

```dart
verify(() => repo.save(any(that: predicate((User u) => u.name == 'Ada'))))
  .called(1);
verifyNever(() => repo.delete(any()));
```

Avoid verifying every interaction. Tests that mirror implementation details break on refactors. Verify boundaries: external API calls, analytics events, persistence writes.

Avoid mocking Flutter framework classes (`BuildContext`, `Widget`). Pump widgets instead. Mock your domain layer, not `Navigator`.

## Mockito migration cheat sheet

| Mockito | Mocktail |
|---------|----------|
| `@GenerateMocks([Repo])` | `class MockRepo extends Mock implements Repo {}` |
| `when(repo.fetch()).thenAnswer(...)` | `when(() => repo.fetch()).thenAnswer(...)` |
| `verify(repo.fetch())` | `verify(() => repo.fetch())` |
| `any` | `any()` |
| `@GenerateNiceMocks` | stub explicitly or use lenient patterns sparingly |

Run both libraries temporarily if migration is large; they coexist in dev_dependencies.

## Mocking streams and Duration

```dart
when(() => repo.watchUser()).thenAnswer((_) => Stream.fromIterable([
  User(id: '1', name: 'Ada'),
  User(id: '1', name: 'Ada Lovelace'),
]));
```

Use `fake_async` with timers:

```dart
fakeAsync((async) {
  when(() => repo.debouncedSearch(any())).thenAnswer((_) async {
    async.elapse(const Duration(milliseconds: 300));
    return results;
  });
});
```

## Spying on real implementations

Partial mocks are awkward in Mocktail—prefer composition:

```dart
class RecordingRepo implements UserRepository {
  RecordingRepo(this._inner);
  final UserRepository _inner;
  final List<String> calls = [];

  @override
  Future<User> findById(String id) {
    calls.add(id);
    return _inner.findById(id);
  }
}
```

Record side effects without full mock setup when integration-lite tests suffice.

## CI and test speed

Keep mock setup in `setUp`, not per assertion. Share `FakeUserRepository` instances across tests in a group when stateless. Avoid `verify` in every test—assert output state instead unless testing "must call analytics" contracts.

Flaky tests often trace to missing `await` on async stubs or shared mutable mock state—call `reset(mock)` in `tearDown` when reusing mocks across tests.

## Mockito coexistence during migration

Run both in dev_dependencies temporarily—convert test files file-by-file; delete mockito build.yaml when last @GenerateMocks removed.

## Integration with fake_async

Combine Mocktail stubs with fake_async for debounce and timer tests—ensure async stubs complete within elapsed fake time.


## Generic methods

Mocktail supports generic methods with same syntax—register fallback values for generic type args used in `any()` matchers.

## Null safety migration remnants

Legacy `Mock` from mockito without null safety—delete entirely; Mocktail requires Dart 3.

## Behavior-driven tests

Prefer given-when-then structure with mocks verifying collaboration at boundaries—readable for product managers reviewing acceptance tests.

## Code review focus

Reviewers check tests assert outcomes not implementation—verify(() => repo.save()) only when save must happen exactly once contractually.

## TearDown reset

Document team standard: reset mocks in tearDown not setUp to preserve failure context inspection before reset when test fails mid-execution.

## Rollout guidance

Testing guild office hours monthly Mocktail patterns live coding—junior engineers attend optional attendance improves test quality faster than written guide alone.

## Resources

- [Mocktail on pub.dev](https://pub.dev/packages/mocktail)
- [Mocktail GitHub repository](https://github.com/felangel/mocktail)
- [Testing Flutter apps (Flutter docs)](https://docs.flutter.dev/testing)
- [Dart test package](https://pub.dev/packages/test)
- [Effective Dart: Testing](https://dart.dev/effective-dart/testing)
