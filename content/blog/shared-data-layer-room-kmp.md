---
title: "A Shared Data Layer with Room and Kotlin Multiplatform"
slug: "shared-data-layer-room-kmp"
description: "Build a shared offline data layer with Room on Kotlin Multiplatform: KMP setup, expect/actual database builders, migrations, and sharing DAOs across Android and iOS."
datePublished: "2026-04-13"
dateModified: "2026-04-13"
tags: ["Kotlin Multiplatform", "Room", "Android", "iOS"]
keywords: "Room KMP, Room Multiplatform, shared data layer, KMP database, offline storage, SQLite, expect actual"
faq:
  - q: "Does Room support Kotlin Multiplatform?"
    a: "Yes. Room added Kotlin Multiplatform support so a single Room database definition — entities, DAOs, and the database class — can run on Android, iOS, and JVM. It uses the SQLite driver abstraction under the hood, with a platform-specific driver on each target."
  - q: "How do you create a Room database in a KMP shared module?"
    a: "Define the entities, DAOs, and RoomDatabase in commonMain, then provide a platform-specific database builder via expect/actual — Android supplies a Context, iOS supplies a documents-directory path. Both hand the builder a BundledSQLiteDriver so behavior is consistent."
  - q: "Should I share the whole data layer or just the database?"
    a: "Share the database, DAOs, and repository logic in commonMain, and keep platform-specific concerns — file paths, keychain access, background scheduling — behind expect/actual or dependency injection. The repository API stays common; the wiring is per-platform."
---

For a long time, "share your business logic with Kotlin Multiplatform, but keep the database native" was the pragmatic advice — SQLDelight covered KMP, Room was Android-only. That changed when Room shipped Kotlin Multiplatform support. Now a single Room database — the same `@Entity`, `@Dao`, and `RoomDatabase` you already know — can back an offline data layer on Android and iOS from one `commonMain` source set. For a Kotlin-heavy team, that's a big deal: your entire persistence layer becomes shared code, and you keep the Room API you're fluent in.

I've built shared data layers both ways, and Room-on-KMP removes the main reason teams used to duplicate persistence. Here's how it fits together, including the `expect`/`actual` seam that trips people up and how migrations work across platforms.

## The architecture: common logic, platform wiring

