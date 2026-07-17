---
title: "Distributed Tracing with OpenTelemetry"
slug: "observability-distributed-tracing-otel"
description: "Implement distributed tracing with OpenTelemetry: instrumentation, context propagation, span attributes, collectors, and debugging microservices."
datePublished: "2025-10-03"
dateModified: "2026-07-17"
tags: ["DevOps", "Observability", "Backend", "Architecture"]
keywords: "OpenTelemetry tracing, distributed tracing, OTel SDK, trace context propagation, Jaeger tracing, span attributes, microservices debugging"
faq:
  - q: "Do I need to instrument every service for tracing to be useful?"
    a: "Start with your API gateway and the top three services by request volume. Even 30% coverage gives you enough context to narrow failures. Add instrumentation to additional services when debugging requires visibility into their internal spans."
  - q: "What is the overhead of OpenTelemetry tracing?"
    a: "With 10% head-based sampling, overhead is typically 1–3% CPU and 1–5 MB memory per service. Tail-based sampling (keep all error traces, sample 1% of success traces) provides better signal with similar overhead."
  - q: "How do traces relate to logs and metrics?"
    a: "Traces show the path and timing of a single request across services. Logs provide event details at each step. Metrics aggregate behavior over time. Link them with trace_id in logs and exemplars on metrics—click from a latency spike to the slow traces that caused it."
---

A user reports checkout took 12 seconds. Your API logs show 200 ms. Payment logs show 150 ms. Shipping logs show 180 ms. Nothing looks slow individually, but something in between ate 11 seconds. Without distributed tracing, you grep three services and guess at network gaps. With OpenTelemetry, one trace shows every span: API (200 ms) → payment queue wait (10,800 ms) → payment process (150 ms). The queue was the problem.

## Core concepts

| Concept | Definition |
|---------|------------|
| Trace | End-to-end journey of one request (shared trace_id) |
| Span | One operation within a trace (HTTP call, DB query, function) |
| Context | trace_id + span_id + trace_flags propagated between services |
| Baggage | Key-value pairs propagated across services (user_id, tenant) |
| Collector | Receives, processes, and exports spans to backends |

## Auto-instrumentation (Node.js)

```javascript
// tracing.js — import BEFORE other modules
import { NodeSDK } from "@opentelemetry/sdk-node";
import { getNodeAutoInstrumentations } from "@opentelemetry/auto-instrumentations-node";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";

const sdk = new NodeSDK({
  traceExporter: new OTLPTraceExporter({
    url: "http://otel-collector:4318/v1/traces",
  }),
  instrumentations: [getNodeAutoInstrumentations()],
  serviceName: "checkout-api",
});

sdk.start();
```

```bash
node --import ./tracing.js server.js
```

Auto-instrumentation wraps HTTP, Express, pg, Redis, and gRPC clients with zero code changes.

## Manual spans for business logic

```javascript
import { trace } from "@opentelemetry/api";

const tracer = trace.getTracer("checkout-api");

async function processCheckout(cartId) {
  return tracer.startActiveSpan("processCheckout", async (span) => {
    span.setAttribute("cart.id", cartId);
    try {
      const cart = await tracer.startActiveSpan("fetchCart", async (s) => {
        const result = await cartService.get(cartId);
        s.setAttribute("cart.item_count", result.items.length);
        s.end();
        return result;
      });

      const payment = await chargePayment(cart);
      span.setAttribute("payment.amount", payment.amount);
      span.setStatus({ code: SpanStatusCode.OK });
      return payment;
    } catch (err) {
      span.setStatus({ code: SpanStatusCode.ERROR, message: err.message });
      span.recordException(err);
      throw err;
    } finally {
      span.end();
    }
  });
}
```

## Context propagation

For tracing to work across services, every outbound HTTP call must carry trace headers:

```
traceparent: 00-<trace_id>-<span_id>-01
tracestate: vendor=value
```

Auto-instrumentation handles this. For manual propagation:

```javascript
import { propagation, context } from "@opentelemetry/api";

const headers = {};
propagation.inject(context.active(), headers);
await fetch("http://payment-service/charge", { headers });
```

The payment service's auto-instrumentation extracts these headers and creates a child span linked to the same trace.

## OpenTelemetry Collector

```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 5s
    send_batch_size: 1000
  memory_limiter:
    limit_mib: 512

exporters:
  otlp/jaeger:
    endpoint: jaeger:4317
    tls:
      insecure: true

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [otlp/jaeger]
```

Run one collector per cluster. Services send spans to the collector; the collector batches and forwards to Jaeger, Tempo, or Datadog.

## Sampling strategies

**Head-based (at trace start):**

```javascript
import { TraceIdRatioBasedSampler } from "@opentelemetry/sdk-trace-base";

// Sample 10% of traces
const sampler = new TraceIdRatioBasedSampler(0.1);
```

**Tail-based (in collector):** Keep 100% of error traces, 1% of success traces. Requires the collector to buffer complete traces before deciding—higher memory, better signal.

Always sample errors at 100%. Missing error traces defeats the purpose.

## Debugging with traces

1. **Find slow requests:** Filter traces where total duration > 2s.
2. **Identify the slow span:** The widest bar in the waterfall view.
3. **Check span attributes:** `db.statement`, `http.url`, `error.message`.
4. **Compare to baseline:** Same endpoint, normal traces average 200 ms—this one spent 9s in `payment-queue-wait`.

Add custom attributes that help your team:

```javascript
span.setAttribute("user.id", userId);
span.setAttribute("tenant.id", tenantId);
span.setAttribute("feature_flag.new_checkout", true);
```

## Linking traces to logs

```javascript
import { trace } from "@opentelemetry/api";

const span = trace.getActiveSpan();
const traceId = span?.spanContext().traceId;

logger.info({ trace_id: traceId, cart_id: cartId }, "Processing checkout");
```

In Grafana/Loki, filter `{trace_id="abc123"}` to see all logs for one request.

Sample errors at 100% and success at 1% — error traces without representative success baselines hide latency regressions on happy paths.

## Context propagation across services

W3C `traceparent` header must propagate through every hop:

```javascript
// Node.js fetch with propagation
const { propagation, context } = require("@opentelemetry/api");
const headers = {};
propagation.inject(context.active(), headers);
await fetch(url, { headers });
```

Broken propagation creates orphan spans — the trace shows service A and C but not B, making latency attribution impossible.

## Tail sampling configuration

```yaml
# OpenTelemetry Collector tail_sampling
processors:
  tail_sampling:
    policies:
      - name: errors
        type: status_code
        status_code: { status_codes: [ERROR] }
      - name: slow
        type: latency
        latency: { threshold_ms: 2000 }
      - name: probabilistic
        type: probabilistic
        probabilistic: { sampling_percentage: 1 }
```

Tail sampling requires collector memory buffering — size for peak trace volume × max trace duration.

Pair with [observability SLIs SLOs error budgets](https://blog.michaelsam94.com/observability-slis-slos-error-budgets/) when defining trace-based SLOs.

## Common production mistakes

Teams get distributed tracing otel wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Observability for distributed tracing otel fails when dashboards exist but nobody owns alert routing, high-cardinality labels explode metrics cost, and logs lack trace correlation so incidents become grep archaeology.

## Debugging and triage workflow

When distributed tracing otel misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [OpenTelemetry documentation](https://opentelemetry.io/docs/) — official guides and concepts
- [OpenTelemetry JS SDK](https://opentelemetry.io/docs/languages/js/) — Node.js instrumentation
- [W3C Trace Context specification](https://www.w3.org/TR/trace-context/) — traceparent header format
- [Jaeger architecture](https://www.jaegertracing.io/docs/latest/architecture/) — trace storage and query
- [Grafana Tempo](https://grafana.com/docs/tempo/latest/) — trace backend integrated with Grafana
