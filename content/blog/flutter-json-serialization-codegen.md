---
title: "JSON Serialization Without the Boilerplate"
slug: "flutter-json-serialization-codegen"
description: "Generate fromJson and toJson in Flutter with json_serializable: annotations, custom converters, nested objects, and build_runner workflows."
datePublished: "2024-12-12"
dateModified: "2024-12-12"
tags: ["Flutter", "Dart"]
keywords: "json_serializable Flutter, JSON codegen Dart, fromJson toJson, build_runner json, Dart serialization"
faq:
  - q: "How does json_serializable work in Flutter?"
    a: "json_serializable is a build_runner code generator that reads @JsonSerializable annotations on Dart classes and generates fromJson and toJson methods in a .g.dart part file. It handles nested objects, lists, enums, and nullable fields with configurable naming conventions and custom type converters."
  - q: "Should I use json_serializable or Freezed for JSON?"
    a: "Use json_serializable alone for simple API DTOs needing serialization only. Use Freezed when you also want immutable copyWith, union types, and equality—Freezed integrates json_serializable for JSON generation. Hand-written fromJson is fine for one or two small classes; codegen pays off at scale."
  - q: "How do I handle snake_case JSON with camelCase Dart fields?"
    a: "Add @JsonSerializable(fieldRename: FieldRename.snake) on the class or configure globally in build.yaml. The generator maps api_field_name to apiFieldName automatically in both directions."
---

I maintained hand-written `fromJson` for thirty API models. The backend renamed one field; seventeen files broke because copy-paste parsers diverged over time. `json_serializable` generates parsing from annotations—change the Dart field, run build_runner, done. JSON serialization codegen is the lowest-friction code generation in Flutter and the one I add to every project on day one.

## Setup

```yaml
dependencies:
  json_annotation: ^4.9.0

dev_dependencies:
  json_serializable: ^6.8.0
  build_runner: ^2.4.12
```

Basic model:

```dart
import 'package:json_annotation/json_annotation.dart';

part 'user.g.dart';

@JsonSerializable()
class User {
  const User({
    required this.id,
    required this.email,
    this.displayName,
  });

  final String id;
  final String email;
  final String? displayName;

  factory User.fromJson(Map<String, dynamic> json) => _$UserFromJson(json);
  Map<String, dynamic> toJson() => _$UserToJson(this);
}
```

Generate:

```bash
dart run build_runner build --delete-conflicting-outputs
```

## Field renaming and exclusions

```dart
@JsonSerializable(fieldRename: FieldRename.snake)
class Product {
  const Product({
    required this.productId,
    required this.unitPrice,
    @JsonKey(includeFromJson: false) this.localOnlyFlag = false,
  });

  final String productId;
  final double unitPrice;
  final bool localOnlyFlag;

  factory Product.fromJson(Map<String, dynamic> json) =>
      _$ProductFromJson(json);
  Map<String, dynamic> toJson() => _$ProductToJson(this);
}
```

`@JsonKey(name: 'custom_api_key')` overrides individual fields.

## Nested objects and lists

```dart
@JsonSerializable()
class Order {
  const Order({
    required this.id,
    required this.items,
    required this.customer,
  });

  final String id;
  final List<OrderItem> items;
  final Customer customer;

  factory Order.fromJson(Map<String, dynamic> json) => _$OrderFromJson(json);
  Map<String, dynamic> toJson() => _$OrderToJson(this);
}

@JsonSerializable()
class OrderItem {
  const OrderItem({required this.sku, required this.quantity});
  final String sku;
  final int quantity;
  factory OrderItem.fromJson(Map<String, dynamic> json) =>
      _$OrderItemFromJson(json);
  Map<String, dynamic> toJson() => _$OrderItemToJson(this);
}
```

Generator recursively generates for nested `@JsonSerializable` types.

## Enums

```dart
enum OrderStatus { pending, shipped, delivered }

@JsonSerializable()
class Shipment {
  const Shipment({required this.status});
  
  @JsonKey(unknownEnumValue: OrderStatus.pending)
  final OrderStatus status;

  factory Shipment.fromJson(Map<String, dynamic> json) =>
      _$ShipmentFromJson(json);
}
```

