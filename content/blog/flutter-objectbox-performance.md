---
title: "High-Performance Storage with ObjectBox"
slug: "flutter-objectbox-performance"
description: "ObjectBox is an embedded NoSQL database built for speed on mobile. Indexes, relations, and sync hooks without the SQLite overhead you did not ask for."
datePublished: "2025-01-25"
dateModified: "2025-01-25"
tags: ["Flutter", "Dart", "Database", "Mobile"]
keywords: "ObjectBox Flutter, embedded database Dart, ObjectBox performance, NoSQL mobile storage, ObjectBox relations"
faq:
  - q: "ObjectBox vs Isar vs Drift—which is fastest?"
    a: "Benchmarks vary by workload, but ObjectBox consistently leads on simple CRUD and relation-heavy reads thanks to its object-oriented storage engine and memory-mapped files. Drift shines when you need SQL, migrations, and complex joins. Profile your actual queries before choosing."
  - q: "Does ObjectBox work offline-first out of the box?"
    a: "ObjectBox is fully local-first—all reads and writes hit on-device storage. Sync to a backend requires ObjectBox Sync or your own replication layer. The database itself does not fetch from network."
  - q: "How do schema changes work in ObjectBox?"
    a: "You modify annotated entity classes and run the ObjectBox generator. Added fields get defaults; removed fields are dropped on open. For non-trivial migrations, use @Property(uid) to preserve field identity across renames."
---

We had a feed screen that loaded 2,000 cached articles from SQLite through Room-style ORM mapping. Scrolling stuttered on mid-range Android—not because of widgets, because the isolate spent 80ms deserializing rows on every pull-to-refresh. Switching that cache to ObjectBox dropped the same query to under 5ms. The UI did not change; the storage engine did.

ObjectBox is an embedded object database for Dart and Flutter. Entities are plain classes with annotations; a generator builds type-safe accessors. Data lives in a binary store optimized for mobile CPUs, not a generic SQL parser executing on a phone.

## Entity definition

```dart
import 'package:objectbox/objectbox.dart';

@Entity()
class Article {
  @Id()
  int id = 0;

  @Unique(onConflict: ConflictStrategy.replace)
  @Index()
  String remoteId;

  String title;
  String body;
  DateTime publishedAt;

  Article({
    this.id = 0,
    required this.remoteId,
    required this.title,
    required this.body,
    required this.publishedAt,
  });
}
```

Run `dart run build_runner build` to produce `objectbox.g.dart` with a `Store` and `Box<Article>` APIs.

## Opening the store

```dart
late final Store store;

Future<void> initObjectBox() async {
  final dir = await getApplicationDocumentsDirectory();
  store = await openStore(directory: '${dir.path}/objectbox');
}

Box<Article> get articleBox => store.box<Article>();
```

Open once at app startup—`Store` is expensive to create, cheap to query. Close on logout if user data must be wiped from disk.

## Queries that stay fast

```dart
final recent = articleBox
  .query(Article_.publishedAt.greaterThan(cutoff.millisecondsSinceEpoch))
  .order(Article_.publishedAt, flags: Order.descending)
  .build()
  .find();

final one = articleBox
  .query(Article_.remoteId.equals('abc-123'))
  .build()
  .findFirst();
```

Use `@Index()` on fields you filter or sort. `@Unique` enforces deduplication on sync ingest—handy when the API resends the same record.

For pagination, combine `limit` and `offset` on the query builder rather than loading everything into Dart and slicing.

## Relations without JOIN pain

```dart
@Entity()
class Author {
  @Id() int id = 0;
  String name;

  final articles = ToMany<Article>();
}

@Entity()
class Article {
  @Id() int id = 0;
  final author = ToOne<Author>();
}
```

`ToMany` and `ToOne` map object graphs directly. Loading an author with articles is a native relation fetch, not N+1 SQL unless you design it that way.

## Writes and transactions

```dart
store.runInTransaction(TxMode.write, () {
  for (final item in batch) {
    articleBox.put(item);
  }
});
```

