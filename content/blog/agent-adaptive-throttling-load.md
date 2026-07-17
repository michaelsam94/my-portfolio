---
title: "AI Agents: Adaptive Throttling Load"
slug: "agent-adaptive-throttling-load"
description: "Static rate limits fail when traffic spikes or dependencies slow down — adaptive throttling uses live latency and error signals to shed load before cascading failures take down your API."
datePublished: "2025-12-01"
dateModified: "2025-12-01"
tags: ["AI", "Agent", "Adaptive"]
keywords: "adaptive throttling, load shedding, rate limiting, AIMD, token bucket, circuit breaker, backpressure, overload protection"
faq:
  - q: "How is adaptive throttling different from a fixed rate limit?"
    a: "Fixed limits (100 req/s per API key) ignore system health. Adaptive throttling adjusts permitted throughput based on real-time signals — p99 latency, error rates, queue depth, CPU — allowing higher throughput when healthy and tightening automatically when the service degrades."
  - q: "What signals should drive throttle decisions?"
    a: "Use symptoms, not causes: request latency percentiles, 5xx rate, saturation of thread pools, GPU memory for inference endpoints, and upstream dependency health. Avoid throttling on CPU alone — a batch job can spike CPU while request latency stays flat."
  - q: "Should throttling return 429 or queue requests?"
    a: "Return 429 or 503 with Retry-After when latency SLO is at risk — queuing unbounded requests amplifies tail latency and memory pressure. Short bounded queues (50–200ms wait) work for idempotent reads; fail fast for expensive LLM inference and writes."
  - q: "Can adaptive throttling work with LLM inference endpoints?"
    a: "Yes. Track time-to-first-token, tokens/sec, and GPU KV-cache utilization. Shed load by rejecting new sessions before degrading in-flight requests. Offer degraded model tiers (smaller model, shorter context) as a throttle stage before hard rejection."
---
Every API team sets rate limits. Most are static numbers someone picked during a design review — 100 requests per minute per key, 10 concurrent connections, a token bucket sized for normal Tuesday traffic.

Then Black Friday arrives, a dependency slows from 40ms to 800ms, or a viral feature doubles QPS. Static limits either block healthy traffic (set too low) or allow a death spiral (set too high). Workers pile up, garbage collection pauses grow, the database connection pool exhausts, and every request — including health checks — starts timing out.

Adaptive throttling closes the loop: the limit moves with system capacity rather than a spreadsheet guess.

## Feedback control, not magic

Think of adaptive throttling as a thermostat. You set a target (p99 latency < 300ms), measure the process variable (current p99), and adjust the control output (accepted request rate).

```
         ┌──────────────┐
  setpoint ──►│  Controller  │──► admission rate
  (SLO target) │  (AIMD / PID) │
         ▲     └──────┬───────┘
         │            │
         └────────────┘
              measured p99 / error rate
```

Unlike a circuit breaker that trips open and stays open, adaptive throttles **gradually** reduce admission, probe recovery, and ramp back — similar to TCP congestion control.

## Signals that should drive decisions

Prioritize **user-visible symptoms**:

| Signal | Why it matters | Caveat |
|--------|----------------|--------|
| p99 request latency | Direct SLO proxy | Noisy on low traffic — use min sample window |
| 5xx / timeout rate | User pain | Lagging indicator; combine with latency |
| Active in-flight requests | Queue buildup predictor | Set max concurrency per worker |
| Thread pool saturation | Rejection imminent | JVM, Node worker pools |
| GPU memory / batch queue | LLM-specific | TTFT spikes before OOM |
| Upstream dependency latency | Early warning | Throttle before your pool fills |

Do not throttle on CPU alone. A background compaction job can hit 90% CPU while API latency is fine. Conversely, latency can explode at moderate CPU when locks contend.

## AIMD: the workhorse algorithm

Additive Increase, Multiplicative Decrease is the classic adaptive pattern from TCP:

- **Increase** allowed rate slowly when healthy (+N req/s every window)
- **Decrease** multiplicatively when unhealthy (rate × 0.5 on breach)

