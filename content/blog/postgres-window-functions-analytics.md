---
title: "Postgres Window Functions for Analytics"
slug: "postgres-window-functions-analytics"
description: "Running totals, rank, lag/lead, and frame clauses for reporting queries without self-join explosion."
datePublished: "2026-03-11"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
keywords: "postgres window functions, running total, lag lead, rank dense_rank, analytics SQL"
faq:
  - q: "When should I use a window function instead of a self-join or subquery?"
    a: "Use windows when you need a value from another row in the same result set without collapsing rows — running totals, prior-period comparisons, rankings within a partition. Self-joins explode row counts and become error-prone on tie-breaking; windows keep one row per entity and express the relationship declaratively."
  - q: "What is the difference between ROWS and RANGE frame clauses?"
    a: "ROWS counts physical row offsets (previous 1 row). RANGE uses logical value distance on the ORDER BY key — all rows with the same order value are peers. For time-series with duplicate timestamps, RANGE includes all ties; ROWS may exclude some peers. Default frames differ: aggregate windows default to RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW."
  - q: "Do window functions slow down queries compared to GROUP BY?"
    a: "They add a WindowAgg node after sorting or hashing. For large partitions, memory and sort cost dominate. You cannot index a window directly, but indexing (partition columns, ORDER BY columns) helps the sort beneath WindowAgg. Often window queries are faster than equivalent correlated subqueries because the planner computes once per partition."
---

The finance team asked for month-over-month revenue retention by cohort without exporting to a spreadsheet. The first attempt — three self-joins on `subscriptions` — timed out at ninety seconds and double-counted upgrades. Rewriting with `LAG()` and a defined frame turned the same report into an eight-second query that analysts could parameterize in Metabase. Window functions are Postgres's native answer to "spreadsheet logic in SQL."

## The OVER clause mental model

A window function computes across a **window** of rows related to the current row. Unlike `GROUP BY`, it does not collapse the result set.

```sql
SELECT
  customer_id,
  order_date,
  amount,
  SUM(amount) OVER (
    PARTITION BY customer_id
    ORDER BY order_date
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS running_total
FROM orders;
```

Every row stays visible; `running_total` accumulates within each `customer_id` partition.

Execution shape (simplified):

```
Seq Scan / Index Scan
        │
        ▼
   Sort (partition, order)
        │
        ▼
   WindowAgg
        │
        ▼
   Result
```

Read plans with `EXPLAIN (ANALYZE, BUFFERS)` and look for `WindowAgg` plus sort node width.

## Ranking: ROW_NUMBER, RANK, DENSE_RANK

Product wanted "top 3 products per category by revenue last quarter." Rank functions differ on ties:

```sql
WITH ranked AS (
  SELECT
    category,
    product_name,
    revenue,
    ROW_NUMBER() OVER (PARTITION BY category ORDER BY revenue DESC) AS rn,
    RANK()           OVER (PARTITION BY category ORDER BY revenue DESC) AS rk,
    DENSE_RANK()     OVER (PARTITION BY category ORDER BY revenue DESC) AS dr
  FROM product_revenue
  WHERE quarter = '2026-Q2'
)
SELECT * FROM ranked WHERE rn <= 3;
```

| Function | Tie behavior | Gap after tie |
|----------|--------------|---------------|
| `ROW_NUMBER()` | Arbitrary order among ties | Never gaps |
| `RANK()` | Same rank for ties | Skips numbers (1,1,3) |
| `DENSE_RANK()` | Same rank for ties | No gaps (1,1,2) |

Use `ROW_NUMBER()` when you need exactly N rows. Use `RANK()` for leaderboard semantics where ties share placement.

Filter ranked results in an outer query or CTE — you cannot use `WHERE rank <= 3` directly on the window in the same SELECT level.

## LAG and LEAD for period-over-period analysis

Cohort and retention reports almost always need the previous or next row in time order:

```sql
SELECT
  date_trunc('month', created_at) AS month,
  COUNT(*) AS new_users,
  LAG(COUNT(*)) OVER (ORDER BY date_trunc('month', created_at)) AS prev_month,
  ROUND(
    100.0 * (COUNT(*) - LAG(COUNT(*)) OVER (ORDER BY date_trunc('month', created_at)))
    / NULLIF(LAG(COUNT(*)) OVER (ORDER BY date_trunc('month', created_at)), 0),
    2
  ) AS mom_pct_change
FROM users
GROUP BY date_trunc('month', created_at)
ORDER BY 1;
```

`LAG(expr, offset, default)` avoids NULL on the first row when you supply a default. `LEAD()` looks forward — useful for detecting sessions ending without a logout event.

For **same-day-last-year** comparisons, fill missing dates with `generate_series` in a CTE first or LAG skips rows.

## Frames: rolling averages and moving windows

Rolling seven-day active users:

```sql
SELECT
  day,
  daily_active,
  AVG(daily_active) OVER (
    ORDER BY day
    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
  ) AS rolling_7d_avg
FROM daily_metrics;
```

`ROWS` counts literal rows — if your series has gaps (weekends missing), the window covers seven **observed** rows, not seven calendar days. For calendar windows on sparse data, generate a dense date spine first:

```sql
WITH spine AS (
  SELECT d::date AS day
  FROM generate_series('2026-01-01'::date, '2026-06-30'::date, '1 day') d
),
filled AS (
  SELECT s.day, COALESCE(m.daily_active, 0) AS daily_active
  FROM spine s
  LEFT JOIN daily_metrics m USING (day)
)
SELECT day, daily_active,
       AVG(daily_active) OVER (
         ORDER BY day
         ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
       ) AS rolling_7d_avg
FROM filled;
```

`RANGE BETWEEN INTERVAL '6 days' PRECEDING AND CURRENT ROW` requires an appropriate `ORDER BY` type (timestamp/date) and includes peer rows sharing the same order key.

## FIRST_VALUE and LAST_VALUE for session boundaries

Session analytics often need the landing page (first event) alongside every subsequent click in the same session:

```sql
SELECT
  session_id,
  event_time,
  page_url,
  FIRST_VALUE(page_url) OVER (
    PARTITION BY session_id ORDER BY event_time
    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
  ) AS landing_page,
  LAST_VALUE(page_url) OVER (
    PARTITION BY session_id ORDER BY event_time
    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
  ) AS exit_page
FROM clickstream;
```

`LAST_VALUE` requires explicit frame to `UNBOUNDED FOLLOWING` — default frame stops at current row, giving wrong "last" value. This footgun appears in half of broken funnel queries we review.

## NTILE and percentile buckets

Decile analysis for customer spend:

```sql
SELECT
  customer_id,
  total_spend,
  NTILE(10) OVER (ORDER BY total_spend) AS spend_decile
FROM customer_totals;
```

`PERCENT_RANK()` and `CUME_DIST()` express relative standing (0–1). Choose based on whether you need bucket labels (NTILE) or continuous rank fraction (PERCENT_RANK).

## Multiple windows in one query

Postgres allows different `OVER` clauses in the same SELECT — each may trigger separate WindowAgg nodes or combine depending on partition/order compatibility:

```sql
SELECT
  employee_id,
  department,
  salary,
  AVG(salary) OVER (PARTITION BY department) AS dept_avg,
  salary - AVG(salary) OVER (PARTITION BY department) AS vs_dept_avg,
  RANK() OVER (PARTITION BY department ORDER BY salary DESC) AS dept_rank
FROM employees;
```

When partitions and orderings match, the planner may compute one window pass — verify with `EXPLAIN`.

## Real report: subscription MRR bridge

Monthly recurring revenue bridge with new, expansion, contraction, churn:

```sql
WITH monthly AS (
  SELECT
    account_id,
    date_trunc('month', snapshot_date) AS month,
    mrr
  FROM account_mrr_snapshots
),
with_lag AS (
  SELECT
    account_id,
    month,
    mrr,
    LAG(mrr) OVER (PARTITION BY account_id ORDER BY month) AS prev_mrr
  FROM monthly
)
SELECT
  month,
  SUM(CASE WHEN prev_mrr IS NULL THEN mrr ELSE 0 END) AS new_mrr,
  SUM(CASE WHEN prev_mrr IS NOT NULL AND mrr > prev_mrr THEN mrr - prev_mrr ELSE 0 END) AS expansion,
  SUM(CASE WHEN prev_mrr IS NOT NULL AND mrr < prev_mrr AND mrr > 0 THEN prev_mrr - mrr ELSE 0 END) AS contraction,
  SUM(CASE WHEN mrr = 0 AND prev_mrr > 0 THEN prev_mrr ELSE 0 END) AS churn
FROM with_lag
GROUP BY month
ORDER BY month;
```

This pattern — stage with windows, aggregate in outer query — keeps business logic readable and testable per CTE.

## Performance tactics

1. **Reduce rows before the window.** Filter time range in inner query.
2. **Index for sort elimination.** Composite index on `(partition_col, order_col)`.
3. **work_mem.** Large partitions spill sort to disk — watch `EXPLAIN` for external merge.
4. **Distinct on alternative.** "Latest row per user" sometimes fits `DISTINCT ON` better than `ROW_NUMBER()` — benchmark both.
5. **Materialized views.** Dashboards hitting the same window definitions every minute belong in a matview.

## Common mistakes

- **Nesting window functions.** `LAG(SUM(x) OVER (...))` is invalid; compute inner window in subquery first.
- **Forgetting ORDER BY in frame.** Undefined row order means nondeterministic running totals.
- **Default frame with aggregates.** `SUM(x) OVER (ORDER BY t)` uses `RANGE ... CURRENT ROW`, which behaves differently from `ROWS` on ties — be explicit.
- **Mixing GROUP BY and windows incorrectly.** Window runs after GROUP BY; reference grouped columns or aggregates.

## Export to BI tools

Metabase, Lightdash, and Mode pass SQL through to Postgres — window functions work natively. Document frame semantics in saved question descriptions so analysts do not "fix" queries by adding self-joins.

Window functions express analytic questions in the shape analysts already think — partitioned, ordered, compared to neighbors. They replace fragile self-joins with declarative frames, and they profile like any other sort-heavy query: filter early, index the sort keys, and read the plan.

## Gap analysis with IGNORE NULLS (PostgreSQL 14+)

Sparse event streams skip months with zero activity — `LAG` returns NULL across gaps unless you densify the spine. PostgreSQL 14 adds `IGNORE NULLS` option on some window functions in limited contexts; more portable pattern remains `generate_series` left join. For funnel drop-off, compare `COUNT(*) FILTER (WHERE step = 'checkout')` over window partitions rather than joining step tables — fewer rows, clearer intent.

## Recursive comparison to self-join reports

A self-join for "orders with amount greater than previous order per customer" duplicates the orders table:

```sql
-- Self-join: O(n²) risk on large tables
SELECT a.customer_id, a.order_id, a.amount
FROM orders a
JOIN orders b ON b.customer_id = a.customer_id AND b.order_date < a.order_date
WHERE a.amount > (SELECT MAX(amount) FROM orders c
                  WHERE c.customer_id = a.customer_id AND c.order_date < a.order_date);
```

Window equivalent scans once:

```sql
SELECT customer_id, order_id, amount
FROM (
  SELECT *, LAG(amount) OVER (PARTITION BY customer_id ORDER BY order_date) AS prev
  FROM orders
) x WHERE amount > prev;
```

Benchmark on production row counts — windows usually win above 100k rows per partition when sort can use index.
