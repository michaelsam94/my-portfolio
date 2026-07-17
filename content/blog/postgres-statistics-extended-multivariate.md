---
title: "Postgres Extended Statistics and Multivariate Correlation"
slug: "postgres-statistics-extended-multivariate"
description: "Use CREATE STATISTICS with dependencies and ndistinct to fix bad cardinality estimates on correlated columns and JOIN planning."
datePublished: "2026-03-04"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
keywords: "extended statistics, multivariate ndistinct, functional dependencies, postgres planner, CREATE STATISTICS"
faq:
  - q: "What problem do extended statistics solve that ANALYZE alone cannot?"
    a: "Standard statistics store per-column histograms and ndistinct. The planner assumes column values are independent unless told otherwise. Correlated columns—city/state, brand/product_line—produce wrong row estimates when combined in WHERE clauses. Extended statistics capture dependencies and multivariate ndistinct."
  - q: "When should I create extended statistics?"
    a: "When EXPLAIN shows orders-of-magnitude misestimates on queries filtering multiple correlated columns, or JOIN sizes wildly off. Confirm with EXPLAIN ANALYZE comparing estimated vs actual rows. Avoid creating stats on every column pair."
  - q: "What is the difference between dependencies and ndistinct extended stats?"
    a: "Functional dependencies record that knowing one column value determines another with degree n. ndistinct stats track distinct counts of column combinations, improving estimates for AND conditions and GROUP BY on multiple columns."
  - q: "Do extended statistics require manual ANALYZE after creation?"
    a: "Yes. CREATE STATISTICS defines what to collect; ANALYZE populates pg_statistic_ext_data. After bulk loads, run ANALYZE explicitly. Use stats_target option for finer granularity on critical stat objects."
---

The planner is only as smart as its cardinality estimates. **`EXPLAIN`** predicts 50 rows, **`EXPLAIN ANALYZE`** returns 50,000—nested loop disaster, wrong parallel worker count. Single-column histograms assume **`country = 'DE' AND language = 'de'`** independence when every German row speaks German.

**Extended statistics** let you declare **functional dependencies** and **multivariate ndistinct** so the optimizer models correlation.

## Baseline: what ANALYZE stores

Combined selectivity for **`WHERE a = 1 AND b = 2`** defaults to **`sel(a) * sel(b)`**—wrong when **`b`** determined by **`a`**.

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM customers
WHERE country_code = 'DE' AND default_locale = 'de-DE';
```

## CREATE STATISTICS overview

```sql
CREATE STATISTICS stat_customer_locale (dependencies, ndistinct)
ON country_code, default_locale
FROM customers;

ANALYZE customers;
```

### Functional dependencies

**`dependencies`** detects **`b`** functionally dependent on **`a`**. Example: **`zip_code → city`**.

```sql
CREATE STATISTICS stat_zip_city (dependencies)
ON zip_code, city FROM addresses;
ANALYZE addresses;
```

### Multivariate ndistinct

**`ndistinct`** tracks distinct count of **(a,b)** together.

```sql
CREATE STATISTICS stat_brand_line (ndistinct)
ON brand_id, product_line FROM products;
```

### Combined with mcv (PG 14+)

```sql
CREATE STATISTICS stat_orders_filter (dependencies, ndistinct, mcv)
ON tenant_id, status, created_date FROM orders;
```

## stats_target and sample size

```sql
CREATE STATISTICS stat_orders_filter (mcv)
ON tenant_id, status FROM orders
WITH (stats_target = 1000);
ANALYZE orders;
```

Higher target increases ANALYZE time—use on proven problem queries only.

## Expressions and generated columns

Extended stats require plain column references. For **`date_trunc('day', created_at)`**, use generated column:

```sql
ALTER TABLE events ADD created_day date
  GENERATED ALWAYS AS ((created_at AT TIME ZONE 'UTC')::date) STORED;
