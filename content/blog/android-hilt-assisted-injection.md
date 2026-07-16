---
title: "Assisted Injection with Hilt"
slug: "android-hilt-assisted-injection"
description: "Use Hilt @AssistedInject for ViewModels and objects with runtime parameters: AssistedFactory, SavedStateHandle, navigation args, and testing patterns."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Android", "Hilt", "Dependency Injection", "Architecture"]
keywords: "Hilt AssistedInject, AssistedFactory Hilt, Hilt ViewModel parameters, assisted injection Android, SavedStateHandle Hilt"
faq:
  - q: "What is assisted injection in Hilt?"
    a: "Assisted injection lets Hilt provide some constructor dependencies (via @Inject) while you pass runtime parameters (via @Assisted) that aren't known at compile time — like navigation arguments, user IDs, or SavedStateHandle. An @AssistedFactory interface creates instances with the runtime params while Hilt supplies the rest."
  - q: "When do I need @AssistedInject instead of regular @Inject?"
    a: "Use @AssistedInject when an object needs both DI-managed dependencies (repository, analytics) and runtime parameters (item ID, screen args). Common cases: detail ViewModels parameterized by entity ID, workers parameterized by task data, and any class where the constructor args come from navigation or user input."
  - q: "How does AssistedInject work with ViewModels?"
    a: "Define the ViewModel with @AssistedInject and @Assisted parameters, create an @AssistedFactory interface, and use Hilt's viewModel factory integration or a custom AbstractSavedStateViewModelFactory. For Navigation Compose, use hiltViewModel() with navBackStackEntry arguments passed via the factory."
---

