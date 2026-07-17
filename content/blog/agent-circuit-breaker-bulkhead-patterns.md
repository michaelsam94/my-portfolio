---
title: "AI Agents: Circuit Breaker Bulkhead Patterns"
slug: "agent-circuit-breaker-bulkhead-patterns"
description: "Retries and parallel tool calls turn one slow LLM into a fleet-wide outage—circuit breakers stop hammering dead dependencies while bulkheads cap concurrency per route, tenant, and tool pool."
datePublished: "2024-10-30"
dateModified: "2024-10-30"
tags: ["AI", "Agent", "Circuit"]
keywords: "circuit breaker, bulkhead, resilience patterns, agent orchestration, LLM timeout, concurrency limits, fallback model, failure isolation"
faq:
  - q: "Where should circuit breakers sit in an agent pipeline?"
    a: "At every outbound dependency boundary: LLM gateway, embedding service, vector DB, reranker, and external tool HTTP clients. Breakers track failure rate per dependency name—not per agent session—so one bad route opens while others stay closed."
  - q: "What is the difference between a circuit breaker and a bulkhead for agents?"
    a: "A circuit breaker stops calls after errors exceed a threshold, giving the dependency time to recover. A bulkhead limits concurrent in-flight calls (semaphore per pool) so one tenant's tool storm cannot exhaust workers shared by everyone else."
  - q: "How do breakers interact with LLM streaming?"
    a: "Open the breaker on sustained timeouts, connection errors, and 5xx—not on single slow tokens mid-stream. Track TTFB separately from stream duration; half-open probes use small non-streaming health checks to avoid tying up long connections."
  - q: "What fallback should run when the primary model breaker opens?"
    a: "Pre-declare an ordered fallback chain (cheaper model, cached response, templated apology with retry-after). Never silently switch models without logging—downstream eval assumptions and cost accounting depend on knowing which route served the reply."
---
One degraded embedding cluster should not take down customer-facing agents. Without isolation, it does exactly that: sessions pile up waiting on retrieval, thread pools fill, health checks time out, and Kubernetes replaces healthy pods while the root cause is still a single dependency refusing connections. Circuit breakers and bulkheads are the difference between **failing one feature** and **failing the fleet**.

Microservices literature popularized these patterns for HTTP APIs. Agent orchestration adds fan-out—multiple retrievals, parallel tools, streaming completions—so defaults from a Spring Boot tutorial rarely fit. This post covers breakers and bulkheads sized for LLM agent workloads.

## Circuit breaker states for agent dependencies

Classic three-state breakers apply:

| State | Behavior | Agent nuance |
|-------|----------|--------------|
| Closed | Calls pass; failures counted | Count 429 as failure if sustained; single 429 may be normal |
| Open | Fail fast; no calls | Return fallback before acquiring bulkhead slot |
| Half-open | Limited probes | Use cheap probe (mini embed, HEAD request) not full agent turn |

```typescript
// resilience/circuitBreaker.ts
type State = "closed" | "open" | "half_open";

export class CircuitBreaker {
  private state: State = "closed";
  private failures = 0;
  private lastOpenedAt = 0;

  constructor(
    private readonly name: string,
    private readonly failureThreshold: number,
    private readonly openDurationMs: number,
    private readonly halfOpenPermits: number,
  ) {}

  async execute<T>(fn: () => Promise<T>, fallback: () => T): Promise<T> {
    if (this.state === "open") {
      if (Date.now() - this.lastOpenedAt > this.openDurationMs) {
        this.state = "half_open";
        this.failures = 0;
      } else {
        metrics.counter("breaker.short_circuit").add(1, { dep: this.name });
        return fallback();
      }
    }

    try {
      const result = await fn();
      this.onSuccess();
      return result;
    } catch (err) {
      this.onFailure(err);
      if (this.state === "open") return fallback();
      throw err;
    }
  }

  private onFailure(err: unknown) {
    this.failures++;
    if (this.failures >= this.failureThreshold) {
      this.state = "open";
      this.lastOpenedAt = Date.now();
      metrics.counter("breaker.opened").add(1, { dep: this.name });
    }
  }

  private onSuccess() {
    if (this.state === "half_open") this.state = "closed";
    this.failures = 0;
  }
}
```

Tune thresholds per dependency class. Embedding batch APIs tolerate brief spikes; payment tool calls should open quickly after consecutive errors.

## Bulkheads: concurrency pools that match work

Bulkheads implement **maximum parallel in-flight calls** per pool. Without them, one orchestrator instance accepts unlimited concurrent tool HTTP calls and exhausts file descriptors or upstream connection limits.

Partition pools by:

- **Dependency** — embed, vector, rerank, tools
- **Tenant tier** — enterprise vs free shares floor, not ceiling
- **Route** — GPT-4 class vs flash model separate semaphores

```typescript
// resilience/bulkhead.ts
export class Bulkhead {
  private inFlight = 0;
  private queue: Array<() => void> = [];

  constructor(
    private readonly name: string,
    private readonly maxConcurrent: number,
    private readonly maxWaitMs: number,
  ) {}

  async run<T>(fn: () => Promise<T>): Promise<T> {
    await this.acquire();
    try {
      return await fn();
    } finally {
      this.release();
    }
  }

  private acquire(): Promise<void> {
    if (this.inFlight < this.maxConcurrent) {
      this.inFlight++;
      return Promise.resolve();
    }
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        metrics.counter("bulkhead.rejected").add(1, { pool: this.name });
        reject(new BulkheadRejectedError(this.name));
      }, this.maxWaitMs);

      this.queue.push(() => {
        clearTimeout(timer);
        this.inFlight++;
        resolve();
      });
    });
  }

  private release() {
    this.inFlight--;
    const next = this.queue.shift();
    if (next) next();
  }
}
```

