---
title: "Dart Extension Types: Zero-Cost Wrappers"
slug: "dart-extension-types-zero-cost"
description: "Use Dart 3.3 extension types for type-safe IDs and units with zero runtime overhead—representation, implements, and interop patterns."
datePublished: "2025-06-14"
dateModified: "2025-06-14"
tags: ["Flutter", "Dart"]
keywords: "Dart extension types, zero-cost abstraction, type-safe IDs, extension type representation, Dart 3.3"
faq:
  - q: "What is a Dart extension type?"
    a: "Extension types wrap an existing representation type (int, String, List) with a distinct static type at compile time without creating a wrapper object at runtime. UserId typed as extension type over String erases to String in compiled JS and native code—zero allocation cost unlike wrapper classes."
  - q: "How are extension types different from typedefs?"
    a: "Typedefs are aliases—UserId and String are interchangeable to the type checker. Extension types are distinct types—you cannot pass String where UserId is expected without explicit conversion. Extension types prevent mixing incompatible IDs while keeping runtime representation."
  - q: "Can extension types implement interfaces?"
    a: "Yes—extension type UserId implements Comparable<UserId> adds methods and interface conformance while representation stays String. You cannot extend classes. Use implements for Comparable, formatting, or platform interop facades."
---

Strong typing for `UserId` vs `OrderId` as plain `String` typedefs catches nothing—both interchange freely and bugs ship. Wrapper classes fix typing but allocate on every construction. Extension types split the difference: compile-time distinct types, runtime same representation. Dart 3.3's answer to Kotlin inline value classes and Rust newtypes.

## Basic extension type

```dart
extension type UserId(String id) {
  bool get isValid => id.length >= 8;
  String get display => id.substring(0, 4);
}

extension type OrderId(String id) {}

void ship(OrderId order, UserId user) { /* ... */ }

// ship(user, order); // compile error — types differ
ship(OrderId('ord_123'), UserId('usr_456')); // OK
```

Representation is `String`; at runtime `UserId('x')` is just `'x'`.

## Numeric representation

```dart
extension type Meters(double value) {
  Meters operator +(Meters other) => Meters(value + other.value);
}

extension type Kilometers(double value) {
  Kilometers operator *(int scalar) => Kilometers(value * scalar);
}

// Meters + Kilometers // error without explicit conversion
```

Prevents unit confusion in physics and layout math.

## implements interfaces

```dart
extension type Percentage(int basisPoints) implements Comparable<Percentage> {
  static Percentage fromWhole(int percent) => Percentage(percent * 100);

  @override
  int compareTo(Percentage other) => basisPoints.compareTo(other.basisPoints);

  double get asDouble => basisPoints / 10000;
}
```

## Interop and JSON

```dart
extension type JsonMap(Map<String, Object?> _json) {
  String? string(String key) => _json[key] as String?;
  int intOr(String key, int fallback) => _json[key] as int? ?? fallback;
}

// Parse boundary
JsonMap parsePayload(Map<String, Object?> raw) => JsonMap(raw);
```

Distinct type for parsed JSON vs raw map—cast once at boundary.

Serialization:

```dart
extension type UserId(String id) {
  String toJson() => id;
  factory UserId.fromJson(Object? json) => UserId(json as String);
}
```

## vs legacy wrapper class

```dart
// Old: allocates
class UserIdClass {
  final String value;
  UserIdClass(this.value);
}

// Extension type: no allocation
extension type UserId(String id) {}
```

Hot paths creating thousands of IDs per frame benefit measurably in GC pressure.

## Limitations

No runtime type check distinguishes extension types—`identical` and `is` see representation:

```dart
UserId('a') is String // true in some contexts — check docs for current rules
```

Do not rely on `is UserId` for dynamic dispatch—use static types.

Cannot extend classes. Cannot add fields beyond representation—only methods and static members.

Pattern matching treats as representation type in some cases—verify exhaustiveness with sealed wrappers if needed.

## Migration from typedef

```dart
typedef UserId = String; // weak typing

extension type UserId(String id) {} // strong typing, same runtime
```

