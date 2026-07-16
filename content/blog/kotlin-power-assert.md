---
title: "Kotlin Power-Assert for Readable Test Failures"
slug: "kotlin-power-assert"
description: "Kotlin power-assert rewrites plain assert calls to show every intermediate value in the failure, so you stop guessing why an assertion failed and read the answer."
datePublished: "2026-04-07"
dateModified: "2026-04-07"
tags: ["Kotlin", "Testing", "Android"]
keywords: "Kotlin power-assert, assert plugin, readable assertions, Kotlin 2.x testing, test diagnostics"
faq:
  - q: "What is the Kotlin power-assert compiler plugin?"
    a: "Power-assert is an official Kotlin compiler plugin that rewrites calls to assert and other configured functions so that when the assertion fails, the error message includes the value of every sub-expression in the condition. Instead of a bare 'Assertion failed', you get a diagram showing exactly which part of the expression evaluated to what, which usually tells you the cause without opening a debugger."
  - q: "Does power-assert affect production or release builds?"
    a: "No. It only transforms functions you explicitly list in the plugin configuration, and standard library assert is a no-op unless assertions are enabled on the JVM. You typically enable it for test source sets, so it adds diagnostics to test failures without touching your shipped code paths."
  - q: "Can power-assert enhance functions other than assert?"
    a: "Yes. You configure a list of fully qualified functions to transform — commonly kotlin.assert, kotlin.test.assertTrue, and require. Any boolean-condition function you register gets the same expression-diagram treatment, so you can point it at your existing assertion helpers."
---

`Assertion failed`. That's the entire message the JVM gives you when a plain `assert(order.total == expected.total)` fails, and it's useless — you know *that* it failed, not *why*. The Kotlin power-assert plugin fixes this by rewriting the assertion at compile time so the failure prints every intermediate value in the expression, laid out as a diagram under the source line. You go from a one-word insult to a readable breakdown that usually points straight at the bug.

I turned it on across a multi-module Android project last year expecting a minor convenience. What I actually got was a measurable drop in the time between "test went red" and "I know the cause," because most of that time was previously spent adding print statements to reconstruct what the assertion already knew.

## The problem with bare assertions

Consider a test that checks a computed cart total:

```kotlin
@Test
fun applies_discount() {
    val cart = Cart(items = listOf(Item("A", 1000), Item("B", 500)))
    assert(cart.totalAfterDiscount(percent = 10) == 1350)
}
```

If `totalAfterDiscount` has an off-by-one in the rounding, the stock JVM message is `java.lang.AssertionError`. You now have to open the debugger or scatter `println` calls to learn that the actual value was `1349`. Multiply that by every flaky assertion in a large suite and it's real, recurring friction — the kind that quietly pushes people toward writing fewer assertions per test.

## What power-assert prints instead

With the plugin enabled, the same failure becomes something like:

```text
Assertion failed
assert(cart.totalAfterDiscount(percent = 10) == 1350)
       |    |                                  |
       |    1349                               false
       Cart(items=[Item(A, 1000), Item(B, 500)])
```

Every sub-expression is annotated with its evaluated value, aligned under the token that produced it. You can see `1349` versus the expected `1350` and the boolean result, all without touching a debugger. That diagram is the whole feature, and it's why once a team uses it they don't go back.

## Turning it on

Power-assert ships as a first-party Gradle plugin. You apply it and list the functions you want transformed:

```kotlin
plugins {
    kotlin("multiplatform") version "2.1.0"
    kotlin("plugin.power-assert") version "2.1.0"
}

powerAssert {
    functions = listOf(
        "kotlin.assert",
        "kotlin.test.assertTrue",
        "kotlin.test.assertEquals",
        "kotlin.require",
    )
}
```

The `functions` list is the important knob. Only the functions you name get rewritten, which is why the plugin is safe to leave on — it doesn't touch anything you didn't opt into. I scope it to test source sets in practice, though it works anywhere. Note that it's a compiler plugin, so it composes cleanly with the rest of your build once you're on a modern toolchain; if you've done the work of [migrating to the Kotlin K2 compiler](https://blog.michaelsam94.com/kotlin-k2-compiler-migration/), power-assert is one of the plugins that benefits from the more consistent frontend.

## Enhancing your own assertion helpers

The part teams miss: you're not limited to the standard library. If your codebase has assertion helpers — and most mature test suites do — you can register them. Say you wrote:

```kotlin
fun assertWithinTolerance(actual: Double, expected: Double, tolerance: Double = 0.01) {
    assert(kotlin.math.abs(actual - expected) < tolerance)
}
```

Add `"com.example.testutil.assertWithinTolerance"` to the `functions` list and its failures now diagram the subtraction and the comparison. This is genuinely useful for domain-specific checks — geolocation distances, currency rounding, timestamp windows — where the interesting value is the *difference*, not the operands. Being able to see the computed delta in the failure message is exactly the diagnostic you'd otherwise reconstruct by hand.

## Where it fits, and where it doesn't

Power-assert is a diagnostics multiplier, not a replacement for good assertion libraries. Here's my honest breakdown:

- **Great for**: boolean-condition assertions where the failure cause is *inside* the expression — comparisons, arithmetic, string equality, membership checks.
- **Less useful for**: assertions that already have rich failure output. A good `assertThat(list).containsExactly(...)` from a fluent library already tells you what diverged; wrapping that in power-assert adds little.
- **Neutral for**: `assertEquals(expected, actual)` on simple values — the standard message is already fine, though the diagram doesn't hurt.

So I don't rip out fluent assertion libraries when I add power-assert. I use it to upgrade the *plain* assertions that people reach for when a fluent matcher would be overkill — the `assert(x > 0 && y in range)` one-liners that are quick to write but historically opaque to debug. That combination, quick to write *and* readable when they fail, is what makes people write more of them.

## A note on coroutines and async tests

Assertion clarity matters most where reproduction is hardest, and async tests are the poster child. When a `Flow` emits the wrong value under a specific dispatcher timing, you want the failure to tell you the actual emission, not send you into a debugging session against a race. Power-assert pairs well with the structured approach to [coroutine testing with Turbine](https://blog.michaelsam94.com/kotlin-coroutines-testing-turbine/): Turbine gives you deterministic control over emissions, and power-assert makes the assertion on each emission self-explanatory when it fails. Together they cut the "why did this async test fail on CI but not locally" investigations way down.

## Is it worth the setup?

The setup is one plugin line and a function list — call it fifteen minutes for a project. The return is that every plain assertion in your suite gets self-documenting failures for free, forever. There's no runtime cost in release builds, no new API for engineers to learn, and no behavior change beyond richer error text. That's about as close to a free lunch as build tooling gets.

The broader point, and the reason I bring it up in code reviews now: assertions people can read when they fail are assertions people trust. Trusted assertions get written more often and deleted less often, and a suite full of them is what actually keeps regressions out. Power-assert is a small plugin that nudges the whole team's testing habits in the right direction, which is why I reach for it early rather than as a nice-to-have. It slots in alongside your existing practice for [testing Compose UIs](https://blog.michaelsam94.com/testing-compose-uis-v2/) without asking you to change how you write tests at all.

## Resources

- [Kotlin power-assert compiler plugin docs](https://kotlinlang.org/docs/power-assert.html)
- [kotlin.test documentation](https://kotlinlang.org/api/latest/kotlin.test/)
- [Kotlin 2.0 release notes](https://kotlinlang.org/docs/whatsnew20.html)
- [Turbine — Flow testing library](https://github.com/cashapp/turbine)
- [The Kotlin Blog](https://blog.jetbrains.com/kotlin/)
