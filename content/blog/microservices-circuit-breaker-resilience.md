---
title: "Circuit Breakers and Resilience"
slug: "microservices-circuit-breaker-resilience"
description: "Protect microservices from cascading failures with circuit breakers, bulkheads, retries, and timeouts — patterns that keep one slow dependency from taking down everything."
datePublished: "2025-06-05"
dateModified: "2026-07-17"
tags:
keywords: "circuit breaker pattern, microservices resilience, bulkhead pattern, retry with backoff, cascading failure prevention, resilience4j circuit breaker"
faq:
  - q: "When should a circuit breaker open?"
    a: "Open the circuit when the failure rate exceeds a threshold within a sliding window — typically 50% failures over 10 requests in a 60-second window. Also open on consecutive timeouts. The circuit stays open for a cooldown period (30–60 seconds) before allowing a test request through."
  - q: "What happens when the circuit is open?"
    a: "Calls fail fast without reaching the downstream service. Return a fallback response (cached data, default value, or error message) immediately. This prevents thread/connection exhaustion on the caller and gives the failing service time to recover."
  - q: "How do circuit breakers interact with retries?"
    a: "Retry before the circuit breaker, not after. Retries handle transient failures (network blip). The circuit breaker handles sustained failures (service down). Retrying against an open circuit wastes resources — check circuit state before retrying."
---
Your order service calls the payment service. Payment is slow — database lock contention, maybe a deployment gone wrong. Order service threads block waiting. Thread pool exhausts. Order service stops accepting requests. Checkout is down. Catalog service calls order service for stock checks — also hangs. The entire platform freezes because one dependency got slow.

Cascading failures are the dominant failure mode in microservice architectures. Circuit breakers, bulkheads, timeouts, and retries are the four patterns that prevent one sick service from killing its callers.

## Circuit breaker states

```
Closed (normal) → failures exceed threshold → Open (fail fast)
Open → cooldown expires → Half-Open (test request)
Half-Open → test succeeds → Closed
Half-Open → test fails → Open
```

```python
from enum import Enum
import time

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=30, half_open_max=1):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.half_open_calls = 0

    def call(self, func, fallback=None):
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
            else:
                return fallback() if fallback else raise CircuitOpenError()

        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls >= self.half_open_max:
                return fallback() if fallback else raise CircuitOpenError()
            self.half_open_calls += 1

        try:
            result = func()
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            if fallback and self.state == CircuitState.OPEN:
                return fallback()
            raise

    def _on_success(self):
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
```

## Using resilience4j (Java) or pybreaker (Python)

Production libraries handle edge cases your hand-rolled breaker will miss:

```python
import pybreaker

payment_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=30,
    exclude=[ValidationError],  # don't count client errors as failures
)

@payment_breaker
def charge_payment(order_id: str, amount: float):
    return payment_client.charge(order_id, amount)

def checkout(order):
    try:
        result = charge_payment(order.id, order.total)
    except pybreaker.CircuitBreakerError:
        return {"status": "payment_unavailable", "message": "Try again in a few minutes"}
    return {"status": "confirmed", "payment_id": result.id}
```

## Timeouts: the simplest resilience pattern

Every outbound call needs a timeout. Without one, a hung dependency blocks a thread forever:

```python
import httpx

async def call_with_timeout(url: str, timeout: float = 2.0):
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url)
        return response.json()
```

Set timeouts shorter than the caller's own timeout. If your API has a 5-second SLA and you call three services sequentially, each gets ~1.5 seconds max. Prefer parallel calls to multiply available time.

## Retries with exponential backoff

Retry transient failures, not permanent ones:

```python
import tenacity

@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=tenacity.retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    before_sleep=tenacity.before_sleep_log(logger, logging.WARNING),
)
async def fetch_inventory(product_id: str):
    return await call_with_timeout(f"http://inventory/stock/{product_id}")
```

Do not retry:
- 4xx client errors (bad request, not found)
- Validation failures
- When the circuit breaker is open

## Bulkhead pattern: isolate failure domains

Bulkheads limit concurrent calls to a specific dependency, preventing one slow service from consuming all threads:

```python
import asyncio

class Bulkhead:
    def __init__(self, max_concurrent: int):
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def execute(self, coro):
        async with self.semaphore:
            return await coro

payment_bulkhead = Bulkhead(max_concurrent=10)
inventory_bulkhead = Bulkhead(max_concurrent=50)

async def checkout(order):
    payment = await payment_bulkhead.execute(charge_payment(order))
    stock = await inventory_bulkhead.execute(check_inventory(order))
    return combine(payment, stock)
```

If payment is slow, only 10 threads block — the other 90 remain available for inventory, catalog, and other operations.

## Fallback strategies

When the circuit is open, serve degraded responses:

| Dependency | Fallback |
|-----------|----------|
| Product recommendations | Return cached popular items |
| User profile | Return name from JWT, skip avatar |
| Payment processing | Queue for later processing |
| Real-time inventory | Return "availability unknown" |
| Search | Return cached recent results |

```python
def get_recommendations(user_id: str) -> list:
    try:
        return recommendation_breaker.call(
            lambda: recommendation_service.get(user_id),
            fallback=lambda: cache.get(f"recs:fallback") or POPULAR_ITEMS,
        )
    except CircuitOpenError:
        return POPULAR_ITEMS
```

Cache fallbacks during normal operation so they are fresh when needed.

## Composing the patterns

The resilience stack for each outbound call:

```
Request → Timeout → Retry (transient only) → Circuit Breaker → Bulkhead → Service
                ↓ on failure at any layer
            Fallback response
```

Order matters. Timeout is innermost (per-attempt). Retry wraps timeout. Circuit breaker wraps retry. Bulkhead limits total concurrency.

## Common production mistakes

Teams get circuit breaker resilience wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of circuit breaker resilience fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When circuit breaker resilience misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Half-open state tuning

The half-open probe count and success threshold determine how aggressively you recover after an outage. Too eager and you flap; too conservative and you starve callers while the dependency is healthy. Start with one probe per second and three consecutive successes to close — then tune from incident data.

## Resources

- [Release It! by Michael Nygard (circuit breaker origin)](https://pragprog.com/titles/mnee2/release-it-second-edition/)
- [resilience4j documentation](https://resilience4j.readme.io/docs/circuitbreaker)
- [pybreaker Python library](https://github.com/dynatrace/oss-python-pybreaker)
- [Microsoft: Circuit Breaker pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker)
- [Netflix Hystrix (historical reference)](https://github.com/Netflix/Hystrix/wiki)
