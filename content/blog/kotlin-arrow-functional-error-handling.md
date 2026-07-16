---
title: "Functional Error Handling with Arrow"
slug: "kotlin-arrow-functional-error-handling"
description: "Handle errors functionally in Kotlin with Arrow: Either, Raise, typed errors, and patterns that replace exceptions in domain logic without ceremony."
datePublished: "2025-11-17"
dateModified: "2025-11-17"
tags: ["Android", "Kotlin"]
keywords: "Arrow Kotlin, Either, Raise, functional error handling, typed errors, domain errors, bind"
faq:
  - q: "When should I use Arrow Either instead of Kotlin Result?"
    a: "Either carries a typed error on the left channel—PaymentDeclined, NetworkTimeout—while Result uses Throwable. Either composes with map, flatMap, and zip without forcing everything into exception hierarchy. Result fits simple success/failure; Either fits domain models where errors are expected business outcomes."
  - q: "What is Arrow Raise and how does it differ from Either?"
    a: "Raise is Arrow's typed short-circuit syntax—like try/catch but for typed errors. You call raise(Error) to exit a block early, or bind() on Either to unwrap successes. Under the hood it compiles to efficient control flow without nested flatMap chains."
  - q: "Does Arrow add significant binary size to Android apps?"
    a: "Arrow modules are granular—depend on arrow-core and arrow-fx-coroutines rather than the entire ecosystem. R8 shrinks unused code. Typical Android usage adds modest size compared to networking libraries. Profile release builds if size is critical."
---

Exceptions for control flow are convenient until they aren't. A `catch (e: Exception)` around a checkout call conflates "card declined" with "JSON parse failed" with "thread interrupted." The UI shows a generic error; logs bury the signal. Arrow gives you **typed errors as values**—`Either<PaymentError, Receipt>`—and composes them without try/catch spaghetti.

Arrow is a functional library for Kotlin. For error handling, the important pieces are **Either**, **Raise**, and **ensure**—tools to model failure as data and short-circuit cleanly across suspend boundaries.

## Either: errors as data

```kotlin
sealed interface PaymentError {
    data object InsufficientFunds : PaymentError
    data class Declined(val reason: String) : PaymentError
    data class GatewayFailure(val code: Int) : PaymentError
}

fun charge(amount: Money, card: Card): Either<PaymentError, Receipt> =
    either {
        if (amount > card.availableBalance) {
            raise(PaymentError.InsufficientFunds)
        }
        gateway.charge(amount, card)
            .mapLeft { PaymentError.GatewayFailure(it.code) }
            .bind()
    }
```

`either { }` is Raise syntax—`raise` exits with Left; `bind()` unwraps Right or short-circuits on Left.

At the edge, fold to UI:

```kotlin
charge(total, card).fold(
    ifLeft = { error ->
        when (error) {
            PaymentError.InsufficientFunds -> showInsufficientFunds()
            is PaymentError.Declined -> showDeclined(error.reason)
            is PaymentError.GatewayFailure -> showRetry()
        }
    },
    ifRight = { receipt -> navigateToConfirmation(receipt) }
)
```

## Composing operations without nested flatMap

Sequential steps read top-to-bottom:

```kotlin
suspend fun placeOrder(cart: Cart): Either<OrderError, Order> = either {
    val validated = validateCart(cart).bind()
    val priced = pricingService.price(validated).bind()
    val payment = processPayment(priced).bind()
    fulfillment.submit(priced, payment).bind()
}
```

Each `.bind()` propagates errors automatically. Compare to nested `flatMap` chains that obscure the happy path.

Parallel independent calls use `zip`:

```kotlin
either {
    val inventory = async { inventoryCheck(itemId).bind() }
    val shipping = async { shippingQuote(address).bind() }
    Pair(inventory.await(), shipping.await())
}
```

## Raise vs exceptions at boundaries

Keep exceptions at system boundaries—HTTP clients, JDBC, Android APIs. Convert once:

```kotlin
suspend fun fetchRates(): Either<RatesError, Rates> =
    either {
        withContext(Dispatchers.IO) {
            catch({ api.getRates() }) { RatesError.Network(it) }.bind()
        }
    }
```

Do not let exceptions leak through domain layers. Do not throw `PaymentError`—it's not an exception, it's a return value.

## Interop with Result and nullable

Convert at integration points:

```kotlin
fun Either<PaymentError, Receipt>.toResult(): Result<Receipt> =
    fold(
        ifLeft = { Result.failure(it.toException()) },
        ifRight = { Result.success(it) }
    )

fun <L, R> Either<L, R>.getOrNull(): R? = getOrNull()
```

Prefer one style per layer: Arrow in domain, Result at SDK boundaries if partners expect it.

## Testing typed errors

Assertions become explicit:

```kotlin
@Test
fun `declines when insufficient funds`() = runTest {
    val result = charge(Money(100), cardWithBalance(50))
    result shouldBeLeft PaymentError.InsufficientFunds
}
```

Arrow's test matchers (`shouldBeLeft`, `shouldBeRight`) beat `assertTrue(result.isFailure)`.

## When not to use Arrow

- Throwaway scripts and prototypes
- Teams unfamiliar with FP who won't maintain Either chains
- Hot paths where profiling shows allocation overhead matters (rare)

For Android ViewModels and use cases handling predictable business failures, typed errors improve readability and crash-free metrics.

## Stack traces on typed errors

Either left channel without exception loses stack trace—log at boundary when mapping domain error to HTTP 400. For unexpected infrastructure failures, still use Throwable inside Result or Either at IO edge.


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

- [Arrow documentation — Either](https://arrow.apache.org/apidocs/arrow-core/arrow.core/either/index.html) — core API reference
- [Arrow Raise guide](https://arrow.apache.org/learn/typed-errors/) — typed error patterns and migration from exceptions
- [Arrow GitHub repository](https://github.com/apache/arrow-kotlin) — module structure and release notes
- [Domain modeling with typed errors (KotlinConf)](https://kotlinlang.org/docs/exceptions.html) — official Kotlin exception philosophy for comparison
