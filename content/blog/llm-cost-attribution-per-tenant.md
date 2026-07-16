---
title: "Per-Tenant LLM Cost Attribution"
slug: "llm-cost-attribution-per-tenant"
description: "Attribute LLM spend to tenants, features, and users: token metering, cost allocation tags, billing integration, and dashboards that answer 'who spent $500 yesterday?'"
datePublished: "2024-11-15"
dateModified: "2024-11-15"
tags: ["AI", "LLM", "Architecture", "Backend"]
keywords: "LLM cost attribution, per-tenant billing AI, token metering, LLM cost tracking, SaaS AI billing"
faq:
  - q: "What dimensions should LLM cost attribution track?"
    a: "Minimum: tenant_id, feature/use-case, model, input_tokens, output_tokens, timestamp. Add user_id for seat-based billing, request_id for debugging, and environment (prod/staging) to exclude test spend. Without feature tags, you know tenant spend but can't optimize the expensive workflow."
  - q: "How do I calculate cost when providers change pricing?"
    a: "Maintain a pricing table keyed by model and date range. Apply pricing at log time using the rate effective on that date — don't retroactively recalculate. Store raw token counts permanently; compute dollar amounts at query time from the pricing table so price updates don't require re-ingesting logs."
  - q: "Should I pass LLM costs directly to customers?"
    a: "Depends on your model. Usage-based billing (cost + markup) works for developer tools and API products. Included quotas with overage charges work for SaaS apps. Either way, show customers a usage dashboard — surprise invoices churn accounts even when the math is fair."
---

Finance asked which customer drove the 4x spike in OpenAI spend last Tuesday. Without per-tenant attribution, the answer is "we're not sure — maybe the new feature?" With proper metering, it's "Tenant X's document summarization job after they uploaded 12,000 PDFs." Cost attribution isn't accounting trivia — it's how you price products, identify abuse, and justify infrastructure decisions to people who sign checks.

## The metering event

Emit one event per LLM call (or per batch line item):

```python
@dataclass
class LLMUsageEvent:
    timestamp: datetime
    tenant_id: str
    user_id: str | None
    feature: str              # "support_chat", "doc_summary"
    model: str
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int  # provider prompt cache hits
    latency_ms: int
    request_id: str
    status: str               # "success", "error", "timeout"
```

Sink to ClickHouse, BigQuery, or TimescaleDB — not your application Postgres unless volume is low.

## Cost calculation

```python
PRICING = {
    ("gpt-4o", "2024-11-01"): {"input": 2.50, "output": 10.00},  # per 1M tokens
    ("gpt-4o-mini", "2024-11-01"): {"input": 0.15, "output": 0.60},
}

def compute_cost(event: LLMUsageEvent) -> Decimal:
    rates = lookup_pricing(event.model, event.timestamp)
    billable_input = event.input_tokens - event.cached_input_tokens
    cached_rate = rates["input"] * 0.5  # provider discount
    return (
        billable_input * rates["input"] / 1_000_000
        + event.cached_input_tokens * cached_rate / 1_000_000
        + event.output_tokens * rates["output"] / 1_000_000
    )
```

Include embedding costs, reranker calls, and moderation API calls — they're part of tenant COGS.

## Instrumentation in the gateway

Centralize in your model gateway so every service gets attribution for free:

```python
async def complete(request: CompletionRequest) -> Response:
    start = time.monotonic()
    try:
        response = await provider.complete(request)
        await emit_usage(LLMUsageEvent(
            tenant_id=request.tenant_id,
            feature=request.feature,
            model=request.model,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            cached_input_tokens=getattr(response.usage, "cached_tokens", 0),
            latency_ms=int((time.monotonic() - start) * 1000),
            request_id=request.id,
            status="success",
        ))
        return response
    except Exception as e:
        await emit_usage(..., status="error")
        raise
```

Never rely on each team to log their own calls — someone will forget.

## Aggregation queries

Questions your data should answer in seconds:

```sql
-- Top tenants by spend yesterday
SELECT tenant_id, sum(cost_usd) AS spend
FROM llm_usage
WHERE date = yesterday()
GROUP BY tenant_id
ORDER BY spend DESC
LIMIT 20;

-- Cost by feature for one tenant
SELECT feature, sum(cost_usd), sum(input_tokens + output_tokens)
FROM llm_usage
WHERE tenant_id = $1 AND date >= $2
GROUP BY feature;
```

Pre-aggregate daily rollups for dashboard speed. Keep raw events for drill-down.

