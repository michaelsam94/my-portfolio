---
title: "Paging 3 RemoteMediator for Offline Lists"
slug: "android-paging3-remote-mediator"
description: "Build offline-first paginated lists with Paging 3 RemoteMediator: network-database coordination, REFRESH/PREPEND/APPEND loads, and error handling."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Android", "Paging", "Room", "Architecture"]
keywords: "Paging 3 RemoteMediator, offline-first paging, RemoteMediator Room, PagingSource RemoteMediator, cached pagination Android"
faq:
  - q: "What is RemoteMediator in Paging 3?"
    a: "RemoteMediator bridges a local database (Room) and a remote API for offline-first pagination. It fetches pages from the network, caches them in the database, and PagingSource reads from the database. When offline, users see cached data. RemoteMediator handles REFRESH, PREPEND, and APPEND load types to sync the local cache with the remote source."
  - q: "When do I need RemoteMediator vs a simple PagingSource?"
    a: "Use a simple PagingSource when data comes only from the network and offline access isn't needed. Use RemoteMediator when you want cached data available offline, need to reduce network calls by reading from cache, or want to show stale data instantly while refreshing in the background."
  - q: "How does RemoteMediator handle errors?"
    a: "Return MediatorResult.Error(e) for network failures — Paging keeps showing cached data and displays an error state. Return MediatorResult.Success(endOfPaginationReached) when the remote source has no more pages. The UI shows cached items with an error banner, not a blank screen."
---

RemoteMediator is what makes Paging 3 work offline — and it's the most misunderstood class in the library. Without it, PagingSource hits the network on every page load and shows nothing when offline. With it, PagingSource reads from Room (instant, offline-capable), and RemoteMediator syncs the network data into Room in the background. The user sees cached data immediately, fresh data arrives silently, and network failures show stale data with an error indicator instead of a blank screen. I've built offline-first feeds, order lists, and catalog browsers with this pattern; the architecture is always the same even when the domain changes.

## Architecture

```
UI → LazyPagingItems → Pager
                          ├── PagingSource (reads Room)
                          └── RemoteMediator (writes Room from API)
                                    ↓
                              Room Database ← → REST API
```

PagingSource never touches the network. RemoteMediator never touches the UI. Clean separation.

## Setup

```kotlin
@OptIn(ExperimentalPagingApi::class)
fun getOrdersPaged(): Flow<PagingData<OrderEntity>> {
    return Pager(
        config = PagingConfig(pageSize = 20, enablePlaceholders = false),
        remoteMediator = OrderRemoteMediator(db, api),
        pagingSourceFactory = { db.orderDao().pagingSource() }
    ).flow
}
```

## RemoteMediator implementation

```kotlin
@OptIn(ExperimentalPagingApi::class)
class OrderRemoteMediator(
    private val db: AppDatabase,
    private val api: OrderApi,
) : RemoteMediator<Int, OrderEntity>() {

    override suspend fun initialize(): InitializeAction {
        val cacheExpired = db.orderDao().getLastUpdated()
            ?.let { System.currentTimeMillis() - it > 60 * 60 * 1000 } // 1 hour
            ?: true
        return if (cacheExpired) InitializeAction.LAUNCH_INITIAL_REFRESH
               else InitializeAction.SKIP_INITIAL_REFRESH
    }

    override suspend fun load(
        loadType: LoadType,
        state: PagingState<Int, OrderEntity>
    ): MediatorResult {
        return try {
            val page = when (loadType) {
                LoadType.REFRESH -> 0
                LoadType.PREPEND -> return MediatorResult.Success(endOfPaginationReached = true)
                LoadType.APPEND -> {
                    val lastItem = state.lastItemOrNull()
                        ?: return MediatorResult.Success(endOfPaginationReached = true)
                    (lastItem.pageIndex + 1)
                }
            }

            val response = api.getOrders(page = page, size = state.config.pageSize)

            db.withTransaction {
                if (loadType == LoadType.REFRESH) {
                    db.orderDao().clearAll()
                }
                db.orderDao().insertAll(response.items.map { it.toEntity(page) })
                db.orderDao().setLastUpdated(System.currentTimeYear())
            }

            MediatorResult.Success(
                endOfPaginationReached = response.items.isEmpty() || !response.hasMore
            )
        } catch (e: Exception) {
            MediatorResult.Error(e)
        }
    }
}
```

Key decisions:
- **REFRESH**: clear cache and reload from page 0
- **PREPEND**: usually not needed (return end reached)
- **APPEND**: fetch next page based on last cached item's page index
- **Transaction**: wrap DB writes in `withTransaction` for atomicity

## Room setup

