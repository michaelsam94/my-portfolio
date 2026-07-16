---
title: "Feature Stores for ML"
slug: "feature-stores-ml"
description: "Operationalize ML features with feature stores: offline/online serving, point-in-time correctness, Feast and Tecton patterns, and avoiding training-serving skew."
datePublished: "2026-02-08"
dateModified: "2026-02-08"
tags: ["Data Engineering", "Machine Learning", "MLOps", "Feature Store"]
keywords: "feature store ML, Feast feature store, online offline features, point in time join, training serving skew, feature registry, Tecton ML features"
faq:
  - q: "What problem does a feature store solve?"
    a: "Feature stores centralize feature definitions, compute, and serving so training and inference use the same logic. They provide offline stores for batch training with point-in-time correct joins and online stores for low-latency inference — reducing training-serving skew and duplicate feature pipelines across teams."
  - q: "When do I need a feature store versus SQL views?"
    a: "SQL views work for small teams with few models and tolerant latency. Adopt a feature store when multiple models reuse features, you need sub-10ms online serving, point-in-time historical joins are painful manually, or feature versioning and lineage become compliance requirements."
  - q: "What is point-in-time correctness?"
    a: "Training labels must join feature values as they existed at prediction time — not future-leaked values. Point-in-time joins filter feature history by event timestamp, preventing inflated offline metrics that collapse in production."
---

The fraud model looked brilliant offline — until production recall cratered because training joined `user_chargeback_count` including chargebacks that happened *after* the transaction being labeled. Data scientists rebuilt the join three times in Spark notebooks; the serving team copied a different SQL snippet into the API. Feature stores exist to make that class of failure boring: define features once, backfill history with point-in-time correctness, serve the same values online at inference, and version definitions like API schema.

## Offline vs online stores

| Store | Latency | Use |
|-------|---------|-----|
| Offline (warehouse, Parquet) | Minutes–hours | Training, batch scoring |
| Online (Redis, DynamoDB) | Milliseconds | Real-time inference |

```
                    ┌──► Offline (BigQuery/Snowflake)
Feature definition ─┤
                    └──► Online (Redis) via materialization job
```

Materialization pushes latest feature values from offline compute to online keys on schedule or on change.

## Feast example

Define entities and features:

```python
# features.py
from feast import Entity, FeatureView, Field, FileSource
from feast.types import Float32, Int64
from datetime import timedelta

user = Entity(name="user_id", join_keys=["user_id"])

user_stats_source = FileSource(
    path="data/user_stats.parquet",
    timestamp_field="event_timestamp",
)

user_stats_fv = FeatureView(
    name="user_stats",
    entities=[user],
    ttl=timedelta(days=7),
    schema=[
        Field(name="transaction_count_7d", dtype=Int64),
        Field(name="avg_amount_7d", dtype=Float32),
    ],
    source=user_stats_source,
)
```

Historical retrieval for training:

```python
from feast import FeatureStore

store = FeatureStore(repo_path=".")
training_df = store.get_historical_features(
    entity_df=entity_df,  # user_id + event_timestamp per label row
    features=["user_stats:transaction_count_7d", "user_stats:avg_amount_7d"],
).to_df()
```

Feast performs **point-in-time join** — feature values at or before each label timestamp only.

Online serving:

```python
features = store.get_online_features(
    features=["user_stats:transaction_count_7d"],
    entity_rows=[{"user_id": 12345}],
).to_dict()
```

## Point-in-time join intuition

Label row: user 123 made transaction at `T`.

Wrong: join current feature snapshot at training run date `T+30` — leaks future.

Correct: join latest feature event where `feature_timestamp <= T`.

Feature stores encode this in `get_historical_features` — manual SQL rarely gets it right across dozens of feature tables.

## Training-serving skew sources

| Skew source | Feature store mitigation |
|-------------|-------------------------|
| Different SQL logic | Single feature definition |
| Different normalization | Shared transform in pipeline |
| Missing values handled differently | Central imputation spec |
| Stale online values | TTL monitoring, freshness SLAs |
| Wrong entity key mapping | Entity registry |

Log online feature vectors with model version for debugging production mispredictions.

## Feature registry and versioning

Registry tracks:

- Owner team
- Schema and dtype
- Source pipeline
- Version / changelog

Breaking change → new FeatureView name (`user_stats_v2`) — train new model, cutover, deprecate v1.

Lineage to dbt models or Spark jobs documents upstream freshness.

## Architecture options

- **Feast** — open source, bring your own offline/online stores
- **Tecton** — managed, opinionated streaming+batch
- **Cloud-native** — SageMaker Feature Store, Vertex Feature Store, Databricks Feature Engineering

Start minimal: one high-value feature group (user aggregates) end-to-end before platformizing.

## Operational metrics

- Online serving p99 latency
- Feature freshness (`now - last_materialization`)
- Null rate spikes
- Training/serving value diff audits (sample compare)

Feature stores are organizational glue as much as technology — success requires data eng + ML agreeing on ownership of definitions.

