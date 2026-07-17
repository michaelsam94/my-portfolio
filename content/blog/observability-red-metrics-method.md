---
title: "RED Metrics Per API Method"
slug: "observability-red-metrics-method"
description: "Instrument every HTTP route and gRPC method with Rate, Errors, and Duration—the minimum golden signals per endpoint."
datePublished: "2026-01-29"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Observability"
  - "Backend"
  - "SRE"
keywords: "RED method metrics, rate errors duration, golden signals microservices, http metrics per route, grpc red metrics"
faq:
  - q: "What does RED stand for?"
    a: "Rate, Errors, Duration histogram—Tom Wilkie's request-driven service signals."
  - q: "How is RED different from four golden signals?"
    a: "Four golden signals add Saturation. RED covers request path; add pool queues and USE for why RED degraded."
  - q: "Should health endpoints be included?"
    a: "Exclude /health and /metrics from SLO dashboards—they dilute error ratios."
---

Outage postmortem: which endpoint broke? Service-level counter hid `/checkout/v2/apply-coupon` at 12% errors for an hour. RED per normalized route answers the first incident question.

## PromQL

Rate: `sum(rate(http_requests_total[5m])) by (route)`. Errors: 5xx ratio per route. Duration: histogram_quantile p99 by route.

## gRPC RED

`grpc_server_handled_total` and handling histogram by `grpc_method` and `grpc_code`.

## Cardinality

Normalize `/users/:id`; alert per tier-1 method not service aggregate.

## GraphQL

Label by `graphql.operation.name`—not bare `POST /graphql`.


## USE metrics for saturation complement

RED on methods tells you requests fail or slow; **USE** (Utilization, Saturation, Errors) on resources explains why:

| Resource | Utilization | Saturation |
|----------|-------------|------------|
| DB pool | connections_active / max | wait_time in traces |
| Event loop | eventloop delay gauge | request queue depth |
| CPU | container CPU / limit | throttling seconds |

Dashboard row: RED for `POST /checkout` adjacent to pool wait p99—on-call sees method errors correlate with pool saturation without separate incident.

## GraphQL and RED

GraphQL single HTTP endpoint breaks naive RED per route—label by `graphql.operation.name` from parsed query or persisted query id:

```javascript
const operationName = parseOperationName(req.body.query);
labels.route = `graphql:${operationName}`;
```

Without this, all GraphQL traffic masquerades as `POST /graphql` one blob.

## Recording rules for alert stability

Alert on 5-minute recorded error ratio per method—smoother than raw counter spikes from deploy pod churn:

```yaml
- record: method:http_errors:ratio5m
  expr: |
    sum by (route) (rate(http_requests_total{status_class="5xx"}[5m]))
    /
    sum by (route) (rate(http_requests_total[5m]))
```

Pages link to method-level dashboard row, not whole-service aggregate hiding broken coupon endpoint.

## Worker queue RED

Background workers are not HTTP—apply RED to `{queue_name}`:

- Rate: jobs processed / sec
- Errors: jobs failed / total
- Duration: job handler histogram

Same dashboard patterns as HTTP; different instrumentation hook in worker framework middleware.

## API versioning in route label

`/api/v1/users` vs `/api/v2/users` must be distinct normalized routes during migration—both active simultaneously. Collapsing to `/api/:ver/users` preserves version breakdown for canary analysis.

## RED in serverless and function platforms

Lambda and Cloud Functions need RED on invocation handler, not just API Gateway HTTP metrics—cold start latency appears in function duration histogram, not edge 5xx. Instrument handler entry/exit in runtime wrapper shared library so all functions get consistent labels without copy-paste.

Batch jobs exposing HTTP admin port for health only should still emit RED on job processing endpoints if operators hit manual trigger APIs—do not leave admin routes as only instrumented surface while business logic runs silently.


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
