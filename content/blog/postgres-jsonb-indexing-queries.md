---
title: "Indexing and Querying JSONB"
slug: "postgres-jsonb-indexing-queries"
description: "Query and index JSONB in PostgreSQL efficiently: operators, GIN indexes, jsonpath, expression indexes, and schema design for semi-structured data."
datePublished: "2026-03-19"
dateModified: "2026-07-17"
tags: ["PostgreSQL", "Backend", "Database", "JSON"]
keywords: "PostgreSQL JSONB indexing, jsonb_path_ops GIN, JSONB query operators, jsonpath Postgres, JSONB performance"
faq:
  - q: "Should I store data as JSONB or normalized columns?"
    a: "Normalize fields you filter, sort, or join on frequently. JSONB suits optional attributes, event payloads, schema-flexible config, and data shaped by external APIs. Hybrid works best — core columns typed, extensions in JSONB."
  - q: "Which GIN operator class should I use for JSONB?"
    a: "jsonb_path_ops for containment queries (@>) — smaller, faster. jsonb_ops supports key existence (?), ?&, ?| operators in addition to @>. Match operator class to your query patterns or create multiple indexes."
  - q: "How do I index a specific JSONB key?"
    a: "Expression index on extracted value: CREATE INDEX ON events ((payload->>'user_id')). For nested paths use jsonb_path or -> chain. Partial index if only some rows have the key."
---

Event sourcing lite: one `events` table, `payload JSONB`, ship it. Six months later, `WHERE payload->>'user_id' = '123'` scans 40 million rows. JSONB is flexible until it isn't — without the right index and operator, you're doing full table scans on opaque blobs.

## JSONB operators you'll use

| Operator | Meaning | Example |
|----------|---------|---------|
| `->` | Get JSON object field | `payload->'user'` |
| `->>` | Get as text | `payload->>'user_id'` |
| `@>` | Contains | `payload @> '{"type":"click"}'` |
| `?` | Key exists | `payload ? 'email'` |
| `#>>` | Path as text | `payload#>>'{user,id}'` |

```sql
SELECT * FROM events
WHERE payload @> '{"type": "purchase", "status": "completed"}';

SELECT * FROM events
WHERE payload->>'user_id' = '550e8400-e29b-41d4-a716-446655440000';
```

`@>` containment uses GIN efficiently. `->>` equality needs expression index unless wrapped in generated column.

## GIN indexes for containment

```sql
CREATE INDEX events_payload_gin ON events USING GIN (payload jsonb_path_ops);
-- Supports: payload @> '{"type": "click"}'
```

Broader operator support:

```sql
CREATE INDEX events_payload_ops ON events USING GIN (payload jsonb_ops);
-- Supports: @>, ?, ?&, ?|, @?
```

`jsonb_path_ops` index is ~30% smaller for `@>`-only workloads — prefer it when you don't need `?` key existence.

## Expression indexes for scalar lookups

```sql
CREATE INDEX events_user_id_idx ON events ((payload->>'user_id'))
WHERE payload ? 'user_id';
```

Partial `WHERE` excludes rows missing key — smaller index for sparse fields.

Generated column (Postgres 12+):

```sql
ALTER TABLE events ADD COLUMN user_id UUID
  GENERATED ALWAYS AS ((payload->>'user_id')::uuid) STORED;

CREATE INDEX events_user_id_btree ON events (user_id);
```

Queryable like normal column; stays synced on insert/update.

## JSONPath queries (Postgres 12+)

```sql
SELECT * FROM events
WHERE jsonb_path_exists(payload, '$.items[*].price ? (@.double() > 100)');

SELECT jsonb_path_query_first(payload, '$.metadata.source') FROM events;
```

Complex paths may not use GIN — test EXPLAIN. `@?` and `@@` operators can use GIN with jsonb_ops in some cases.

## Schema design patterns

**Envelope + typed core:**
```sql
CREATE TABLE orders (
  id UUID PRIMARY KEY,
  customer_id UUID NOT NULL,
  total_cents INT NOT NULL,
  metadata JSONB DEFAULT '{}'
);
CREATE INDEX ON orders (customer_id);
CREATE INDEX ON orders USING GIN (metadata jsonb_path_ops);
```

**Category column for partition pruning:**
```sql
CREATE TABLE events (
  id BIGSERIAL PRIMARY KEY,
  category TEXT NOT NULL,  -- 'click', 'purchase'
  payload JSONB NOT NULL
);
CREATE INDEX ON events (category, id DESC);
-- Filter category first, then JSONB
```

Don't store searchable fields only inside JSONB if every query extracts them — promote to columns.

## Update and bloat considerations

JSONB updates rewrite entire JSON value if any key changes — TOAST compression helps but hot keys on wide documents cause bloat.

Split frequently updated keys to columns; keep stable blob in JSONB.

`jsonb_strip_nulls` on insert reduces size if API sends null-heavy payloads.

## Anti-patterns

- No index on filter path used in every query
- `@>` with dynamic key order — `{"a":1,"b":2}` ≠ `{"b":2,"a":1}` for containment; normalize JSON key order on write or use consistent construction
- Storing large base64 blobs in JSONB — use bytea or object storage
- `SELECT *` on wide JSONB — extract needed keys

