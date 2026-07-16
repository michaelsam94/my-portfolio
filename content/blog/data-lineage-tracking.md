---
title: "Data Lineage Tracking"
slug: "data-lineage-tracking"
description: "Lineage shows where data came from and where it went. Column-level graphs, automated capture, impact analysis, and why manual diagrams always lie."
datePublished: "2025-07-20"
dateModified: "2025-07-20"
tags: ["Data Engineering", "Analytics"]
keywords: "data lineage, impact analysis, OpenLineage, DataHub, column lineage, data governance"
faq:
  - q: "What is data lineage?"
    a: "Data lineage is the directed graph of how data flows from sources through transformations to downstream tables, dashboards, and ML features. Table-level lineage shows dependencies between datasets; column-level lineage traces individual fields through joins and expressions."
  - q: "Why does automated lineage beat manual documentation?"
    a: "Manual lineage diagrams stale within days of the first undeployed PR. Automated capture parses SQL, reads dbt manifests, hooks orchestrators, and updates on every job run. Impact analysis during schema changes requires freshness measured in hours, not quarters."
  - q: "How do I implement lineage without a commercial tool?"
    a: "Start with dbt docs lineage from manifest.json, OpenLineage events from Airflow or Spark, and warehouse query logs for ad-hoc dependencies. Combine in DataHub or Marquez. Full column lineage needs SQL parsing or engine-native hooks — table-only lineage is a valid first phase."
---

The question that justifies lineage investment: "If I change this column, what breaks?" Without an answer, schema migrations become roulette. Lineage turns them into a checklist — every downstream dashboard, export, and model flagged before merge.

## Table vs column lineage

**Table lineage** — `raw.orders` → `stg_orders` → `fct_orders` → Looker explore. Enough for ownership, freshness alerts, and coarse impact analysis.

**Column lineage** — `raw.orders.discount_code` → `stg_orders.promo_id` → `fct_orders.net_revenue` (via `gmv - discount`). Required for PII tagging propagation, GDPR deletion requests, and precise migration scoping.

Most teams start table-level; add column-level where compliance or complex transforms demand it.

## Capture mechanisms

| Source | What it captures |
|---|---|
| dbt `manifest.json` | Model DAG, source declarations |
| OpenLineage facets | Job runs, input/output datasets |
| Spark / Flink listeners | Engine-native read/write events |
| SQL parsers (sqlglot, sqllineage) | Ad-hoc warehouse queries |
| BI metadata APIs | Dashboard → dataset links |

OpenLineage standardizes event emission:

```python
# Simplified OpenLineage emit from a Python job
from openlineage.client import OpenLineageClient
from openlineage.client.run import Run, Job, Dataset

client = OpenLineageClient(url="http://marquez:5000")
client.emit(
    Run(
        runId=str(uuid.uuid4()),
        job=Job(namespace="prod", name="daily_revenue_etl"),
        inputs=[Dataset(namespace="snowflake", name="analytics.stg_orders")],
        outputs=[Dataset(namespace="snowflake", name="analytics.fct_revenue")],
    )
)
```

