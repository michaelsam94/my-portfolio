---
title: "Functional Error Handling in Dart"
slug: "flutter-error-handling-either-dartz"
description: "Replace try/catch spaghetti with Either and Result types in Dart: railway-oriented error handling, fpdart patterns, and clean failure propagation in Flutter apps."
datePublished: "2024-10-31"
dateModified: "2024-10-31"
tags: ["Flutter", "Dart"]
keywords: "Dart Either, fpdart Flutter, functional error handling, Result type Dart, railway oriented programming"
faq:
  - q: "What is Either in Dart functional programming?"
    a: "Either is a sum type representing success (Right) or failure (Left). Functions return Either<Failure, Success> instead of throwing exceptions, forcing callers to handle both paths explicitly. Libraries like fpdart and dartz provide Either with map, flatMap, and fold operations for composable error handling."
  - q: "Should I use exceptions or Either in Flutter?"
    a: "Exceptions suit truly exceptional unrecoverable cases—programmer errors, platform failures. Either suits expected failures—network errors, validation failures, not-found cases—that business logic must handle gracefully. Many Flutter apps use Either in domain/data layers and throw only at UI boundaries for unhandled cases."
  - q: "What is the difference between dartz and fpdart?"
    a: "Both provide Either and functional types. fpdart is the actively maintained successor with better Dart 3 support, sealed classes integration, and improved API ergonomics. New projects should prefer fpdart; dartz remains in legacy codebases."
---

Every repository method threw a different exception type. Cubits caught `DioException`, `FormatException`, and occasionally `TypeError` from the same call stack. UI showed "Something went wrong" for everything. Refactoring to `Either<Failure, T>` forced us to classify failures once at the data boundary and propagate typed errors up the stack. The code got longer in places; the bug surface shrank dramatically.

## The problem with exceptions for flow control

```dart
// Callers forget to catch; failures become unhandled async errors
Future<User> fetchUser(String id) async {
  final response = await dio.get('/users/$id');
  return User.fromJson(response.data);
}
```

Exceptions are invisible in the type signature. `Future<User>` promises success; failure modes are undocumented.

## Either basics with fpdart

```yaml
dependencies:
  fpdart: ^1.1.0
```

```dart
sealed class Failure {
  const Failure();
}

class NetworkFailure extends Failure {
  const NetworkFailure(this.message);
  final String message;
}

class NotFoundFailure extends Failure {
  const NotFoundFailure();
}

Future<Either<Failure, User>> fetchUser(String id) async {
  try {
    final response = await dio.get('/users/$id');
    return Right(User.fromJson(response.data));
  } on DioException catch (e) {
    if (e.response?.statusCode == 404) {
      return const Left(NotFoundFailure());
    }
    return Left(NetworkFailure(e.message ?? 'Network error'));
  } on FormatException {
    return const Left(NetworkFailure('Invalid response format'));
  }
}
```

Callers must handle both sides:

```dart
final result = await fetchUser('42');
result.fold(
  (failure) => emit(UserError(failure)),
  (user) => emit(UserLoaded(user)),
);
```

## Chaining with flatMap

Railway-oriented composition—short-circuit on first Left:

```dart
Future<Either<Failure, OrderConfirmation>> checkout(Cart cart) async {
  return await validateCart(cart)
      .flatMap((validCart) => chargePayment(validCart))
      .flatMap((payment) => createOrder(payment))
      .flatMap((order) => sendConfirmation(order));
}

Future<Either<Failure, ValidCart>> validateCart(Cart cart) async {
  if (cart.isEmpty) return const Left(ValidationFailure('Cart is empty'));
  return Right(ValidCart.from(cart));
}
```

Each step returns `Either`; `flatMap` chains without nested if/else.

## Custom Result type (lighter alternative)

If Either feels heavy, a sealed Result works in pure Dart 3:

```dart
sealed class Result<T> {
  const Result();
}

class Success<T> extends Result<T> {
  const Success(this.value);
  final T value;
}

class Error<T> extends Result<T> {
  const Error(this.failure);
  final Failure failure;
}

extension ResultX<T> on Result<T> {
  R when<R>({
    required R Function(Failure) error,
    required R Function(T) success,
  }) => switch (this) {
    Success(value: final v) => success(v),
    Error(failure: final f) => error(f),
  };
}
```

No dependency; pattern match with switch expressions.

## Integration with Cubit/Bloc

```dart
class ProfileCubit extends Cubit<ProfileState> {
  ProfileCubit(this._repo) : super(ProfileInitial());
  final ProfileRepository _repo;

  Future<void> load() async {
    emit(ProfileLoading());
    final result = await _repo.getProfile();
    result.fold(
      (f) => emit(ProfileError(_messageFor(f))),
      (profile) => emit(ProfileLoaded(profile)),
    );
  }

  String _messageFor(Failure f) => switch (f) {
    NetworkFailure(:final message) => message,
    NotFoundFailure() => 'Profile not found',
    _ => 'Unexpected error',
  };
}
```

Map failures to user strings in one place per feature.

## Either in repositories

Keep exception catching at the data layer boundary:

```dart
class UserRepositoryImpl implements UserRepository {
  @override
  Future<Either<Failure, User>> getUser(String id) async {
    return TaskEither.tryCatch(
      () async {
        final dto = await _api.fetchUser(id);
        return dto.toEntity();
      },
      (error, stack) => _mapError(error),
    ).run();
  }

  Failure _mapError(Object error) {
    if (error is DioException) {
      return NetworkFailure(error.message ?? 'Request failed');
    }
    return const NetworkFailure('Unknown error');
  }
}
```

`TaskEither` from fpdart wraps async Either with tryCatch ergonomics.

### When to still throw

- **Assertion failures** — programmer bugs in debug.
- **Platform channel errors** — often unrecoverable at app level.
- **Widget build errors** — Flutter framework expects exceptions for error boundaries.

Don't Either-wrap everything. Use at domain boundaries where failure is expected and typed.

### Testing Either code

```dart
test('returns NotFoundFailure on 404', () async {
  when(() => api.fetchUser('missing'))
      .thenThrow(DioException(requestOptions: RequestOptions(), response: Response(statusCode: 404, requestOptions: RequestOptions())));

  final result = await repo.getUser('missing');
  expect(result.isLeft(), true);
  expect(result.getLeft().toNullable(), isA<NotFoundFailure>());
});
```

Exhaustive failure testing becomes straightforward—no try/catch in tests.

### UI mapping layer for Failures

Keep user strings out of domain Failures:

```dart
extension FailureMessage on Failure {
  String localized(AppLocalizations l10n) => switch (this) {
    NetworkFailure() => l10n.errorNetwork,
    NotFoundFailure() => l10n.errorNotFound,
    _ => l10n.errorGeneric,
  };
}
```

Cubits emit Failure objects; widgets map to localized strings at presentation edge. Enables i18n without polluting data layer with BuildContext.

Log Left failures with structured logging (level, failure type, stack) before emitting UI state—production debugging needs failure distribution metrics. Track NetworkFailure rate in analytics dashboard separate from user-facing error screens to distinguish infra issues from validation errors.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

Schedule a quarterly review of this implementation against current SDK release notes—Flutter and cloud providers ship breaking changes on six-month cadences, and assumptions that held last year may need adjustment. Capture before-and-after metrics when you change configuration so regressions are obvious in retrospect rather than debated from memory.

## Resources

- [fpdart package](https://pub.dev/packages/fpdart)
- [fpdart Either documentation](https://pub.dev/documentation/fpdart/latest/fpdart/Either-class.html)
- [TaskEither for async](https://pub.dev/documentation/fpdart/latest/fpdart/TaskEither-class.html)
- [Railway oriented programming (Scott Wlaschin)](https://fsharpforfunandprofit.com/rop/)
- [Dart sealed classes](https://dart.dev/language/class-modifiers#sealed)
