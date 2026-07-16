---
title: "Incremental Models in dbt"
slug: "data-incremental-models-dbt"
description: "Incremental dbt models cut warehouse cost and runtime by processing only new rows. Strategies, merge keys, late-arriving data, and when full-refresh still wins."
datePublished: "2025-07-14"
dateModified: "2025-07-14"
tags: ["Data Engineering", "Analytics"]
keywords: "dbt incremental model, merge strategy, delete insert, warehouse cost, late arriving data, dbt best practices"
faq:
  - q: "When should I use a dbt incremental model?"
    a: "Use incremental models when the table is large, append-heavy, and full refreshes exceed your job window or budget. Event logs, fact tables, and daily snapshots with stable keys are strong candidates. Skip incrementals for small dimensions, heavily mutating datasets needing full recompute, or tables where correctness requires scanning all history every run."
  - q: "What is the difference between merge and delete+insert in dbt?"
    a: "Merge upserts rows by a unique key — new rows insert, matching keys update. Delete+insert removes rows matching a predicate (often a date partition) then inserts fresh data for that range. Merge handles row-level changes; delete+insert suits partition-overwrite patterns on warehouses like BigQuery and Snowflake."
  - q: "How do I handle late-arriving data in incremental models?"
    a: "Widen the incremental lookback window — process the last N days each run instead of only since max(timestamp). Use merge on a natural key so corrected rows upsert. Document the lookback in model config and monitor duplicate or stale counts if the window is too narrow."
---

Running `dbt run` on a ten-billion-row events table as a table materialization works exactly once — the second run, someone asks why the job costs four hundred dollars and still misses the SLA. Incremental models are how you keep large fact tables fresh without re-reading history every night.

## How dbt incrementals work

An incremental model tells dbt: on first run build the full table; on subsequent runs run a different SQL branch that touches only new or changed data.

```sql
{{ config(
    materialized='incremental',
    unique_key='event_id',
    incremental_strategy='merge'
) }}

SELECT
    event_id,
    user_id,
    event_type,
    occurred_at,
    properties
FROM {{ source('raw', 'events') }}

{% if is_incremental() %}
  WHERE occurred_at > (SELECT max(occurred_at) FROM {{ this }})
{% endif %}
```

`is_incremental()` is false on `--full-refresh`; true otherwise. The filter defines your incremental window.

## Choosing a strategy

dbt supports warehouse-specific strategies via `incremental_strategy`:

| Strategy | Behavior | Good for |
|---|---|---|
| `merge` | Upsert on `unique_key` | Mutable rows, CDC streams |
| `delete+insert` | Delete matching predicate, insert batch | Partitioned facts |
| `append` | Insert only, no updates | Immutable logs |
| `insert_overwrite` | Replace partitions (BigQuery) | Daily partition tables |

Snowflake and BigQuery merge semantics differ — test idempotency. A duplicate run should land the same row counts, not double inserts.

```sql
{{ config(
    materialized='incremental',
    unique_key='order_id',
    incremental_strategy='delete+insert',
    partition_by={'field': 'order_date', 'data_type': 'date'}
) }}

{% if is_incremental() %}
  WHERE order_date >= dateadd('day', -3, current_date())
{% endif %}
```

The three-day lookback catches late-arriving orders without full refresh.

## Unique keys matter

`unique_key` drives merge behavior. Pick a key that's actually unique in the source — composite keys when needed:

```yaml
# dbt_project.yml
models:
  analytics:
    fct_orders:
      +unique_key: ['order_id', 'line_item_id']
```

Missing or wrong keys produce silent duplicates or lost updates. Add a dbt test:

```yaml
# schema.yml
models:
  - name: fct_orders
    tests:
      - dbt_utils.unique_combination_of_columns:
          combination_of_columns: [order_id, line_item_id]
```

## Late-arriving and correcting data

Pure `max(timestamp)` incrementals miss rows that backfill into older partitions. Patterns:

1. **Lookback window** — reprocess last N days every run
2. **Merge on business key** — same `order_id` gets updated in place
3. **Micro-batch streaming** — shorter intervals shrink the correction window

Document the lookback in model description so the next engineer doesn't "optimize" it to zero and break finance reports.

## When to full-refresh anyway

