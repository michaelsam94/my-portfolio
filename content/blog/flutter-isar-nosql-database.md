---
title: "Fast Local Storage with Isar"
slug: "flutter-isar-nosql-database"
description: "Use Isar for high-performance local storage in Flutter: schemas, indexes, watchers, transactions, and migration from Hive with codegen."
datePublished: "2024-12-06"
dateModified: "2024-12-06"
tags: ["Flutter", "Dart"]
keywords: "Isar Flutter, NoSQL Dart, Isar database, local storage Flutter, Isar vs Hive"
faq:
  - q: "What is Isar database in Flutter?"
    a: "Isar is a fast NoSQL database for Dart and Flutter with ACID transactions, composite indexes, full-text search, and reactive watchers. It uses code generation for type-safe schemas and stores data in binary format optimized for mobile read/write performance."
  - q: "Is Isar better than Hive?"
    a: "Isar is the spiritual successor to Hive by the same author, with better query capabilities, indexes, and multi-isolate support. Hive remains stable for simple key-value boxes; Isar suits apps needing filtering, sorting, pagination, and complex queries on local data without SQL."
  - q: "Does Isar work on Flutter web?"
    a: "Isar supports iOS, Android, macOS, Linux, and Windows. Web support is limited or experimental depending on version—check current pub.dev platform badges. For web-first apps needing local storage, consider drift/wasm or browser IndexedDB wrappers instead."
---

Hive handled our cached products until we needed "filter by category, sort by price, paginate 20 at a time" offline. Hive isn't a query engine—you load the box and filter in Dart. Isar added indexed queries and watchers with microsecond reads on 10,000 objects. If your local storage needs exceed put/get/list, Isar earns its codegen setup cost.

## Setup

```yaml
dependencies:
  isar: ^3.1.0+1
  isar_flutter_libs: ^3.1.0+1
  path_provider: ^2.1.4

dev_dependencies:
  isar_generator: ^3.1.0+1
  build_runner: ^2.4.12
```

Define collection:

```dart
import 'package:isar/isar.dart';

part 'product.g.dart';

@collection
class Product {
  Id id = Isar.autoIncrement;

  @Index(type: IndexType.value)
  late String category;

  late String name;

  @Index()
  late double price;

  DateTime? lastSynced;
}
```

Initialize:

```dart
late Isar isar;

Future<void> initIsar() async {
  final dir = await getApplicationDocumentsDirectory();
  isar = await Isar.open(
    [ProductSchema],
    directory: dir.path,
  );
}
```

Generate:

```bash
dart run build_runner build --delete-conflicting-outputs
```

## CRUD operations

```dart
// Write
await isar.writeTxn(() async {
  await isar.products.put(Product()
    ..category = 'electronics'
    ..name = 'Headphones'
    ..price = 99.99);
});

// Read by id
final product = await isar.products.get(1);

// Delete
await isar.writeTxn(() async {
  await isar.products.delete(1);
});
```

All writes must occur inside `writeTxn`—ACID guaranteed.

## Queries with filters and sort

```dart
final results = await isar.products
    .filter()
    .categoryEqualTo('electronics')
    .priceBetween(50, 200)
    .sortByPrice()
    .limit(20)
    .findAll();
```

Composite indexes speed multi-field filters—define in schema:

```dart
@Index(composite: [CompositeIndex('category'), CompositeIndex('price')])
late String category;
```

Pagination:

```dart
final page = await isar.products
    .where()
    .sortByPriceDesc()
    .offset(pageIndex * 20)
    .limit(20)
    .findAll();
```

## Reactive watchers

UI updates on data change:

```dart
Stream<List<Product>> watchElectronics() {
  return isar.products
      .filter()
      .categoryEqualTo('electronics')
      .watch(fireImmediately: true);
}

// Widget
StreamBuilder<List<Product>>(
  stream: watchElectronics(),
  builder: (_, snapshot) {
    final products = snapshot.data ?? [];
    return ListView.builder(
      itemCount: products.length,
      itemBuilder: (_, i) => ProductTile(product: products[i]),
    );
  },
)
```

Multiple watchers on same collection stay consistent within transactions.

## Bulk import

```dart
await isar.writeTxn(() async {
  await isar.products.putAll(productsFromApi);
});
```

`putAll` in single transaction is orders of magnitude faster than individual puts.

## Full-text search

```dart
@collection
class Article {
  Id id = Isar.autoIncrement;

  @Index(type: IndexType.hash, caseSensitive: false)
  late String title;

  @Index(type: IndexType.hash, elementsType: IndexType.hash)
  List<String> tags = [];
}
```

Query with `.titleContains('flutter', caseSensitive: false)`.

### Migration from Hive

1. Open both databases during migration window.
2. Read Hive box, transform to Isar objects, bulk put.
3. Mark migration complete in shared_preferences.
4. Remove Hive dependency after stable release.

```dart
Future<void> migrateHiveToIsar() async {
  final done = prefs.getBool('isar_migrated') ?? false;
  if (done) return;

  final hiveBox = await Hive.openBox<ProductHive>('products');
  final products = hiveBox.values.map((h) => Product()
    ..category = h.category
    ..name = h.name
    ..price = h.price).toList();

  await isar.writeTxn(() => isar.products.putAll(products));
  await prefs.setBool('isar_migrated', true);
  await hiveBox.close();
}
```

### Isar vs Drift

| Need | Isar | Drift |
|------|------|-------|
| Object queries | Excellent | SQL |
| Relational joins | Limited | Excellent |
| Full-text search | Built-in | FTS5 extension |
| Learning curve | Low (NoSQL) | Medium (SQL) |

Pick Isar for object-heavy caches; Drift for relational offline-first sync.

### Isar multi-isolate access

Isar supports isolates with Isar.open in worker isolate or Isar.getInstance passing existing instance reference—read current docs for your version's isolate story. Heavy writes in background isolate prevent UI jank during bulk sync imports after login.

Isar inspector desktop app connects to running debug app for query debugging—faster than print statements during schema iteration. Index only fields you filter or sort on; over-indexing slows writes on sync-heavy features importing thousands of records on login.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

Schedule a quarterly review of this implementation against current SDK release notes—Flutter and cloud providers ship breaking changes on six-month cadences, and assumptions that held last year may need adjustment. Capture before-and-after metrics when you change configuration so regressions are obvious in retrospect rather than debated from memory.

Version-pin dependencies mentioned here in your pubspec.lock or infrastructure modules, and note the Flutter/Dart SDK constraint your team validated. Upgrading without re-running the verification steps in this article is the most common source of regressions. If something fails after an upgrade, compare release notes first, then your git history for the last known-good configuration.

Pair this setup with logging sufficient to diagnose field failures: request identifiers, cache keys, and user-visible error codes. Support teams need traceability from a screenshot to the underlying state without redeploying debug builds.

## Common production mistakes

Teams get isar nosql database wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Flutter teams implementing isar nosql database often regress performance by rebuilding entire subtrees on every frame, ignoring platform channel latency, or testing only on iOS simulators. Profile on mid-range Android hardware before calling the work done.

## Resources

- [Isar documentation](https://isar.dev/)
- [Isar package](https://pub.dev/packages/isar)
- [Isar schemas and indexes](https://isar.dev/schema.html)
- [Isar queries](https://isar.dev/queries.html)
- [Isar watchers](https://isar.dev/watchers.html)
