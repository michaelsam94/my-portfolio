# Part 3: posts 9-14

POSTS_P3 = {}

POSTS_P3["devops-feature-store-governance"] = (
    {
        "title": "Feature Store Governance and Feature Ownership",
        "description": "When feature count exceeds tribal knowledge, registries need named owners, SLAs, deprecation policies, and catalog metadata—or consumers blame model teams for stale vectors nobody owns.",
        "datePublished": "2026-07-31",
        "tags": ["DevOps", "Feature Stores", "Platform"],
        "keywords": "feature governance, feature ownership, Feast catalog, feature deprecation, MLOps",
        "faq": [
            {
                "q": "Who should own a feature in the registry?",
                "a": "The team that produces the upstream data and stands behind freshness SLAs—not the model team that consumes it. Consumer teams own integration tests; producer teams own computation, backfill, and incident response for their FeatureViews.",
            },
            {
                "q": "What metadata should every feature include?",
                "a": "Owner contact, freshness SLA, source systems, PII classification, deprecation status, and example entity keys for debugging. Feast tags and external catalog (DataHub, Amundsen) should agree on owner and tier.",
            },
            {
                "q": "How do you deprecate a feature safely?",
                "a": "Mark deprecated in registry, notify consumers via catalog alerts, maintain parallel serving for one release cycle, verify no training jobs reference it, then remove in coordinated PR across repo and downstream notebooks.",
            },
            {
                "q": "What SLAs apply to tier-1 features?",
                "a": "Common pattern: 99.5% materialization success, max staleness 2× interval, incident response within business hours for consumer-facing models. Document exceptions—batch-only features may have 24h staleness by design.",
            },
        ],
    },
    r"""Forty teams shared one Feast project. When `user_ltv_90d` went stale, the recommendations model degraded for a week. Slack threads asked "who owns this?"—no entry in the catalog, three conflicting notebooks computing similar names, and a data engineer on vacation who "usually handled merchant stuff."

Feature stores collapse duplication until nobody knows who fixes production. Governance is ownership made visible.

## RACI for features

| Role | Responsibility |
|------|----------------|
| Producer (owner) | Computation, materialization, backfill, freshness incidents |
| Consumer | Integration tests, model impact assessment |
| Platform | Registry infrastructure, CI templates, catalog sync |
| Data governance | PII classification, retention alignment |

Assign owner at FeatureView creation—block `feast apply` in prod without owner tag:

```python
@feature_view(
    name="user_ltv_features",
    entities=[user],
    ttl=timedelta(days=1),
    tags={"owner": "team:growth-analytics", "tier": "1", "pii": "none"},
)
def user_ltv_fv(source):
    ...
```

## Catalog integration

Sync Feast registry to DataHub on every apply:

```yaml
# GitHub Actions step
- name: Emit lineage to DataHub
  run: |
    datahub ingest -c feast/datahub_recipe.yml
```

DataHub displays owner, upstream tables, and downstream ML models. Consumers subscribe to change notifications.

Minimum catalog fields:

- **Description** — plain language, not column name restatement
- **Freshness SLA** — "updated hourly by :15"
- **Deprecation** — `active | deprecated | retired`
- **Consumers** — linked model names or services

## Deprecation workflow

```
1. Owner marks FeatureView deprecated + target removal date
2. Catalog emails registered consumers automatically
3. Consumers acknowledge or file exception
4. Serving reads gated off per consumer timeline
5. Remove from repo; archive offline columns after retention window
```

Never delete offline warehouse columns the same day as registry removal—training reproducibility needs history.

## Shared vs team-scoped features

| Type | Naming | Change process |
|------|--------|----------------|
| Core entity (user, merchant) | `core/user_*` | Architecture review |
| Team experimental | `exp/recs_*` | Team lead approval |
| One-off model | `model/churn_v3_*` | Consumer-only; no reuse without review |

Experimental features in shared namespaces cause silent reuse—worst case is another team's production model training on your sandbox computation.

## SLA enforcement

Track producer SLAs:

```sql
-- freshness audit
SELECT
  feature_view,
  MAX(event_timestamp) AS latest_event,
  TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(event_timestamp), MINUTE) AS lag_minutes
FROM feature_freshness_audit
GROUP BY feature_view
HAVING lag_minutes > 120;
```

Page owner on tier-1 breach; weekly report for tier-2.

## Access and PII

Features containing derived PII need classification tags and restricted registry visibility. Inference service accounts read only FeatureViews on allowlist IAM policy (enforced at warehouse layer for offline, Redis ACLs for online).

## Quarterly feature review

Platform hosts 60-minute review: top 20 features by consumer count, stale deprecated entries, duplicate definitions, SLA misses. Output is a cleanup sprint, not a slide deck.

Governance does not slow teams—it routes incidents to someone who can fix them instead of broadcasting to four hundred engineers.
""",
)

