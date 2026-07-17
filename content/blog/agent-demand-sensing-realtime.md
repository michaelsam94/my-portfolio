---
title: "AI Agents: Demand Sensing Realtime"
slug: "agent-demand-sensing-realtime"
description: "Demand Sensing Realtime: production patterns for ai teams — design, implementation, testing, security, and operations."
datePublished: "2025-08-03"
dateModified: "2025-08-03"
tags: ["AI", "Agent", "Demand"]
keywords: "agent, demand, sensing, realtime, ai, production, engineering, architecture"
faq:
  - q: "What is demand sensing in an agent platform context?"
    a: "It is the continuous measurement and short-horizon forecasting of agent workload—requests per second, token throughput, queue depth, tool fan-out, and GPU/API quota consumption—so autoscaling, rate limits, and model routing adjust before users hit throttling or latency cliffs."
  - q: "How is agent demand sensing different from generic HTTP autoscaling?"
    a: "Agent requests have heavy tail latency: one prompt may spawn ten tool calls, each invoking an LLM or database. CPU-based HPA misses token bursts and embedding batch jobs. Demand signals must include in-flight tool executions, token budget burn rate, and provider rate-limit headroom—not just request count."
  - q: "What signals best predict agent capacity stress 5–15 minutes ahead?"
    a: "Leading indicators include queue ingress rate acceleration, p95 time-to-first-token drift, rising 429 rates from model providers, growing tool-call concurrency per session, and session count spikes correlated with marketing events or cron-triggered batch agents."
  - q: "Should demand sensing drive cost optimization or latency optimization?"
    a: "Both, with explicit priority tiers. Premium tenant traffic triggers scale-up on latency SLO burn; background batch agents defer to cheaper models when demand forecasts exceed quota. Without tier labels on ingress, cost and latency objectives fight each other unpredictably."
---
Black Friday started normally. Request rate to the shopping assistant agent doubled over twenty minutes—expected. What caught the team off guard was **tool fan-out**: each conversation averaged 7.3 tool calls versus the baseline 2.1, because the new "compare similar products" feature hit every session. Token consumption quadrupled while HTTP request autoscaling added only two pods. p95 latency crossed eight seconds; the model provider started returning 429s; checkout abandonment spiked before anyone correlated dashboards.

Demand sensing for agent platforms is **short-horizon workload forecasting** tuned to agent-specific economics: tokens, tool parallelism, and provider quotas—not just QPS. Real-time sensing closes the loop between ingress metrics, autoscaling, model routing, and rate-limit policies before users feel the squeeze.

## Agent workload anatomy

Decompose demand into measurable components:

| Signal | What it captures | Why HTTP metrics miss it |
|--------|------------------|--------------------------|
| `ingress_rps` | New agent sessions / messages | Hides multi-turn depth |
| `in_flight_tools` | Active tool executions | CPU idle while waiting on LLM |
| `token_burn_rate` | Input + output tokens / sec | Direct cost driver |
| `embedding_qps` | Retrieval index queries | Separate quota pool |
| `provider_429_rate` | Upstream throttling | Lagging indicator |
| `queue_age_p99` | Orchestrator backlog | User-visible latency |

```
Events ──▶ [Ingress] ──▶ Orchestrator Q ──▶ Workers ──▶ LLM / tools
              │                │                │
              ▼                ▼                ▼
         demand-sensing   queue metrics   token counters
              │                │                │
              └────────────────┴────────────────┘
                              │
                    forecast + actuate
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         scale workers   route model    tighten limits
```

## Real-time aggregation pipeline

Use stream processing with sub-minute windows. Kafka + Flink, Kinesis Analytics, or Materialize all work; the pattern matters more than the vendor.

```python
from dataclasses import dataclass
from collections import deque
import time
import statistics


@dataclass
class DemandSnapshot:
    timestamp: float
    ingress_rps: float
    token_burn_rate: float
    in_flight_tools: int
    queue_age_p99_ms: float
    provider_429_rate: float


class DemandSensor:
    """Sliding-window aggregator with simple acceleration detection."""

    def __init__(self, window_seconds: int = 300):
        self.window = window_seconds
        self.samples: deque[DemandSnapshot] = deque()

    def ingest(self, snap: DemandSnapshot) -> None:
        self.samples.append(snap)
        cutoff = time.time() - self.window
        while self.samples and self.samples[0].timestamp < cutoff:
            self.samples.popleft()

    def ingress_acceleration(self) -> float:
        """Ratio of recent 60s RPS to prior 60s RPS."""
        if len(self.samples) < 10:
            return 1.0
        mid = len(self.samples) // 2
        recent = [s.ingress_rps for s in list(self.samples)[mid:]]
        prior = [s.ingress_rps for s in list(self.samples)[:mid]]
        if not prior or statistics.mean(prior) == 0:
            return 1.0
        return statistics.mean(recent) / statistics.mean(prior)

    def forecast_stress(self) -> str:
        accel = self.ingress_acceleration()
        latest = self.samples[-1] if self.samples else None
        if not latest:
            return "normal"

        if latest.provider_429_rate > 0.05 or latest.queue_age_p99_ms > 5000:
            return "critical"
        if accel > 1.8 or latest.token_burn_rate > self._token_ceiling * 0.85:
            return "elevated"
        if accel > 1.3:
            return "watch"
        return "normal"

    @property
    def _token_ceiling(self) -> float:
        return 500_000  # tokens/min quota — inject from config
```

Emit snapshots to Prometheus every 10–15 seconds. Downsample for long-term storage; keep raw granularity for alerting.

## Actuation policies

Sensing without action is a dashboard exercise. Tie forecasts to automated responses:

**Scale-out triggers**

- `elevated` for 2 consecutive minutes → add worker replicas (+25%)
- `critical` → add replicas (+50%), enable overflow queue, page on-call

**Model routing**

- `elevated` → route non-premium tenants to smaller/faster model tier
- `critical` → disable expensive tools (visual search, long-context RAG) via feature flag

**Rate limiting**

- Dynamic token bucket per tenant based on global `token_burn_rate`
- Graceful degradation messages before hard 429

```yaml
# demand-policy.yaml
tiers:
  premium:
    min_model: claude-sonnet
    max_tools_per_turn: 10
  standard:
    min_model: claude-haiku
    max_tools_per_turn: 5

actuation:
  elevated:
    - action: scale_workers
      factor: 1.25
    - action: downgrade_tier
      from: standard
      model: gpt-4o-mini
  critical:
    - action: scale_workers
      factor: 1.50
    - action: disable_tool
      tools: [visual_search, long_rag]
    - action: page
      team: agent-platform
```

## Forecasting beyond heuristics

Simple acceleration detection catches sudden spikes. Add lightweight forecasting for planned events:

- **Calendar features** — marketing sends, payroll chatbot crons, month-end reporting agents
- **ARIMA or Prophet** on hourly token burn for 24-hour horizon (batch pre-scaling)
- **Synthetic load profiles** — replay sanitized production traces at 2× before known events

Do not over-invest in ML forecasting before basic signals work. A rolling p95 TTFT alert outperforms a bad LSTM.

## Cost-aware demand sensing

Token burn is dollars. Track `cost_rate_usd_per_min` alongside latency. When forecast shows quota exhaustion in 20 minutes at current burn:

1. Shed lowest-priority batch workloads
2. Increase cache TTL on retrieval (stale-but-fast)
3. Notify finance dashboard—not just engineering

```python
def should_shed_batch(snapshot: DemandSnapshot, forecast_minutes: float) -> bool:
    headroom = snapshot.token_ceiling - snapshot.token_burn_rate
    if headroom <= 0:
        return True
    minutes_remaining = headroom / max(snapshot.token_burn_rate, 1)
    return minutes_remaining < forecast_minutes
```

## Observability and SLOs

Define demand-sensing SLOs themselves:

- Sensor lag < 30 seconds (event to metric)
- Actuation latency < 90 seconds (metric to scale decision)
- False scale rate < 2 per day (avoid flapping)

Dashboard panels: ingress RPS, acceleration ratio, token burn vs ceiling, in-flight tools, model 429 rate, actuation log (what fired, when).

## Testing

- **Load replay** — production trace at 3× in staging; verify actuation fires
- **Chaos** — artificially cap provider quota; confirm routing downgrade
- **Game day** — disable autoscaling; verify manual runbook from demand dashboard

## Multi-region and multi-provider sensing

Agent platforms rarely depend on a single model region. Demand sensing must aggregate across:

- **Provider shards** — OpenAI us-east vs Azure OpenAI west Europe; 429 on one shard should trigger routing shift before global SLO burn.
- **Regional ingress** — EU traffic spike may not appear in US-only dashboards; fuse metrics with `region` label.
- **Embedding vs completion pools** — retrieval spikes can saturate vector DB before LLM quotas blink.

Use a global demand controller that reads regional snapshots every 30 seconds and publishes a `global_stress_level` enum consumed by routing services. Avoid split-brain: one controller cluster with leader election, not per-region silos making conflicting scale decisions.

```yaml
# regional-fusion example
regions:
  us-east-1:
    weight: 0.45
    stress: elevated
  eu-west-1:
    weight: 0.35
    stress: normal
  ap-southeast-1:
    weight: 0.20
    stress: watch

global_action:
  stress: elevated  # weighted max
  route_new_sessions:
    premium: us-east-1
    standard: eu-west-1  # cheaper haiku pool with headroom
```

## Tenant-level fairness under stress

Global scale-up may be insufficient if one tenant runs a batch job consuming 40% of token budget. Layer **tenant demand caps** on top of global sensing:

- Track `token_burn_rate` by `tenant_id`
- When global stress is `elevated`, throttle tenants above p95 historical share
- Notify tenant admins via webhook before hard throttle—product trust matters

Fairness prevents noisy-neighbor batch agents from degrading interactive sessions for everyone else.

## Closing the loop with post-incident review

After every latency or 429 incident, compare demand sensor timeline to human actions:

- Did `elevated` fire before or after user complaints?
- Did actuation run but prove insufficient (under-provisioned)?
- Did false `watch` alerts cause unnecessary scale cost?

Tune thresholds from evidence, not intuition. Store incident retrospectives linked to dashboard snapshots at decision timestamps.

## The takeaway

Real-time demand sensing for agents measures what actually stresses the system: tokens, tools, and queues—not container CPU. Aggregate sub-minute signals, detect acceleration early, and actuate scaling and routing with tier-aware policies. Black Friday's surprise was not traffic volume—it was fan-out per session. Build sensors that see inside the conversation, not just at the load balancer.

## Resources

- [Kubernetes HPA — custom metrics](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [KEDA — event-driven autoscaling](https://keda.sh/)
- [AWS Predictive Scaling](https://docs.aws.amazon.com/autoscaling/ec2/userguide/ec2-auto-scaling-predictive-scaling.html)
- [Google Cloud Autoscaling agent workloads](https://cloud.google.com/architecture/best-practices-for-running-ai-ml-on-gke)
- [Companion: Adaptive Throttling Under Load](/agent-adaptive-throttling-load/)
- [Companion: Token Budget Compression](/agent-token-budget-compression/)
