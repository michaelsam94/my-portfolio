---
title: "RAG: Capacity Forecasting Models"
slug: "rag-capacity-forecasting-models"
description: "Forecast embedding GPU hours, vector index growth, and query QPS for RAG pipelines using time-series models—Prophet for seasonality, ARIMA for short horizons, and queueing theory for saturation points."
datePublished: "2026-03-28"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Capacity"]
keywords: "capacity forecasting, RAG scaling, Prophet, ARIMA, embedding GPU, vector index growth, time series, queueing theory, capacity planning"
faq:
  - q: "What metrics should RAG capacity forecasts target?"
    a: "Forecast embedding compute (GPU-hours per day), vector index storage growth (GB/month), query QPS at p95, and reranker CPU utilization separately. Each layer has different growth drivers—corpus size drives index storage, user adoption drives QPS, model changes drive embedding cost per document."
  - q: "When is Prophet better than ARIMA for RAG traffic?"
    a: "Prophet handles weekly seasonality (Monday spikes, weekend lulls) and holiday effects in user query patterns. ARIMA works for short horizons (1–7 days) when traffic is relatively stationary. Use Prophet for quarterly budget planning; ARIMA for weekly autoscaling tuning."
  - q: "How do you forecast vector index size before reindexing?"
    a: "Model index size as: document_count × avg_chunks_per_doc × (embedding_dim × 4 bytes + metadata overhead). Add 30% headroom for HNSW graph overhead. Validate against actual index size after each corpus increment and recalibrate the multiplier."
---
Finance asked for Q4 GPU budget numbers six weeks before a major product launch would triple the knowledge base. The RAG platform team had Grafana dashboards showing current utilization but no model for what happens when document count goes from 2 million to 8 million chunks and daily active users double. They extrapolated linearly, underestimated embedding reindex cost by 4×, and spent October in emergency quota negotiations with the cloud provider.

Capacity forecasting for RAG is not generic infrastructure planning. Retrieval pipelines have distinct resource dimensions—embedding compute, vector storage, query serving, reranking—that grow at different rates driven by different inputs. This post covers practical forecasting models for each dimension and how to combine them into budget-ready projections.

## Decompose RAG capacity into forecastable dimensions

Before choosing a model, split the pipeline into components with independent growth curves:

| Dimension | Driver | Unit | Typical growth pattern |
|-----------|--------|------|------------------------|
| Embedding compute | Corpus size × reindex frequency | GPU-hours/day | Step jumps on bulk ingest |
| Vector index storage | Chunk count × dimensions | GB | Linear with corpus |
| Query embedding | User QPS × cache miss rate | GPU-ms/query | Follows adoption curve |
| Hybrid retrieval | QPS × index size | CPU-ms/query | Sublinear with caching |
| Reranker | QPS × candidates × model size | CPU/GPU-ms | Linear with QPS |
| Context assembly | QPS × avg chunk count | Memory bandwidth | Linear with QPS |

Forecast each separately, then sum for total cost. A single "RAG QPS" metric hides the embedding reindex cliff.

## Time-series forecasting for query traffic

User query QPS is the most familiar forecasting target. RAG query patterns often show:

- **Daily seasonality** — peak business hours, low overnight
- **Weekly seasonality** — Monday highest, Friday lowest
- **Launch spikes** — step changes after product releases
- **Drift** — gradual adoption growth

### Prophet for seasonal RAG traffic

Facebook Prophet handles seasonality and holidays without manual feature engineering:

```python
import pandas as pd
from prophet import Prophet

# Daily query QPS aggregated from Prometheus
df = pd.read_csv("rag_query_qps_daily.csv")  # columns: ds, y
df["ds"] = pd.to_datetime(df["ds"])

model = Prophet(
    yearly_seasonality=True,
    weekly_seasonality=True,
    daily_seasonality=False,  # use hourly data if intraday matters
    changepoint_prior_scale=0.05,
)
model.add_country_holidays(country_name="US")
model.fit(df)

future = model.make_future_dataframe(periods=90)
forecast = model.predict(future)

# Budget planning: p95 of forecast + 20% headroom
q4_peak = forecast[forecast["ds"] >= "2026-10-01"]["yhat_upper"].max()
budget_qps = q4_peak * 1.2
```

Prophet's `yhat_upper` gives confidence intervals useful for capacity headroom decisions. For RAG, also forecast **p95 QPS** separately from mean—retrieval latency SLOs bind on tail traffic.

### ARIMA for short-horizon autoscaling

For Kubernetes HPA tuning or weekly capacity reviews, ARIMA on differenced QPS works:

```python
from statsmodels.tsa.arima.model import ARIMA

qps_series = load_hourly_qps()  # last 30 days
model = ARIMA(qps_series, order=(2, 1, 2))
fitted = model.fit()
forecast = fitted.forecast(steps=168)  # next 7 days hourly
```

ARIMA assumes stationarity after differencing. RAG traffic with frequent step changes (launches) needs changepoint detection first—remove or segment around known events before fitting.

## Forecasting embedding compute for corpus growth

Embedding cost spikes during bulk reindex, not steady-state query traffic. Model it explicitly:

```
embedding_gpu_hours = (new_documents + updated_documents) × avg_chunks × seconds_per_chunk / 3600
```

Where `seconds_per_chunk` comes from benchmark on your GPU class:

```python
def forecast_reindex_cost(
    current_docs: int,
    new_docs: int,
    updated_docs: int,
    avg_chunks_per_doc: float,
    sec_per_chunk: float,
    gpu_hour_cost: float,
) -> dict:
    total_chunks = (new_docs + updated_docs) * avg_chunks_per_doc
    gpu_hours = total_chunks * sec_per_chunk / 3600
    return {
        "total_chunks": int(total_chunks),
        "gpu_hours": round(gpu_hours, 1),
        "cost_usd": round(gpu_hours * gpu_hour_cost, 2),
    }

# Example: 500k new docs, 50k updated, 3 chunks/doc, 0.08 sec/chunk on A10
forecast_reindex_cost(2_000_000, 500_000, 50_000, 3.0, 0.08, 1.50)
# → ~36 GPU-hours, ~$54 for this batch (excluding query embedding)
```

Add pipeline overhead: failed retries (×1.1), batch inefficiency at tail (×1.15), parallel job contention (×1.2). Historical calibration against actual reindex jobs is essential—first forecasts are always wrong.

## Vector index storage growth

Index storage grows predictably with chunk count:

```
storage_gb = chunk_count × (embedding_bytes + metadata_bytes + hnsw_overhead)
```

For a typical setup:

- 768-dim float32 embedding: 3,072 bytes
- Metadata (doc_id, chunk_idx, text preview): ~500 bytes
- HNSW graph overhead: ~1.5–2× raw vector storage

```python
def forecast_index_storage(
    chunk_count: int,
    embedding_dim: int = 768,
    metadata_bytes: int = 500,
    hnsw_multiplier: float = 1.8,
) -> float:
    vector_bytes = chunk_count * embedding_dim * 4
    metadata_total = chunk_count * metadata_bytes
    raw = vector_bytes + metadata_total
    return (raw * hnsw_multiplier) / (1024 ** 3)  # GB

forecast_index_storage(8_000_000)  # ~82 GB for 8M chunks
```

Validate monthly: compare predicted vs actual index size from your vector DB metrics. Recalibrate `hnsw_multiplier`—it varies by index parameters (M, efConstruction).

## Queueing theory for saturation forecasting

Time-series forecasts tell you demand. Queueing models tell you when latency SLOs break.

For embedding endpoint with M/M/c approximation:

```
ρ = λ / (c × μ)

where λ = arrival rate (queries/sec)
      c = number of GPU workers
      μ = service rate per worker (queries/sec)
```

When ρ approaches 1, p95 latency explodes. Forecast the date ρ exceeds 0.7 (common headroom threshold):

```python
def days_until_saturation(
    current_qps: float,
    daily_growth_rate: float,
    workers: int,
    service_rate_per_worker: float,
    threshold: float = 0.7,
) -> float:
    mu_total = workers * service_rate_per_worker
    target_qps = threshold * mu_total

    if current_qps >= target_qps:
        return 0

    # exponential growth: qps(t) = qps(0) × (1 + r)^t
    import math
    days = math.log(target_qps / current_qps) / math.log(1 + daily_growth_rate)
    return days

days_until_saturation(current_qps=45, daily_growth_rate=0.02, workers=4, service_rate_per_worker=15)
# → ~23 days until 70% utilization at 2% daily growth
```

This gives actionable "add capacity by date X" signals, not just cost projections.

## Building a RAG capacity dashboard

Combine forecasts into a single planning view:

1. **Historical actuals** — 90 days of QPS, GPU utilization, index size from Prometheus
2. **Prophet forecast** — 90-day forward QPS with confidence bands
3. **Corpus growth schedule** — planned document ingest from product roadmap
4. **Derived forecasts** — reindex cost, storage growth, saturation date
5. **Budget line** — monthly cost projection with headroom multiplier

Refresh corpus growth schedule monthly—product launches slip, and stale inputs produce stale forecasts.

## Common forecasting mistakes in RAG

**Linear extrapolation of index size during reindex.** Reindex is a step function, not a slope. Model discrete events.

**Ignoring cache miss rate changes.** New corpus versions invalidate caches, temporarily spiking embedding QPS. Forecast miss rate separately after major ingest.

**Single GPU metric for mixed workloads.** Query embedding and batch document embedding compete for the same pool. Split forecasts or separate node pools.

**No headroom for eval and shadow traffic.** Offline eval jobs and canary shadow pipelines consume embedding capacity not visible in user QPS.

**Forecasting mean instead of p95.** Autoscaling on mean QPS guarantees tail latency violations.

## Operational integration

Wire forecasts into planning rituals:

- **Weekly:** Compare ARIMA 7-day forecast vs actual; tune HPA if systematic bias
- **Monthly:** Update corpus growth schedule; recalculate reindex cost estimate
- **Quarterly:** Prophet forecast for budget; present saturation dates to leadership
- **Pre-launch:** Scenario model with 1×, 2×, 3× adoption assumptions

Capacity forecasting is not precision—it is decision support. A forecast that says "saturation in 18–28 days at current growth" is more useful than a point estimate of "$47,200/month" that ignores reindex cliffs.

## Scenario planning for major corpus events

Product launches that triple document count require scenario modeling beyond single-point forecasts. Build three scenarios—conservative (1.5× corpus growth), expected (2×), aggressive (3×)—and forecast embedding GPU hours, index storage, and query QPS for each. Present leadership with ranges, not point estimates. Include a "reindex cliff" line item separate from steady-state monthly cost. Teams that forecast only steady-state QPS get blindsided by one-time reindex cost every corpus version bump.

Track forecast accuracy monthly: compare predicted vs actual QPS, index size, and GPU utilization. Systematic over-forecasting wastes budget; under-forecasting causes incidents. A 15% correction factor applied to embedding sec-per-chunk after each reindex job improves the next forecast measurably.

## Resources

- Facebook Prophet documentation and seasonality tuning
- statsmodels ARIMA reference
- Kleinrock queueing systems fundamentals
- Vector database vendor sizing guides (Pinecone, Weaviate, pgvector)
