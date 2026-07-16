---
title: "Surviving Process Death with SavedStateHandle"
slug: "android-savedstatehandle-process-death"
description: "Survive Android process death with SavedStateHandle: saving UI state, navigation args, Compose saveable, and testing process death scenarios."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Android", "Architecture", "Lifecycle", "Jetpack Compose"]
keywords: "SavedStateHandle process death, Android state restoration, ViewModel SavedStateHandle, survive process death Android, saved state ViewModel"
faq:
  - q: "What is process death on Android?"
    a: "Process death occurs when the system kills your app's process under memory pressure while it's in the background. When the user returns, the system recreates the Activity and restores saved state, but all in-memory objects (ViewModel fields, singleton caches) are gone. SavedStateHandle persists ViewModel state across process death automatically."
  - q: "What should I save in SavedStateHandle?"
    a: "Save UI state the user expects to persist: scroll position, form input, selected tab, filter settings, and in-progress edits. Don't save sensitive data (passwords, tokens), large objects (full lists — use Room instead), or derived state that can be recomputed from saved inputs."
  - q: "How do I test process death?"
    a: "Use 'Don't keep activities' in Developer Options for quick manual testing. In instrumentation tests, use ActivityScenario.recreate() or executeShellCommand('am kill package.name') followed by relaunch. For Compose, verify saveable state survives recreation."
---

Process death is the bug that only happens on your user's phone, never on yours. You background the app, the system kills the process to free memory, the user comes back — and your form is empty, the selected tab reset to zero, the scroll position lost. ViewModel survives configuration changes (rotation) but not process death. SavedStateHandle bridges that gap: it persists key-value state through the system's saved state bundle, automatically restored when the process is recreated. Every app with forms, filters, or multi-step flows needs this; most apps don't implement it until users complain.

## SavedStateHandle in ViewModel

```kotlin
@HiltViewModel
class EditorViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val repository: DocumentRepository,
) : ViewModel() {

    // Survives process death — backed by SavedStateHandle
    var title: String
        get() = savedStateHandle["title"] ?: ""
        set(value) { savedStateHandle["title"] = value }

    var body: String
        get() = savedStateHandle["body"] ?: ""
        set(value) { savedStateHandle["body"] = value }

    // Navigation arg — also in SavedStateHandle
    private val documentId: String = savedStateHandle["docId"] ?: ""

    // Transient state — NOT saved, reloaded from repository
    private val _document = MutableStateFlow<Document?>(null)
    val document: StateFlow<Document?> = _document.asStateFlow()

    init {
        if (documentId.isNotEmpty()) {
            viewModelScope.launch { _document.value = repository.get(documentId) }
        }
    }
}
```

Rule: if the user typed it or selected it, save it. If it came from the network/database, reload it.

## Compose saveable delegate

For Compose-first ViewModels, use the saveable property delegate:

```kotlin
@HiltViewModel
class SearchViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
) : ViewModel() {

    var query by savedStateHandle.saveable { mutableStateOf("") }
    var selectedFilter by savedStateHandle.saveable { mutableStateOf(Filter.ALL) }
    var scrollIndex by savedStateHandle.saveable { mutableIntStateOf(0) }
}
```

`saveable` handles types that implement `Saver` or are primitives/strings/Parcelable.

## Custom types with Saver

For complex UI state:

```kotlin
@Parcelize
data class FilterState(val category: String, val sortOrder: SortOrder) : Parcelable

var filter by savedStateHandle.saveable { mutableStateOf(FilterState("all", SortOrder.DATE)) }
// Parcelable types work automatically
```

For non-Parcelable custom types, provide a Saver:

```kotlin
var chartConfig by savedStateHandle.saveable(
    saver = Saver(
        save = { it.toJson() },
        restore = { ChartConfig.fromJson(it) }
    )
) { mutableStateOf(ChartConfig.default()) }
```

## Navigation args survive too

Arguments passed via Navigation Component are stored in SavedStateHandle:

```kotlin
// Navigate with arg
navController.navigate("editor/doc-123")

// ViewModel receives it
@HiltViewModel
class EditorViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
) : ViewModel() {
    private val docId: String = savedStateHandle.get<String>("docId")!!
}
```

With typed routes:

```kotlin
@Serializable data class EditorRoute(val docId: String)

// SavedStateHandle contains nav args automatically
private val docId = savedStateHandle.toRoute<EditorRoute>().docId
```

## Compose UI state

For state held in Composables (not ViewModel), use `rememberSaveable`:

```kotlin
@Composable
fun SearchBar() {
    var query by rememberSaveable { mutableStateOf("") }
    TextField(value = query, onValueChange = { query = it })
}
```

`rememberSaveable` survives both configuration changes and process death within the Activity's saved state.

## Testing process death

Manual testing:

```bash
# Enable "Don't keep activities" in Developer Options
# Or force-kill and relaunch:
adb shell am kill com.example.app
# Then reopen app from recents
```

Instrumentation test:

```kotlin
@Test
fun formStateSurvivesProcessDeath() {
    val scenario = ActivityScenario.launch(EditorActivity::class.java)
    onView(withId(R.id.titleInput)).perform(typeText("My Document"))
    scenario.recreate()
    onView(withId(R.id.titleInput)).check(matches(withText("My Document")))
}
```

For ViewModel state:

```kotlin
@Test
fun viewModelStateSurvivesRecreation() {
    val handle = SavedStateHandle(mapOf("title" to "Saved Title"))
    val vm = EditorViewModel(handle, fakeRepo)
    assertEquals("Saved Title", vm.title)
}
```

## What NOT to save

| Don't save | Why | Instead |
|-----------|-----|---------|
| Passwords, tokens | Security risk | Reload from secure storage |
| Full item lists | Bundle size limit (~1MB) | Room database |
| Computed/derived state | Redundant | Recompute from saved inputs |
| Sensitive PII | Saved state is not encrypted | Encrypted storage |

## SavedStateHandle vs Room vs DataStore

| Mechanism | Scope | Survives | Use for |
|-----------|-------|----------|---------|
| SavedStateHandle | ViewModel/Activity | Process death | UI state, form input |
| Room | App | Forever | Structured data |
| DataStore | App | Forever | Preferences, settings |

SavedStateHandle is for transient UI state the user expects to see when they return. Room is for data. Don't conflate them.

Test SavedStateHandle survival with `adb shell am kill` not just rotation — process death clears in-memory state that rotation preserves.

## Compose integration

In Compose, prefer `rememberSaveable` for UI-local state and ViewModel SavedStateHandle for business state:

```kotlin
@Composable
fun EditorScreen(viewModel: EditorViewModel = hiltViewModel()) {
    var expanded by rememberSaveable { mutableStateOf(false) }  // UI-only
    val title by viewModel.title.collectAsState()  // SavedStateHandle-backed
}
```

Don't duplicate state in both `rememberSaveable` and ViewModel — single source of truth per field.

## Bundle size limits

SavedState persists to a Bundle with ~1MB limit across all keys. Symptoms of overflow:

- `TransactionTooLargeException` on process death recovery
- Silent truncation on some OEM skins

Store IDs and flags in SavedStateHandle; load full objects from Room on init using saved IDs.

Pair with [Android lifecycle aware components](https://blog.michaelsam94.com/android-lifecycle-aware-components/) for understanding when state saves vs clears.

## Common production mistakes

Teams get savedstatehandle process death wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping savedstatehandle process death on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Debugging and triage workflow

When savedstatehandle process death misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [SavedStateHandle documentation](https://developer.android.com/topic/libraries/architecture/viewmodel/viewmodel-savedstate)
- [Save UI state (Android)](https://developer.android.com/topic/libraries/architecture/saving-states)
- [rememberSaveable in Compose](https://developer.android.com/reference/kotlin/androidx/compose/runtime/saveable/package-summary)
- [Lifecycle-aware components](https://blog.michaelsam94.com/android-lifecycle-aware-components/)
- [Assisted injection with SavedStateHandle](https://blog.michaelsam94.com/android-hilt-assisted-injection/)
