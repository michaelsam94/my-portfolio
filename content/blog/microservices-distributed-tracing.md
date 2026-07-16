---
title: "Distributed Tracing Across Services"
slug: "microservices-distributed-tracing"
description: "Trace requests across microservices with OpenTelemetry: context propagation, span instrumentation, sampling strategies, and debugging production latency."
datePublished: "2025-06-13"
dateModified: "2025-06-13"
tags: ["BE", "Microservices", "Observability", "OpenTelemetry"]
keywords: "distributed tracing microservices, OpenTelemetry tracing, trace context propagation, Jaeger tracing, span instrumentation, W3C trace context"
faq:
  - q: "What is the difference between a trace and a span?"
    a: "A trace represents the entire journey of a request across all services. A span is a single operation within that trace — one HTTP call, one database query, one function execution. Spans form a tree: a parent span (API gateway) contains child spans (service calls, DB queries)."
  - q: "How does trace context propagate between services?"
    a: "The W3C Trace Context standard defines traceparent and tracestate HTTP headers. When Service A calls Service B, it injects the current trace ID and span ID into headers. Service B extracts them and creates a child span linked to the same trace. OpenTelemetry SDKs handle injection and extraction automatically."
  - q: "Should I trace every request in production?"
    a: "No. Full tracing at high volume generates enormous data and adds latency. Use head-based sampling (trace 1–10% of requests) or tail-based sampling (collect all spans but only export traces that are slow or errored). Always trace 100% in staging."
---

A user reports checkout took 12 seconds. Your API gateway logs show 200ms. The order service logs show 800ms. The payment service logs show nothing — it was called but has no record because the request ID format differs. Three services, three log formats, no way to connect them into one timeline.

Distributed tracing links every operation in a request into a single trace — a waterfall showing exactly where time was spent and which service caused the delay. OpenTelemetry is the standard that makes this work across languages and vendors.

## Traces, spans, and context

```
Trace (trace_id: abc123)
├── Span: API Gateway (200ms)
│   ├── Span: Auth check (15ms)
│   └── Span: Order Service call (170ms)
│       ├── Span: Validate order (5ms)
│       ├── Span: DB query (20ms)
│       └── Span: Payment Service call (140ms)
│           ├── Span: Fraud check (30ms)
│           └── Span: Charge card (100ms)  ← the bottleneck
```

Each span records: operation name, start/end time, status, attributes (HTTP method, status code, DB statement), and events (log messages within the span).

## Instrumenting with OpenTelemetry

Automatic instrumentation for Python:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint="http://otel-collector:4317")))
trace.set_tracer_provider(provider)

app = FastAPI()
FastAPIInstrumentor.instrument_app(app)
HTTPXClientInstrumentor().instrument()
```

This automatically creates spans for incoming HTTP requests and outgoing HTTP calls, propagating trace context via headers.

Manual spans for business logic:

```python
tracer = trace.get_tracer("order-service")

async def process_order(order_id: str):
    with tracer.start_as_current_span("process_order") as span:
        span.set_attribute("order.id", order_id)

        with tracer.start_as_current_span("validate_inventory"):
            inventory = await check_inventory(order_id)

        with tracer.start_as_current_span("charge_payment") as payment_span:
            payment_span.set_attribute("payment.amount", order.total)
            result = await payment_service.charge(order)

        span.set_attribute("order.status", "confirmed")
        return result
```

## Context propagation

W3C Trace Context headers pass trace identity between services:

```http
GET /payments/charge HTTP/1.1
traceparent: 00-abc123def456-789abc-01
tracestate: vendor=value
```

OpenTelemetry SDKs inject and extract automatically for supported HTTP clients and servers. For message queues, propagate context in message headers:

```python
from opentelemetry.propagate import inject, extract

# Producer: inject context into message headers
carrier = {}
inject(carrier)
kafka_producer.send("orders", value=payload, headers=list(carrier.items()))

# Consumer: extract context and create linked span
context = extract(dict(msg.headers()))
with tracer.start_as_current_span("process_order_event", context=context):
    process(json.loads(msg.value()))
```

Without context propagation in async messaging, traces break at queue boundaries.

## Sampling strategies

Tracing every request at 10,000 RPS generates unsustainable data volume.

**Head-based sampling** — decide at trace start:

```python
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

provider = TracerProvider(sampler=TraceIdRatioBased(0.1))  # 10% of traces
```

**Tail-based sampling** — collect all spans, export selectively (requires OpenTelemetry Collector):

```yaml
# otel-collector-config.yaml
processors:
  tail_sampling:
    policies:
      - name: errors
        type: status_code
        status_code: {status_codes: [ERROR]}
      - name: slow
        type: latency
        latency: {threshold_ms: 2000}
      - name: baseline
        type: probabilistic
        probabilistic: {sampling_percentage: 5}
```

Tail-based sampling keeps all error and slow traces while sampling 5% of normal traffic — the best of both worlds but requires collector infrastructure.

## Debugging with traces

Finding the 12-second checkout in Jaeger or Grafana Tempo:

1. Search by trace ID (from response header or access log).
2. Or search by service + min duration > 5s.
3. Open the trace waterfall.
4. Identify the widest span — that is where time was spent.
5. Click into that span's attributes for details.

Common findings:
- **Missing database index:** DB query span takes 8 seconds.
- **N+1 queries:** 50 sequential DB spans instead of one batch.
- **Slow external API:** payment service span waits 10 seconds.
- **Missing timeout:** span shows 30-second gap with no child spans.

## Adding trace ID to logs

Correlate traces with logs for deeper debugging:

```python
import logging
from opentelemetry import trace

class TraceIdFilter(logging.Filter):
    def filter(self, record):
        span = trace.get_current_span()
        ctx = span.get_span_context()
        record.trace_id = format(ctx.trace_id, '032x') if ctx.trace_id else 'none'
        return True

logging.getLogger().addFilter(TraceIdFilter())
# Log format: "%(asctime)s [%(trace_id)s] %(message)s"
```

Search logs by trace ID to see application logs alongside the trace waterfall.

Treat production rollout as a measured change: ship with observability, validate rollback, and review metrics 24 hours after deploy — patterns that look obvious in docs fail when skipped under release pressure.

## Common production mistakes

Teams get distributed tracing wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of distributed tracing fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When distributed tracing misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [OpenTelemetry tracing documentation](https://opentelemetry.io/docs/concepts/signals/traces/)
- [W3C Trace Context specification](https://www.w3.org/TR/trace-context/)
- [Jaeger distributed tracing](https://www.jaegertracing.io/docs/)
- [Grafana Tempo (trace storage)](https://grafana.com/docs/tempo/latest/)
- [OpenTelemetry Python auto-instrumentation](https://opentelemetry.io/docs/languages/python/automatic/)
