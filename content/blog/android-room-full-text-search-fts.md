---
title: "Full-Text Search in Room with FTS4"
slug: "android-room-full-text-search-fts"
description: "Room supports SQLite FTS virtual tables for fast in-app search. Learn FTS4 setup, MATCH queries, ranking with bm25, and syncing content tables with external content FTS."
datePublished: "2024-08-11"
dateModified: "2024-08-11"
tags: ["Android", "Room", "SQLite", "Search"]
keywords: "Room FTS4, full text search Android, SQLite MATCH, bm25 ranking, external content FTS, Room migration"
faq:
  - q: "Should I use FTS3, FTS4, or FTS5 with Room?"
    a: "Room's @Fts4 annotation maps to SQLite FTS4, which ships on all Android versions Room supports. FTS5 offers better ranking and auxiliary functions but requires SQLite 3.9+ and isn't exposed through Room's FTS annotations. FTS4 is the practical choice for Android apps using Room today."
  - q: "What is external content FTS?"
    a: "An external content FTS table indexes columns from a regular content table without duplicating all data inline. You maintain the content table as usual and keep the FTS index in sync via triggers or explicit insert/update calls. This avoids storing text twice while still getting tokenized search."
  - q: "How do I rank search results by relevance?"
    a: "SQLite FTS4 supports bm25() in newer SQLite builds bundled with Android. Where available, ORDER BY bm25(table_name) ASC ranks better matches first. Fallback: use MATCH with prefix queries and sort by recency or a custom weight column in your content table."
---

Users expect instant search in note apps, messaging clients, and offline catalogs. Naive `LIKE '%query%'` scans every row and ignores word boundaries — slow on 50k messages and useless for prefix matching. SQLite's FTS (Full-Text Search) module tokenizes text into an inverted index so `MATCH` queries return in milliseconds. Room has first-class FTS support through `@Fts4` entities, which removes most of the raw SQL boilerplate.

## FTS vs LIKE

| Feature | LIKE | FTS4 |
|---------|------|------|
| Index | Full table scan | Inverted index |
| Prefix search | Awkward | Native (`term*`) |
| Word boundaries | No | Yes |
| Ranking | Manual | bm25 / matchinfo |
| Storage | None extra | Index overhead ~30–50% |

For any table where users type free-text queries, FTS pays for itself above a few thousand rows.

## Basic FTS entity

```kotlin
@Entity(tableName = "notes")
data class Note(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val title: String,
    val body: String,
    val updatedAt: Long
)

@Fts4(contentEntity = Note::class)
@Entity(tableName = "notes_fts")
data class NoteFts(
    val title: String,
    val body: String
)
```

Room creates an external content FTS4 table linked to `notes`. You must keep them synchronized — Room does not auto-sync on content updates unless you use the recommended pattern below.

## DAO queries

```kotlin
@Dao
interface NoteDao {
    @Insert
    suspend fun insert(note: Note): Long

    @Query("""
        SELECT notes.* FROM notes
        JOIN notes_fts ON notes.rowid = notes_fts.rowid
        WHERE notes_fts MATCH :query
        ORDER BY notes.updatedAt DESC
        LIMIT :limit
    """)
    suspend fun search(query: String, limit: Int = 50): List<Note>
}
```

Sanitize user input before passing to `MATCH`. Strip `"`, `*`, and `-` unless you intentionally support advanced FTS syntax:

```kotlin
fun sanitizeFtsQuery(raw: String): String {
    return raw.trim()
        .split("\\s+".toRegex())
        .filter { it.isNotBlank() }
        .joinToString(" ") { token ->
            "${token.replace("\"", "")}*"
        }
}
```

The trailing `*` enables prefix matching so `"kot"` finds `"kotlin"`.

## Syncing content and FTS

When using `contentEntity`, Room expects you to manage sync. The simplest approach: use `@Upsert` on the content table and let Room's FTS triggers handle it if you declare the relationship correctly, or explicitly rebuild:

```kotlin
@Query("INSERT INTO notes_fts(notes_fts) VALUES('rebuild')")
suspend fun rebuildFtsIndex()
```

