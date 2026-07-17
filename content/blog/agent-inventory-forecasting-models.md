---
title: "AI Agents: Inventory Forecasting Models"
slug: "agent-inventory-forecasting-models"
description: "Inventory Forecasting Models: production patterns for ai teams — design, implementation, testing, security, and operations."
datePublished: "2025-08-01"
dateModified: "2025-08-01"
tags: ["AI", "Agent", "Inventory"]
keywords: "agent, inventory, forecasting, models, ai, production, engineering, architecture"
faq:
  - q: "Which forecasting models work best when agents drive replenishment decisions?"
    a: "Start with hierarchical statistical baselines (ETS, Prophet, or lightweight ARIMA) at SKU-location grain, then add gradient-boosted models for feature-rich catalogs. LLM agents should consume forecast intervals and confidence bands—not raw point estimates—so procurement tools can apply safety-stock rules without hallucinating quantities."
  - q: "How do agent-triggered forecasts differ from traditional demand planning?"
    a: "Agents introduce conversational context: a buyer asking 'do we have enough for the promo?' needs same-day horizon updates, not monthly MRP runs. Agent pipelines must expose idempotent forecast APIs keyed by SKU, warehouse, and horizon, with explicit staleness timestamps so the LLM never cites a forecast computed before yesterday's spike."
  - q: "What data quality issues break inventory forecasting in agent workflows?"
    a: "Silent stock adjustments, duplicate SKU aliases, missing lead times, and promotions not tagged in history. Agents amplify bad inputs by confidently recommending purchase orders. Enforce data contracts upstream—validated lead times, promotion flags, and outlier capping—before any model output reaches a tool call."
  - q: "Should agents pick the forecasting model automatically?"
    a: "No. Agents should route to a governed model registry with per-category defaults (fast movers vs long-tail, perishable vs durable). Automatic model selection without offline backtests causes regime switches mid-quarter. Let the agent explain which model tier was used and why, pulling metadata from the registry—not improvising."
---
A procurement agent recommended ordering 12,000 units of a SKU that had sold 400 units in the prior ninety days. The root cause was not model complexity—it was a stale Prophet run from before a product discontinuation, combined with an LLM that treated the point forecast as gospel. Inventory forecasting for agent platforms is not "plug in ML and let the bot order." It is a governed pipeline: clean signals, tiered models, uncertainty bands, and tool contracts that refuse to act on expired or low-confidence predictions.

When agents sit between planners and ERP systems, forecasting becomes a **real-time decision service** with audit requirements. This deep dive covers model selection, feature engineering, serving architecture, and the guardrails that keep autonomous replenishment suggestions from becoming expensive mistakes.

## Forecast grain and hierarchy

Inventory forecasts fail when grain is ambiguous. Define the unit of prediction explicitly:

| Grain | Typical horizon | Agent use case |
|-------|-----------------|----------------|
| SKU × warehouse | 7–90 days | Replenishment, transfer orders |
| SKU × region | 14–180 days | Capacity planning, promo prep |
| Category × DC | 30–365 days | Slotting, vendor negotiations |

Hierarchical reconciliation matters: category totals should not contradict summed SKU forecasts by 30%. Use MinT or bottom-up reconciliation so agents citing regional numbers do not contradict warehouse-level tools in the same conversation.

```
Sales history ──▶ Feature store ──▶ Model tier router ──▶ Forecast service
       │                  │                  │                    │
       │                  │                  │                    ▼
       │                  │                  │            {p10, p50, p90, as_of}
       │                  │                  │                    │
       ▼                  ▼                  ▼                    ▼
   ERP adjustments   Promo calendar    Registry metadata    Agent tools (PO, transfer)
```

## Model tiers for production

Avoid one model for everything. A practical registry:

**Tier A — Statistical baselines (fast movers).** ETS or Prophet on daily demand with seasonality flags. Cheap to retrain nightly; interpretable; strong for stable SKUs with two-plus years of history.

