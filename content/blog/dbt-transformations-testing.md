---
title: "Data Transformations with dbt"
slug: "dbt-transformations-testing"
description: "dbt brings software engineering to warehouse transforms — models, refs, tests, and docs. Project structure, materializations, and CI patterns that scale."
datePublished: "2025-09-21"
dateModified: "2025-09-21"
tags: ["Data Engineering", "Analytics"]
keywords: "dbt transformations, dbt testing, dbt models, analytics engineering, dbt project structure, data build tool"
faq:
  - q: "What does dbt do?"
    a: "dbt (data build tool) compiles SQL transformations into a directed acyclic graph, runs them against your warehouse in dependency order, and provides testing, documentation, and lineage. You write SELECT statements; dbt handles CREATE TABLE/VIEW and orchestrates builds."
  - q: "How do dbt tests differ from custom SQL checks?"
    a: "dbt tests are declarative YAML attached to models — unique, not_null, relationships, accepted_values — executed automatically on dbt run or test. Failed tests block deploys in CI. Custom generic tests and singular SQL tests extend coverage for domain rules."
  - q: "What materialization should I use for dbt models?"
    a: "Views for lightweight staging layers; tables for heavily queried marts; incremental for large append-heavy facts; ephemeral for intermediate CTEs inlined into downstream models. Default staging to view, marts to table or incremental based on size and refresh SLA."
---

Before dbt, our "transformation layer" was a folder of numbered SQL files and a wiki page explaining run order. dbt didn't invent warehouse SQL — it made transforms **versioned, tested, and dependency-aware** the way application code already was.

## Core primitives

**Models** — one `.sql` file, one relation:

```sql
-- models/marts/fct_orders.sql
{{ config(materialized='table') }}

SELECT
    o.order_id,
    o.customer_id,
    o.order_date,
    sum(li.quantity * li.unit_price) AS gross_amount
FROM {{ ref('stg_orders') }} o
JOIN {{ ref('stg_order_lines') }} li USING (order_id)
GROUP BY 1, 2, 3
```

**ref()** — dependency edge; dbt builds DAG automatically.

**sources** — declare raw tables:

```yaml
sources:
  - name: raw
    tables:
      - name: orders
```

**tests** — data quality gates in schema YAML.

## Project layering

Standard layout:

```
models/
  staging/     # 1:1 with sources, rename, cast, light clean
  intermediate/ # business logic blocks, reusable
  marts/       # consumer-facing facts and dims
```

Staging stays views; marts materialize tables. Intermediate as ephemeral or views unless reused heavily.

Naming: `stg_<source>__<entity>`, `int_<description>`, `fct_` / `dim_` prefixes.

## Testing strategy

```yaml
models:
  - name: fct_orders
    columns:
      - name: order_id
        tests: [unique, not_null]
      - name: customer_id
        tests:
          - not_null
          - relationships:
              to: ref('dim_customers')
              field: customer_id
      - name: status
        tests:
          - accepted_values:
              values: ['pending', 'paid', 'shipped', 'cancelled']
```

Singular test for domain rules:

```sql
-- tests/assert_revenue_matches_lines.sql
SELECT order_id
FROM {{ ref('fct_orders') }} o
JOIN (
  SELECT order_id, sum(amount) AS line_total
  FROM {{ ref('int_order_lines_enriched') }}
  GROUP BY 1
) li USING (order_id)
WHERE abs(o.gross_amount - li.line_total) > 0.01
```

Run in CI on every PR against staging warehouse slice.

## Macros and DRY

```sql
{% macro cents_to_dollars(column) %}
  ({{ column }} / 100.0)::numeric(18,2)
{% endmacro %}
```

Package hub: `dbt_utils`, `dbt_expectations`, `codegen`. Don't macro-spaghetti business logic — intermediate models often read clearer.

## Documentation and lineage

```yaml
models:
  - name: fct_orders
    description: "Order grain fact. One row per order_id."
    columns:
      - name: gross_amount
        description: "Sum of line items before tax, USD."
```

`dbt docs generate` produces searchable site with lineage graph — feeds catalog integration.

## CI/CD pipeline

```yaml
# GitHub Actions sketch
- run: dbt deps
- run: dbt seed --target ci
- run: dbt build --select state:modified+ --defer --target ci
- run: dbt test --select state:modified+
```

Slim CI runs only modified subgraph. `--defer` to prod upstream refs without rebuilding entire warehouse.

Enforce model contracts and query tags for cost attribution.

## Environments and targets

