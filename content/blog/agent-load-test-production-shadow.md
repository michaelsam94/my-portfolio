---
title: "AI Agents: Load Test Production Shadow"
slug: "agent-load-test-production-shadow"
description: "Load Test Production Shadow: production patterns for ai teams — design, implementation, testing, security, and operations."
datePublished: "2026-03-31"
dateModified: "2026-03-31"
tags: ["AI", "Agent", "Load"]
keywords: "agent, load, test, production, shadow, ai, engineering, architecture"
faq:
  - q: "What is shadow load testing in production?"
    a: "Shadow testing duplicates a slice of real production traffic to a parallel stack — or replays captured requests — without serving responses to users. The shadow path exercises new code, model versions, or infra at production scale and shape while the primary path handles live traffic."
  - q: "How is shadow testing different from synthetic load testing?"
    a: "Synthetic tests use scripted scenarios and guessed payload distributions. Shadow traffic preserves header mixes, payload sizes, auth patterns, and edge-case query shapes that scripts miss — especially important for agent APIs with long prompts and tool-call JSON variance."
  - q: "What traffic percentage is safe to shadow?"
    a: "Start at 0.1–1% mirrored requests, or async replay from sampled logs at controlled QPS. Increase only when shadow stack cost, downstream side effects, and observability are proven isolated. Never shadow writes to shared databases without a sandbox sink."
  - q: "Can you shadow test LLM agent endpoints without doubling token cost?"
    a: "Yes — shadow at the gateway with truncated prompts, cached embeddings, or a cheaper stub model for load shape while separately validating quality on a smaller golden set. Full model shadow is for pre-launch validation windows with explicit budget caps."
---
Staging passed k6 at 500 RPS with mock responses. Production launch day, the agent API melted at 120 RPS — because real prompts averaged 4,200 tokens, tool schemas bloated JSON bodies, and forty percent of requests triggered retrieval fan-out to a vector store staging never exercised at concurrent depth.

Synthetic load tests answer "can the server accept connections?" Shadow load testing in production answers "does this stack survive *our* traffic?" — the mix of long agent prompts, streaming SSE connections, embedding cache misses, and retry storms that only appear when real users and real integrations show up.

This article covers shadow traffic architecture for agent platforms: mirroring safely, replaying from logs, controlling cost, and reading results without taking down the primary path.

## Shadow vs canary vs synthetic

| Approach | Traffic source | User impact | Best for |
|----------|----------------|-------------|----------|
| **Synthetic** | Scripts | None | Baseline capacity, regression in CI |
| **Canary** | Real, routed | Small % see new version | Release validation |
| **Shadow** | Real, duplicated | None (responses discarded) | Scale proof, model/infra comparison |

Shadow is not a release mechanism — users never hit the shadow stack's response. It is an observability and capacity instrument: compare latency histograms, error rates, queue depth, and GPU utilization between primary and shadow under identical load shape.

For agent systems, shadow excels when:

- Prompt length distribution has heavy tails synthetic scripts underestimate.
- Tool-call loops create variable fan-out (1–15 downstream HTTP calls per request).
- Streaming connections hold resources for 30–120 seconds.
- New embedding models or retrieval indexes need production query patterns before cutover.

## Architecture patterns

### Inline mirror at the gateway

The edge proxy duplicates requests to shadow upstream after forwarding to primary:

```
Client → Gateway → Primary agent service → response to client
              └→ Shadow agent service → 204 / discard
```

Envoy example with `request_mirror_policies`:

```yaml
# envoy shadow cluster fragment
routes:
  - match: { prefix: "/v1/agent" }
    route:
      cluster: agent_primary
      request_mirror_policies:
        - cluster: agent_shadow
          runtime_fraction:
            default_value:
              numerator: 1
              denominator: 1000   # 0.1%
```

Shadow cluster points to isolated deployment with:

- Separate database read replicas or synthetic sink for writes
- Distinct rate-limit buckets so shadow cannot starve primary
- `x-shadow-traffic: true` header injected for downstream filtering

### Async replay from access logs

Safer for write-heavy paths: sample sanitized requests to object storage, replay at controlled QPS from a worker fleet:

```python
# replay/shadow_worker.py
import asyncio
import aiohttp
import json
from datetime import datetime

SHADOW_URL = "https://agent-shadow.internal/v1/agent/run"
MAX_QPS = 50

async def replay_record(session: aiohttp.ClientSession, record: dict):
    headers = {k: v for k, v in record["headers"].items() if k.lower() != "host"}
    headers["x-shadow-replay"] = "true"
    headers["x-original-timestamp"] = record["timestamp"]
    async with session.post(
        SHADOW_URL,
        headers=headers,
        json=record["body"],
        timeout=aiohttp.ClientTimeout(total=120),
    ) as resp:
        await resp.read()  # drain body, discard

async def run_batch(records):
    sem = asyncio.Semaphore(MAX_QPS)
    async with aiohttp.ClientSession() as session:
        async def bounded(r):
            async with sem:
                await replay_record(session, r)
        await asyncio.gather(*[bounded(r) for r in records])
```

Replay preserves temporal clustering — bursts after marketing emails, Monday morning spikes — that uniform synthetic RPS hides.

### Service mesh traffic mirroring

Istio `VirtualService` mirror block:

```yaml
apiVersion: networking.istio.io/v1
kind: VirtualService
metadata:
  name: agent-api
spec:
  hosts: [agent-api.prod.svc.cluster.local]
  http:
    - route:
        - destination:
            host: agent-api.prod.svc.cluster.local
          weight: 100
      mirror:
        host: agent-api-shadow.prod.svc.cluster.local
      mirrorPercentage:
        value: 0.5
```

