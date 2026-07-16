---
title: "Slowly Changing Dimensions"
slug: "data-modeling-slowly-changing-dimensions"
description: "SCD Type 1, 2, and 3 patterns for tracking dimension history. When to overwrite, version rows, or store prior values — with SQL examples."
datePublished: "2025-07-26"
dateModified: "2025-07-26"
tags: ["Data Engineering", "Analytics"]
keywords: "slowly changing dimensions, SCD Type 2, dimension modeling, Kimball, effective dates, data warehouse"
faq:
  - q: "What is a Slowly Changing Dimension?"
    a: "An SCD is a dimension table whose attributes change over time for the same natural key — a customer moves cities, a product gets renamed. The modeling question is whether to overwrite history, preserve every version, or keep limited prior values."
  - q: "When should I use SCD Type 2?"
    a: "Use Type 2 when historical accuracy matters for reporting — you need to know what region a customer belonged to at the time of each past order. Each change inserts a new row with effective dates and often a surrogate key; facts join to the version active on the transaction date."
  - q: "What is the difference between SCD Type 1 and Type 2?"
    a: "Type 1 overwrites the attribute in place, losing prior values. Type 2 preserves history by closing the current row and inserting a new version. Type 1 suits corrections and attributes where history doesn't matter; Type 2 suits attributes that affect historical analysis."
---

A customer changed their billing address in March. Your Q1 revenue by region report still attributes their January orders to the old state — or it doesn't, depending on choices nobody documented because the dimension table "just updates nightly." Slowly Changing Dimension patterns exist to make that choice explicit instead of accidental.

## The three types you'll actually use

Kimball defined more variants; production warehouses live in Types 1–3.

### Type 1 — overwrite

```sql
UPDATE dim_customer
SET city = 'Austin', updated_at = current_timestamp()
WHERE customer_id = 42;
```

Simple, no history. Use for typo fixes, attributes that never affect historical reports (`email_format_preference`), or when source systems don't version and you accept ambiguity.

### Type 2 — add new row

```sql
-- Close current version
UPDATE dim_customer
SET effective_to = '2025-07-25', is_current = false
WHERE customer_id = 42 AND is_current = true;

-- Insert new version
INSERT INTO dim_customer (
  customer_sk, customer_id, city, effective_from, effective_to, is_current
) VALUES (
  9001, 42, 'Austin', '2025-07-26', '9999-12-31', true
);
```

Facts store `customer_sk` (surrogate key) at transaction time, or join on `customer_id` + transaction date between `effective_from` and `effective_to`:

```sql
SELECT o.order_id, d.city
FROM fct_orders o
JOIN dim_customer d
  ON o.customer_id = d.customer_id
 AND o.order_date >= d.effective_from
 AND o.order_date < d.effective_to;
```

Type 2 is the default for geo, segment, pricing tier — anything that changes business meaning retroactively if overwritten.

### Type 3 — prior value column

Keep `current_city` and `previous_city`. Limited history (one hop). Rare in modern warehouses — Type 2 with partitioning is usually cleaner — but useful when legal requires "show me what we knew at filing time" without full versioning infrastructure.

## Surrogate keys and grain

Type 2 dimensions need a **surrogate key** (`customer_sk`) distinct from the **natural key** (`customer_id`). Facts should reference surrogate keys when history must be frozen at load time; natural-key date-range joins work for late-binding analytics but cost more at query time.

Document grain in dbt schema YAML: "one row per customer per attribute change."

## Implementing in dbt

dbt snapshots automate Type 2:

```sql
{% snapshot customer_snapshot %}

{{
    config(
      target_schema='snapshots',
      unique_key='customer_id',
      strategy='timestamp',
      updated_at='updated_at',
    )
}}

SELECT * FROM {{ source('crm', 'customers') }}

{% endsnapshot %}
```

dbt generates `dbt_valid_from`, `dbt_valid_to`, `dbt_scd_id`. Merge snapshots into `dim_customer` with effective date columns matching your warehouse conventions.

