---
title: "The Three Pillars of Observability"
slug: "observability-three-pillars"
description: "Understand the three pillars of observability—metrics, logs, and traces—and how to combine them for effective production debugging and SRE workflows."
datePublished: "2025-10-18"
dateModified: "2026-07-17"
tags: ["DevOps", "Observability", "SRE", "Architecture"]
keywords: "three pillars observability, metrics logs traces, observability stack, monitoring vs observability, production debugging, telemetry pillars"
faq:
  - q: "What is the difference between monitoring and observability?"
    a: "Monitoring tells you when known problems occur—dashboards and alerts on predefined thresholds. Observability lets you investigate unknown problems by exploring metrics, logs, and traces without predicting what will break. You need both: monitoring for known failure modes, observability for novel ones."
  - q: "Do I need all three pillars from day one?"
    a: "Start with structured logs and basic metrics (request rate, error rate, latency). Add distributed tracing when you have more than three services or debugging crosses service boundaries. Each pillar adds value independently, but their combination is greater than the sum."
  - q: "How do the three pillars connect?"
    a: "Use exemplars to link metrics to traces. Include trace_id in log entries. Use consistent labels (service, environment) across all three. In Grafana, configure data source linking so clicking a metric spike opens related traces and logs."
---

Production is down. Someone checks the CPU graph—it looks fine. Another person greps logs and finds timeout errors. A third opens Jaeger and spots a slow database span. Three people, three tools, thirty minutes before they correlate their findings. The three pillars of observability—metrics, logs, and traces—are not three separate monitoring strategies. They are three views of the same system, and their value multiplies when linked.

## The three pillars

| Pillar | Question it answers | Data type | Tool examples |
|--------|-------------------|-----------|---------------|
| Metrics | What is happening, in aggregate? | Numeric time series | Prometheus, Grafana, Datadog |
| Logs | What happened, with details? | Discrete events | Loki, Elasticsearch, CloudWatch |
| Traces | Where did time go, across services? | Request paths with timing | Jaeger, Tempo, Zipkin |

```
         ┌──────────┐
         │  Metrics  │  "Error rate spiked to 3% at 14:32"
         └─────┬────┘
               │ exemplar / alert
         ┌─────▼────┐
         │  Traces   │  "Slow spans point to inventory-service"
         └─────┬────┘
               │ trace_id
         ┌─────▼────┐
         │   Logs    │  "Connection pool exhausted, 50 timeouts"
         └──────────┘
```

## Metrics: the aggregate view

Metrics compress thousands of events into numbers over time:

```promql
# Request rate
sum(rate(http_requests_total[5m])) by (service)

# Error rate
sum(rate(http_requests_total{status=~"5.."}[5m]))
/
sum(rate(http_requests_total[5m]))

# P99 latency
histogram_quantile(0.99,
  sum by (le, service) (rate(http_request_duration_seconds_bucket[5m]))
)
```

Metrics are cheap to store (bytes per series per day) and fast to query. They tell you something changed but not why.

**Best for:** Dashboards, alerting, capacity planning, SLO tracking.

## Logs: the event record

Logs capture individual events with context:

```json
{
  "timestamp": "2025-10-18T14:32:05.123Z",
  "level": "error",
  "message": "database connection timeout",
  "service": "inventory-api",
  "trace_id": "abc123",
  "error": "timeout after 5000ms",
  "context": { "pool_size": 20, "active_connections": 20 }
}
```

Logs are verbose (kilobytes per event) and expensive at high volume. They tell you what happened to specific requests.

**Best for:** Debugging specific failures, audit trails, security events.

## Traces: the request journey

Traces show the path and timing of one request across services:

```
checkout-api [200ms]
  ├── inventory-service [1800ms]  ← bottleneck
  │     └── postgres.query [1750ms]
  └── payment-service [120ms]
```

Traces are moderate cost (sampled at 1–10%). They tell you where time was spent across service boundaries.

**Best for:** Latency debugging, dependency mapping, cross-service failures.

## Connecting the pillars

**trace_id is the glue:**

```javascript
// In your request handler
const traceId = span.spanContext().traceId;

// Metrics: exemplar on histogram
histogram.observe(duration, { trace_id: traceId });

// Logs: field on every entry
logger.info({ trace_id: traceId, order_id }, "order processed");
```

**Grafana data source linking:**

```yaml
# Prometheus/Mimir datasource
exemplarTraceIdDestinations:
  - datasourceUid: tempo
    name: trace_id

# Loki datasource
derivedFields:
  - name: Trace
    matcherRegex: "trace_id=(\\w+)"
    datasourceUid: tempo
    url: "$${__value.raw}"
```

Click a metric spike → see the trace → see the logs. One workflow, three pillars.

## Debugging workflow example

**14:32 — Alert:** Checkout error rate > 1%.

1. **Metrics:** Open error rate dashboard. Spike started at 14:30, affects only `checkout-api`.
2. **Metrics:** Click exemplar on the heatmap. Opens trace `abc123`.
3. **Traces:** Trace shows `inventory-service` span failing with 503, duration 5s (timeout).
4. **Logs:** Filter `{service="inventory-api"} | json | trace_id="abc123"`. Log says "connection pool exhausted, 20/20 active."
5. **Root cause:** Traffic spike exhausted the database connection pool.
6. **Fix:** Increase pool size from 20 to 50. Error rate drops to 0.1% by 14:45.

Total investigation time: 8 minutes. Without pillar linking: 30–60 minutes.

## What about the fourth pillar?

Some add **profiling** (continuous CPU/memory snapshots) as a fourth pillar. Profiling answers "which function consumed resources"—between metrics (aggregate resource usage) and traces (per-request path). It complements the three pillars for performance optimization.

## Building the stack incrementally

**Week 1:** Structured JSON logs with `service`, `level`, `request_id`.
**Week 2:** Prometheus metrics—request rate, error rate, latency histogram per service.
**Week 3:** Grafana dashboards combining logs (Loki) and metrics (Prometheus).
**Month 2:** OpenTelemetry tracing on API gateway and top 3 services.
**Month 3:** Exemplar linking, trace_id in logs, SLO dashboards.

Don't wait for perfect instrumentation. Ship one pillar at a time.

## Anti-patterns

- **Metrics for everything:** Per-user metrics explode cardinality. Use logs or events.
- **Logs as metrics:** Counting errors by grepping logs is fragile. Use counter metrics.
- **100% trace sampling in production:** Expensive and unnecessary. Sample 5–10%, always keep errors.
- **Three disconnected tools:** If you can't click from metric to trace to log, you have three monitors, not observability.

Treat production rollout as a measured change: ship with observability, validate rollback, and review metrics 24 hours after deploy — patterns that look obvious in docs fail when skipped under release pressure.

## Common production mistakes

Teams get three pillars wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Observability for three pillars fails when dashboards exist but nobody owns alert routing, high-cardinality labels explode metrics cost, and logs lack trace correlation so incidents become grep archaeology.

## Debugging and triage workflow

When three pillars misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Google SRE Book — Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/) — foundational observability concepts
- [OpenTelemetry documentation](https://opentelemetry.io/docs/concepts/observability-primer/) — observability primer
- [Grafana observability stack](https://grafana.com/docs/grafana-cloud/send-data/) — integrated metrics, logs, traces
- [Charity Majors on observability](https://www.honeycomb.io/blog/observability-101-terminology-and-concepts) — pillars vs monitoring debate
- [Prometheus best practices](https://prometheus.io/docs/practices/) — metric design guidelines
