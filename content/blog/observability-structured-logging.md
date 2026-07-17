---
title: "Structured Logging Done Right"
slug: "observability-structured-logging"
description: "Implement structured logging for production: JSON format, field conventions, log levels, correlation IDs, and querying with Loki or Elasticsearch."
datePublished: "2025-10-15"
dateModified: "2026-07-17"
tags:
keywords: "structured logging, JSON logging, log correlation, OpenTelemetry logs, Loki structured logs, log levels best practices, production logging"
faq:
  - q: "Why use structured logging instead of plain text?"
    a: "Structured logs (JSON) make fields machine-queryable. Searching '{\\\"level\\\":\\\"error\\\",\\\"user_id\\\":\\\"42\\\"}' in Loki or Elasticsearch takes milliseconds. Searching plain text 'error.*user.*42' with regex is slow, fragile, and misses variations. At scale, unstructured logs are effectively unsearchable."
  - q: "What fields should every log entry include?"
    a: "Minimum: timestamp (ISO 8601), level, message, service name. Add trace_id for correlation with distributed traces, request_id for per-request grouping, and user_id or tenant_id where applicable. Use OpenTelemetry semantic conventions for field names."
  - q: "How verbose should production logs be?"
    a: "INFO for business events (order created, payment processed). WARN for recoverable anomalies (retry succeeded, deprecated API used). ERROR for failures requiring attention (payment declined, database timeout). DEBUG only in development—never in production unless temporarily enabled per-request."
---
`grep "error" production.log` returns 50,000 lines. Half are stack traces from a dependency. A third are retry warnings logged at ERROR level. The actual root cause—"connection refused to payment-db:5432"—is buried on line 34,221. Structured logging does not prevent bad logs, but it makes good logs findable. JSON fields are queryable. Correlation IDs link scattered entries into one request story. Consistent levels mean your alerts fire on real problems.

## JSON log format

```json
{
  "timestamp": "2025-10-15T14:32:01.234Z",
  "level": "error",
  "message": "Payment processing failed",
  "service": "checkout-api",
  "trace_id": "abc123def456",
  "span_id": "789ghi",
  "request_id": "req-uuid-42",
  "user_id": "user-99",
  "error": {
    "type": "PaymentDeclinedError",
    "message": "Card declined: insufficient funds",
    "stack": "PaymentDeclinedError: Card declined...\n  at processPayment..."
  },
  "context": {
    "order_id": "ord-123",
    "amount": 49.99,
    "currency": "USD",
    "payment_method": "card"
  }
}
```

Every field is a query target. `level="error" AND context.order_id="ord-123"` finds this exact failure.

## Implementation patterns

**Node.js (pino):**

```javascript
import pino from "pino";

const logger = pino({
  level: process.env.LOG_LEVEL || "info",
  formatters: {
    level: (label) => ({ level: label }),
  },
  base: { service: "checkout-api" },
});

logger.info({ order_id: "ord-123", amount: 49.99 }, "Order created");
logger.error({ err, order_id: "ord-123" }, "Payment processing failed");
```

Pino is 5–10x faster than Winston because it serializes JSON without formatting overhead.

**Python (structlog):**

```python
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
)

log = structlog.get_logger(service="checkout-api")
log.info("order_created", order_id="ord-123", amount=49.99)
log.error("payment_failed", order_id="ord-123", error=str(exc), exc_info=True)
```

**Go (slog — stdlib):**

```go
logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
    Level: slog.LevelInfo,
}))

logger.Info("order created",
    "order_id", "ord-123",
    "amount", 49.99,
    "service", "checkout-api",
)
```

## Log levels: use them correctly

| Level | When | Example |
|-------|------|---------|
| DEBUG | Development only | SQL query text, cache hits |
| INFO | Normal business events | Order created, user logged in |
| WARN | Recoverable problems | Retry succeeded, rate limit approaching |
| ERROR | Failures needing action | Payment failed, DB connection lost |
| FATAL | Process cannot continue | Config missing, port in use |

```python
# BAD — everything is ERROR
logger.error("Retrying payment, attempt 2")  # this is WARN or INFO
logger.error("User not found")               # this is INFO (expected case)
logger.error("Payment declined")            # this IS error (correct)

# GOOD
logger.info("user_not_found", user_id=uid)       # expected 404
logger.warning("payment_retry", attempt=2)        # recoverable
logger.error("payment_failed", order_id=oid, err) # needs attention
```

Alert on ERROR rate, not individual errors. Expected errors (404, validation failures) should be INFO.

## Correlation IDs

