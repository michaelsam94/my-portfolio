---
title: "Usage Metering Aggregation for Agent Billing"
slug: "agent-usage-metering-aggregation"
description: "Aggregate token, tool, and compute meters for agent SaaS billing: event schemas, idempotent rollups, Stripe usage records, and reconciliation against raw telemetry."
datePublished: "2025-04-27"
dateModified: "2026-07-17"
tags: ["AI Agents", "Billing", "Metering", "SaaS"]
keywords: "agent usage metering, token aggregation billing, Stripe metered usage agents, usage records reconciliation"
faq:
  - q: "What should agent metering events capture at minimum?"
    a: "tenant_id, meter_name, quantity (numeric), timestamp (UTC), idempotency_key, dimensions (model, agent_sku, region). Optional: run_id for dispute debugging. Never put PII or prompt content in billing events."
  - q: "At what granularity should token usage aggregate before Stripe?"
    a: "Roll up to hourly or daily per tenant per meter for API rate limits, but emit raw events immediately to your ledger. Stripe Billing Meters accept high-cardinality identifiers — batch usage record API calls to avoid throttling."
  - q: "How do you handle retries without double billing?"
    a: "Idempotency keys on every event: hash(tenant_id, run_id, meter, window_start). Dedupe in stream processor and again at Stripe submission. Reconciliation job compares ledger sums to Stripe dashboard daily."
  - q: "Tool calls vs tokens — one meter or many?"
    a: "Separate meters: input_tokens, output_tokens, tool_invocations, premium_tool_surcharge. Plans mix included allowances per meter. Bundling into one 'credit' obscures margin leaks when tool costs spike."
---

Agent SaaS pricing slides say "per seat plus usage" — engineering has to define what a **usage event** is when one customer run spans three model calls, two code interpreter minutes, and a retrieval index query. Metering aggregation turns firehose telemetry into invoice lines without double-charging retries or losing margin on unbilled tool surcharges.

## Event schema design

Immutable usage events append to Kafka / Kinesis / Pub/Sub:

```json
{
  "event_id": "01JABC...",
  "idempotency_key": "tenant_42:run_9f3:output_tokens:2026-07-17T10:00Z",
  "tenant_id": "tenant_42",
  "meter": "output_tokens",
  "quantity": 1842,
  "unit": "tokens",
  "occurred_at": "2026-07-17T10:04:32.118Z",
  "dimensions": {
    "model": "gpt-4o",
    "agent_sku": "support_bot",
    "region": "us-east-1"
  },
  "run_id": "run_9f3"
}
```

Schema rules:

- `quantity` always positive; refunds are separate `adjustment` events with negative quantity.
- `occurred_at` is business time, not processor lag time.
- `dimensions` capped at 5 keys — Stripe metadata limits apply downstream.

## Ingestion and idempotent rollup

```python
from redis import Redis

redis = Redis()
DEDUPE_TTL = 86400 * 35  # cover billing period + buffer

def ingest_usage(event: dict) -> bool:
    key = f"usage:dedupe:{event['idempotency_key']}"
    if not redis.set(key, "1", nx=True, ex=DEDUPE_TTL):
        return False  # duplicate
    usage_ledger.insert(event)
    rollup_buffer.add(event)
    return True
```

Flink / Materialize window:

```sql
SELECT
  tenant_id,
  meter,
  tumble_start(occurred_at, INTERVAL '1' HOUR) AS window_start,
  SUM(quantity) AS total_qty
FROM usage_events
GROUP BY tenant_id, meter, tumble(occurred_at, INTERVAL '1' HOUR);
```

## Mapping meters to Stripe Billing

Stripe Meters (2024+ model):

```python
import stripe

def report_hourly_usage(tenant_id: str, meter_name: str, qty: int, hour: datetime):
    stripe.billing.MeterEvent.create(
        event_name=meter_name,
        payload={
            "stripe_customer_id": customer_id_for(tenant_id),
            "value": str(qty),
        },
        timestamp=int(hour.timestamp()),
        identifier=f"{tenant_id}:{meter_name}:{hour.isoformat()}",
    )
```

`identifier` must be unique — reuse causes silent dedupe on Stripe side (desired).

| Internal meter | Stripe price linkage | Typical plan |
|----------------|---------------------|--------------|
| input_tokens | Price meter `input_tokens` | Included 1M, then tiered |
| output_tokens | Price meter `output_tokens` | Tiered |
| tool_invocations | Price meter `tools` | Per 1k calls |
| storage_gb_hours | Price meter `vector_storage` | Add-on |

## Multi-model cost allocation

Different models, different COGS — aggregate separately even if customer sees one bill:

```python
COGS_PER_1K = {
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "claude-3-5-sonnet": {"input": 0.003, "output": 0.015},
}

def margin_report(tenant_id: str, period: str) -> dict:
    usage = ledger.sum_by_model(tenant_id, period)
    revenue = stripe.invoices.retrieve_for(tenant_id, period).total
    cogs = sum(
        (u.input_tokens / 1000 * COGS_PER_1K[u.model]["input"]
         + u.output_tokens / 1000 * COGS_PER_1K[u.model]["output"])
        for u in usage
    )
    return {"revenue": revenue, "cogs": cogs, "margin": revenue - cogs}
```

Finance uses this; customers never see model-level lines unless enterprise contract requires it.

## Reconciliation job

Nightly cron:

```python
def reconcile(date: str):
    internal = ledger.daily_totals(date)
    stripe_totals = stripe_api.meter_summaries(date)
    for (tenant, meter), internal_qty in internal.items():
        stripe_qty = stripe_totals.get((tenant, meter), 0)
        drift = abs(internal_qty - stripe_qty) / max(internal_qty, 1)
        if drift > 0.001:  # 0.1%
            alerts.publish("billing_drift", tenant, meter, internal_qty, stripe_qty)
```

Drift sources: clock skew on `timestamp`, duplicate idempotency key collisions, failed Stripe API retries without ledger rollback.

## Included allowances and overage

Plan engine sits between raw meters and Stripe:

```python
def billable_quantity(tenant_id: str, meter: str, raw_qty: int, period: str) -> int:
    allowance = plans.included(tenant_id, meter, period)
    consumed = ledger.period_to_date(tenant_id, meter, period)
    remaining = max(0, allowance - consumed)
    billable = max(0, raw_qty - remaining)
    return billable
```

Only report **billable** quantities to Stripe; internal ledger keeps gross for analytics.

## Agent-specific meters

Don't forget hidden costs:

| Meter | Source |
|-------|--------|
| embedding_tokens | Indexing pipeline |
| rerank_calls | Cross-encoder invocations |
| sandbox_cpu_seconds | Code interpreter |
| egress_gb | Large tool payloads |

Product may not pass through all — but engineering must see them for pricing decisions.

## Dispute handling

Support needs run-level drill-down:

```sql
SELECT run_id, meter, sum(quantity) AS qty
FROM usage_events
WHERE tenant_id = $1 AND run_id = $2
GROUP BY run_id, meter;
```

Retain raw events 13 months minimum for SOC2 / tax audit alignment.

## Resources

- [Stripe — Billing Meters documentation](https://docs.stripe.com/billing/subscriptions/usage-based/recording-usage)
- [Stripe — Idempotent requests](https://docs.stripe.com/api/idempotent_requests)
- [OpenMeter — usage-based billing patterns](https://openmeter.io/docs)
- [SOC 2 — audit trail requirements for billing systems](https://www.aicpa.org/resources/landing/system-and-organization-controls-soc-suite-of-services)

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

