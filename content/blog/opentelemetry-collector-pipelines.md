---
title: "OpenTelemetry Collector Pipelines in Practice"
slug: "opentelemetry-collector-pipelines"
description: "A practical guide to OpenTelemetry Collector pipelines: receivers, processors, exporters, plus batching, tail sampling, and a topology that scales."
datePublished: "2026-02-15"
dateModified: "2026-07-17"
tags: ["Observability", "DevOps", "OpenTelemetry"]
keywords: "OpenTelemetry Collector, otel pipelines, receivers processors exporters, tail sampling, telemetry pipeline"
faq:
  - q: "What is the OpenTelemetry Collector?"
    a: "The OpenTelemetry Collector is a vendor-neutral service that receives, processes, and exports telemetry — traces, metrics, and logs. It sits between your applications and your observability backends, decoupling instrumentation from destination so you can change vendors, add processing, or fan out to multiple systems without touching application code. A Collector runs configurable pipelines, each made of receivers that ingest data, processors that transform it, and exporters that send it onward."
  - q: "What are receivers, processors, and exporters?"
    a: "They are the three component types that make up a Collector pipeline. Receivers ingest telemetry into the Collector, for example the OTLP receiver accepting data over gRPC or HTTP. Processors transform data in flight — batching, filtering, adding attributes, or sampling. Exporters send the processed telemetry to one or more backends such as Prometheus, Jaeger, or a commercial APM. A pipeline is a named chain wiring specific receivers to processors to exporters for one signal type."
  - q: "What is tail-based sampling and why use the Collector for it?"
    a: "Tail-based sampling decides whether to keep a trace after all its spans have arrived, so the decision can consider the whole trace — keep it if it errored, was slow, or hit a rare code path. This requires buffering all spans of a trace in one place, which the Collector's tailsampling processor does. It's far more useful than head sampling (deciding at the start) because you keep the interesting traces and drop the boring ones, controlling cost without losing signal."
---

The OpenTelemetry Collector is the piece of observability infrastructure I now install before anything else, because it does one thing that pays off forever: it decouples your instrumentation from your backend. Applications emit telemetry in one standard format (OTLP); the Collector receives it, processes it, and exports it to whatever backend you use today — and to a different one tomorrow, without redeploying a single service. Each Collector runs **pipelines** built from three component types: receivers that ingest data, processors that transform it, and exporters that ship it out.

I've migrated teams off a vendor mid-incident-season by changing four lines of Collector config instead of re-instrumenting forty services. That's the leverage this component gives you. Let me walk through how the pipelines actually fit together and the configuration that matters in production.

## The pipeline model

A Collector's behavior is entirely defined by its config, and the mental model is small. You declare components, then wire them into pipelines under `service`. A pipeline is scoped to one signal — traces, metrics, or logs — and names which receivers feed it, which processors run in order, and which exporters get the result.

```yaml
receivers:
  otlp:
    protocols:
      grpc:
      http:

processors:
  memory_limiter:
    check_interval: 1s
    limit_percentage: 80
  batch:
    timeout: 5s
    send_batch_size: 8192

exporters:
  otlphttp/backend:
    endpoint: https://otel.example.com

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [otlphttp/backend]
```

Two details in there are load-bearing. **Processor order matters** — they run top to bottom in the list, so `memory_limiter` first (to shed load before you do expensive work) then `batch` last (to group right before export) is deliberate, not cosmetic. And the same receiver can feed multiple pipelines while a pipeline can fan out to multiple exporters, which is how you send traces to Jaeger and a commercial APM simultaneously.

## Processors are where the value lives

Receivers and exporters are mostly plumbing; the intelligence is in the processors. The ones I configure on essentially every deployment:

- **`memory_limiter`** — the safety valve. Under a telemetry flood, an unbounded Collector will OOM and take your observability down exactly when you need it. This processor refuses data before that happens. Always first.
- **`batch`** — groups telemetry into fewer, larger export calls. This is not optional for cost and throughput; unbatched export hammers your backend and your egress bill. Always present, always last before export.
- **`resourcedetection`** / **`attributes`** — enrich spans with environment metadata (cloud region, k8s pod, service version) or scrub sensitive fields. Do PII redaction *here*, centrally, rather than trusting every service to do it.
- **`filter`** — drop telemetry you never want (health-check spans, noisy endpoints) before it costs you money downstream.

