---
title: "Room Relations and Multimap Queries"
slug: "android-room-multimap-relations"
description: "Room @Relation and @Junction map one-to-many and many-to-many joins into nested objects. Multimap queries return Map<K, List<V>> for grouped results without manual aggregation in Kotlin."
datePublished: "2024-08-16"
dateModified: "2024-08-16"
tags: ["Android", "Room", "Kotlin", "Database"]
keywords: "Room Relation, Room Junction, multimap query, one to many Room, many to many Room, nested database objects"
faq:
  - q: "What is the difference between @Relation and @Embedded?"
    a: "@Embedded flattens columns from a single table into the parent object — useful when one row maps to one object. @Relation loads related rows from another table (or through a junction table) and nests them as a List or single object. Use @Relation when the data lives in separate tables with foreign keys."
  - q: "Why do Room relation queries sometimes return duplicate parent rows?"
    a: "SQL JOINs multiply rows — one playlist with 50 songs produces 50 joined rows. Room deduplicates parent entities when mapping @Relation results, but the SQL still transfers redundant data. For large lists, consider a two-query approach or a multimap query that groups explicitly."
  - q: "When should I use multimap queries?"
    a: "Use @MapInfo multimap queries when you need results grouped by a key, such as messages grouped by date or tasks grouped by project ID. Room returns Map<K, List<V>> directly, avoiding manual groupBy in Kotlin and keeping aggregation logic in the DAO layer."
---

Fetching a playlist with its songs, or a project with all assignees, is the most common relational query in mobile apps. Without Room's relation support, you write two queries and merge lists in the repository — error-prone when IDs don't align or when pagination splits parent and child fetches. Room's `@Relation`, `@Junction`, and multimap queries handle the join mapping declaratively so your DAO returns fully nested objects.

## One-to-many with @Relation

```kotlin
@Entity
data class Playlist(
    @PrimaryKey val id: Long,
    val name: String
)

@Entity(foreignKeys = [ForeignKey(
    entity = Playlist::class,
    parentColumns = ["id"],
    childColumns = ["playlistId"],
    onDelete = ForeignKey.CASCADE
)])
data class Song(
    @PrimaryKey val id: Long,
    val playlistId: Long,
    val title: String,
    val durationMs: Long
)

data class PlaylistWithSongs(
    @Embedded val playlist: Playlist,
    @Relation(
        parentColumn = "id",
        entityColumn = "playlistId"
    )
    val songs: List<Song>
)
```

```kotlin
@Dao
interface PlaylistDao {
    @Transaction
    @Query("SELECT * FROM Playlist WHERE id = :id")
    suspend fun getPlaylistWithSongs(id: Long): PlaylistWithSongs?

    @Transaction
    @Query("SELECT * FROM Playlist ORDER BY name")
    fun observeAllWithSongs(): Flow<List<PlaylistWithSongs>>
}
```

`@Transaction` is required — Room runs the parent query and child queries atomically so you never observe a half-loaded relation.

## Many-to-many with @Junction

```kotlin
@Entity
data class Student(@PrimaryKey val id: Long, val name: String)

@Entity
data class Course(@PrimaryKey val id: Long, val title: String)

@Entity(primaryKeys = ["studentId", "courseId"])
data class Enrollment(
    val studentId: Long,
    val courseId: Long
)

data class StudentWithCourses(
    @Embedded val student: Student,
    @Relation(
        parentColumn = "id",
        entityColumn = "id",
        associateBy = Junction(
            value = Enrollment::class,
            parentColumn = "studentId",
            entityColumn = "courseId"
        )
    )
    val courses: List<Course>
)
```

The junction table is the join table — Room uses it to resolve which courses belong to which student without a direct foreign key between them.

## Multimap queries

Room 2.5+ supports returning `Map<K, V>` with `@MapInfo`:

