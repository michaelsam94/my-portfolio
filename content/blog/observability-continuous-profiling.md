---
title: "Continuous Profiling in Production"
slug: "observability-continuous-profiling"
description: "Deploy continuous profiling in production with Pyroscope, Parca, and eBPF: flame graphs, overhead control, and turning profiles into performance fixes."
datePublished: "2025-09-30"
dateModified: "2026-07-17"
tags: ["DevOps", "Observability", "Performance", "Backend"]
keywords: "continuous profiling, production profiling, flame graphs, Pyroscope, Parca profiling, eBPF profiling, CPU profiling production"
faq:
  - q: "What is the performance overhead of continuous profiling?"
    a: "Modern eBPF-based profilers (Parca, Pyroscope with eBPF) add 1–5% CPU overhead at default sampling rates (100 Hz). This is acceptable for most production workloads. Legacy instrumentation-based profilers can add 10–20% and should use lower sampling rates or profile subsets of instances."
  - q: "How is continuous profiling different from ad-hoc profiling?"
    a: "Ad-hoc profiling captures a snapshot when you manually trigger it—often after the performance problem has passed. Continuous profiling samples 24/7 and stores time-series profile data, letting you compare CPU usage before and after a deployment or during a latency spike hours ago."
  - q: "Which languages support production profiling?"
    a: "eBPF profilers work for any compiled language (Go, Rust, C++, Java) and natively compiled Python. Node.js and Ruby need runtime-specific agents. JVM profiling works via async-profiler or eBPF with frame pointer support."
---

A deploy increased P99 latency from 200 ms to 800 ms. You SSH in, run `perf record`, capture 30 seconds of data, and find nothing—the spike happened four hours ago during peak traffic. Continuous profiling solves this by sampling stack traces every 10–100 milliseconds around the clock, storing them as time-series data. When latency spikes, you open a flame graph from that exact time window and see which function grew.

## How continuous profiling works

```
Application process
  ↓ (every 10ms)
Sampler collects stack trace → Label with pod, version, region
  ↓
Compress and ship to profile store (Pyroscope, Parca, Datadog)
  ↓
Query by time range + labels → Render flame graph
```

eBPF profilers attach at the kernel level—no code changes, no agent per language. They read stack frames from `/proc` or DWARF debug info.

## Pyroscope setup

```yaml
# docker-compose.yml
services:
  pyroscope:
    image: grafana/pyroscope:latest
    ports:
      - "4040:4040"
    volumes:
      - pyroscope-data:/var/lib/pyroscope

  app:
    image: my-app:latest
    environment:
      PYROSCOPE_SERVER_ADDRESS: http://pyroscope:4040
      PYROSCOPE_APPLICATION_NAME: my-app
```

**Go integration:**

```go
import "github.com/grafana/pyroscope-go"

pyroscope.Start(pyroscope.Config{
    ApplicationName: "my-app",
    ServerAddress:   os.Getenv("PYROSCOPE_SERVER_ADDRESS"),
    Tags: map[string]string{
        "hostname": os.Getenv("HOSTNAME"),
        "version":  os.Getenv("APP_VERSION"),
    },
    ProfileTypes: []pyroscope.ProfileType{
        pyroscope.ProfileCPU,
        pyroscope.ProfileAllocObjects,
        pyroscope.ProfileInuseSpace,
    },
})
```

**Python integration:**

```python
import pyroscope

pyroscope.configure(
    application_name="my-app",
    server_address="http://pyroscope:4040",
    tags={"region": "us-east-1", "version": "1.2.3"},
)
```

## Reading flame graphs

```
┌──────────────────────────────────────────────────────────┐
│                      main()                               │  ← root
├──────────────────────┬───────────────────────────────────┤
│   handle_request()   │         startup()                 │
├──────────┬───────────┤                                   │
│ db_query │ json_parse│                                   │
│  (45%)   │   (30%)   │                                   │
└──────────┴───────────┴───────────────────────────────────┘
```