The discipline I push: **transform and reduce in the Collector, not in the app.** Keeping instrumentation dumb and moving policy into the Collector means changing sampling, redaction, or routing is a config rollout, not a fleet-wide redeploy. That separation is what makes an observability practice sustainable, and it ties directly into how you [design for observability and SLOs](https://blog.michaelsam94.com/designing-for-observability-slos/) — the Collector is where SLI-relevant signal gets shaped and preserved while noise gets dropped.

## Tail sampling: keep the interesting traces

The processor that most changes your cost/signal tradeoff is `tail_sampling`. Head-based sampling decides at a trace's *start* whether to keep it — before you know if it errored or was slow — so you either keep everything (expensive) or randomly drop, including the failures you most wanted. Tail sampling waits until all of a trace's spans have arrived, then decides based on the *whole* trace.

```yaml
processors:
  tail_sampling:
    decision_wait: 10s
    policies:
      - name: keep-errors
        type: status_code
        status_code: { status_codes: [ERROR] }
      - name: keep-slow
        type: latency
        latency: { threshold_ms: 500 }
      - name: sample-rest
        type: probabilistic
        probabilistic: { sampling_percentage: 5 }
```

This keeps 100% of errors, 100% of slow traces, and 5% of the boring successful ones — which is exactly the distribution you want. The catch is architectural: tail sampling requires *all spans of a trace to reach the same Collector instance*. That constraint dictates your topology, which is the next thing.

## Deployment topology: agent plus gateway

For anything beyond a toy, the pattern that scales is **two tiers**:

| Tier | Runs as | Job |
| --- | --- | --- |
| Agent | DaemonSet / sidecar per node | Receive local telemetry, add host/pod metadata, forward |
| Gateway | Horizontally-scaled deployment | Central processing, tail sampling, export to backends |

Agents sit close to the workloads, do cheap local enrichment, and forward to the gateway. The gateway tier does the expensive, stateful work — tail sampling, heavy aggregation, and export. Because tail sampling needs all of a trace's spans together, the gateway must route spans so that every span of a given trace lands on the same instance; the `loadbalancing` exporter (keyed by trace ID) between agent and gateway is how you guarantee that. Get this wrong and tail sampling silently makes bad decisions on partial traces — a subtle, nasty failure.

This is also the layer that complements kernel-level approaches like [eBPF observability with OpenTelemetry](https://blog.michaelsam94.com/ebpf-observability-opentelemetry-obi/): eBPF instrumentation can emit OTLP straight into the same Collector pipelines, so auto-captured and app-emitted telemetry converge on one processing and export path.

## Operating it without regret

A few hard-won operational notes. **Monitor the Collector itself** — it exposes its own metrics (queue sizes, dropped spans, export failures), and a Collector silently dropping data is worse than no Collector because you *think* you have coverage. **Configure exporter queues and retries** so a backend blip buffers rather than drops. **Set the `memory_limiter` conservatively** relative to the container limit; I've seen "80%" plus a bursty batch still OOM because the limiter checks periodically, not continuously. And **version your config in git** with the rest of your infra — a Collector config change is a production change and deserves the same review as code.

The reason I lead with the Collector on every new platform is that it turns observability from a set of hardwired vendor integrations into a programmable pipeline you control. Instrument once in OTLP, and where the data goes, how it's sampled, what's redacted, and how it's enriched all become config you can evolve. That flexibility is worth the modest operational cost many times over — especially the first time you need to change backends, add redaction for a compliance audit, or cut telemetry spend by half without touching a line of application code.

## Agent vs gateway collector topology

Run **agents** as DaemonSet (one per node) for host metrics and local trace batching; run **gateway** collectors as Deployment behind load balancer for tail sampling and multi-tenant routing. Agents forward to gateway via `otlp` exporter — never expose every app's traces directly to SaaS backend (cost and cardinality explosion).

## Processor ordering matters

Wrong order breaks pipelines:

```
memory_limiter → resourcedetection → attributes → batch → tail_sampling → exporter
```

Put `memory_limiter` first to protect the collector process. Run `tail_sampling` after `batch` when using tail sampling processor — it needs complete trace batches. `attributes` processor adding `k8s.pod.name` should run after `resourcedetection` populates cloud/K8s resource attrs.

## Cardinality control

Drop high-cardinality labels before export:

```yaml
processors:
  transform/dropurl:
    trace_statements:
      - context: span
        statements:
          - delete_key(attributes, "http.url")
          - set(attributes["http.route"], attributes["http.route"])
```

`http.url` with raw IDs can generate millions of metric series — Prometheus scrapes choke, bills spike.

## Resources

- [OpenTelemetry Collector documentation](https://opentelemetry.io/docs/collector/)
- [Collector configuration reference](https://opentelemetry.io/docs/collector/configuration/)
- [opentelemetry-collector-contrib (processors, receivers, exporters)](https://github.com/open-telemetry/opentelemetry-collector-contrib)
- [Tail sampling processor docs](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/processor/tailsamplingprocessor/README.md)
- [OTLP specification](https://opentelemetry.io/docs/specs/otlp/)
- [Collector deployment patterns](https://opentelemetry.io/docs/collector/deployment/)