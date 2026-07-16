---
title: "SQLDelight in Kotlin Multiplatform Projects"
slug: "kotlin-multiplatform-sqldelight"
description: "SQLDelight generates type-safe Kotlin from your SQL and runs on Android, iOS, and JVM. How it works in KMP, drivers per platform, migrations, and reactive queries."
datePublished: "2024-06-12"
dateModified: "2024-06-12"
tags: ["Kotlin", "Kotlin Multiplatform", "Databases"]
keywords: "SQLDelight, Kotlin Multiplatform database, type-safe SQL, SQLDelight KMP, SQL migrations, reactive queries coroutines"
faq:
  - q: "How is SQLDelight different from Room?"
    a: "SQLDelight takes SQL as the source of truth: you write .sq files and it generates type-safe Kotlin APIs from them, verifying your queries at compile time against the schema. Room is Android-only and generates code from annotated Kotlin/Java DAOs. The decisive difference for multiplatform is that SQLDelight targets Android, iOS, JVM, and more, while Room does not run on iOS."
  - q: "Does SQLDelight require a different driver per platform?"
    a: "Yes. SQLDelight defines a common SqlDriver interface and ships platform drivers: AndroidSqliteDriver on Android, NativeSqliteDriver on iOS/native, and a JDBC driver on the JVM. You provide the correct driver via expect/actual or dependency injection, and the generated query code is identical across platforms because it only depends on the driver interface."
  - q: "Can SQLDelight return reactive streams?"
    a: "Yes. With the coroutines extension, any query exposes asFlow() plus mapToList/mapToOne operators, emitting a fresh result whenever the underlying tables change. This gives you a reactive database layer that works across platforms, so a Compose or SwiftUI layer can observe query results without manual invalidation."
---

SQLDelight inverts the usual ORM relationship: instead of generating SQL from your code, it generates type-safe Kotlin from your SQL. You write plain `.sq` files, SQLDelight parses them against your schema at compile time, and emits Kotlin APIs where every query is a checked function with typed parameters and results. The reason it's the default database choice for Kotlin Multiplatform is simple — it runs everywhere Kotlin does (Android, iOS, JVM, native, even JS), because it abstracts the actual SQLite engine behind a common driver interface, with a real platform driver per target. Room can't follow you to iOS; SQLDelight can.

I've built the persistence layer of a KMP app on SQLDelight, sharing the entire data layer between Android and iOS, and the standout property is that a typo in a column name or a wrong-arity query is a *compile error*, not a runtime crash on some user's device. SQL you write is SQL SQLDelight validates. That alone changes how confident I am shipping schema changes.

## SQL is the source of truth

You define tables and queries in `.sq` files, and the generated Kotlin mirrors them exactly:

```sql
-- User.sq
CREATE TABLE user (
    id TEXT NOT NULL PRIMARY KEY,
    name TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

selectAll:
SELECT * FROM user ORDER BY created_at DESC;

selectById:
SELECT * FROM user WHERE id = ?;

insert:
INSERT INTO user(id, name, created_at) VALUES (?, ?, ?);
```

Each labeled statement (`selectAll`, `selectById`, `insert`) becomes a typed Kotlin function on a generated `UserQueries` class:

```kotlin
val users: List<User> = database.userQueries.selectAll().executeAsList()
val one: User? = database.userQueries.selectById("42").executeAsOneOrNull()
database.userQueries.insert(id = "42", name = "Ada", created_at = now)
```

