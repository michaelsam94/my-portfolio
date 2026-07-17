---
title: "System Design: Metrics and Monitoring"
slug: "system-design-metrics-monitoring"
description: "Design a metrics and monitoring platform collecting time-series data from thousands of services, with alerting, dashboards, and long-term storage at scale."
datePublished: "2025-10-25"
dateModified: "2026-07-17"
tags: ["System Design", "Observability", "Monitoring", "DevOps"]
keywords: "metrics monitoring system design, time series database, Prometheus architecture, alerting pipeline, observability platform, Datadog system design"
faq:
  - q: "What is the difference between metrics, logs, and traces?"
    a: "Metrics are numeric measurements over time — request rate, error rate, latency histograms. Logs are discrete event records with context — error messages, audit trails. Traces follow a single request across services — span timings, dependency maps. Metrics answer 'what is happening?' at aggregate level. Logs answer 'what happened for this specific event?' Traces answer 'why is this request slow across services?' A complete observability stack uses all three."
  - q: "How do you handle metrics cardinality explosion?"
    a: "Cardinality is the number of unique time series — metric name plus label combinations. High-cardinality labels (user_id, request_id) on high-frequency metrics create millions of series and crash storage. Limit labels to low-cardinality dimensions (service, endpoint, status_code, region). Use logs or traces for per-request detail. Set cardinality limits in your metrics pipeline and drop or aggregate series that exceed thresholds."
  - q: "Push vs pull for metrics collection — which is better?"
    a: "Pull (Prometheus scraping targets) is simpler for Kubernetes — the scraper discovers targets via service discovery and pulls metrics on a schedule. Push (StatsD, OpenTelemetry collector receiving metrics) is necessary for short-lived jobs, serverless functions, and services behind firewalls. Most production systems use both: pull for long-running services, push via a collector gateway for everything else."
faqAnswers:
  - question: "When is system design metrics monitoring the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for system design metrics monitoring?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back system design metrics monitoring safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
When our API latency spiked at 3 AM, the on-call engineer needed to know three things in under sixty seconds: which service was slow, which endpoint, and whether it was all users or one tenant. Logs would get there eventually — after writing a query across terabytes of JSON. Traces would show the path — if sampling caught the slow requests. Metrics answered instantly: `http_request_duration_p99{service="checkout", endpoint="/pay"}` jumped from 200ms to 4s at 03:02 UTC, all tenants affected.

A metrics and monitoring platform ingests numeric time-series data from every service, stores it efficiently, evaluates alert rules, and serves dashboards. It's the nervous system of production infrastructure.

## Architecture overview

```
Services → Exporters/SDK → Collection Agents → Ingestion Pipeline → Time-Series DB
                                                          ↓
                                                    Alert Evaluator → PagerDuty/Slack
                                                          ↓
                                                    Dashboard Server (Grafana)
```

Services expose metrics via `/metrics` endpoints (Prometheus format) or push to a collector (OpenTelemetry, StatsD). Collection agents scrape or receive, batch, and forward to the ingestion pipeline. The time-series database stores and queries data. Alert evaluators run PromQL or equivalent against the database.

## Metric types and naming

Four fundamental metric types:

- **Counter:** Monotonically increasing value. `http_requests_total`, `errors_total`. Use `rate()` to get per-second rate.
- **Gauge:** Value that goes up and down. `memory_usage_bytes`, `active_connections`, `queue_depth`.
- **Histogram:** Distribution of values in configurable buckets. `http_request_duration_seconds` with buckets `[0.01, 0.05, 0.1, 0.5, 1, 5]`. Enables percentile calculation.
- **Summary:** Pre-computed quantiles (less common, harder to aggregate across instances).

Naming convention: `{namespace}_{metric}_{unit}_{type_suffix}`

```
http_request_duration_seconds_bucket
http_requests_total
process_cpu_seconds_total
jvm_memory_used_bytes
```

Labels add dimensions: `{method="POST", status="500", service="checkout"}`. Keep label cardinality low — service, endpoint, status code, region. Never label with user IDs or request IDs on counters.

## Ingestion pipeline

At scale (millions of data points per second), the ingestion pipeline needs buffering and batching:

```python
# Simplified ingestion handler
async def ingest_metrics(batch: list[MetricSample]):
    validated = [s for s in batch if validate_labels(s) and validate_cardinality(s)]
    deduplicated = deduplicate_samples(validated)
    compressed = compress_batch(deduplicated)

    # Write to hot storage (last 15 days)
    await hot_store.write(compressed)

    # Downsample and write to warm storage (15 days - 1 year)
    if should_downsample():
        await warm_store.write(downsample(compressed, resolution="5m"))

    # Evaluate alert rules against new data
    await alert_engine.evaluate(validated)
```

**Hot storage:** Full resolution (15-second scrape interval), last 15 days. Used for real-time dashboards and alerting. Typically in-memory or SSD-backed (Prometheus local storage, VictoriaMetrics).

**Warm storage:** Downsampled to 1-minute or 5-minute resolution, 15 days to 1 year. Used for trend analysis and capacity planning.

**Cold storage:** Hourly aggregates, 1+ years. Object storage (S3) for compliance and long-term trends.

## Alerting design

Alert rules evaluate metric queries on a schedule:

```yaml
# Prometheus alert rule
groups:
  - name: checkout
    rules:
      - alert: HighErrorRate
        expr: |
          sum(rate(http_requests_total{service="checkout", status=~"5.."}[5m]))
          / sum(rate(http_requests_total{service="checkout"}[5m])) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Checkout error rate above 5% for 5 minutes"
```

Key alerting principles:

- **Alert on symptoms, not causes.** Alert on high latency and error rate, not on CPU usage (unless CPU is the known cause).
- **Use `for` duration.** Require the condition to hold for N minutes before firing — prevents flapping on transient spikes.
- **Every alert must be actionable.** If the on-call can't do anything about it, it's not an alert — it's a dashboard panel.
- **Route by severity.** Critical → page. Warning → Slack. Info → dashboard only.

## Dashboard design

Effective dashboards follow a hierarchy:

1. **Overview:** Service health at a glance — RED metrics (Rate, Errors, Duration) per service.
2. **Service detail:** Endpoint-level breakdown, dependency latency, resource utilization.
3. **Debugging:** Correlated logs, traces, and metric drill-down for incident investigation.

Use template variables for service, region, and environment so one dashboard serves all contexts.

## Scaling the metrics platform

| Scale | Approach |
|-------|----------|
| < 100 services | Single Prometheus instance + Grafana |
| 100-1000 services | Prometheus federation or VictoriaMetrics cluster |
| 1000+ services | Hierarchical collection: per-cluster collectors → global aggregator |
| Multi-region | Regional collectors, global query federation |

Prometheus horizontal scaling uses federation (scraping other Prometheus instances) or sharding (each instance handles a subset of targets). VictoriaMetrics and Cortex/Mimir offer native clustering for large deployments.

## OpenTelemetry as the standard

OpenTelemetry (OTel) is becoming the vendor-neutral standard for metrics, logs, and traces:

```python
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

meter = metrics.get_meter("checkout-service")
request_counter = meter.create_counter("http.requests", description="Total HTTP requests")
latency_histogram = meter.create_histogram("http.duration", unit="ms")

# In request handler:
request_counter.add(1, {"method": "POST", "status": "200"})
latency_histogram.record(duration_ms, {"endpoint": "/pay"})
```

OTel SDKs instrument code; the OTel Collector receives, processes, and exports to any backend (Prometheus, Datadog, Grafana Cloud).

## Recording rules and query performance

Ad-hoc PromQL across raw metrics at dashboard load time does not scale. Pre-compute expensive aggregations with recording rules:

```yaml
groups:
  - name: checkout_recording
    rules:
      - record: checkout:http_requests:rate5m
        expr: sum(rate(http_requests_total{service="checkout"}[5m])) by (endpoint, status)
```

Dashboards query recorded metrics; alerts use the same recordings for consistency. Without recording rules, a Grafana dashboard with twenty panels each running `rate()` over millions of series will timeout during incidents — exactly when you need dashboards most.

## SLO burn alerts that wake the right person

Error budget burn rate alerts should page only when user-visible SLO is at risk — not when a non-critical batch job metric spikes. Multi-window burn (e.g., 1h and 6h) reduces false positives from brief blips. Tie alert names to customer journeys: `checkout_success_rate_burn` not `prometheus_scrape_failures`. On-call runbooks link from alert annotations to dashboards filtered to the failing service and region.

## Resources

- [Prometheus documentation — metric types](https://prometheus.io/docs/concepts/metric_types/)
- [Google SRE Book — Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/)
- [OpenTelemetry metrics specification](https://opentelemetry.io/docs/specs/otel/metrics/)
- [VictoriaMetrics cluster architecture](https://docs.victoriametrics.com/cluster-victoriametrics/)
- [Grafana alerting best practices](https://grafana.com/docs/grafana/latest/alerting/best-practices/)

## system design metrics monitoring rollout

Field RUM on Android 4G. Rollback documented in the PR. Test back navigation and offline recovery.

## SLOs before dashboards

Instrument the golden journeys first: availability and latency SLOs, then RED/USE metrics that explain burn. Cardinality kills: never put user IDs or unbounded paths into label values. Enforce label budgets in the metrics library.

## Alerting humans can survive

Page on symptom burn rates; ticket on causes. Every alert needs a runbook with the first three queries. Exemplars from latency alerts into traces beat log archaeology. Monitor remote-write lag and HA pair health — a silent metrics black hole is discovered only during customer pain.

## Verification layer 1 for system design metrics monitoring

Define an acceptance check for layer 1: failure injection, timeout behavior, and rollback. Keep it next to the code that implements system design metrics monitoring. Reviewers confirm the check fails when the control is disabled.

## Verification layer 2 for system design metrics monitoring

Define an acceptance check for layer 2: failure injection, timeout behavior, and rollback. Keep it next to the code that implements system design metrics monitoring. Reviewers confirm the check fails when the control is disabled.

## Verification layer 3 for system design metrics monitoring

Define an acceptance check for layer 3: failure injection, timeout behavior, and rollback. Keep it next to the code that implements system design metrics monitoring. Reviewers confirm the check fails when the control is disabled.

## Verification layer 4 for system design metrics monitoring

Define an acceptance check for layer 4: failure injection, timeout behavior, and rollback. Keep it next to the code that implements system design metrics monitoring. Reviewers confirm the check fails when the control is disabled.
