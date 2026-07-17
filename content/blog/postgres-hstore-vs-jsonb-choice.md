---
title: "Postgres hstore vs jsonb Choice"
slug: "postgres-hstore-vs-jsonb-choice"
description: "Compare hstore and jsonb for semi-structured data — schema flexibility, indexing, query syntax, and migration paths."
datePublished: "2026-02-23"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
keywords: "hstore vs jsonb, postgres semi-structured data, key value storage, gin index jsonb, hstore extension"
faq:
  - q: "Can hstore store nested objects like jsonb?"
    a: "No. hstore is a flat key-value map with string keys and string values only. jsonb supports nested objects, arrays, numbers, booleans, and null. If your data has hierarchy — addresses with nested fields, arrays of tags — jsonb is the correct choice."
  - q: "Which type indexes better for key lookups?"
    a: "Both support GIN indexes. hstore GIN indexes excel at key existence and key-value equality queries. jsonb GIN with jsonb_path_ops or default ops handles key existence, containment (@>), and path queries. jsonb is more flexible; hstore is slightly more compact for flat string maps."
  - q: "Is hstore still maintained for new projects?"
    a: "hstore predates jsonb and remains supported but receives no new features. New projects should default to jsonb unless they specifically need hstore's text-only flat map with slightly smaller storage for simple key-value pairs and existing hstore-heavy codebases."
---

Applications inevitably accumulate fields that do not deserve dedicated columns — user preferences, product attributes varying by category, metadata tags. Postgres offers two native types for semi-structured data: **hstore** (key-value pairs, text only) and **jsonb** (binary JSON with rich types). Both avoid schema migrations for every new attribute. They differ in type support, query ergonomics, indexing, and which one your team will still want to maintain in five years.

## Type fundamentals

**hstore** — flat map of string → string:

```sql
CREATE EXTENSION hstore;

SELECT 'name=>Alice, role=>admin, tier=>pro'::hstore;
-- "name"=>"Alice", "role"=>"admin", "tier"=>"pro"

SELECT hstore 'name' AS val FROM ...;
-- Returns 'Alice' (text)
```

**jsonb** — binary JSON with native types:

```sql
SELECT '{"name": "Alice", "role": "admin", "score": 42, "tags": ["a","b"]}'::jsonb;

SELECT data->>'name' FROM profiles;   -- text extraction
SELECT data->'tags'->1 FROM profiles; -- array element
SELECT (data->>'score')::int FROM profiles; -- typed numeric
```

| Feature | hstore | jsonb |
| --- | --- | --- |
| Value types | Text only | String, number, boolean, null, array, object |
| Nesting | Flat only | Unlimited nesting |
| Key uniqueness | Enforced (duplicate keys rejected) | Last key wins on duplicate |
| Order preservation | No key order | Object key order not guaranteed (jsonb normalizes) |
| Storage | Compact for flat maps | Larger overhead, especially small objects |
| Standard format | Postgres-specific | JSON standard — interoperable |

## Query syntax comparison

Flat attribute lookup:

```sql
-- hstore
SELECT * FROM products WHERE attrs -> 'color' = 'red';
SELECT * FROM products WHERE attrs @> 'color=>red';

-- jsonb
SELECT * FROM products WHERE attrs->>'color' = 'red';
SELECT * FROM products WHERE attrs @> '{"color": "red"}';
```

Multiple key conditions:

```sql
-- hstore
SELECT * FROM products WHERE attrs @> 'color=>red,size=>large';

-- jsonb
SELECT * FROM products WHERE attrs @> '{"color": "red", "size": "large"}';
```

Key existence:

```sql
-- hstore
SELECT * FROM products WHERE attrs ? 'color';

-- jsonb
SELECT * FROM products WHERE attrs ? 'color';
SELECT * FROM products WHERE attrs ?| array['color', 'size'];  -- any key
SELECT * FROM products WHERE attrs ?& array['color', 'size'];  -- all keys
```

Nested data — jsonb only:

```sql
SELECT * FROM orders
WHERE metadata @> '{"shipping": {"country": "DE"}}';

SELECT * FROM orders
WHERE metadata #>> '{shipping,postal_code}' LIKE '10%';
```

hstore cannot represent this without serializing nested structures as escaped strings — an anti-pattern.

## Indexing strategies

**hstore GIN index**:

```sql
CREATE INDEX products_attrs_gin ON products USING gin (attrs);
-- Supports: @>, ?, ?&, ?|
```

**jsonb GIN index** (default ops):

```sql
CREATE INDEX products_data_gin ON products USING gin (data);
-- Supports: @>, ?, ?|, ?&, @?, @@ (jsonpath PG 12+)
```

**jsonb path ops** (smaller index, containment only):

```sql
CREATE INDEX products_data_path ON products USING gin (data jsonb_path_ops);
-- Supports: @> only — smaller index, faster containment
```

**Expression indexes** for specific keys:

```sql
CREATE INDEX products_color ON products ((attrs->>'color'));  -- jsonb
CREATE INDEX products_color ON products ((attrs -> 'color')); -- hstore
```

For high-cardinality key lookups on a known key, expression B-tree indexes outperform GIN for equality.

## Storage and performance benchmarks

hstore stores keys and values as text without JSON parsing overhead. For a flat map of 10–20 string attributes per row across millions of rows, hstore can be 10–30% smaller than equivalent jsonb.

jsonb parsing cost on insert/update is higher — binary conversion normalizes key order and whitespace. For write-heavy attribute updates, hstore updates individual keys without rewriting the entire document (similar to jsonb partial update with `||`):

