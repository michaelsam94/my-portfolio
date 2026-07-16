---
title: "Dart 3 Class Modifiers Explained"
slug: "dart-3-class-modifiers"
description: "Use Dart 3 sealed, final, base, and interface class modifiers to control inheritance, exhaustiveness, and API surface in Flutter and server Dart."
datePublished: "2025-06-08"
dateModified: "2025-06-08"
tags: ["Flutter", "Dart"]
keywords: "Dart 3 class modifiers, sealed class, final class, base class, interface class, exhaustiveness"
faq:
  - q: "What are Dart 3 class modifiers?"
    a: "Dart 3 adds sealed, final, base, interface, and mixin class modifiers controlling who can extend, implement, or mix in a class. Default implicit class behavior changed—libraries outside yours cannot extend or implement your classes unless you mark them base or open explicitly with intent."
  - q: "When should I use sealed classes?"
    a: "Use sealed for closed type hierarchies—UI states, network results, AST node types—where all variants live in one library. Switch statements over sealed types get compile-time exhaustiveness checking when using pattern matching. Subclasses must be in the same library or part file."
  - q: "What is the difference between base and interface?"
    a: "base allows extending the class outside the library but not implementing it as interface. interface allows implements but not extends. final disallows both outside library. Pick modifiers that match your API contract—prevent breaking subclasses or fake implementations."
---

Dart 3 stopped treating every class as implicitly subclassable from anywhere. Class modifiers—`sealed`, `final`, `base`, `interface`, `mixin`—encode intent in the type system: "these are all the states," "extend but do not implement," "implement this contract only." Flutter codebases adopting them get exhaustiveness checks in switches and fewer breaking changes from well-meaning subclasses.

## Modifier reference

| Modifier | Extend (outside lib) | Implement (outside lib) | Same library subclasses |
|----------|---------------------|-------------------------|-------------------------|
| (none/default) | No* | No* | Yes |
| `base` | Yes | No | Yes |
| `interface` | No | Yes | Yes |
| `final` | No | No | Yes |
| `sealed` | No | No | Yes, closed set |
| `mixin class` | Yes | Yes | Yes |

*Dart 3 default: classes are not extendable/implementable outside declaring library unless marked.

## sealed — closed hierarchies

```dart
sealed class Result<T> {}

class Success<T> extends Result<T> {
  final T value;
  Success(this.value);
}

class Failure<T> extends Result<T> {
  final Object error;
  Failure(this.error);
}

String describe(Result<int> r) => switch (r) {
  Success(value: var v) => 'Ok: $v',
  Failure(error: var e) => 'Err: $e',
  // no default — compiler verifies exhaustiveness
};
```

All subclasses must be in same library—typically same file or part files.

## final — no external subtyping

```dart
final class ApiClient {
  void fetch() { /* ... */ }
}

// Other library:
// class MockClient extends ApiClient {} // compile error
```

Use for concrete classes not designed for inheritance—prefer composition or explicit interfaces for testing.

## base — extend but not implement

```dart
base class Shape {
  void draw(Canvas canvas) {}
}

class Circle extends Shape {} // OK in other library
// class FakeShape implements Shape {} // error
```

Prevents fake implementations that skip base class behavior.

## interface — implement contract

```dart
interface class Serializable {
  Map<String, Object?> toJson();
}

class User implements Serializable {
  @override
  Map<String, Object?> toJson() => {'name': name};
}
```

## mixin class — mixin and class

```dart
mixin class Dismissible {
  void onDismiss() {}
}

class Card extends Dismissible with OtherMixin {}
```

Replaces awkward `class X {}` + `mixin X {}` duplication for mixin-as-class patterns.

## Flutter state modeling

```dart
sealed class AuthState {}

class AuthInitial extends AuthState {}
class AuthLoading extends AuthState {}
class AuthAuthenticated extends AuthState {
  final User user;
  AuthAuthenticated(this.user);
}
class AuthError extends AuthState {
  final String message;
  AuthError(this.message);
}

Widget build(AuthState state) => switch (state) {
  AuthInitial() => LoginPrompt(),
  AuthLoading() => LoadingSpinner(),
  AuthAuthenticated(user: var u) => HomeScreen(user: u),
  AuthError(message: var m) => ErrorView(m),
};
```