`profiles.yml` targets: dev (personal schema), staging, prod. Developers run against dev schemas; prod deploys via merge to main + orchestrated `dbt build`.

Never share prod credentials locally without read-only sandbox.

## Common failure modes

Circular refs — dbt catches at compile. Over-materializing everything as table — warehouse cost explosion. Missing tests on grain keys — silent duplication in joins. Giant monolithic models — split intermediate steps for debuggability.

dbt succeeds when analytics engineers own the project like app repos: PR review, tests required, docs not optional.

## Incremental models for large facts

Full table rebuilds on billion-row facts don't scale. Incremental materialization processes only new/changed rows:

```sql
-- models/marts/fct_events.sql
{{ config(
    materialized='incremental',
    unique_key='event_id',
    on_schema_change='append_new_columns',
) }}

SELECT *
FROM {{ ref('stg_events') }}
{% if is_incremental() %}
WHERE event_timestamp > (SELECT max(event_timestamp) FROM {{ this }})
{% endif %}
```

Key decisions:
- **unique_key** — deduplication on merge (Snowflake MERGE, BigQuery MERGE)
- **Incremental strategy** — `append` vs `merge` vs `delete+insert` depending on late-arriving data
- **is_incremental()** — full refresh on first run, incremental on subsequent

For late-arriving events (mobile offline sync), use a lookback window:

```sql
{% if is_incremental() %}
WHERE event_timestamp > (SELECT max(event_timestamp) - interval '3 days' FROM {{ this }})
{% endif %}
```

## Snapshots for slowly changing dimensions

Track historical changes to dimension attributes:

```yaml
# snapshots/customers_snapshot.sql
{% snapshot customers_snapshot %}
{{
    config(
      target_schema='snapshots',
      unique_key='customer_id',
      strategy='timestamp',
      updated_at='updated_at',
    )
}}
SELECT * FROM {{ source('raw', 'customers') }}
{% endsnapshot %}
```

Type 2 SCD history without hand-written effective date logic. Query `dbt_valid_from` / `dbt_valid_to` for point-in-time joins.

## dbt packages and the package hub

Don't reinvent common patterns:

```yaml
# packages.yml
packages:
  - package: dbt-labs/dbt_utils
    version: 1.1.1
  - package: calogica/dbt_expectations
    version: 0.10.1
  - package: dbt-labs/codegen
    version: 0.12.0
```

`dbt_utils.pivot`, `dbt_utils.date_spine`, `dbt_expectations.expect_column_values_to_be_between` — standardize across projects. Run `dbt deps` in CI before build.

## Environment management and defer

Developers shouldn't rebuild the entire warehouse locally:

```bash
# Build only your model and downstream, defer upstream to prod
dbt run --select my_new_model+ --defer --target dev

# CI: build only modified models
dbt build --select state:modified+ --defer --target ci
```

`--defer` references production tables for upstream dependencies — dev schema only materializes your changes. Requires `manifest.json` from prod stored in S3/artifact store.

## Failure modes

- **Circular ref** — dbt catches at compile; fix dependency direction
- **Everything materialized as table** — warehouse cost explosion; default staging to views
- **No tests on grain keys** — duplicate rows in joins silently inflate metrics
- **Monolithic 500-line models** — split into intermediate steps for debuggability
- **Skipping docs** — lineage graph incomplete; analysts can't self-serve
- **Running dbt run without dbt test in CI** — broken models reach production

## Production checklist

- Project layered: staging (views) → intermediate → marts (tables/incremental)
- Grain key tests (unique, not_null) on every mart
- Relationship tests between facts and dimensions
- CI runs `dbt build --select state:modified+` on every PR
- `--defer` configured for dev and CI targets
- Documentation generated and published on merge to main
- Incremental models have lookback window for late-arriving data

Schedule `dbt source freshness` checks on raw sources — stale ingestion should block downstream marts before analysts discover stale dashboards.

Run dbt tests on production snapshots weekly, not just CI fixtures — schema drift in source systems breaks assumptions tests never caught.

## Resources

- [dbt documentation](https://docs.getdbt.com/)
- [dbt best practices — project structure](https://docs.getdbt.com/best-practices/how-we-structure/1-guide-overview)
- [dbt test documentation](https://docs.getdbt.com/docs/build/data-tests)
- [dbt Labs — dbt_utils package](https://github.com/dbt-labs/dbt-utils)
- [Analytics Engineering with dbt (O'Reilly)](https://www.oreilly.com/library/view/analytics-engineering-with/9781098153294/)
