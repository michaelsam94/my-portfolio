---
title: "Testing Coroutines and Flows with Turbine"
slug: "testing-coroutines-flows-turbine"
description: "Turbine testing for coroutines and Flows: use runTest and StandardTestDispatcher to assert emissions without flaky sleeps or manual collection boilerplate."
datePublished: "2026-04-17"
dateModified: "2026-04-17"
tags: ["Kotlin", "Testing", "Coroutines"]
keywords: "Turbine testing, test coroutines, test Flow, runTest, StandardTestDispatcher, Flow testing Kotlin"
faq:
  - q: "What is Turbine for testing Kotlin Flows?"
    a: "Turbine is a small testing library from CashApp that turns Flow collection into a sequence of explicit assertions. Inside a test block you call flow.test { }, then use awaitItem, awaitComplete, and awaitError to consume emissions one at a time. It removes the manual collect-into-a-list boilerplate and, crucially, fails the test if you leave emissions unconsumed, which catches subtle Flow bugs."
  - q: "Why can't I just collect a Flow into a list in tests?"
    a: "You can for simple finite Flows, but it breaks down for hot or infinite Flows like StateFlow and SharedFlow, which never complete, so toList() hangs forever. It also can't easily assert ordering, timing between emissions, or that no extra items arrived. Turbine handles hot flows, enforces that every emission is accounted for, and gives precise per-item assertions."
  - q: "What does runTest do in coroutine tests?"
    a: "runTest is the coroutine test builder that runs your test body on a virtual-time test scheduler. It skips delays automatically so a delay(10_000) resolves instantly, controls dispatcher execution deterministically, and fails the test if coroutines are still running or leaked at the end. Combined with a TestDispatcher, it makes asynchronous code execute in a predictable, controllable order."
---

Asynchronous code is where flaky tests come from. A `Thread.sleep(500)` hoping a coroutine finished, an assertion that passes on your machine and fails in CI, a `StateFlow` test that hangs because the flow never completes — every Android team has these scars. The modern cure is three tools working together: `runTest` for virtual time, a `TestDispatcher` for deterministic scheduling, and Turbine for asserting `Flow` emissions cleanly. Together they let you test coroutines and flows without a single sleep and without the "collect into a list and hope" pattern that falls apart on hot flows.

I've deleted a lot of `delay`-based test hacks after adopting this stack, and the payoff is tests that are both faster (virtual time skips delays instantly) and honest (they fail loudly when an emission is missing or extra). Let me build it up from the coroutine primitives to Turbine.

## runTest and virtual time

The foundation is `runTest`, which runs your test body on a scheduler that controls time. A `delay(10_000)` inside doesn't wait ten seconds — the scheduler advances virtual time and it resolves immediately. It also fails the test if coroutines leak past the end of the body, catching a whole class of "forgot to cancel" bugs.

```kotlin
@Test
fun loadsUser() = runTest {
    val repo = FakeUserRepository(delayMs = 5_000)  // simulated slow network
    val user = repo.getUser("42")                    // resolves instantly under runTest
    assertEquals("Ada", user.name)
}
```

That `5_000` ms delay costs zero real time. This is the first reason to stop using `Thread.sleep` in tests: virtual time makes waiting *deterministic* instead of a race, so a test either asserts the right thing or fails — it never "usually passes."

## Choosing the right TestDispatcher

There are two `TestDispatcher` flavors, and the choice changes behavior:

- **`StandardTestDispatcher`** queues new coroutines rather than running them eagerly. Nothing runs until you yield or call `advanceUntilIdle()`. This mirrors real dispatch and is best when you want to control *when* coroutines proceed — for example, asserting an intermediate loading state before completion.
- **`UnconfinedTestDispatcher`** runs new coroutines eagerly up to their first suspension. Less realistic, but convenient when you just want the flow to make progress without manual advancement.

My default is `StandardTestDispatcher`, because it forces me to be explicit about scheduling and exposes ordering bugs that `Unconfined` papers over. For a ViewModel test where I want to observe `Loading` then `Success`, standard is the only one that reliably lets me catch the intermediate state:

```kotlin
@Test
fun emitsLoadingThenSuccess() = runTest {
    val dispatcher = StandardTestDispatcher(testScheduler)
    val vm = UserViewModel(repo, dispatcher)

    assertEquals(UiState.Loading, vm.state.value)  // before advancing
    advanceUntilIdle()                              // let the coroutine finish
    assertEquals(UiState.Success("Ada"), vm.state.value)
}
```

