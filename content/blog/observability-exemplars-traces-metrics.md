---
title: "Linking Metrics to Traces with Exemplars"
slug: "observability-exemplars-traces-metrics"
description: "Connect Prometheus histogram metrics to distributed traces with exemplars: configuration, querying, and debugging latency spikes from dashboards."
datePublished: "2025-10-06"
dateModified: "2026-07-17"
tags:
keywords: "Prometheus exemplars, metrics traces correlation, histogram exemplars, Grafana exemplars, OpenTelemetry exemplars, latency debugging"
faq:
  - q: "What is a Prometheus exemplar?"
    a: "An exemplar is a trace_id attached to a specific histogram observation. When you see a latency spike in a heatmap or histogram, exemplars let you click through to the exact distributed trace that produced that data point—connecting aggregate metrics to individual request paths."
  - q: "Do exemplars increase metrics storage cost?"
    a: "Exemplars add roughly 5–15% to histogram storage depending on sampling rate. Most teams attach exemplars to 1–10% of observations, which is enough to debug spikes without significant cost increase."
  - q: "Which metrics backends support exemplars?"
    a: "Prometheus 2.26+, Grafana Mimir, Grafana Cloud, and Cortex support exemplar storage. Grafana dashboards render exemplars as clickable dots on heatmaps. Tempo and Jaeger serve as the trace backend for click-through."
---
Your Grafana heatmap shows checkout latency P99 jumped from 300 ms to 2.1 seconds at 14:32. You switch to traces, set the time range, and scroll through 4,000 traces looking for slow ones. Twenty minutes later you find one. Exemplars eliminate this: the heatmap dot at 14:32 links directly to the trace that recorded a 2.1-second observation. Metrics tell you something broke; exemplars tell you which request to investigate.

## How exemplars work

```
Request → Span created (trace_id: abc123)
       → Histogram records observation (duration: 2.1s)
       → Exemplar attached: {trace_id: "abc123", value: 2.1}
       → Stored alongside metric in Prometheus/Mimir
       → Grafana heatmap shows dot → click → Tempo trace
```

Exemplars are metadata on histogram data points, not separate metrics.

## OpenTelemetry SDK configuration

```javascript
import { MeterProvider, PeriodicExportingMetricReader } from "@opentelemetry/sdk-metrics";
import { OTLPMetricExporter } from "@opentelemetry/exporter-metrics-otlp-http";

const exporter = new OTLPMetricExporter({
  url: "http://otel-collector:4318/v1/metrics",
});

const meterProvider = new MeterProvider({
  readers: [new PeriodicExportingMetricReader({ exporter, exportIntervalMillis: 15000 })],
  exemplarFilter: "trace_based", // attach exemplars to sampled traces
});

const histogram = meterProvider
  .getMeter("checkout")
  .createHistogram("http.server.duration", {
    advice: { explicitBucketBoundaries: [0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10] },
  });

// Recording automatically attaches trace context as exemplar
histogram.record(responseTimeMs, { "http.route": "/checkout" });
```

`exemplarFilter: "trace_based"` attaches exemplars only when the current request has an active sampled trace—avoiding exemplar spam on unsampled requests.

## Prometheus native exemplars

```go
import (
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promauto"
    "go.opentelemetry.io/otel/trace"
)

var requestDuration = promauto.NewHistogram(prometheus.HistogramOpts{
    Name:    "http_request_duration_seconds",
    Buckets: []float64{0.05, 0.1, 0.25, 0.5, 1, 2.5, 5},
})

func handleRequest(w http.ResponseWriter, r *http.Request) {
    start := time.Now()
    // ... handle request ...
    duration := time.Since(start).Seconds()

    span := trace.SpanFromContext(r.Context())
    if span.SpanContext().IsSampled() {
        requestDuration.(prometheus.ExemplarObserver).ObserveWithExemplar(
            duration,
            prometheus.Labels{
                "trace_id": span.SpanContext().TraceID().String(),
                "span_id":  span.SpanContext().SpanID().String(),
            },
        )
    } else {
        requestDuration.Observe(duration)
    }
}
```