## Billing integration

Map usage to your billing system:

| Billing model | Implementation |
|---------------|----------------|
| Flat SaaS fee | Attribution for internal cost only |
| Included quota + overage | Sum tokens per billing period, charge above threshold |
| Pure usage | Invoice = sum(cost_usd) × markup |
| Credits | Deduct from prepaid balance per request |

Show customers the same numbers internally — discrepancies erode trust.

## Anomaly detection

Alert when:

- Tenant daily spend > 3× trailing 7-day average
- Single feature spikes (runaway agent loop)
- Staging environment exceeds prod spend (test gone wrong)
- Error rate high but spend high (retry storm)

```python
if tenant.spend_today > tenant.avg_daily_spend * 3:
    alert(f"Spend anomaly: {tenant.id}", severity="P2")
```

## Internal chargeback

Even without customer billing, attribute costs to teams:

- Tag `team` or `cost_center` on features
- Monthly report: eng platform vs product vs support AI
- Drives decisions on model tier, caching investment, batch vs real-time

## Privacy in usage logs

Usage events contain tenant IDs and potentially prompt metadata. Don't log full prompts in the metering pipeline — link via request_id to trace store with retention policies.

## Token metering implementation

Capture usage at the SDK middleware layer:

```python
from dataclasses import dataclass
import time

@dataclass
class UsageEvent:
    tenant_id: str
    feature: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    request_id: str
    timestamp: float

async def metered_completion(tenant_id: str, feature: str, **kwargs):
    start = time.time()
    response = await openai_client.chat.completions.create(**kwargs)
    event = UsageEvent(
        tenant_id=tenant_id,
        feature=feature,
        model=kwargs["model"],
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
        cost_usd=calculate_cost(kwargs["model"], response.usage),
        request_id=response.id,
        timestamp=start,
    )
    await usage_store.insert(event)
    return response
```

Wrap every LLM call — don't rely on post-hoc log parsing for billing accuracy.

## Cost allocation dashboard

Aggregate usage events for finance and eng visibility:

```sql
-- Daily cost by tenant and feature
SELECT
    tenant_id,
    feature,
    model,
    DATE(timestamp) AS day,
    SUM(input_tokens + output_tokens) AS total_tokens,
    SUM(cost_usd) AS daily_cost_usd,
    COUNT(*) AS request_count
FROM usage_events
WHERE timestamp >= NOW() - INTERVAL '30 days'
GROUP BY 1, 2, 3, 4
ORDER BY daily_cost_usd DESC;
```

Expose to tenants via API for self-service cost visibility. Internal teams see cost by feature for optimization decisions.

## Budget enforcement

Hard and soft limits per tenant:

```python
async def check_budget(tenant_id: str) -> None:
    spend = await usage_store.get_monthly_spend(tenant_id)
    budget = await tenant_config.get_budget(tenant_id)

    if spend >= budget.hard_limit:
        raise BudgetExceeded(f"Tenant {tenant_id} exceeded monthly budget")
    if spend >= budget.soft_limit:
        await alert_tenant(tenant_id, f"80% of monthly budget used")
        # Downgrade to cheaper model for remaining requests
        return ModelTier.ECONOMY
    return ModelTier.STANDARD
```

Soft limit at 80%: alert + downgrade to cheaper model. Hard limit: block requests. Prevents surprise bills from runaway agent loops.

## Failure modes

- **No per-request metering** — post-hoc log parsing misses retries and streaming
- **Full prompts in usage logs** — PII in billing pipeline; compliance violation
- **No budget enforcement** — tenant runs up unlimited bill
- **Cost calculated from list price** — actual cost differs with volume discounts
- **No anomaly detection** — runaway loop discovered at month-end

## Production checklist

- UsageEvent captured at SDK middleware for every LLM call
- Tenant ID and feature tag on every event
- No full prompts in metering pipeline (request_id links to trace store)
- Soft budget alert at 80%; hard limit blocks requests
- Daily cost dashboard by tenant and feature
- Anomaly alert: daily spend >3× trailing 7-day average

## Resources

- [OpenAI usage API](https://platform.openai.com/docs/api-reference/usage)
- [Anthropic usage and cost tracking](https://docs.anthropic.com/en/api/usage-cost-api)
- [ClickHouse for analytics workloads](https://clickhouse.com/docs/en/intro)
- [LangSmith cost tracking](https://docs.smith.langchain.com/observability/how_to_guides/cost_tracking)
- [FinOps Foundation AI cost principles](https://www.finops.org/)