Mesh mirroring copies at L7 including headers; verify shadow backends strip auth cookies that should not replay to alternate tenants.

## Side-effect isolation — the non-negotiable rule

Shadow traffic that creates tickets, charges cards, or sends email is an incident. Enforce isolation:

**Write path guards.** Middleware rejects mutating operations unless `x-shadow-traffic` is set, routing to `/dev/null` sinks or in-memory stores:

```typescript
export function shadowWriteGuard(req: Request, res: Response, next: NextFunction) {
  if (req.headers["x-shadow-traffic"] === "true" && req.method !== "GET") {
    if (process.env.SHADOW_SINK === "noop") {
      return res.status(204).end();
    }
    req.shadowMode = true; // repositories use ShadowTicketRepo
  }
  next();
}
```

**Tool sandbox.** Agent shadow instances register stub tools — CRM writes log to Kafka topic `shadow.tool_calls`, not Salesforce.

**LLM budget caps.** Shadow model router enforces daily token ceiling; overflow returns cached responses or 429 to replay workers.

Document isolation in runbooks; audit quarterly with chaos tests that intentionally send shadow headers to primary write paths in staging.

## Measuring agent-specific saturation

Standard CPU/memory miss agent bottlenecks. Shadow comparisons should dashboard:

| Signal | Primary vs shadow delta indicates |
|--------|-----------------------------------|
| SSE connection count | Streaming handler leaks |
| p95 time-to-first-token | Model queue or GPU scheduling |
| Retrieval QPS per agent request | Index under-provisioned |
| Embedding cache hit rate | Memory pressure on cache tier |
| Tool-call timeout rate | Downstream dependency limits |
| GPU KV cache utilization | Batch size misconfig on shadow |

Compare **histograms**, not just averages. Agent latency is multi-modal: cache hits at 200ms, cold retrieval at 8s. Shadow replay should use Mann-Whitney or KS tests in analysis notebooks — eyeballing p50 hides bimodal failure.

Example Prometheus recording rule:

```yaml
- record: agent:shadow:ttft_p95_ratio
  expr: |
    histogram_quantile(0.95, sum(rate(http_ttft_bucket{stack="shadow"}[5m])) by (le))
    /
    histogram_quantile(0.95, sum(rate(http_ttft_bucket{stack="primary"}[5m])) by (le))
```

Alert when ratio > 1.25 sustained 15 minutes during shadow campaigns.

## Cost control for LLM shadow paths

Full-fidelity model shadow doubles inference spend. Tiered approach:

1. **Shape-only shadow** — gateway truncates prompts to 512 tokens, uses small model; validates autoscaling and connection handling.
2. **Sampled quality shadow** — 1% full model for eval against golden outputs.
3. **Time-boxed full shadow** — 48-hour window before major launch with finance-approved budget.

Tag cloud costs with `stack=shadow` labels on every resource. Finance should see shadow as a line item, not a mystery spike.

## Security and compliance

Production request logs contain PII and secrets. Before replay:

- Strip `Authorization`, cookies, and query tokens in log pipeline.
- Replace user IDs with stable pseudonyms mapping to fixture accounts in shadow DB.
- Block replay of admin or billing routes unless redaction pipeline is certified.
- Retain sampled payloads encrypted; restrict replay worker IAM to read-only on log bucket.

Legal review may classify shadow replay as processing production personal data — document lawful basis and retention limits.

## Running a shadow campaign

A practical playbook:

1. **Hypothesis** — "Shadow index v2 handles 2× retrieval QPS at equal p95 TTFT."
2. **Scope** — 0.5% mirror, 24 hours, read-only agent paths.
3. **Pre-flight** — shadow stack at parity with primary (instance types, limits); dashboards cloned with `stack` label.
4. **Execute** — ramp 0.1% → 0.5% over two hours; watch error budget burn on primary (mirroring adds gateway CPU).
5. **Analyze** — compare saturation metrics; run retrieval quality eval on sampled shadow responses if full model.
6. **Decide** — promote index, scale shadow cluster to primary, or rollback and file capacity ticket.

Post-mortem template includes "was shadow representative?" — if marketing ran a flash campaign during the window, note non-stationarity.

## When shadow testing misleads

**Cold shadow caches.** First hours understate retrieval latency. Warm caches with replay pre-period or compare after steady state.

**Different feature flags.** Shadow must mirror flag state or behavior diverges for reasons unrelated to the hypothesis.

**Missing WebSocket shadow.** Mirroring HTTP POST but not persistent SSE understates connection memory.

**Downstream throttling.** Third-party APIs rate-limit shadow IPs separately; stub externals consistently.

## The takeaway

Shadow load testing closes the gap between staging heroics and production reality for agent platforms. Mirror or replay real traffic at controlled fractions, isolate side effects ruthlessly, compare agent-specific signals beyond CPU, and cap LLM spend. Used well, shadow proves capacity and catches retrieval and streaming regressions before they become user-facing — without asking customers to load-test your next release.

## Resources

- [Envoy request mirroring](https://www.envoyproxy.io/docs/envoy/latest/api-v3/config/route/v3/route_components.proto#envoy-v3-api-field-config-route-v3-routeaction-request-mirror-policies) — inline traffic duplication
- [Istio traffic mirroring](https://istio.io/latest/docs/tasks/traffic-management/mirroring/) — mesh-based shadow routing
- [k6 execution scenarios](https://grafana.com/docs/k6/latest/using-k6/scenarios/) — complement shadow with synthetic baselines
- [Google SRE: load testing](https://sre.google/sre-book/load-balancing-datacenter/) — capacity planning context
- [OpenTelemetry trace sampling](https://opentelemetry.io/docs/concepts/sampling/) — correlate shadow and primary requests in analysis
