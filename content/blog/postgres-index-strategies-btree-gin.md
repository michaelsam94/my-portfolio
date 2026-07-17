---
title: "Postgres Index Strategies"
slug: "postgres-index-strategies-btree-gin"
description: "Choose the right Postgres index type: B-tree, GIN, GiST, BRIN, partial and covering indexes, with EXPLAIN-driven decisions for OLTP workloads."
datePublished: "2026-03-16"
dateModified: "2026-07-17"
tags: ["PostgreSQL", "Backend", "Database", "Performance"]
keywords: "PostgreSQL index types, B-tree GIN GiST, partial index Postgres, covering index INCLUDE, Postgres index strategy"
faq:
  - q: "When should I use a GIN index instead of B-tree in Postgres?"
    a: "GIN suits composite values searched by containment — JSONB keys, array elements, full-text tsvector, pg_trgm fuzzy match. B-tree suits equality and range on scalar columns (id, timestamp, status). Wrong index type means sequential scans despite an index existing."
  - q: "What is a partial index and when is it useful?"
    a: "An index with a WHERE clause indexing only matching rows — e.g. WHERE status = 'pending'. Smaller index, faster writes, perfect for queries always filtering on that condition. Unused if queries omit the filter."
  - q: "Do covering indexes (INCLUDE) eliminate table lookups?"
    a: "For index-only scans when visibility map confirms heap pages are all-visible. INCLUDE columns appear in index leaf pages but aren't searchable keys. Reduces heap fetches for SELECT lists returning few columns."
---

`CREATE INDEX` on every column is a reflex. I've seen tables with fourteen indexes where only two were used — write amplification killed insert throughput. Postgres offers B-tree, GIN, GiST, BRIN, hash, and SP-GiST; picking wrong type gives you an expensive sequential scan with extra storage overhead.

## B-tree: default for scalars

Equality, range, sorting, `LIKE 'prefix%'`:

```sql
CREATE INDEX orders_user_created_idx ON orders (user_id, created_at DESC);
```

Composite index column order matters — leading column must appear in WHERE for efficient use (with exceptions for skip scans on newer versions).

**Multi-column rule:** put high-selectivity equality columns first, range columns last.

```sql
-- Good for: WHERE user_id = ? AND created_at > ?
CREATE INDEX ON orders (user_id, created_at);

-- Bad for user-only queries if user_id is second — verify with EXPLAIN
```

## GIN: containment and full-text

```sql
-- JSONB
CREATE INDEX ON events USING GIN (payload jsonb_path_ops);
-- Query: payload @> '{"type": "click"}'

-- Arrays
CREATE INDEX ON posts USING GIN (tags);
-- Query: tags @> ARRAY['postgres']

-- Full text
CREATE INDEX ON articles USING GIN (search_vector);
```

`jsonb_path_ops` smaller/faster for `@>`; default `jsonb_ops` supports more operators (`?`, `?&`).

GIN updates are expensive — avoid on high-write JSONB if queries are rare.

## GiST: geometry and ranges

PostGIS geometries, range types, exclusion constraints:

```sql
CREATE INDEX ON bookings USING GIST (during);
-- Overlap query: during && '[2026-03-01, 2026-03-05]'
```

Also full-text alternative to GIN when update frequency is high (trade read speed).

## BRIN: massive sequential data

Block Range INdex — stores min/max per heap block range. Tiny index size for time-series:

```sql
CREATE INDEX ON logs USING BRIN (created_at) WITH (pages_per_range = 128);
```

Works when physical row order correlates with indexed column (append-only timestamps). Random UUID inserts — BRIN useless.

## Partial indexes

```sql
CREATE INDEX orders_pending_idx ON orders (created_at)
WHERE status = 'pending';
```

Index 2% of rows instead of 100%. Queries must include `status = 'pending'` (or stricter) for planner use.

Unique partial index for soft-delete patterns:

```sql
CREATE UNIQUE INDEX users_email_active_idx ON users (email)
WHERE deleted_at IS NULL;
```

## Covering indexes (INCLUDE)

```sql
CREATE INDEX orders_user_idx ON orders (user_id)
INCLUDE (total_cents, status);
```

Index-only scan returns `total_cents, status` without heap visit when visibility map allows.

Check with:
```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT total_cents, status FROM orders WHERE user_id = 123;
-- Index Only Scan using orders_user_idx
```

## Index maintenance reality

- **`CREATE INDEX CONCURRENTLY`** — no write lock; use in prod
- **Duplicate indexes** — `(a)` and `(a,b)` where `(a,b)` covers `(a)` queries — drop redundant
- **Unused indexes** — `pg_stat_user_indexes.idx_scan = 0` over 30 days → candidate drop
- **Bloat** — `REINDEX INDEX CONCURRENTLY` during low traffic

```sql
SELECT indexrelname, idx_scan, pg_size_pretty(pg_relation_size(indexrelid))
FROM pg_stat_user_indexes
WHERE scidx_scan = 0 AND schemaname = 'public'
ORDER BY pg_relation_size(indexrelid) DESC;
```

## EXPLAIN-driven workflow

1. Run query with `EXPLAIN (ANALYZE, BUFFERS)`
2. Sequential scan on large table? — candidate index
3. Index scan but high heap fetches? — consider INCLUDE
4. Wrong index type? — switch GIN/B-tree
5. Index used but slow? — correlation, bloat, or statistics — `ANALYZE`, increase `default_statistics_target`