POSTS_P3["devops-feature-store-materialization"] = (
    {
        "title": "Feature Store Materialization Job Operations",
        "description": "Feast materialization is the heartbeat of online features—schedule it, monitor row counts, handle backfills, and forbid overlapping jobs that double Redis load.",
        "datePublished": "2026-07-28",
        "tags": ["DevOps", "Feature Stores", "Data Engineering"],
        "keywords": "feature materialization, Feast materialize, Airflow, CronJob, backfill",
        "faq": [
            {
                "q": "What is the difference between materialize and materialize-incremental?",
                "a": "`materialize start end` processes a fixed timestamp window—use for backfills. `materialize-incremental end` advances from last successful watermark to end—use for hourly/daily scheduled jobs. Mixing them without checkpoint discipline causes gaps or duplicates.",
            },
            {
                "q": "How do you prevent overlapping materialization jobs?",
                "a": "Kubernetes CronJob concurrencyPolicy Forbid, Airflow max_active_runs=1, or distributed lock (Redis/etcd) around feast CLI invocation. Overlaps duplicate writes and inflate Redis ops.",
            },
            {
                "q": "What metrics prove materialization health?",
                "a": "Job success/failure, duration p95, rows written per FeatureView, lag from max event timestamp to now, and post-job online/offline sample match rate. Alert on zero rows when expecting millions.",
            },
            {
                "q": "When should materialization run relative to upstream ETL?",
                "a": "Schedule after upstream DAG success sensor fires—not fixed clock time alone. If warehouse facts land at :40, materialize at :45 with sensor, not :05 when data is missing.",
            },
        ],
    },
    r"""Materialization failed silently every night for six days because Airflow marked the task green—the BashOperator returned 0 even though `feast materialize-incremental` logged "0 rows written" after a typo in FeatureView name. Online features froze; nobody noticed until A/B metrics drifted.

Materialization jobs are production pipelines, not cron afterthoughts.

## Job design patterns

**Incremental (steady state)**

```bash
#!/usr/bin/env bash
set -euo pipefail
END=$(date -u +"%Y-%m-%dT%H:%M:%S")
feast materialize-incremental "$END"
ROWS=$(python scripts/count_materialized_rows.py --since "$END")
if [[ "$ROWS" -lt "$MIN_ROWS" ]]; then
  echo "Expected >= $MIN_ROWS rows, got $ROWS"
  exit 1
fi
```

**Windowed backfill**

```bash
feast materialize 2026-01-01T00:00:00 2026-01-08T00:00:00 \
  --feature-views user_daily_features
```

## Airflow DAG with upstream sensor

```python
from airflow import DAG
from airflow.providers.google.cloud.sensors.bigquery import BigQueryTableExistenceSensor
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

with DAG(
    "feast_materialize_user_features",
    schedule="@hourly",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
) as dag:
    wait_facts = BigQueryTableExistenceSensor(
        task_id="wait_user_facts",
        project_id="analytics",
        dataset_id="warehouse",
        table_id="f_user_daily",
        poke_interval=60,
        timeout=3600,
    )
    materialize = BashOperator(
        task_id="feast_materialize",
        bash_command="cd /opt/feast_repo && ./scripts/materialize_incremental.sh",
    )
    wait_facts >> materialize
```

## Observability

Export OpenTelemetry or pushgateway metrics from wrapper script:

| Metric | Labels |
|--------|--------|
| `feast_materialize_duration_seconds` | feature_view |
| `feast_materialize_rows` | feature_view |
| `feast_materialize_lag_seconds` | feature_view |
| `feast_materialize_success` | job_name |

Dashboard panels: last success time, row count vs 7-day median, lag trend.

## Failure modes

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| 0 rows | Upstream delay, wrong view name | Sensor on ETL; validate names in CI |
| Timeout | Data volume growth | Partition materialization; increase resources |
| Duplicate spikes | Overlapping jobs | Enforce single active run |
| Partial window | Job killed mid-run | Idempotent windows; checkpoint |

## Resource sizing

Materialization is CPU and warehouse-slot bound. Start with:

- 2–4 CPU, 8Gi for medium FeatureViews (<10M entities/window)
- Warehouse slot reservation during job—avoid contending with ad hoc analysts
- Redis pipeline batch size tuned from load test (often 500–5000 keys per batch)

## Runbook excerpt

**Incident: materialization failing 3+ times**

1. Check upstream ETL status.
2. Run manual incremental with debug logging in staging clone.
3. If registry corruption suspected, `feast registry-dump` and compare to Git.
4. Pause inference flag for affected models if lag exceeds 2× SLA.
5. Backfill gap window after root fix.

Materialization operations reward paranoia: zero-row success is failure, overlap is expensive, and clocks lie when upstream data is late.
""",
)

