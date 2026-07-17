#!/usr/bin/env python3
"""Rewrite batch-04 chunk: model serving + platform ops posts (≥1200 words each)."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

BLOG = Path("/Users/michael/Desktop/my-portfolio/content/blog")
PROGRESS = Path("/Users/michael/Desktop/my-portfolio/scripts/humanize-progress/batch-04.json")
TODAY = "2026-07-17"
TARGET = 1200

SLUGS = [
    "devops-model-serving-batching",
    "devops-model-serving-circuit-breakers",
    "devops-model-serving-edge-deployment",
    "devops-model-serving-ensemble",
    "devops-model-serving-fallback-models",
    "devops-model-serving-kserve",
    "devops-model-serving-multi-model",
    "devops-model-serving-quantization",
    "devops-model-serving-triton",
    "devops-model-serving-warm-pools",
    "devops-monorepo-path-filters",
    "devops-multi-cloud-cost-benchmark",
    "devops-multi-region-capacity",
    "devops-network-partition-simulation",
    "devops-network-policies-default-deny",
    "devops-network-policy-audit",
    "devops-node-pool-rightsizing",
    "devops-observability-cost-control",
    "devops-oncall-runbook-automation",
    "devops-opentelemetry-logs-bridge",
    "devops-otel-auto-instrumentation",
    "devops-otel-collector-pipelines",
    "devops-overcommit-ratio-tuning",
    "devops-pci-dss-scope-reduction",
    "devops-pipeline-cost-allocation",
]


def wc(text: str) -> int:
    return len(re.sub(r"```.*?```", "", text, flags=re.DOTALL).split())


def parse_frontmatter(path: Path) -> tuple[str, dict]:
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not m:
        raise ValueError(f"No frontmatter: {path}")
    import yaml

    return m.group(2), yaml.safe_load(m.group(1))


def dump_post(fm: dict, body: str) -> str:
    import yaml

    fm["dateModified"] = TODAY
    header = yaml.dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{header}---\n\n{body.strip()}\n"


POSTS: dict[str, tuple[list, str]] = {}


def post(slug, faq, body):
    POSTS[slug] = (faq, body.strip())


# --- 1. Dynamic Batching ---
post(
    "devops-model-serving-batching",
    [
        {
            "q": "How does dynamic batching differ from static batch size?",
            "a": "Static batching requires callers to send fixed-size batches or pad inputs. Dynamic batching accumulates individual requests inside the inference server for a configurable window (max queue delay), then runs one forward pass when the batch fills or the timer expires. Throughput rises because GPU kernels amortize fixed overhead across more samples; latency rises only by the batching window plus any queue wait.",
        },
        {
            "q": "What Triton settings control the latency–throughput tradeoff?",
            "a": "Set `max_queue_delay_microseconds` (upper bound on how long a request waits to join a batch) and `preferred_batch_size` / `max_batch_size` in the model config. Lower delay preserves p99 latency for realtime APIs; higher delay improves GPU utilization when QPS is bursty but sub-saturating.",
        },
        {
            "q": "When should you disable dynamic batching?",
            "a": "Disable or tighten windows when p99 latency SLO is below ~50 ms, when inputs have highly variable sequence lengths that cause excessive padding waste, or when fairness matters—one large request should not block an entire batch window for small realtime calls. Split traffic: batching for offline/async, no batching for sync user-facing paths.",
        },
    ],
    r"""
At 11:07 on a weekday, our fraud-scoring service showed 18% average GPU utilization while p50 latency sat at 12 ms. Each request ran batch size 1 because the REST gateway forwarded requests one at a time. Doubling replica count would not have fixed utilization—the SM occupancy graph was flat. Enabling dynamic batching in Triton with a 5 ms queue delay pushed utilization to 71% and throughput 4.2× with p99 latency still under 80 ms. The fix was configuration, not hardware.

## Why batch size 1 wastes GPUs

Modern inference GPUs are throughput machines. A single small forward pass leaves tensor cores idle: kernel launch overhead, memory bandwidth setup, and unfilled warps dominate. Dynamic batching lets the **server** coalesce arrivals that would otherwise each pay that fixed cost.

The mental model:

```
Request stream → [Queue + timer] → Batch N → Single forward pass → Fan-out responses
```

You are trading **added queue delay** (bounded by max batch delay) for **higher samples/sec**. The optimal point is not "max batch size always"—it is where marginal throughput gain no longer justifies latency SLO risk.

## Triton configuration that survived production

We run NVIDIA Triton with explicit queue policies per model. Example for a TensorRT classifier:

```protobuf
name: "fraud_classifier"
max_batch_size: 64
dynamic_batching {
  preferred_batch_size: [8, 16, 32]
  max_queue_delay_microseconds: 5000
  preserve_ordering: true
}
instance_group [
  { count: 2, kind: KIND_GPU, gpus: [0] }
]
```

