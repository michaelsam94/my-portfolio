---
title: "The Result Pattern with Sealed Classes"
slug: "flutter-result-pattern-sealed"
description: "Sealed Result types replace thrown exceptions in Dart with exhaustive success and failure handling. Cleaner repositories, testable errors, and switch expressions that compile."
datePublished: "2025-02-21"
dateModified: "2025-02-21"
tags: ["Flutter", "Dart", "Architecture", "Mobile"]
keywords: "Result pattern Dart, sealed class Flutter, exhaustive switch Dart 3, error handling Dart, Success Failure type"
faq:
  - q: "Result pattern vs throwing exceptions in Dart?"
    a: "Exceptions are fine for truly exceptional programmer errors. Result types model expected failures—network timeouts, validation errors, 404 responses—as values callers must handle. That makes control flow visible in types and tests without try/catch gymnastics."
  - q: "Do I need a package or roll my own Result?"
    a: "Dart 3 sealed classes make a lightweight custom Result trivial and zero-dependency. Packages like multiple_result or fpdart add map/flatMap utilities if you want functional chaining. Start sealed and add a package only when boilerplate grows."
  - q: "How does Result work with async UI state?"
    a: "Map Result to AsyncValue or your own loading/error/data union in ViewModels. The repository returns Result<User, ApiError>; the notifier sets state based on switch (result) { Success() => ..., Failure() => ... }."
---

`try/catch` around every repository call hid a bug for weeks: one code path caught `Exception`, swallowed it, and returned null. The UI showed an empty state that looked like "no data" instead of "request failed." Sealed `Result` types force the caller to acknowledge failure branches at compile time—exhaustive switches do not let you forget.

## Defining a sealed Result

```dart
sealed class Result<T, E> {
  const Result();
}

final class Success<T, E> extends Result<T, E> {
  const Success(this.value);
  final T value;
}

final class Failure<T, E> extends Result<T, E> {
  const Failure(this.error);
  final E error;
}
```

Use a sealed error type too:

```dart
sealed class ApiError {
  const ApiError();
}

final class NetworkError extends ApiError {
  const NetworkError(this.message);
  final String message;
}

final class Unauthorized extends ApiError {
  const Unauthorized();
}
```

## Repository returning Result

```dart
class UserRepository {
  Future<Result<User, ApiError>> fetchUser(String id) async {
    try {
      final response = await _client.get('/users/$id');
      if (response.statusCode == 401) {
        return const Failure(Unauthorized());
      }
      if (response.statusCode != 200) {
        return Failure(NetworkError('HTTP ${response.statusCode}'));
      }
      return Success(User.fromJson(response.data));
    } on SocketException {
      return const Failure(NetworkError('offline'));
    }
  }
}
```

No throw across the domain boundary—failures are data.

## Exhaustive handling

```dart
Future<void> load() async {
  final result = await repo.fetchUser(id);

  switch (result) {
    case Success(value: final user):
      state = AsyncData(user);
    case Failure(error: final Unauthorized()):
      auth.logout();
    case Failure(error: final NetworkError(:final message)):
      state = AsyncError(message);
  }
}
```

Dart 3 exhaustiveness checking warns if you add a new `ApiError` variant without updating switches—refactors stay safe.

## Mapping and chaining

```dart
Result<UserDto, ApiError> mapUser(Result<JsonMap, ApiError> raw) {
  return switch (raw) {
    Success(value: final json) => Success(UserDto.fromJson(json)),
    Failure(error: final e) => Failure(e),
  };
}
```

For heavy chaining, extension methods help:

```dart
extension ResultX<T, E> on Result<T, E> {
  Result<R, E> mapSuccess<R>(R Function(T) f) => switch (this) {
        Success(value: final v) => Success(f(v)),
        Failure(error: final e) => Failure(e),
      };
}
```

## UI presentation

```dart
Widget buildBody(Result<List<Item>, ApiError> result) {
  return switch (result) {
    Success(value: final items) when items.isEmpty =>
      const EmptyState(),
    Success(value: final items) =>
      ItemList(items: items),
    Failure(error: final NetworkError()) =>
      const OfflineBanner(),
    Failure(error: final Unauthorized()) =>
      const LoginPrompt(),
  };
}
```