`unknownEnumValue` handles new API enum values gracefully.

## Custom converters

```dart
class TimestampConverter implements JsonConverter<DateTime, int> {
  const TimestampConverter();

  @override
  DateTime fromJson(int json) =>
      DateTime.fromMillisecondsSinceEpoch(json * 1000);

  @override
  int toJson(DateTime object) => object.millisecondsSinceEpoch ~/ 1000;
}

@JsonSerializable()
class Event {
  const Event({required this.createdAt});
  
  @TimestampConverter()
  final DateTime createdAt;

  factory Event.fromJson(Map<String, dynamic> json) => _$EventFromJson(json);
}
```

Register global converters in `build.yaml`:

```yaml
targets:
  $default:
    builders:
      json_serializable:
        options:
          field_rename: snake
          explicit_to_json: true
```

`explicit_to_json: true` calls `toJson()` on nested objects instead of raw maps.

## Generic responses

```dart
@JsonSerializable(genericArgumentFactories: true)
class ApiResponse<T> {
  const ApiResponse({required this.data, required this.meta});
  final T data;
  final Meta meta;

  factory ApiResponse.fromJson(
    Map<String, dynamic> json,
    T Function(Object? json) fromJsonT,
  ) =>
      _$ApiResponseFromJson(json, fromJsonT);
}

// Usage
final response = ApiResponse<User>.fromJson(
  jsonMap,
  (json) => User.fromJson(json as Map<String, dynamic>),
);
```

### Read-only vs write-only JSON

```dart
@JsonSerializable(createToJson: false)
class ReadOnlyConfig {
  // only fromJson generated
}

@JsonSerializable(createFactory: false)
class WriteOnlyPayload {
  // only toJson generated
}
```

### Testing generated serialization

```dart
test('User JSON round trip', () {
  const user = User(id: '1', email: 'a@b.com', displayName: 'Ada');
  final json = user.toJson();
  final restored = User.fromJson(json);
  expect(restored, user);
});

test('handles null optional fields', () {
  final user = User.fromJson({'id': '1', 'email': 'a@b.com'});
  expect(user.displayName, isNull);
});
```

Commit `.g.dart` files or regenerate in CI—team policy varies.

### json_serializable vs alternatives

| Tool | Notes |
|------|-------|
| json_serializable | Standard, flexible |
| Freezed + json | Immutable + unions |
| dart_mappable | Alternative codegen |
| Manual | OK for < 5 models |

### checked: true for strict parsing

```dart
@JsonSerializable(checked: true)
```

Throws CheckedFromJsonException with field path on type mismatch—surfaces API contract breaks in staging instead of silent zero defaults corrupting business logic.

Part files must stay generated—never manual edit .g.dart. PR checklist item: if model changed, build_runner output included. Conflicts in generated files resolve by regenerating, not manual merge.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

Schedule a quarterly review of this implementation against current SDK release notes—Flutter and cloud providers ship breaking changes on six-month cadences, and assumptions that held last year may need adjustment. Capture before-and-after metrics when you change configuration so regressions are obvious in retrospect rather than debated from memory.

Version-pin dependencies mentioned here in your pubspec.lock or infrastructure modules, and note the Flutter/Dart SDK constraint your team validated. Upgrading without re-running the verification steps in this article is the most common source of regressions. If something fails after an upgrade, compare release notes first, then your git history for the last known-good configuration.

Use `@JsonKey(unknownEnumValue: ...)` for API enums — server adds enum value, app crashes on deserialize without unknown fallback.

## Resources

- [json_serializable package](https://pub.dev/packages/json_serializable)
- [json_annotation](https://pub.dev/packages/json_annotation)
- [JsonSerializable class](https://pub.dev/documentation/json_annotation/latest/json_annotation/JsonSerializable-class.html)
- [JsonKey annotation](https://pub.dev/documentation/json_annotation/latest/json_annotation/JsonKey-class.html)
- [Dart JSON serialization guide](https://dart.dev/libraries/serialization/json)