Orchestrators (Airflow with the OpenLineage provider, Dagster's asset graph) emit these automatically when configured.

## Impact analysis workflow

When deprecating `legacy_user_id`:

1. Query lineage for downstream nodes within N hops
2. Notify owners from catalog metadata
3. Block schema PR until acks or migration tickets exist
4. Run regression tests on affected dbt models

```yaml
# dbt exposure links dashboards to models — feeds lineage
exposures:
  - name: executive_revenue_dashboard
    type: dashboard
    maturity: high
    depends_on:
      - ref('fct_daily_revenue')
    owner:
      email: finance-analytics@company.com
```

Exposures close the gap between warehouse tables and business consumers.

## Lineage quality problems

**Missing ad-hoc queries.** Analysts create `CREATE TABLE AS SELECT` outside dbt — invisible until you mine warehouse audit logs.

**Broken parser coverage.** Exotic SQL, multi-statement scripts, and dynamic SQL defeat static analysis. Tag those jobs manual-review.

**Environment mixing.** Dev tables linked to prod dashboards poison graphs. Namespace by environment strictly.

**Stale edges.** Deleted models linger until garbage collection. Schedule lineage reconciliation jobs.

Treat lineage confidence as a metric — `% edges verified in last 7 days`.

## Privacy and compliance use cases

Lineage answers "where does email propagate?" for DSAR deletion — trace columns tagged `pii:email` through transforms, identify all materialized copies, queue deletion or anonymization jobs.

Audit trails pair with Iceberg/Delta time travel: lineage says what depends on what; snapshots say what values looked like when.

## Organizational adoption

Embed lineage in PR bots: "This change affects 4 models and 2 Looker explores." Don't make engineers open a separate portal for every question.

Start with production dbt project + top Airflow DAGs. Expand to Spark and BI when table-level coverage exceeds 80% of critical assets.

## Lineage in CI/CD workflows

Embed lineage checks in the development workflow, not as a separate portal:

**PR bot integration:**

```yaml
# GitHub Action: on dbt model change, query lineage API
- name: Lineage impact check
  run: |
    AFFECTED=$(datahub get --urn "urn:li:dataset:(urn:li:dataPlatform:dbt,${{ env.MODEL_NAME }},PROD)" --downstream)
    echo "Downstream impact: $AFFECTED"
    # Post as PR comment
```

When an engineer changes `stg_orders`, the PR automatically lists affected marts, dashboards, and ML features. Reviewers see blast radius before approving.

**Schema change gate:**

Block column renames/drops until downstream owners acknowledge:

1. Engineer proposes schema change in PR
2. Lineage API returns downstream nodes
3. Bot creates ack tickets for each downstream owner
4. Merge blocked until all acks received or migration plan documented

## OpenLineage in practice

Standardize event emission across orchestrators:

```python
# Airflow with OpenLineage provider
from airflow.providers.openlineage.plugins.listener import OpenLineageListener

# Dagster emits automatically when configured
# Spark: spark.openlineage.* config properties
```

Events flow to Marquez or DataHub:

```
Airflow/Dagster/Spark → OpenLineage events → Marquez → DataHub ingestion
```

Start with table-level input/output datasets. Add column-level facets when compliance requires it.

## Lineage for ML feature stores

ML pipelines often escape traditional lineage:

```
raw.events → dbt stg_events → fct_user_features → feature store → model v3
```

Register feature store tables as dbt exposures or OpenLineage datasets. When `fct_user_features.churn_score` changes, lineage should show which model versions and serving endpoints are affected.

Without this, data scientists discover feature schema changes when predictions silently degrade.

## Failure modes

- **Ad-hoc SQL invisible** — analysts CREATE TABLE AS SELECT outside dbt; mine warehouse audit logs to discover
- **Stale lineage graph** — deleted models linger as orphaned nodes; schedule reconciliation
- **Environment mixing** — dev tables linked to prod dashboards; namespace strictly by environment
- **Manual diagrams as source of truth** — outdated within weeks; automate or don't bother
- **Column lineage without confidence score** — parser-guessed edges treated as verified; tag confidence level

## Production checklist

- dbt manifest.json ingested into lineage catalog
- OpenLineage events emitted from orchestrator (Airflow/Dagster)
- dbt exposures link models to dashboards and ML features
- PR bot shows downstream impact on model changes
- Schema change gate requires downstream owner ack
- Lineage freshness metric tracked (% edges verified in last 7 days)
- Ad-hoc query audit supplements automated capture

Column-level lineage via SQL parsing (sqlglot, DataHub SQL parser) adds precision but increases maintenance — enable for PII-tagged columns first, expand based on compliance audit requirements.

Run lineage impact analysis before every column rename in production — downstream dashboards break silently long before the warehouse team notices schema drift.

## Resources

- [OpenLineage project](https://openlineage.io/)
- [Marquez — OpenLineage reference implementation](https://marquezproject.ai/)
- [DataHub lineage features](https://datahubproject.io/docs/features/feature-guides/lineage/)
- [dbt exposures documentation](https://docs.getdbt.com/docs/build/exposures)
- [sqllineage — Python SQL lineage parser](https://github.com/reata/sqllineage)
