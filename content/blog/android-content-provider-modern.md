---
title: "Do You Still Need a ContentProvider?"
slug: "android-content-provider-modern"
description: "When ContentProvider is still the right choice on Android, and modern alternatives for sharing data between apps, processes, and your own components."
datePublished: "2026-07-15"
dateModified: "2026-07-15"
tags: ["Android", "Architecture", "Data", "Security"]
keywords: "ContentProvider Android, when to use ContentProvider, Android data sharing, ContentProvider alternatives, FileProvider Android"
faq:
  - q: "Are ContentProviders still used in modern Android apps?"
    a: "Yes, but mostly for specific cases: sharing files via FileProvider, exposing data to other apps (contacts, calendar integrations), SearchManager integration, and widget data binding. For sharing data within your own app, Room, DataStore, and in-process repositories have replaced ContentProvider as the default pattern."
  - q: "What is FileProvider and why do I need it?"
    a: "FileProvider is a ContentProvider subclass that generates content:// URIs for files, enabling secure file sharing between apps via Intent. Required when passing files to camera apps, share sheets, or other apps via Intent — file:// URIs are blocked on modern Android. You almost certainly need FileProvider even if you don't need a custom ContentProvider."
  - q: "What are alternatives to ContentProvider for inter-app data sharing?"
    a: "For file sharing: FileProvider. For structured data: expose a bound Service with AIDL or share via deep links to your app's UI. For simple key-value sharing: create a custom URI scheme handled by your Activity. ContentProvider remains the standard when multiple apps need query-level access to your data (like a contacts app exposing contacts)."
---

ContentProvider feels like a 2012 API — and for most internal app data, it is. Room replaced SQLite + ContentProvider for your own database. DataStore replaced SharedPreferences + ContentProvider wrappers. ViewModels and repositories replaced the CursorLoader dance. But ContentProvider hasn't gone away; it's just moved to the edges: FileProvider for sharing files, exposing data to other apps that query it, and widget/search integration. The question isn't "should I use ContentProvider?" — it's "am I sharing data across app boundaries, or within my own process?"

## When you still need ContentProvider

| Use case | Provider type | Alternative? |
|----------|--------------|-------------|
| Share file with camera/gallery/share sheet | FileProvider | None — required |
| Expose app data to other apps (contacts-like) | Custom ContentProvider | Bound Service + AIDL |
| App widget data binding | Custom or shared DB | Glance + in-process data |
| Search suggestions | Custom ContentProvider | In-app search only: skip |
| Cross-process within your app | ContentProvider | Room + multi-process mode (avoid) |
| SDK auto-init via provider | Library's provider | App Startup library |

If your data stays within your app, you don't need a ContentProvider. Full stop.

## FileProvider: the one you probably need

Every app that shares files uses FileProvider:

```xml
<provider
    android:name="androidx.core.content.FileProvider"
    android:authorities="${applicationId}.fileprovider"
    android:exported="false"
    android:grantUriPermissions="true">
    <meta-data
        android:name="android.support.FILE_PROVIDER_PATHS"
        android:resource="@xml/file_paths" />
</provider>
```

```xml
<!-- res/xml/file_paths.xml -->
<paths>
    <cache-path name="images" path="images/" />
    <files-path name="docs" path="documents/" />
</paths>
```

Share a file:

```kotlin
val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
val intent = Intent(Intent.ACTION_SEND).apply {
    type = "image/jpeg"
    putExtra(Intent.EXTRA_STREAM, uri)
    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
}
startActivity(Intent.createChooser(intent, "Share"))
```

Without FileProvider, `file://` URIs trigger a `FileUriExposedException` on API 24+.

## Custom ContentProvider for inter-app data

If other apps need to query your data (like a note-taking app exposing notes to a launcher search):

```kotlin
class NotesProvider : ContentProvider() {
    override fun onCreate(): Boolean = true

    override fun query(
        uri: Uri, projection: Array<String>?, selection: String?,
        selectionArgs: Array<String>?, sortOrder: String?
    ): Cursor? {
        val match = uriMatcher.match(uri)
        return when (match) {
            NOTES -> database.query("notes", projection, selection, selectionArgs, null, null, sortOrder)
            else -> throw IllegalArgumentException("Unknown URI: $uri")
        }
    }
    // insert, update, delete...
}
```

Declare with explicit permissions:

```xml
<provider
    android:name=".NotesProvider"
    android:authorities="com.example.app.notes"
    android:exported="true"
    android:readPermission="com.example.app.permission.READ_NOTES" />
```

`android:exported="true"` is required for inter-app access — and it's a security surface. Validate every query, limit exposed columns, and use permissions.

## What replaced ContentProvider internally

**Room + Repository** for database access:

```kotlin
@Dao
interface NoteDao {
    @Query("SELECT * FROM notes")
    fun getAll(): Flow<List<Note>>
}
```

No Cursor, no ContentResolver, no URI matching. Type-safe, coroutine-friendly, testable.

**DataStore** for preferences — replaces the old SharedPreferences ContentProvider pattern some libraries used.

**SharedFlow/StateFlow** for in-app event broadcasting — replaces ContentObserver for your own data changes.

