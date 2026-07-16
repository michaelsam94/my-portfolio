---
title: "Sharing ViewModels in Kotlin Multiplatform"
slug: "kotlin-multiplatform-viewmodel-shared"
description: "Share ViewModels across Android and iOS in KMP: androidx lifecycle multiplatform, StateFlow UI state, SwiftUI integration, and SavedStateHandle patterns."
datePublished: "2025-12-23"
dateModified: "2025-12-23"
tags: ["Android", "Kotlin"]
keywords: "KMP ViewModel, shared ViewModel, Kotlin Multiplatform, StateFlow, SwiftUI, lifecycle-viewmodel"
faq:
  - q: "Can I use Android ViewModel in commonMain?"
    a: "Yes, with androidx.lifecycle ViewModel KMP artifacts. ViewModel, viewModelScope, and SavedStateHandle have multiplatform versions. Place feature ViewModels in commonMain and collect state from Android Compose and iOS SwiftUI."
  - q: "How does iOS observe Kotlin ViewModel state?"
    a: "Expose StateFlow or MutableStateFlow from the ViewModel. Swift uses SKIE, KMP-NativeCoroutines, or manual collectors to bridge Flow to ObservableObject. State updates drive SwiftUI views the same way as on Android."
  - q: "Where should navigation logic live in KMP?"
    a: "Keep navigation platform-specific—Compose Navigation on Android, SwiftUI NavigationStack on iOS. ViewModels emit one-shot events or state flags; UI layers translate to routes. Shared navigation abstractions often over-couple platforms."
---

The product team wanted identical checkout logic on Android and iOS. Duplicating validation rules failed twice before we moved `CheckoutViewModel` into `commonMain` with a single `CheckoutUiState` data class. Android wired it through `viewModel()`; iOS held the same instance in a `ObservableViewModel` wrapper. Bug fixes shipped once.

**Shared ViewModels** are viable in modern KMP thanks to androidx lifecycle multiplatform support. Business logic, state reduction, and coroutine scope management live in common code; platforms only render state and forward intents.

## Dependencies

```kotlin
// commonMain
commonMain.dependencies {
    implementation("org.jetbrains.androidx.lifecycle:lifecycle-viewmodel-compose:2.8.4")
    implementation("org.jetbrains.androidx.lifecycle:lifecycle-runtime-compose:2.8.4")
}
```

Align versions with Kotlin and Compose Multiplatform BOM.

## Shared ViewModel

```kotlin
// commonMain
data class CheckoutUiState(
    val items: ImmutableList<LineItem>,
    val total: Money,
    val submitting: Boolean = false,
    val error: String? = null
)

class CheckoutViewModel(
    private val repository: CheckoutRepository
) : ViewModel() {

    private val _state = MutableStateFlow(CheckoutUiState(emptyList(), Money.ZERO))
    val state: StateFlow<CheckoutUiState> = _state.asStateFlow()

    fun submit() {
        viewModelScope.launch {
            _state.update { it.copy(submitting = true, error = null) }
            repository.submitOrder()
                .onSuccess { /* navigate via event */ }
                .onFailure { e ->
                    _state.update { it.copy(submitting = false, error = e.message) }
                }
        }
    }
}
```

## Android integration

```kotlin
@Composable
fun CheckoutRoute(
    viewModel: CheckoutViewModel = viewModel { CheckoutViewModel(AppGraph.checkoutRepository) }
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    CheckoutScreen(state = state, onSubmit = viewModel::submit)
}
```

Use Koin or manual factory in `viewModel { }`.

## iOS integration

Hold ViewModel at screen scope:

```kotlin
// iosMain helper
class CheckoutController(
    repository: CheckoutRepository
) {
    val viewModel = CheckoutViewModel(repository)
}
```

Swift with SKIE or NativeCoroutines:

```swift
struct CheckoutView: View {
    @StateViewModel var viewModel = CheckoutController(repository: ...).viewModel

    var body: some View {
        let state = viewModel.state.value
        // render state
    }
}
```

Exact Swift API depends on coroutines bridge choice—pick one per project.

## One-shot events

Avoid navigation state in UiState when possible. Use `Channel` or sharedFlow for events:

```kotlin
private val _events = Channel<CheckoutEvent>(Channel.BUFFERED)
val events = _events.receiveAsFlow()

// after success
_events.send(CheckoutEvent.NavigateToConfirmation(orderId))
```

UI collects events in LaunchedEffect / Swift task and consumes once.

## SavedStateHandle

For process death on Android and equivalent on iOS where supported:

```kotlin
class DetailViewModel(
    savedStateHandle: SavedStateHandle,
    private val repo: ItemRepository
) : ViewModel() {
    private val itemId: String = savedStateHandle["itemId"] ?: error("id required")
}
```

Pass arguments through platform navigation into SavedStateHandle factory.

## Testing shared ViewModels

```kotlin
@Test
fun submitFailure() = runTest {
    val vm = CheckoutViewModel(FailingRepository())
    vm.submit()
    advanceUntilIdle()
    assertNotNull(vm.state.value.error)
    assertFalse(vm.state.value.submitting)
}
```

No Android framework needed—ViewModel test artifacts work in commonTest.

## Pitfalls

- Leaking `Context` or UI types into ViewModel
- Platform-specific formatting in ViewModel—pass locale-aware formatters in
- Creating new ViewModel per recomposition on iOS—scope to screen lifetime

## Process death on Android

SavedStateHandle survives process death; iOS has no equivalent—persist critical state to repository or local store on iOS when user backgrounds during multi-step flows.

Document platform differences in feature specs so QA tests both behaviors.


## What to measure after rollout

Track error rates, tail latency, and resource utilization for two weeks after changes land—most regressions appear under real traffic mixes, not in staging smoke tests. Keep a rollback path documented: feature flags, Helm revision, or Git revert with known good digest. Review on-call pages tied to the topic quarterly; delete alerts that never fire and add thresholds that would have caught your last incident.

Run a short blameless postmortem if production surprised you, even for minor issues. The goal is updating this runbook section with one concrete lesson per quarter so the next engineer inherits context, not just configuration snippets.


## Documentation your team should maintain

Maintain a one-page runbook link from your main service README: prerequisites, owner rotation, last drill date, and known sharp edges. Link to vendor docs in the Resources section below but capture org-specific decisions (CIDR ranges, cluster names, approval gates) in internal docs that stay current. New hires should deploy a safe canary within a week using only that runbook—if they cannot, the doc is incomplete.


## Pre-production checklist

Before promoting to production, walk through this list with someone who was not the primary author—fresh eyes catch assumptions.

- **Staging parity**: The staging environment exercises the same code paths as production, including failure modes you expect to handle (timeouts, retries, partial outages).
- **Observability**: Dashboards and alerts exist for the metrics and log patterns discussed above; on-call knows where to look first.
- **Rollback**: You can revert to the previous known-good state in one documented step without improvising.
- **Access control**: Only the principals that need access have it; audit logs are enabled where the topic touches secrets or infrastructure APIs.
- **Load test**: You have evidence—not intuition—about behavior at expected peak plus headroom.

If any item is "we will do that later," treat it as a release blocker for tier-1 services.


## Common questions from reviewers

Reviewers and auditors often ask whether this approach scales with team growth and whether it fails safely. Answer explicitly in your design doc: what happens when dependencies are down, when credentials expire, and when traffic doubles overnight. Prefer defaults that deny or degrade gracefully over defaults that fail open. Document known limits (throughput ceilings, supported versions, regions) in the same place operators look during incidents—avoid scattering critical constraints across Slack threads.


## Version and compatibility notes

Pin library and control-plane versions in production manifests; track upstream release notes quarterly. Run upgrade drills in non-production before bumping minor versions that touch serialization, auth, or CRD schemas. Keep a compatibility matrix in your internal wiki listing supported Kubernetes, broker, and SDK versions validated together.

## Resources

- [ViewModel KMP documentation](https://developer.android.com/kotlin/multiplatform/viewmodel) — official androidx guidance
- [Lifecycle KMP artifacts](https://developer.android.com/jetpack/androidx/releases/lifecycle) — version matrix
- [SKIE for Swift interop](https://skie.touchlab.co/) — Flow and suspend bridging
- [KMP-NativeCoroutines](https://github.com/rickclephas/KMP-NativeCoroutines) — alternative Flow bridge