POSTS_P3["devops-feature-store-monitoring"] = (
    {
        "title": "Feature Store Monitoring and Data Quality",
        "description": "Monitor feature freshness, null rates, distribution drift, and online/offline parity—before model metrics degrade and nobody can explain why.",
        "datePublished": "2026-08-06",
        "tags": ["DevOps", "Feature Stores", "MLOps"],
        "keywords": "feature monitoring, data drift, Feast observability, feature quality",
        "faq": [
            {
                "q": "What should you monitor for production feature stores?",
                "a": "Materialization success and lag, online serving latency, null/missing rate per feature, distribution drift vs training baseline, online/offline value mismatch samples, and Redis/memory pressure for online store.",
            },
            {
                "q": "How is feature drift different from model drift?",
                "a": "Feature drift is change in input distribution (mean shift, new nulls) before the model scores. Model drift is change in prediction or outcome distribution. Feature monitoring catches upstream data bugs earlier—broken ETL, stale materialization, schema changes.",
            },
            {
                "q": "How often should online/offline consistency checks run?",
                "a": "Hourly for tier-1 features with automated sampling (500–1000 entities). Daily full statistical profile on offline store. Alert when mismatch rate exceeds 0.1% or when any tier-1 feature null rate doubles week-over-week.",
            },
            {
                "q": "Which tools integrate with Feast for monitoring?",
                "a": "Evidently AI, Great Expectations, WhyLabs, and custom Prometheus exporters from materialization wrappers. Feast native does not replace statistical monitoring—export metrics to your existing observability stack.",
            },
        ],
    },
    r"""Model monitoring showed stable AUC while chargebacks rose. Root cause: `merchant_category` null rate jumped from 0.2% to 18% after a upstream vendor feed change—materialization still succeeded, filling nulls the model never saw in training.

Feature store monitoring answers "are the inputs sane?" before model dashboards answer "is the score sane?"

## Monitoring layers

```
Layer 1: Infrastructure — job success, Redis latency, memory
Layer 2: Freshness — lag from event time, last materialize timestamp
Layer 3: Quality — nulls, bounds, categorical cardinality
Layer 4: Consistency — online vs offline sample match
Layer 5: Drift — PSI/KS vs training baseline
```

Each layer pages different on-call rotations if needed—platform vs data producer.

## Prometheus metrics from serving

```python
from prometheus_client import Histogram, Counter

FEATURE_FETCH_LATENCY = Histogram(
    "feast_get_online_features_seconds",
    "Online feature fetch latency",
    ["feature_view"],
)
FEATURE_NULLS = Counter(
    "feast_feature_null_total",
    "Null feature values returned",
    ["feature_name"],
)

def fetch_features(entity_rows, features):
    with FEATURE_FETCH_LATENCY.labels(feature_view=features[0].split(":")[0]).time():
        result = store.get_online_features(features=features, entity_rows=entity_rows)
    for name, values in result.to_dict().items():
        if name in features and any(v is None for v in values):
            FEATURE_NULLS.labels(feature_name=name).inc()
    return result
```

## Statistical checks with Great Expectations

```python
import great_expectations as gx

suite = context.add_expectation_suite("user_daily_features")
suite.add_expectation(
    gx.expectations.ExpectColumnValuesToNotBeNull(column="txn_count_7d")
)
suite.add_expectation(
    gx.expectations.ExpectColumnValuesToBeBetween(
        column="avg_spend_7d", min_value=0, max_value=1_000_000
    )
)
```

Run against offline store partition after materialization; fail pipeline on violation.

## Drift detection

Population Stability Index weekly:

```python
def psi(expected, actual, buckets=10):
    # compare training baseline histogram to current week
    ...
```

Alert when PSI > 0.2 for tier-1 numeric features. Investigate upstream before retraining.

## Dashboard essentials

One Grafana row per critical FeatureView:

- Materialization lag (minutes)
- Rows written (vs 7d median)
- Online p99 fetch latency
- Null rate %
- Online/offline mismatch rate (from hourly job)
- PSI top movers

## Incident correlation

Link feature alerts to model serving dashboards. When `feast_feature_null_total` spikes, overlay model prediction distribution—helps confirm user impact quickly.

## Synthetic probes

Blackbox job every 5 minutes:

```python
PROBE_ENTITY = {"user_id": "probe-fixed-uuid"}
expected = load_fixture("probe_user_features.json")
actual = store.get_online_features(...).to_dict()
assert_vectors_equal(actual, expected, tolerance=0.01)
```

Fixed entity with stable upstream data catches slow staleness statistical tests miss.

Feature monitoring is cheap insurance against silent ETL regressions—the kind that pass unit tests because SQL still runs.
""",
)

