---
title: "ETL vs ELT Pipelines"
slug: "etl-vs-elt-pipelines"
description: "Choose ETL or ELT for your data stack: where transforms run, warehouse-native patterns, streaming vs batch, and cost implications on Snowflake and BigQuery."
datePublished: "2026-01-12"
dateModified: "2026-01-12"
tags: ["Data Engineering", "ETL", "ELT", "Analytics"]
keywords: "ETL vs ELT, extract load transform, modern data stack ELT, dbt transformations, data pipeline architecture, warehouse-native transforms, batch vs streaming ETL"
faq:
  - q: "What is the main difference between ETL and ELT?"
    a: "ETL transforms data before loading into the destination — traditional with on-prem warehouses and limited compute. ELT loads raw data first, then transforms inside the warehouse using its compute (SQL, dbt). ELT dominates cloud analytics because separation of storage and compute makes transform-after-load cheaper and more flexible."
  - q: "When should I still use ETL instead of ELT?"
    a: "Use ETL when you must reduce data before cloud egress (PII filtering at source), target system lacks transform compute (operational DB replicas), regulatory constraints forbid raw landing zones, or transforms are CPU-heavy ML feature prep better done in Spark before load."
  - q: "Does ELT mean I skip data quality checks?"
    a: "No — shift quality left with ingestion contracts and right with dbt tests after load. ELT changes where transforms run, not whether you validate. Raw landing zones need schema evolution handling and access controls like any curated layer."
---

The pipeline team spent six months maintaining a fragile Python ETL cluster that transformed CSV exports before loading Snowflake — then bought more warehouse credits anyway because analysts re-ran the same joins in SQL. Cloud warehouses with elastic compute inverted the old constraint: storage is cheap, transformation SQL near data is fast, and maintaining separate ETL servers is overhead. ELT (extract, load, transform) became the default modern pattern — but ETL still wins when you must strip PII before bits leave a hospital network or shrink payloads crossing expensive egress. The choice is architectural, not religious.

## Pattern comparison

```
ETL:
Source ──extract──► Transform engine ──load──► Warehouse (curated)

ELT:
Source ──extract──► Raw landing (warehouse/staging) ──transform──► Curated marts
                              ▲
                         dbt / SQL in warehouse
```

| Factor | ETL | ELT |
|--------|-----|-----|
| Transform location | External (Airflow+Python, Spark) | Warehouse (dbt) |
| Raw history | Often discarded | Usually retained |
| Schema flexibility | Rigid pre-load | Evolve transforms post-load |
| Ops burden | ETL infra + warehouse | Orchestration + warehouse |
| PII at rest in landing | Minimized | Requires governance |

## ELT with dbt (typical stack)

Ingestion: Fivetran, Airbyte, or custom sync → `raw` schema

```sql
-- models/staging/stg_orders.sql
select
    id as order_id,
    user_id,
    cast(total_cents as bigint) as total_cents,
    created_at::timestamp_tz as created_at
from {{ source('raw', 'orders') }}
where _fivetran_deleted = false
```

```sql
-- models/marts/fct_orders.sql
select
    order_id,
    user_id,
    total_cents / 100.0 as total_usd,
    date_trunc('day', created_at) as order_date
from {{ ref('stg_orders') }}
```

Orchestrate with Airflow/Dagster triggering dbt run after sync completes. Tests in dbt (`unique`, `not_null`, relationships) catch transform regressions.

## When ETL remains correct

**PII minimization before cloud:**

```python
# extract on-prem
for row in extract_from_ehr():
    yield {
        "patient_hash": hmac_patient_id(row["patient_id"]),
        "diagnosis_code": row["code"],
        # no raw name/DOB leaves building
    }
```

**Heavy ML feature engineering** — Spark computes embeddings on cluster; load feature table only.

**Operational replication** — CDC stream to Postgres read replica without warehouse round trip.

**Cost control on ingress** — compress/deduplicate terabytes before S3 Standard storage charges accumulate.

## Streaming blur the lines