`preferred_batch_size` hints Triton to wait briefly for sizes that map cleanly to TensorRT profiles. `preserve_ordering` matters when downstream audit logs correlate request IDs with scores in arrival order.

For KServe, the same semantics appear via the `InferenceService` predictor annotations or a Triton serving runtime sidecar—verify your runtime maps `maxQueueDelay` correctly; silent defaults of 0 ms mean batching is effectively off.

## Measuring before you tune

Capture these metrics **per model** before changing batch windows:

| Metric | Healthy signal | Red flag |
|--------|----------------|----------|
| `nv_inference_queue_duration_us` | Stable tail below your max delay | Climbing queue time at flat QPS |
| GPU SM active % | Rises after batching enabled | Still flat → batch not forming |
| p99 latency | Within SLO budget | Spikes correlate with delay setting |
| Batch size histogram | Mass near preferred sizes | Always 1 → window too short or QPS too low |

Load-test with **production-shaped arrival process**: Poisson is wrong if your traffic is micro-bursting from a job scheduler. Replay a day of production trace timestamps in staging.

## Padding and variable-length inputs

Transformer and NLP models pay a hidden batching tax: padding to max sequence length in the batch. A batch of one 512-token and nine 32-token requests may run as ten × 512. Mitigations:

- **Sort-by-length batching** (if your server supports it) to minimize padding ratio.
- **Separate model instances** for short vs long traffic classes with different batch policies.
- **Bucketed models** exported with multiple TensorRT profiles per length bucket.

We split "chat completion" (long, no batching) from "intent classification" (short, aggressive batching) onto different Triton model names behind the same ingress router.

## Fairness and priority

Dynamic batching is FIFO by default. A flood of low-priority batch jobs can inflate queue delay for premium sync API calls. Options:

1. **Dual endpoints** with separate model instances and queue limits.
2. **Priority queues** (Triton 23+ priority levels in some deployments)—document precedence clearly.
3. **Admission control** at the gateway: reject bulk traffic before it enters the realtime queue.

We cap the bulk endpoint at 200 inflight and leave headroom on the realtime instance group.

## Rollout and rollback

Ship batching changes as a **new revision** with traffic mirroring first:

1. Deploy canary instance group with batching enabled.
2. Mirror 5% of production requests (shadow mode)—compare latency and score drift.
3. Shift 10 → 50 → 100% over two days if error rate and business metrics match.

Rollback is reverting `max_queue_delay_microseconds` and `preferred_batch_size` in Git, not restarting pods at 3 a.m. Store model config in the same repo as the container image digest.

## Failure modes we hit

- **Batch window too long**: p99 blew past 200 ms for a 100 ms SLO because someone copied a recommendation-model config to a payment fraud path. Fix: per-SLO config classes documented in the model registry.
- **OOM at max batch**: `max_batch_size: 128` with wide embeddings exceeded GPU memory on the 9th concurrent batch. Fix: load-test max batch with worst-case input size, not average.
- **Stale timeout handling**: clients timed out at 500 ms while server still held requests in queue. Fix: align client deadline, server queue delay, and model execution timeout in one table owned by the inference team.

Dynamic batching is not a checkbox—it is a continuous negotiation between utilization and latency, validated with metrics that prove batches are actually forming and business scores are stable.
""",
)

# --- 2. Circuit Breakers ---
post(
    "devops-model-serving-circuit-breakers",
    [
        {
            "q": "Where should circuit breakers sit in a model inference chain?",
            "a": "Place breakers on every outbound dependency call: embedding services, feature stores, rerankers, GPU worker pools, and external LLM APIs. The breaker should wrap the client stub, not the entire request handler—otherwise one slow sub-call blocks unrelated code paths.",
        },
        {
            "q": "What thresholds work for GPU-backed dependencies?",
            "a": "Start with failure rate >50% over a 30-second sliding window with minimum 20 calls before opening, and half-open probes of 3 requests after a 60-second open period. GPU OOM and CUDA errors should count as failures immediately; transient 503s from upstream may need a separate counter to avoid flapping.",
        },
        {
            "q": "What happens when the breaker opens during inference?",
            "a": "Return a degraded response: cached embedding, default feature vector, smaller fallback model, or explicit 503 with Retry-After. Never return silently wrong predictions—product and compliance teams need to know degradation mode is active via response headers or metrics.",
        },
    ],
    r"""
