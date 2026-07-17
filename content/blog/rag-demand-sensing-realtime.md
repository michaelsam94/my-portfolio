---
title: "RAG: Demand Sensing Realtime"
slug: "rag-demand-sensing-realtime"
description: "Real-time demand sensing for inventory and ops — streaming signals, short-horizon forecasts, and RAG-assisted exception triage at the edge of the supply chain."
datePublished: "2025-08-02"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Demand"]
keywords: "rag, demand, sensing, realtime, ai, production, engineering, architecture"
faq:
  - q: "How is real-time demand sensing different from traditional demand forecasting?"
    a: "Traditional forecasting optimizes weekly or monthly replenishment with batch models trained on historical shipments. Demand sensing ingests intraday signals—POS scans, web traffic, weather, promotions, social spikes—and updates short-horizon forecasts continuously, often at SKU-location granularity with latency measured in minutes, not days."
  - q: "Where does RAG fit in a demand sensing stack?"
    a: "RAG augments numeric forecasts with contextual retrieval: promotional calendars, supplier constraint memos, regional event schedules, and past exception playbooks. When a sensor spike triggers an alert, retrieval grounds the ops copilot in why similar spikes happened before and which mitigations worked."
  - q: "What streaming architecture supports sub-hour forecast refresh?"
    a: "Event streams from POS and digital channels into a feature store with point-in-time correctness, online feature serving for inference microservices, and a rules layer for known anomalies. Kafka or Pulsar feeds aggregation windows; Flink or Spark Structured Streaming computes rolling demand rates compared to same-day-last-week baselines."
---
Store 847 was allocated twelve cases of sunscreen Tuesday morning based on a monthly forecast. By noon, a heat wave alert and a regional influencer post drove sell-through at 4× the plan. The DC had inventory—but the replenishment system would not reconsider until Friday's batch job. Markdown candidates sat in warm stores while Store 847 stocked out by 4 p.m. The data to predict the spike existed in POS streams, weather APIs, and marketing's unpublished influencer schedule; nothing fused them in time.

**Demand sensing** closes that gap by treating demand as a live signal, not a lagging report. When paired with RAG over operational knowledge—promo rules, vendor lead times, store cluster profiles—it gives planners and automated systems both the number and the narrative needed to act before stockouts.

## Signal inventory for short-horizon sensing

Effective sensing combines fast proxies with slower confirmatory data:

| Signal | Latency | Granularity | Role |
|--------|---------|-------------|------|
| POS transactions | Seconds | SKU-store | Ground truth sell-through |
| E-commerce cart adds | Seconds | SKU-DC region | Leading indicator |
| Web search on site | Minutes | Category-geo | Intent shift |
| Weather forecasts | Hourly | Store cluster | Seasonal lift driver |
| Social listening | Minutes–hours | Brand-region | Viral demand spikes |
| Competitor promo scrapes | Daily | Market | Share shift context |
| Inventory on hand | Minutes | SKU-location | Constraint for action |

The art is weighting signals by category: weather dominates lawn care; social spikes dominate beauty SKUs tied to influencers; neither helps much for commodity canned goods.

## From batch forecast to continuous refresh

Legacy architecture:

```
[Monthly history] → [Batch ML] → [Static forecast file] → [ERP]
```

Demand sensing architecture:

```
[POS/events] ──→ [Stream processor] ──→ [Feature store online]
                           ↓
              [Short-horizon model ensemble]
                           ↓
              [Exception detector vs baseline]
                           ↓
         [Replenishment API / planner alerts / RAG copilot]
```

**Baseline comparison** matters more than absolute prediction at intraday horizons. Compare cumulative sell-through today vs same weekday last week, adjusted for known promos. Deviation beyond 2.5σ triggers sensing workflows—not every twitch, but spikes that batch forecasts cannot see until too late.

Feature examples computed in rolling windows:

- `units_sold_1h`, `units_sold_4h`, `units_sold_same_window_lw`
- `velocity_ratio = units_sold_1h / avg(units_sold_1h last 4 same-weekdays)`
- `cart_add_to_purchase_conversion_2h`
- `temperature_delta_vs_yesterday` at store geo

Point-in-time correctness in the feature store prevents training-serving skew when promos are backfilled into calendars.

## Model choices at intraday horizons

Deep learning shines on long horizons with rich seasonality; sensing often wins with simpler, fast-updating models:

- **Exponential smoothing** on detrended intraday curves, recalibrated hourly.
- **Bayesian structural time series** for SKU-store pairs with sufficient history.
- **Gradient boosted trees** on engineered velocity features when history is sparse (new SKUs)—trained daily, scored every 15 minutes.

Ensemble the statistical baseline with a **promo uplift layer** from marketing's structured feed. Unstructured promo context—"influencer post expected mid-week, not in ERP"—is where RAG enters.

## RAG for exception triage and grounded recommendations

Numeric forecasts answer *how much*; operators ask *why now* and *what worked last time*. Index:

- Historical exception tickets with resolution notes
- Regional event calendars and school holiday schedules
- Supplier constraint bulletins ("Brand X allocation cut 20% through month-end")
- Playbooks for heat waves, viral spikes, and competitor price wars

When Store 847 triggers a spike alert, the copilot retrieves:

```text
Query: SKU-4412 sunscreen Store 847 velocity 4.2x baseline heat advisory SE region
Retrieved:
- 2024-07-12 similar spike: influencer + heat; mitigation: emergency DC transfer, +48 units, stockout avoided
- Promo calendar: no planned discount this week
- Supplier memo: no allocation constraint on SKU-4412
```

Ground retrieval in structured alert context—store ID, SKU, deviation magnitude, active weather codes—so embeddings match operational language, not generic product descriptions.

Guardrails: retrieval augments, never overrides, hard inventory constraints. If DC on-hand is zero, no prose playbook creates stock.

## Actioning sensing output

Connect forecasts to systems that can move inventory:

1. **Auto-replenishment triggers** for high-confidence spikes below safety stock thresholds.
2. **Planner queue** with ranked exceptions and retrieved context for human approval.
3. **Markdown prevention holds** when sensing predicts sustained lift—avoid clearing inventory before the spike peaks.
4. **Supplier signal** for vendor-managed inventory partners via EDI/API when contractual.

Latency budget: sensing alert to replenishment order creation under 30 minutes for perishable/high-velocity categories. Measure **time-to-intervention** as a KPI, not only forecast MAPE.

## Data quality and false spike control

POS duplicate scans, returns mis-posted as sales, and ecommerce cancel lag create phantom velocity. Implement:

- **Return netting** in rolling windows with configurable delay.
- **Store register heartbeat** alerts—silence looks like zero demand, not stability.
- **Cross-channel reconciliation** when web orders fulfill from store inventory.

Social listening false positives ( sarcastic mentions, unrelated homonyms) need entity linking to brand and SKU before entering feature pipelines.

## Governance and explainability

Planners trust sensing when they see *why* the system spiked an alert. Log top contributing features (`velocity_ratio`, `temp_delta`, `social_mention_zscore`) alongside RAG citations. Monthly calibration reviews compare alerted spikes to outcomes—did intervention help, or would doing nothing have been fine?

Separate model versions for experimental categories; do not auto-transfer inventory on sensing v2 until shadow mode beats v1 on precision at fixed recall.

Demand sensing turns streaming commerce data into minutes-level foresight. RAG layers institutional memory on top of velocity math so operators act with context, not just a red number on a dashboard. Store 847's sunscreen case ends when POS deviation triggers a transfer recommendation backed by last summer's playbook—before the afternoon stockout, not in next week's retrospective.

## Connecting sensing to supplier and allocation systems

Downstream from forecast refresh, **allocation APIs** need structured payloads—not only scalar uplift factors. Send `{ sku, store, horizon_hours, predicted_units, confidence_interval, contributing_signals[] }` so ERP rules engines apply vendor minimums and case pack rounding. RAG copilots help planners interpret *why* allocation changed when finance questions a 40% bump on sunscreen SKUs.

Closed-loop measurement compares sensed spikes where intervention occurred vs counterfactual stores excluded from auto-transfer as control cohort. Without controls, leadership cannot tell if sensing paid for itself or merely correlated with weather everyone already saw on news.

## Failure modes in live sensing

**Flash crowds** from flash sales break baselines trained on normal weekdays—maintain event calendars as hard overrides that widen confidence bands or disable auto-transfer until human confirms. **Register downtime** mimics zero demand; heartbeat alerts pause sensing for affected stores rather than forecasting stockouts that are actually POS outages.

Seasonality model drift after assortment changes (discontinued SKUs still in feature history) requires **assortment version tags** on feature rows—rebuild features when planogram resets, not only on calendar schedule.

## Feature store hygiene for intraday models

Point-in-time correctness breaks when promo flags backfill late. Ingest marketing promo tables with **event time** partitioning; feature joins use `as_of_timestamp` per store-SKU, not `current_date()`. Document late-arrival tolerance: promos may arrive 6 hours delayed—sensing model widens uncertainty bands until promo confirmed.

Monitor **feature freshness SLI**: percentage of store-SKU pairs with features updated within last 15 minutes during business hours. Drop below 98% triggers incident—stale features worse than stale batch forecasts because operators trust realtime labels.

## Organizational adoption and change management

Planners accustomed to weekly batch forecasts resist intraday signals until trust builds. Run **shadow mode** for two selling seasons: sensing recommendations appear in sidebar without auto-execution; planners compare to their manual decisions and log override reasons. Overrides feed RAG corpus with labeled examples ("ignored heat spike because supplier confirmed stockout") improving copilot advice quality.

Executive sponsorship matters when sensing triggers cross functional boundaries—store managers distrust DC transfers they did not request. Change management includes training on interpreting confidence intervals and explicit "why now" narrative from retrieved playbooks, not only numeric spike alerts on mobile devices.
