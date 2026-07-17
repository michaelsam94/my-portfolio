---
title: "AI Agents: Feature Store Online Offline"
slug: "agent-feature-store-online-offline"
description: "Feature Store Online Offline: production patterns for ai teams — design, implementation, testing, security, and operations."
datePublished: "2025-04-05"
dateModified: "2025-04-05"
tags: ["AI", "Agent", "Feature"]
keywords: "agent, feature, store, online, offline, ai, production, engineering, architecture"
faq:
  - q: "What is the difference between online and offline stores in a feature store?"
    a: "The offline store holds historical feature values at scale for training and batch analytics — typically Parquet on object storage or a warehouse table partitioned by event_time. The online store serves low-latency point lookups keyed by entity_id for inference and live agents — Redis, DynamoDB, or Feast's online backend. Same logical features; different latency, consistency, and retention profiles."
  - q: "How do you prevent training-serving skew in agent feature pipelines?"
    a: "Compute features once in the batch pipeline, materialize identical definitions to the online store via scheduled or streaming jobs, and version feature definitions in git. Use point-in-time correct joins for training labels. Never reimplement feature logic separately in the agent serving path — wrap shared transformation libraries used by both offline and online materialization."
  - q: "When should agent platforms adopt a feature store vs ad-hoc Redis keys?"
    a: "Adopt when three or more models or agents share entities (user, tenant, session), feature definitions change weekly, or compliance requires reproducible training snapshots. Stay ad-hoc for a single prototype agent with five features — operational overhead exceeds benefit until sharing and versioning pain appears."
  - q: "What consistency level is realistic between online and offline stores?"
    a: "Expect eventual consistency: online may lag offline materialization by minutes to hours. Document SLAs per feature group. Agent decisions needing fresh state (last tool error count) use streaming materialization or compute-on-read with TTL cache; slow-changing features (30-day activity aggregates) tolerate hourly batch sync."
---
The routing model trained on warehouse features showing "avg_tool_latency_7d" from Snowflake. Production agents read a Redis hash updated by a different Spark job that rounded differently and keyed sessions by `session_id` instead of `user_id`. Offline metrics looked great; live agents routed high-priority tickets wrong for two days before someone diffed training SQL against the serving getter. A feature store exists to make **one definition** materialize to **two stores** with **point-in-time correctness** — not to add another dashboard.

Agent platforms increasingly score requests with ML: triage urgency, retrieval routing, tool selection priors, fraud signals on tool calls. Features span user history, tenant configuration, session context, and embedding-derived signals. Without a feature store, teams duplicate transformation logic, leak future data into training, and serve stale Redis keys that diverge from batch pipelines. This piece covers online/offline architecture, materialization patterns, point-in-time joins, and operational guardrails for agent workloads.

## Online vs offline: responsibilities

```
                    ┌─────────────────────┐
  Events / logs ──► │  Feature transform  │ ◄── shared definition (git versioned)
                    │  (Spark / Flink)    │
                    └──────────┬──────────┘
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
    ┌──────────────────┐              ┌──────────────────┐
    │  OFFLINE store   │              │  ONLINE store    │
    │  Parquet / BQ /  │   materialize│  Redis / Dynamo  │
    │  Snowflake       │ ───────────► │  low-latency KV  │
    └────────┬─────────┘              └────────┬─────────┘
             │                                 │
             ▼                                 ▼
    Model training /                    Live agent inference
    batch eval / backtests              (routing, ranking)
```

| Dimension | Offline | Online |
|-----------|---------|--------|
| Latency | Seconds to hours | Single-digit ms p99 |
| Query pattern | Scan, point-in-time join | Get by entity key |
| Retention | Years | Hours to weeks |
| Consistency | Snapshot / partition | Per-key upsert |
| Primary use | Train, evaluate, audit | Serve agent decisions |

## Entity model for agents

Define entities explicitly — ambiguity causes skew:

- `user_id` — cross-session behavior, entitlement tier
- `tenant_id` — org-level limits, model config
- `session_id` — in-conversation signals (turn count, last tool error)
- `ticket_id` — support agent routing features

A feature belongs to exactly one entity type. Joining session features to user models requires documented aggregation windows, not implicit coalescing at serve time.

Example feature groups:

```yaml
# features/user_engagement.yaml
feature_group: user_engagement_v3
entity: user_id
features:
  - name: sessions_7d
    dtype: int64
    description: Distinct agent sessions in trailing 7 days
  - name: avg_tool_success_rate_30d
    dtype: float64
  - name: last_active_at
    dtype: timestamp
offline_source: s3://features/offline/user_engagement_v3/
online_store: redis_cluster_a
ttl_seconds: 604800
materialization_schedule: "0 */1 * * *"  # hourly
```

Version the YAML in git; CI validates schema and runs transformation tests.

## Shared transformation library

The anti-pattern: PySpark for offline, TypeScript for online. The fix: core logic in one language or RPC service:

```python
# features/transforms/tool_success_rate.py
from datetime import timedelta
import pandas as pd

def compute_tool_success_rate(
    events: pd.DataFrame,
    as_of: pd.Timestamp,
    window: timedelta,
) -> float:
    """Point-in-time correct: only events with event_time <= as_of."""
    start = as_of - window
    windowed = events[
        (events["event_time"] > start) & (events["event_time"] <= as_of)
    ]
    if windowed.empty:
        return 0.0
    return windowed["success"].mean()
```

Offline pipeline calls this in Spark UDF or pandas groupby; online materialization calls the same function on sliding windows from a stream buffer, or copies batch-computed values from the offline partition latest to Redis.

## Point-in-time correct training

Training must not use features computed with future information. For each label row `(entity_id, label_time)`, join features as of `label_time`:

```sql
-- BigQuery-style point-in-time join pattern
SELECT
  l.user_id,
  l.label_time,
  l.escalated AS label,
  f.avg_tool_success_rate_30d,
  f.sessions_7d
FROM labels l
ASOF JOIN feature_snapshots f
  MATCH_CONDITION (l.label_time >= f.snapshot_time)
  ON l.user_id = f.user_id
WHERE l.label_time BETWEEN @train_start AND @train_end;
```

Feast, Tecton, and Hopsworks automate this; roll-your-own teams need snapshot tables partitioned by `snapshot_time` or use `event_time` in offline store with strict join semantics.

## Materialization paths

**Batch materialization (most common).** Hourly Spark job writes offline partition, then pushes latest values per entity to Redis:

```python
# jobs/materialize_online.py
def materialize(feature_group: str, partition_date: str) -> None:
    offline = read_parquet(f"s3://features/offline/{feature_group}/dt={partition_date}")
    latest = offline.sort("event_time").groupby("user_id").tail(1)

    pipe = redis.pipeline()
    for row in latest.itertuples():
        key = f"fg:{feature_group}:{row.user_id}"
        pipe.hset(key, mapping=row._asdict())
        pipe.expire(key, TTL[feature_group])
    pipe.execute()

    metrics.gauge("materialize_rows", len(latest), tags={"fg": feature_group})
```

**Streaming materialization.** Flink consumes agent event Kafka topic, maintains tumbling windows, upserts online store within seconds. Use for `last_tool_error_code`, `turn_count_session` — features agents need fresh mid-conversation.

**On-demand hydration.** Agent worker calls feature store SDK at request time; SDK merges online hits with batch fallback. Higher latency — acceptable for non-critical path features only.

## Agent serving integration

```typescript
// services/feature-client.ts
import { Redis } from "ioredis";

const redis = new Redis(process.env.FEATURE_REDIS_URL);

export interface AgentFeatures {
  sessions7d: number;
  avgToolSuccessRate30d: number;
  tenantModelTier: string;
}

export async function getAgentFeatures(
  userId: string,
  tenantId: string,
): Promise<AgentFeatures> {
  const [userHash, tenantHash] = await Promise.all([
    redis.hgetall(`fg:user_engagement_v3:${userId}`),
    redis.hgetall(`fg:tenant_config_v1:${tenantId}`),
  ]);

  if (!userHash.sessions_7d) {
    metrics.increment("feature_cache_miss", { group: "user_engagement_v3" });
  }

  return {
    sessions7d: parseInt(userHash.sessions_7d ?? "0", 10),
    avgToolSuccessRate30d: parseFloat(userHash.avg_tool_success_rate_30d ?? "0"),
    tenantModelTier: tenantHash.model_tier ?? "standard",
  };
}
```

Log feature vector hashes on agent decisions for replay debugging — not raw PII features in public logs.

## Consistency SLAs and staleness

Publish per feature group:

| Feature group | Max staleness | Materialization |
|---------------|---------------|-----------------|
| user_engagement_v3 | 1 hour | Batch hourly |
| session_live_v1 | 30 seconds | Streaming |
| tenant_config_v1 | 5 minutes | CDC from Postgres |

Agent orchestrator checks `feature_freshness_timestamp` metadata when present; degrade to safe default routing if stale beyond SLA.

## Validation and drift detection

**Offline-online parity job.** Sample 1000 random entities daily; compare offline latest partition to online Redis; alert on >0.1% mismatch.

**Distribution monitoring.** Track PSI (Population Stability Index) on key features weekly; agent behavior shifts when input distributions drift.

**Schema enforcement.** Reject materialization jobs that add columns without registry update; breaking dtype changes require new feature group version (`_v4`).

```python
def parity_check(entity_ids: list[str], fg: str) -> list[str]:
    mismatches = []
    for eid in entity_ids:
        offline = fetch_offline_latest(fg, eid)
        online = fetch_online(fg, eid)
        if not features_equal(offline, online, rtol=1e-5):
            mismatches.append(eid)
    return mismatches
```

## When not to use a feature store

- Single model, five features, one team — Postgres columns or agent session JSON suffice.
- Features are pure functions of the current prompt with no historical state.
- Sub-10ms end-to-end latency budget cannot tolerate an extra Redis round trip — embed minimal features in the request payload instead.

Adopt when sharing, versioning, and compliance pressure exceed tooling cost. Revisit the build-vs-buy decision every quarter as agent count and shared feature overlap grow.

## Security and compliance

Feature stores aggregate behavioral data — apply row-level access in the warehouse, encrypt Redis at rest, and restrict online store network to agent worker VPC. Training exports need audit logs (who pulled which snapshot). For GDPR deletion, propagate `user_id` tombstones to offline partitions and online key deletes.

## The takeaway

Online and offline feature stores are two materialization targets for one versioned definition — not two teams' interpretations of "similar" SQL. Agent platforms need explicit entities, point-in-time training joins, shared transform code, materialization SLAs, and parity checks between stores. Batch hourly for slow features, stream for session-live signals, and never reimplement transforms in the agent hot path. That discipline prevents training-serving skew and makes model debugging a data diff instead of a three-day hunt.

## Resources

- [Feast — Open source feature store](https://docs.feast.dev/)
- [Tecton — Enterprise feature platform](https://docs.tecton.ai/)
- [Hopsworks feature store](https://docs.hopsworks.ai/latest/concepts/fs/)
- [Uber Michelangelo — Feature catalog patterns](https://www.uber.com/blog/michelangelo-machine-learning-platform/)
- [Google — Training-serving skew avoidance](https://developers.google.com/machine-learning/guides/rules-of-ml#rule-training-serving_skew)
- [Databricks — Point-in-time joins](https://docs.databricks.com/en/machine-learning/feature-store/time-series.html)