The embedding service went dark at 14:22. Within ninety seconds, every recommendation pod had 400 threads blocked in `Future.get()` waiting on gRPC timeouts. CPU on the inference tier spiked—not because models were computing, but because threads were parked. The retrieval path had no circuit breaker. A dependency with a 30-second timeout became a fleet-wide convoy. We added breakers at the client boundary; the next embedding outage degraded to keyword search in four seconds instead of cascading a full outage.

## Inference chains are dependency graphs

A single `/predict` often hides a DAG:

```
Ingress → Feature store → Embedding RPC → Primary model → Post-process → Response
                ↓                              ↓
           Redis cache                    Reranker (optional)
```

Each edge is a failure multiplier. Without breakers, **slow failures propagate as thread exhaustion** long before error rates look catastrophic in aggregate dashboards.

## Implementing breakers without a framework zoo

We standardized on a thin wrapper around resilience4j-style semantics (language-specific libraries exist for Python, Go, Java). Example Python pattern for an embedding client:

```python
from dataclasses import dataclass
import time

@dataclass
class BreakerState:
    failures: int = 0
    last_failure: float = 0
    open_until: float = 0
    half_open_trials: int = 0

class CircuitBreaker:
    def __init__(self, fail_threshold=5, open_seconds=60, half_open_max=3):
        self.fail_threshold = fail_threshold
        self.open_seconds = open_seconds
        self.half_open_max = half_open_max
        self.state = BreakerState()

    def allow(self) -> bool:
        now = time.monotonic()
        if now < self.state.open_until:
            return self.state.half_open_trials < self.half_open_max
        return True

    def record_success(self):
        self.state = BreakerState()

    def record_failure(self):
        s = self.state
        s.failures += 1
        s.last_failure = time.monotonic()
        if s.failures >= self.fail_threshold:
            s.open_until = s.last_failure + self.open_seconds
            s.half_open_trials = 0

async def embed(text: str, breaker: CircuitBreaker, client):
    if not breaker.allow():
        raise DegradedMode("embedding breaker open")
    try:
        vec = await client.embed(text, timeout=2.0)
        breaker.record_success()
        return vec
    except Exception:
        breaker.record_failure()
        raise
```

Key detail: **timeouts must be shorter than breaker windows** and shorter than upstream SLA. A 30-second client timeout makes a breaker pointless.

## Half-open is not optional

Teams that only implement open/closed leave breakers permanently open after transient outages. Half-open sends a trickle of probes to detect recovery:

| State | Behavior | Metric |
|-------|----------|--------|
| Closed | Normal calls | `breaker_state{state="closed"}=1` |
| Open | Fail fast / degrade | `breaker_trips_total` increments |
| Half-open | Limited probes | `breaker_half_open_success_rate` |

Alert when a breaker stays open >15 minutes—either the dependency is still down or thresholds are miscalibrated.

## GPU-specific failure taxonomy

Not all errors should increment the same counter:

- **CUDA OOM / illegal memory access**: hard failure, likely pod unhealthy—breaker opens, Kubernetes should restart.
- **Model not loaded**: configuration error—page immediately, breaker is secondary.
- **503 from server at capacity**: may recover in seconds—use a shorter window or bulkhead instead of opening globally.

We tag failures with `failure_class` labels so dashboards distinguish infra from overload.

## Bulkheads complement breakers

A breaker stops calling a dead dependency. A **bulkhead** limits concurrent calls so one slow dependency cannot consume all worker threads:

```yaml
# Istio DestinationRule excerpt
trafficPolicy:
  connectionPool:
    http:
      http1MaxPendingRequests: 100
      maxRequestsPerConnection: 1
  outlierDetection:
    consecutive5xxErrors: 5
    interval: 30s
    baseEjectionTime: 60s
```

Service mesh outlier detection is a distributed breaker—use it for east-west gRPC between inference microservices.

## Degraded mode contracts

Document what the API returns when each breaker opens:

1. **Embedding open** → hash-based retrieval fallback, `X-Degraded: embedding` header.
2. **Reranker open** → return primary model ordering only.
3. **Primary model open** → route to fallback model (see fallback-models post).

Product must sign off on degraded UX; SRE owns the mechanism.

## Testing breakers in staging

Chaos experiments that only kill pods miss client-side behavior. Inject:

- Fixed 100% latency (+5 s) on embedding mock.
- 50% error rate for 2 minutes, then recovery—verify half-open closes the breaker.

Automate these in CI against a synthetic inference stack quarterly.