- **Width** = proportion of samples (CPU time or memory).
- **Y-axis** = call stack depth (bottom = entry point).
- **Look for wide plateaus** — functions consuming disproportionate time.
- **Compare profiles** — diff flame graphs before/after a deploy.

## Parca with Kubernetes

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: parca-agent
spec:
  template:
    spec:
      containers:
        - name: parca-agent
          image: ghcr.io/parca-dev/parca-agent:v0.30.0
          args:
            - --remote-store-address=parca.parca.svc:7070
            - --node=$(NODE_NAME)
          securityContext:
            privileged: true  # required for eBPF
```

Parca runs as a DaemonSet—one agent per node profiles all pods on that node.

## Turning profiles into fixes

**Scenario:** CPU spike after deploy.

1. Open Pyroscope, filter `version=1.2.3`, time range = spike window.
2. Flame graph shows `json.Marshal` at 35% (was 5% in `version=1.2.2`).
3. Git diff shows new code serializing a 50 MB struct on every request.
4. Fix: serialize only required fields. CPU returns to baseline.

**Scenario:** Memory leak over 48 hours.

1. Query `inuse_space` profile type, compare hour 1 vs hour 48.
2. `cache.Store` grows from 2% to 40% of heap.
3. Cache has no TTL—entries accumulate.
4. Fix: add LRU eviction with 1-hour TTL.

## Overhead management

| Strategy | Overhead | Coverage |
|----------|----------|----------|
| eBPF 100 Hz on all pods | 1–3% | 100% |
| Agent on 20% of pods | <1% effective | Statistical |
| Profile only on canary | ~0% on main | Canary only |
| On-demand trigger | 0% until triggered | Point-in-time |

Start with eBPF profiling on 100% of instances at 100 Hz. Reduce sampling rate to 20 Hz if overhead exceeds 5%.

## Integrating with traces

Grafana pairs profiles with traces via exemplars:

```
Trace span (slow request) → "View profile at this timestamp" → Flame graph
```

This connects "this request was slow" to "this function was hot during that request."

## Pyroscope and Parca setup

Deploy continuous profiling alongside existing observability stack:

```yaml
# docker-compose addition
pyroscope:
  image: grafana/pyroscope:latest
  ports: ["4040:4040"]
  volumes: ["pyroscope-data:/data"]

# Application config (Go example)
import "github.com/grafana/pyroscope-go"