```kotlin
data class TaskSummary(
    val projectId: Long,
    val title: String,
    val status: String
)

@MapInfo(keyColumn = "projectId", valueColumn = "id")
data class ProjectTaskMap

@Dao
interface TaskDao {
    @Query("""
        SELECT projectId, id, title, status
        FROM Task
        WHERE status != 'archived'
        ORDER BY projectId, dueDate
    """)
    suspend fun tasksGroupedByProject(): Map<Long, List<TaskSummary>>
}
```

For a single-value mapping (one task per project):

```kotlin
@MapInfo(keyColumn = "projectId")
@Query("SELECT projectId, * FROM Task WHERE isPrimary = 1")
suspend fun primaryTaskByProject(): Map<Long, Task>
```

I've replaced many repository-layer `groupBy { it.projectId }` calls with multimap DAO methods — fewer lines and the grouping stays close to the SQL where it belongs.

## Performance considerations

`@Relation` issues N+1 queries under the hood: one for parents, one per relation type. For a list of 100 playlists each with songs, that's two queries total (not 101) — Room batches by relation. Still, large JOIN results transfer redundant parent columns.

| Pattern | Best for | Watch out for |
|---------|----------|---------------|
| @Relation | Moderate lists, nested UI models | Large many-to-many sets |
| Multimap | Grouped dashboards, section headers | Key column must be stable |
| Raw JOIN + manual map | Full control, pagination | Boilerplate, test burden |
| Paging 3 + RemoteMediator | Infinite feeds | Relations don't page nested children automatically |

When a playlist has 10,000 songs, don't load all via `@Relation`. Page songs separately with `PagingSource` and load the playlist header alone.

## Nullable relations

For optional one-to-one relations, use a single-object relation:

```kotlin
data class UserWithAvatar(
    @Embedded val user: User,
    @Relation(parentColumn = "avatarId", entityColumn = "id")
    val avatar: Avatar?  // Room supports nullable single relations
)
```

Ensure the foreign key allows NULL if the relation is optional.

## Testing

Use an in-memory Room database in tests to verify relation mapping:

```kotlin
@RunWith(AndroidJUnit4::class)
class PlaylistDaoTest {
    private lateinit var db: AppDatabase

    @Before
    fun setup() {
        db = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            AppDatabase::class.java
        ).build()
    }

    @Test
    fun relationReturnsAllSongs() = runTest {
        val dao = db.playlistDao()
        val pid = dao.insert(Playlist(id = 0, name = "Road Trip"))
        dao.insert(Song(id = 0, playlistId = pid, title = "Track 1", durationMs = 180_000))
        val result = dao.getPlaylistWithSongs(pid)
        assertEquals(1, result?.songs?.size)
    }
}
```

Use `@Relation` with `@Junction` for many-to-many — manual join queries bypass Room's relation cache and cause N+1 on lists.

## @Junction for many-to-many

```kotlin
@Entity(primaryKeys = ["playlistId", "songId"])
data class PlaylistSongCrossRef(val playlistId: Long, val songId: Long)

data class PlaylistWithSongs(
    @Embedded val playlist: Playlist,
    @Relation(parentColumn = "id", entityColumn = "id",
        associateBy = Junction(PlaylistSongCrossRef::class))
    val songs: List<Song>
)
```

Without `@Junction`, Room can't map M:N — queries return duplicates or empty relations.

## Common production mistakes

Teams get room multimap relations wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping room multimap relations on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Debugging and triage workflow

When room multimap relations misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Room relations overview](https://developer.android.com/training/data-storage/room/relationships)
- [Room @Junction reference](https://developer.android.com/reference/androidx/room/Junction)
- [Room multimap @MapInfo](https://developer.android.com/reference/androidx/room/MapInfo)
- [Room @Transaction requirement](https://developer.android.com/reference/androidx/room/Transaction)
- [Paging 3 with Room guide](https://developer.android.com/topic/libraries/architecture/paging/v3-network-db)