Update call sites to construct `UserId(raw)` at boundaries; internal code stays typed.

## Flutter example

```dart
extension type RouteName(String name) {
  static RouteName home = RouteName('/home');
  static RouteName settings = RouteName('/settings');
}

void navigate(RouteName route) {
  GoRouter.of(context).go(route.name);
}

navigate(RouteName.home); // not navigate('/home') from random strings
```

## Extension types in API boundaries

The highest-value use is at system boundaries — network, database, platform channels — where untyped strings enter typed code:

```dart
// HTTP client layer
extension type AuthToken(String value) {
  bool get isExpired => JwtDecoder.isExpired(value);
  Map<String, dynamic> get claims => JwtDecoder.decode(value);
}

extension type ApiEndpoint(String path) {
  static ApiEndpoint users = ApiEndpoint('/v2/users');
  static ApiEndpoint orders = ApiEndpoint('/v2/orders');
  Uri resolve(String baseUrl) => Uri.parse('$baseUrl$path');
}

// Usage — compile error if you swap endpoints
Future<User> fetchUser(AuthToken token, UserId id) async {
  final response = await http.get(
    ApiEndpoint.users.resolve(baseUrl).replace(path: '${ApiEndpoint.users.path}/$id'),
    headers: {'Authorization': 'Bearer ${token.value}'},
  );
  return User.fromJson(jsonDecode(response.body));
}
```

Construct extension types once at the boundary (`UserId.fromJson`, `AuthToken.fromStorage`); internal code never sees raw strings.

## Collections as representation

Extension types work over any representation, not just primitives:

```dart
extension type ReadonlyBytes(Uint8List bytes) {
  int get length => bytes.length;
  int operator [](int index) => bytes[index];
  // No mutating methods exposed — compile-time readonly
}

extension type MutableBytes(Uint8List bytes) {
  void writeByte(int offset, int value) => bytes[offset] = value;
}
```

Same underlying `Uint8List`, different capabilities enforced statically. Useful for binary protocol parsing where buffer mutation should be explicit.

## Performance characteristics

Extension types compile away — no wrapper allocation, no indirection:

```dart
// Generates identical JS/native code:
String rawId = 'usr_123';
UserId typedId = UserId('usr_123');
// Both are just String at runtime
```

Benchmark on hot paths (game loops, sensor streams creating thousands of values per second) shows measurable GC reduction vs wrapper classes. For typical app code, the win is compile-time safety, not performance — but the safety comes free.

## Extension types vs sealed classes

| Need | Extension type | Sealed class |
|---|---|---|
| Distinct primitive IDs | ✓ | Overkill |
| Runtime polymorphism | ✗ | ✓ |
| Pattern matching exhaustiveness | Limited | ✓ |
| Zero allocation | ✓ | Allocates |
| JSON with variants | Awkward | Natural |

Use extension types for newtypes (IDs, units, tokens). Use sealed classes for domain events and state machines. They compose — a sealed class can hold extension type fields.

## Failure modes

- **Runtime type checks fail** — `value is UserId` may not work as expected; extension types erase to representation at runtime
- **JSON deserialization without factory** — casting `json['id'] as String` bypasses typing; always use `UserId.fromJson` at boundary
- **Mixing representation types** — `UserId(42)` fails if representation is String; enforce at construction
- **Over-wrapping** — not every string needs an extension type; use for IDs, tokens, and units where mix-ups cause bugs

## Production checklist

- Extension types for domain IDs at API/storage boundaries
- Factory constructors for JSON parsing (`fromJson`) and validation
- No raw representation types in business logic signatures
- `implements` used for Comparable, formatting where needed
- Language version 3.3+ in pubspec.yaml
- Analyzer enforces construction at boundaries, not deep in call stack

## Resources

- [Dart extension types documentation](https://dart.dev/language/extension-types)
- [Dart 3.3 release notes](https://dart.dev/resources/whats-new#dart-3-3)
- [Extension type spec](https://github.com/dart-lang/language/blob/main/accepted/2.18/extension-types/feature-specification.md)
- [Effective Dart: Types](https://dart.dev/effective-dart/design#types)