## The ContentObserver trap

Don't use ContentObserver to watch your own app's ContentProvider. Use Room's Flow or DataStore's data Flow:

```kotlin
// Old: ContentObserver on your own provider
// New:
noteDao.getAll().collect { notes -> updateUI(notes) }
```

ContentObserver makes sense when watching *another app's* provider (e.g., contacts changes). For your own data, reactive queries are simpler and more reliable.

## Library ContentProviders

Many SDKs init via ContentProvider (Firebase, WorkManager, etc.). This runs before Application.onCreate on the main thread. Audit your merged manifest:

```bash
./gradlew :app:processDebugManifest
grep -i "provider" app/build/intermediates/merged_manifests/debug/AndroidManifest.xml
```

Migrate to [App Startup](https://developer.android.com/topic/libraries/app-startup) where the library supports it. Disable auto-init for SDKs that don't:

```xml
<meta-data android:name="firebase_analytics_collection_deactivated" android:value="true" tools:replace="android:value" />
```

## Security checklist for exported providers

- [ ] `android:exported` is `false` unless inter-app access is required
- [ ] Read/write permissions declared and enforced
- [ ] URI matcher validates all paths — no path traversal
- [ ] SQL selection uses parameterized queries, not string concatenation
- [ ] Only expose minimum necessary columns
- [ ] FileProvider paths are as narrow as possible

## Cross-app data sharing in 2026

Prefer explicit APIs over exported providers:

| Need | Modern approach | Legacy |
|------|-----------------|--------|
| Share file | FileProvider + FLAG_GRANT_READ_URI_PERMISSION | Exported provider |
| Share structured data | App Links + REST/GraphQL | ContentProvider query |
| Contacts integration | ContactsContract (system) | Custom provider |
| Widget data | Room + Glance remote views | Provider query |

Export providers only when Android framework requires it (sync adapters) or documented inter-app contract exists.

## Room as provider replacement

Internal data access never needs ContentProvider:

```kotlin
@Dao
interface NoteDao {
    @Query("SELECT * FROM notes WHERE id = :id")
    fun observeNote(id: Long): Flow<Note?>

    @Query("SELECT * FROM notes")
    fun observeAll(): Flow<List<Note>>
}
```

Expose data to other apps via authenticated API if needed — not SQLite through ContentProvider.

## Testing providers

If you maintain exported providers:

```kotlin
@RunWith(AndroidJUnit4::class)
class NoteProviderTest {
    @Test
    fun query_returnsExpectedColumns() {
        val cursor = contentResolver.query(NotesContract.CONTENT_URI, null, null, null, null)
        assertNotNull(cursor)
        assertTrue(NotesContract.ALL_COLUMNS.all { col -> cursor.getColumnIndex(col) >= 0 })
        cursor.close()
    }
}
```

Test permission enforcement — unprivileged context should get SecurityException on write.

Pair with [Android DataStore migration](https://blog.michaelsam94.com/android-datastore-migration-sharedpreferences/) for key-value data that never needed providers.

## Common production mistakes

Teams get content provider modern wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping content provider modern on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Column naming and SQL injection

User-supplied sort columns in `query()` are injection surface — allowlist `validColumns` set. `ContentProvider.call()` method names similarly need allowlist when exposing custom RPC.

## URI permission persistence

Granting read URI permission via `FLAG_GRANT_READ_URI_PERMISSION` expires when granting task finishes — document for share-sheet flows; use `takePersistableUriPermission` when long-lived access required.

## Content Provider Modern Supplement 0 on Samsung and Pixel divergence

Exercise content provider modern supplement 0 on Galaxy A-series and Pixel a-series — emulators hide OEM battery and storage quirks. Capture Macrobenchmark or Firebase trace for the critical path touching content; regressions above 8% block release for `android-content-provider-modern-supplement-0`.

Document permission and background behavior in internal runbook: what breaks under Doze, what requires foreground service, and what Play policy declarations apply. Support tickets referencing "Content Provider Modern Supplement 0" should map to a single runbook section with known workarounds.

## Modern regression gates for Play Vitals

Before promoting `android-content-provider-modern-supplement-0` changes past 20% rollout, compare ANR rate, slow cold start, and excessive wakeups against seven-day baseline. Fail rollback review if 0 path shows >5% increase in `slow frames` without documented trade-off approval.

## Field testing content with battery saver enabled

Xiaomi and Oppo ship aggressive background killers. After implementing content provider modern supplement 0, run 24-hour monkey test on three OEM devices with battery saver enabled. Failures here predict one-star reviews that Crashlytics never captures — especially for 0 flows that assume reliable background delivery.

## Resources

- [ContentProvider overview (Android)](https://developer.android.com/guide/topics/providers/content-providers)
- [FileProvider guide](https://developer.android.com/reference/androidx/core/content/FileProvider)
- [Room persistence library](https://developer.android.com/training/data-storage/room)
- [DataStore guide](https://developer.android.com/topic/libraries/architecture/datastore)
- [Migrating SharedPreferences to DataStore](https://blog.michaelsam94.com/android-datastore-migration-sharedpreferences/)