Pattern guards keep widgets declarative—no nested if-is checks.

## Testing advantages

```dart
test('returns Failure on 401', () async {
  when(() => client.get(any())).thenAnswer(
    (_) async => Response(statusCode: 401, data: null),
  );

  final result = await repo.fetchUser('1');

  expect(result, isA<Failure<User, ApiError>>());
  expect((result as Failure).error, isA<Unauthorized>());
});
```

Assertions on types beat expecting thrown exceptions.

## When not to use Result

- Flutter framework callbacks where exceptions are idiomatic
- Parser bugs and assert-level invariants—keep throws
- Interop with APIs that only throw unless you wrap at the boundary once

Use Result at architectural seams: repositories, use cases, platform services.

## Interop at system boundaries

Wrap third-party SDKs that throw at your repository boundary:

```dart
Future<Result<Payment, PaymentError>> charge(PaymentRequest req) async {
  try {
    final receipt = await stripe.charge(req);
    return Success(receipt);
  } on StripeException catch (e) {
    return Failure(PaymentError.fromStripe(e));
  }
}
```

UI never imports Stripe types—only `Result` and your sealed `PaymentError`.

## Logging and observability

Log failures with structured fields:

```dart
case Failure(error: final NetworkError(:final message)):
  logger.warning('fetch failed', extra: {'message': message});
```

Do not log Success payloads containing PII at info level in production.

## Migration from nullable returns

Legacy `Future<User?>` where null meant not found:

```dart
@Deprecated('Use fetchUserResult')
Future<User?> fetchUser(String id) async {
  final r = await fetchUserResult(id);
  return switch (r) {
    Success(value: final u) => u,
    Failure() => null,
  };
}
```

Migrate callers incrementally; delete deprecated path when grep clean.


## Serialization across isolates

Result types crossing isolates must be sendable—sealed errors with simple fields work; avoid wrapping non-Sendable objects in Failure.

## GraphQL and Result

Map GraphQL errors array to Failure variants—partial data with errors becomes `Success` with warnings or `Failure` based on product rules documented per query.

## Documentation for consumers

README on repository package lists all Error variants and when thrown—onboarding speed for new engineers.

## Lint enforcement

Custom lint: forbid `throw` in `lib/data/` layer except documented exceptions—CI grep check until analyzer plugin exists.

## HTTP status mapping table

Maintain table in repo docs: 401 → Unauthorized, 403 → Forbidden, 404 → NotFound sealed variants—repository layer maps consistently; UI switches on sealed types not raw status integers.

## Rollout guidance

Result pattern adoption starts single bounded context checkout Q1 expand orders Q2—big bang repository rewrite abandoned mid-sprint teaches incremental migration lesson.

## Team practices

Shipping Flutter Result Pattern Sealed in production taught our team that documentation beats hero demos. We wrote runbooks covering failure modes, on-call steps, and rollback triggers before the second release, not after the first outage.

When reviewing PRs touching Flutter Result Pattern Sealed, we ask for measurable outcomes: latency, crash rate, or support ticket volume—not subjective feels faster. If metrics are unavailable, the PR includes a DevTools trace or load test snippet proving the change.

Onboarding engineers paste a checklist into their first Flutter Result Pattern Sealed PR description: environment setup verified, tests added or updated, accessibility spot-checked, and release notes drafted for user-visible changes.

We keep a living FAQ in the repo wiki for Flutter Result Pattern Sealed questions repeated in Slack more than twice. FAQ entries link to source files and Slack threads, reducing tribal knowledge and repeated explanations in code review.

## Resources

- [Dart sealed classes](https://dart.dev/language/class-modifiers#sealed)
- [Pattern matching (Dart docs)](https://dart.dev/language/patterns)
- [Exhaustive switch checking](https://dart.dev/language/branches#exhaustiveness-checking)
- [fpdart TaskEither](https://pub.dev/packages/fpdart)
- [Effective Dart: Design](https://dart.dev/effective-dart/design)
