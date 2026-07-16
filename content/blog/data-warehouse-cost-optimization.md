---
title: "Warehouse Cost Optimization"
slug: "data-warehouse-cost-optimization"
description: "Snowflake and BigQuery bills grow quietly. Query tuning, clustering, materialized views, workload isolation, and governance that actually cuts spend."
datePublished: "2025-08-16"
dateModified: "2025-08-16"
tags: ["Data Engineering", "Analytics"]
keywords: "warehouse cost optimization, Snowflake cost, BigQuery cost, query tuning, data warehouse spend"
faq:
  - q: "What causes data warehouse costs to spike unexpectedly?"
    a: "Full table scans from missing partition filters, runaway BI dashboards refreshing large explores, duplicate dbt runs, oversized virtual warehouses, cross-region egress, and storage of unbounded raw history. Costs compound when many teams share one warehouse without query attribution or budgets."
  - q: "How do I find expensive queries in Snowflake?"
    a: "Use ACCOUNT_USAGE.QUERY_HISTORY filtered by bytes_scanned and execution_time. Warehouse metering views show credit consumption by warehouse. Tag queries with dbt query comments or session tags to map spend to teams and jobs."
  - q: "What are the highest-impact cost optimizations?"
    a: "Enforce partition filters on large tables, convert wide full-refresh models to incremental dbt, right-size warehouses with auto-suspend, cache or materialize hot aggregations, expire stale tables, and block ad-hoc SELECT * on terabyte tables via governance."
---

Nobody gets promoted for saving warehouse dollars until finance asks why analytics spend doubled quarter-over-quarter. Cost optimization isn't heroics — it's making expensive operations visible, then removing the ones nobody needed.

## Know where credits go

Instrument before tuning:

```sql
-- Snowflake: top queries last 7 days by bytes scanned
SELECT
  query_text,
  user_name,
  warehouse_name,
  bytes_scanned,
  total_elapsed_time / 1000 AS seconds
FROM snowflake.account_usage.query_history
WHERE start_time >= dateadd('day', -7, current_timestamp())
ORDER BY bytes_scanned DESC
LIMIT 20;
```

BigQuery equivalent: `INFORMATION_SCHEMA.JOBS_BY_PROJECT` with `total_bytes_processed`.

Tag sessions — dbt adds query comments; set `QUERY_TAG` in Snowflake for Airflow/Dagster jobs. Unattributed spend becomes political; attributed spend becomes fixable.

## Query patterns that burn money

**SELECT * on wide fact tables.** Analyst habit; block with row access policies or views exposing needed columns only.

**Missing partition predicates.** One line in WHERE saves terabytes:

```sql
-- Bad: full scan
SELECT count(*) FROM events WHERE event_type = 'purchase';

-- Good: partition prune
SELECT count(*) FROM events
WHERE event_date = '2025-07-15' AND event_type = 'purchase';
```

Use `require_partition_filter = true` in BigQuery; document required filters in catalog.

**Cartesian joins from missing keys.** dbt tests on relationships catch many; not all.

**Repeated identical aggregations.** Same daily revenue rollup computed by five dashboards — materialize once.

## Incremental models and clustering

Full-refresh dbt models on billion-row tables nightly is a budget fire. Incremental merge with lookback (see incremental models guide) cuts scan volume 90%+ when source is append-heavy.

**Clustering / sorting** aligns micro-partitions with filter columns — `CLUSTER BY (event_date, product_id)` in BigQuery, clustering keys in Snowflake. Recluster when partition depth metrics degrade.

## Materialized views and aggregates

Precompute hot paths:

```sql
CREATE MATERIALIZED VIEW daily_revenue AS
SELECT
  order_date,
  sum(net_revenue) AS revenue,
  count(*) AS orders
FROM fct_orders
GROUP BY order_date;
```

Refresh policies balance freshness vs cost. BI tools point at MVs; ad-hoc explores on raw facts get rate-limited.

## Warehouse sizing and isolation

Oversized virtual warehouses idle expensive. Right-size with auto-suspend (60–300 seconds) and auto-resume. Separate warehouses:

| Warehouse | Workload |
|---|---|
| `wh_etl` | dbt, batch — larger, off-peak |
| `wh_bi` | Dashboards — medium, business hours |
| `wh_adhoc` | Analyst exploration — small + query timeout |

Prevent ETL and BI competing on one 4XL warehouse.