POSTS_P3["devops-feature-store-point-in-time"] = (
    {
        "title": "Point-in-Time Correct Feature Joins",
        "description": "Point-in-time joins prevent label leakage in training—Feast get_historical_features encodes temporal correctness, but only if event timestamps and FeatureView definitions match reality.",
        "datePublished": "2026-08-10",
        "tags": ["DevOps", "Feature Stores", "MLOps"],
        "keywords": "point in time join, label leakage, Feast historical features, temporal correctness",
        "faq": [
            {
                "q": "What is a point-in-time correct join?",
                "a": "For each training label at time T, features must reflect only data available before T—never future transactions, updated aggregates, or backfilled values computed with hindsight. Point-in-time joins enforce temporal semantics automatically when configured correctly.",
            },
            {
                "q": "What causes label leakage in feature stores?",
                "a": "Using current feature values for historical labels, event timestamps set to processing time instead of business time, aggregate windows that include post-label events, and training on data before backfill completes across the full label window.",
            },
            {
                "q": "How does Feast get_historical_features work?",
                "a": "You supply an entity dataframe with entity keys and event_timestamp per label row. Feast joins each row to feature values valid at that timestamp from offline store—handling time-travel alignment per FeatureView TTL and aggregation windows.",
            },
            {
                "q": "How do you validate point-in-time correctness?",
                "a": "Manual spot checks: pick random labels, reconstruct features with raw SQL using AS OF logic, compare to Feast output. Automated tests with synthetic datasets where ground truth is known. Never ship new FeatureView without leakage test in CI.",
            },
        ],
    },
    r"""The churn model reported 0.98 AUC in offline evaluation. Production scored random users like VIPs. Training labels used `event_timestamp` at midnight while features included same-day purchases—classic leakage through a timezone-aligned aggregate window.

Point-in-time correctness is not a Feast checkbox—it is how you define timestamps, windows, and entity grain in every FeatureView.

## The leakage mental model

```
Timeline for one customer label (churned on June 15):

  May 1 ───────────── June 14 │ June 15 (label)
        features must use      │ label event
        only this region         ▼

WRONG: txn_count_30d computed through June 15 including post-churn activity
RIGHT: txn_count_30d as of June 14 23:59:59 business time
```

## Entity dataframe contract

```python
import pandas as pd

entity_df = pd.DataFrame({
    "user_id": [101, 102, 103],
    "event_timestamp": [
        pd.Timestamp("2026-06-15 00:00:00"),
        pd.Timestamp("2026-06-16 00:00:00"),
        pd.Timestamp("2026-06-17 00:00:00"),
    ],
    "churned": [1, 0, 1],  # label — not passed to Feast
})

training_df = store.get_historical_features(
    entity_df=entity_df,
    features=[
        "user_behavior:txn_count_30d",
        "user_behavior:days_since_login",
    ],
).to_df()
```

`event_timestamp` is the anchor—Feast resolves feature values as of that instant.

## FeatureView time semantics

```python
@feature_view(
    name="user_behavior",
    entities=[user],
    ttl=timedelta(days=90),
    schema=[Field(name="txn_count_30d", dtype=Int64)],
    online=True,
    source=user_transactions_source,
)
def user_behavior_fv(input_df):
    # aggregation window must END before label time — enforced by Feast join
    return input_df.groupby("user_id").agg(...)
```

Document whether source `event_timestamp` is:

- **Business event time** (transaction completed)—preferred
- **Processing time** (warehouse insert)—dangerous for late-arriving data

## Late-arriving data

If transactions can land in warehouse 48h late, point-in-time joins at training time understate activity unless you:

1. Use processing-time snapshots with explicit lag in SLA, or
2. Rebuild training snapshots after late data cutoff, or
3. Exclude recent label window from training (`event_timestamp < now() - 3 days`)

## Validation SQL spot check

```sql
-- Manual verification for user 101, label time T
SELECT COUNT(*) AS txn_count_30d
FROM transactions
WHERE user_id = 101
  AND event_time <= TIMESTAMP('2026-06-14 23:59:59')
  AND event_time > TIMESTAMP('2026-05-15 23:59:59');
```

Compare to Feast historical output row—must match exactly.

## CI leakage test with synthetic data

```python
def test_no_future_leakage():
    # inject transaction AFTER label time in source
    # assert feature value excludes it
    result = build_historical_features(entity_df_with_label_at_t)
    assert result.loc[0, "txn_count_1d"] == 0
```

## Serving vs training alignment

Online serving returns **latest materialized** values—not point-in-time unless you engineer streaming FeatureViews with event-time aggregation. Training-serving skew appears when offline joins use business time and online uses processing lag. Monitor and document expected gap.

Point-in-time joins turn temporal correctness from a review meeting debate into a repeatable query—if timestamps and windows are honest.
""",
)

