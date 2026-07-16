---
title: "Testing Coroutines with runTest"
slug: "kotlin-coroutines-testing-runtest"
description: "Test Kotlin coroutines with runTest: virtual time, TestDispatcher, advanceUntilIdle, and patterns for ViewModels, repositories, and structured concurrency."
datePublished: "2025-11-29"
dateModified: "2025-11-29"
tags: ["Android", "Kotlin"]
keywords: "runTest, kotlinx-coroutines-test, TestDispatcher, virtual time, advanceUntilIdle, coroutine testing"
faq:
  - q: "Why not use runBlocking in coroutine tests?"
    a: "runBlocking uses real time and blocks the test thread. Slow delays make tests flaky and slow. runTest uses a TestDispatcher with virtual time—delay(5000) completes instantly when you advance the clock. Tests become deterministic and fast."
  - q: "What is the difference between StandardTestDispatcher and UnconfinedTestDispatcher?"
    a: "StandardTestDispatcher queues coroutines until you call runCurrent or advanceUntilIdle—explicit control. UnconfinedTestDispatcher executes eagerly on the calling thread until the first suspension, which can surprise you with ordering. Standard is the default choice for most unit tests."
  - q: "How do I inject TestDispatcher into classes under test?"
    a: "Pass a CoroutineDispatcher constructor parameter or use a test rule that sets Dispatchers.setMain(testDispatcher) for Android ViewModel tests. Avoid hardcoding Dispatchers.IO in code you want to test—inject dispatchers or use a CoroutineScope you control in tests."
---

A ViewModel test flaked three times in CI before someone noticed `delay(300)` in debounce logic was running real time on a loaded runner. The fix was not increasing timeouts—it was `runTest { advanceTimeBy(300) }` so the debounce fired instantly and deterministically. Coroutine tests fail when they respect wall clock; they pass when you control virtual time.

**runTest** from `kotlinx-coroutines-test` is the standard harness for coroutine unit tests. It installs a `TestScope`, tracks unfinished coroutines, and throws if work leaks after the test body completes.

## Basic runTest structure

```kotlin
@Test
fun `loads data on init`() = runTest {
    val repository = FakeRepository()
    val viewModel = ItemViewModel(repository, this)

    viewModel.load()
    advanceUntilIdle()

    assertEquals(listOf("item-1"), viewModel.state.value.items)
}
```

`advanceUntilIdle()` runs all pending tasks until the dispatcher queue is empty.

Dependencies:

```kotlin
testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.9.0")
```

## Virtual time and delays

```kotlin
@Test
fun `retries after backoff`() = runTest {
    val api = FlakyApi(failuresBeforeSuccess = 2)
    val client = RetryClient(api, delayMs = 1_000)

    val deferred = async { client.fetch() }
    advanceTimeBy(1_000) // first retry
    advanceTimeBy(1_000) // second retry
    advanceUntilIdle()

    assertEquals("ok", deferred.await())
}
```

Without advancing time, `delay(1000)` suspends forever in StandardTestDispatcher.

## StandardTestDispatcher explicitly

```kotlin
@Test
fun `emits in order`() = runTest {
    val dispatcher = StandardTestDispatcher(testScheduler)
    val scope = TestScope(dispatcher)

    scope.launch {
        repo.observe().collect { emitted.add(it) }
    }

    repo.emit("a")
    runCurrent() // execute tasks scheduled until next suspend
    assertEquals(listOf("a"), emitted)
}
```

`runCurrent()` vs `advanceUntilIdle()`: use `runCurrent` when you want step-by-step assertions mid-flow.

## Testing ViewModels with Dispatchers.Main

```kotlin
@OptIn(ExperimentalCoroutinesApi::class)
class MainDispatcherRule(
    private val dispatcher: TestDispatcher = StandardTestDispatcher()
) : TestWatcher() {
    override fun starting(description: Description) {
        Dispatchers.setMain(dispatcher)
    }
    override fun finished(description: Description) {
        Dispatchers.resetMain()
    }
}

@Test
fun `viewModel uses main`() = runTest {
    val viewModel = UserViewModel(repo)
    viewModel.onRefresh()
    advanceUntilIdle()
    assertFalse(viewModel.uiState.value.loading)
}
```

Combine `@get:Rule val main = MainDispatcherRule()` with `runTest` sharing the same scheduler when using `StandardTestDispatcher(testScheduler)`.

## Exception and cancellation testing

runTest fails if coroutines launch but never complete:

```kotlin
@Test
fun `cancels work when scope cleared`() = runTest {
    val job = launch { longRunningWork() }
    job.cancel()
    advanceUntilIdle()
    assertTrue(job.isCancelled)
}
```

Use `assertThrows<CancellationException>` for explicit cancellation paths.

For expected exceptions in child coroutines, use `SupervisorJob` in production code and assert error states—not uncaught test failures.

## Turbine for Flow tests

Pair runTest with Turbine for Flow assertions:

```kotlin
@Test
fun `state flow updates`() = runTest {
    viewModel.uiState.test {
        assertEquals(Loading, awaitItem())
        advanceUntilIdle()
        assertEquals(Success(data), awaitItem())
        cancelAndIgnoreRemainingEvents()
    }
}
```

Turbine's `awaitItem()` respects test scheduler when configured with the same scope.

## Common mistakes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| Hardcoded Dispatchers.IO | Test hangs or uses real time | Inject dispatcher |
| Missing advanceUntilIdle | Assertions see stale state | Advance after actions |
| GlobalScope in code under test | runTest reports uncaught jobs | Refactor to injected scope |
| Mixing runBlocking + runTest | Nondeterministic ordering | runTest only |

## TestScope vs runTest timeout

`runTest` default timeout catches leaked coroutines. Long integration tests may need `runTest(timeout = 30.seconds)`—but prefer splitting true integration tests to separate JVM suite without virtual time.


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


## Resources

- [kotlinx-coroutines-test API](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-test/) — runTest, TestScope, TestDispatcher
- [Testing coroutines guide](https://developer.android.com/kotlin/coroutines/test) — Android documentation for ViewModel testing
- [Coroutines test README](https://github.com/Kotlin/kotlinx.coroutines/blob/master/kotlinx-coroutines-test/README.md) — migration notes from older test APIs
- [Turbine library](https://github.com/cashapp/turbine) — Flow testing companion to runTest