## Migration from JSONB-only to hybrid schema

When JSONB queries dominate slow-query logs, promote hot keys incrementally without a big-bang rewrite:

1. Add nullable generated column for the hottest key
2. Backfill in batches during low traffic
3. Create B-tree index on generated column
4. Update application to filter on column first, JSONB second
5. After one release, make column NOT NULL if business rules require it

This pattern shipped a search feature from 800ms p95 to 40ms on a 30M-row events table — same data model externally, different physical layout internally. Track promotion candidates by logging slow-query keys from pg_stat_statements normalized on JSON path.

## jsonb_strip_nulls and storage

Strip null keys on ingest if upstream API sends sparse objects — smaller JSONB storage, faster comparisons. For write-heavy JSONB, monitor TOAST behavior; consider extracting only search fields to columns while keeping full blob for archival.

## Operational notes

For API responses returning full JSONB documents, separate read replica for analytics queries on JSONB containment — OLTP write path stays isolated from analyst exploration queries.

Version JSON schema documents alongside API — when payload shape changes, index and query paths update in same PR reducing drift between documented and indexed fields.

## JSONB GIN index

```sql
CREATE INDEX idx_data_gin ON documents USING GIN (data jsonb_path_ops);
SELECT * FROM documents WHERE data @> '{"status": "active"}';
```

`jsonb_path_ops` smaller index than default jsonb_ops — use when queries are containment-only.


## GIN default vs jsonb_path_ops

Default GIN supports containment and key existence. jsonb_path_ops smaller index, faster containment, loses key-existence operators. Choose path_ops when queries always containment on full path.

## Expression index on nested key

Hot path filters data status — index data->>'status' B-tree often beats full document GIN when single key high cardinality.

## jsonb aggregation pitfalls

jsonb_agg in subquery without LIMIT explodes memory — same as row explosion in JOIN. Prefer lateral join with jsonb_build_object.

## TOAST and wide jsonb

Large jsonb offloaded TOAST — updates to one key rewrite whole TOAST chunk. Normalize frequently updated fields to columns.

## @> containment operator patterns

Query `data @> '{"status":"active"}'::jsonb` uses GIN efficiently. Negation `@>` with NOT requires careful planning — often seq scan. Prefer status as generated column with B-tree when filtering active/inactive on every request.

## jsonb_set for partial updates

Updating nested key rewrites whole jsonb row — TOAST churn on wide documents. Hot nested field → promote to column; jsonb_set for rare admin metadata only.

## jsonb_path_ops operator class

CREATE INDEX ON docs USING gin (data jsonb_path_ops) — supports @> containment only. Index size 30-40% smaller than default jsonb_ops in benchmarks on nested documents — choose when query patterns fixed.

## Sequential keys inside jsonb

Monotonic id inside jsonb array appends cause HOT update failure — wide jsonb row rewrite each append. Normalize array to child table when array grows unbounded (comment threads, audit log in jsonb anti-pattern).

## jsonb_array_elements in WHERE

Unnested array search without GIN on array path often seq scans — normalize to junction table when array membership queried routinely (tag lists, category ids). jsonb OK for admin-only rare queries, not product hot path.

## Statistics on jsonb paths

CREATE STATISTICS ON (data) FROM table for whole jsonb document — planner estimates containment selectivity better on correlated keys inside same document. ANALYZE after statistics creation; EXPLAIN rows estimate improves for @> queries on skewed jsonb payloads.

## Closing notes

Document jsonb schema version in column comment — application migrates keys over time; partial index on data->>'schema_version' = '2' keeps hot path fast while legacy rows age out.

## Additional guidance

Validate jsonb index usage in CI EXPLAIN test for top three jsonb filter queries — fails PR when plan switches to seq scan after statistics change. Keeps jsonb_path_ops index from being dropped accidentally when developer assumes GIN unused because local dataset too small to trigger index scan in dev environment testing.

jsonb_strip_nulls on ingest reduces index size when optional keys omitted frequently — smaller GIN index fits memory, improves cache hit rate for containment queries on product catalog documents with sparse optional attribute keys varying by category vertical in same collection table.

Promote frequently filtered jsonb keys to generated STORED columns when EXPLAIN shows repeated jsonb_path_ops index scan on same path.

CI EXPLAIN test on three hottest jsonb queries catches planner regression when statistics drift after bulk import — fails PR before merge not after marketing launch.

When jsonb document width exceeds eight kilobytes TOAST threshold, promote hot filter keys to typed columns — write amplification on partial key update rewrites entire TOAST chunk slowing checkout catalog updates during flash inventory sync jobs.

## Resources

- [PostgreSQL JSON types documentation](https://www.postgresql.org/docs/current/datatype-json.html)
- [PostgreSQL JSON functions](https://www.postgresql.org/docs/current/functions-json.html)
- [JSONB indexing docs](https://www.postgresql.org/docs/current/datatype-json.html#JSON-INDEXING)
- [PostgreSQL jsonpath](https://www.postgresql.org/docs/current/functions-json.html#FUNCTIONS-SQLJSON-PATH)
- [Crunchy Data JSONB tips](https://www.crunchydata.com/blog/jsonb-type-performance-in-postgresql)
