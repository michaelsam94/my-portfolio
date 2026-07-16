---
title: "Taming Metric Cardinality"
slug: "observability-metrics-cardinality"
description: "Control Prometheus metric cardinality: label design, cardinality explosion patterns, recording rules, and cost management for high-cardinality telemetry."
datePublished: "2025-10-09"
dateModified: "2025-10-09"
tags: ["DevOps", "Observability", "Performance", "Operations"]
keywords: "metric cardinality, Prometheus cardinality, high cardinality metrics, label design Prometheus, cardinality explosion, metrics cost control"
faq:
  - q: "What metric cardinality is too high?"
    a: "A single metric series count above 1 million is a warning sign. Above 10 million strains most Prometheus setups. Total active series across all metrics above 50 million typically requires dedicated solutions (Grafana Mimir, Thanos) with aggressive retention and downsampling policies."
  - q: "Which labels cause cardinality explosions?"
    a: "User IDs, request IDs, email addresses, UUIDs, unbounded HTTP paths, and error messages are the most common offenders. Each unique label combination creates a new time series. A metric with user_id label and 100,000 users creates 100,000 series."
  - q: "How do I find high-cardinality metrics in my setup?"
    a: "Query Prometheus: topk(20, count by (__name__)({__name__=~'.+'})). In Grafana Cloud, use the cardinality management dashboard. In self-hosted setups, check tsdb analyze or promtool tsdb analyze."
---

Prometheus memory usage hit 28 GB overnight. Nobody deployed new instrumentation. Investigation found `http_requests_total` grew from 50,000 to 4.2 million series because someone added `user_id` as a label. Each user now has their own time series for every endpoint, status code, and method combination. Metric cardinality—the number of unique label combinations per metric name—is the silent killer of observability stacks. One bad label turns a cheap histogram into a storage catastrophe.

## How cardinality works

```
http_requests_total{method="GET", path="/api/users", status="200"}     → series 1
http_requests_total{method="POST", path="/api/users", status="201"}    → series 2
http_requests_total{method="GET", path="/api/users", status="200", user_id="42"}  → series 3
http_requests_total{method="GET", path="/api/users", status="200", user_id="99"}  → series 4
```

Each unique label value combination is a separate time series stored in memory and on disk.

**Cardinality formula:**

```
series count = |label_1 values| × |label_2 values| × ... × |label_n values|
```

5 methods × 50 paths × 10 status codes = 2,500 series. Add `user_id` with 100,000 users: 250 million series.

## Labels to never use

| Label | Why it explodes |
|-------|----------------|
| `user_id` | Unbounded, grows with users |
| `request_id` | Unique per request |
| `trace_id` | Unique per trace |
| `url` (full) | Includes query params |
| `error_message` | Unbounded text |
| `email` | PII + unbounded |
| `ip_address` | Thousands of unique values |

## Safe label design

```python
# BAD — unbounded path label
REQUESTS.labels(method="GET", path=request.path, status=200).inc()
# /api/users/42, /api/users/99, /api/users/101 → new series each

# GOOD — normalized path
def normalize_path(path: str) -> str:
    return re.sub(r"/\d+", "/:id", path)

REQUESTS.labels(method="GET", path=normalize_path(request.path), status=200).inc()
# /api/users/:id for all user IDs → one series
```

Standard labels that work:

```
service, environment, region, method, route (normalized), status_class (2xx, 4xx, 5xx)
```

## Detecting cardinality problems

```promql
# Top 20 metrics by series count
topk(20, count by (__name__) ({__name__=~".+"}))

# Series count for a specific metric
count({__name__="http_requests_total"})

# Label values contributing most to cardinality
topk(10, count by (path) (http_requests_total))
```

Set alerts:

```yaml
- alert: HighCardinalityMetric
  expr: count by (__name__) ({__name__=~".+"}) > 100000
  for: 15m
  annotations:
    summary: "Metric {{ $labels.__name__ }} has {{ $value }} series"
```

## Fixing existing explosions

**1. Relabel at scrape time** — drop bad labels before storage:

```yaml
metric_relabel_configs:
  - source_labels: [user_id]
    regex: .+
    action: labeldrop
```

**2. Recording rules** — aggregate away high-cardinality labels:

```yaml
groups:
  - name: aggregations
    rules:
      - record: http_requests:rate5m
        expr: sum by (method, route, status_class) (rate(http_requests_total[5m]))
```

Query the aggregated metric in dashboards. Keep the raw metric with short retention (1 day) for debugging.

**3. Fix the instrumentation** — remove the label at the source. This is the correct long-term fix.

## Cardinality budgets

Assign per-team budgets:

| Team | Max series | Max labels per metric |
|------|-----------|----------------------|
| Platform | 5M | 8 |
| Product teams | 1M each | 6 |
| Experiments | 100K (7-day TTL) | 5 |

New metrics require review if they add labels beyond the standard set.

## High-cardinality alternatives

When you need per-user or per-request detail, use the right tool:

| Need | Tool | Not |
|------|------|-----|
| Per-request timing | Distributed traces | Metrics with request_id |
| Per-user behavior | Event analytics (ClickHouse) | Metrics with user_id |
| Per-error details | Structured logs | Metrics with error_message |
| Per-URL performance | Traces with http.url attribute | Metrics with full url label |

Metrics aggregate. Logs and traces disaggregate. Using metrics for per-entity data is an architecture mistake.

## Grafana Mimir limits

```yaml
limits:
  max_label_names_per_series: 30
  max_label_value_length: 2048
  cardinality_limit: 100000  # per metric name per tenant
  max_global_series_per_user: 5000000
```

Configure ingestion limits to reject high-cardinality metrics at the source rather than crashing the store.

## Detecting cardinality explosions early

Set alerts before the TSDB falls over:

```promql
# Top metrics by series count
topk(10, count by (__name__)({__name__=~".+"}))

# Rate of new series (cardinality growth)
sum(rate(prometheus_tsdb_head_series_created_total[5m]))
```

Alert when:
- Any single metric exceeds 100K series
- Total series growth > 10% day-over-day
- Ingestion rejected samples spike (Mimir `cortex_discarded_samples_total`)

Run weekly cardinality reports — assign owners to metrics in the top 20.

## Label naming conventions

Standardize labels across services to enable cross-team dashboards:

| Label | Values | Never |
|-------|--------|-------|
| `service` | kebab-case service name | hostname |
| `env` | prod, staging, dev | free-form |
| `status_class` | 2xx, 4xx, 5xx | full status code (use sparingly) |
| `route` | parameterized `/users/:id` | raw URL paths |

Use OpenTelemetry semantic conventions as the baseline — mixing `http.method` and `method` doubles cardinality for the same concept.

## Cost impact

Managed observability bills by ingested samples or series. One bad deploy adding `user_id` label to a counter can 100× your bill overnight:

```
Before: http_requests_total{route="/api/orders"} → 50 series
After:  http_requests_total{route="/api/orders", user_id="..."} → 2M series
```

Add cardinality review to service onboarding checklist. Platform team provides approved instrumentation library with safe defaults.

Pair with [SLIs, SLOs, and error budgets](https://blog.michaelsam94.com/observability-slis-slos-error-budgets/) — high-cardinality metrics don't improve SLO measurement; they threaten the metrics store that SLOs depend on.

## Production checklist

- [ ] Weekly cardinality report with metric owners assigned
- [ ] `user_id` and `request_id` banned from metric labels
- [ ] Ingestion limits configured in Mimir/Prometheus
- [ ] OpenTelemetry semantic conventions enforced in SDK
- [ ] Traces used for per-request detail, not high-cardinality metrics

## Common production mistakes

Teams get metrics cardinality wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Observability for metrics cardinality fails when dashboards exist but nobody owns alert routing, high-cardinality labels explode metrics cost, and logs lack trace correlation so incidents become grep archaeology.

## Resources

- [Prometheus metric and label naming](https://prometheus.io/docs/practices/naming/) — official best practices
- [Grafana Mimir cardinality management](https://grafana.com/docs/mimir/latest/manage/run-production-environment/production-tips/cardinality/) — production guidance
- [Prometheus relabeling](https://prometheus.io/docs/prometheus/latest/configuration/configuration/#relabel_config) — drop labels at scrape time
- [Robust Perception cardinality blog](https://www.robustperception.io/whats-a-respectable-number-of-active-time-series) — cardinality benchmarks
- [OpenTelemetry attribute naming](https://opentelemetry.io/docs/specs/semconv/general/naming/) — semantic conventions for labels
