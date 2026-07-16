---
title: "Retries with Jitter and Backoff"
slug: "backend-retry-jitter-exponential-backoff"
description: "Naive retries amplify outages. Exponential backoff with jitter spreads retry storms across time. Implement retry policies for HTTP clients, message consumers, and database connections with concrete formulas."
datePublished: "2024-11-09"
dateModified: "2024-11-09"
tags: ["Backend", "Architecture", "Reliability"]
keywords: "exponential backoff, retry jitter, retry storm, backoff formula, full jitter, equal jitter, retry policy HTTP"
faq:
  - q: "Why add jitter to exponential backoff?"
    a: "Without jitter, all clients retry at the same intervals — 1s, 2s, 4s, 8s — creating synchronized traffic spikes that keep the failing service down. Jitter randomizes delay within a range, spreading retries across time so recovery isn't overwhelmed by a coordinated retry wave."
  - q: "What is full jitter vs equal jitter?"
    a: "Full jitter: delay = random(0, min(cap, base * 2^attempt)). Equal jitter: delay = (base * 2^attempt)/2 + random(0, (base * 2^attempt)/2). Full jitter spreads more aggressively. AWS recommends full jitter for most cases — it minimizes overlap between retrying clients."
  - q: "Which HTTP status codes should trigger retries?"
    a: "Retry on 429 (with Retry-After header), 502, 503, 504, and connection timeouts. Do not retry 400, 401, 403, 404, or 422 — the request itself is wrong and retrying wastes resources. 409 may or may not be retryable depending on semantics."
---

A dependency goes down and every client retries every second. The dependency comes back, gets immediately hammered by synchronized retries from ten thousand instances, goes down again, and the cycle repeats for an hour. This is a retry storm — caused not by the original failure but by well-intentioned retry logic with zero jitter. Exponential backoff spaces retries out; jitter randomizes the spacing so clients don't move in lockstep.

## Backoff formula

Base delay doubles each attempt, capped at a maximum:

```
delay = min(cap, base * 2^attempt)
```

With **full jitter** (AWS recommended):

```
delay = random(0, min(cap, base * 2^attempt))
```

| Attempt | Base (100ms) | No jitter | Full jitter range |
|---------|-------------|-----------|-------------------|
| 0 | 100ms | 100ms | 0–100ms |
| 1 | 200ms | 200ms | 0–200ms |
| 2 | 400ms | 400ms | 0–400ms |
| 3 | 800ms | 800ms | 0–800ms |
| 5 | 3200ms | 3200ms | 0–3200ms |

## TypeScript implementation

```typescript
interface RetryOptions {
  maxAttempts: number;
  baseDelayMs: number;
  maxDelayMs: number;
  retryable?: (error: unknown) => boolean;
}

function fullJitterDelay(attempt: number, base: number, cap: number): number {
  const ceiling = Math.min(cap, base * 2 ** attempt);
  return Math.floor(Math.random() * ceiling);
}

async function withRetry<T>(
  fn: () => Promise<T>,
  opts: RetryOptions
): Promise<T> {
  const { maxAttempts, baseDelayMs, maxDelayMs, retryable = () => true } = opts;

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (error) {
      if (attempt === maxAttempts - 1 || !retryable(error)) throw error;
      const delay = fullJitterDelay(attempt, baseDelayMs, maxDelayMs);
      await sleep(delay);
    }
  }
  throw new Error('unreachable');
}
```

Usage:

```typescript
const response = await withRetry(
  () => fetch('https://api.partner.com/inventory'),
  {
    maxAttempts: 5,
    baseDelayMs: 200,
    maxDelayMs: 30_000,
    retryable: (err) => err instanceof HttpError && [502, 503, 504].includes(err.status),
  }
);
```

## Respect Retry-After

On 429 responses, honor the server's hint:

```typescript
async function fetchWithRetry(url: string): Promise<Response> {
  for (let attempt = 0; attempt < 5; attempt++) {
    const resp = await fetch(url);
    if (resp.status !== 429) return resp;

    const retryAfter = resp.headers.get('Retry-After');
    const delayMs = retryAfter
      ? parseInt(retryAfter, 10) * 1000
      : fullJitterDelay(attempt, 1000, 60_000);

    await sleep(delayMs);
  }
  throw new Error('Rate limited after max retries');
}
```

## Circuit breaker pairing

Retries without a circuit breaker retry into a dead service forever (bounded, but still wasteful). Open the circuit after N consecutive failures; fail fast until a probe succeeds:

```
Closed (normal) → failures exceed threshold → Open (fail fast)
Open → timeout → Half-open (probe) → success → Closed
                                    → failure → Open
```

Libraries: `opossum` (Node), `resilience4j` (Java), `gobreaker` (Go).

## Message consumer retries

Kafka/SQS consumers should retry with backoff before sending to DLQ:

```typescript
async function processMessage(msg: Message): Promise<void> {
  const attempt = msg.headers['x-retry-count'] ?? 0;
  try {
    await handleEvent(msg.body);
  } catch (error) {
    if (attempt >= 5) {
      await deadLetterQueue.send(msg);
      return;
    }
    const delay = fullJitterDelay(attempt, 1000, 300_000);
    await retryQueue.send(msg, { delaySeconds: delay / 1000, headers: { 'x-retry-count': attempt + 1 } });
  }
}
```

## What not to retry

- Non-idempotent POST without idempotency key
- Validation errors (4xx except 429)
- Authentication failures (401/403) — rotate credentials first
- Errors that succeeded partially without compensation logic

My default policy: 3–5 attempts, 200ms base, 30s cap, full jitter, circuit breaker at 50% failure rate over 30 seconds.

## Decorrelated jitter and AWS guidance

AWS published three jitter strategies beyond full jitter:

| Strategy | Formula | Behavior |
|---|---|---|
| Full jitter | `random(0, cap)` | Maximum spread, lowest overlap |
| Equal jitter | `half + random(0, half)` | Minimum delay guaranteed |
| Decorrelated jitter | `random(base, prevDelay * 3)` | Adapts to actual delay |

Decorrelated jitter works well when previous delay is tracked — each retry independently chooses a new delay based on the last, preventing the "everyone at zero" spike of full jitter on attempt 0 while still spreading subsequent retries.

For infrastructure-level retries (load balancers, service mesh), configure retry budgets — max percentage of requests that can be retries. Envoy's `retry_budget` prevents retry storms from consuming all connection pool capacity.

## Idempotency requirements for retries

Retrying a non-idempotent operation creates duplicates:

```typescript
// Dangerous — retries on timeout may double-charge
await withRetry(() => stripe.charges.create({ amount: 5000, source: token }));

// Safe — idempotency key makes retries safe
await withRetry(() => stripe.charges.create(
  { amount: 5000, source: token },
  { idempotencyKey: `charge-${orderId}` }
));
```

Rule: if the operation has side effects (payment, email, inventory decrement), it needs an idempotency key before you wrap it in retry logic. Read operations and idempotent upserts are safe to retry freely.

## Retry budgets and hedging

**Retry budget** — cap total retry traffic as percentage of normal traffic:

```
max_retries = normal_request_rate * retry_budget_percent
```

When budget exhausted, fail fast instead of retrying. Prevents a degraded dependency from consuming all client capacity.

**Hedged requests** — send a second copy of slow requests after a delay (e.g., 95th percentile latency). First response wins; cancel the loser. Useful for latency-sensitive reads where tail latency matters more than load. Don't hedge writes — you'll create duplicates.

## Per-dependency retry configuration

Not every dependency gets the same policy:

| Dependency | Max attempts | Base delay | Cap | Notes |
|---|---|---|---|---|
| Payment provider | 3 | 500ms | 10s | Idempotency key required |
| Internal API | 5 | 100ms | 30s | Circuit breaker at 50% |
| Email service | 3 | 1s | 60s | DLQ on exhaustion |
| Database | 2 | 50ms | 1s | Fail fast, don't mask DB issues |
| CDN/static | 1 | 0 | 0 | No retry, use fallback URL |

Centralize retry config in a service mesh or shared library — don't scatter magic numbers across call sites.

## Observability for retry storms

Metrics to alert on:

- `retry_attempts_total{service, attempt_number}` — spike in attempt > 0 indicates dependency trouble
- `retry_exhausted_total` — retries gave up; likely user-facing errors
- `circuit_breaker_state{dependency}` — open circuit = fail-fast mode active
- Ratio of retry traffic to primary traffic — exceeds budget threshold

Dashboard the dependency's perspective too — if your retries double their traffic during an outage, you're part of the problem.

## Failure modes

- **Retrying 500s on POST without idempotency** — creates duplicate records
- **No cap on attempts or delay** — retries forever, masking permanent failures
- **Synchronized retries across clients** — no jitter, creates thundering herd
- **Retrying through an overloaded service** — keeps it overloaded; circuit breaker prevents this
- **Ignoring Retry-After on 429** — violates rate limit contract, gets IP banned
- **Retry at every layer** — client retries × service mesh retries × load balancer retries = exponential amplification

## Production checklist

- Full jitter on all client-side retry policies
- Idempotency keys on all retried write operations
- Circuit breaker paired with retry (fail fast when open)
- Retry-After header honored on 429 responses
- Per-dependency retry config documented
- Retry budget configured at infrastructure level
- Retry metrics dashboarded with alerts on exhaustion spikes

## Resources

- [AWS Exponential Backoff And Jitter](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
- [Google Cloud retry strategy](https://cloud.google.com/iot/docs/how-tos/exponential-backoff)
- [Polly .NET resilience library](https://github.com/App-vNext/Polly)
- [Envoy retry policies](https://www.envoyproxy.io/docs/envoy/latest/configuration/http/http_filters/router_filter#config-http-filters-router-x-envoy-retry-on)
- [gRPC retry design](https://github.com/grpc/proposal/blob/master/A6-client-retries.md)
