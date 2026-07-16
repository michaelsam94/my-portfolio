---
title: "Immutable Models with Freezed"
slug: "flutter-freezed-data-classes"
description: "Generate immutable Dart models with Freezed: unions, copyWith, JSON serialization, and the patterns that replace hand-written boilerplate safely."
datePublished: "2024-11-15"
dateModified: "2024-11-15"
tags: ["Flutter", "Dart"]
keywords: "Flutter Freezed, immutable Dart models, freezed union, copyWith Dart, json_serializable freezed"
faq:
  - q: "What is Freezed in Dart?"
    a: "Freezed is a code generator for immutable data classes, unions (sealed class alternatives), and exhaustive pattern matching. It generates copyWith, equality, hashCode, and toString. Combined with json_serializable, it produces fromJson/toJson for API models with minimal hand-written code."
  - q: "How is Freezed different from Equatable?"
    a: "Equatable only adds value equality—you still write copyWith, constructors, and serialization manually. Freezed generates the full immutable class including deep copyWith for nested objects and union types for state machines. Equatable suits simple classes; Freezed suits models and UI state."
  - q: "Can I use Freezed with json_serializable?"
    a: "Yes—add @JsonSerializable and factory fromJson to Freezed classes. Run build_runner once to generate both .freezed.dart and .g.dart files. Use @Freezed(toJson: false) if you only deserialize from API."
---

I counted 847 lines of hand-written model code in one feature—constructors, copyWith, equality, JSON parsing, all drifting out of sync with the API. Freezed replaced it with annotated class definitions and generated the rest. Immutable models aren't a style preference in Flutter; they're how you keep Bloc state predictable and prevent "I mutated the list in place and the UI didn't rebuild" bugs.

## Setup

```yaml
dependencies:
  freezed_annotation: ^2.4.4
  json_annotation: ^4.9.0

dev_dependencies:
  freezed: ^2.5.7
  json_serializable: ^6.8.0
  build_runner: ^2.4.12
```

Basic model:

```dart
import 'package:freezed_annotation/freezed_annotation.dart';

part 'user.freezed.dart';
part 'user.g.dart';

@freezed
class User with _$User {
  const factory User({
    required String id,
    required String name,
    required String email,
    @Default(false) bool isVerified,
  }) = _User;

  factory User.fromJson(Map<String, dynamic> json) => _$UserFromJson(json);
}
```

Generate:

```bash
dart run build_runner build --delete-conflicting-outputs
```

## copyWith and immutability

```dart
final user = User(id: '1', name: 'Ada', email: 'ada@example.com');
final updated = user.copyWith(name: 'Ada Lovelace');
// user unchanged; updated is new instance
```

Nested copyWith for nested Freezed objects works automatically. Lists are replaced entirely—use spread for append:

```dart
state.copyWith(items: [...state.items, newItem]);
```

## Union types for state machines

Perfect for Bloc/Cubit state:

```dart
@freezed
class AuthState with _$AuthState {
  const factory AuthState.initial() = _Initial;
  const factory AuthState.loading() = _Loading;
  const factory AuthState.authenticated(User user) = _Authenticated;
  const factory AuthState.error(String message) = _Error;
}
```

Exhaustive handling with Dart 3 switch:

```dart
Widget build(BuildContext context) {
  return switch (authState) {
    AuthInitial() => const SizedBox.shrink(),
    AuthLoading() => const CircularProgressIndicator(),
    AuthAuthenticated(:final user) => HomeScreen(user: user),
    AuthError(:final message) => ErrorView(message: message),
  };
}
```

Compiler warns on missing cases—unlike stringly-typed status enums.

## JSON serialization patterns

**Snake case API:**

```dart
@freezed
class Product with _$Product {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory Product({
    required String productId,
    required double unitPrice,
  }) = _Product;

  factory Product.fromJson(Map<String, dynamic> json) =>
      _$ProductFromJson(json);
}
```

**Custom converters:**

```dart
@freezed
class Event with _$Event {
  const factory Event({
    required String id,
    @TimestampConverter() required DateTime createdAt,
  }) = _Event;

  factory Event.fromJson(Map<String, dynamic> json) => _$EventFromJson(json);
}

class TimestampConverter implements JsonConverter<DateTime, int> {
  const TimestampConverter();
  @override
  DateTime fromJson(int json) =>
      DateTime.fromMillisecondsSinceEpoch(json * 1000);
  @override
  int toJson(DateTime object) => object.millisecondsSinceEpoch ~/ 1000;
}
```

**Read-only API models:**

```dart
@Freezed(toJson: false)
class ApiResponse with _$ApiResponse {
  const factory ApiResponse({required String status}) = _ApiResponse;
  factory ApiResponse.fromJson(Map<String, dynamic> json) =>
      _$ApiResponseFromJson(json);
}
```

## @Default and nullable fields

```dart
const factory Settings({
  @Default(ThemeMode.system) ThemeMode themeMode,
  @Default(true) bool notificationsEnabled,
  String? locale,
}) = _Settings;
```

Defaults apply in constructor and fromJson when key absent.

## Private constructor for methods

Add instance methods to Freezed classes:

```dart
@freezed
class Cart with _$Cart {
  const Cart._(); // enables custom methods
  const factory Cart({required List<CartItem> items}) = _Cart;

  double get total => items.fold(0, (sum, i) => sum + i.price);
  bool get isEmpty => items.isEmpty;
}
```

### Testing Freezed models

Equality works out of the box:

```dart
test('copyWith preserves other fields', () {
  final a = User(id: '1', name: 'A', email: 'a@b.com');
  final b = a.copyWith(name: 'B');
  expect(a.email, b.email);
  expect(a == b, isFalse);
});
```

JSON round-trip:

```dart
test('fromJson toJson round trip', () {
  final json = {'id': '1', 'name': 'Ada', 'email': 'a@b.com', 'is_verified': false};
  final user = User.fromJson(json);
  expect(user.toJson(), json);
});
```

### Common issues

1. **Missing part directives** — `part 'user.freezed.dart';` required.
2. **Stale generated files** — run build_runner after annotation changes.
3. **Mutable collections in factory** — pass `List.unmodifiable` or Freezed copies on construction.
4. **Union JSON** — use `@Freezed(unionKey: 'type')` for discriminated deserialization.

### @JsonKey for unknown fields

Ignore unknown API fields to prevent breakage:

```dart
@JsonSerializable(ignoreUnknown: true)
```

When backend adds fields, old app versions continue parsing. Pair with integration tests loading fixture JSON from production API samples updated weekly.

Union types for network Result wrappers pair well with pattern matching in Cubits—sealed API state classes prevent impossible states like simultaneously loading and loaded. Regenerate after API schema changes in same PR as backend deploy to catch mismatches in CI.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

Schedule a quarterly review of this implementation against current SDK release notes—Flutter and cloud providers ship breaking changes on six-month cadences, and assumptions that held last year may need adjustment. Capture before-and-after metrics when you change configuration so regressions are obvious in retrospect rather than debated from memory.

Run build_runner in CI and fail on uncommitted generated files — drift between `.freezed.dart` and source causes cryptic compile errors.

## Resources

- [Freezed package](https://pub.dev/packages/freezed)
- [Freezed documentation](https://pub.dev/packages/freezed#readme)
- [json_serializable](https://pub.dev/packages/json_serializable)
- [Freezed union types guide](https://pub.dev/packages/freezed#union-types)
- [Dart immutable data patterns](https://dart.dev/guides/language/language-tour#class-modifiers)
