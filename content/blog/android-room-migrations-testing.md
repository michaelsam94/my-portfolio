---
title: "Testing Room Database Migrations"
slug: "android-room-migrations-testing"
description: "Test Room database migrations automatically: MigrationTestHelper, exported schemas, validation tests, and catching migration bugs before production."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Android", "Room", "Testing", "Architecture"]
keywords: "Room migration testing, MigrationTestHelper, Room schema export, test database migrations Android, Room autoMigration"
faq:
  - q: "How do you test Room database migrations?"
    a: "Export Room schemas to JSON files in version control, then use MigrationTestHelper to create a database at version N, insert test data, run the migration to version N+1, and verify schema and data integrity. Run these as instrumentation tests or JVM tests with Robolectric."
  - q: "Should I export Room schemas?"
    a: "Yes — always. Enable schema export in your Room database annotation. Each schema version is saved as a JSON file. These files are the baseline for MigrationTestHelper and serve as documentation of your database evolution."
  - q: "What is Room autoMigration?"
    a: "Room autoMigration automatically handles simple schema changes (adding columns, tables) without writing manual Migration classes. Enable it with @AutoMigration on your @Database annotation. Test autoMigrations with MigrationTestHelper too — auto doesn't mean infallible."
---

Room migrations are the code path nobody tests until a user updates the app and loses data. You added a column in version 5, wrote a Migration, shipped it — and the migration SQL has a typo that drops a table on devices upgrading from version 3. MigrationTestHelper catches this before release by creating real database files at old versions, running your migration, and verifying the result. I've seen migration tests save production data more than once; the setup takes 30 minutes and pays for itself on the first caught bug.

## Export schemas

```kotlin
@Database(
    entities = [User::class, Order::class],
    version = 3,
    exportSchema = true,
    autoMigrations = [
        AutoMigration(from = 1, to = 2),
        AutoMigration(from = 2, to = 3),
    ]
)
abstract class AppDatabase : RoomDatabase()
```

```kotlin
// build.gradle.kts
android {
    defaultConfig {
        ksp {
            arg("room.schemaLocation", "$projectDir/schemas")
        }
    }
}
```

Commit `schemas/` directory to git. Each version produces a JSON file describing the exact schema.

## Write migration tests

```kotlin
@RunWith(AndroidJUnit4::class)
class MigrationTest {
    private val TEST_DB = "migration-test"

    @get:Rule
    val helper = MigrationTestHelper(
        InstrumentationRegistry.getInstrumentation(),
        AppDatabase::class.java,
        emptyList(),  // autoMigrationSpecs
    )

    @Test
    fun migrate1To2() {
        // Create database at version 1
        helper.createDatabase(TEST_DB, 1).apply {
            execSQL("INSERT INTO users (id, name) VALUES ('u1', 'Alice')")
            close()
        }

        // Run migration
        helper.runMigrationsAndValidate(TEST_DB, 2, true, MIGRATION_1_2)

        // Verify data survived
        getMigratedRoomDatabase().userDao().getById("u1").let { user ->
            assertEquals("Alice", user.name)
        }
    }

    @Test
    fun migrate2To3() {
        helper.createDatabase(TEST_DB, 2).apply {
            execSQL("INSERT INTO users (id, name, email) VALUES ('u1', 'Alice', 'alice@test.com')")
            execSQL("INSERT INTO orders (id, user_id, total) VALUES ('o1', 'u1', 99.99)")
            close()
        }

        helper.runMigrationsAndValidate(TEST_DB, 3, true, MIGRATION_2_3)

        getMigratedRoomDatabase().orderDao().getById("o1").let { order ->
            assertEquals(99.99, order.total, 0.01)
        }
    }

    @Test
    fun migrateAll() {
        // Test full migration chain from v1 to current
        helper.createDatabase(TEST_DB, 1).apply {
            execSQL("INSERT INTO users (id, name) VALUES ('u1', 'Alice')")
            close()
        }
        helper.runMigrationsAndValidate(TEST_DB, 3, true, MIGRATION_1_2, MIGRATION_2_3)
    }
}
```

The `migrateAll` test is the most important — it verifies the full chain from earliest supported version to current.

## Manual migrations

When autoMigration can't handle the change:

```kotlin
val MIGRATION_2_3 = object : Migration(2, 3) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL("ALTER TABLE orders ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'")
        db.execSQL("CREATE INDEX idx_orders_status ON orders(status)")
    }
}
```

Test every manual migration individually AND as part of the full chain.

## Destructive migration fallback

