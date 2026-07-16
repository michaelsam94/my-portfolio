---
title: "Lock-Free Code with kotlinx.atomicfu"
slug: "kotlin-atomicfu-lock-free"
description: "Write lock-free Kotlin with kotlinx.atomicfu: atomic primitives, JVM field optimization, reentrant locks as escape hatch, and when atomics beat synchronized blocks."
datePublished: "2025-11-21"
dateModified: "2025-11-21"
tags: ["Android", "Kotlin"]
keywords: "kotlinx.atomicfu, lock-free, atomic operations, concurrent Kotlin, reentrant lock, performance"
faq:
  - q: "What does kotlinx.atomicfu optimize on the JVM?"
    a: "AtomicFu transforms @Volatile and atomic operations at compile time into plain fields with intrinsic operations where safe, avoiding boxed AtomicInteger overhead in hot paths. On Native and JS it maps to platform atomics. The API stays consistent across Kotlin Multiplatform targets."
  - q: "When should I use atomics instead of Mutex or synchronized?"
    a: "Use atomics for simple counters, flags, and compare-and-swap updates on single fields. Reach for Mutex when you protect multi-field invariants or hold locks across suspend points—atomics cannot guard compound state transitions alone."
  - q: "Is lock-free always faster than locks?"
    a: "No. Under low contention, atomics win. Under high contention with complex critical sections, locks can be faster and easier to reason about. Measure. Incorrect lock-free algorithms cause subtle bugs that outweigh microsecond savings."
---

We had a metrics counter incremented from twelve coroutines on Dispatchers.Default. `synchronized` worked but showed up in profiles— not because locking was slow, but because every increment serialized. Switching to a single `atomic` int removed the monitor bottleneck and cut p99 batch flush time by 30%. That is the narrow window where `kotlinx.atomicfu` earns its place: simple shared mutable state updated concurrently without wrapping everything in `synchronized`.

**kotlinx.atomicfu** provides atomic primitives for Kotlin Multiplatform with compile-time JVM optimizations. It is not a general concurrency framework—it is a scalpel for counters, reference swaps, and lock-free structures when you know your invariants fit in one CAS loop.

## Setup and basic usage

```kotlin
// build.gradle.kts
plugins {
    id("org.jetbrains.kotlin.plugin.atomicfu") version "0.25.0"
}

dependencies {
    implementation("org.jetbrains.kotlinx:atomicfu:0.25.0")
}
```

```kotlin
import kotlinx.atomicfu.atomic

class RequestMetrics {
    private val active = atomic(0)
    private val completed = atomic(0L)

    fun onStart() { active.incrementAndGet() }
    fun onComplete() {
        active.decrementAndGet()
        completed.incrementAndGet()
    }

    fun snapshot(): MetricsSnapshot =
        MetricsSnapshot(active.value, completed.value)
}
```

`value`, `incrementAndGet`, `compareAndSet`, and `getAndUpdate` cover most cases.

## Compare-and-swap patterns

Update complex values immutably:

```kotlin
private val state = atomic<ConnectionState>(ConnectionState.Idle)

fun connect() {
    state.update { current ->
        if (current is ConnectionState.Idle) ConnectionState.Connecting
        else current
    }
}

fun markConnected() {
    state.compareAndSet(ConnectionState.Connecting, ConnectionState.Connected)
}
```

For multi-field invariants, CAS on a single immutable data class snapshot works; CAS on two separate atomics does not—another thread can observe torn state.

## Atomic arrays and lazy initialization

```kotlin
private val slots = atomicArrayOfNulls<Worker>(16)

fun assign(index: Int, worker: Worker): Boolean =
    slots[index].compareAndSet(null, worker)
```

One-shot lazy init without double-checked locking bugs:

```kotlin
private val cache = atomic<ExpensiveResource?>(null)

fun resource(): ExpensiveResource =
    cache.value ?: cache.updateAndGet { existing ->
        existing ?: buildResource()
    }!!
```

Still race-safe—two threads might build briefly; dedupe with compareAndSet if construction is costly.

## reentrantLock as escape hatch

AtomicFu includes `reentrantLock` for KMP-compatible locking when atomics are insufficient:

```kotlin
import kotlinx.atomicfu.locks.reentrantLock
import kotlinx.atomicfu.locks.withLock

private val lock = reentrantLock()
private val buffer = mutableListOf<Event>()

fun append(event: Event) = lock.withLock {
    buffer.add(event)
}
```

Prefer `Mutex` in coroutine code that suspends inside critical sections—locks block threads; `Mutex` cooperates with cancellation.

## JVM transformation details

The AtomicFu compiler plugin replaces `@Volatile` atomics with optimized field access in production bytecode. Debug mode can disable transformation for easier stepping in debugger.

Do not mix AtomicFu atomics with direct field reads outside the API—always go through `.value`.

## Pitfalls

- **ABA problems** — use versioned state or `AtomicRef` carefully in lock-free data structures
- **False sharing** — rare on JVM for typical app code; matters in extreme throughput servers
- **Long counters on 32-bit** — use `atomicLong` explicitly
- **Testing** — stress with many threads; lock-free bugs reproduce intermittently

Profile before rewriting all locks. A `Mutex`-guarded cache with low contention is fine.

## kotlinx.coroutines sync vs atomicfu

For coroutine-safe counters updated from many dispatchers, `atomic` is correct. For protecting suspend functions, use `Mutex`—never hold `synchronized` or atomic spin across suspension points.


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

- [kotlinx.atomicfu GitHub](https://github.com/Kotlin/kotlinx.atomicfu) — plugin config and API docs
- [AtomicFu Kotlin API reference](https://kotlinlang.org/api/kotlinx.atomicfu/) — function listing per platform
- [Java VarHandle vs atomics](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/lang/invoke/VarHandle.html) — JVM low-level comparison
- [Kotlin coroutines Mutex guide](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines.sync/-mutex/) — when to prefer Mutex over atomics
