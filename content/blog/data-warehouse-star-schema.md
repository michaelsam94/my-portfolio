---
title: "Star Schema Modeling"
slug: "data-warehouse-star-schema"
description: "Star schemas center fact tables surrounded by dimension tables. Grain, degenerate dimensions, conformed dimensions, and Kimball patterns that still work in modern warehouses."
datePublished: "2025-08-19"
dateModified: "2025-08-19"
tags: ["Data Engineering", "Analytics"]
keywords: "star schema, dimensional modeling, fact table, dimension table, Kimball, data warehouse design"
faq:
  - q: "What is a star schema?"
    a: "A star schema is a dimensional model with a central fact table containing measurable events or transactions connected directly to dimension tables describing who, what, where, and when. The diagram resembles a star — facts in the center, dimensions as points. Join paths are simple compared to snowflake normalization."
  - q: "What is fact table grain?"
    a: "Grain is the definition of one row in a fact table — one line item per order, one page view per session, one daily snapshot per account. Every measure must be additive or semi-additive at that grain. Ambiguous grain produces double-counted metrics."
  - q: "When should I use snowflake instead of star schema?"
    a: "Snowflake schema normalizes dimensions into sub-dimensions (product → category → department). It saves storage and enforces hierarchy consistency but adds joins. Most cloud warehouses prefer denormalized wide dimensions for query simplicity unless dimensions are huge or shared hierarchies require normalization."
---

Star schema isn't legacy — it's the reason your CFO's revenue number matches finance's spreadsheet when both query from `fct_orders` at the same grain. Dimensional modeling survived Hadoop, survived the lakehouse, because **grain discipline** beats clever normalization for analytics workloads.

## Facts and dimensions

**Fact table** — numeric measures + foreign keys to dimensions:

```sql
CREATE TABLE fct_orders (
  order_id          BIGINT,      -- degenerate dimension
  order_date_key    INT,         -- FK to dim_date
  customer_key      INT,         -- FK to dim_customer
  product_key       INT,         -- FK to dim_product
  quantity          INT,
  gross_amount      DECIMAL(18,2),
  discount_amount   DECIMAL(18,2),
  net_amount        DECIMAL(18,2)
);
```

**Dimension tables** — descriptive context:

```sql
CREATE TABLE dim_customer (
  customer_key      INT PRIMARY KEY,
  customer_id       VARCHAR,
  name              VARCHAR,
  segment           VARCHAR,
  country           VARCHAR
);
```

Analysts filter and group on dimensions; facts supply numbers.

## Declare grain explicitly

Before writing SQL, finish this sentence: **"One row represents ___."**

| Fact | Grain |
|---|---|
| `fct_order_lines` | One product line on one order |
| `fct_orders` | One order header (risky if lines differ) |
| `fct_daily_inventory` | One product-warehouse-day snapshot |

Mixing grains in one fact table creates double-counting when summing measures. Split facts instead of bolting line and header measures together.

Document grain in dbt:

```yaml
models:
  - name: fct_order_lines
    description: "One row per order line item. Do not sum with header-level facts."
```

## Additive, semi-additive, non-additive

- **Additive** — sum across all dimensions (`quantity`, `revenue`)
- **Semi-additive** — sum across some dims, not time (`account_balance`)
- **Non-additive** — ratios (`margin_pct`) — compute from summed components, not average of ratios

```sql
-- Wrong: average of daily margins
SELECT avg(margin_pct) FROM fct_daily_store;

-- Right: ratio of sums
SELECT sum(profit) / sum(revenue) FROM fct_daily_store;
```

## Conformed dimensions

`dim_date` and `dim_customer` shared across fact tables enable consistent drill-across:

```
fct_sales ──▶ dim_customer ◀── fct_support_tickets
         └──▶ dim_date      ◀──┘
```

Without conformed dimensions, "customers" means different things in sales vs support reports.

## Role-playing dimensions

Same physical `dim_date` joins multiple roles via views or aliases:

```sql
SELECT *
FROM fct_orders o
JOIN dim_date d_order ON o.order_date_key = d_order.date_key
JOIN dim_date d_ship ON o.ship_date_key = d_ship.date_key;
```

Or create views `dim_order_date`, `dim_ship_date` pointing at `dim_date`.

## Degenerate dimensions

Natural keys stored in fact without separate dimension — `order_id`, `invoice_number`. No attribute table needed; still useful for drill-through.

## Star vs snowflake vs wide tables

| Approach | Tradeoff |
|---|---|
| Star | Simple joins, wider dimensions |
| Snowflake | Normalized dims, more joins |
| Single wide table | Fast scans, duplication, brittle schema |

