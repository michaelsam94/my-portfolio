---
title: "Data Quality Gates with Great Expectations"
slug: "devops-pipeline-data-quality-great-expectations"
description: "Block pipeline promote on Great Expectations suites and data docs."
datePublished: "2026-08-27"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Data Pipelines"
  - "Data Engineering"
keywords: "Great Expectations, data quality"
faq:
  - q: "When should teams prioritize Data Quality Gates with Great Expectations?"
    a: "On pipelines feeding ML or finance tables."
  - q: "What is the most common mistake with Great Expectations?"
    a: "Expectations on sample only—full partition violations missed."
  - q: "Should Great Expectations block deploy or only warn?"
    a: "Block promotion to production tables and downstream consumers that cannot tolerate silent corruption. Warn on staging and dev with the same suite so expectations stay aligned. Finance and ML feature tables should fail closed."
  - q: "How do you test Great Expectations without slowing every commit?"
    a: "Run lightweight expectations on samples in PR CI; run full-partition suites on schedule and before merge to main. Cache validation artifacts and parallelize by partition key."
---
Null primary keys loaded to prod—GE suite existed but not in critical path.

## What changes when you leave the tutorial


Block pipeline promote on Great Expectations suites and data docs.

Production data quality gates with great expectations fails on retries, partial outages, and human process gaps — not on the happy-path tutorial.

## Design constraints you cannot ignore


Prefer defaults that fail closed: deny, queue, or degrade safely rather than return silently wrong data.

Document who may change Great Expectations in production, how rollback works, and which environments are allowed to diverge.

## Step-by-step in production order


1. Inventory consumers and SLAs. 2. Implement enforcement on the write/promote path. 3. Add observability. 4. Drill failure modes. 5. Expand scope.

Validate each step with someone who did not write the original Great Expectations config — fresh eyes catch assumptions.

## Edge cases that bypass happy-path tests


Edge cases: late-arriving data, duplicate events, schema drift mid-run, credential rotation during job execution, and traffic spikes during deploy.

For each, document drop vs retry vs dead-letter vs fail-closed — and test it.

## Observability hooks


Structured logs with run_id, partition, and validation outcome. Metrics with bounded labels — never high-cardinality user IDs on Prometheus.

Traces across orchestrator, worker, and warehouse when requests cross team boundaries.

## Summary


Data Quality Gates with Great Expectations earns its keep when it prevents silent corruption, unsafe deploys, or unbounded cost — not when it decorates a architecture diagram.

## Reference configuration


```python
# checkpoint blocks dbt/Airflow promote
context = gx.get_context()
result = context.run_checkpoint(
    checkpoint_name="orders_daily_prod_gate",
    batch_request={
        "datasource_name": "warehouse",
        "data_asset_name": "orders",
        "batch_parameters": {"partition_date": "{{ ds }}"},
    },
)
if not result.success:
    raise AirflowException(result.run_results)
```

## Partition-level validation

Sample-only expectations miss full-partition violations — null keys on edge partitions, timezone-boundary duplicates, and late-arriving facts. Schedule full scans before promote and incremental expectations on every run. Store validation results as queryable tables so analysts see history, not only pass/fail in Slack.

## Operating Great Expectations at scale

After the first successful deploy of data quality gates with great expectations, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Great Expectations settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Data Pipelines pipelines touch ingestion, serving, and finance. Document interfaces where Great Expectations gates hand off to downstream owners so failures are not bounced without context.

## Operating Great Expectations at scale

After the first successful deploy of data quality gates with great expectations, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Great Expectations settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Data Pipelines pipelines touch ingestion, serving, and finance. Document interfaces where Great Expectations gates hand off to downstream owners so failures are not bounced without context.

## Operating Great Expectations at scale

After the first successful deploy of data quality gates with great expectations, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Great Expectations settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Data Pipelines pipelines touch ingestion, serving, and finance. Document interfaces where Great Expectations gates hand off to downstream owners so failures are not bounced without context.

## Operating Great Expectations at scale

After the first successful deploy of data quality gates with great expectations, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Great Expectations settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Data Pipelines pipelines touch ingestion, serving, and finance. Document interfaces where Great Expectations gates hand off to downstream owners so failures are not bounced without context.

## Operating Great Expectations at scale

After the first successful deploy of data quality gates with great expectations, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Great Expectations settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Data Pipelines pipelines touch ingestion, serving, and finance. Document interfaces where Great Expectations gates hand off to downstream owners so failures are not bounced without context.

## Operating Great Expectations at scale

After the first successful deploy of data quality gates with great expectations, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Great Expectations settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Data Pipelines pipelines touch ingestion, serving, and finance. Document interfaces where Great Expectations gates hand off to downstream owners so failures are not bounced without context.

## Operating Great Expectations at scale

After the first successful deploy of data quality gates with great expectations, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Great Expectations settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Data Pipelines pipelines touch ingestion, serving, and finance. Document interfaces where Great Expectations gates hand off to downstream owners so failures are not bounced without context.

## Operating Great Expectations at scale

After the first successful deploy of data quality gates with great expectations, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Great Expectations settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Data Pipelines pipelines touch ingestion, serving, and finance. Document interfaces where Great Expectations gates hand off to downstream owners so failures are not bounced without context.

## Operating Great Expectations at scale

After the first successful deploy of data quality gates with great expectations, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Great Expectations settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Data Pipelines pipelines touch ingestion, serving, and finance. Document interfaces where Great Expectations gates hand off to downstream owners so failures are not bounced without context.

## Operating Great Expectations at scale

After the first successful deploy of data quality gates with great expectations, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Great Expectations settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Data Pipelines pipelines touch ingestion, serving, and finance. Document interfaces where Great Expectations gates hand off to downstream owners so failures are not bounced without context.

## Operating Great Expectations at scale

After the first successful deploy of data quality gates with great expectations, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Great Expectations settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Data Pipelines pipelines touch ingestion, serving, and finance. Document interfaces where Great Expectations gates hand off to downstream owners so failures are not bounced without context.

## Further reading

- https://greatexpectations.io/
- https://docs.dagster.io/
- https://openlineage.io/
