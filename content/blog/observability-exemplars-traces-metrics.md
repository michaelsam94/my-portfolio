---
title: "Linking Metrics to Traces with Exemplars"
slug: "observability-exemplars-traces-metrics"
description: "Connect Prometheus histogram metrics to distributed traces with exemplars: configuration, querying, and debugging latency spikes from dashboards."
datePublished: "2025-10-06"
dateModified: "2025-10-06"
tags: ["DevOps", "Observability", "Performance", "Backend"]
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

## Common production mistakes

Teams get exemplars traces metrics wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Observability for exemplars traces metrics fails when dashboards exist but nobody owns alert routing, high-cardinality labels explode metrics cost, and logs lack trace correlation so incidents become grep archaeology.

## Debugging and triage workflow

When exemplars traces metrics misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Prometheus exemplars proposal](https://github.com/prometheus/prometheus/design-proposals/storage-exemplars.md) — design document
- [OpenTelemetry exemplars specification](https://opentelemetry.io/docs/specs/otel/metrics/data-model/#exemplars) — data model
- [Grafana exemplars documentation](https://grafana.com/docs/grafana/latest/basics/exemplars/) — dashboard configuration
- [Grafana Tempo trace backend](https://grafana.com/docs/tempo/latest/) — trace storage for click-through
- [OpenTelemetry metrics SDK exemplar filter](https://opentelemetry.io/docs/specs/otel/metrics/sdk/#exemplar) — SDK configuration
