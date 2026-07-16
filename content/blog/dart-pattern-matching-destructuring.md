---
title: "Pattern Matching and Destructuring in Dart"
slug: "dart-pattern-matching-destructuring"
description: "Use Dart 3 switch expressions, pattern matching, destructuring records, and guarded cases for exhaustive control flow in Flutter apps."
datePublished: "2025-06-26"
dateModified: "2025-06-26"
tags: ["Flutter", "Dart"]
keywords: "Dart pattern matching, switch expressions, destructuring, sealed class switch, record patterns"
faq:
  - q: "What is pattern matching in Dart 3?"
    a: "Pattern matching binds variables by destructuring values—records, objects, lists, maps—and matches shapes in switch/case, if-case, and for-in. Switch expressions with sealed types provide compile-time exhaustiveness. Patterns replace verbose type-check and cast chains."
  - q: "How do switch expressions differ from switch statements?"
    a: "Switch expressions use => syntax and return a value—no break needed. They are expression-oriented: final color = switch (status) { Ok() => green, Error() => red };. Statements use case blocks with fall-through disabled by default in Dart 3."
  - q: "Can I destructure records and objects in patterns?"
    a: "Yes—(x, y) in point patterns, User(name: var n) in object patterns, [first, ...rest] in list patterns. Destructuring assigns local variables directly in case arms, if-case, and for loops."
---

Before Dart 3, `switch` on strings and cascading `if (x is Foo)` casts filled codebases. Pattern matching collapses type check, cast, and destructure into one syntax—especially powerful with `sealed` hierarchies where the analyzer proves you handled every case. Switch expressions assign results inline; object patterns pull fields without manual getters. This is the idiomatic control flow style for new Dart code.

## Switch expressions

```dart
String badge(NetworkStatus status) => switch (status) {
  NetworkStatus.online => 'Connected',
  NetworkStatus.offline => 'Offline',
  NetworkStatus.metered => 'Metered',
};
```

No `break`; each arm is an expression.

## Sealed class exhaustiveness

```dart
sealed class LoadState {}
class Loading extends LoadState {}
class Loaded extends LoadState {
  Loaded(this.data);
  final List<Item> data;
}
class Failed extends LoadState {
  Failed(this.error);
  final Object error;
}

Widget build(LoadState state) => switch (state) {
  Loading() => const CircularProgressIndicator(),
  Loaded(data: var items) => ItemList(items),
  Failed(error: var e) => ErrorMessage(e.toString()),
};
```

Missing case → compile error.

## Object patterns

```dart
void describe(Object obj) {
  switch (obj) {
    case User(name: final n, email: final e):
      print('$n <$e>');
    case Order(id: final id, total: > 1000):
      print('Large order $id');
    case Order(id: final id):
      print('Order $id');
    default:
      print('Unknown');
  }
}
```

Field patterns match public getters or record fields. Relational subpatterns (`> 1000`) add guards inline.

## Record destructuring

```dart
final point = (3, 4);
var (x, y) = point;

switch (point) {
  case (0, 0):
    print('origin');
  case (var a, var b) when a == b:
    print('diagonal');
  default:
    print('$x, $y');
}
```

Named records:

```dart
({String name, int age}) user = (name: 'Ada', age: 36);
if (user case (name: 'Ada', age: var a)) {
  print(a);
}
```

## List patterns

```dart
switch (list) {
  case []:
    print('empty');
  case [single]:
    print('one: $single');
  case [first, second, ...rest]:
    print('$first, $second, +${rest.length}');
}
```

## if-case

```dart
if (response case ApiSuccess(data: final user)) {
  showProfile(user);
} else if (response case ApiError(code: 404)) {
  showNotFound();
}
```

Replaces nested `if (response is ApiSuccess) { final user = response.data; ... }`.

## for-in with patterns

```dart
for (final (index, value) in items.indexed) {
  print('$index: $value');
}

for (final MapEntry(key: k, value: v) in map.entries) {
  print('$k -> $v');
}
```

## Guard clauses

```dart
String classify(int n) => switch (n) {
  < 0 => 'negative',
  0 => 'zero',
  > 0 && < 10 => 'small',
  _ => 'large',
};
```

`_` wildcard matches anything—use when sealed exhaustiveness not required.

## Null patterns

```dart
switch (maybeUser) {
  case null:
    print('signed out');
  case User(name: var n):
    print('hello $n');
}
```

## Flutter routing example

```dart
RouteConfig parseUri(Uri uri) => switch (uri.pathSegments) {
  [] => HomeRoute(),
  ['item', final id] => ItemRoute(id: id),
  ['settings'] => SettingsRoute(),
  _ => NotFoundRoute(),
};
```