```go
type AdaptiveLimiter struct {
    currentLimit float64 // requests per second
    minLimit     float64
    maxLimit     float64
    increaseStep float64
    decreaseFactor float64
    mu           sync.Mutex
}

func (l *AdaptiveLimiter) Adjust(p99Ms float64, errorRate float64, targetP99 float64) {
    l.mu.Lock()
    defer l.mu.Unlock()

    healthy := p99Ms < targetP99 && errorRate < 0.01

    if healthy {
        l.currentLimit = math.Min(l.currentLimit+l.increaseStep, l.maxLimit)
    } else {
        l.currentLimit = math.Max(l.currentLimit*l.decreaseFactor, l.minLimit)
    }
}

func (l *AdaptiveLimiter) Allow() bool {
    l.mu.Lock()
    limit := l.currentLimit
    l.mu.Unlock()
    return l.tokenBucket.TryAcquire(1.0 / limit)
}
```

Run the adjust loop every 1–5 seconds with smoothed metrics (exponential moving average over 30–60s). Raw per-second p99 flickers and causes limit oscillation.

## Layered admission control

Apply throttles at multiple layers; inner layers protect precious resources:

```
Client → Edge (CDN/WAF) → Gateway (global limit) → Service (adaptive) → Dependency pool
```

**Edge:** block obvious abuse, geo anomalies, credential stuffing — static rules.

**Gateway:** global concurrency cap as last resort — protects the fleet.

**Service adaptive:** the AIMD loop on latency/error — most granular.

**Dependency pool:** separate limits on DB connections, LLM provider tokens, embedding batch size.

A request rejected at the gateway saves a DB round trip. A request rejected at the service after auth still wasted JWT validation — order cheap checks before expensive ones, but authenticate before user-specific rate limits to prevent key sharing abuse.

## Token bucket vs sliding window vs concurrency

Adaptive throttling adjusts the **rate parameter**; you still need a **shape**:

- **Token bucket**: allows bursts; good for interactive APIs
- **Sliding window log**: precise; higher memory cost
- **Concurrency semaphore**: limits in-flight work — often the binding constraint for LLM inference

For GPU-backed endpoints, concurrency limits beat RPS limits. One request streaming 8k tokens occupies the GPU for seconds; counting requests per second misleads.

```typescript
class ConcurrencyGate {
  private inFlight = 0;

  constructor(
    private maxConcurrent: number,
    private adaptiveController: AdaptiveLimiter
  ) {}

  async acquire(): Promise<ReleaseFn> {
    const effectiveMax = Math.floor(
      this.maxConcurrent * this.adaptiveController.getCapacityRatio()
    );

    if (this.inFlight >= effectiveMax) {
      throw new ThrottledError("server_busy", {
        retryAfterMs: estimateWaitTime(this.inFlight, effectiveMax),
      });
    }

    this.inFlight++;
    return () => {
      this.inFlight--;
    };
  }
}
```

`getCapacityRatio()` returns currentLimit / maxLimit from the AIMD controller, scaling concurrency smoothly.

## Graceful degradation tiers

Hard 429s frustrate users. Tiered responses convert throttle events into partial service:

1. **Tier A (healthy):** full feature set, normal models
2. **Tier B (elevated load):** disable non-essential features (recommendations, rich previews)
3. **Tier C (stressed):** smaller LLM, truncated context, cached responses only
4. **Tier D (critical):** 429/503 with Retry-After

```typescript
async function handleChatRequest(req: ChatRequest): Promise<ChatResponse> {
  const loadTier = loadController.currentTier();

  switch (loadTier) {
    case "A":
      return fullPipeline(req);
    case "B":
      return fullPipeline({ ...req, skipRag: true });
    case "C":
      return degradedPipeline(req, { model: "small", maxTokens: 512 });
    case "D":
      throw new ServiceUnavailableError({ retryAfter: 30 });
  }
}
```

Product must pre-define tiers. Engineers should not invent degradation behavior during an incident.

## Per-tenant fairness under global stress

Global adaptive limits prevent fleet collapse but allow one tenant to consume the entire budget. Add **weighted fair queuing**:

