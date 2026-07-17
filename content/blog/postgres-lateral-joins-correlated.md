---
title: "Postgres Lateral Joins Correlated"
slug: "postgres-lateral-joins-correlated"
description: "Use LATERAL joins for correlated subqueries that reference outer rows — top-N per group, unnest with context, and set-returning functions."
datePublished: "2026-02-23"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
keywords: "lateral join postgres, correlated subquery, top n per group, cross join lateral, set returning function"
faq:
  - q: "How is LATERAL different from a regular JOIN?"
    a: "A regular JOIN evaluates its right side independently — the same result for every outer row. LATERAL allows the right side to reference columns from the left side, re-evaluating per outer row. It is syntactic sugar for correlated subqueries in the FROM clause with cleaner composition of multiple lateral sources."
  - q: "When should I use LATERAL instead of a window function?"
    a: "Use window functions when you need ranking across a set without per-row subquery execution. Use LATERAL when the inner query is inherently per-row — calling a set-returning function with outer parameters, fetching top-N with LIMIT tied to outer row, or when the inner side is a complex subquery that would require nested window + filter."
  - q: "Does LATERAL cause N+1 query performance problems?"
    a: "It can — LATERAL re-executes the right side for each outer row unless the planner optimizes it to a join or hash strategy. Always EXPLAIN ANALYZE. Index columns referenced in the LATERAL correlation. For large outer sets with expensive inner queries, a window function or grouped aggregation may outperform naive LATERAL."
---

You need the three most recent orders per customer. Or a JSON array unnested with access to the parent row's ID. Or a geospatial nearest-neighbor lookup for each store location. Standard joins cannot express "for each row on the left, run this query using that row's values" — correlated subqueries in SELECT or WHERE work but become unreadable and often perform poorly. **LATERAL** puts correlated execution in the FROM clause, composing cleanly with other joins and letting the planner optimize what would otherwise be nested loops hidden in subqueries.

## LATERAL semantics

```sql
SELECT *
FROM outer_table o
CROSS JOIN LATERAL (
  SELECT * FROM inner_table i
  WHERE i.foreign_key = o.id
  LIMIT 3
) recent;
```

For each row `o`, the lateral subquery executes with `o.id` in scope. `CROSS JOIN LATERAL` is required when the lateral subquery could return zero rows (still produces outer row with NULLs if LEFT JOIN LATERAL). Without LATERAL keyword, referencing `o.id` inside the subquery is a syntax error.

Equivalent correlated subquery in SELECT (less composable):

```sql
SELECT o.*,
  (SELECT json_agg(i.*) FROM inner_table i WHERE i.foreign_key = o.id LIMIT 3)
FROM outer_table o;
```

## Top-N per group

Classic pattern — three latest orders per customer:

```sql
SELECT c.id, c.name, recent.*
FROM customers c
CROSS JOIN LATERAL (
  SELECT o.id AS order_id, o.total, o.created_at
  FROM orders o
  WHERE o.customer_id = c.id
  ORDER BY o.created_at DESC
  LIMIT 3
) recent;
```

With index:

```sql
CREATE INDEX orders_customer_created ON orders (customer_id, created_at DESC);
```

EXPLAIN ANALYZE should show index scan per customer or a optimized join — not sequential scan of entire orders table per customer.

Window function alternative:

```sql
SELECT * FROM (
  SELECT o.*,
         row_number() OVER (PARTITION BY customer_id ORDER BY created_at DESC) AS rn
  FROM orders o
) ranked
WHERE rn <= 3;
```

Compare both with EXPLAIN ANALYZE at your data scale. Window functions scan the full partition once; LATERAL with good index may win for sparse outer sets (few customers, many orders).

## LEFT JOIN LATERAL for optional matches

Include customers with zero orders:

```sql
SELECT c.id, c.name, recent.order_id, recent.total
FROM customers c
LEFT JOIN LATERAL (
  SELECT o.id AS order_id, o.total
  FROM orders o
  WHERE o.customer_id = c.id
  ORDER BY o.created_at DESC
  LIMIT 1
) recent ON true;
```

`ON true` — the lateral subquery itself filters correlation; join condition is always satisfied when rows exist. Without LEFT, customers with no orders disappear from results.

## Set-returning functions

LATERAL shines with functions returning sets:

```sql
SELECT p.id, p.name, tag
FROM products p
CROSS JOIN LATERAL unnest(p.tags) AS tag;
```

Unnest tags array per product with product context available.

JSON expansion:

```sql
SELECT d.id, elem->>'key' AS key, elem->>'value' AS value
FROM documents d
CROSS JOIN LATERAL jsonb_array_elements(d.metadata->'attributes') AS elem;
```

Geospatial nearest neighbor per store:

```sql
SELECT s.id, nearest.location, nearest.distance
FROM stores s
CROSS JOIN LATERAL (
  SELECT l.location, l.location <-> s.location AS distance
  FROM landmarks l
  ORDER BY l.location <-> s.location
  LIMIT 1
) nearest;
```

Requires GiST index on `landmarks.location` for acceptable performance.

## Multiple LATERAL joins

Chain independent correlated sources:

```sql
SELECT
  c.id,
  recent_orders.order_count,
  recent_orders.latest_total,
  top_product.product_name
FROM customers c
CROSS JOIN LATERAL (
  SELECT count(*) AS order_count,
         max(created_at) AS last_order,
         (SELECT total FROM orders o2
          WHERE o2.customer_id = c.id
          ORDER BY created_at DESC LIMIT 1) AS latest_total
  FROM orders o
  WHERE o.customer_id = c.id
) recent_orders
CROSS JOIN LATERAL (
  SELECT p.name AS product_name
  FROM order_items oi
  JOIN products p ON p.id = oi.product_id
  JOIN orders o ON o.id = oi.order_id
  WHERE o.customer_id = c.id
  GROUP BY p.name
  ORDER BY sum(oi.quantity) DESC
  LIMIT 1
) top_product;
```

Each LATERAL block references `c.id` independently. Readable decomposition vs nested subqueries.

## LATERAL with generate_series

Generate per-row sequences:

```sql
SELECT e.id, e.name, day.date
FROM employees e
CROSS JOIN LATERAL generate_series(
  e.start_date,
  e.end_date,
  '1 day'::interval
) AS day(date);
```

Produce one row per day in each employee's employment range — useful for gap filling in reports.

## Planner behavior and optimization

Postgres may rewrite LATERAL to:

- **Nested loop** with index scan on inner — ideal for top-N with index
- **Hash join** if inner is materialized once and probed
- **SubPlan** in older plans for simple correlations

Force investigation with:

```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT ... CROSS JOIN LATERAL (...) ...;
```

Red flags:

- Sequential scan on inner for every outer row
- `Rows Removed by Filter` in millions
- Execution time scaling linearly with outer row count × inner cost

Fix with indexes on correlation columns, reduce outer row set with WHERE before LATERAL, or rewrite to window function / grouped aggregation.

## LATERAL vs DISTINCT ON

Top-1 per group with DISTINCT ON:

```sql
SELECT DISTINCT ON (customer_id)
  customer_id, id, total, created_at
FROM orders
ORDER BY customer_id, created_at DESC;
```

Single table, single dimension — DISTINCT ON is often faster and simpler. LATERAL wins when:

- Inner query involves joins or aggregation
- N > 1 with complex ordering
- Outer table is not the same as inner partition key table

## LATERAL in UPDATE and DELETE

Correlated subqueries in data modification:

```sql
UPDATE products p
SET lowest_competitor_price = comp.price
FROM (
  SELECT p2.id AS product_id, MIN(c.price) AS price
  FROM products p2
  CROSS JOIN LATERAL (
    SELECT price FROM competitor_prices cp
    WHERE cp.product_id = p2.id
    ORDER BY price ASC
    LIMIT 1
  ) c
  GROUP BY p2.id
) comp
WHERE p.id = comp.product_id;
```

Prefer JOIN syntax over LATERAL in UPDATE when a simple join suffices — LATERAL adds value when inner requires ORDER BY LIMIT per row.

## Common mistakes

**Forgetting LATERAL keyword**:

```sql
-- ERROR: invalid reference to FROM-clause entry
FROM customers c, (SELECT * FROM orders WHERE customer_id = c.id) o
```

**CROSS JOIN LATERAL when LEFT intended**: Customers without orders excluded.

**Missing index on correlation column**: Nested loop degrades to O(n×m).

**LATERAL subquery returning multiple unbounded rows**: Always LIMIT or aggregate when expecting one row — otherwise duplicate outer rows.

**Using LATERAL where simple JOIN works**:

```sql
-- Unnecessary LATERAL
FROM orders o
CROSS JOIN LATERAL (SELECT name FROM customers c WHERE c.id = o.customer_id) cust

-- Simple JOIN
FROM orders o JOIN customers c ON c.id = o.customer_id
```

## Readability guidelines

Use LATERAL when:

- Inner query references outer row columns
- Inner uses LIMIT/ORDER BY per outer row
- Inner invokes set-returning functions with outer parameters
- Decomposing complex query into named lateral "modules"

Avoid LATERAL when a plain JOIN or window function expresses the logic with equal clarity and better performance.

## Debugging LATERAL plan regressions

When a LATERAL query regresses after a Postgres upgrade or statistics change:

1. Capture EXPLAIN ANALYZE from before and after
2. Check whether correlation column statistics drifted: `SELECT attname, n_distinct, correlation FROM pg_stats WHERE tablename = 'orders' AND attname = 'customer_id'`
3. Try increasing statistics target: `ALTER TABLE orders ALTER COLUMN customer_id SET STATISTICS 1000; ANALYZE orders;`
4. Compare forced plans: `SET enable_nestloop = off` temporarily to test hash join alternative
5. If regression persists, rewrite to window function and A/B test at production row counts

Document the winning pattern in query comments — LATERAL vs window function choice is data-volume dependent and should not be left to implicit team knowledge.

## Summary

LATERAL joins let the right side of a FROM clause reference left-side rows, re-evaluating per outer row. They excel at top-N per group, set-returning function expansion, and correlated lookups that would otherwise be opaque nested subqueries. Index correlation columns, verify plans with EXPLAIN ANALYZE, and compare against window function alternatives at production data volumes. Used deliberately, LATERAL makes complex correlated SQL readable; used blindly, it becomes a nested loop performance trap.
