---
title: "Building LLM Cost Dashboards"
slug: "llm-observability-cost-dashboards"
description: "Build LLM cost dashboards that drive decisions: metrics to track, Grafana/Datadog patterns, anomaly alerts, unit economics, and the views finance and engineering both need."
datePublished: "2024-12-21"
dateModified: "2024-12-21"
tags: ["AI", "LLM", "DevOps", "Architecture"]
keywords: "LLM cost dashboard, LLM observability, token cost monitoring, LLM spend Grafana, GenAI cost metrics"
faq:
  - q: "What are the essential metrics for an LLM cost dashboard?"
    a: "Daily/weekly spend (total and per tenant), cost per request by feature, token breakdown (input vs output vs cached), cost per successful task completion, model mix distribution, and cache hit rate. Without feature-level tags, you know you're spending money but can't optimize anything."
  - q: "How do I show LLM costs to non-technical stakeholders?"
    a: "Translate tokens into dollars, show trends not absolutes, compare cost per outcome (cost per resolved support ticket, cost per generated document), and benchmark against budget. Executives care about unit economics and trajectory — not tokenizer details."
  - q: "Should cost dashboards be real-time or daily aggregates?"
    a: "Both. Real-time (or 5-minute granularity) for anomaly detection and runaway loop alerts. Daily aggregates for trend analysis and billing reconciliation. Real-time every LLM call is expensive to query — pre-aggregate into rollups."
---

The Slack message said "AI costs seem high." Nobody could say how high, which feature, or since when. The OpenAI dashboard showed account-level spend; it didn't attribute the document summarization spike to one enterprise tenant uploading a archive folder. An LLM cost dashboard isn't a vanity chart — it's the instrument panel that tells you whether to cache, downgrade models, or call a customer about their usage.

## Metrics hierarchy

**Level 1 — Executive (weekly review)**:

- Total LLM spend vs budget
- Cost per active tenant (unit economics)
- MoM growth rate
- Top 5 cost drivers by feature

**Level 2 — Engineering (daily)**:

- Spend by feature, model, environment
- Token volume: input / output / cached
- Cost per request p50/p95
- Cache hit rate and estimated savings

**Level 3 — Debugging (real-time)**:

- Per-request cost with trace ID
- Anomaly alerts (>3× normal rate)
- Error/retry cost (failed calls still cost tokens)

## Data pipeline

```
LLM gateway → usage events → Kafka/queue → ClickHouse/TimescaleDB → Grafana/Datadog
```

Event schema (from metering layer):

```sql
CREATE TABLE llm_usage (
    timestamp DateTime64(3),
    tenant_id UUID,
    feature LowCardinality(String),
    model LowCardinality(String),
    input_tokens UInt32,
    output_tokens UInt32,
    cached_tokens UInt32,
    cost_usd Decimal(10, 6),
    latency_ms UInt32,
    status LowCardinality(String),
    request_id UUID
) ENGINE = MergeTree()
ORDER BY (tenant_id, feature, timestamp);
```

Materialized views for rollups:

```sql
CREATE MATERIALIZED VIEW llm_daily_by_feature
ENGINE = SummingMergeTree()
ORDER BY (date, tenant_id, feature)
AS SELECT
    toDate(timestamp) AS date,
    tenant_id,
    feature,
    sum(cost_usd) AS total_cost,
    sum(input_tokens + output_tokens) AS total_tokens,
    count() AS request_count
FROM llm_usage
GROUP BY date, tenant_id, feature;
```

## Dashboard panels

**Panel 1: Spend trend (stacked area)**
Feature breakdown over 30 days. Shows which feature grew.

**Panel 2: Model mix (pie/bar)**
GPT-4o vs mini vs embedding models. Tracks downgrade progress.

**Panel 3: Unit economics (table)**
Cost per completed task by feature. Combines cost data with outcome events.

**Panel 4: Cache impact (stat + trend)**
Hit rate, estimated savings = hits × avg_cost_per_miss.

**Panel 5: Top tenants (bar)**
Spend by tenant, filterable. Catches runaway usage.

**Panel 6: Anomaly feed (table)**
Auto-detected spikes with tenant, feature, magnitude.

## Grafana example

```json
{
  "targets": [{
    "rawSql": "SELECT date, feature, sum(total_cost) FROM llm_daily_by_feature WHERE date >= now() - interval 30 day GROUP BY date, feature ORDER BY date"
  }],
  "type": "timeseries",
  "title": "Daily LLM Spend by Feature"
}
```

Use variables for `$tenant_id` and `$environment` filtering.

## Alerting rules