**Tier B — Gradient boosting (heterogeneous catalogs).** LightGBM or XGBoost on lag features, price changes, promo indicators, and competitor signals. Handles intermittent demand better when paired with zero-inflated targets or Croston-style baselines for comparison.

**Tier C — Deep sequence models (selective).** Temporal Fusion Transformer or N-BEATS only where SKU count × revenue justifies GPU retraining and MLOps overhead. Never default here—operational cost is high and explainability is harder for procurement audits.

```python
from dataclasses import dataclass
from datetime import date, timedelta
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing


@dataclass
class ForecastResult:
    sku: str
    warehouse_id: str
    horizon_days: int
    p50: list[float]
    p10: list[float]
    p90: list[float]
    model_id: str
    as_of: date
    mape_backtest: float


def forecast_sku_ets(
    history: pd.Series,
    sku: str,
    warehouse_id: str,
    horizon: int = 28,
) -> ForecastResult:
    """Tier A baseline with simple interval from residual std."""
    model = ExponentialSmoothing(
        history,
        trend="add",
        seasonal="add",
        seasonal_periods=7,
    ).fit()
    p50 = model.forecast(horizon).tolist()
    resid_std = (history - model.fittedvalues).std()
    p10 = [max(0, x - 1.28 * resid_std) for x in p50]
    p90 = [x + 1.28 * resid_std for x in p50]
    return ForecastResult(
        sku=sku,
        warehouse_id=warehouse_id,
        horizon_days=horizon,
        p50=p50,
        p10=p10,
        p90=p90,
        model_id="ets_v2_weekly_seasonal",
        as_of=date.today(),
        mape_backtest=compute_mape(history, model),
    )
```

Expose `model_id`, `as_of`, and backtest error in every API response. Agents use this metadata in user-facing explanations.

## Feature store and promotion handling

Agents ask about promos constantly. If promotion flags live only in marketing spreadsheets, forecasts lag reality. Minimum feature set:

- **Calendar** — holidays, paydays, school terms by region
- **Price and discount depth** — elasticity proxies
- **Promo type** — BOGO vs percentage off (different lift shapes)
- **Inventory position** — stockouts censor demand; impute carefully
- **Lead time** — vendor-specific, not a global constant

Stockouts truncate observed demand. Treat zero on-hand days as censored: naive history understates true demand and agents over-order after recovery. Use simple imputation or specialized intermittent-demand methods for long-tail SKUs.

## Serving architecture for agent tools

Forecast APIs must be **idempotent**, **cacheable**, and **versioned**:

```typescript
// Agent tool boundary — never return bare numbers without metadata
import { z } from "zod";

const ForecastRequest = z.object({
  sku: z.string().min(1),
  warehouseId: z.string().min(1),
  horizonDays: z.number().int().min(1).max(90),
  idempotencyKey: z.string().uuid(),
});

const ForecastResponse = z.object({
  sku: z.string(),
  warehouseId: z.string(),
  horizonDays: z.number(),
  intervals: z.object({
    p10: z.array(z.number()),
    p50: z.array(z.number()),
    p90: z.array(z.number()),
  }),
  modelId: z.string(),
  asOf: z.string().datetime(),
  mapeBacktest: z.number(),
  staleAfter: z.string().datetime(),
});

export async function getInventoryForecast(
  input: z.infer<typeof ForecastRequest>,
): Promise<z.infer<typeof ForecastResponse>> {
  const parsed = ForecastRequest.parse(input);
  const cached = await cache.get(cacheKey(parsed));
  if (cached && !isStale(cached)) return cached;

  const result = await forecastService.predict(parsed);
  await cache.set(cacheKey(parsed), result, { ttlSeconds: 3600 });
  return ForecastResponse.parse(result);
}
```

Agent system prompts should instruct: **if `asOf` is older than one business day or `mapeBacktest` exceeds category threshold, escalate to human planner**—do not create purchase orders autonomously.

