---
title: "Log and Trace Correlation"
slug: "observability-log-trace-correlation"
description: "Inject trace_id and span_id into structured logs so Loki queries jump to Tempo traces."
datePublished: "2026-01-20"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Observability"
  - "OpenTelemetry"
  - "Logging"
keywords: "log trace correlation, trace_id in logs, opentelemetry logs traces, grafana derived fields, distributed tracing logging"
faq:
  - q: "What fields are required?"
    a: "Minimum trace_id (32 hex). Better: trace_id + span_id + service.name matching trace resource."
  - q: "How do I correlate across async boundaries?"
    a: "Inject W3C traceparent into Kafka/SQS headers; consumer extracts and continues context."
  - q: "Does correlation work with sampling?"
    a: "Always log trace_id even if span not exported—sampled traces still correlate."
---

Four thousand `"payment failed"` log lines—200 with user filter—still no downstream call identified until someone guessed a Jaeger trace. `trace_id` in JSON logs and Grafana derived fields turn grep archaeology into click-through investigation.

## Implementation

OTel active span → inject `trace_id`/`span_id` in pino, structlog, slog middleware.

## Grafana

Loki derived field regex on trace_id → Tempo datasource link. Tempo → logs with `{service.name="$service"} | json | trace_id="$trace_id"`.

## Async

Producer inject headers; consumer extract before processing. Cron jobs start root span or link to scheduler metadata.

## Guardrails

Hex encoding consistent; no duplicate trace IDs from middleware and logger; never generate independent IDs in loggers.


## OpenTelemetry Logs Bridge

OTel 1.24+ logs SDK correlates automatically when logs emitted inside active span context. Prefer OTel logs exporter → Loki over ad-hoc trace_id injection when greenfield—one propagation path.

## Log volume vs trace sampling

At 10% trace sampling, 90% of logs carry trace_ids with no backend trace—acceptable for log filtering by id when sampled. Document in runbook: "trace_id not found → check sampling; use log context alone."

## Cross-vendor correlation

Datadog logs + traces: use `dd.trace_id` attribute. Hybrid cloud during migration may need dual fields temporarily—normalize in log pipeline to single `trace_id` for query UX.

## Serverless and trace context

Lambda cold starts must extract traceparent from API Gateway event headers and inject into logger before first log line—or entire invocation orphaned. AWS Distro for OpenTelemetry layer handles this if stdout JSON includes trace fields automatically.

## Log-based trace reconstruction (last resort)

When trace backend lost but logs retain trace_id, reconstruct partial timeline by sorting logs on trace_id—ugly but saves incident when Tempo retention expired. Argues for log trace_id retention ≥ trace retention.

## Parser compatibility across log agents

Fluent Bit, Vector, and Promtail parse JSON differently—validate trace_id field extraction in staging with each agent version before fleet rollout. Double-escaped JSON from nested loggers breaks derived fields regex; standardize on single JSON object per log line without stringified JSON wrappers.

Include trace_id in audit logs for security-sensitive operations even when trace sampling is off—audit trail completeness outweighs trace backend storage cost for those events.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.

## Production review cadence

Revisit dashboards and alert thresholds after every deploy affecting this observability surface. Weekly on-call review should include one exemplar trace or log linked from a metric spike—paper metrics without exemplars train teams to ignore charts.