## Streaming features

Batch feature computation (nightly Spark job) isn't enough for real-time models — fraud detection, recommendations, dynamic pricing need streaming features:

```
Event stream → Flink/Spark Streaming → Online store (Redis)
                    ↓
              Offline store (warehouse) for training backfill
```

Feast supports streaming sources:

```python
from feast import StreamFeatureView
from feast.data_source import PushSource

push_source = PushSource(
    name="user_transactions_push",
    batch_source=user_stats_source,
)

@stream_feature_view(
    sources=[push_source],
    entities=[user],
    mode="spark",
    ttl=timedelta(hours=1),
)
def user_realtime_stats(df):
    return df.groupBy("user_id").agg(
        count("transaction_id").alias("transaction_count_1h"),
        avg("amount").alias("avg_amount_1h"),
    )
```

Streaming and batch features coexist — training uses batch historical values; serving uses streaming for low-latency inference.

## Feature store vs dbt marts

Overlap causes organizational confusion:

| Concern | dbt mart | Feature store |
|---|---|---|
| Audience | Analysts, BI dashboards | ML models, real-time inference |
| Freshness | Hourly/daily batch | Seconds (online store) |
| Point-in-time joins | Manual, error-prone | Built-in |
| Versioning | Git + dbt manifest | Feature registry |
| Serving latency | Seconds (warehouse query) | Milliseconds (Redis) |

Pattern: dbt builds the mart; feature store reads from mart for offline features and materializes to online store. Don't duplicate computation — feature store references dbt output as batch source.

## Failure modes

- **Training-serving skew** — different SQL logic in training vs serving; single feature definition prevents this
- **Future leakage in training** — manual point-in-time joins include post-label data; feature store enforces timestamp filtering
- **Stale online features** — materialization job fails silently; monitor freshness SLAs
- **No feature versioning** — model retrained on changed features without new version; breaking changes need new FeatureView name
- **Feature store before product-market fit** — platform overhead for one model; start with dbt marts + Redis cache

## Production checklist

- Feature definitions owned by named team (data eng + ML)
- Point-in-time correct joins verified on sample training data
- Online store freshness monitored with alerts
- Feature versioning: new FeatureView name for breaking changes
- Training-serving skew audit (sample compare offline vs online values)
- Materialization job failure alerts
- Start with one feature group end-to-end before platformizing

Evaluate managed feature stores (Tecton, SageMaker Feature Store) when Feast ops overhead exceeds team capacity — the organizational patterns remain the same regardless of vendor.

## Feature store maturity stages

Most teams don't need a feature store on day one. Progress through stages:

**Stage 1 — dbt marts + Redis cache:** Features computed in dbt, cached in Redis for online serving. Sufficient for 1–3 models.

**Stage 2 — Feast offline/online:** Point-in-time correct joins, materialization jobs, feature registry. Needed when 5+ models share features.

**Stage 3 — Managed (Tecton/SageMaker):** Real-time feature pipelines, automatic backfill, monitoring. Needed when ML team exceeds 10 engineers.

Skipping stages creates platform overhead before product-market fit. Start with Stage 1; migrate when training-serving skew becomes a recurring incident.

## Training-serving skew detection

The most common feature store failure — training and serving use different feature values:

```python
def audit_training_serving_skew(feature_name: str, sample_size: int = 1000):
    offline = feast.get_historical_features(
        entity_df=sample_entities,
        features=[f"{feature_name}"],
    )
    online = [feast.get_online_features(
        features=[f"{feature_name}"],
        entity_rows=[{"user_id": id}],
    ).to_dict() for id in sample_entities["user_id"]]

    diffs = compare(offline, online)
    skew_rate = sum(d != 0 for d in diffs) / len(diffs)
    if skew_rate > 0.01:
        alert(f"Training-serving skew detected: {feature_name} skew_rate={skew_rate:.2%}")
```

Run skew audit weekly on all production features. >1% skew rate indicates materialization lag or logic divergence.

## Feature freshness monitoring

Online features must be fresh — stale features silently degrade model quality:

```sql
-- Alert when feature materialization is stale
SELECT feature_name, MAX(materialized_at) AS last_materialized,
       NOW() - MAX(materialized_at) AS staleness
FROM feature_materialization_log
GROUP BY feature_name
HAVING NOW() - MAX(materialized_at) > INTERVAL '1 hour';
```

Define freshness SLA per feature: user profile features (1 hour), real-time behavioral features (5 minutes), daily aggregates (24 hours).

## Resources

- [Feast documentation](https://docs.feast.dev/)
- [Tecton feature store platform](https://www.tecton.ai/)
- [Point-in-time joins explained (Feast blog)](https://docs.feast.dev/getting-started/concepts/point-in-time-joins)
- [Uber Michelangelo feature store paper](https://www.uber.com/blog/michelangelo-machine-learning-platform/)
- [Feature Stores for ML (ML Ops Community)](https://mlops.community/)