Bloc/Cubit emit sealed states—UI switches exhaustively.

## Migration from Dart 2

Implicit public classes were subclassable—Dart 3 breaks external extends. Fix:

- Add `base` if extension intended
- Add `interface` if implementation intended  
- Add `final` to lock down

```dart
// Before: class Vehicle {}
// After intent-preserving:
base class Vehicle {}
```

Run analyzer with `--fatal-infos` after SDK 3 upgrade.

## Testing with modifiers

`final` classes block Mockito `@GenerateMocks` extends—use `implements` against interface abstractions:

```dart
interface class HttpClient {
  Future<Response> get(Uri url);
}

class MockHttpClient implements HttpClient { /* manual or mockito implements */ }
```

Or keep test doubles in same library as `final` class via `@visibleForTesting` subclass in part file.

## Choosing the right modifier

Decision tree for new classes:

```
Is this a closed set of variants (states, results, events)?
  → sealed class

Should external code extend this class?
  → base class

Should external code implement this as interface only?
  → interface class

Should external code do neither?
  → final class

Is this both a mixin and a class?
  → mixin class
```

Default in Dart 3 is restrictive (neither extend nor implement from outside) — explicitly choose openness rather than accidentally blocking intended subclasses.

## sealed vs enum

| Feature | enum | sealed class |
|---|---|---|
| Variants with data | Awkward (fields per constant) | Natural (constructor per variant) |
| Exhaustive switch | ✓ | ✓ |
| Add variant later | Breaking if exhaustive switch | Same library only |
| Memory | Singleton constants | Can hold unique data per instance |

Use enums for fixed constants (`HttpMethod.GET`). Use sealed classes for variants with different payloads (`ApiSuccess(data)` vs `ApiError(code, message)`).

## Library API design with modifiers

Publishing a Dart package requires intentional modifier choices:

```dart
// Public API — allow extension, prevent fake implementations
base class HttpClient { ... }

// Public contract — allow implementations, prevent extension
interface class AuthProvider {
  Future<User?> getCurrentUser();
}

// Internal implementation — lock down completely
final class _HttpClientImpl extends HttpClient { ... }

// Closed event hierarchy
sealed class DomainEvent {}
class OrderCreated extends DomainEvent { ... }
class PaymentReceived extends DomainEvent { ... }
```

Document modifier choices in package README — consumers need to know if they can extend, implement, or must compose.

## Breaking changes from Dart 2 migration

Packages that were subclassable in Dart 2 break consumers on Dart 3 upgrade:

```dart
// Dart 2: consumers could extend anywhere
class Vehicle {}

// Dart 3 default: compile error for external extends
// Fix: explicitly mark intent
base class Vehicle {}  // if extension was intended
final class Vehicle {}  // if extension was never intended
```

Run `dart analyze` on all dependent packages after adding modifiers. Publish migration guide for package consumers.

## Failure modes

- **sealed subclass in wrong library** — compile error; all variants must be same library
- **final class blocks testing** — Mockito can't extend; use interface abstraction instead
- **Missing modifier on public API** — accidentally blocks intended extension in Dart 3
- **Over-using sealed** — not every class hierarchy needs sealing; open hierarchies valid for plugin systems

## Production checklist

- State machines and API results modeled as sealed classes
- Public API classes have explicit modifier matching intended usage
- Package migration guide documents modifier changes from Dart 2
- Test doubles use interface classes, not extends of final classes
- Analyzer run with `--fatal-infos` after modifier adoption
- sealer variants in same file or part file

Run `dart fix --apply` after Dart 3 upgrade to auto-add `base` modifier to classes that were implicitly extendable — reduces manual migration effort for large codebases.

## Resources

- [Dart class modifiers documentation](https://dart.dev/language/class-modifiers)
- [Dart 3 migration guide](https://dart.dev/resources/dart-3-migration)
- [Sealed types and patterns](https://dart.dev/language/patterns#sealed-types)
- [Effective Dart: Design](https://dart.dev/effective-dart/design)
