---
title: "Paging 3 with Jetpack Compose"
slug: "android-paging3-compose"
description: "Integrate Paging 3 with Jetpack Compose: PagingSource, LazyPagingItems, load states, error handling, and header/footer with Paging 3.3+."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Android", "Jetpack Compose", "Paging", "Architecture"]
keywords: "Paging 3 Compose, LazyPagingItems, Jetpack Compose pagination, PagingSource Compose, collectAsLazyPagingItems"
faq:
  - q: "How do you use Paging 3 with Jetpack Compose?"
    a: "Collect a Flow<PagingData<T>> in your ViewModel using cachedIn(viewModelScope). In Compose, collect it with collectAsLazyPagingItems() and pass the result to LazyColumn's items() extension. Handle LoadState for loading, error, and empty states via lazyPagingItems.loadState."
  - q: "What is the difference between Paging 2 and Paging 3?"
    a: "Paging 3 uses Flow instead of LiveData, has built-in Kotlin coroutine support, separates concerns with PagingSource and RemoteMediator, and provides first-class Compose integration via LazyPagingItems. Paging 2's PagedListAdapter is replaced by LazyPagingItems in Compose or PagingDataAdapter in Views."
  - q: "How do you handle errors in Paging 3 with Compose?"
    a: "Check lazyPagingItems.loadState.refresh, .prepend, and .append for LoadState.Error. Display error UI and offer retry via lazyPagingItems.retry(). For item-level errors, use PagingSource.LoadResult.Error which shows an error state for that page while keeping loaded items visible."
---

Paging 3 with Compose is the standard pattern for infinite scroll lists — orders, messages, search results, feeds. The library handles loading pages in the background, deduplicating, and presenting a seamless scroll experience. What trips teams up is the LoadState handling (three different load states, each with loading/error/success), the ViewModel caching setup, and knowing when you need RemoteMediator for offline-first. I've built paging into enough list screens to know the 80% case takes an hour; the remaining 20% (offline cache, header/footer, jump-to-top) is where the docs get sparse.

## Basic setup

```kotlin
class OrdersViewModel @Inject constructor(
    private val repository: OrderRepository
) : ViewModel() {
    val orders: Flow<PagingData<Order>> = repository.getOrdersPaged()
        .cachedIn(viewModelScope)
}
```

```kotlin
// Repository
fun getOrdersPaged(): Flow<PagingData<Order>> {
    return Pager(
        config = PagingConfig(pageSize = 20, enablePlaceholders = false),
        pagingSourceFactory = { OrderPagingSource(api) }
    ).flow
}
```

```kotlin
// PagingSource
class OrderPagingSource(private val api: OrderApi) : PagingSource<Int, Order>() {
    override suspend fun load(params: LoadParams<Int>): LoadResult<Int, Order> {
        return try {
            val page = params.key ?: 0
            val response = api.getOrders(page = page, size = params.loadSize)
            LoadResult.Page(
                data = response.items,
                prevKey = if (page == 0) null else page - 1,
                nextKey = if (response.items.isEmpty()) null else page + 1
            )
        } catch (e: Exception) {
            LoadResult.Error(e)
        }
    }

    override fun getRefreshKey(state: PagingState<Int, Order>): Int? {
        return state.anchorPosition?.let { anchor ->
            state.closestPageToPosition(anchor)?.prevKey?.plus(1)
                ?: state.closestPageToPosition(anchor)?.nextKey?.minus(1)
        }
    }
}
```

## Compose UI

```kotlin
@Composable
fun OrdersScreen(viewModel: OrdersViewModel = hiltViewModel()) {
    val lazyOrders = viewModel.orders.collectAsLazyPagingItems()

    LazyColumn {
        items(
            count = lazyOrders.itemCount,
            key = lazyOrders.itemKey { it.id },
        ) { index ->
            val order = lazyOrders[index]
            if (order != null) {
                OrderRow(order = order)
            } else {
                OrderRowPlaceholder()
            }
        }

        // Loading/error footer
        when (val state = lazyOrders.loadState.append) {
            is LoadState.Loading -> item { LoadingFooter() }
            is LoadState.Error -> item {
                ErrorFooter(onRetry = { lazyOrders.retry() })
            }
            else -> {}
        }
    }

    // Full-screen refresh state
    when (val state = lazyOrders.loadState.refresh) {
        is LoadState.Loading -> LoadingScreen()
        is LoadState.Error -> ErrorScreen(onRetry = { lazyOrders.retry() })
        else -> {}
    }
}
```

Three load states to handle:
- **refresh** — initial load or pull-to-refresh
- **append** — loading next page (show footer)
- **prepend** — loading previous page (rare, for bidirectional paging)

## Pull-to-refresh