CREATE STATISTICS stat_events (ndistinct)
ON tenant_id, created_day FROM events;
```

## Worked example: join misestimate

**`orders JOIN customers`** with **`country = 'FR' AND tier = 'enterprise'`**—planner expects 100 rows, gets 80k.

```sql
CREATE STATISTICS stat_customer_tier (dependencies, ndistinct)
ON country, tier, account_type FROM customers;
ANALYZE customers;
```

Re-explain—hash join may appear with realistic memory grant. Stats fix cardinality; indexes still required for IO.

## Workflow for fixing a bad plan

1. Capture misestimate ≥ 10×
2. Identify correlated columns in WHERE, JOIN, GROUP BY
3. CREATE STATISTICS
4. ANALYZE
5. Re-run EXPLAIN ANALYZE

## Limits and planner behavior

- Stats apply when listed columns appear in relevant clauses
- Cross-table correlation not covered—fix joins separately
- Partitioned tables: verify behavior on your Postgres version

## Maintenance burden

Audit quarterly; drop unused stats:

```sql
DROP STATISTICS stat_legacy_pair;
```

## Comparison with other fixes

| Approach | Fixes correlation |
| --- | --- |
| Extended statistics | Yes, same table |
| Partial indexes | Query path only |
| Denormalize flag | Application change |
| pg_hint_plan | Per query hack |

## Version upgrade regression testing

Capture EXPLAIN golden files pre-upgrade; compare estimates post-upgrade. Drop stats objects that no longer help.

## When extended stats cannot help

Highly volatile columns (random UUID per row) have no stable correlation. Cross-table join errors need FK ANALYZE on both sides.

## Sampling and ANALYZE frequency

After bulk UPDATE overnight, run manual ANALYZE before peak—autovacuum analyze delay may leave stale dependencies.

Prefer extended stats when correlation is structural (geography, product taxonomy, status enums), not accidental stale stats.



## Correlated join keys across tables

Extended stats do not fix **`orders.customer_id JOIN customers.id`** when **`orders.status`** correlates with **`customers.tier`** on different tables—planner multiplies selectivities across tables independently. Mitigations: denormalize **`customer_tier`** onto **`orders`**, use **`CREATE STATISTICS`** on denormalized column pair, or increase statistics targets on join keys. Multivariate stats are not a universal cardinality panacea.

## Automatic extended stats future

Postgres research continues on auto-detecting dependencies during **`ANALYZE`**—today manual **`CREATE STATISTICS`** remains explicit. Review release notes on major upgrades for **`default_statistics_target`** or auto dependency features before re-creating dozens of stat objects manually.

## EXPLAIN interpretation exercise

When **`rows=1`** estimate on nested loop inner side explodes to millions, check whether inner filter combines two correlated columns on same table—classic extended stats candidate. When misestimate on **`OR`** predicates, stats may need **`mcv`** list capturing frequent combined tuples absent from univariate MCV.

## Storage overhead

**`pg_statistic_ext_data`** grows with **`stats_target`** and column count in stat object—monitor catalog bloat on instances with hundreds of custom stat objects. Drop stats tied to dropped query patterns after schema simplification.




## Functional dependency degree interpretation

**`stxdependencies`** JSON shows degree close to 1.0 when **`city`** almost determined by **`zip`**. Degree 0.3 means weak dependency—planner adjustment subtle. Re-analyze after postal code boundary changes (rare real-world event) that break dependency.

## Extended stats on partitioned tables

Create matching **`CREATE STATISTICS`** on parent partitioned table where supported—verify **`ANALYZE`** propagates to partitions on your version. Misaligned stats on default partition only skew plans for rows landing in default.

## Manual row estimates last resort

**`ALTER TABLE ... ALTER COLUMN ... SET (n_distinct = ...)`** per column hacky compared to extended stats—use only when stats cannot capture skew (e.g., pending partition empty). Extended stats preferred when correlation is root cause.




## Teaching the planner: workshop exercise

Pick one slow report query, capture misestimate ratio, add extended stats, re-measure—team learning beats silent stat object proliferation. Document stat object purpose in migration message **`-- stats: fix join orders/customers underestimate after tier filter`**.

## pg_stat_statements pairing

Find queries with highest total time where plan shows nested loop and bad row estimate—prioritize extended stats candidacy. Queries already using hash join with good timing need stats work elsewhere.




## Anti-pattern: stats without ANALYZE job

Creating stats during migration Friday without **`ANALYZE`** before Monday traffic leaves planner blind until autovacuum catches up—schedule **`ANALYZE`** in same migration transaction or immediately after commit. CI migration tests should assert **`pg_statistic_ext_data`** non-empty for new stats objects.




## Column group cardinality sanity check

Before **`CREATE STATISTICS`**, run **`SELECT count(distinct (a,b)) FROM t`** on sample or full table offline—if combined ndistinct equals product of individual ndistinct estimates, extended stats may add little value. When combined ndistinct far below product, dependencies or ndistinct stats likely help.

## Histogram bounds and correlated range queries

Range queries **`WHERE salary BETWEEN ... AND department = 'Sales'`** may misestimate when salary correlates with department—**`mcv`** extended stats help skewed department/salary pairs. Pure dependencies insufficient when correlation is statistical not functional.



## Planner regression after stats deployment

Deploy stats in canary: create on staging clone with production stats snapshot, compare top 20 query plans, then production create+analyze during low traffic. Rollback plan DROP STATISTICS if p95 latency regresses on unrelated queries—extended stats occasionally help one query hurt another via global plan changes.

## Combining with partial indexes

Partial index on hot subset plus extended stats on full table—planner must estimate index predicate selectivity and remaining filters; ensure partial index predicate columns included in stats object when correlated with filtered columns.


## Catalog hygiene

Quarterly review pg_statistic_ext entries against pg_stat_statements—drop stats unused by any top query plan. Stale stats objects consume ANALYZE time without benefit.




## Stats on expression indexes

If query filters indexed expression, stats on base column alone insufficient—extend generated column approach or use expression index matching exact predicate. Extended stats cannot reference arbitrary expressions directly.

## auto_explain pairing

Enable auto_explain for plans where estimated rows off by 100x; correlate with missing extended stats on filter columns. Close loop: stat object ticket links to auto_explain log hash.

## Column order in CREATE STATISTICS

Column order in CREATE STATISTICS does not affect dependency detection but documents intent—list driving column first in migration comments for future DBAs.

Name extended statistics after the query family they fix so future engineers do not drop them as unused catalog clutter during spring cleaning.

## Resources

- [CREATE STATISTICS](https://www.postgresql.org/docs/current/sql-createstatistics.html)
- [Planner statistics](https://www.postgresql.org/docs/current/planner-stats-details.html)