## Safety stock and agent action thresholds

Point forecasts alone are dangerous. Encode operations research basics in tool logic, not in LLM arithmetic:

```python
def recommend_reorder_qty(
    forecast: ForecastResult,
    on_hand: int,
    on_order: int,
    lead_time_days: int,
    service_level: float = 0.95,
) -> dict:
    """Deterministic policy layer — LLM explains, does not compute."""
    demand_during_lt = sum(forecast.p50[:lead_time_days])
    sigma_lt = pooled_sigma(forecast, lead_time_days)
    z = z_score(service_level)
    safety = z * sigma_lt
    target = demand_during_lt + safety
    net_position = on_hand + on_order
    reorder_qty = max(0, int(target - net_position))
    return {
        "reorder_qty": reorder_qty,
        "safety_stock": int(safety),
        "demand_during_lead_time": int(demand_during_lt),
        "policy": "base_stock_lead_time",
        "requires_human_approval": reorder_qty > 10_000 or forecast.mape_backtest > 0.35,
    }
```

Large orders and high backtest error flip `requires_human_approval`. The agent drafts the rationale; humans approve in ERP.

## Evaluation and backtesting discipline

Offline metrics that matter for agent-facing forecasts:

- **MAPE / WAPE** — weighted by revenue or margin, not equal SKU weight
- **Pinball loss** — validates interval calibration (p10/p90)
- **Bias** — persistent over-forecast causes capital lockup; under-forecast causes stockouts

Run rolling-origin backtests monthly. Promote model tier changes only when new tier beats incumbent on WAPE **and** interval coverage on a holdout set stratified by ABC class.

Log every agent tool call that consumed a forecast: `forecast_id`, `sku`, `action_taken`, `human_override`. This closes the loop for model retraining and incident review.

## Operational concerns

**Retrain cadence** — nightly for Tier A; weekly for Tier B with drift detection triggers. Black Friday and seasonal boundaries need manual registry overrides.

**Latency** — agent conversations tolerate 200–800 ms for forecast fetch; precompute hot SKUs into Redis. Cold long-tail queries can async with "checking inventory outlook…" UX.

**Multi-tenant isolation** — retailer's demand history must never leak across tenants in shared feature stores. Partition by `tenant_id` at storage and API layers.

## Security and compliance

Forecast outputs influence money movement. Audit trails should capture who (agent session / user), what SKU, which model version, and resulting PO numbers. Role-based tool access: read-only forecast for support agents; write PO only for approved procurement roles with step-up auth.

Do not embed raw supplier pricing in prompts when unnecessary—forecast intervals suffice for quantity decisions.

## Testing strategy

- **Golden SKU set** — 50 SKUs with known promo spikes; assert interval coverage
- **Contract tests** — ERP mock returns consistent on-hand; verify reorder math
- **Agent evals** — prompt suite asking "should we reorder X?" with fixed fixture data; score tool selection and refusal on stale forecasts
- **Chaos** — disable forecast service; agent must fail gracefully, not invent numbers

## The takeaway

Inventory forecasting models for agents are a governed decision service: hierarchical grain, tiered models with explicit metadata, uncertainty bands, and deterministic policy layers that compute order quantities. The LLM explains and routes; it does not invent demand. Stale forecasts and missing promo flags cause more damage than choosing Prophet over LightGBM—invest in data contracts and tool guardrails first.

## Resources

- [Amazon Forecast — hierarchical forecasting](https://docs.aws.amazon.com/forecast/latest/dg/hierarchical.html)
- [Prophet documentation (Meta)](https://facebook.github.io/prophet/)
- [scikit-forecast — global vs local models](https://skforecast.org/)
- [M5 forecasting competition insights](https://www.kaggle.com/competitions/m5-forecasting-accuracy)
- [Companion: Demand Sensing Realtime](/agent-demand-sensing-realtime/)
- [Companion: Reconciliation Batch Jobs](/agent-reconciliation-batch-jobs/)
