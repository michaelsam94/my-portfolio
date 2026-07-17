---
title: "AI Agents: Global Load Balancer Health"
slug: "agent-global-load-balancer-health"
description: "Design health checks and failover for global load balancers serving agent APIs—streaming-aware probes, regional drain, capacity signals, and avoiding false negatives on long-lived SSE connections."
datePublished: "2026-04-07"
dateModified: "2026-04-07"
tags: ["AI", "Agent", "Global"]
keywords: "global load balancer, health checks, GCLB, CloudFront, agent API, SSE, failover, regional drain, anycast"
faq:
  - q: "Why do standard HTTP health checks fail for agent endpoints?"
    a: "Agent APIs use long-lived SSE/WebSocket streams, GPU-backed inference with variable latency, and dependency chains (vector DB, model provider). A /health returning 200 from a process that cannot complete inference is worse than failing—GLB marks the backend healthy while users timeout on real requests. Health checks must validate critical dependencies with timeouts matching production SLOs."
  - q: "Should health checks call the LLM provider?"
    a: "Use synthetic lightweight checks in production—embedding ping or cached minimal completion—not full user prompts. Rate-limit health traffic separately. In degraded mode, fail health when provider error rate exceeds threshold so GLB shifts traffic to regions with working upstreams."
  - q: "How do we drain a region without killing active agent sessions?"
    a: "Set backend weight to zero (connection draining) with drain timeout exceeding p99 stream duration. Stop new session affinity to draining backends. Return Retry-After on new connections. Signal clients to reconnect via SSE id field before hard cutoff."
  - q: "What metrics should drive automated regional failover?"
    a: "Combine GLB probe success with application golden signals: inference error rate, p95 time-to-first-token, and queue depth. Failover on composite burn rate, not probe alone—prevents flapping when probes pass but inference is melting down."
---
Regional failover sent 40% of agent traffic to `us-central1` during a partial outage—but users in Europe saw 90-second hangs because the load balancer kept routing new SSE connections to a backend pool whose `/health` returned 200 while the GPU queue was saturated. Probes checked a static JSON file; they never touched the model router.

Global load balancer health for agent systems sits at the intersection of anycast routing, streaming HTTP, and bursty GPU workloads. A green health check that ignores inference backlog is how you drain an entire region's reputation without triggering failover. This post covers probe design, dependency validation, connection draining for long streams, and composite signals that automate regional shift without flapping.

## GLB health vs agent readiness

Cloud load balancers (GCP GLB, AWS ALB/Global Accelerator, Cloudflare Load Balancing, Azure Front Door) mark backends healthy when probes succeed on configured paths. Agent stacks need **readiness** distinct from **liveness**:

| Check type | Validates | Risk if used alone |
|------------|-----------|-------------------|
| Liveness | Process up | Routes to pods that cannot infer |
| Readiness | Can serve new sessions | May ignore dependency degradation |
| Deep readiness | Model route + vector ping | Higher probe cost; tune frequency |

Expose two endpoints:

- `/healthz` — process alive (kube liveness)
- `/readyz` — can accept new agent sessions (GLB + kube readiness)

GLB should target `/readyz`, not `/healthz`.

## Readiness probe implementation

```python
# readiness.py
import asyncio
import time
from dataclasses import dataclass

@dataclass
class ReadinessResult:
    ok: bool
    checks: dict[str, bool]
    latency_ms: dict[str, float]

async def check_vector(timeout: float = 0.5) -> bool:
    start = time.monotonic()
    try:
        await vector_client.ping(timeout=timeout)
        return True
    except Exception:
        return False
    finally:
        pass

async def check_model_router(timeout: float = 1.0) -> bool:
    # Lightweight: metadata or cached token, not full generation
    try:
        await model_router.ping(timeout=timeout)
        return True
    except Exception:
        return False

async def check_queue_depth(max_depth: int = 100) -> bool:
    depth = await session_queue.depth()
    return depth < max_depth

async def readiness() -> ReadinessResult:
    t0 = time.monotonic()
    vector_ok, model_ok, queue_ok = await asyncio.gather(
        check_vector(),
        check_model_router(),
        check_queue_depth(),
    )
    checks = {"vector": vector_ok, "model_router": model_ok, "queue": queue_ok}
    ok = all(checks.values())
    return ReadinessResult(
        ok=ok,
        checks=checks,
        latency_ms={"total": (time.monotonic() - t0) * 1000},
    )
```

```typescript
// Express handler
app.get("/readyz", async (_req, res) => {
  const result = await readiness();
  res.status(result.ok ? 200 : 503).json({
    ok: result.ok,
    checks: result.checks,
    latency_ms: result.latency_ms,
  });
});
```

Return **503** when any critical dependency fails—GLB removes the backend from rotation.

## Probe tuning for streaming workloads

Default GLB intervals (5–10s) and timeouts (5s) may be wrong for agent APIs:

**Timeout** must exceed p99 dependency latency under load, but stay below user-facing fail threshold. Start with 2s for vector ping, 3s for model router ping.

**Interval** — faster detects failure quicker but amplifies probe load. Separate health traffic from user traffic via dedicated probe path rate limits.

**Unhealthy threshold** — require 2–3 consecutive failures before marking unhealthy to avoid flapping on transient provider blips.

**Healthy threshold** — require 2 consecutive successes before re-admitting after recovery—prevents thundering herd on cold GPU nodes.

For SSE endpoints, do not use the stream URL as health check—intermediaries buffer differently. Use `/readyz` on the same origin.

## Multi-region backend configuration