- Each tenant has a base quota
- Unused quota expires (prevent hoarding)
- During global throttle, no tenant exceeds 2× their fair share

```python
def admit(tenant_id: str, global_limit: float) -> bool:
    tenant_limit = tenant_quotas.get(tenant_id, default_quota)
    tenant_usage = usage_counter.rate(tenant_id)
    global_usage = usage_counter.rate("global")

    if global_usage >= global_limit:
        # under global stress, enforce fair share strictly
        fair_share = global_limit / active_tenant_count()
        return tenant_usage < fair_share

    return tenant_usage < tenant_limit
```

Enterprise contracts may guarantee minimum throughput — reserve capacity headroom in your maxLimit calculation.

## Client behavior on 429 and 503

Throttling only works if clients back off. Return:

```
HTTP/1.1 429 Too Many Requests
Retry-After: 2
X-RateLimit-Remaining: 0
Content-Type: application/problem+json

{"type":"throttled","title":"Server busy","retryAfterMs":2000}
```

Document exponential backoff with jitter in your SDK:

```typescript
async function withRetry<T>(fn: () => Promise<T>, maxAttempts = 5): Promise<T> {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (e) {
      if (!(e instanceof ThrottledError) || attempt === maxAttempts - 1) throw e;
      const delay = e.retryAfterMs ?? Math.min(1000 * 2 ** attempt, 30000);
      await sleep(delay + Math.random() * 500);
    }
  }
  throw new Error("unreachable");
}
```

Without jitter, synchronized client retries create **retry storms** that recreate the overload.

## Observability for throttle decisions

Dashboard panels operators need during incidents:

- Current admission rate vs max (the AIMD limit over time)
- Rejected request rate by tier and tenant
- p99 latency overlaid with throttle events
- In-flight concurrency vs pool size

Log every throttle decision at debug sampling (1%) in normal operation, 100% during elevated tiers. Include `loadTier`, `currentLimit`, `p99`, and `errorRate` as structured fields.

Alert when rejection rate exceeds 5% for five minutes — users notice before your error budget math catches up.

## Testing adaptive behavior

Unit test the controller with synthetic metric feeds:

```go
func TestAIMDDecreaseOnLatencyBreach(t *testing.T) {
    lim := NewAdaptiveLimiter(1000, 100, 10000, 50, 0.5)
    lim.Adjust(p99Ms: 600, errorRate: 0, targetP99: 300)
    assert.Equal(t, 500.0, lim.CurrentLimit())
}
```

Integration tests with k6 or Locust:

1. Baseline load at SLO
2. Spike to 3× expected QPS
3. Assert p99 stays bounded and rejection rate rises
4. Drop load, assert recovery within N windows

Chaos experiments: inject 500ms latency into dependency calls and verify throttle engages before connection pool exhaustion.

## When not to adapt

Adaptive throttling adds complexity. Skip it when:

- Traffic is flat and predictable with hard contractual SLAs per tenant (static quotas suffice)
- The service is purely async/batch with unbounded queueing acceptable
- You have autos scaling faster than overload develops (rare for stateful or GPU workloads)

For most synchronous APIs and inference endpoints serving variable LLM load, adaptive admission is cheaper than outage pages.

Static rate limits are a fence. Adaptive throttling is cruise control — it slows before the engine redlines and speeds up when the road clears. Wire it to latency and error signals you already collect, tier degradation before hard failure, and teach clients to backoff. Your on-call will spend fewer nights draining connection pools.

## Resources

- [Google SRE Book: Handling Overload (Chapter 21)](https://sre.google/sre-book/handling-overload/)
- [Netflix: Performance Under Load (Adaptive concurrency)](https://netflixtechblog.com/performance-under-load-3e6fa9a60581)
- [Envoy Proxy: Global rate limiting](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/other_features/global_rate_limiting)
- [AWS Architecture Blog: Token bucket rate limiting](https://aws.amazon.com/blogs/architecture/rate-limiting-strategies-for-serverless-applications/)
- [Martin Fowler: Circuit Breaker pattern](https://martinfowler.com/bliki/CircuitBreaker.html)