The parameters are typed, the result `User` is a generated data class, and the SQL was checked against the schema when you compiled. Rename `name` to `full_name` in the table and every query referencing `name` fails to compile until you fix it. This is the same "let the compiler enforce the contract" philosophy behind [modeling domains with sealed interfaces](https://blog.michaelsam94.com/kotlin-sealed-interfaces-domain-modeling/) — push correctness to compile time.

## One schema, one driver per platform

The multiplatform story hinges on a single interface, `SqlDriver`, with a concrete implementation per target. Your generated queries only depend on the interface, so they're literally the same code everywhere; you just hand them the right driver.

```kotlin
// commonMain — the shared factory contract
expect class DriverFactory {
    fun createDriver(): SqlDriver
}
```

```kotlin
// androidMain
actual class DriverFactory(private val context: Context) {
    actual fun createDriver(): SqlDriver =
        AndroidSqliteDriver(AppDatabase.Schema, context, "app.db")
}
```

```kotlin
// iosMain
actual class DriverFactory {
    actual fun createDriver(): SqlDriver =
        NativeSqliteDriver(AppDatabase.Schema, "app.db")
}
```

Android gets `AndroidSqliteDriver`, iOS gets `NativeSqliteDriver` (which uses the system SQLite via Kotlin/Native), and the JVM gets a JDBC driver. The `AppDatabase` and all `*Queries` are shared. This is the same `expect`/`actual` seam you use for other platform specifics, and it keeps the *entire query layer* in `commonMain` — the driver is the only platform-specific line. That shared data layer is exactly what a [SwiftUI front end consuming the KMP module](https://blog.michaelsam94.com/kotlin-multiplatform-swiftui-interop/) sits on top of.

## Reactive queries with coroutines

Add the coroutines extension and any query becomes an observable `Flow` that re-emits whenever the underlying tables change:

```kotlin
fun observeUsers(): Flow<List<User>> =
    database.userQueries.selectAll()
        .asFlow()
        .mapToList(Dispatchers.IO)
```

Insert or update a `user` row anywhere and this `Flow` emits the fresh list — no manual invalidation, no observer registration. This turns SQLDelight into a reactive source of truth: your UI observes queries, writes happen wherever, and the reads update themselves. On Android you collect this in a `ViewModel` and expose it via [`stateIn`](https://blog.michaelsam94.com/kotlin-flow-sharein-statein-hot-flows/); on iOS you bridge the `Flow` to Swift. The dedup and change-notification are handled by SQLDelight tracking which tables each query touches.

## Migrations are versioned SQL

Schema changes go in numbered `.sqm` migration files, and SQLDelight applies them in order based on the schema version:

```sql
-- 1.sqm  (migrate from version 1 to 2)
ALTER TABLE user ADD COLUMN email TEXT;
```

SQLDelight can verify migrations against your schema at build time, catching a migration that leaves the database in a state your queries don't expect — again, at compile time rather than in production. Two habits I enforce: keep migrations forward-only and never edit a shipped one (write a new migration instead), and turn on the schema verification and migration tests the Gradle plugin offers. Databases are the place where a mistake is expensive and hard to reverse, so the extra compile-time checking is worth every second it adds to the build.

## Where SQLDelight fits vs the alternatives

| Concern | SQLDelight | Room | Realm |
|---|---|---|---|
| Multiplatform (incl. iOS) | Yes | Android only | Yes |
| Source of truth | Your SQL | Annotated DAOs | Object model |
| Compile-time query checking | Yes | Partial | No |
| Reactive queries | Flow extension | Flow/LiveData | Live objects |
| Learning curve | Know SQL | Know annotations | Proprietary API |

The honest trade-off: SQLDelight makes you *write SQL*. If your team wants to avoid SQL entirely and you're Android-only, Room's annotation model may feel friendlier. But for KMP there's no real contest — Room doesn't run on iOS — and I'd argue that making SQL explicit is a feature, not a tax. You see exactly what query runs, you can optimize it directly, and you never fight an ORM guessing wrong about your intent. On a project sharing data logic across two platforms, having one validated SQL schema drive both apps eliminated an entire class of "the Android and iOS data layers drifted apart" bugs.

## Getting started, briefly

Add the Gradle plugin, declare your database in the build config (package name, schema location), drop `.sq` files in `src/commonMain/sqldelight`, and the plugin generates the `AppDatabase` and query classes on build. Wire a `DriverFactory` per platform, construct `AppDatabase(driver)`, and inject it wherever you need data. From there it's just calling typed query functions and observing `Flow`s. The setup cost is an afternoon; the payoff is a single, compile-checked, reactive data layer serving every platform your Kotlin code targets.

## Resources

- [SQLDelight documentation](https://sqldelight.github.io/sqldelight/)
- [SQLDelight coroutines extensions](https://sqldelight.github.io/sqldelight/2.0.2/multiplatform_sqlite/coroutines/)
- [SQLite documentation](https://www.sqlite.org/docs.html)
- [Kotlin Multiplatform expect/actual declarations](https://kotlinlang.org/docs/multiplatform-expect-actual.html)