Call `rebuildFtsIndex()` after bulk imports. For incremental updates, Room 2.5+ with external content sets up triggers automatically when you use `@Fts4(contentEntity = ...)`.

## Ranking with bm25

On devices with SQLite 3.20+ (API 24+ effectively everywhere you ship):

```kotlin
@Query("""
    SELECT notes.* FROM notes
    JOIN notes_fts ON notes.rowid = notes_fts.rowid
    WHERE notes_fts MATCH :query
    ORDER BY bm25(notes_fts) ASC
    LIMIT :limit
""")
suspend fun searchRanked(query: String, limit: Int = 50): List<Note>
```

Lower bm25 scores mean better relevance. Combine with recency by sorting in Kotlin or adding a weighted SQL expression if title matches should outweigh body matches.

## Migration from non-FTS schema

Adding FTS to an existing table requires a migration:

```kotlin
val MIGRATION_3_4 = object : Migration(3, 4) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL("""
            CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts
            USING fts4(title, body, content='notes')
        """)
        db.execSQL("INSERT INTO notes_fts(notes_fts) VALUES('rebuild')")
    }
}
```

Test migrations with [Room migration testing](https://blog.michaelsam94.com/android-room-migrations-testing/) — FTS rebuilds on large tables can take seconds and block the main thread if run synchronously at startup.

## UI integration

Debounce search input (300ms is my default), run queries on `Dispatchers.IO`, and expose results via `Flow`:

```kotlin
fun searchNotes(query: String): Flow<List<Note>> =
    query.debounce(300)
        .map { sanitizeFtsQuery(it) }
        .filter { it.isNotBlank() }
        .distinctUntilChanged()
        .flatMapLatest { q ->
            flow { emit(noteDao.searchRanked(q)) }
        }
        .flowOn(Dispatchers.IO)
```

Highlight matching terms in the UI with `AnnotatedString` — FTS doesn't return match offsets in Room, so highlight the raw query tokens client-side.

## FTS5 vs FTS4 on Android

Room supports both via `@Fts4` annotation. FTS5 improvements:

- **`bm25()` ranking** — better relevance than FTS4 default
- **Prefix queries** — `term*` without separate prefix index
- **Column filters** — search only `title:` or `body:`

```kotlin
@Fts4(contentEntity = Note::class, tokenizer = FtsOptions.TOKENIZER_UNICODE61)
@Entity(tableName = "notes_fts")
data class NoteFts(
    @ColumnInfo(name = "title") val title: String,
    @ColumnInfo(name = "body") val body: String,
)
```

`UNICODE61` tokenizer handles accented characters — `SIMPLE` breaks international search.

## Performance at scale

FTS tables grow with content. Mitigations:

- **External content** — FTS index references main table, stays synchronized via triggers (Room handles this)
- **Batch inserts** — wrap bulk imports in transaction; FTS trigger fires per row otherwise
- **Limit results** — `LIMIT 50` on search; users rarely scroll past first page
- **Avoid `%term%` LIKE fallback** — full table scan; fix tokenization instead

Rebuild FTS after bulk delete: `INSERT INTO notes_fts(notes_fts) VALUES('rebuild')` — schedule during maintenance window for 100K+ rows.

## Multilingual search

FTS tokenizers are language-specific. Options:

- Store `language` column, pick tokenizer per row (complex)
- Use Unicode61 for mixed-language notes (good enough for most apps)
- Delegate to server-side Elasticsearch for CJK languages where SQLite tokenization is weak

Pair with [Room migrations testing](https://blog.michaelsam94.com/android-room-migrations-testing/) before shipping FTS schema changes to production users.

## Common production mistakes

Teams get room full text search fts wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping room full text search fts on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Resources

- [Room FTS documentation](https://developer.android.com/training/data-storage/room/defining-data#fts)
- [SQLite FTS3/FTS4 module reference](https://www.sqlite.org/fts3.html)
- [Room @Fts4 API reference](https://developer.android.com/reference/androidx/room/Fts4)
- [SQLite bm25() function](https://www.sqlite.org/fts5.html#appendix_a)
- [Android App Search vs Room FTS (when to use each)](https://developer.android.com/reference/androidx/appsearch/app/AppSearchManager)
