---
title: "Local Databases with Drift"
slug: "flutter-drift-sqlite-orm"
description: "Type-safe SQLite in Flutter with Drift: table definitions, migrations, streams, and the patterns that beat raw sqflite for complex local data."
datePublished: "2024-10-28"
dateModified: "2024-10-28"
tags: ["Flutter", "Dart"]
keywords: "Flutter Drift, SQLite Flutter, drift ORM, type-safe SQL Dart, Flutter local database"
faq:
  - q: "What is Drift in Flutter?"
    a: "Drift (formerly Moor) is a reactive SQLite persistence library for Dart and Flutter. You define tables as Dart classes, generate type-safe query code with drift_dev, and get Stream-based watch queries that emit on data changes. It wraps sqflite on mobile and sqlite3 on desktop with a unified API."
  - q: "How is Drift different from sqflite?"
    a: "sqflite exposes raw SQL strings—you manually parse rows into maps. Drift generates typed DAOs, compile-time query validation, migration helpers, and reactive streams. sqflite is lighter for trivial key-value storage; Drift wins when schemas grow beyond a few tables or you need observable queries."
  - q: "How do Drift migrations work?"
    a: "Set schemaVersion on your database class and implement migration strategy in onUpgrade. Use migrator.addColumn, createTable, and custom SQL for complex changes. drift_dev can generate step-by-step migration tests. Always increment schemaVersion and test migrations against copies of production databases."
---

Raw `sqflite` worked until we needed six related tables, reactive UI updates when any row changed, and migrations that didn't corrupt user data on upgrade. Drift—SQLite with generated type safety and stream queries—turned 200 lines of stringly-typed SQL into table classes and compile-time checked queries. The learning curve is one afternoon; the payoff lasts the project's lifetime.

## Project setup

```yaml
dependencies:
  drift: ^2.20.0
  sqlite3_flutter_libs: ^0.5.24
  path_provider: ^2.1.4
  path: ^1.9.0

dev_dependencies:
  drift_dev: ^2.20.0
  build_runner: ^2.4.12
```

Define tables:

```dart
import 'package:drift/drift.dart';

class Tasks extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get title => text().withLength(min: 1, max: 200)();
  BoolColumn get completed => boolean().withDefault(const Constant(false))();
  DateTimeColumn get dueDate => dateTime().nullable()();
}
```

Database class:

```dart
@DriftDatabase(tables: [Tasks])
class AppDatabase extends _$AppDatabase {
  AppDatabase(QueryExecutor e) : super(e);

  @override
  int get schemaVersion => 1;

  static AppDatabase open() {
    return AppDatabase(_openConnection());
  }
}

LazyDatabase _openConnection() {
  return LazyDatabase(() async {
    final dir = await getApplicationDocumentsDirectory();
    final file = File(p.join(dir.path, 'app.db'));
    return NativeDatabase.createInBackground(file);
  });
}
```

Run codegen:

```bash
dart run build_runner build --delete-conflicting-outputs
```

## CRUD operations

Drift generates methods on `_$AppDatabase`:

```dart
// Insert
Future<int> addTask(String title) {
  return into(tasks).insert(TasksCompanion.insert(title: title));
}

// Query all
Future<List<Task>> getAllTasks() => select(tasks).get();

// Update
Future<bool> toggleComplete(Task task) {
  return update(tasks).replace(task.copyWith(completed: !task.completed));
}

// Delete
Future<int> deleteTask(int id) {
  return (delete(tasks)..where((t) => t.id.equals(id))).go();
}
```

Custom queries with type safety:

```dart
Future<List<Task>> overdueTasks() {
  final now = DateTime.now();
  return (select(tasks)
        ..where((t) => t.dueDate.isSmallerThanValue(now))
        ..where((t) => t.completed.equals(false)))
      .get();
}
```

## Reactive streams for UI

Drift's killer feature—UI rebuilds when data changes:

```dart
Stream<List<Task>> watchAllTasks() => select(tasks).watch();

// In widget
StreamBuilder<List<Task>>(
  stream: database.watchAllTasks(),
  builder: (_, snapshot) {
    final tasks = snapshot.data ?? [];
    return ListView.builder(
      itemCount: tasks.length,
      itemBuilder: (_, i) => TaskTile(task: tasks[i]),
    );
  },
)
```

With Riverpod:

```dart
@Riverpod(keepAlive: true)
Stream<List<Task>> taskList(TaskListRef ref) {
  return ref.watch(databaseProvider).watchAllTasks();
}
```

## Joins and relations

```dart
class Categories extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get name => text()();
}

class TaskCategories extends Table {
  IntColumn get taskId => integer().references(Tasks, #id)();
  IntColumn get categoryId => integer().references(Categories, #id)();
}

Future<List<TaskWithCategory>> tasksWithCategories() {
  final query = select(tasks).join([
    innerJoin(taskCategories, taskCategories.taskId.equalsExp(tasks.id)),
    innerJoin(categories, categories.id.equalsExp(taskCategories.categoryId)),
  ]);
  return query.map((row) {
    return TaskWithCategory(
      task: row.readTable(tasks),
      category: row.readTable(categories),
    );
  }).get();
}
```

## Migrations

```dart
@override
int get schemaVersion => 2;

@override
MigrationStrategy get migration => MigrationStrategy(
  onCreate: (m) async => await m.createAll(),
  onUpgrade: (m, from, to) async {
    if (from < 2) {
      await m.addColumn(tasks, tasks.priority);
    }
  },
);
```

Test migrations:

```dart
test('migration from v1 to v2 preserves data', () async {
  // Create v1 schema, insert data, upgrade, verify
});
```

Export schema snapshots with `drift_dev schema dump` for CI migration tests.

## Transactions

```dart
Future<void> bulkImport(List<TaskInsert> items) {
  return transaction(() async {
    for (final item in items) {
      await into(tasks).insert(item);
    }
  });
}
```

All operations in a transaction succeed or roll back atomically.

### Drift vs alternatives

| Library | Type | Best for |
|---------|------|----------|
| Drift | SQL ORM | Relational data, complex queries |
| Isar | NoSQL | Object store, fast reads |
| Hive | Key-value | Simple caching |
| sqflite | Raw SQL | Minimal deps, tiny schemas |

Choose Drift when you need SQL expressiveness with Dart ergonomics and reactive queries.

### Drift on multiple platforms

Desktop uses NativeDatabase directly; web experimental support uses WasmDatabase.open. Configure conditional imports:

```dart
import 'connection/native.dart' if (dart.library.html) 'connection/web.dart';
```

Run migrations on all platforms in CI—even if mobile is primary, desktop developers hit schema mismatches first. Export schema snapshots per version for drift schema steps testing.

Use drift_db_viewer in debug builds for inspecting local database during QA—attach to app documents directory. Encrypt sensitive columns at application level if SQLCipher full-database encryption isn't required; Drift supports custom statements for ATTACH encrypted databases when needed.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

Schedule a quarterly review of this implementation against current SDK release notes—Flutter and cloud providers ship breaking changes on six-month cadences, and assumptions that held last year may need adjustment. Capture before-and-after metrics when you change configuration so regressions are obvious in retrospect rather than debated from memory.

Version-pin dependencies mentioned here in your pubspec.lock or infrastructure modules, and note the Flutter/Dart SDK constraint your team validated. Upgrading without re-running the verification steps in this article is the most common source of regressions. If something fails after an upgrade, compare release notes first, then your git history for the last known-good configuration.

## Resources

- [Drift documentation](https://drift.simonbinder.eu/docs/getting-started/)
- [Drift package](https://pub.dev/packages/drift)
- [Table definitions guide](https://drift.simonbinder.eu/docs/getting-started/advanced_dart_tables/)
- [Migrations in Drift](https://drift.simonbinder.eu/docs/migrations/)
- [Stream queries](https://drift.simonbinder.eu/docs/stream_queries/)