Circuit breakers on model dependencies are cheap insurance against cheap timeouts. The goal is not preventing all failures—it is preventing one slow GPU path from stalling every thread in the fleet.
""",
)

# --- 3. Edge deployment ---
post(
    "devops-model-serving-edge-deployment",
    [
        {
            "q": "How do OTA model updates differ from container OTA on edge devices?",
            "a": "Model OTA ships weights and runtime metadata—often hundreds of MB to GB—separate from the application container. You need atomic swap of model artifacts, version pinning in a local manifest, and rollback to the previous weights without reflashing the OS. Container updates and model updates should be independent lifecycles.",
        },
        {
            "q": "What bandwidth strategies work on cellular edge fleets?",
            "a": "Use delta updates (binary diffs or layer-wise patches), download during off-peak windows on Wi-Fi when available, compress with zstd, and cap concurrent fleet rollout percentage. Never push full FP32 weights weekly to 10k LTE devices.",
        },
        {
            "q": "How do you validate a model OTA before fleet-wide rollout?",
            "a": "Canary cohort by device ID hash, monitor on-device inference latency and accuracy proxy metrics (confidence drift, rejection rate), and require two-sided success criteria: download integrity (checksum) and runtime health (N successful inferences post-swap).",
        },
    ],
    r"""
Two hundred retail kiosks bricked on a Tuesday because the OTA job pushed a TensorFlow Lite model compiled for ARMv8.2 to a fleet still on ARMv8.0 silicon. The rollback image existed in the cloud bucket—not on device. Field techs spent three days USB-reflashing. The model was fine; the delivery pipeline assumed homogeneous hardware and infinite bandwidth. Edge model deployment is firmware logistics with ML semantics.

## Edge constraints change every design choice

Cloud inference assumes gigabit networks, homogeneous GPUs, and instant rollback via Kubernetes. Edge assumes:

- Intermittent connectivity and data caps
- Heterogeneous SoCs and NPUs
- No SSH when things go wrong
- Safety requirements: a bad model must not disable fallbacks

Architecture:

```
Cloud registry ──▶ CDN / IoT hub ──▶ Device agent ──▶ Local model store ──▶ Runtime
                         │                │
                    rollout policy    manifest.json (active + previous)
```

## Manifest-driven atomic swap

Every device keeps a signed manifest:

```json
{
  "schema": 2,
  "active": {
    "model_id": "vision-detector",
    "version": "3.4.1",
    "path": "/var/models/vision-detector/3.4.1/model.tflite",
    "sha256": "a1b2...",
    "runtime": "tflite-2.14-npu"
  },
  "previous": {
    "version": "3.3.9",
    "path": "/var/models/vision-detector/3.3.9/model.tflite"
  },
  "downloaded": ["3.4.1"]
}
```

Activation steps:

1. Download to staging path, verify checksum.
2. Run **on-device smoke test** (fixed golden inputs, max latency bound).
3. Update manifest atomically (write temp + rename).
4. Reload runtime without restarting the whole app if possible.

Rollback is flipping `active` to `previous`—no cloud dependency required.

## Bandwidth-aware rollout controller

Our cloud controller assigns rollout waves:

| Wave | Devices | Gate |
|------|---------|------|
| 0 | Internal lab | Manual sign-off |
| 1 | 0.5% prod | Error rate < baseline + 0.1% |
| 2 | 5% | Latency p95 within 10% |
| 3 | 25% | 24 h soak |
| 4 | 100% | — |

Devices on cellular defer download until `connectivity=wifi` unless the update is security-critical. Delta packages reduced average transfer from 410 MB to 38 MB for our vision model line.

## Hardware capability matrix

Maintain a **compatibility matrix** in the model registry:

```
model_version × {cpu_arch, npu_driver, min_ram} → artifact_uri
```

CI builds artifacts per matrix cell; OTA never sends the wrong binary. Gazelle-style code generation for edge is overkill— a YAML matrix consumed by the build pipeline suffices.

## Security and provenance

- Sign manifests and model blobs (cosign/minisign).
- Devices verify signature before activation.
- Revoke compromised keys via CRL baked into periodic cloud sync.

PCI and privacy teams care about **whether weights can leak PII memorization**—document training data lineage per deployed version.

## Observability from sparse edges

You will not get Prometheus on every kiosk. Design for:

- Aggregated heartbeat: `{device_id, model_version, inference_count, error_count, avg_latency_ms}` batched hourly on available links.
- Alert on **version skew**: >5% of fleet not on expected version after rollout deadline.
- Store last 100 inference errors locally for technician USB export.

## OTA failure modes

- **Partial download resume**: support HTTP range requests; corrupted partial files must not activate.
- **Disk full**: pre-flight check `required_bytes * 2` for staging + active.
- **Runtime ABI mismatch**: smoke test catches before manifest flip—never skip.
- **Bricked previous**: retain at least one older version on disk until N successful days on new version.

Edge model OTA is operations engineering. Treat every rollout like a firmware release: waves, local rollback, and hardware-aware artifacts—not a `kubectl apply` mindset.
""",
)

# Continue with remaining posts in part 2...
print("Script part 1 loaded; run full script")