```kotlin
Room.databaseBuilder(context, AppDatabase::class.java, "app.db")
    .fallbackToDestructiveMigration()  // ONLY for debug builds
    .build()
```

Never use destructive migration in production — users lose all data on upgrade. Use it only in debug builds for developer convenience. Production must have tested migration paths for every version jump.

## CI integration

Run migration tests in CI:

```yaml
- name: Room migration tests
  run: ./gradlew :app:connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=com.example.MigrationTest
```

Or with Robolectric for JVM execution (faster, no emulator):

```kotlin
@Config(sdk = [33])
@RunWith(RobolectricTestRunner::class)
class MigrationTest { /* same tests, runs on JVM */ }
```

## Migration checklist

Before shipping a schema change:
- [ ] Schema exported and committed
- [ ] Manual migration written (if not autoMigration)
- [ ] Individual migration test (N → N+1)
- [ ] Full chain test (v1 → current)
- [ ] Test data inserted pre-migration survives post-migration
- [ ] Indexes recreated if needed
- [ ] Default values set for new NOT NULL columns

## AutoMigration vs manual migrations

Room 2.4+ supports AutoMigration for additive schema changes:

```kotlin
@Database(
    entities = [User::class, Order::class],
    version = 3,
    autoMigrations = [
        AutoMigration(from = 1, to = 2),
        AutoMigration(from = 2, to = 3, spec = Migration2To3::class),
    ]
)
abstract class AppDatabase : RoomDatabase()

@DeleteColumn(tableName = "users", columnName = "legacy_field")
@RenameColumn(tableName = "orders", fromColumnName = "total", toColumnName = "amount")
class Migration2To3 : AutoMigrationSpec
```

AutoMigration handles: add column, add table, add index. Manual migration required for: data transformation, column rename without annotation, complex SQL.

Use AutoMigration when possible — less code, fewer bugs. Fall back to manual for data migrations.

## Testing migration with production-like data

Export anonymized production schema + sample data for migration tests:

```kotlin
@Test
fun migrateProductionSample() {
    // Copy anonymized prod DB fixture to test assets
    val helper = MigrationTestHelper(
        InstrumentationRegistry.getInstrumentation(),
        AppDatabase::class.java,
        emptyList(),
        FrameworkSQLiteOpenHelperFactory()
    )
    helper.createDatabase(TEST_DB, 5).apply {
        // Insert production-like data from fixture SQL
        execSQL("INSERT INTO orders SELECT * FROM prod_sample_orders")
        close()
    }
    helper.runMigrationsAndValidate(TEST_DB, 6, true, MIGRATION_5_6).close()
}
```

Catch migration failures that empty test databases miss — NOT NULL constraints, index conflicts, data type coercion edge cases.

## Multi-step migration chains

When users skip versions (v3 → v7), Room runs all intermediate migrations:

```
v3 → v4 → v5 → v6 → v7  (all run sequentially)
```

Test the full chain, not just adjacent steps:

```kotlin
@Test
fun migrateAllVersions() {
    helper.createDatabase(TEST_DB, 1).close()
    helper.runMigrationsAndValidate(TEST_DB, CURRENT_VERSION, true, *ALL_MIGRATIONS).close()
}
```

One broken intermediate migration bricks users who haven't updated in months.

## Failure modes

- **Destructive migration in production** — users lose all data on upgrade
- **Missing migration for version jump** — crash on upgrade from old version
- **NOT NULL column without default** — migration fails on existing rows
- **Index not recreated after table rebuild** — query performance regression
- **Migration tested only N→N+1** — full chain untested; skip-version users crash

## Production checklist

- Schema exported and committed on every version bump
- AutoMigration used for additive changes; manual for data transforms
- Individual migration test (N → N+1) for each version
- Full chain test (v1 → current) in CI
- Production-like data fixture in migration tests
- Destructive migration only in debug builds

Export schema JSON from Room on every release and diff in CI — silent migration gaps surface as `IllegalStateException` on user devices, not in dev builds.

## Resources

- [Room migration testing guide](https://developer.android.com/training/data-storage/room/migrating-db-versions)
- [MigrationTestHelper reference](https://developer.android.com/reference/androidx/room/testing/MigrationTestHelper)
- [Room autoMigration](https://developer.android.com/reference/kotlin/androidx/room/AutoMigration)
- [Room multimap relations](https://blog.michaelsam94.com/android-room-multimap-relations/)
- [Testing with Robolectric](https://blog.michaelsam94.com/android-testing-robolectric/)