## Migration tips

Replace `if (x is T) { x as T }` chains incrementally.

Enable analyzer lint ` exhaustive_cases` for switches on enums and sealed types.

Patterns in assignment require language version 3.0+.

## Pattern matching in async code

Patterns shine in async/network code where responses are sealed hierarchies:

```dart
Future<void> handleResponse(ApiResponse response) async {
  switch (response) {
    case ApiSuccess(data: final user):
      await cacheUser(user);
      navigateToProfile(user);
    case ApiError(statusCode: 401):
      await refreshToken();
      retryLastRequest();
    case ApiError(statusCode: var code) when code >= 500:
      showRetryDialog();
    case ApiError(message: final msg):
      showError(msg);
  }
}
```

Compare to pre-Dart 3:

```dart
if (response is ApiSuccess) {
  final user = response.data;
  await cacheUser(user);
  // ...
} else if (response is ApiError) {
  if (response.statusCode == 401) { /* ... */ }
  // ...
}
```

The pattern version binds variables in the case arm — no repeated casts, no nested ifs.

## JSON parsing with patterns

Parse API responses at the boundary with destructuring:

```dart
sealed class JsonResult {}
class JsonOk extends JsonResult {
  JsonOk(this.data);
  final Map<String, Object?> data;
}
class JsonErr extends JsonResult {
  JsonErr(this.message);
  final String message;
}

JsonResult parseResponse(Map<String, Object?> json) => switch (json) {
  {'status': 'ok', 'data': Map<String, Object?> data} => JsonOk(data),
  {'status': 'error', 'message': String msg} => JsonErr(msg),
  _ => JsonErr('Unknown response shape'),
};
```

Map patterns destructure JSON shapes directly — field names must match keys. Combine with `sealed` result types for exhaustive handling downstream.

## Logical patterns and or-patterns

Dart 3..0+ supports logical combinations:

```dart
String routeAuthority(Uri uri) => switch (uri) {
  Uri(scheme: 'https', host: 'api.example.com') => 'production',
  Uri(scheme: 'https', host: 'staging.example.com') => 'staging',
  Uri(scheme: 'http' || 'https', host: 'localhost') => 'local',
  _ => 'unknown',
};
```

Or-patterns (`||`) match any of several alternatives in one arm. Useful for grouping related cases without duplicating bodies.

## Wildcard and rest patterns in production

The `_` wildcard is for catch-all arms when sealed exhaustiveness isn't required:

```dart
Color statusColor(Status s) => switch (s) {
  Status.active => Colors.green,
  Status.pending => Colors.orange,
  Status.failed => Colors.red,
  _ => Colors.grey,  // deprecated, archived, unknown future values
};
```

For lists, rest patterns preserve tail without copying:

```dart
switch (items) {
  case [first, ...rest] when rest.isEmpty:
    print('Single item: $first');
  case [first, second, ...rest]:
    print('Multi: $first, $second, +${rest.length} more');
}
```

## Migration strategy from legacy switch

Incremental migration path for large codebases:

1. Enable `strict-casts` and `strict-inference` analyzer options
2. Convert enums to sealed classes where new variants are expected
3. Replace `switch` statements with switch expressions on sealed types first — highest value
4. Convert `if (x is T)` chains in new code; leave legacy code until touched
5. Enable `exhaustive_cases` lint for all switches on enums and sealed types

Don't big-bang migrate — pattern matching pays off most in new code and hot paths (routing, state machines, API parsing).

## Failure modes

- **Non-exhaustive switch on sealed class** — compile error after adding new variant; this is the feature working correctly
- **Guard clause order matters** — `case Order(total: > 1000)` must come before `case Order()` or larger orders match the general case first
- **Map pattern typos** — `{'status': 'ok'}` won't match `{'status': 'OK'}`; normalize at parse boundary
- **Over-patterning simple cases** — `if (x case int n)` for a single int check is overkill; use patterns where destructuring adds value

## Production checklist

- Sealed classes for API responses, UI state, and domain events
- Switch expressions for state-to-UI mapping in Flutter builds
- `exhaustive_cases` lint enabled in analysis_options.yaml
- JSON parsed with map patterns at network boundary
- Legacy `if (x is T)` chains migrated incrementally on touch
- Language version 3.0+ enforced in pubspec.yaml

## Resources

- [Dart patterns documentation](https://dart.dev/language/patterns)
- [Switch expressions](https://dart.dev/language/branches#switch-expressions)
- [Pattern types reference](https://dart.dev/language/pattern-types)
- [Dart 3 patterns codelab](https://dart.dev/codelabs/dart-patterns-records)