Not every dependency is known at compile time. Your `DetailViewModel` needs a `Repository` (Hilt knows how to provide that) and an `itemId` from navigation arguments (Hilt doesn't). Regular `@Inject` can't handle the `itemId` — it's different every time someone opens a detail screen. `@AssistedInject` splits the constructor: Hilt provides the stable dependencies, you pass the runtime ones through an `@AssistedFactory`. It's the pattern behind every parameterized ViewModel in a Hilt app, and the one DI concept that confuses people until they see the factory interface.

## Basic pattern

```kotlin
class DetailViewModel @AssistedInject constructor(
    @Assisted private val itemId: String,
    private val repository: ItemRepository,
    private val analytics: Analytics,
) : ViewModel() {

    @AssistedFactory
    interface Factory {
        fun create(itemId: String): DetailViewModel
    }

    val item = repository.getItem(itemId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)
}
```

Hilt generates the factory implementation. You inject `DetailViewModel.Factory` and call `create(itemId)`.

## With Navigation Compose

For nav graph ViewModels with route arguments:

```kotlin
@Composable
fun DetailScreen(
    backStackEntry: NavBackStackEntry = navController.currentBackStackEntry!!,
    viewModel: DetailViewModel = hiltViewModel(),
) {
    // Hilt extracts nav args if ViewModel is scoped to the backStackEntry
}
```

When the ViewModel needs explicit assisted params from nav args:

```kotlin
@Composable
fun DetailScreen(itemId: String) {
    val factory = hiltViewModel<DetailViewModelFactory>().detailViewModelFactory
    val viewModel: DetailViewModel = viewModel(
        factory = DetailViewModel.provideFactory(factory, itemId)
    )
}

// Companion for ViewModelProvider.Factory
companion object {
    fun provideFactory(factory: Factory, itemId: String) =
        object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T =
                factory.create(itemId) as T
        }
}
```

## SavedStateHandle with AssistedInject

Combine assisted params with SavedStateHandle for [process death survival](https://blog.michaelsam94.com/android-savedstatehandle-process-death/):

```kotlin
class EditorViewModel @AssistedInject constructor(
    @Assisted savedStateHandle: SavedStateHandle,
    private val repository: DocumentRepository,
) : ViewModel() {

    @AssistedFactory
    interface Factory {
        fun create(handle: SavedStateHandle): EditorViewModel
    }

    private val documentId: String = savedStateHandle["docId"]
        ?: throw IllegalArgumentException("docId required")

    var title by savedStateHandle.saveable { mutableStateOf("") }
}
```

Register the factory in a Hilt module for SavedStateHandle injection:

```kotlin
@Module
@InstallIn(ViewModelComponent::class)
abstract class ViewModelModule {
    @Binds
    abstract fun bindEditorFactory(impl: EditorViewModel.Factory): EditorViewModel.Factory
}
```

## Workers with AssistedInject

WorkManager workers with runtime input data:

```kotlin
@HiltWorker
class SyncWorker @AssistedInject constructor(
    @Assisted context: Context,
    @Assisted params: WorkerParameters,
    private val syncRepository: SyncRepository,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val userId = inputData.getString("user_id") ?: return Result.failure()
        return syncRepository.sync(userId)
    }
}
```

Hilt automatically provides `@Assisted context` and `@Assisted params` for `@HiltWorker` — no custom factory needed.

## Testing

Mock the factory in tests:

```kotlin
@Test
fun loadsItemById() = runTest {
    val fakeRepo = FakeItemRepository()
    val vm = DetailViewModel(
        itemId = "item-123",
        repository = fakeRepo,
        analytics = FakeAnalytics(),
    )
    advanceUntilIdle()
    assertEquals("item-123", vm.item.value?.id)
}
```

AssistedInject constructors are public — test directly without Hilt, passing fake dependencies and assisted params explicitly.

## AssistedInject vs alternatives

| Approach | When |
|----------|------|
| `@AssistedInject` | Object needs DI deps + runtime params |
| `@HiltViewModel` + SavedStateHandle | Params come from nav args saved in handle |
| Factory in module (`@Provides`) | Simple cases, no code generation needed |
| `@Inject constructor()` | No runtime params needed |

If your only runtime param is navigation args, `@HiltViewModel` with SavedStateHandle is simpler than full AssistedInject. Use AssistedInject when params come from non-navigation sources or you have multiple runtime params.

For broader Hilt patterns, see [Hilt dependency injection patterns](https://blog.michaelsam94.com/hilt-dependency-injection-patterns/) and [multibindings](https://blog.michaelsam94.com/android-hilt-multibindings/).

## AssistedInject with WorkManager

WorkManager workers need runtime params (task ID, retry count) plus DI dependencies:

```kotlin
@HiltWorker
class SyncWorker @AssistedInject constructor(
    @Assisted context: Context,
    @Assisted params: WorkerParameters,
    private val repository: DataRepository,
    private val analytics: AnalyticsTracker,
) : CoroutineWorker(context, params) {

    @AssistedFactory
    interface Factory : ChildWorkerFactory {
        override fun create(context: Context, params: WorkerParameters): SyncWorker
    }

    override suspend fun doWork(): Result {
        val taskId = inputData.getString("task_id") ?: return Result.failure()
        return try {
            repository.sync(taskId)
            Result.success()
        } catch (e: Exception) {
            if (runAttemptCount < 3) Result.retry() else Result.failure()
        }
    }
}
```

Register the factory in `@HiltWorkerFactory` — Hilt generates the wiring automatically.

## Multiple assisted parameters

AssistedInject supports multiple runtime parameters:

```kotlin
class OrderProcessor @AssistedInject constructor(
    @Assisted private val orderId: String,
    @Assisted private val priority: Int,
    private val paymentGateway: PaymentGateway,
    private val notificationService: NotificationService,
) {
    suspend fun process() { ... }
}

@AssistedFactory
interface OrderProcessorFactory {
    fun create(orderId: String, priority: Int): OrderProcessor
}
```

Each unique combination of assisted params creates a new instance — factory pattern keeps DI clean.

## Common AssistedInject mistakes

- **Using AssistedInject for navigation args** — `@HiltViewModel` + SavedStateHandle is simpler
- **Assisted param in singleton scope** — runtime params mean new instance each call; don't scope to singleton
- **Missing `@AssistedFactory`** — compilation error; factory interface required
- **Testing without factory** — test constructor directly, passing fakes for both assisted and injected params
- **AssistedInject in composables** — use ViewModel instead; composables shouldn't hold assisted instances

## Failure modes

- **AssistedInject for single nav arg** — over-engineering; use SavedStateHandle
- **Factory not registered with Hilt** — runtime crash on worker/service creation
- **Assisted params in @Singleton** — different callers get same instance with stale params
- **Missing @HiltWorker annotation** — WorkManager can't inject dependencies

## Production checklist

- AssistedInject used when 2+ runtime params or non-navigation params needed
- SavedStateHandle preferred for navigation args in ViewModels
- @AssistedFactory interface defined for every @AssistedInject class
- Workers use @HiltWorker with ChildWorkerFactory pattern
- Unit tests call constructor directly with fake dependencies

## Common production mistakes

Teams get hilt assisted injection wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping hilt assisted injection on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Resources

- [Hilt Assisted Injection guide](https://developer.android.com/training/dependency-injection/hilt-jetpack#assisted-injection)
- [Dagger AssistedInject documentation](https://dagger.dev/dev-guide/assisted-injection.html)
- [Hilt ViewModel documentation](https://developer.android.com/training/dependency-injection/hilt-jetpack#viewmodels)
- [Hilt Worker documentation](https://developer.android.com/training/dependency-injection/hilt-jetpack#workmanager)
- [SavedStateHandle process death survival](https://blog.michaelsam94.com/android-savedstatehandle-process-death/)