```kotlin
val lazyOrders = viewModel.orders.collectAsLazyPagingItems()

PullToRefreshBox(
    isRefreshing = lazyOrders.loadState.refresh is LoadState.Loading,
    onRefresh = { lazyOrders.refresh() },
) {
    LazyColumn { /* items */ }
}
```

## Empty state

```kotlin
if (lazyOrders.loadState.refresh is LoadState.NotLoading && lazyOrders.itemCount == 0) {
    EmptyOrdersScreen()
}
```

Check both conditions — `NotLoading` alone fires before the first load completes.

## Offline-first with RemoteMediator

For cached lists that work offline, add a [RemoteMediator](https://blog.michaelsam94.com/android-paging3-remote-mediator/):

```kotlin
Pager(
    config = PagingConfig(pageSize = 20),
    remoteMediator = OrderRemoteMediator(db, api),
    pagingSourceFactory = { db.orderDao.pagingSource() }
).flow
```

PagingSource reads from Room; RemoteMediator fetches from network and caches.

## Common pitfalls

**Forgetting `cachedIn(viewModelScope)`.** Without it, every recomposition restarts paging from page 0.

**Not setting `key` in items().** Unkeyed lists cause recomposition glitches on insert/delete.

**Using `enablePlaceholders = true` without null checks.** Placeholders return null items — handle with placeholder UI or disable placeholders.

**Blocking the main thread in PagingSource.load().** All loading is already suspend — but don't wrap blocking calls without `withContext(Dispatchers.IO)`.

## Paging with search and filters

When the list has search or filter state, invalidate PagingSource on filter change:

```kotlin
class OrderViewModel : ViewModel() {
    private val _searchQuery = MutableStateFlow("")
    val searchQuery = _searchQuery.asStateFlow()

    @OptIn(ExperimentalCoroutinesApi::class)
    val orders: Flow<PagingData<Order>> = searchQuery
        .debounce(300)
        .distinctUntilChanged()
        .flatMapLatest { query ->
            Pager(
                config = PagingConfig(pageSize = 20, enablePlaceholders = false),
                pagingSourceFactory = { OrderPagingSource(api, query) }
            ).flow
        }
        .cachedIn(viewModelScope)

    fun onSearch(query: String) { _searchQuery.value = query }
}
```

`flatMapLatest` cancels the previous PagingSource when search changes — no stale results from old query.

## Header and footer items in paged lists

Use `item` and `items` together in LazyColumn:

```kotlin
LazyColumn {
    item { SearchBar(onQueryChange = viewModel::onSearch) }
    items(
        count = lazyPagingItems.itemCount,
        key = lazyPagingItems.itemKey { it.id }
    ) { index ->
        lazyPagingItems[index]?.let { order ->
            OrderRow(order)
        }
    }
    if (lazyPagingItems.loadState.append is LoadState.Loading) {
        item { CircularProgressIndicator(Modifier.fillMaxWidth()) }
    }
}
```

Header items (search bar, filters) sit outside the paged items — they don't reload on page fetch.

## Testing PagingSource

Test paging logic without Compose:

```kotlin
class OrderPagingSourceTest {
    @Test
    fun loadFirstPage_returnsCorrectItems() = runTest {
        val source = OrderPagingSource(fakeApi, query = "")
        val result = source.load(PagingSource.LoadParams.Refresh(key = null, loadSize = 20, placeholdersEnabled = false))
        assertThat(result).isInstanceOf(PagingSource.LoadResult.Page::class.java)
        val page = result as PagingSource.LoadResult.Page
        assertThat(page.data).hasSize(20)
        assertThat(page.nextKey).isEqualTo(2)
    }
}
```

Test edge cases: empty result, error response, last page (nextKey = null).

## Failure modes

- **Missing cachedIn** — paging restarts on every recomposition
- **No key in items()** — list items jump/recompose incorrectly on insert
- **Search without flatMapLatest** — stale results from previous query shown
- **Placeholders enabled without null handling** — crash on null item access
- **RemoteMediator without invalidation** — stale cache served after network refresh

## Production checklist

- `cachedIn(viewModelScope)` on all PagingData flows
- `key` parameter set in `items()` for stable identity
- Search/filter uses `flatMapLatest` to cancel stale paging
- RemoteMediator for offline-first lists
- PagingSource unit tests for first page, empty, and error cases
- Append loading indicator shown during pagination

## Common production mistakes

Teams get paging3 compose wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping paging3 compose on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Resources

- [Paging 3 library guide](https://developer.android.com/topic/libraries/architecture/paging/v3-overview)
- [Paging with Compose](https://developer.android.com/topic/libraries/architecture/paging/v3-paged-data#compose)
- [PagingSource reference](https://developer.android.com/reference/kotlin/androidx/paging/PagingSource)
- [RemoteMediator for offline lists](https://blog.michaelsam94.com/android-paging3-remote-mediator/)
- [Compose custom lazy layouts](https://blog.michaelsam94.com/compose-custom-lazy-layouts/)