POSTS_P3["devops-feature-store-schema-evolution"] = (
    {
        "title": "Feature Store Schema Evolution",
        "description": "Adding, renaming, or changing feature types requires versioned FeatureViews, coordinated backfills, and serving flags—schema evolution fails loudly or models fail quietly.",
        "datePublished": "2026-08-13",
        "tags": ["DevOps", "Feature Stores", "Data Engineering"],
        "keywords": "feature schema evolution, FeatureView versioning, backward compatibility, Feast schema",
        "faq": [
            {
                "q": "How do you add a new feature column safely?",
                "a": "Add nullable column to FeatureView schema, backfill offline history, materialize to online, deploy inference that tolerates nulls during rollout, then backfill nulls and enable flag. Never assume default zero is safe—zero may be meaningful.",
            },
            {
                "q": "Should you rename features or create new versions?",
                "a": "Create new FeatureView or version suffix (`user_features_v2`) for breaking changes. Renaming in place breaks training reproducibility and consumer code silently. Deprecate old view after migration window.",
            },
            {
                "q": "What breaking changes require model retraining?",
                "a": "Unit changes (cents to dollars), log vs linear transform, categorical encoding map changes, window length changes (7d to 14d), and bug fixes that materially shift distributions—even if column name unchanged.",
            },
            {
                "q": "How does Feast handle schema changes in the registry?",
                "a": "feast apply updates registry schema; online/offline stores may reject incompatible types. Always run apply in staging first, validate materialization sample, and pin SDK versions across materialization and serving.",
            },
        ],
    },
    r"""Someone changed `risk_score` from INT to FLOAT in the FeatureView and ran `feast apply` Friday afternoon. Materialization succeeded. Inference pods on last week's SDK crashed on deserialization until Monday—twelve models on the floor.

Schema evolution in feature stores is distributed database migration with ML blast radius.

## Change taxonomy

| Change type | Risk | Pattern |
|-------------|------|---------|
| Add nullable column | Low | Expand → backfill → enforce |
| Add non-null column | Medium | Backfill before enforce NOT NULL semantics |
| Rename column | High | New FeatureView; parallel serve |
| Type change | High | New column name; never in-place cast |
| Window logic change | High | New view; retrain models |

## Expand-contract for features

**Expand**

```python
@feature_view(
    name="merchant_risk_v2",
    schema=[
        Field(name="risk_score", dtype=Float32),
        Field(name="risk_score_legacy", dtype=Int64),  # parallel during migration
    ],
    ...
)
```

**Migrate consumers** — training notebooks, inference services, dashboards.

**Contract** — remove `risk_score_legacy` after registry shows zero reads for 30 days (metric from serving SDK wrapper).

## Backfill coordination

Schema additions with history requirements:

1. Deploy schema with nullable new field (all nulls OK).
2. Offline backfill SQL for historical partitions.
3. Incremental materialization per window.
4. Verify null rate < threshold globally.
5. Enable model flag reading new field.

Block step 5 in CI if completeness check fails.

## Inference backward compatibility

```python
def vector_to_model_input(feast_dict):
    score = feast_dict.get("risk_score")
    if score is None:
        score = feast_dict.get("risk_score_legacy", 0)
        if score is not None:
            score = float(score)  # explicit cast during migration
    return {"risk_score": score}
```

Remove fallback only after metrics prove full materialization.

## Registry and SDK pinning

```dockerfile
# inference image
ARG FEAST_VERSION=0.38.4
RUN pip install feast==${FEAST_VERSION}
```

Materialization and serving must share minor version during schema changes. Document in CHANGELOG:

```
FEAST-412: merchant_risk_v2 adds risk_score Float32
- requires feast>=0.38.4
- backfill complete 2026-08-01
- legacy view deprecated 2026-09-01
```

## Communication template

Post to `#ml-platform` and catalog subscribers:

- What changed
- Consumer action required (Y/N)
- Backfill ETA
- Rollback plan (flag off, revert Git SHA)

## Testing in CI

```python
def test_schema_matches_registry():
    repo_schema = load_repo_feature_view("merchant_risk_v2")
    registry_schema = store.get_feature_view("merchant_risk_v2")
    assert repo_schema.schema == registry_schema.schema
```

Schema evolution fails gracefully when you version aggressively, backfill before enforce, and treat renames as new contracts—not find-and-replace Friday deploys.
""",
)