Schedule periodic `--full-refresh` on incrementals with complex logic — monthly or after logic changes. Incremental drift accumulates from bug fixes, changed joins, and source backfills you didn't anticipate.

Also full-refresh when:

- Logic change alters historical rows (currency correction)
- `unique_key` definition changes
- Source deduplication rules change

Automate a canary: compare row counts and checksums between incremental and a sampled full rebuild.

## Cost and performance tuning

- Cluster or partition on the incremental filter column
- Push filters to the source scan — don't pull ten days into a CTE then filter
- Use `incremental_predicates` (dbt 1.6+) for merge optimization on supported warehouses
- Monitor bytes scanned per run in warehouse query history

```sql
{{ config(
    incremental_predicates = [
      "DBT_INTERNAL_DEST.occurred_at >= dateadd('day', -7, current_date())"
    ]
) }}
```

Predicates limit merge scan scope on large destinations.

## Testing incrementals locally

```bash
dbt run --select fct_events --full-refresh
dbt run --select fct_events  # incremental pass
dbt run --select fct_events  # idempotency check
```

Seed a small raw slice with overlapping timestamps to verify lookback and merge. Unit test the SQL diff between incremental and full paths if logic is non-trivial.

## Incremental strategy selection by warehouse

| Strategy | Warehouse | Behavior |
|---|---|---|
| `merge` | Snowflake, BigQuery, Databricks | UPSERT on unique key |
| `delete+insert` | Postgres, Redshift | Delete matching keys, insert new |
| `append` | Any | Insert only; duplicates possible |
| `insert_overwrite` | BigQuery | Replace partitions |

```sql
{{ config(
    materialized='incremental',
    unique_key='event_id',
    incremental_strategy='merge',
    on_schema_change='append_new_columns',
) }}
```

Use `merge` when you need idempotent upserts. Use `append` only for immutable event logs where duplicates are impossible. `delete+insert` simpler but slower on large tables.

## Handling late-arriving data

Events arrive after the incremental window closes:

```sql
{% if is_incremental() %}
    WHERE updated_at >= (
        SELECT COALESCE(MAX(updated_at), '1970-01-01')
        FROM {{ this }}
    ) - INTERVAL '3 days'  -- lookback window
{% endif %}
```

3-day lookback catches late arrivals without full refresh. Tune lookback to your SLA — longer lookback = more bytes scanned per run. Document lookback in model description.

## Microbatch vs streaming incrementals

For near-real-time pipelines, run incrementals frequently with small batches:

```yaml
# dbt Cloud job: every 15 minutes
schedule: "*/15 * * * *"
select: "tag:streaming"
```

Pair with warehouse auto-suspend disabled during business hours. 15-minute microbatch incrementals cost less than streaming infrastructure for most analytics use cases.

## Failure modes

- **No lookback window** — late-arriving data missed permanently
- **Schema change without on_schema_change** — incremental run fails on new column
- **Append strategy with duplicates** — row count grows unbounded; use merge
- **Full refresh forgotten after logic change** — stale data persists in destination
- **Incremental filter on wrong column** — updated_at vs created_at confusion

## Production checklist

- Incremental strategy matches warehouse capabilities
- Lookback window documented and tested with late-arriving data
- `on_schema_change='append_new_columns'` configured
- Canary comparison: incremental vs full refresh row counts monthly
- Idempotency verified: running incremental twice produces same result
- Full refresh procedure documented for logic changes

## Common production mistakes

Teams get incremental models dbt wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Data pipelines for incremental models dbt silently corrupt when schema evolution is backward-incompatible, late-arriving events are dropped, and warehouse costs spike because nobody partitions by query pattern.

## Resources

- [dbt docs — Incremental models](https://docs.getdbt.com/docs/build/incremental-models)
- [dbt docs — incremental_strategy](https://docs.getdbt.com/reference/resource-configs/snowflake-configs#incremental-strategies)
- [dbt docs — Model contracts and constraints](https://docs.getdbt.com/docs/collaborate/govern/model-contracts)
- [Snowflake — Merge statement performance](https://docs.snowflake.com/en/sql-reference/sql/merge)
- [dbt-utils package — unique_combination_of_columns](https://github.com/dbt-labs/dbt-utils)
