---
title: "Sound Null Safety in Practice"
slug: "dart-null-safety-sound-migration"
description: "Migrate and maintain sound null-safe Dart code: nullable types, flow analysis, late variables, and boundary patterns for JSON and platform APIs."
datePublished: "2025-06-23"
dateModified: "2025-06-23"
tags: ["Flutter", "Dart"]
keywords: "Dart null safety, sound null safety, nullable types, late keyword, null safety migration"
faq:
  - q: "What is sound null safety in Dart?"
    a: "Sound null safety guarantees non-nullable types cannot hold null at runtime—the compiler inserts checks and flow analysis proves safety. Unlike nullable annotations in some languages, Dart rejects code that could assign null to String without String?. Runtime null on non-nullable type throws before unsound behavior spreads."
  - q: "When should I use late instead of nullable?"
    a: "Use late when a non-nullable field is initialized after construction but before first read—State initState, dependency injection setup. Use nullable when absence is meaningful business state—optional profile photo, missing API field. late throws LateInitializationError if read before assign; nullable forces explicit handling."
  - q: "How do I handle null from JSON APIs?"
    a: "Parse at boundary with explicit defaults or nullable types—User.fromJson returns nullable fields as Type? and required fields throw on missing. Avoid ! bang operator on API data; use ??, ??=, or early return. json_serializable includeIfNull and required annotations document contract."
---

Null safety migration is mostly done—Dart 3 requires it—but teams still sprinkle `!` on API responses and wonder why production crashes. Sound null safety is only sound when boundaries treat external data as untrusted and the type system reflects optional vs required domain concepts. The mechanics are simple: `?`, `!`, `late`, `??`. The discipline is architectural.

## Nullable vs non-nullable

```dart
String alwaysThere;      // cannot be null
String? maybeThere;      // can be null

void greet(String? name) {
  print('Hello, ${name ?? 'guest'}');
}

void strict(String name) {
  // caller must not pass null — compile error if String? provided
  print('Hello, $name');
}
```

## Flow analysis promotion

```dart
void printLength(String? text) {
  if (text == null) return;
  print(text.length); // text promoted to String
}

void checkFlag(bool? enabled) {
  if (enabled == true) {
    // enabled promoted to bool inside block
  }
}
```

Promotion fails if variable reassigned or captured in closure before use—local final helps:

```dart
final value = maybeNull;
if (value != null) {
  use(value); // promoted
}
```

## late initialization

```dart
class ProfileController {
  late final UserRepository repo;

  ProfileController(UserRepository repository) {
    repo = repository;
  }
}

// Flutter pattern
class _MyState extends State<MyWidget> {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: kDuration);
  }
}
```

`late final` assigns once; `late` without final allows reassignment.

## Avoiding bang operator

```dart
// Bad — crashes if API lies
final name = json['name']! as String;

// Better
final name = json['name'] as String? ?? 'Unknown';

// Best — typed parser
factory User.fromJson(Map<String, dynamic> json) {
  final name = json['name'];
  if (name is! String) throw FormatException('name required');
  return User(name: name, bio: json['bio'] as String?);
}
```

Reserve `!` for invariants proven by logic analyzer cannot see—document why safe.

## Collection and generic variance

```dart
List<String>? nullableList;
List<String?> stringsWithNulls;
// List<String> ≠ List<String?> — map keys often String?, values Object?
```

## Required named parameters

```dart
class Order {
  Order({required this.id, required this.total, this.note});

  final String id;
  final double total;
  final String? note;
}
```

Constructor enforces non-null for required business fields.

## Migration leftovers

```dart
// ignore: avoid_dynamic_calls — audit these
dynamic legacy = fetchLegacy();
final s = legacy as String; // can throw
```

Replace dynamic boundaries with Object? and type checks.

`// @dart=2.9` files should be zero in Dart 3 projects.

## JSON with json_serializable

```dart
@JsonSerializable()
class Account {
  const Account({required this.email, this.phone});

  final String email;
  final String? phone;

  factory Account.fromJson(Map<String, dynamic> json) => _$AccountFromJson(json);
}
```