## Storage costs matter too

Time-travel and fail-safe retention in Snowflake, undeleted BigQuery snapshots, raw JSON hoarding — storage is cheaper than compute but not free. Policies:

- Drop staging tables after N days
- Iceberg/Delta snapshot expiration
- Compress or archive cold partitions to Glacier tier

## Governance without bureaucracy

- Query timeouts on ad-hoc warehouses (5–15 min)
- Max bytes billed per user/day alerts
- Approved views for self-serve instead of raw table access
- Office hours for expensive new models before production schedule

Cost caps work when paired with alternatives — not "no" but "here's the materialized path."

## Measure savings

Track monthly: bytes scanned per domain, cost per dbt model (via query tags + model name), BI dashboard refresh cost. Revisit after major product launches — new events tables reset baselines.

## Snowflake-specific optimizations

**Warehouse auto-scaling:** Multi-cluster warehouses for BI workloads with unpredictable concurrency — scale from 1 to 3 clusters during business hours, single cluster off-peak.

**Resource monitors:** Hard caps prevent runaway spend:

```sql
CREATE RESOURCE MONITOR monthly_budget
  WITH CREDIT_QUOTA = 5000
  TRIGGERS
    ON 75 PERCENT DO NOTIFY
    ON 100 PERCENT DO SUSPEND;
```

**Result caching:** Identical queries within 24 hours return cached results at zero compute cost. Structure dashboards to hit cache — stable date filters, not `CURRENT_TIMESTAMP()` in WHERE.

**Zero-copy cloning:** Test dbt models against production-scale data without doubling storage:

```sql
CREATE DATABASE dev_analyst CLONE prod_analytics;
-- No storage cost until dev modifies data
```

## BigQuery-specific optimizations

**Partition and cluster every large table:**

```sql
CREATE TABLE events
PARTITION BY DATE(event_timestamp)
CLUSTER BY user_id, event_type
AS SELECT * FROM raw_events;
```

**BI Engine reservation** for sub-second dashboard queries on hot tables — in-memory acceleration for Looker/Tableau.

**Flex slots** for batch workloads — 60% cheaper than on-demand for dbt runs scheduled off-peak.

**Column-level security** instead of duplicating masked tables — reduces storage duplication.

## dbt cost attribution

Tag every dbt run for cost tracking:

```yaml
# profiles.yml
prod:
  query_tag: "dbt_{{ target.name }}_{{ invocation_id }}"
```

Then attribute warehouse spend:

```sql
SELECT
  regexp_substr(query_tag, 'dbt_prod_(.+)', 1, 1, 'e') AS dbt_run,
  sum(credits_used) AS credits
FROM snowflake.account_usage.warehouse_metering_history
GROUP BY 1
ORDER BY 2 DESC;
```

Identify the 10 most expensive dbt models and prioritize incremental conversion.

## Failure modes

- **No query attribution** — can't identify which team/job drives spend
- **Full-refresh nightly on billion-row tables** — largest single cost driver in most warehouses
- **One oversized warehouse for everything** — ETL and BI compete, both over-provisioned
- **Unbounded raw storage** — years of raw JSON nobody queries
- **BI dashboards on raw facts** — repeated full scans; no materialization layer
- **Missing partition filters** — single query scans terabytes

## Production checklist

- Query attribution via tags on all automated jobs
- Top 20 expensive queries reviewed monthly
- Large tables partitioned and clustered
- dbt staging as views, marts as incremental where possible
- Separate warehouses for ETL, BI, and ad-hoc
- Resource monitors with alerts at 75% budget
- Stale tables and unused models archived quarterly

## Common production mistakes

Teams get warehouse cost optimization wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Data pipelines for warehouse cost optimization silently corrupt when schema evolution is backward-incompatible, late-arriving events are dropped, and warehouse costs spike because nobody partitions by query pattern.

## Resources

- [Snowflake — Understanding compute cost](https://docs.snowflake.com/en/user-guide/cost-understanding-compute)
- [BigQuery — Optimizing query performance](https://cloud.google.com/bigquery/docs/best-practices-performance-overview)
- [dbt — Incremental models](https://docs.getdbt.com/docs/build/incremental-models)
- [Select.dev — Snowflake cost management](https://select.dev/posts/snowflake-cost-optimization)
- [Snowflake query profile documentation](https://docs.snowflake.com/en/user-guide/ui-query-profile)