Don't index low-cardinality columns alone (`status` with 3 values) unless partial index narrows heavily.

## Index review cadence

Quarterly index audit: unused indexes drop, duplicate indexes merge, missing indexes from pg_stat_statements top queries add. Automate report generation; human approves drops — blind automation drops indexes used by monthly reporting jobs.

## Operational notes

Use `pg_stat_progress_create_index` during large `CREATE INDEX CONCURRENTLY` operations in prod — progress visibility prevents premature cancellation of long builds that were actually advancing.

Schedule REINDEX CONCURRENTLY for indexes exceeding bloat threshold from pgstattuple sampling — proactive maintenance beats emergency rebuild during peak traffic.

When dropping unused indexes, capture `pg_stat_user_indexes` snapshot just before drop for audit — teams occasionally drop indexes used by monthly batch jobs not visible in OLTP stats window.

Review foreign key indexes on child tables during schema review — Postgres does not auto-index FK columns; missing indexes slow cascades and joins dramatically at scale.

Use `hypopg` or `EXPLAIN` hypothetical indexes in staging before creating heavy production indexes — estimates wrong less often than guesswork from slow query text alone.

## Index type selection

| Query pattern | Index |
|---------------|-------|
| `=`, `<`, `>` on scalar | B-tree |
| `@>`, `?`, JSONB containment | GIN |
| Full text search | GIN (tsvector) |
| UUID primary key | B-tree (default) |
| Low cardinality boolean | Partial index, not standalone |

`CREATE INDEX CONCURRENTLY` in production — non-concurrent blocks writes.


## B-tree vs GIN decision tree

Equality and range on scalar columns use B-tree. JSONB containment, full-text, array overlap use GIN. GiST for geometric/exclusion. Wrong index type — planner may ignore index entirely.

## Partial indexes for hot subsets

CREATE INDEX ON orders (created_at) WHERE status = pending — smaller index, faster writes, matches queue worker query exactly.

## Covering indexes with INCLUDE

Index on user_id, created_at DESC INCLUDE total_cents, status — index-only scan for list endpoint. INCLUDE columns not searchable.

## Multi-column order matters

tenant_id, created_at supports WHERE tenant_id ORDER BY created_at; reversed order does not. Leading column should be most selective equality filter.

## Index bloat monitoring

pg_stat_user_indexes idx_scan vs idx_tup_fetch — zero scans for months suggests unused index candidate for drop. High idx_tup_read with low idx_scan indicates inefficient index — wrong column order or stale stats.

## Concurrent index build operations

CREATE INDEX CONCURRENTLY cannot run inside transaction block — migration tools must support non-transactional DDL. Failed CONCURRENTLY leaves INVALID index — REINDEX CONCURRENTLY or DROP and retry. Monitor pg_stat_progress_create_index during large table build.

## BRIN for append-only time series

BRIN on created_at for append-only logs — tiny index size, effective for time-range queries on terabyte tables if physical order correlates with time. Not substitute for B-tree on UUID primary key random inserts — correlation missing, BRIN useless.

## Hash indexes limited use case

Postgres hash indexes WAL-logged since PG10 but still no range scans — equality only. Rare use; B-tree equality competes fine. Hash cannot unique enforce in older versions — prefer B-tree unique.

## Index-only scan prerequisites

Include all SELECT columns in index or satisfy visibility map all-visible page — VACUUM lag prevents index-only scan until heap all-visible. Heavy UPDATE table may never benefit — consider covering index tradeoff vs heap fetch cost measured in EXPLAIN BUFFERS.

## Duplicate index detection

pg_stat_user_indexes plus pg_indexes query finds indexes on (a,b) and (a) subset redundancy — drop narrower duplicate after verifying query plans use composite only. Savings on write path significant on high INSERT tables.

## Index recommendation workflow

pg_qualstats or hypopg extension suggests indexes from qualification usage — human reviews before CREATE INDEX CONCURRENTLY. Auto-index bots dangerous on write-heavy tables — always check INSERT rate and existing index count before adding fourth index on same table.

## Closing notes

REINDEX CONCURRENTLY schedule for GIN indexes on jsonb after bulk import season — bloat from gin pending list slows containment queries until merge completes.

## Additional guidance

Drop unused indexes discovered via pg_stat_user_indexes idx_scan zero over thirty days — each index slows INSERT and UPDATE on hot OLTP paths. Schedule DROP INDEX CONCURRENTLY after confirming no monthly report job uses index via pg_stat_statements plan samples referencing index name in bitmap scan nodes.

Concurrent index creation on production requires lock_timeout set in migration session — failed CONCURRENTLY leaving INVALID index blocks retry until DROP INDEX CONCURRENTLY cleanup; migration tool idempotency checks pg_index.indisvalid before CREATE to prevent duplicate invalid index objects cluttering catalog.

Review pg_stat_user_indexes quarterly with service owners — drop zero-scan indexes after confirming no monthly batch job dependency.

## Resources

- [PostgreSQL index types documentation](https://www.postgresql.org/docs/current/indexes-types.html)
- [PostgreSQL partial indexes](https://www.postgresql.org/docs/current/indexes-partial.html)
- [PostgreSQL index-only scans](https://www.postgresql.org/docs/current/indexes-index-only-scans.html)
- [Use The Index, Luke — PostgreSQL chapter](https://use-the-index-luke.com/sql/postgresql)
- [PostgreSQL BRIN indexes](https://www.postgresql.org/docs/current/brin.html)
