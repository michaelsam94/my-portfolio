---
title: "Hive vs shared_preferences"
slug: "flutter-hive-vs-shared-preferences"
description: "Choose between Hive and shared_preferences for Flutter local storage: performance, type safety, encryption, migration paths, and when each wins."
datePublished: "2024-11-24"
dateModified: "2024-11-24"
tags: ["Flutter", "Dart"]
keywords: "Hive Flutter, shared_preferences, local storage Flutter, Hive vs SharedPreferences, key value storage Dart"
faq:
  - q: "What is the difference between Hive and shared_preferences?"
    a: "shared_preferences stores primitive key-value pairs via platform-native APIs (NSUserDefaults, SharedPreferences on Android)—simple but limited to basic types. Hive is a pure Dart NoSQL box storage supporting arbitrary objects, collections, lazy boxes, and optional AES encryption with faster read/write for larger datasets."
  - q: "When should I use shared_preferences in Flutter?"
    a: "Use shared_preferences for small app settings—theme mode, onboarding completed flag, last sync timestamp, auth token strings. It's built into most Flutter projects, requires no code generation, and persists across app restarts reliably for simple data under a few hundred KB."
  - q: "Is Hive faster than shared_preferences?"
    a: "Hive benchmarks significantly faster for bulk reads and complex objects because it stores binary data in indexed boxes rather than serializing through platform channels per key. For a handful of settings, the difference is negligible. Hive wins when storing lists of objects, cached API responses, or data exceeding simple string/bool/int/float/double/stringList types."
---

Every Flutter tutorial stores the theme toggle in `shared_preferences`. That's fine until you cache 500 product objects as JSON strings and startup stutters parsing them on the main isolate. Hive stores typed objects in binary boxes; `shared_preferences` delegates to platform key-value stores with type restrictions. Neither replaces SQLite for relational queries—they solve lightweight persistence, differently.

## shared_preferences basics

```yaml
dependencies:
  shared_preferences: ^2.3.2
```

```dart
final prefs = await SharedPreferences.getInstance();

await prefs.setString('auth_token', token);
await prefs.setBool('onboarding_done', true);
await prefs.setStringList('recent_searches', ['flutter', 'dart']);

final token = prefs.getString('auth_token');
```

Supported types: `String`, `int`, `double`, `bool`, `List<String>`.

**Limitations:**

- No custom objects without manual JSON encode/decode.
- Every read/write async (platform channel on older versions; now mostly async API).
- No encryption built-in.
- Not designed for large datasets—everything loads through platform APIs.

Perfect for:

```dart
class SettingsRepository {
  static const _themeKey = 'theme_mode';

  Future<void> saveTheme(ThemeMode mode) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_themeKey, mode.name);
  }

  Future<ThemeMode> loadTheme() async {
    final prefs = await SharedPreferences.getInstance();
    final name = prefs.getString(_themeKey);
    return ThemeMode.values.byName(name ?? 'system');
  }
}
```

## Hive basics

```yaml
dependencies:
  hive: ^2.2.3
  hive_flutter: ^1.1.0

dev_dependencies:
  hive_generator: ^2.0.1
  build_runner: ^2.4.12
```

Initialize once:

```dart
void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Hive.initFlutter();
  Hive.registerAdapter(ProductAdapter());
  await Hive.openBox<Product>('products');
  runApp(MyApp());
}
```

Type adapter:

```dart
@HiveType(typeId: 1)
class Product extends HiveObject {
  @HiveField(0)
  final String id;
  @HiveField(1)
  final String name;
  @HiveField(2)
  final double price;

  Product({required this.id, required this.name, required this.price});
}
```

CRUD:

```dart
final box = Hive.box<Product>('products');

await box.put('42', Product(id: '42', name: 'Widget', price: 9.99));
final product = box.get('42');
await box.delete('42');

// Iterate all
for (final product in box.values) {
  print(product.name);
}
```

## Performance comparison

| Scenario | shared_preferences | Hive |
|----------|-------------------|------|
| Save bool flag | Excellent | Overkill |
| 1000 cached objects | Slow JSON parse | Fast binary read |
| Lazy load large cache | Not supported | LazyBox |
| Encrypted storage | Manual | HiveAesCipher built-in |
| Web support | Yes | Limited |

Benchmark your actual payload—micro-benchmarks lie; real JSON parsing on main thread hurts UX.

## Hive encryption

```dart
final encryptionKey = await _getOrCreateKey(); // 256-bit key in secure storage
await Hive.openBox(
  'secrets',
  encryptionCipher: HiveAesCipher(encryptionKey),
);
```

Store encryption key in `flutter_secure_storage`, not Hive itself.

## Migration between them

Moving from shared_preferences to Hive:

```dart
Future<void> migratePrefsToHive() async {
  final prefs = await SharedPreferences.getInstance();
  final box = await Hive.openBox('settings');

  if (box.isEmpty && prefs.containsKey('auth_token')) {
    box.put('auth_token', prefs.getString('auth_token'));
    await prefs.remove('auth_token');
  }
}
```

Run once on app upgrade. Keep migration idempotent.

## When to skip both

Need SQL queries, joins, migrations → **Drift/sqflite**.

Need fastest object store with indexes → **Isar**.

Need only in-memory session state → **Riverpod/Bloc state**, no persistence.

### Practical decision guide

```
Is it a simple app setting (bool, string, int)?
  → shared_preferences

Is it a list of objects or cache > 100 KB?
  → Hive or Isar

Need relational queries?
  → Drift

Need secure token only?
  → flutter_secure_storage (not either)
```

I've seen teams adopt Hive for three keys because "it's faster." That's unnecessary complexity. Match tool to data shape.

### Migration and type adapters versioning

Hive typeId must remain stable—never reuse IDs after deleting classes. Document typeId registry in team wiki. When changing field layout, increment adapter version with @HiveField new indices and write migration reading old box format before opening new schema.

Hive compact operation reclaims disk periodically—call box.compact() after bulk deletes in cache eviction routines. Monitor box size in debug overlay for features caching large API responses; unbounded cache growth fills device storage over months of use.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

Schedule a quarterly review of this implementation against current SDK release notes—Flutter and cloud providers ship breaking changes on six-month cadences, and assumptions that held last year may need adjustment. Capture before-and-after metrics when you change configuration so regressions are obvious in retrospect rather than debated from memory.

Version-pin dependencies mentioned here in your pubspec.lock or infrastructure modules, and note the Flutter/Dart SDK constraint your team validated. Upgrading without re-running the verification steps in this article is the most common source of regressions. If something fails after an upgrade, compare release notes first, then your git history for the last known-good configuration.

Pair this setup with logging sufficient to diagnose field failures: request identifiers, cache keys, and user-visible error codes. Support teams need traceability from a screenshot to the underlying state without redeploying debug builds.

Encrypt Hive boxes storing tokens — unencrypted Hive on rooted devices exposes session data SharedPreferences would at least fragment.

## Resources

- [shared_preferences package](https://pub.dev/packages/shared_preferences)
- [Hive documentation](https://docs.hivedb.dev/)
- [hive_flutter package](https://pub.dev/packages/hive_flutter)
- [flutter_secure_storage](https://pub.dev/packages/flutter_secure_storage)
- [Isar database (Hive successor)](https://isar.dev/)