Run build_runner; nullable fields match optional JSON keys.

## Platform channels

```dart
final result = await channel.invokeMethod<String>('getToken');
if (result == null) {
  throw StateError('Platform returned null token');
}
return result; // promoted String
```

Platform returns are always nullable from type system's view.

## Testing null cases

```dart
test('handles missing bio', () {
  final user = User.fromJson({'name': 'Ada'});
  expect(user.bio, isNull);
});
```

Test null branches explicitly—coverage tools flag untested `?` paths.

## Null-aware operators in depth

Dart provides several operators beyond `?` and `!`:

```dart
// Null-aware access
user?.profile?.avatarUrl  // short-circuits on null

// Null-aware assignment
cache ??= computeExpensive();  // assign only if null

// Null-aware spread
final combined = [...?maybeList, ...requiredList];

// Null assertion cascade — avoid
user!.profile!.avatar!;  // chain of crashes waiting to happen
```

`?.` is preferred over `if (x != null) x.field` for property chains. `??=` is useful for lazy initialization without `late`.

## Null safety in async code

Async gaps break flow analysis promotion:

```dart
Future<void> processUser(String? id) async {
  if (id == null) return;
  await fetchProfile(id);  // ERROR: id might be null after await
  print(id.length);        // promotion lost across async gap
}
```

Fix with local final:

```dart
Future<void> processUser(String? id) async {
  final userId = id;
  if (userId == null) return;
  await fetchProfile(userId);
  print(userId.length);  // promoted — local final not reassigned
}
```

This pattern applies everywhere async work sits between null check and use — network calls, file I/O, delays.

## `late` pitfalls in Flutter

Common `LateInitializationError` sources:

```dart
// Bug: accessed before initState completes
class _MyState extends State<MyWidget> {
  late final controller = AnimationController(vsync: this);  // vsync not available at field init

  // Fix: initialize in initState
  late final AnimationController controller;
  @override
  void initState() {
    super.initState();
    controller = AnimationController(vsync: this, duration: kDuration);
  }
}
```

Never use `late` for fields that depend on `BuildContext` or `TickerProvider` — initialize in `initState` or `didChangeDependencies`.

## Generic nullability

Generics and nullability interact confusingly:

```dart
T? nullableGeneric<T>(T? value) => value;  // T might be non-nullable type param
List<String?> listWithNullElements;         // list cannot be null, elements can
List<String>? nullableList;                 // list can be null, elements cannot be null (if String non-nullable)
```

When designing APIs, be explicit: `Future<User?>` returns nullable user; `Future<User>` guarantees user or throws.

## Migration audit checklist

For codebases still carrying null-safety debt:

- [ ] Zero `// @dart=2.9` files remaining
- [ ] `dynamic` usage audited — replace with `Object?` + type checks at boundaries
- [ ] Bang operator (`!`) count trending down — grep and review each usage
- [ ] All JSON parsing uses typed factories, not raw map access with `!`
- [ ] Platform channel results handled as nullable
- [ ] Tests cover null branches for every `?` field in public API

## Failure modes

- **Bang operator on API data** — `json['field']!` crashes when API omits field; use typed parser
- **Promotion lost across async** — null check before await doesn't protect after await
- **late read before assign** — field accessed in constructor body before assignment
- **Nullable generic confusion** — `List<String?>` vs `List<String>?` mix-ups in function signatures
- **Ignoring platform null returns** — MethodChannel results are always `T?` from compiler's view

## Production checklist

- External data parsed at boundary with typed factories
- Bang operator usage documented and minimized (<5 per codebase ideally)
- Async null checks use local final pattern
- `late` fields initialized in initState, not at declaration
- json_serializable with explicit nullable/required annotations
- Null branch tests for every public nullable field

## Resources

- [Dart null safety guide](https://dart.dev/null-safety)
- [Understanding null safety (deep dive)](https://dart.dev/null-safety/understanding-null-safety)
- [Dart 3 migration](https://dart.dev/resources/dart-3-migration)
- [json_serializable package](https://pub.dev/packages/json_serializable)
