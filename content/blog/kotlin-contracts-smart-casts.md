---
title: "Kotlin Contracts and Smarter Smart Casts"
slug: "kotlin-contracts-smart-casts"
description: "Use Kotlin contracts to improve smart casts: custom null checks, boolean implications, and experimental API boundaries for library authors."
datePublished: "2025-11-25"
dateModified: "2025-11-25"
tags: ["Android", "Kotlin"]
keywords: "Kotlin contracts, smart cast, ContractBuilder, returns, implies, null check, compiler"
faq:
  - q: "What problem do Kotlin contracts solve?"
    a: "The compiler cannot always infer that a nullable value was checked by a custom function. Contracts tell the compiler what a function guarantees—returns true means the argument is non-null, or calling this function implies a condition—enabling smart casts after custom guards."
  - q: "Are contracts stable public API?"
    a: "The contracts DSL for library authors is experimental and requires @OptIn(ExperimentalContracts::class). Standard library functions like require, check, and assert use contracts internally—you benefit without opting in. Writing your own contracts is for framework and utility authors."
  - q: "Can contracts change runtime behavior?"
    a: "No. Contracts are compile-time only annotations processed by the Kotlin compiler. They do not emit bytecode checks. Incorrect contracts can unsoundly smart-cast and cause ClassCastException at runtime if you lie to the compiler."
---

You write a utility `fun String?.isNullOrBlank(): Boolean` and expect the compiler to smart-cast after `if (!name.isNullOrBlank()) { name.uppercase() }`. It does not—because without a contract, the compiler treats your function as a black box that might mutate `name` through reflection or globals. Contracts are the formal promise that lets the compiler trust your guard functions.

**Kotlin contracts** describe function behavior for the compiler: what is true after a function returns, what parameters are consumed, whether a function calls lambdas exactly once. Most developers use contracts indirectly via `requireNotNull` and `check`. Library authors write them explicitly.

## Built-in contracts you already use

```kotlin
fun process(input: String?) {
    requireNotNull(input) { "input required" }
    // input is String here — requireNotNull contract
    println(input.length)
}

fun validate(flag: Boolean) {
    check(flag) { "flag must be true" }
    // compiler knows flag is true
}
```

`requireNotNull` declares `returns() implies (value != null)`. That is why smart cast works.

## Writing a custom contract

```kotlin
@OptIn(ExperimentalContracts::class)
fun CharSequence?.isNotNullOrEmpty(): Boolean {
    contract {
        returns(true) implies (this@isNotNullOrEmpty != null)
    }
    return this != null && this.isNotEmpty()
}

fun greet(name: CharSequence?) {
    if (name.isNotNullOrEmpty()) {
        println("Hello, ${name.length}") // smart cast: CharSequence
    }
}
```

The receiver must be referenced exactly as in the function signature inside `implies`.

## returns(value) and boolean guards

```kotlin
@OptIn(ExperimentalContracts::class)
fun String?.isValidEmail(): Boolean {
    contract {
        returns(true) implies (this@isValidEmail != null)
    }
    if (this == null) return false
    return contains('@') && length > 3
}
```

Pair with `returns(false)` when both outcomes carry information:

```kotlin
@OptIn(ExperimentalContracts::class)
fun holdsLock(): Boolean {
    contract {
        returns(true) implies (lockHeld)
        returns(false) implies (!lockHeld)
    }
    return lockHeld
}
```

Only express facts the function actually enforces.

## callsInPlace for lambdas

Useful for scope functions and inline guards:

```kotlin
@OptIn(ExperimentalContracts::class)
inline fun <T> T.alsoIf(condition: Boolean, block: (T) -> Unit): T {
    contract {
        callsInPlace(block, InvocationKind.AT_MOST_ONCE)
    }
    if (condition) block(this)
    return this
}
```

`callsInPlace` with `EXACTLY_ONCE` enables initialization analysis:

```kotlin
contract {
    callsInPlace(block, InvocationKind.EXACTLY_ONCE)
}
// After block(), compiler knows lateinit was assigned
```

## Experimental boundaries

Mark public APIs carefully:

```kotlin
@OptIn(ExperimentalContracts::class)
@SinceKotlin("1.3")
fun myUtil(): Boolean { /* contract */ }
```

Contracts in public libraries can break binary compatibility if signatures change—keep contract functions stable.

Do not over-contract. Every `implies` claim is a liability if implementation drifts.

## What contracts cannot do

- Track relationships between two unrelated parameters (`implies arg1 == arg2`)
- Model arbitrary class invariants across method calls
- Replace proper type design—prefer sealed types and value classes for domain rules

If smart cast fails, local `val` copies often suffice:

```kotlin
val local = name
if (local != null) use(local)
```

Contracts reduce boilerplate at scale in utility modules.

## IDE vs compiler

Contracts affect compilation, not IDE inference in all versions—Android Studio may still warn where compiler accepts smart cast. Trust compile task over yellow highlights when they disagree.


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

- [Kotlin contracts documentation](https://kotlinlang.org/docs/contracts.html) — official syntax and experimental status
- [KEEP-248: Kotlin contracts proposal](https://github.com/Kotlin/KEEP/blob/master/proposals/contracts-for-kotlin.md) — design rationale
- [Standard library contract examples](https://github.com/JetBrains/kotlin/tree/master/libraries/stdlib/src/kotlin/util) — require, check, assert implementations
- [Kotlin compiler smart cast rules](https://kotlinlang.org/docs/typecasts.html#smart-casts) — when casts work without contracts