The shape that works: everything about *what* the data is lives in `commonMain`; everything about *where the file goes and how the platform hands it over* lives in the platform source sets. Your repository — the API the rest of the app calls — is fully common. This is the same [Kotlin Multiplatform production](https://blog.michaelsam94.com/kotlin-multiplatform-production-guide/) principle applied to persistence: share the boring, isolate the platform.

```kotlin
// commonMain — pure Room, shared by every target
@Entity(tableName = "charge_session")
data class ChargeSessionEntity(
    @PrimaryKey val id: String,
    val chargerId: String,
    val startedAt: Long,
    val energyWh: Int,
    val synced: Boolean = false,
)

@Dao
interface ChargeSessionDao {
    @Query("SELECT * FROM charge_session ORDER BY startedAt DESC")
    fun observeAll(): Flow<List<ChargeSessionEntity>>

    @Upsert suspend fun upsert(session: ChargeSessionEntity)

    @Query("SELECT * FROM charge_session WHERE synced = 0")
    suspend fun pendingSync(): List<ChargeSessionEntity>
}

@Database(entities = [ChargeSessionEntity::class], version = 1)
abstract class AppDatabase : RoomDatabase() {
    abstract fun sessions(): ChargeSessionDao
}
```

Notice the DAO exposes a `Flow` and `suspend` functions — that's what lets the shared repository present a reactive, coroutine-friendly API to both platforms, tying straight into the [coroutines and Flow patterns](https://blog.michaelsam94.com/kotlin-coroutines-flow-patterns/) the UI already uses.

## The expect/actual database builder

Room needs a place to put the file and a SQLite driver. Those differ per platform, so declare a common contract and implement it on each side:

```kotlin
// commonMain
expect class DatabaseBuilderFactory {
    fun create(): RoomDatabase.Builder<AppDatabase>
}

fun buildDatabase(factory: DatabaseBuilderFactory): AppDatabase =
    factory.create()
        .setDriver(BundledSQLiteDriver())   // consistent SQLite everywhere
        .setQueryCoroutineContext(Dispatchers.IO)
        .build()
```

```kotlin
// androidMain
actual class DatabaseBuilderFactory(private val context: Context) {
    actual fun create(): RoomDatabase.Builder<AppDatabase> {
        val dbFile = context.getDatabasePath("app.db")
        return Room.databaseBuilder<AppDatabase>(context, dbFile.absolutePath)
    }
}
```

```kotlin
// iosMain
actual class DatabaseBuilderFactory {
    actual fun create(): RoomDatabase.Builder<AppDatabase> {
        val dbPath = documentDirectory() + "/app.db"
        return Room.databaseBuilder<AppDatabase>(name = dbPath)
    }

    private fun documentDirectory(): String {
        val documents = NSFileManager.defaultManager.URLForDirectory(
            NSDocumentDirectory, NSUserDomainMask, null, true, null
        )
        return requireNotNull(documents?.path)
    }
}
```

Using `BundledSQLiteDriver` on both platforms matters: it ships a known SQLite version with your app instead of relying on the OS's, so a query behaves identically on an old Android device and a new iPhone. That consistency is worth the small binary cost.

## Migrations work the same — write them once

Schema migrations are one of the best parts of this setup: you write the `Migration` in `commonMain` and it applies on every platform. No more keeping two migration paths in sync.

```kotlin
// commonMain
val MIGRATION_1_2 = object : Migration(1, 2) {
    override fun migrate(connection: SQLiteConnection) {
        connection.execSQL(
            "ALTER TABLE charge_session ADD COLUMN tariffId TEXT"
        )
    }
}
// ...builder.addMigrations(MIGRATION_1_2)
```

Enable schema export in your build so Room can verify migrations in tests, and always add a real migration rather than `fallbackToDestructiveMigration` in production — wiping a user's offline data on upgrade is the kind of bug that generates one-star reviews.

## Offline-first is the real payoff

A shared Room layer shines for offline-first apps: write locally first, mark rows unsynced, and reconcile with the backend when connectivity returns. The `pendingSync()` query above is the seam for that — a shared repository can drain it and push to the server, retrying on failure. The sync *policy* (when, how often, conflict resolution) can live in common code too, though the background scheduling that triggers it is platform-specific: [WorkManager](https://blog.michaelsam94.com/workmanager-reliable-background-work/) on Android, `BGTaskScheduler` on iOS, both behind an `expect`/`actual` interface.

| Layer | Where it lives |
| --- | --- |
| Entities, DAOs, `@Database` | commonMain |
| Repository + sync policy | commonMain |
| DB path + driver setup | androidMain / iosMain |
| Background scheduling | platform (behind expect/actual) |
| Secure key for encryption | platform (Keystore / Keychain) |

## What to watch for

Room-on-KMP is solid, but a few things still need care. Compile times on iOS are longer than Android's; the KSP-generated code needs a clean build occasionally when you change schema significantly. Encryption isn't built in — if you need it, you'll wrap the driver and manage keys per platform via [the Android Keystore](https://blog.michaelsam94.com/android-security-keystore-encrypted-storage/) and the iOS Keychain. And test the iOS path on a real device early; the file-path plumbing is the part most likely to surprise you.

For a team already fluent in Room and Kotlin, this is the lowest-friction way to get a genuinely shared, offline-capable data layer across mobile. You keep the API you know, you write migrations once, and the platform differences shrink to a few dozen lines of `actual` glue. That's a much better place to be than maintaining two persistence stacks that drift apart over time.

## Resources

- [Room Kotlin Multiplatform guide](https://developer.android.com/kotlin/multiplatform/room)
- [Room documentation](https://developer.android.com/training/data-storage/room)
- [Kotlin Multiplatform docs](https://kotlinlang.org/docs/multiplatform.html)
- [SQLite driver (AndroidX)](https://developer.android.com/jetpack/androidx/releases/sqlite)
- [expect/actual declarations](https://kotlinlang.org/docs/multiplatform-expect-actual.html)
- [Android developers blog](https://android-developers.googleblog.com/)

*Designing an offline-first shared data layer? [Get in touch](https://michaelsam94.com/) — I've shipped a few.*