```yaml
alerts:
  - name: tenant_spend_spike
    condition: tenant_daily_spend > 3 * tenant_7d_avg
    severity: P2
    notify: [eng-ai-oncall, customer-success]

  - name: daily_budget_80pct
    condition: org_daily_spend > daily_budget * 0.8
    severity: P1
    notify: [eng-lead, finance]

  - name: cache_hit_rate_drop
    condition: cache_hit_rate < 0.20 for 1h
    severity: P3
    notify: [eng-ai]
```

Alert on rate of change, not just absolutes — a steady $500/day might be fine; $500 after $50/day is not.

## Unit economics calculation

```python
def cost_per_outcome(feature: str, period: str) -> float:
    total_cost = sum_cost(feature, period)
    outcomes = count_successful_completions(feature, period)
    return total_cost / max(outcomes, 1)
```

"Support chat costs $0.42 per resolved conversation" is actionable. "$500/day on support chat" is not.

## FinOps integration

- Tag cloud costs with LLM provider invoices for reconciliation
- Compare provider dashboard totals vs your metering (should match within 2%)
- Monthly review: budget vs actual, forecast next month from trend
- Chargeback reports for internal teams or customer billing

## Common dashboard mistakes

- Showing token counts without dollar amounts (meaningless to finance)
- No feature dimension (can't optimize)
- Including staging/test traffic in production dashboards
- No link from cost spike to trace/request for investigation

## Dashboard structure for LLM ops

Organize dashboards in three tiers:

**Tier 1 — Executive (daily review):**
- Total daily spend vs budget
- Cost per resolved outcome by feature
- Week-over-week spend trend

**Tier 2 — Engineering (real-time):**
- Token usage by model, feature, tenant
- P99 latency by model
- Error rate and retry rate
- Cache hit rate

**Tier 3 — Investigation (on-demand):**
- Trace detail for expensive requests (>10k tokens)
- Cost spike correlation with deployment events
- Per-tenant anomaly detection

```sql
-- Tier 1 query: daily spend by feature
SELECT
    DATE(timestamp) AS day,
    feature,
    SUM(cost_usd) AS daily_cost,
    SUM(cost_usd) / COUNT(DISTINCT tenant_id) AS cost_per_tenant
FROM llm_usage_events
WHERE timestamp >= NOW() - INTERVAL '30 days'
GROUP BY 1, 2
ORDER BY daily_cost DESC;
```

## Cost anomaly detection

Alert on rate of change, not just absolute thresholds:

```python
def detect_cost_anomaly(tenant_id: str, feature: str) -> bool:
    today = get_spend(tenant_id, feature, period="today")
    avg_7d = get_avg_spend(tenant_id, feature, days=7)
    if today > avg_7d * 3 and today > 10.0:  # 3× average AND >$10
        return True
    return False

# Common anomaly causes:
# - Runaway agent loop (retry storm)
# - New feature deployed without token limits
# - Staging traffic in production metering
# - Prompt change increasing output length
```

Link anomaly alert directly to trace store — click alert → see expensive requests → identify root cause.

## Token efficiency metrics

Track efficiency alongside cost:

```python
EFFICIENCY_METRICS = {
    "tokens_per_resolved_outcome": total_tokens / successful_completions,
    "cache_hit_rate": cache_hits / total_requests,
    "retry_rate": retried_requests / total_requests,
    "truncation_rate": truncated_requests / total_requests,
    "avg_output_tokens": sum_output_tokens / total_requests,
}
```

High retry rate indicates prompt or model issue causing failures and re-attempts. High truncation rate indicates context window management failure.

## Failure modes

- **Token counts without dollar amounts** — meaningless to finance stakeholders
- **No feature dimension** — can't identify which feature to optimize
- **Staging traffic in production dashboard** — inflated costs; filter by environment
- **No anomaly detection** — cost spike discovered at month-end invoice
- **Dashboard without trace link** — can see spike, can't investigate cause

## Production checklist

- Three-tier dashboard: executive, engineering, investigation
- Cost in USD alongside token counts on all panels
- Feature and tenant dimensions on every metric
- Anomaly alert: daily spend >3× 7-day average
- Trace link from cost spike alert to expensive request details
- Staging/test traffic excluded from production cost dashboards

## Resources

- [OpenAI usage dashboard and API](https://platform.openai.com/usage)
- [Grafana time series dashboards](https://grafana.com/docs/grafana/latest/visualizations/panels-visualizations/visualizations/time-series/)
- [ClickHouse for real-time analytics](https://clickhouse.com/docs/en/intro)
- [Datadog LLM observability](https://docs.datadoghq.com/llm_observability/)
- [OpenTelemetry GenAI metrics](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-metrics/)
