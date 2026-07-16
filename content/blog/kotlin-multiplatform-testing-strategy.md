---
title: "A Testing Strategy for Kotlin Multiplatform"
slug: "kotlin-multiplatform-testing-strategy"
description: "A practical Kotlin Multiplatform testing strategy: what to test in commonTest, when to run on each platform, and how to fake platform code without pain."
datePublished: "2024-09-22"
dateModified: "2024-09-22"
tags: ["Kotlin", "Kotlin Multiplatform", "Testing", "Android"]
keywords: "Kotlin Multiplatform testing, commonTest, KMP unit tests, kotlin.test, runTest multiplatform, expect actual testing"
faq:
  - q: "Where should Kotlin Multiplatform tests live?"
    a: "Put the bulk of your tests in commonTest so they run on every target and verify the shared logic once. Add platform-specific tests in androidUnitTest, iosTest, or jvmTest only for code that genuinely differs per platform or exercises real platform APIs. This keeps most of your suite fast and portable while still catching platform-specific regressions."
  - q: "How do I test suspend functions in KMP?"
    a: "Use kotlinx-coroutines-test's runTest, which works across targets and gives you a virtual scheduler so delays don't slow the suite. Inject a dispatcher rather than hardcoding Dispatchers.Main or Dispatchers.IO so tests can swap in a test dispatcher. Avoid Dispatchers.Main in common tests unless you've set up a test main dispatcher, since not all targets provide one by default."
  - q: "How do I fake platform-specific code in common tests?"
    a: "Model platform behavior behind a common interface and inject a fake implementation in commonTest, rather than trying to override an expect/actual declaration. You can't substitute an actual class per test because it's resolved at compile time. Depending on interfaces instead of expect classes is what makes common logic testable in isolation."
---

The best thing about Kotlin Multiplatform testing is also the thing teams miss: a test written in `commonTest` runs on *every* target you configure. Write the logic once, verify it once, and get Android, iOS, and JVM coverage from the same source. The teams that get value from KMP testing lean into that — they push logic into common code specifically so they can test it in one place — and the teams that struggle are usually the ones that spread testable logic across platform source sets where it has to be re-verified per target.

So a KMP testing strategy is really a question of *where each kind of test lives*, and how you structure code so the answer is "mostly `commonTest`."

## The source-set map for tests

Mirror your production source sets in test source sets:

- **`commonTest`** — the center of gravity. Pure logic: parsing, mapping, validation, state reduction, use cases. Uses `kotlin.test` assertions so it compiles on all targets. This should be the largest test source set by far.
- **`jvmTest` / `androidUnitTest`** — JVM-only tests, and the place you can use JUnit, MockK, or heavier tooling when you need it. Good for testing the JVM/Android bindings of your platform interfaces.
- **`iosTest`** (and other native test source sets) — run on the simulator via the Kotlin/Native test runner. Slower to spin up, so reserve them for genuinely platform-specific behavior.

The rule I give teams: **if a test doesn't need a platform API, it belongs in `commonTest`.** Putting a pure-logic test in `androidUnitTest` out of habit means iOS never runs it.

## kotlin.test is your common assertion library

`commonTest` can't use JUnit directly because JUnit is JVM-only. `kotlin.test` provides a multiplatform assertion API that maps to the right runner per target — JUnit on JVM/Android, the native runner on Apple targets.

```kotlin
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class PriceFormatterTest {
    @Test
    fun formats_whole_amounts_without_decimals() {
        assertEquals("$5", formatPrice(500, "USD"))
    }

    @Test
    fun rejects_negative_amounts() {
        assertFailsWith<IllegalArgumentException> { formatPrice(-1, "USD") }
    }
}
```

This exact test now runs on Android, iOS, and JVM. That's the payoff: one assertion, three platforms, no duplication.

## Testing coroutines with runTest

Most shared logic is asynchronous, and `kotlinx-coroutines-test` is multiplatform. `runTest` gives you a virtual clock so `delay` calls resolve instantly, and it works on every target.