Cloud columnar engines handle wide denormalized dimensions well. Normalize when dimension rows exceed millions with sparse attributes — or use entity-attribute-value (usually avoid).

## Building stars in dbt

Staging → intermediate → marts:

```
stg_orders ──┐
stg_order_items ──┼──▶ int_order_lines ──▶ fct_order_lines
dim_product ──────┘
dim_customer (SCD2 snapshot)
dim_date (generated spine)
```

Facts reference surrogate keys from dimensions. Load dimensions before facts or use late-binding date-range joins for Type 2.

## Common mistakes

Fan traps from joining facts through shared dimensions at wrong grain. Junk dimensions stuffing low-cardinality flags into one table — acceptable at small scale. Null foreign keys breaking inner joins — use `unknown` dimension rows.

Star schema success is boring documentation of grain and conformed dimensions — not ER diagram aesthetics.

## Slowly Changing Dimensions (SCD) in practice

Dimensions change over time — SCD Type 2 preserves history:

```sql
-- dim_customer with SCD Type 2
CREATE TABLE dim_customer (
    customer_sk BIGINT PRIMARY KEY,       -- surrogate key (changes per version)
    customer_id TEXT NOT NULL,            -- natural key (stable)
    name TEXT,
    city TEXT,
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL DEFAULT '9999-12-31',
    is_current BOOLEAN NOT NULL DEFAULT TRUE
);

-- dbt snapshot handles SCD2 automatically
{% snapshot dim_customer_snapshot %}
    SELECT customer_id, name, city FROM {{ ref('stg_customers') }}
{% endsnapshot %}
```

Join facts to dimensions using date-range logic:

```sql
SELECT f.order_amount, d.name
FROM fct_orders f
JOIN dim_customer d
  ON f.customer_id = d.customer_id
  AND f.order_date BETWEEN d.valid_from AND d.valid_to
```

Use SCD Type 1 (overwrite) for dimensions where history doesn't matter (e.g., corrected typos). Use SCD Type 2 for attributes that affect analytics (customer tier, product category).

## Conformed dimensions across facts

The same `dim_date` and `dim_customer` appear in multiple fact tables:

```
fct_orders ──→ dim_customer ←── fct_support_tickets
fct_orders ──→ dim_date     ←── fct_support_tickets
```

Conformed dimensions enable cross-fact analysis: "support ticket volume by customer tier" joins `fct_support_tickets` to the same `dim_customer` used by `fct_orders`.

Define conformed dimensions once in dbt `marts/core/` — never duplicate dimension logic per fact.

## Aggregate fact tables

Pre-compute common rollups to avoid scanning massive fact tables:

```sql
-- Monthly order summary (aggregate fact)
CREATE TABLE fct_orders_monthly AS
SELECT
    DATE_TRUNC('month', order_date) AS month,
    customer_sk,
    product_sk,
    COUNT(*) AS order_count,
    SUM(order_amount) AS total_amount
FROM fct_orders
GROUP BY 1, 2, 3;
```

Use aggregate facts for dashboards querying monthly totals. Keep atomic fact for drill-down to individual orders. dbt makes this easy with incremental models on the aggregate.

## Failure modes

- **Undocumented grain** — "one row per what?" ambiguous; double-counting in joins
- **Fan trap** — joining two facts through shared dimension at wrong grain
- **SCD Type 2 without date-range join** — current dimension row used for all history
- **Duplicate dimension logic** — inconsistent customer definitions across facts
- **Null foreign keys** — inner join drops fact rows; use unknown dimension row

## Production checklist

- Grain documented for every fact table (one row per X)
- Conformed dimensions in shared dbt marts/core layer
- SCD Type 2 for attributes affecting historical analysis
- Unknown dimension row for null foreign keys
- Aggregate facts for common dashboard rollups
- dbt tests: unique, not_null on surrogate keys; relationships between facts and dims

## Resources

- [Kimball Group — Dimensional modeling techniques](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/)
- [The Data Warehouse Toolkit (Kimball & Ross)](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/books/data-warehouse-dw-toolkit/)
- [dbt — How we structure our dbt projects](https://docs.getdbt.com/best-practices/how-we-structure/1-guide-overview)
- [Star schema vs snowflake (Oracle)](https://docs.oracle.com/en/database/oracle/oracle-database/19/dwhsg/part-dimension-modeling.html)
- [Dimensional modeling (Snowflake guide)](https://docs.snowflake.com/en/user-guide/table-design-dimension-model)