```kotlin
@Entity(tableName = "orders")
data class OrderEntity(
    @PrimaryKey val id: String,
    val title: String,
    val status: String,
    val pageIndex: Int,
    val remoteOrder: Int,  // position in remote list
)

@Dao
interface OrderDao {
    @Query("SELECT * FROM orders ORDER BY remoteOrder ASC")
    fun pagingSource(): PagingSource<Int, OrderEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(orders: List<OrderEntity>)

    @Query("DELETE FROM orders")
    suspend fun clearAll()

    @Query("SELECT MAX(fetched_at) FROM orders")
    suspend fun getLastUpdated(): Long?

    @Query("UPDATE orders SET fetched_at = :time WHERE id = (SELECT id FROM orders LIMIT 1)")
    suspend fun setLastUpdated(time: Long)
}
```

## Compose UI with offline support

```kotlin
@Composable
fun OrdersScreen(viewModel: OrdersViewModel = hiltViewModel()) {
    val orders = viewModel.orders.collectAsLazyPagingItems()

    // Show cached data even on error
    when (val refreshState = orders.loadState.refresh) {
        is LoadState.Error -> {
            OfflineBanner(
                message = "Showing cached data",
                onRetry = { orders.retry() }
            )
        }
        else -> {}
    }

    LazyColumn {
        items(count = orders.itemCount, key = orders.itemKey { it.id }) { index ->
            orders[index]?.let { OrderRow(it) }
        }
    }
}
```

On network error, cached items remain visible. User sees stale data with a retry option — not a blank screen.

## initialize() for smart refresh

Control when RemoteMediator auto-refreshes:

```kotlin
override suspend fun initialize(): InitializeAction {
    // Only refresh if cache is older than 1 hour
    val stale = db.orderDao().getLastUpdated()
        ?.let { System.currentTimeMillis() - it > 3_600_000 }
        ?: true
    return if (stale) InitializeAction.LAUNCH_INITIAL_REFRESH
           else InitializeAction.SKIP_INITIAL_REFRESH
}
```

`SKIP_INITIAL_REFRESH` shows cached data instantly, then appends fresh data on scroll. `LAUNCH_INITIAL_REFRESH` clears cache and reloads on every Pager creation.

## Testing

Test RemoteMediator with in-memory Room and mock API:

```kotlin
@Test
fun refresh_cachesOrdersFromApi() = runTest {
    val db = Room.inMemoryDatabaseBuilder(context, AppDatabase::class.java).build()
    val fakeApi = FakeOrderApi(items = listOf(order1, order2))
    val mediator = OrderRemoteMediator(db, fakeApi)

    val result = mediator.load(LoadType.REFRESH, emptyPagingState())
    assertTrue(result is MediatorResult.Success)

    val cached = db.orderDao().getAll()
    assertEquals(2, cached.size)
}
```

## End of pagination and remote keys

RemoteMediator must handle API pagination correctly:

```kotlin
override suspend fun load(loadType: LoadType, state: PagingState<Int, Order>): MediatorResult {
    val page = when (loadType) {
        LoadType.REFRESH -> 1
        LoadType.PREPEND -> return MediatorResult.Success(endOfPaginationReached = true)
        LoadType.APPEND -> {
            val remoteKeys = db.remoteKeysDao().remoteKeysForLastItem(state)
            remoteKeys?.nextKey ?: return MediatorResult.Success(endOfPaginationReached = true)
        }
    }
    // fetch page, insert to DB with RemoteKeys entity
}
```

Store `RemoteKeys` table with `prevKey`/`nextKey` per item — Paging 3 requires this for APPEND/PREPEND without re-fetching page 1.

## Conflict resolution on refresh

REFRESH typically clears and reloads — bad UX for infinite scroll mid-list:

```kotlin
LoadType.REFRESH -> {
    db.withTransaction {
        db.remoteKeysDao().clearAll()
        db.orderDao().clearAll()
    }
    // reload page 1
}
```

Alternative: `RemoteMediator` with `LoadType.REFRESH` that upserts without clear — user keeps scroll position, stale items update in place. More complex but better UX for social feeds.

## Production monitoring

- Mediator error rate by `LoadType`
- Cache hit ratio (APPEND without network call when offline)
- Time from REFRESH to first page displayed
- Database size growth (unbounded cache needs eviction policy)

Pair with [Android Paging3 Compose](https://blog.michaelsam94.com/android-paging3-compose/) for UI integration with RemoteMediator-backed flows.

## Common production mistakes

Teams get paging3 remote mediator wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping paging3 remote mediator on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Resources

- [RemoteMediator reference](https://developer.android.com/reference/kotlin/androidx/paging/RemoteMediator)
- [Paging 3 with Room and RemoteMediator guide](https://developer.android.com/topic/libraries/architecture/paging/v3-network-db)
- [Room with Paging 3](https://developer.android.com/topic/libraries/architecture/paging/v3-paged-data)
- [Paging 3 with Compose](https://blog.michaelsam94.com/android-paging3-compose/)
- [Handling flaky networks on mobile](https://blog.michaelsam94.com/handling-flaky-networks-mobile/)