Injecting the dispatcher (rather than hardcoding `Dispatchers.IO`) is the design decision that makes this testable at all — a theme that runs through all the [Kotlin coroutines and Flow patterns](https://blog.michaelsam94.com/kotlin-coroutines-flow-patterns/) worth adopting: pass dispatchers in, never reach for the global ones inside a class you want to test.

## Where Turbine earns its place

Now the flow half. You *can* collect a finite flow into a list with `toList()`. But try that on a `StateFlow` or `SharedFlow` and it hangs forever — hot flows never complete. Turbine solves this by letting you consume emissions one at a time inside a `test { }` block:

```kotlin
@Test
fun searchEmitsResults() = runTest {
    val vm = SearchViewModel(repo)

    vm.results.test {
        assertEquals(emptyList(), awaitItem())     // initial state
        vm.search("kotlin")
        assertEquals(SearchState.Loading, awaitItem())
        assertEquals(expectedResults, awaitItem())
        cancelAndIgnoreRemainingEvents()
    }
}
```

`awaitItem()` suspends until the next emission arrives (in virtual time), then returns it. You assert each emission in order, which makes the *sequence* — not just the final value — part of the contract. And Turbine's best feature is strictness: if the flow emits something you didn't consume, or completes when you expected an item, the test fails. That catches the subtle bugs — an extra emission from an over-eager `combine`, a missing `Loading` state — that a `toList()` assertion silently swallows.

## The Turbine API you'll actually use

A handful of calls cover almost everything:

| Call | Purpose |
| --- | --- |
| `awaitItem()` | Assert and return the next emission |
| `awaitComplete()` | Assert the flow completed |
| `awaitError()` | Assert the flow terminated with an exception |
| `expectNoEvents()` | Assert nothing was emitted (e.g. after debounce) |
| `cancelAndIgnoreRemainingEvents()` | Stop collecting a hot flow cleanly |
| `skipItems(n)` | Ignore n emissions you don't care about |

`expectNoEvents()` is underused and genuinely valuable. Testing a debounced search? Emit a keystroke, `expectNoEvents()`, advance virtual time past the debounce window, *then* `awaitItem()`. That proves the debounce actually suppressed the intermediate value — something almost impossible to assert reliably with sleeps.

## Testing operators and error paths

Turbine shines for the tricky operators. Take a `debounce` + `distinctUntilChanged` pipeline — the exact place bugs hide:

```kotlin
@Test
fun debouncesRapidInput() = runTest {
    val queries = MutableStateFlow("")
    val debounced = queries.debounce(300).distinctUntilChanged()

    debounced.test {
        assertEquals("", awaitItem())
        queries.value = "k"
        queries.value = "ko"
        queries.value = "kot"
        expectNoEvents()          // nothing yet — still within debounce window
        advanceTimeBy(301)
        assertEquals("kot", awaitItem())   // only the settled value
        cancelAndIgnoreRemainingEvents()
    }
}
```

That test would be a nightmare of `sleep` calls without virtual time and Turbine. Error paths are equally clean: make the source throw, then assert with `awaitError()` and inspect the exception type. Testing that a flow *recovers* via `catch` becomes a precise sequence of `awaitItem()` calls rather than guesswork.

This flow-level rigor complements UI-level testing rather than replacing it. I test the ViewModel's flow contract with Turbine and the rendered result with the tools in [testing Compose UIs](https://blog.michaelsam94.com/testing-compose-uis-v2/) — the flow test proves the state machine is correct, the Compose test proves the screen reflects it. Splitting responsibilities that way keeps each test focused and fast.

The overall discipline: inject dispatchers, run under `runTest` with `StandardTestDispatcher`, and assert flows with Turbine's item-by-item strictness. Do that and your async tests stop being the flaky, slow part of the suite and become the part you actually trust. No sleeps, no races, no "re-run CI and hope" — just deterministic assertions about what your coroutines and flows really do.

## Resources

- [Turbine on GitHub (CashApp)](https://github.com/cashapp/turbine)
- [Testing Kotlin coroutines — official guide](https://kotlinlang.org/docs/coroutines-testing.html)
- [Test your Flows — Android documentation](https://developer.android.com/kotlin/flow/test)
- [kotlinx-coroutines-test reference](https://github.com/Kotlin/kotlinx.coroutines/tree/master/kotlinx-coroutines-test)
- [Kotlin Flow documentation](https://kotlinlang.org/docs/flow.html)