```sql
-- hstore: merge keys
UPDATE products SET attrs = attrs || 'color=>blue' WHERE id = 1;

-- jsonb: merge keys
UPDATE products SET data = data || '{"color": "blue"}' WHERE id = 1;
```

At typical OLTP scale, the performance difference is rarely the deciding factor — query patterns and type needs dominate.

## Schema evolution patterns

**EAV (Entity-Attribute-Value) alternative**: Both types avoid the join-heavy EAV pattern:

```sql
-- EAV anti-pattern
SELECT v.value FROM entity_values v JOIN attributes a ON ... WHERE entity_id = 1 AND a.name = 'color';

-- hstore/jsonb
SELECT attrs->>'color' FROM products WHERE id = 1;
```

**Partial schema + overflow column**:

```sql
CREATE TABLE products (
  id          serial PRIMARY KEY,
  name        text NOT NULL,
  price       numeric NOT NULL,
  category    text NOT NULL,
  extra_attrs jsonb DEFAULT '{}'  -- category-specific overflow
);
```

Fixed columns for query-critical fields; jsonb for variable attributes. Index expression on `extra_attrs->>'warranty_months'` only if queried.

## Migration from hstore to jsonb

Existing hstore column conversion:

```sql
ALTER TABLE products
  ALTER COLUMN attrs TYPE jsonb
  USING hstore_to_json_loose(attrs);
```

`hstore_to_json_loose` converts values to JSON types where possible (numbers, booleans, null).

Reverse (rare):

```sql
ALTER TABLE products
  ALTER COLUMN data TYPE hstore
  USING jsonb_each_text(data)::hstore;  -- loses nesting
```

Application code migration: replace `->` hstore operators with jsonb `->>`/`->`, update containment syntax.

## When to choose hstore

- Flat string-only metadata (HTTP headers, env vars, simple tags)
- Existing codebase already on hstore with working GIN indexes
- Storage size critical at billions of rows with simple maps
- No nested structure now or ever

## When to choose jsonb

- Nested objects or arrays
- Numeric or boolean values without string casting
- JSON API interchange — data arrives and departs as JSON
- jsonpath queries (PG 12+): `@@` operator
- New projects (default choice)
- Partial document updates with typed values

## Combining both (don't)

Avoid tables with both hstore and jsonb columns for the same conceptual data. Pick one. Mixed models confuse ORMs and query planners.

## ORM support

**Rails**: `store_accessor` works with hstore and jsonb columns. jsonb preferred in modern Rails.

**SQLAlchemy**: JSON type maps to jsonb. hstore requires dialect-specific type.

**Prisma**: jsonb via `Json` type. No hstore support.

## Validation and constraints

jsonb schema validation (PG extension or application-level):

```sql
-- CHECK constraint for required keys
ALTER TABLE products ADD CONSTRAINT data_has_name
  CHECK (data ? 'name');

-- pg_jsonschema extension (if available)
CHECK (jsonb_matches_schema('{"type":"object","required":["name"]}', data))
```

hstore validation:

```sql
ALTER TABLE products ADD CONSTRAINT attrs_has_color
  CHECK (attrs ? 'color');
```

Neither enforces value types in hstore — `'price'=>'not-a-number'` is valid. jsonb stores typed values; application or CHECK with casting enforces types.

## Real-world decision example

Product catalog with category-specific attributes:

```
Electronics: warranty_months (int), voltage (int)
Clothing: size (string), material (string)
```

jsonb wins — numeric warranty without casting, nested variant arrays for SKUs. hstore would store `'warranty_months'=>'24'` as text requiring cast on every numeric comparison.

User preference bag (theme, locale, notifications_on):

```
hstore viable: flat, string-only, small
jsonb also fine: boolean notifications_on without 'true'/'false' strings
```

Default to jsonb even here for boolean typing.

## Performance testing methodology

Before committing to hstore or jsonb for a high-volume table, benchmark with representative data:

```sql
-- Generate 1M rows with comparable payloads
INSERT INTO bench_hstore SELECT i, ('key' || (i % 100)) => 'value' || i FROM generate_series(1,1000000) i;
INSERT INTO bench_jsonb SELECT i, jsonb_build_object('key' || (i % 100), 'value' || i) FROM generate_series(1,1000000) i;

-- Compare equality lookup
EXPLAIN ANALYZE SELECT * FROM bench_hstore WHERE attrs -> 'key50' = 'value50';
EXPLAIN ANALYZE SELECT * FROM bench_jsonb WHERE data->>'key50' = 'value50';

-- Compare storage
SELECT pg_size_pretty(pg_total_relation_size('bench_hstore'));
SELECT pg_size_pretty(pg_total_relation_size('bench_jsonb'));
```

Run on staging hardware matching production. Storage differences matter at tens of millions of rows; at thousands, choose based on developer ergonomics and type requirements instead.

Document the benchmark results in your ADR (Architecture Decision Record) so future engineers understand why hstore or jsonb was chosen — these decisions are frequently re-litigated during code review without written context.

## Summary

hstore is a flat string key-value map — compact and simple for truly flat metadata. jsonb is the modern default for semi-structured Postgres data: nested documents, typed values, JSON interoperability, and richer indexing including jsonpath. New projects should choose jsonb unless hstore's specific flat-text compactness is measured and necessary. Migrate legacy hstore with `hstore_to_json_loose`, index based on actual query patterns, and keep query-critical fields in typed columns rather than buried in either format.


For greenfield columns prefer jsonb; migrate legacy hstore with hstore_to_jsonb, dual-write, and a concurrent GIN rebuild sized for I/O.