pyroscope.Start(pyroscope.Config{
    ApplicationName: "api-server",
    ServerAddress:   "http://pyroscope:4040",
    ProfileTypes:    []pyroscope.ProfileType{
        pyroscope.ProfileCPU,
        pyroscope.ProfileAllocObjects,
        pyroscope.ProfileInuseObjects,
    },
})
```

Zero instrumentation code for supported languages — agent samples automatically. Query by service, pod, and time range in Grafana.

## Reading flame graphs

Flame graph interpretation for production debugging:

```
Width  = time spent in function (wider = more CPU)
Height = call stack depth (bottom = entry point, top = leaf)
Color  = package/namespace (usually random, ignore color)
```

Look for:
- **Wide plateau at top** — hot leaf function; optimization target
- **Wide bar mid-stack** — caller spending time in one callee
- **Unexpected library frames** — JSON serialization, regex, logging in hot path
- **Growing over time** — memory leak (inuse_space growing across profiles)

Compare profiles before and after deploy to catch performance regressions.

## Profile types and when to use each

| Profile type | Shows | Use for |
|---|---|---|
| CPU | On-CPU time per function | Hot path optimization |
| inuse_space | Currently allocated memory | Memory leak detection |
| alloc_space | Total allocations (GC pressure) | Allocation-heavy code paths |
| goroutines / threads | Concurrent execution | Concurrency bottlenecks |
| mutex / block | Lock contention | Deadlock and contention |

Run CPU profiling continuously. Trigger inuse_space profiling when heap metrics trend upward.

## Failure modes

- **Profiling only on demand** — miss intermittent spikes; profile continuously
- **100% sampling on all pods** — >5% overhead; reduce to 20Hz if needed
- **Profiles not linked to traces** — can't connect slow request to hot function
- **Flame graph misread** — optimize leaf function when caller is the real issue
- **No baseline profile** — can't detect regression after deploy

## Production checklist

- Continuous profiling deployed (Pyroscope, Parca, or Datadog Profiler)
- CPU profiling at 100Hz on all production instances
- Profiles linked to trace exemplars in Grafana
- Baseline profile captured before each major deploy
- Alert on inuse_space growth trend (>10% over 24 hours)
- Flame graph review in post-incident process for latency incidents

Profile production at 1–5% sample rate continuously — episodic profiling during incidents captures the wrong code path because traffic patterns differ under stress.

## Pairing profiles with LLM gateways

Inference gateways spend CPU on JSON parsing, tokenizer calls, and streaming flushes — not model matmul. Continuous profiling reveals when “slow LLM” is actually slow middleware. Compare flame graphs between canary and baseline deploys when p95 shifts without GPU utilization changes.

## Storage profiling for JVM and Node

Heap profiles complement CPU: LLM gateways buffering streaming responses may show allocation hotspots invisible in CPU-only views. Schedule weekly automated profile diff jobs in CI against a recorded baseline — regressions in `JSON.parse` or gzip middleware show up before customers notice.

## Flame graph reading for on-call

Train on-call to read icicle charts top-down:

1. **Width** — percentage of samples in that frame
2. **Self vs total** — hover for self time vs cumulative child time
3. **Plateau** — wide flat frames are optimization targets

Runbook snippet: "If `runtime.systemstack` or `syscall` dominates, suspect IO not CPU—switch to trace and pool metrics before optimizing Go code."

## Allocation profiling for GC pressure

CPU profiles miss services spending 40% in GC because allocations are hot. Enable alloc profiling on canary when:

- `go_gc_duration_seconds` spikes correlate with latency
- JVM `jvm.gc.pause` alerts fire without CPU saturation

Parca/Pyroscope heap profiles show `make([]byte)` or JSON marshal paths—fix allocation before tuning `GOGC`.

## Profiling multi-tenant SaaS

Noisy neighbor tenants may dominate profiles without attribution. Label profiles with `tenant_tier` not `tenant_id`—sample pod metadata at scrape time. Enterprise tier latency incident → filter profiles to pods handling enterprise traffic via deployment shard labels.

## Relationship to eBPF network observability

Profiles show CPU in HTTP handler; eBPF flows show retransmit storms. Combined timeline: network packet loss spike → retry loop in handler → CPU profile shows `io.ReadAll` hot. Use both pillars before blaming application algorithm.

## Vendor vs self-hosted decision matrix

| Factor | Self-hosted Parca/Pyroscope | Datadog CP |
|--------|----------------------------|------------|
| Ops burden | You run object storage + agents | Vendor |
| Data residency | Full control | Vendor region |
| Trace correlation | DIY Tempo linking | Integrated APM |
| Cost at 500 pods | Infra + eng time | Per-host fee |

Document decision in ADR when adopting continuous profiling—revisit when pod count 10×.

## Resources

- [Grafana Pyroscope documentation](https://grafana.com/docs/pyroscope/latest/) — setup and query guide
- [Parca GitHub](https://github.com/parca-dev/parca) — open-source continuous profiling
- [Brendan Gregg's flame graph guide](https://www.brendangregg.com/flamegraphs.html) — how to read flame graphs
- [eBPF profiling fundamentals](https://www.brendangregg.com/ebpf.html) — kernel-level sampling
- [async-profiler for JVM](https://github.com/async-profiler/async-profiler) — low-overhead Java profiling