Kafka → Flink SQL transforms → sink to Iceberg is stream-ETL. Kafka → raw topic → warehouse streaming ingest → dbt incremental is stream-ELT.

Pick based on latency SLA:

- Sub-minute dashboards → streaming transform or materialized views
- Hourly/daily analytics → batch ELT sufficient and simpler

## Governance for ELT raw zones

Raw landing is not "throw away security":

- Role-based access — analysts read marts, not raw PII columns
- Column masking policies in Snowflake/BigQuery
- Retention TTL on raw tables
- Lineage from dbt docs + ingestion metadata

Document contracts at source — breaking upstream schema change should fail ingestion, not silently null columns in mart.

## Migration path ETL → ELT

1. Replicate existing ETL output to staging as-is (parity check)
2. Load raw + rebuild one mart in dbt, diff row counts and sums
3. Cut dashboard to dbt mart behind flag
4. Decommission ETL job for that entity
5. Repeat per domain — big bang cutover risky

## Cost implications on cloud warehouses

ELT's "load raw first, transform later" philosophy has cost consequences:

**Storage cost:** Raw landing zones retain full history including columns never used in marts. Snowflake/BigQuery storage is cheap ($23–40/TB/month) but accumulates with PII-heavy raw tables.

**Compute cost:** dbt transforms run on warehouse compute — each model materialization consumes credits. Incremental models and view-based staging reduce this, but naive `materialized='table'` on everything burns credits.

**Egress cost:** ELT assumes data enters the warehouse once. ETL that pre-filters before load saves ingress egress on cloud boundaries — relevant for multi-cloud or on-prem-to-cloud pipelines.

Rule of thumb: ELT is cheaper when transforms are SQL-expressible and warehouse compute is elastic. ETL is cheaper when you must shrink payloads before they cross network boundaries or land in expensive storage.

## Hybrid architectures in practice

Most mature data teams run hybrid, not pure ELT:

```
Sources → Airbyte (EL) → raw landing → dbt (T in warehouse) → marts
                ↓
         PII filter at source (ET before L) for regulated columns
                ↓
         Spark ML features (ET before L) → feature store
```

Extract and load are almost always separated from transform in modern stacks. The question is whether transform happens before load (ETL) or after (ELT) — and the answer is often "both, for different data domains."

## Data contracts at the ingestion boundary

ELT doesn't eliminate the need for upstream contracts:

```yaml
# data contract: raw.orders
schema:
  - name: id
    type: integer
    required: true
  - name: total_cents
    type: integer
    required: true
  - name: status
    type: string
    allowed_values: [pending, paid, shipped, cancelled]
freshness:
  max_delay_minutes: 60
quality:
  - column: id
    tests: [unique, not_null]
```

When upstream breaks the contract (new enum value, missing column), ingestion should fail loudly — not silently load nulls that break dbt marts downstream.

## Failure modes

- **Raw zone without governance** — PII exposed to all warehouse users; column masking required
- **Everything materialized as table in dbt** — warehouse compute cost explosion; use views for staging
- **No data contracts at ingestion** — silent schema changes break marts days later
- **ETL cluster maintained alongside dbt** — duplicate transform logic in Python and SQL
- **Ignoring delete propagation** — ELT raw zone retains deleted rows; dbt must filter `_fivetran_deleted`

## Production checklist

- Raw landing zone with RBAC (not all users access raw PII)
- dbt staging as views, marts as tables/incremental
- Data contracts defined at ingestion boundary
- PII filtered at source for regulated data (ET before L)
- Delete propagation handled in staging models
- Cost monitoring on warehouse compute per dbt run
- Migration from ETL validated with row count/sum parity checks

## Resources

- [dbt documentation — what is dbt](https://docs.getdbt.com/docs/introduction)
- [Airbyte open-source ingestion](https://docs.airbyte.com/)
- [Snowflake ELT patterns](https://docs.snowflake.com/en/guides-overview-loading-data)
- [The Data Warehouse ETL Toolkit (Kimball)](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/etl-system/)
- [Dagster — orchestrating data pipelines](https://docs.dagster.io/)