POSTS_P3["devops-finops-showback-chargeback"] = (
    {
        "title": "FinOps Showback and Chargeback for Kubernetes",
        "description": "Allocate cluster cost by team, namespace, and label using OpenCost or Kubecost—showback drives behavior; chargeback drives budgets.",
        "datePublished": "2026-06-05",
        "tags": ["DevOps", "FinOps", "Platform"],
        "keywords": "FinOps showback, chargeback, OpenCost, Kubecost, Kubernetes cost allocation",
        "faq": [
            {
                "q": "What is the difference between showback and chargeback?",
                "a": "Showback reports costs to teams without financial transfer—informational dashboards. Chargeback actually bills internal teams via finance systems. Start with showback until allocation methodology is trusted; premature chargeback creates political fights over shared costs.",
            },
            {
                "q": "How do you allocate shared cluster overhead?",
                "a": "Split control plane, observability stack, and idle node capacity by proportional share of requested CPU/memory or by equal split across tenants. Document the formula publicly—opaque allocation erodes trust faster than high bills.",
            },
            {
                "q": "Which Kubernetes labels are required for cost allocation?",
                "a": "Minimum: team or cost-center, environment, and application. Enforce via admission policy (OPA/Gatekeeper) rejecting pods without `cost-center` and `team` labels. Namespaces alone are insufficient when multiple apps share one namespace.",
            },
            {
                "q": "OpenCost or Kubecost for platform teams?",
                "a": "OpenCost is CNCF-focused, lighter, Prometheus-native—good for DIY showback. Kubecost adds granular right-sizing recommendations, multi-cloud normalization, and enterprise chargeback integrations. Both use metrics-server + Prometheus; pick based on finance integration needs.",
            },
        ],
    },
    r"""Platform received a $400k annual cloud bill with one line item: `EKS-PROD-USE1`. Finance asked which product teams owed what. Engineering opened the AWS console, gave up after twenty minutes, and negotiated a flat headcount tax—exactly the outcome FinOps practices exist to prevent.

You cannot optimize what you cannot attribute. Kubernetes without cost labels is a communal kitchen where nobody buys dish soap.

## Allocation model

```
Team cost =
  Σ (pod CPU/memory request × node blended rate × uptime)
  + share of idle capacity by request ratio
  + share of cluster services (ingress, monitoring, DNS)
  + attached storage and cross-AZ egress attributed by namespace
```

Blended rate = (node compute cost + amortized RI/Savings Plan discount) / allocatable capacity. Update monthly—spot vs on-demand mix shifts.

## Label enforcement

```yaml
# Gatekeeper ConstraintTemplate excerpt
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: k8srequiredlabels
spec:
  crd:
    spec:
      names:
        kind: K8sRequiredLabels
      validation:
        openAPIV3Schema:
          properties:
            labels:
              type: array
              items:
                type: string
  targets:
    - target: admission.k8s.gatekeeper.sh
      rego: |
        violation[{"msg": msg}] {
          required := input.parameters.labels
          provided := input.review.object.metadata.labels
          missing := required[_]
          not provided[missing]
          msg := sprintf("Missing required label: %v", [missing])
        }
```

Apply to Deployments and StatefulSets in tenant namespaces.

## OpenCost deployment sketch

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: opencost
  namespace: opencost
spec:
  template:
    spec:
      containers:
        - name: opencost
          image: opencost/opencost:1.109.0
          env:
            - name: PROMETHEUS_SERVER_ENDPOINT
              value: "http://prometheus.monitoring:9090"
            - name: CLOUD_PROVIDER_API_KEY
              valueFrom:
                secretKeyRef:
                  name: opencost-api-key
                  key: key
```

Export metrics to Prometheus; Grafana dashboard by `namespace`, `label_team`.

## Showback report cadence

| Audience | Cadence | Content |
|----------|---------|---------|
| Team leads | Weekly | Top 5 cost drivers, week-over-week delta |
| Engineering VP | Monthly | Trends, anomalies, optimization wins |
| Finance | Monthly | CSV by cost-center for ERP import (chargeback phase) |

Include **unit economics**: cost per 1M API requests, cost per training job hour—helps teams compare fairly.

## Shared cost politics

Document upfront:

- **Idle capacity**: allocated by request share, not usage— incentivizes right-sizing requests.
- **GPU nodes**: tagged `gpu-type`; ML teams pay premium rate card.
- **Cross-team databases**: owned by DBA cost-center unless tagged `client-team` on connection pooler.

Disputes go to FinOps council with published methodology PDF—not Slack arguments.

## Optimization loop

Showback without action is wallpaper. Pair reports with:

- Rightsizing recommendations (Kubecost or Goldilocks)
- Spot eligibility for fault-tolerant workloads
- Namespace quota reviews when team exceeds budget threshold

Chargeback phase: finance imports monthly CSV, debits internal budgets. Requires 3+ months of trusted showback.

FinOps for Kubernetes is 20% tooling and 80% label discipline and transparent math. The tax invoice nobody understands is the one everyone ignores.
""",
)