## Grafana configuration

**Data source linking:**

```yaml
# Grafana datasource config for Prometheus/Mimir
jsonData:
  exemplarTraceIdDestinations:
    - name: trace_id
      datasourceUid: tempo-uid
      urlDisplayLabel: "View trace"
```

**Heatmap panel:** Enable "Show exemplars" in the histogram heatmap panel settings. Exemplars appear as colored dots on high-latency cells.

## Querying exemplars

```promql
# Standard histogram query — exemplars returned automatically
histogram_quantile(0.99,
  sum by (le) (rate(http_request_duration_seconds_bucket[5m]))
)
```

In Grafana Explore, switch to "Exemplars" tab on any histogram query to list linked trace IDs.

## Sampling alignment

Exemplars are only useful when the linked trace exists in your trace backend:

| Tracing sample rate | Exemplar value |
|--------------------|----------------|
| 100% | Every heatmap dot links to a trace |
| 10% | ~10% of dots are clickable—still enough for debugging |
| 1% | Sparse exemplars—may miss the exact slow request |
| 0% (tracing off) | Exemplars point to nonexistent traces |

Align tracing and exemplar sampling. If tracing samples at 10%, exemplars on 100% of observations waste storage linking to missing traces.

## Debugging workflow

1. **Alert fires:** Checkout P99 > 1s.
2. **Open heatmap** for `http_request_duration_seconds` filtered to `/checkout`.
3. **Click exemplar dot** at the spike timestamp.
4. **Trace opens** in Tempo showing: API (50 ms) → inventory (2,800 ms) → payment (100 ms).
5. **Root cause:** inventory service had a lock contention on `stock_update`.
6. **Fix:** change row-level lock to optimistic concurrency.

Without exemplars, step 3 is manual trace search. With exemplars, it is one click.

## Storage considerations

Exemplars in Prometheus are stored within the histogram chunk. High-cardinality labels on exemplars (like `user_id`) explode storage—attach only `trace_id` and `span_id`.

Mimir and Cortex support exemplar deduplication at ingestion. Configure limits:

```yaml
limits:
  max_global_exemplars_per_user: 100000
```

## Production checklist

- [ ] Tracing sample rate aligned with exemplar retention
- [ ] Exemplars attach only `trace_id`/`span_id`, not high-cardinality labels
- [ ] Grafana datasource configured for trace click-through
- [ ] Heatmap panels enabled on latency histogram dashboards
- [ ] Exemplar storage limits configured in Mimir/Cortex

Without click-through from metrics to traces configured in Grafana, exemplars are stored cost with zero debugging value.

## Exemplars link metrics to traces

Histogram buckets with trace_id attachment enable click-from-spike-to-trace in Grafana. Sample 1–10% of observations with exemplars — full exemplar capture explodes storage.

## Mimir exemplar limits in production

Configure per-tenant exemplar limits before enabling fleet-wide:

```yaml
limits:
  max_global_exemplars_per_user: 200000
  max_exemplars_per_series: 10
```

Exceeding limits drops exemplars silently—monitor `cortex_discarded_exemplars_total`.

## OpenMetrics exemplar format

Prometheus remote write to Mimir must use OpenMetrics 1.0 text format for exemplar retention. Verify otel-collector `prometheus` exporter `enable_open_metrics: true` when metrics originate from OTel SDK histograms with exemplars attached.

## Debugging workflow automation

Grafana annotation webhook on alert includes deep link:

```
/explore?left={"queries":[{"refId":"A","expr":"..."}],"range":{"from":"now-15m"}}
```

On-call lands on heatmap with exemplars visible—remove manual dashboard hunting from runbook step 2.

## Heatmap panel configuration gotchas

Grafana heatmap requires `format: heatmap` on Prometheus query and `Exemplars: true` in panel options—easy to miss in JSON dashboard provisioning. Lint dashboards in CI with grafonnet or jsonnet tests asserting exemplar config on tier-1 latency panels.

