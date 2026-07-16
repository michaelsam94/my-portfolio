---
title: "Orchestrating Data with Dagster"
slug: "data-orchestration-airflow-dagster"
description: "Dagster models pipelines as software-defined assets with lineage built in. How it compares to Airflow for data teams and when to adopt asset-based orchestration."
datePublished: "2025-07-29"
dateModified: "2025-07-29"
tags: ["Data Engineering", "Analytics"]
keywords: "Dagster, Airflow, data orchestration, software-defined assets, data pipeline, Dagster vs Airflow"
faq:
  - q: "How is Dagster different from Apache Airflow?"
    a: "Airflow orchestrates tasks defined as DAGs with explicit dependencies — good for general workflow scheduling. Dagster centers on data assets — tables, files, models — with ops that materialize them. Lineage, partitioning, and testing are first-class. Dagster fits data pipelines where 'what datasets exist' matters more than 'what tasks ran'."
  - q: "What are software-defined assets in Dagster?"
    a: "Assets are declarative definitions of data objects — often mapping to dbt models, Spark tables, or files — with functions that produce them. Dagster tracks materialization history, partitions, and upstream/downstream relationships automatically, reducing boilerplate compared to wiring Airflow sensors and XComs manually."
  - q: "Can I run Airflow and Dagster together?"
    a: "Yes. Many teams migrate incrementally — Dagster orchestrates new asset-based pipelines while Airflow runs legacy DAGs. Dagster can trigger external jobs and ingest Airflow metadata. Long term, consolidating reduces dual operational overhead."
---

I've operated both Airflow clusters that grew into undebuggable sensor graphs and Dagster deployments where "why didn't `fct_orders` update?" had a one-click asset lineage answer. The tools solve overlapping problems with different centers of gravity — tasks versus datasets.

## Task-centric vs asset-centric

**Airflow** asks: did task `extract_orders` succeed at 3am?

**Dagster** asks: is asset `fct_orders` fresh for partition `2025-07-28`?

Both schedule work. Asset-centric orchestration maps closer to how analysts think — they care about table freshness, not which pod ran `bash_operator.sh`.

```python
from dagster import asset, AssetExecutionContext, DailyPartitionsDefinition

partitions = DailyPartitionsDefinition(start_date="2025-01-01")

@asset(partitions_def=partitions)
def stg_orders(context: AssetExecutionContext) -> None:
    partition_date = context.partition_key
    # load raw orders for partition_date into staging table
    ...

@asset(partitions_def=partitions, deps=[stg_orders])
def fct_orders(context: AssetExecutionContext) -> None:
    ...
```

`deps` builds the graph; Dagster UI shows asset lineage without extra tooling.

## Partitions and backfills

Partitioned assets are Dagster's killer feature for daily/hourly pipelines:

```python
from dagster import define_asset_job, AssetSelection

daily_job = define_asset_job(
    "daily_refresh",
    selection=AssetSelection.assets("fct_orders", "dim_customers"),
    partitions_def=partitions,
)
```

Backfill a date range from the UI or CLI — `dagster asset materialize --partition 2025-07-01`. Airflow achieves this with dynamic task mapping or param-heavy DAGs; Dagster bakes it into the asset model.

## Integrations

- **dbt** — `@dbt_assets` decorator loads manifest, maps models to assets
- **Spark / Pandas** — ops and assets for transforms
- **Airbyte / Fivetran** — ingestion as upstream assets
- **Sensors and schedules** — event-driven and cron materialization

```python
from dagster_dbt import DbtProject, dbt_assets

dbt_project = DbtProject(project_dir="analytics_dbt")

@dbt_assets(manifest=dbt_project.manifest_path)
def analytics_dbt_assets(context, dbt):
    yield from dbt.cli(["build"], context=context).stream()
```

One materialization run updates every dbt model as an asset with shared lineage.

## Testing and observability

Asset checks validate outputs after materialization:

```python
from dagster import asset_check, AssetCheckResult

@asset_check(asset=fct_orders)
def orders_not_empty():
    count = query("SELECT count(*) FROM fct_orders")
    return AssetCheckResult(passed=count > 0)
```

Failures surface on the asset page — closer to CI than Airflow's task log archaeology. OpenTelemetry and run tags support cost attribution per asset.

## When Airflow still wins

- Non-data workflows (ML training grids, infra jobs) where assets add no clarity
- Teams with deep Airflow investment, custom operators, and mature ops
- Simple linear ETL with no partition backfill complexity

Airflow 3 improves UX, but the task-first model remains unless you adopt asset patterns manually.

## Migration strategy

