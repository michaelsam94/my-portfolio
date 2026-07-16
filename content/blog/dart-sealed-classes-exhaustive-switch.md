---
title: "Sealed Classes and Exhaustive Switch in Dart"
slug: "dart-sealed-classes-exhaustive-switch"
description: "Dart 3 sealed classes give you closed hierarchies and compile-time exhaustive switch. Patterns for Flutter UI state, API results, and domain modeling."
datePublished: "2025-07-02"
dateModified: "2025-07-02"
tags: ["Flutter", "Dart"]
keywords: "Dart sealed class, exhaustive switch, pattern matching, Flutter state management, algebraic data types, Dart 3"
faq:
  - q: "What does sealed mean in Dart 3?"
    a: "A sealed class or interface restricts which libraries can implement or extend its subtypes. The compiler knows the complete set of permitted variants, so a switch over a sealed type must handle every case or fail to compile. This turns missing-case bugs into build errors instead of runtime surprises."
  - q: "When should I use sealed classes instead of enums in Dart?"
    a: "Use enums when each case is a simple constant with no per-case data. Use sealed classes when cases carry different fields — a Loading state with progress, an Error with a message, a Success with a payload. Sealed classes are enums that can hold heterogeneous data per variant."
  - q: "Do sealed classes work with freezed or json_serializable?"
    a: "Yes. Freezed generates sealed union types that pair well with exhaustive switch. You can also hand-write sealed hierarchies and add json_serializable per subtype. The exhaustiveness check applies regardless of whether the subtypes are generated or written manually."
---

The first time I refactored a Flutter screen from three nullable booleans to a sealed class, the diff was smaller than I expected and the payoff was immediate: every `switch` over the new type either compiled completely or told me exactly which case I'd forgotten. Dart 3's sealed classes aren't syntactic sugar — they're a way to make illegal states unrepresentable and let the analyzer enforce it.

If you've written `bool isLoading; String? error; List<Item>? items` and then spent twenty lines guarding impossible combinations, you've already felt the problem sealed classes solve.

## What sealed actually means in Dart

A `sealed class` (or `sealed interface`) declares a closed hierarchy. Only subtypes declared in the same library can implement or extend it:

```dart
sealed class NetworkResult<T> {}

final class Success<T> extends NetworkResult<T> {
  Success(this.data);
  final T data;
}

final class Failure<T> extends NetworkResult<T> {
  Failure(this.message, {this.statusCode});
  final String message;
  final int? statusCode;
}

final class Offline<T> extends NetworkResult<T> {}
```

The `final class` modifier prevents further subclassing outside this file. The compiler now knows `NetworkResult` has exactly three shapes. That closed set is what powers exhaustiveness.

## Exhaustive switch is the payoff

Dart 3 switch expressions and statements can be exhaustive over sealed types:

```dart
Widget buildBody(NetworkResult<List<Product>> result) => switch (result) {
  Success(:final data) => ProductGrid(products: data),
  Failure(:final message) => ErrorBanner(text: message),
  Offline() => const NoConnectionView(),
};
```

No default case. Add a `Pending` variant tomorrow and every switch in the project that doesn't handle it becomes a compile error. In a large Flutter codebase, that's worth more than any linter rule.

Pattern matching destructures in the same breath:

```dart
String userMessage(NetworkResult<Order> result) => switch (result) {
  Success(:final data) => 'Order ${data.id} placed',
  Failure(:final message, statusCode: 503) => 'Service temporarily unavailable',
  Failure(:final message) => message,
  Offline() => 'Check your connection and retry',
};
```

Guard clauses on patterns (`statusCode: 503`) keep logic flat without nested `if` chains.

## Modeling Flutter UI state

Async UI is the canonical use case. Replace this:

```dart
// Every combination is representable, most are nonsense.
class ProductsState {
  final bool loading;
  final List<Product>? products;
  final String? error;
}
```

With:

```dart
sealed class ProductsState {}

final class ProductsLoading extends ProductsState {}

final class ProductsLoaded extends ProductsState {
  ProductsLoaded(this.products);
  final List<Product> products;
}

final class ProductsError extends ProductsState {
  ProductsError(this.message);
  final String message;
}
```

Your `Bloc`, `Riverpod` notifier, or `ChangeNotifier` emits one variant at a time. Widgets pattern-match instead of guessing which nullable field is authoritative. I've found this cuts review comments about "what happens if loading and error are both true" to zero.

## Sealed vs enum vs plain inheritance

| Situation | Tool |
|---|---|
| Fixed constants, no per-case data | `enum` |
| Fixed cases with different payloads | `sealed class` |
| Open extension (plugins, third parties) | plain `class` / `interface` |
| JSON unions with code generation | `freezed` sealed union |

Enums got exhaustiveness first, but they can't carry `Success(data: list)` and `Failure(message: 'timeout')` in the same type cleanly. Sealed classes fill that gap without giving up the closed-set guarantee.

## Practical conventions

Keep the hierarchy in one library file — Dart's exhaustiveness rule depends on the compiler seeing all subtypes. Use `final class` for leaf variants you don't want extended further. Prefer `sealed interface` at the top when subtypes might mix in other interfaces.

For API parsing, define one sealed root and map JSON discriminators to subtypes:

```dart
NetworkResult<Product> parseProductResponse(Map<String, dynamic> json) {
  return switch (json['status']) {
    'ok' => Success(Product.fromJson(json['data'])),
    'error' => Failure(json['message'] as String),
    _ => Failure('Unknown response shape'),
  };
}
```

The outer switch on your sealed type stays exhaustive; the JSON switch handles messy wire formats.

## When not to seal

Don't seal hierarchies that third-party code must extend — plugin systems, event buses with external listeners. Closed types trade flexibility for safety. The moment the set isn't fixed, you lose exhaustiveness and should use a regular class with a documented discriminator field.

## Exhaustive switch with sealed classes

```dart
sealed class Result {}
class Success extends Result { final Data data; }
class Failure extends Result { final Error error; }

String handle(Result r) => switch (r) {
  Success(:final data) => data.toString(),
  Failure(:final error) => error.message,
};
```

Compiler errors on missing case when new subtype added — prefer over free-form string status codes.

## Common production mistakes

Teams get sealed classes exhaustive switch wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of sealed classes exhaustive switch fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When sealed classes exhaustive switch misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Dart language — Sealed classes](https://dart.dev/language/class-modifiers#sealed)
- [Dart language — Patterns](https://dart.dev/language/patterns)
- [Flutter architectural overview](https://docs.flutter.dev/resources/architectural-overview)
- [freezed package for union types](https://pub.dev/packages/freezed)
- [Effective Dart: Design](https://dart.dev/effective-dart/design)