For merge-based CDC sources, `strategy='check'` compares hash of tracked columns.

## Handling deletes and late corrections

Source deletes: soft-delete flag on dimension vs hard remove (usually soft with `is_active`). Corrections to past effective dates are painful — often require Type 2 adjustment rows and fact reprocessing. Prevent upstream overwrites without audit trails.

**Late-arriving dimension changes** — customer moved in January but CRM updated in March — need backdated `effective_from` and possibly fact restatement. Finance teams care deeply; agree on policy upfront.

## Performance considerations

Type 2 tables grow with every attribute twitch. Mitigations:

- Track only **slowly** changing columns in snapshot; ignore `last_login`
- Partition by `is_current` or `effective_from`
- Cluster on natural key for join performance
- Periodic compaction of identical consecutive versions if source sends noise

## Choosing a type per column

Hybrid dimensions mix strategies — Type 1 for `email`, Type 2 for `country`. Implement as separate satellite tables (Data Vault style) or multiple snapshot configs keyed to the same entity. Don't Type-2 columns that change hourly unless you mean it.

| Attribute | Typical type | Reason |
|---|---|---|
| Customer segment | Type 2 | Historical cohort analysis |
| Phone number typo fix | Type 1 | No analytical history needed |
| Product category reorg | Type 2 | Restated sales by category |
| Current account manager | Type 1 or 2 | Depends if past commission reports matter |

## Fact table joins and temporal correctness

SCD joins are where analytics break silently:

```sql
-- WRONG: joins current dimension state to historical facts
SELECT f.order_date, d.customer_segment, SUM(f.amount)
FROM fact_orders f
JOIN dim_customer d ON f.customer_id = d.customer_id;

-- RIGHT: join on effective date range
SELECT f.order_date, d.customer_segment, SUM(f.amount)
FROM fact_orders f
JOIN dim_customer d
  ON f.customer_id = d.customer_id
 AND f.order_date >= d.effective_from
 AND f.order_date < COALESCE(d.effective_to, '9999-12-31');
```

Every analyst on your team needs this pattern documented. BI tools with "automatic joins" hide the bug until finance restates a quarter.

## Testing SCD logic

Automated tests for dimension pipelines:

1. **Insert new customer** — one Type 2 row, `is_current=true`
2. **Update segment** — prior row closed, new row opened, dates contiguous
3. **No-op update** — identical hash produces no new row (dbt snapshot behavior)
4. **Backdated change** — effective_from before existing row; verify overlap handling
5. **Delete in source** — soft-delete flag or row removal per policy

Store fixture CSVs in git and run in CI on every dbt model change.

## Warehouse-specific patterns

**BigQuery:** Use `GENERATE_ARRAY` + `UNNEST` for date spine joins against Type 2 ranges, or materialize a daily snapshot table for heavy dashboards.

**Snowflake:** Streams + tasks for incremental snapshot merges; cluster on `(natural_key, effective_from)`.

**Postgres:** Partial index on `WHERE is_current = true` for OLTP-style lookups; btree on `(id, effective_from DESC)` for temporal joins.

Document your `effective_to` sentinel convention — NULL vs `9999-12-31` vs open-ended — and enforce it in schema tests.

## Production checklist

- [ ] Temporal join pattern documented for all analysts
- [ ] dbt snapshot tests for Type 2 continuity (no date gaps)
- [ ] Hybrid Type 1/2 columns explicitly tagged in data catalog
- [ ] Backdated corrections trigger fact restatement workflow
- [ ] `is_current` partial index on large dimension tables

## Resources

- [Kimball Group — Slowly Changing Dimensions](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-2/)
- [dbt snapshots documentation](https://docs.getdbt.com/docs/build/snapshots)
- [Snowflake — Dimension modeling guide](https://docs.snowflake.com/en/user-guide/data-load-considerations-dimension)
- [The Data Warehouse Toolkit (Kimball & Ross)](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/books/data-warehouse-dw-toolkit/)
- [Star schema modeling companion patterns](https://docs.getdbt.com/terms/dimension)