```javascript
import { trace, context } from "@opentelemetry/api";
import { AsyncLocalStorage } from "node:async_hooks";

const requestStore = new AsyncLocalStorage();

app.use((req, res, next) => {
  const requestId = req.headers["x-request-id"] || crypto.randomUUID();
  const span = trace.getSpan(context.active());
  const traceId = span?.spanContext().traceId;

  requestStore.run({ requestId, traceId }, () => {
    res.setHeader("x-request-id", requestId);
    next();
  });
});

function getLogger() {
  const store = requestStore.getStore();
  return logger.child({
    request_id: store?.requestId,
    trace_id: store?.traceId,
  });
}
```

Every log in a request automatically includes `request_id` and `trace_id`.

## Querying in Loki (LogQL)

```logql
# Errors for a specific order
{service="checkout-api"} | json | level="error" | context_order_id="ord-123"

# Error rate over 5 minutes
sum(rate({service="checkout-api"} | json | level="error" [5m]))

# All logs for a trace
{service=~".+"} | json | trace_id="abc123def456"
```

## What not to log

- **Passwords, tokens, API keys** — even in error paths.
- **Full credit card numbers** — PCI violation.
- **Personal data you don't need** — email, phone (log user_id instead).
- **Request/response bodies at INFO** — log at DEBUG with sampling, or not at all.
- **Health check requests** — filter at the collector.

```javascript
const SENSITIVE_KEYS = ["password", "token", "secret", "authorization", "card_number"];

function redact(obj) {
  const cleaned = { ...obj };
  for (const key of Object.keys(cleaned)) {
    if (SENSITIVE_KEYS.some(s => key.toLowerCase().includes(s))) {
      cleaned[key] = "[REDACTED]";
    }
  }
  return cleaned;
}
```

## Sampling high-volume logs

At 10,000 req/s, logging every request at INFO generates 864 million entries per day. Sample:

```javascript
if (Math.random() < 0.01) {
  logger.info({ path: req.path, duration }, "request completed");
}
```

Always log errors and slow requests (duration > threshold) at 100%.

## Dynamic log level per request

Support toggling DEBUG for one user session via header `X-Debug-Session: <signed-token>` validated at edge—avoid global DEBUG in production. Signed token expires in 15 minutes; all debug logs include `debug_session_id` for audit.

## Log shipping backpressure

When Loki ingest falls behind, loggers block or drop—configure async appenders with bounded queue and `drop_on_full` policy for INFO while ERROR sync-writes. Monitor agent buffer depth.

## OpenTelemetry logs vs JSON stdout

Kubernetes collects stdout JSON; OTel logs exporter adds vendor flexibility. Either works—do not duplicate both paths without sampling. Single exit point reduces cost and schema drift.

## Log-based metrics caution

Loki metric queries (`metric queries`) on high-cardinality labels recreate cardinality problem in logs backend—prefer Prometheus counters for rates, logs for drill-down only.

## Exception formatting

Language stack traces as structured `error.stack` array of frames `{file, line, function}` parse better in SIEM than multiline string—optional enhancement for JVM and .NET loggers.

## Resources

- [OpenTelemetry logs data model](https://opentelemetry.io/docs/specs/otel/logs/data-model/) — standard log field conventions
- [Grafana Loki LogQL](https://grafana.com/docs/loki/latest/query/) — structured log querying
- [pino documentation](https://getpino.io/) — fast Node.js JSON logger
- [structlog documentation](https://www.structlog.org/) — structured logging for Python
- [Go slog package](https://pkg.go.dev/log/slog) — standard library structured logging

## Production notes for LLM stacks

When `observability-structured-logging` sits on an inference or RAG path, treat user prompts and retrieved chunks as untrusted input. Log correlation IDs and policy decisions—not raw prompts—in production telemetry. Gate risky operations behind explicit authorization at the gateway, not inside ad-hoc tool handlers.

Roll out changes with shadow mode first: record what **would** have happened under the new rule without blocking traffic. Compare deny rates, latency impact, and false positives for at least one business week before enforcing. Pair enforcement with a runbook entry: symptom, dashboard, rollback (feature flag or config), and owner.

Load-test with production-shaped concurrency. LLM workloads burst differently from CRUD APIs—tail latency and token throttling dominate. If `structured logging done right` protects an invariant (security, billing, data residency), prove the invariant with an automated test that fails CI when someone removes the check.

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


For `observability-structured-logging`, treat observability and security controls as part of the user experience: silent failures erode trust faster than explicit error messages. Instrument deny paths, measure tail latency, and review dashboards with on-call weekly.

For `observability-structured-logging`, treat observability and security controls as part of the user experience: silent failures erode trust faster than explicit error messages. Instrument deny paths, measure tail latency, and review dashboards with on-call weekly.

For `observability-structured-logging`, treat observability and security controls as part of the user experience: silent failures erode trust faster than explicit error messages. Instrument deny paths, measure tail latency, and review dashboards with on-call weekly.

For `observability-structured-logging`, treat observability and security controls as part of the user experience: silent failures erode trust faster than explicit error messages. Instrument deny paths, measure tail latency, and review dashboards with on-call weekly.