```kotlin
class SyncUseCaseTest {
    @Test
    fun retries_then_succeeds() = runTest {
        val api = FakeApi(failTimes = 2)
        val useCase = SyncUseCase(api, dispatcher = StandardTestDispatcher(testScheduler))
        val result = useCase.run()
        assertEquals(3, api.callCount)
        assertTrue(result.isSuccess)
    }
}
```

The critical enabler is *not hardcoding dispatchers*. If `SyncUseCase` reaches for `Dispatchers.IO` internally, you can't control timing in the test. Inject the dispatcher and pass a test dispatcher in tests — the same injectable-dispatcher discipline that keeps [coroutine and Flow code](https://blog.michaelsam94.com/kotlin-coroutines-flow-patterns/) testable applies verbatim in KMP.

## Fake platform code with interfaces, not actuals

Here's the trap that eats afternoons: you have an `expect class DeviceInfo` with an `actual` per platform, and now you want to test common code that depends on it. You can't — `actual` declarations are resolved at compile time per target, so there's no seam to substitute a fake in `commonTest`.

The fix is architectural, not a testing trick: depend on a *common interface*, inject the implementation, and provide a fake in tests.

```kotlin
// common
interface DeviceInfo { val osVersion: String; val isTablet: Boolean }

// commonTest
class FakeDeviceInfo(
    override val osVersion: String = "test",
    override val isTablet: Boolean = false,
) : DeviceInfo

class LayoutDeciderTest {
    @Test
    fun tablet_gets_two_pane() {
        val decider = LayoutDecider(FakeDeviceInfo(isTablet = true))
        assertEquals(Layout.TwoPane, decider.choose())
    }
}
```

This is the same reasoning behind preferring interfaces over `expect class` for anything with logic — covered in [expect/actual patterns that scale](https://blog.michaelsam94.com/kotlin-multiplatform-expect-actual-patterns/). Structure for injection and your common logic becomes trivially fakeable.

## What to run where in CI

You don't need to run every target on every commit if that's slow. A pragmatic tiering:

1. **On every PR:** `commonTest` via the JVM target — fast, catches the vast majority of logic regressions.
2. **On every PR:** `androidUnitTest` if you have Android-specific bindings.
3. **Nightly or on release branches:** the iOS simulator tests, which are slower to boot. This catches platform-specific issues without paying the simulator cost on every push.

The insight is that because `commonTest` logic is platform-independent by construction, running it once on the JVM gives you high confidence cheaply; the native runs are there to catch the platform bindings, which change less often.

## A quick anti-pattern list

- **Logic stuck in `androidUnitTest`** that could be common — iOS silently loses coverage.
- **Hardcoded dispatchers** in shared code — makes coroutine tests flaky or slow.
- **Trying to mock `actual` declarations** — impossible; use interfaces.
- **Real network or clock in common tests** — inject fakes; a test that hits the network isn't a unit test on any platform.

## What I'd take away

Make `commonTest` the heart of your suite: write pure logic there against `kotlin.test`, test coroutines with `runTest` and injected dispatchers, and fake platform behavior through common interfaces rather than fighting `expect`/`actual`. Reserve platform test source sets for the thin bindings that actually touch platform APIs, and tier your CI so the fast common tests gate every PR while slower simulator runs happen less often. Done that way, KMP testing delivers its promise — verify once, cover everywhere — instead of becoming three parallel suites in disguise.

## Resources

- [Kotlin Multiplatform — test your code](https://kotlinlang.org/docs/multiplatform-run-tests.html)
- [kotlin.test API reference](https://kotlinlang.org/api/latest/kotlin.test/)
- [Testing Kotlin coroutines (kotlinx-coroutines-test)](https://kotlinlang.org/docs/coroutines-testing.html)
- [Android — test your app's Kotlin code](https://developer.android.com/kotlin/multiplatform)
