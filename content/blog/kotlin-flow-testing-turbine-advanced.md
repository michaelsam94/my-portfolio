---
title: "Advanced Flow Testing with Turbine"
slug: "kotlin-flow-testing-turbine-advanced"
description: "Advanced Kotlin Flow testing with Turbine: awaitItem, skipItems, expectNoEvents, SharedFlow replay, and runTest integration for reliable stream assertions."
datePublished: "2025-12-07"
dateModified: "2025-12-07"
tags: ["Android", "Kotlin"]
keywords: "Turbine, Flow testing, awaitItem, runTest, SharedFlow, StateFlow, kotlinx.coroutines.test"
faq:
  - q: "Why use Turbine instead of collecting Flows into lists?"
    a: "List collection hides timing— you miss intermediate states, duplicate emissions, or spurious events. Turbine asserts event-by-event with timeouts and explicit completion, catching extra emissions that toList() would silently include."
  - q: "How does Turbine work with runTest virtual time?"
    a: "When you use turbine { } inside runTest, awaitItem uses the test scheduler for timeouts— delays in the Flow under test advance with advanceTimeBy. This keeps Flow tests fast and synchronized with coroutine tests."
  - q: "What causes Turbine 'No items were collected' errors?"
    a: "Usually the Flow is cold and nobody collected yet, SharedFlow has no replay and you subscribed late, or you forgot advanceUntilIdle before awaitItem. For StateFlow, remember it replays the current value immediately on collect."
---

Collecting a Flow into a `List` told us the ViewModel worked. Turbine told us it emitted `Loading` twice, skipped `Empty`, then hit `Success`—because a race restarted load when `refresh()` fired during init. The list had three items; the bug was the order and duplicate loading state. **Turbine** exists for that level of scrutiny.

[Turbine](https://github.com/cashapp/turbine) is a small test library for Kotlin Flows. It provides a `test { }` block, `awaitItem()`, completion assertions, and negative assertions (`expectNoEvents`) that list collectors cannot express.

## Basic pattern

```kotlin
@Test
fun `emits loading then success`() = runTest {
    repository.results.test {
        repository.fetch()
        assertEquals(Loading, awaitItem())
        advanceUntilIdle()
        assertEquals(Success(data), awaitItem())
        awaitComplete()
    }
}
```

Or extension style:

```kotlin
viewModel.uiState.test {
    assertEquals(UiState.Idle, awaitItem())
    viewModel.onAction(Load)
    assertEquals(UiState.Loading, awaitItem())
    advanceUntilIdle()
    assertEquals(UiState.Data(items), awaitItem())
    cancelAndIgnoreRemainingEvents()
}
```

## StateFlow and SharedFlow nuances

**StateFlow** always emits current value first:

```kotlin
@Test
fun stateFlow() = runTest {
    val state = MutableStateFlow(0)
    state.test {
        assertEquals(0, awaitItem()) // immediate replay
        state.value = 1
        assertEquals(1, awaitItem())
    }
}
```

**SharedFlow** without replay emits nothing until new events:

```kotlin
val events = MutableSharedFlow<Event>(replay = 0)

events.test {
    expectNoEvents()
    events.emit(Event.Click)
    assertEquals(Event.Click, awaitItem())
}
```

Set `replay = 1` if subscribers need last event—test accordingly.

## skipItems and takeItems

When initial emissions are irrelevant:

```kotlin
flow.test {
    skipItems(1) // skip initial StateFlow value
    triggerUpdate()
    assertEquals(expected, awaitItem())
}
```

For long streams, `awaitItem()` in a loop with timeout guards against infinite hangs.

## expectNoEvents and debounce

Verify silence during debounce window:

```kotlin
@Test
fun debouncedSearch() = runTest {
    viewModel.queryFlow.test {
        viewModel.onQuery("k")
        viewModel.onQuery("ko")
        viewModel.onQuery("kot")
        expectNoEvents()
        advanceTimeBy(300)
        assertEquals("kot", awaitItem())
    }
}
```

`expectNoEvents()` fails fast if anything arrives—critical for debounce and distinctUntilChanged.

## Error and completion

```kotlin
failingFlow.test {
    val error = awaitError()
    assertIs<IOException>(error)
}

finiteFlow.test {
    awaitItem()
    awaitComplete()
}
```

Do not call `awaitItem()` after `awaitComplete()`.

## Testing combine and flatMapLatest

`flatMapLatest` cancels prior inner Flows—assert cancellation by expecting no further items from old search:

```kotlin
@Test
fun flatMapLatestSwitch()() = runTest {
    repository.searchResults.test {
        repository.search("a")
        advanceUntilIdle()
        assertEquals(resultsForA, awaitItem())

        repository.search("ab")
        advanceUntilIdle()
        assertEquals(resultsForAb, awaitItem())
        expectNoEvents() // no stale "a" results
    }
}
```

## Timeout tuning

Default await timeout is 3 seconds real time—fine locally. In CI with loaded runners, failures may be slow tests not logic bugs. Keep heavy work mocked; Turbine timeouts should never be the bottleneck.

Use `cancelAndIgnoreRemainingEvents()` when testing partial behavior—avoids Turbine reporting unconsumed events at block exit.

## Testing SharedFlow replay buffers

When `replay = 2`, Turbine receives buffered items immediately on subscribe—account for that in assertions:

```kotlin
@Test
fun replayBuffer() = runTest {
    val flow = MutableSharedFlow<Int>(replay = 2)
    flow.emit(1)
    flow.emit(2)
    flow.test {
        assertEquals(1, awaitItem())
        assertEquals(2, awaitItem())
    }
}
```

## cancelAndConsumeRemainingEvents

Use when testing fire-and-forget side effects without caring about trailing emissions—prevents test failure on unconsumed hot flow events after assertions complete.


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

- [Turbine GitHub README](https://github.com/cashapp/turbine/blob/main/README.md) — API reference and examples
- [Cash App Turbine talk notes](https://code.cash.app/turbine) — design rationale
- [kotlinx-coroutines Flow guide](https://kotlinlang.org/docs/flow.html) — cold vs hot flows
- [Testing Flow on Android](https://developer.android.com/kotlin/flow/test) — official patterns with runTest