1. Register existing warehouse tables as external assets (observation-only)
2. Rebuild one domain pipeline — ingestion → dbt — as Dagster assets
3. Compare SLA attainment and mean time to debug
4. Migrate partition backfill-heavy DAGs next
5. Retire Airflow DAGs when asset parity proven

Don't big-bang migrate 400 DAGs.

## Operational notes

Dagster runs as Dagster webserver + daemon + code location (gRPC). Helm charts support Kubernetes. Store IO managers for S3/Snowflake/BigQuery consistently — ad-hoc path logic in assets becomes debt.

## Dagster deployment architecture

Production Dagster has four components:

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Webserver   │────▶│    Daemon     │────▶│  Code Location   │
│  (UI + API)  │     │ (schedules,   │     │  (your assets,   │
│              │     │  sensors)     │     │   gRPC server)   │
└─────────────┘     └──────────────┘     └─────────────────┘
                            │
                     ┌──────▼──────┐
                     │  PostgreSQL  │
                     │ (run storage)│
                     └─────────────┘
```

- **Webserver** — UI for asset graph, run history, backfills
- **Daemon** — executes schedules and sensors; polls for new runs
- **Code location** — your Python package with asset definitions; hot-reloadable
- **Run storage** — PostgreSQL stores run metadata, event logs, asset materialization history

Deploy code locations independently from infrastructure — push new asset code without restarting the daemon.

## Sensors vs schedules

Dagster offers two trigger mechanisms:

```python
from dagster import sensor, RunRequest, DefaultSensorStatus

@sensor(job=daily_job, minimum_interval_seconds=300)
def s3_file_sensor(context):
    new_files = check_s3_prefix("s3://landing/incoming/")
    for file in new_files:
        yield RunRequest(
            run_key=file.key,
            partition_key=file.date,
        )

from dagster import ScheduleDefinition
daily_schedule = ScheduleDefinition(
    job=daily_job,
    cron_schedule="0 6 * * *",
)
```

Sensors react to external events (new file, upstream completion). Schedules run on cron. Use sensors for event-driven pipelines; schedules for predictable daily/hourly refreshes.

## Cost attribution and run tags

Tag runs for cost tracking:

```python
@asset(op_tags={"team": "analytics", "cost_center": "marketing"})
def marketing_attribution(context):
    ...

# Or at job level
daily_job = define_asset_job(
    "daily_refresh",
    tags={"team": "analytics", "warehouse": "snowflake"},
)
```

Query run storage for compute cost by team, warehouse, or asset group. Essential when multiple teams share one Dagster deployment.

## Airflow → Dagster migration patterns

Incremental migration path I've seen work:

1. **Observe-only** — register existing warehouse tables as external assets; no execution change
2. **One domain** — rebuild marketing pipeline as Dagster assets alongside existing Airflow DAG
3. **Compare** — MTTR for pipeline failures, backfill UX, developer onboarding time
4. **Migrate partitioned DAGs** — Airflow dynamic task mapping → Dagster partitioned assets (biggest UX win)
5. **Retire** — disable Airflow DAG when Dagster asset proven for 30 days

Don't migrate generic infra/ML DAGs — they don't benefit from asset modeling.

## Failure modes

- **Asset without IO manager** — ad-hoc S3 paths in every asset function; standardize early
- **No asset checks** — data quality issues discovered by analysts, not at materialization time
- **Sensor storm** — sensor polling too frequently; daemon overwhelmed. Set `minimum_interval_seconds`
- **Monolithic code location** — one giant Python package; split by domain into multiple code locations
- **Ignoring partitions** — processing full table daily when only yesterday's partition changed

## Production checklist

- IO manager configured for each storage backend (S3, Snowflake, BigQuery)
- Asset checks validate critical outputs after materialization
- Partitions defined for time-series data with backfill tested
- Run tags for cost attribution by team/domain
- Sensors have minimum interval configured
- Code locations split by domain, not one monolithic package
- dbt integration via `@dbt_assets` for model lineage

Dagster Cloud offers hosted deployment with branch deployments for PR previews — each PR gets an isolated asset graph for testing pipeline changes before merge.

## Resources

- [Dagster documentation](https://docs.dagster.io/)
- [Dagster dbt integration guide](https://docs.dagster.io/integrations/dbt)
- [Apache Airflow documentation](https://airflow.apache.org/docs/)
- [Dagster vs Airflow comparison (Dagster)](https://dagster.io/blog/airflow-vs-dagster)
- [Software-Defined Assets blog post](https://docs.dagster.io/concepts/assets/software-defined-assets)