```yaml
# GCP BackendService excerpt (conceptual)
backends:
  - group: europe-west1-agent-mig
    capacityScaler: 1.0
  - group: us-central1-agent-mig
    capacityScaler: 1.0
healthChecks:
  - port: 8080
    requestPath: /readyz
    checkIntervalSec: 10
    timeoutSec: 5
    healthyThreshold: 2
    unhealthyThreshold: 3
connectionDraining:
  drainingTimeoutSec: 900  # 15 min — exceed p99 SSE session length
```

Use **capacity scaler** to shift traffic gradually during degradation before full failover—0.5 weight on struggling region while investigating.

## Connection draining and session affinity

Agent clients maintain long SSE connections. When draining:

1. GLB stops new connections to backend (weight 0 or unhealthy)
2. Existing connections complete within `drainingTimeoutSec`
3. Client SDK implements reconnect with `Last-Event-ID`

```typescript
// Client reconnect pattern
async function connectAgentStream(sessionId: string, lastEventId?: string) {
  const headers: Record<string, string> = {};
  if (lastEventId) headers["Last-Event-ID"] = lastEventId;
  const res = await fetch(`/api/agent/stream/${sessionId}`, { headers });
  if (res.status === 503) {
    const retryAfter = Number(res.headers.get("Retry-After") ?? "5");
    await sleep(retryAfter * 1000);
    return connectAgentStream(sessionId, lastEventId);
  }
  // process stream...
}
```

Server sends terminal event before shutdown:

```python
async def graceful_shutdown(signal):
    readiness_state.accepting = False  # /readyz → 503
    await asyncio.sleep(5)  # GLB propagation
    for session in active_sessions:
        await session.send({"event": "server_draining", "retry_ms": 5000})
    await wait_for_sessions(timeout=840)
```

## Composite failover signals

Probes alone cause false negatives (healthy) and false positives (flapping). Add automation from observability:

```python
def should_reduce_region_capacity(metrics: RegionMetrics) -> float:
    """Return capacity scaler 0.0–1.0"""
    if metrics.readyz_success_rate < 0.9:
        return 0.0
    if metrics.ttft_p95_ms > metrics.slo_ttft_ms * 1.5:
        return 0.3
    if metrics.inference_error_rate > 0.05:
        return 0.0
    return 1.0
```

Integrate via control plane API (update backend weight) or runbook automation when burn rate exceeds threshold for 5 minutes. Human approval for full cross-region failover; automatic for single-backend drain within region.

## Anycast, DNS, and health interaction

With anycast (Cloudflare, Fastly), health checks run from multiple probe regions. A backend may appear healthy from US probes but fail EU user paths due to peering issues. Deploy **synthetic checks from user regions** (Catchpoint, Datadog Synthetics) in addition to provider health checks.

For Route53/Cloud DNS failover policies, align TTL with recovery expectations—low TTL (60s) speeds failover but increases DNS load.

## Testing regional failure

Game days to run quarterly:

1. **Dependency kill** — block model provider from one region; verify traffic shifts within SLO
2. **GPU saturation** — load test until queue depth fails readiness; verify GLB removes backends
3. **Partial drain** — capacity scaler 0; verify no new sessions, existing streams complete
4. **Split brain** — two regions healthy but vector replication lag; verify read-your-writes policy

```bash
# Simulate readiness failure in staging
kubectl exec deploy/agent-api -- touch /tmp/fail-readyz
# Observe GLB backend count drop in console/metrics
```

Measure **time-to-detect** and **time-to-mitigate** separately—executives care about both.

## Security considerations

Health endpoints leak infrastructure detail if verbose. Public `/readyz` should return minimal JSON; detailed check breakdown only on internal admin port or authenticated ops path.

Rate-limit probe sources to GLB IP ranges. Attackers probing `/readyz` to map dependency failures is reconnaissance—monitor unusual 503 patterns.

Do not embed secrets in health check requests to downstream dependencies.

## Common failure modes

**Static file /health.** Always 200; useless for agents.

**Probe on wrong port.** Sidecar healthy; app broken.

**Drain timeout too short.** Hard-cut mid-stream; corrupted agent state.

**Session affinity stickiness.** Users pinned to unhealthy backend after failover—combine affinity with readiness.

**Cold start on scale-up.** New backends marked healthy before GPU warm—use startup probe with model warm-up job.

**Ignoring cross-region data.** Failover to region without vector replica—RAG returns empty.

## Cross-provider health check reference

| Provider | Probe config location | Drain support | Notes |
|----------|----------------------|---------------|-------|
| GCP GLB | BackendService `healthChecks` | `connectionDraining.drainingTimeoutSec` | Global vs regional backends differ |
| AWS ALB | Target group health check | Deregistration delay | Use `/readyz` on target port |
| Cloudflare LB | Monitor pools | Steered pool priority | Synthetic monitors from multiple regions |
| Azure Front Door | Health probes | Origin drain via disabled state | Pair with App Gateway readiness |

Align probe timeout with your TTFT SLO—not generic 5s defaults from tutorials.

## The takeaway

Global load balancer health for agent APIs requires readiness probes that validate inference path dependencies, drain timeouts aligned with SSE session length, and composite failover signals beyond HTTP 200. Treat GLB configuration as part of your SLO design—probe what users actually need, drain gracefully, and automate capacity shifts from golden metrics when backends are technically alive but functionally useless.

## Resources

- [GCP load balancer health checks](https://cloud.google.com/load-balancing/docs/health-checks)
- [AWS ELB health checks](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/target-group-health-checks.html)
- [Cloudflare Load Balancing monitors](https://developers.cloudflare.com/load-balancing/monitors/)
- [Kubernetes readiness and liveness probes](https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/)
- [Server-Sent Events — reconnection](https://html.spec.whatwg.org/multipage/server-sent-events.html)
