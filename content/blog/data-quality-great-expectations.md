---
title: "Data Quality with Great Expectations"
slug: "data-quality-great-expectations"
description: "Great Expectations validates datasets with declarative tests and data docs. Suites, checkpoints, custom expectations, and fitting GX into dbt pipelines."
datePublished: "2025-08-04"
dateModified: "2025-08-04"
tags: ["Data Engineering", "Analytics"]
keywords: "Great Expectations, data quality, data validation, GX checkpoints, expectation suite, dbt tests"
faq:
  - q: "What does Great Expectations do?"
    a: "Great Expectations (GX) lets you define expectations — assertions about your data like 'column email must be unique' or 'order_total must be between 0 and 100000'. Checkpoints run suites against batches and produce pass/fail results plus HTML Data Docs for stakeholders."
  - q: "How is Great Expectations different from dbt tests?"
    a: "dbt tests run in-warehouse on models during dbt build — tight integration, SQL-native. GX supports multiple execution engines, profiling-driven expectation generation, richer documentation, and validation of raw landing-zone files before dbt touches them. Many teams use both: GX on ingest, dbt on transforms."
  - q: "Where should data quality checks run in the pipeline?"
    a: "As close to the failure point as possible — validate raw ingest before propagation, validate marts before BI refresh. Fail fast on blocking issues; warn on drift. Store results in a metadata store for trending, not just pass/fail logs."
---

Bad data reaching the CEO dashboard hurts more than a failed Airflow task nobody notices until Monday. Great Expectations gives data teams vocabulary for "this column should look like X" — executable, documented, and shareable with people who don't read SQL.

## Core concepts

| Term | Meaning |
|---|---|
| Expectation | Single assertion (`expect_column_values_to_not_be_null`) |
| Expectation suite | Collection of expectations for a dataset |
| Batch | Data slice validated (table, query result, file) |
| Checkpoint | Runs a suite against a batch with actions |
| Data Docs | Generated HTML site showing results and profiling |

```python
import great_expectations as gx

context = gx.get_context()

suite = context.suites.add(
    gx.ExpectationSuite(name="orders_suite")
)
suite.add_expectation(
    gx.expectations.ExpectColumnValuesToNotBeNull(column="order_id")
)
suite.add_expectation(
    gx.expectations.ExpectColumnValuesToBeBetween(
        column="total_cents", min_value=0, max_value=10_000_000
    )
)
```

Suites live in git — review expectation changes like code.

## Checkpoints in CI and production

```python
checkpoint = context.checkpoints.add(
    gx.Checkpoint(
        name="orders_daily",
        validations=[
            {
                "batch_request": {
                    "datasource_name": "snowflake",
                    "data_asset_name": "analytics.fct_orders",
                },
                "expectation_suite_name": "orders_suite",
            }
        ],
        actions=[
            {"name": "store_validation_result"},
            {"name": "update_data_docs"},
        ],
    )
)
result = checkpoint.run()
if not result.success:
    raise RuntimeError("Orders validation failed")
```

Wire checkpoint failure to PagerDuty for gold-tier assets; Slack warning for silver.

## Profiling to bootstrap suites

GX profilers scan sample batches and suggest expectations — uniqueness ratios, value ranges, regex patterns for emails. Don't accept blindly; analysts confirm business rules. Profiling catches schema drift early when a new enum value appears.

Run profiling on staging after source schema changes; diff suggested expectations in PR.

## Custom expectations

When built-ins aren't enough:

```python
from great_expectations.expectations import BatchExpectation

class ExpectOrderTotalMatchesLines(BatchExpectation):
    metric_dependencies = ("column.sum",)
    # validate sum(line_items) == order_total per order_id
```

Custom expectations package domain logic — "refund amount never exceeds original charge" — reusable across checkpoints.

## GX + dbt together

Reasonable split:

- **GX** — raw landing zone, external vendor files, pre-dbt sanity
- **dbt tests** — model grain, relationships, accepted values on curated marts

Orchestrate GX checkpoint before dbt run in Dagster/Airflow. If raw fails, skip warehouse spend.

GX 1.0+ integrates with Fluent API and cloud-hosted GX; self-hosted OSS core remains viable for many teams.

## Operational maturity

Track validation success rate over time — flapping expectations indicate bad thresholds, not bad data. Version suites; tie checkpoint names to SLAs in catalog metadata.

Avoid expectation sprawl: 200 weak checks dilute signal. Tier blocking vs warning:

```yaml
# Conceptual policy
gold_tables:
  blocking: [not_null on keys, referential integrity, row count bounds]
silver_tables:
  blocking: [not_null on keys]
  warning: [distribution drift]
```

## Common pitfalls

Testing production directly without sampling on huge tables — use `LIMIT` batches or warehouse sampling. Expectations on volatile columns without wide bounds. No owner for fixing failures — route alerts to dataset owner from catalog.

## Expectation tiers and SLAs

Not every table deserves the same rigor. Tier expectations by business impact:

| Tier | Examples | Blocking expectations | Alert channel |
|---|---|---|---|
| Gold | Revenue facts, payment ledger | Keys, referential integrity, row count bounds, business rules | PagerDuty |
| Silver | Product analytics, user events | Keys, not-null on critical columns | Slack #data-alerts |
| Bronze | Raw landing, vendor dumps | Schema presence, row count > 0 | Email digest |

Gold failures halt downstream pipelines. Silver failures warn but allow dbt to proceed with flagged models. Bronze failures log for investigation.

Document tier in your data catalog — dataset owners know their SLA without asking.

## Schema drift detection

The most valuable expectations aren't business rules — they're schema change detectors:

```python
# Auto-generated from last successful profile
suite.add_expectation(
    ExpectTableColumnCountToEqual(value=42)
)
suite.add_expectation(
    ExpectColumnToExist(column="customer_id")
)
suite.add_expectation(
    ExpectColumnValuesToBeInSet(
        column="status",
        value_set=["pending", "confirmed", "shipped", "delivered"],
    )
)
```

When a source adds `status = 'cancelled'` or drops a column, expectations fail before bad data propagates through five dbt models. Run schema expectations on raw landing zone immediately after ingest.

## Integration with orchestration

Wire GX into your pipeline as a gate, not an afterthought:

```python
# Airflow DAG pattern
with DAG("daily_orders") as dag:
    ingest = PythonOperator(task_id="ingest", ...)
    validate_raw = PythonOperator(
        task_id="validate_raw",
        python_callable=run_gx_checkpoint,
        op_kwargs={"checkpoint": "raw_orders_checkpoint"},
    )
    dbt_run = BashOperator(task_id="dbt_run", ...)
    validate_mart = PythonOperator(
        task_id="validate_mart",
        python_callable=run_gx_checkpoint,
        op_kwargs={"checkpoint": "fct_orders_checkpoint"},
    )

    ingest >> validate_raw >> dbt_run >> validate_mart
```

If `validate_raw` fails, dbt never runs — you don't transform garbage. If `validate_mart` fails, BI refresh is blocked but raw data is intact for debugging.

## Trending validation results over time

Single pass/fail is noisy. Store validation results and trend:

- **Pass rate per expectation** — flapping `expect_column_mean_to_be_between` means bounds are too tight, not that data is bad
- **Row count over time** — sudden 50% drop indicates upstream issue, not gradual drift
- **Null rate trending** — slow increase in nulls catches silent source degradation

GX Cloud and self-hosted metadata stores support this. Review monthly with dataset owners — adjust bounds or fix upstream.

## Failure modes

- **Expectation sprawl** — 200 expectations per table; failures are noise. Cap at 10–15 blocking per gold table
- **Testing prod without sampling** — full table scan on billion-row table blocks warehouse. Sample or use incremental batches
- **No owner on failure** — alert goes to `#data` channel, nobody acts. Route to catalog owner
- **Stale expectations** — business rules changed six months ago, expectations didn't. Review quarterly
- **GX-only, no dbt tests** — marts lack relationship tests. Use both at appropriate pipeline stages

## Production checklist

- Expectations tiered by business impact (gold/silver/bronze)
- Schema drift expectations on raw landing zone
- GX checkpoint gates orchestration before dbt run
- Validation results stored and trended over time
- Dataset owner assigned for every checkpoint failure alert
- Quarterly expectation review with analysts
- Sampling configured for large table validations

## Resources

- [Great Expectations documentation](https://docs.greatexpectations.io/docs/)
- [GX expectation gallery](https://greatexpectations.io/expectations/)
- [Integrating GX with Airflow](https://docs.greatexpectations.io/docs/integrations/integration_airflow/)
- [dbt data tests](https://docs.getdbt.com/docs/build/data-tests)
- [Soda Core — alternative validation framework](https://docs.soda.io/)
