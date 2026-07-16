---
title: "Error Handling with Kotlin's Result Type"
slug: "kotlin-result-type-error-handling"
description: "Use Kotlin Result for error handling: fold, mapCatching, getOrThrow vs exceptions, coroutine interop, and when Result beats Either for app code."
datePublished: "2025-12-31"
dateModified: "2025-12-31"
tags: ["Android", "Kotlin"]
keywords: "Kotlin Result, mapCatching, fold, runCatching, error handling, getOrElse, Result coroutines"
faq:
  - q: "Should Result use Throwable for all errors?"
    a: "Result is typed as Result<T> and failures wrap Throwable. Domain errors like InsufficientFunds must become custom exception subclasses or you use sealed wrappers. For rich typed errors without exceptions, Either or sealed Result wrappers fit better."
  - q: "What is the difference between runCatching and try/catch?"
    a: "runCatching returns Result<T>, composing with map, flatMap, and fold without explicit try blocks. It captures any Throwable including Errors—use getOrElse or fold to handle. Prefer it at boundaries where exceptions originate."
  - q: "Can I use Result in suspend functions?"
    a: "Yes. wrap with runCatching inside suspend blocks or use coroutine-specific helpers. Do not block inside Result chains. For parallel results, combine individual Result values explicitly—stdlib has no Result.zip yet, so fold manually or use Arrow."
---

`runCatching { api.charge() }` replaced forty lines of nested try/catch in our payment module. Engineers argued about `Result` versus sealed classes for weeks; in practice, **Result** won for IO boundaries because every SDK already throws, and Result meets exceptions where they live without inventing parallel error hierarchies.

Kotlin's **Result** type (stdlib since 1.5) models success or failure as a value. It shines at system boundaries—network, filesystem, platform APIs—and chains cleanly without throwing until you choose to.

## Creating and transforming

```kotlin
fun loadConfig(path: Path): Result<AppConfig> = runCatching {
    json.decodeFromString<AppConfig>(path.readText())
}

fun validatedConfig(path: Path): Result<AppConfig> =
    loadConfig(path).mapCatching { config ->
        require(config.apiUrl.isNotBlank()) { "apiUrl blank" }
        config
    }
```

`map` transforms success; `mapCatching` catches exceptions in transform and wraps as failure.

Recover without throwing:

```kotlin
val config = validatedConfig(path).getOrElse { error ->
    logger.warn("Using defaults", error)
    AppConfig.DEFAULT
}
```

## fold at UI boundaries

```kotlin
viewModelScope.launch {
    _state.value = Loading
    repository.fetchUser(id).fold(
        onSuccess = { user -> _state.value = Success(user) },
        onFailure = { e -> _state.value = Error(e.userMessage()) }
    )
}

private fun Throwable.userMessage(): String = when (this) {
    is HttpException -> "Server error"
    is IOException -> "Check connection"
    else -> "Something went wrong"
}
```

## flatMap chaining

```kotlin
fun processOrder(id: String): Result<Receipt> =
    fetchOrder(id).flatMap { order ->
        validate(order).flatMap { valid ->
            charge(valid).map { payment ->
                Receipt(order.id, payment.transactionId)
            }
        }
    }

fun <T, R> Result<T>.flatMap(transform: (T) -> Result<R>): Result<R> =
    fold(
        onSuccess = transform,
        onFailure = { Result.failure(it) }
    )
```

Stdlib lacks `flatMap` on Result in older versions—extension or use Kotlin 1.9+ additions; verify your Kotlin version.

## Domain errors as exceptions (pragmatic)

When staying with Result:

```kotlin
sealed class DomainException(message: String) : Exception(message) {
    class OutOfStock(val sku: String) : DomainException("SKU $sku unavailable")
    class PaymentDeclined : DomainException("Card declined")
}

fun checkout(cart: Cart): Result<Order> = runCatching {
    if (!inventory.available(cart)) throw DomainException.OutOfStock(cart.firstSku)
    gateway.charge(cart.total) ?: throw DomainException.PaymentDeclined()
    Order.create(cart)
}
```

Catch specific types in `fold` via `when (e)`.

## Result vs nullable vs Either

| Approach | Best for |
|----------|----------|
| Nullable | Optional missing data, not errors |
| Result | Throwable-based failures, IO boundaries |
| Either | Typed business errors without exceptions |
| Sealed outcome | UI-specific state machines |

Do not mix `Result` and thrown exceptions in the same layer—convert once.

## Testing

```kotlin
@Test
fun `declined payment fails result`() {
    val result = checkout(cartWithDeclinedCard)
    assertTrue(result.isFailure)
    assertIs<DomainException.PaymentDeclined>(result.exceptionOrNull())
}
```

## Pitfalls

- **`Result` in public API return types** — Kotlin convention discourages exposing Result in public signatures per stdlib docs; some teams ignore for internal modules
- **Swallowing stack traces** — log in `onFailure`
- **runCatching catching Errors** — rare but possible; rethrow if needed

## recover and mapError

```kotlin
fun fetch(): Result<Data> = runCatching { api.load() }
    .recover { cache.read() ?: throw it }
```

`recover` transforms failure to success when fallback exists—document when partial success is acceptable vs when failure must propagate.


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


Don't wrap Result in Result — nested Result types confuse callers; map errors to sealed classes at API boundaries.

## Resources

- [Kotlin Result API reference](https://kotlinlang.org/api/latest/jvm/stdlib/kotlin/-result/) — stdlib functions
- [Effective Kotlin Item on Result](https://kt.academy/article/fk-result) — community best practices
- [Kotlin exception handling docs](https://kotlinlang.org/docs/exceptions.html) — when exceptions remain appropriate
- [Arrow Either comparison](https://arrow.apache.org/learn/typed-errors/) — typed error alternative