Order matters: **check breaker before acquiring bulkhead**. Holding a bulkhead slot while returning fallback wastes capacity other sessions need.

## Composing breaker + bulkhead at the LLM gateway

```typescript
// gateway/llmCall.ts
const breakers = {
  "gpt-4o": new CircuitBreaker("gpt-4o", 5, 30_000, 2),
  "gpt-4o-mini": new CircuitBreaker("gpt-4o-mini", 8, 20_000, 3),
};

const bulkheads = {
  "gpt-4o": new Bulkhead("gpt-4o", 40, 500),
  "gpt-4o-mini": new Bulkhead("gpt-4o-mini", 120, 300),
};

export async function complete(
  route: string,
  request: LlmRequest,
): Promise<LlmResponse> {
  const breaker = breakers[route]!;
  const bulkhead = bulkheads[route]!;

  return breaker.execute(
    () =>
      bulkhead.run(() => upstreamClient.complete(route, request)),
    () => fallbackChain(request, route),
  );
}

function fallbackChain(req: LlmRequest, failedRoute: string): LlmResponse {
  audit.log({ event: "breaker_fallback", from: failedRoute, to: "gpt-4o-mini" });
  return complete("gpt-4o-mini", { ...req, maxTokens: Math.min(req.maxTokens, 512) });
}
```

Expose breaker state on metrics dashboards: `breaker_state{dep="gpt-4o"}` gauge 0/1/2 for closed/open/half-open. Page when open persists beyond expected provider incidents.

## Tool fan-out and nested bulkheads

A single user message may invoke five tools. Global orchestrator concurrency is insufficient—nest bulkheads:

```
Session semaphore (per user): max 2 concurrent agent turns
  └── Tool pool bulkhead: max 10 parallel HTTP tools globally
        └── Per-host bulkhead: max 3 to same API origin
```

Prevents one agent from opening fifty connections to a fragile partner API while still allowing other tenants' retrieval to proceed.

## Streaming-specific breaker signals

Do not treat slow token delivery as failure mid-stream unless bytes stall beyond `idleTimeoutMs`. Structure:

1. Breaker closed → acquire bulkhead → open stream
2. If TTFB > threshold → cancel stream, record failure toward breaker
3. If stream idle > threshold → cancel, partial response policy (truncate vs error)
4. Successful stream end → success for breaker

Half-open probes use `maxTokens: 1` completion or provider `/models` health—not full user prompts.

## Testing breakers and bulkheads

Unit tests alone miss timing bugs. Add:

- **Fault injection** — force N consecutive 503s, assert breaker opens and fallback serves
- **Concurrency test** — 200 parallel calls, bulkhead max 20 → exactly 20 in flight, rest reject or queue per policy
- **Recovery test** — after open window, half-open probe succeeds, breaker closes

Load tests should verify **reject rate** under saturation matches SLO—not that every request eventually completes.

## Observability and alerting

Minimum metrics:

- `breaker_state`, `breaker_opened_total`, `breaker_short_circuit_total`
- `bulkhead_in_flight`, `bulkhead_rejected_total`, `bulkhead_wait_seconds`
- `fallback_route_total{from,to}`

Alert on:

- Breaker open > 5 minutes for tier-1 routes
- Bulkhead reject rate > 5% sustained (capacity mismatch)
- Fallback rate spike without declared provider incident (config regression)

Trace attributes: `breaker.decision`, `bulkhead.pool`, `fallback.route` on every agent span.

## Anti-patterns

- **Shared breaker across unrelated APIs** — opens embed breaker and blocks LLM incorrectly
- **Retry inside open breaker** — defeats fail-fast; retries belong in closed state only with jitter caps
- **Unbounded queue on bulkhead** — converts rejections into latency bombs; prefer fast fail + user-visible retry-after
- **Silent model fallback** — breaks cost controls and compliance disclosures

## Tenant fairness and priority bulkheads

Free-tier tenants and internal health checks should not share the same bulkhead pool as paid production traffic. Partition semaphores:

```typescript
const pools = {
  "gpt-4o:enterprise": new Bulkhead("gpt-4o:enterprise", 80, 800),
  "gpt-4o:standard": new Bulkhead("gpt-4o:standard", 30, 400),
  "gpt-4o:internal": new Bulkhead("gpt-4o:internal", 5, 100),
};
```

When a pool saturates, reject with **Retry-After** scoped to tier—enterprise gets shorter backoff hints because their SLO pays for reserved capacity. Avoid stealing slots across tiers; that converts a bulkhead into a hidden priority inversion.

Priority does not mean starvation: reserve a minimum `floor` of slots per tier so a enterprise flood cannot consume 100% of provider quota and block health probes. Probes use the `internal` pool with the tightest breaker thresholds so orchestrators fail fast before user pools degrade.

## Closing

Circuit breakers stop agents from drowning sick dependencies in optimistic retries. Bulkheads stop one session's parallel fan-out from consuming the whole worker pool. Compose them at every outbound edge—breaker first, bulkhead second, declared fallbacks third—and instrument state so on-call sees **which pool is on fire**, not just that pods are restarts.

## Resources

- [Release It! (Michael Nygard)](https://pragprog.com/titles/mnee2/release-it-second-edition/) — circuit breaker and bulkhead foundations
- [Polly .NET resilience](https://www.thepollyproject.org/) — reference implementations adaptable to TypeScript gateways
- [resilience4j](https://resilience4j.readme.io/docs/circuitbreaker) — state machine and configuration knobs
- [Google SRE: Addressing cascading failures](https://sre.google/sre-book/addressing-cascading-failures/) — overload, retries, and graceful degradation
- [Envoy outlier detection](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/upstream/outlier) — edge breakers before traffic hits agent orchestrators