Batch writes inside a transaction reduce fsync overhead. For sync pipelines ingesting hundreds of objects per second, transactions are non-optional.

## ObjectBox vs SQLite wrappers

SQL excels at ad hoc reporting and server-style queries. ObjectBox excels when your app thinks in objects—cache entities, offline mirrors of REST resources, sensor logs. If your team already standardized on Drift for SQL migrations and FTS, ObjectBox is not a drop-in replacement; it is a different model.

Watch binary store size: ObjectBox is efficient but not magic. Periodically prune expired cache entries.

## Sync and multi-device

ObjectBox Sync (commercial) replicates stores between devices and servers with conflict resolution. Rolling your own? Use `remoteId` plus `@Unique`, track sync cursors in a metadata entity, and apply server deltas in transactions.

## Debugging tips

Enable query logging in debug builds to see slow paths. Use `obx-admin` (ObjectBox admin UI) during development to inspect store contents on desktop targets.

If generator fails after entity renames, assign explicit UIDs with `@Entity(uid: ...)` and `@Property(uid: ...)` so ObjectBox maps old on-disk data to new field names.

## Sync ingest patterns

Production sync rarely inserts one row at a time. Batch API responses in a transaction:

```dart
store.runInTransaction(TxMode.write, () {
  for (final dto in response.items) {
    final article = Article(
      remoteId: dto.id,
      title: dto.title,
      body: dto.body,
      publishedAt: DateTime.parse(dto.publishedAt),
    );
    articleBox.put(article);
  }
});
```

Use `putMany` when available for large batches. Track high-water mark in a metadata box:

```dart
@Entity()
class SyncCursor {
  @Id() int id = 0;
  String key;
  DateTime lastSyncedAt;
}
```

On conflict, `@Unique(onConflict: ConflictStrategy.replace)` on `remoteId` ensures idempotent replays if sync retries after partial failure.

## Query plans and indexes in practice

Profile slow queries in debug with ObjectBox query logging enabled. Add composite indexes when filters combine fields—check ObjectBox docs for supported composite index syntax on your version. Avoid `find()` without limits on tables over 10k rows; paginate with `.query().build().find(offset: n, limit: pageSize)`.

Watch memory when loading relations eagerly—`ToMany` on a list screen may load thousands of child objects. Lazy-load detail relations on tap instead.

## Comparison workflow before committing

Benchmark your actual access patterns against Drift/SQLite on a mid-tier device:

1. Seed 5k–20k rows representative of production
2. Measure p95 read latency for feed query and single lookup
3. Measure cold open time including `openStore`
4. Measure APK size delta with `objectbox_flutter_libs`

ObjectBox wins many cache-heavy mobile workloads; SQL wins ad hoc reporting and FTS-heavy search. Hybrid apps sometimes use ObjectBox for offline cache and Postgres as source of truth—plan reconciliation explicitly.

## Backup and corruption recovery

ObjectBox stores are binary files under app documents. Corruption from sudden power loss is rare but possible—catch open failures and delete store in last resort with full resync from server. Document wipe behavior in privacy policy if user data is local-only.

Export debug snapshots only on internal builds; production exports may contain PII.


## ObjectBox Admin

Use ObjectBox Admin GUI connected to debug builds for inspecting store during development—never enable admin on production builds shipped to users.

## File size monitoring

Track store file MB in analytics opt-in debug panel—runaway cache growth signals missing TTL pruning job.

## Encryption at rest

ObjectBox supports encryption with native API—evaluate if threat model requires beyond OS filesystem encryption; key from flutter_secure_storage.

## Relation cascade deletes

Deleting parent entity orphan relations unless configured—verify `@Entity` relation remove behavior in docs when designing sync delete events.

## Resources

- [ObjectBox Flutter documentation](https://docs.objectbox.io/getting-started)
- [objectbox-dart on pub.dev](https://pub.dev/packages/objectbox)
- [ObjectBox query API](https://docs.objectbox.io/queries)
- [ObjectBox relations guide](https://docs.objectbox.io/relations)
- [objectbox_flutter_libs package](https://pub.dev/packages/objectbox_flutter_libs)
