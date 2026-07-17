---
title: "A Shared Data Layer with Room and Kotlin Multiplatform"
slug: "shared-data-layer-room-kmp"
description: "Build a shared offline data layer with Room on Kotlin Multiplatform: KMP setup, expect/actual database builders, migrations, and sharing DAOs across Android and iOS."
datePublished: "2026-04-13"
dateModified: "2026-07-17"
tags:
  - "Kotlin Multiplatform"
  - "Room"
  - "Android"
  - "iOS"
keywords: "Room KMP, Room Multiplatform, shared data layer, KMP database, offline storage, SQLite, expect actual"
faq:
  - q: "q"
    a: "a"
  - q: "q"
    a: "a"
  - q: "q"
    a: "a"
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

## Sync conflict resolution in Room

Last-write-wins loses edits when two devices update the same row offline. Version columns with optimistic locking surface conflicts to UI: "Your change conflicts with a newer version — merge or discard?" For collaborative fields, CRDTs or field-level timestamps beat whole-row LWW. Test airplane-mode edit on two emulators before shipping sync.

## KMP expect/actual for platform secure storage

Shared `TokenRepository` interface with Android `EncryptedSharedPreferences` actual and iOS Keychain actual keeps secrets off plain Room tables. Never store refresh tokens in unencrypted SQLite even if "just for debugging" — backup exports and rooted devices expose them.

## Type-safe queries with Room Query

Share Query suspend functions in common module; DAO interfaces live in shared, actual database builder per platform. Use Transaction for read-then-write sync operations — partial reads between threads cause duplicate sync jobs on Android.

## Migration testing on both platforms

Room schema export from Android as baseline — iOS actual must apply same Migration object. Divergence causes crash on iOS upgrade while Android users unaffected — test migration path on both before release.

## Integration testing notes

Exercise the happy path plus three failure modes specific to shared data layer room kmp: dependency timeout, duplicate delivery, and partial deploy during rolling update. Automated tests should assert idempotent behavior and user-visible error messages—not only HTTP 200 from mocks.

## Documentation and on-call

Link runbook steps from the service catalog entry for shared data layer room kmp. On-call engineers should find rollback command, dashboard URL, and known false-positive alerts without searching Slack history. Update the entry when behavior or metrics change.

## Rollout checklist

Ship behind a feature flag when behavior is user-visible. Compare error rate and p95 latency for seven days against baseline captured before merge. Document rollback in the pull request so on-call can revert without author contact.

## Quick reference

Instrument shared data layer room kmp before optimizing. Keep a dashboard per critical user journey and review weekly during the first month after launch.

Review metrics quarterly; traffic mix shifts can invert prior wins without code changes.

## Notes on shared data layer room kmp

Schema migrations run on both platforms in CI before merge. Use BundledSQLiteDriver consistently — system SQLite differences caused subtle WAL bugs for us. Keep sync conflict policy in commonMain KDoc so iOS and Android product owners share one specification.

## Resources

- [Room Kotlin Multiplatform guide](https://developer.android.com/kotlin/multiplatform/room)
- [Room documentation](https://developer.android.com/training/data-storage/room)
- [Kotlin Multiplatform docs](https://kotlinlang.org/docs/multiplatform.html)
- [SQLite driver (AndroidX)](https://developer.android.com/jetpack/androidx/releases/sqlite)
- [expect/actual declarations](https://kotlinlang.org/docs/multiplatform-expect-actual.html)
- [Android developers blog](https://android-developers.googleblog.com/)

*Designing an offline-first shared data layer? [Get in touch](https://michaelsam94.com/) — I've shipped a few.*

Export Room schemas to CI; migration tests on both Android and iosTest resources.

## Gradle version catalog alignment

Pin Room, SQLite, and KSP versions in `libs.versions.toml` — KMP breaks on mismatched compiler plugin versions across modules.

## Flow and Room

DAO `Flow` emissions integrate with `stateIn` in ViewModel:

```kotlin
class ItemViewModel(dao: ItemDao) : ViewModel() {
    val items = dao.observeAll()
        .map { list -> list.map { it.toDomain() } }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())
}
```

Collect in UI with `collectAsStateWithLifecycle()` on Android; SwiftUI consumes via wrapper exposing `StateFlow` as observable.

## iOS Swift interop

Expose repository with `@ObjCName` or SKIE-generated Swift API — Room stays Kotlin; SwiftUI never touches SQL directly.

## Encryption

SQLCipher via expect/actual driver wrapper for sensitive offline cache — key from iOS Keychain / Android Keystore through platform secure storage interface.

## Migration testing matrix

| Test | Android | iOS | commonTest |
|------|---------|-----|------------|
| Migration 1→2 | ✓ | ✓ | ✓ |
| Destructive fallback | instrumented | simulator | in-memory |

## Offline queue conflict UI

When sync fails, surface `synced=false` items in UI with retry — repository exposes `observePending()` Flow.

## Performance

Index columns used in WHERE and ORDER BY. `@Upsert` batch in transactions for bulk refresh — single transaction per sync wave, not per row.

Room KMP rewards teams that treat shared module as product — with migration CI, platform factories, and repository APIs stable enough for Swift and Kotlin UI teams to parallelize.

## iOS background sync triggers

Room repositories in commonMain; `pushPendingSync()` invoked from WorkManager on Android and BGTaskScheduler on iOS. Test airplane-mode edit on both platforms before release — sync semantics must match, not merely compile.