## Mobile and high-latency clients

Mobile apps may show user latency >> server histogram if network slow—exemplars on server heatmap still valuable but pair with RUM for complete story. Do not argue server SLO green while mobile RUM red without acknowledging client/network path.

## Resources

- [Prometheus exemplars proposal](https://github.com/prometheus/prometheus/design-proposals/storage-exemplars.md) — design document
- [OpenTelemetry exemplars specification](https://opentelemetry.io/docs/specs/otel/metrics/data-model/#exemplars) — data model
- [Grafana exemplars documentation](https://grafana.com/docs/grafana/latest/basics/exemplars/) — dashboard configuration
- [Grafana Tempo trace backend](https://grafana.com/docs/tempo/latest/) — trace storage for click-through
- [OpenTelemetry metrics SDK exemplar filter](https://opentelemetry.io/docs/specs/otel/metrics/sdk/#exemplar) — SDK configuration

## Production notes for LLM stacks

When `observability-exemplars-traces-metrics` sits on an inference or RAG path, treat user prompts and retrieved chunks as untrusted input. Log correlation IDs and policy decisions—not raw prompts—in production telemetry. Gate risky operations behind explicit authorization at the gateway, not inside ad-hoc tool handlers.

Roll out changes with shadow mode first: record what **would** have happened under the new rule without blocking traffic. Compare deny rates, latency impact, and false positives for at least one business week before enforcing. Pair enforcement with a runbook entry: symptom, dashboard, rollback (feature flag or config), and owner.

Load-test with production-shaped concurrency. LLM workloads burst differently from CRUD APIs—tail latency and token throttling dominate. If `linking metrics to traces with exemplars` protects an invariant (security, billing, data residency), prove the invariant with an automated test that fails CI when someone removes the check.

## What teams get wrong

Teams copy a reference architecture without matching their compliance tier, then discover in audit that logs, backups, or support exports reintroduced the data they thought they had eliminated. Another pattern: shipping the demo integration without idempotency, then fighting duplicate side effects when clients retry on model timeouts.

Document the tradeoff you chose—strictness vs recall, cost vs quality, sync vs async—and the metric that tells you if the choice still holds six months later.

## Instrumentation checklist

Ensure every service emits consistent resource attributes: `service.name`, `service.version`, `deployment.environment`. Propagate W3C `traceparent` on outbound HTTP, gRPC metadata, and message headers. For ORM-heavy services, enable query tracing with statement timeouts logged as span events—not as raw SQL with bind parameters.

## SLO wiring

Define SLIs that map to user journeys: checkout success rate, inference completion rate, search results under 500ms. Multi-window burn-rate alerts (e.g., 1h and 6h) catch fast burns and slow leaks. Page on symptom-based alerts; ticket on cause-based logs after mitigation.

## Cardinality and cost control

Drop high-cardinality labels before they hit the metrics backend. Use exemplars to link traces to histogram buckets without labeling every user ID. For LLM gateways, aggregate token usage by model and route—not by end user—in the metrics layer; keep per-tenant billing in a warehouse.

## Operational review cadence

Weekly: review top noisy alerts and dashboards nobody opened. Monthly: game-day a dependency failure and verify runbooks. Quarterly: revalidate sampling and retention against compliance requirements—especially when prompts or PII might appear in debug spans.


For `observability-exemplars-traces-metrics`, treat observability and security controls as part of the user experience: silent failures erode trust faster than explicit error messages. Instrument deny paths, measure tail latency, and review dashboards with on-call weekly.

For `observability-exemplars-traces-metrics`, treat observability and security controls as part of the user experience: silent failures erode trust faster than explicit error messages. Instrument deny paths, measure tail latency, and review dashboards with on-call weekly.

For `observability-exemplars-traces-metrics`, treat observability and security controls as part of the user experience: silent failures erode trust faster than explicit error messages. Instrument deny paths, measure tail latency, and review dashboards with on-call weekly.
