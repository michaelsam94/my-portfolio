---
title: "Postgres Generated Columns and Indexing"
slug: "postgres-generated-columns-indexing"
description: "Design STORED and VIRTUAL generated columns in Postgres 18+, index them for query performance, and avoid redundant computation in application code."
datePublished: "2026-02-16"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
keywords: "Postgres generated column, stored generated column, computed column index, expression index"
faq:
  - q: "STORED vs VIRTUAL generated columns?"
    a: "STORED columns are computed on write and occupy disk — indexable like normal columns. VIRTUAL (Postgres 18+) compute on read — save space but cannot be indexed directly; use expression indexes on the same formula."
  - q: "Should I use generated columns or expression indexes?"
    a: "Generated columns when the value appears in SELECT lists and multiple indexes/queries reuse it. Expression indexes when only one query pattern needs the derivation."
  - q: "Do generated columns work with logical replication?"
    a: "STORED generated columns replicate as regular columns on subscribers Postgres 12+. Verify subscriber version compatibility before relying on them in CDC pipelines."
---

## Normalize once, query many times

Teams duplicate `lower(email)` in every query and wonder why functional indexes multiply. A **generated column** `email_normalized` keeps derivation centralized and index-friendly:


```sql
ALTER TABLE users
  ADD COLUMN email_normalized text
  GENERATED ALWAYS AS (lower(trim(email))) STORED;

CREATE UNIQUE INDEX users_email_norm_idx
  ON users (email_normalized)
  WHERE deleted_at IS NULL;
```

## JSON extraction without repeated operators

Extract hot JSONB keys into generated columns when filters sort or join on them frequently. Pair with partial indexes on the generated column rather than GIN on the full document when cardinality is low.

## Migration strategy

Adding a STORED column rewrites the table — plan `ACCESS EXCLUSIVE` window or use expand-contract: add nullable column, backfill in batches, attach generated definition in maintenance window, then add index `CONCURRENTLY`.


## Immutable expression requirement

Generated column expressions must be immutable — now() forbidden in STORED generated. Use triggers for time-dependent derivations; generated columns for deterministic transforms.

## VIRTUAL columns in Postgres 18+

VIRTUAL saves disk on wide tables where derived value queried rarely. When query pattern stabilizes, promote to STORED plus index.

## ORM visibility

Prisma and some ORMs omit generated columns from insert — integration test insert without generated field. Sequelize defaultValue patterns may conflict.

## Index-only scans

STORED generated column indexed enables index-only scan when SELECT lists only indexed columns. EXPLAIN ANALYZE BUFFERS confirms heap fetches mean vacuum lag.

## Case study: email normalization

Before generated column: three functional indexes on lower(trim(email)) from different teams. After: one STORED email_normalized column, one partial unique index. Insert path 15% faster from single computation, query plans simpler in EXPLAIN output.

## When not to use generated columns

Volatile expressions, cross-row dependencies, or values computed from external API — use materialized view refreshed on schedule instead. Generated columns excel at row-local deterministic transforms.

## Full worked example: order total cents

```sql
ALTER TABLE order_lines
  ADD COLUMN line_total_cents bigint
  GENERATED ALWAYS AS (quantity * unit_price_cents) STORED;

CREATE INDEX order_lines_order_total_idx
  ON order_lines (order_id, line_total_cents);
```

Reporting SUM(line_total_cents) GROUP BY order_id uses index-only scan when visibility map current — verify with EXPLAIN ANALYZE BUFFERS after bulk load + VACUUM.

## Expression index alternative comparison

Same query plan often from `CREATE INDEX ON order_lines ((quantity * unit_price_cents))` without stored column — less disk, recomputes on every index scan entry. Choose STORED when column displayed in UI lists; expression index when filter-only.

## Replication and generated columns

Logical replication replicates STORED values as plain columns — subscriber need not define GENERATED unless transforms differ. Verify subscriber schema version matches before cutover in blue-green database migration.

## Computed columns in migrations

Adding GENERATED STORED to 50M row table rewrites heap — schedule maintenance window or use pg_repack strategy. Safer expand-contract: add nullable regular column, backfill in batches with UPDATE, attach GENERATED in low-traffic window, drop old column.

## Check constraints on generated values

```sql
ALTER TABLE products ADD COLUMN price_cents_display text
  GENERATED ALWAYS AS (to_char(price_cents/100.0, 'FM999.99')) STORED;
```

Display-only generated column indexed for admin search by formatted price — rare but avoids formatting in every SELECT.

## Pitfalls with logical replication

Publisher sends STORED generated values; subscriber table must include column definitions matching or omit generated and receive plain values. Schema drift during replication upgrade breaks apply worker — verify with pg_dump schema diff before major PG upgrade.

## Domain-specific examples beyond email

**SKU normalization:** `GENERATED ALWAYS AS (upper(replace(sku, '-', ''))) STORED` — index supports lookup regardless of client formatting.

**Full name search:** `GENERATED ALWAYS AS (lower(first_name || ' ' || last_name)) STORED` — single index for admin people search instead of concatenating in every query.

**Extracted currency code from jsonb:** when 80% of queries filter `metadata->>'currency'`, promote to STORED generated column then B-tree index — GIN on full jsonb unnecessary.

## Testing generated column migrations

Snapshot EXPLAIN plans before and after on top ten queries touching table — unexpected seq scan after migration signals missing index on new column. Rollback migration drops generated column; ensure no application SELECT * depending on column order in drivers that expose generated unexpectedly to ORM.

## Generated column and UPDATE amplification

Updating base column recomputes STORED generated — write amplification on wide table if generated expression expensive (regex, json parse). Benchmark UPDATE on representative row width; consider VIRTUAL if reads rare or expression index if filter-only.

## Compatibility with pg_dump

pg_dump includes generated column definitions — restore to older PG without generated support fails. Target version in restore checklist must match feature usage; document minimum Postgres version in service README next to pooling mode.

## When application layer still computes

If derived value needed only in one rare admin export, computed column in SELECT sufficient without STORED — avoid disk for unused derivation. Generated columns win when same expression in WHERE, ORDER BY, and SELECT list repeatedly — DRY at storage layer.

## Legal/compliance generated flags

`GENERATED ALWAYS AS (CASE WHEN birth_date < current_date - interval '18 years' THEN true ELSE false END) STORED` — index is_adult for age-gated content queries. current_date makes column volatile in strict reading — use trigger instead if immutable required; document immutability rules with legal before shipping.

## Partitioning and generated columns

Partition key must appear in PK; generated column cannot be partition key unless STORED and deterministic. Range partition on created_at with generated year column for archive queries — verify Postgres version supports generated in partition key expression (often use date_trunc in partition definition instead).

## Read replica lag and generated columns

Replicas compute STORED generated on apply same as primary — no drift. Logical replication publishes stored value; subscriber need not recompute if column list matches — simplifies blue-green cutover when generated columns backfilled on primary first.

## ORM select omission

TypeORM @Column insert false update false on generated property — Prisma @default(dbgenerated()) read-only. Failing to mark read-only causes ORM sending NULL violating GENERATED ALWAYS constraint on INSERT — integration test catches on first create.

## Summary decision matrix

| Need | Prefer |
|------|--------|
| Same expr in WHERE + SELECT often | STORED generated + index |
| Filter only one query | Expression index |
| Volatile/time-dependent | Trigger maintained column |
| Rarely read derived value | Compute in SELECT |

Revisit matrix when query volume doubles — VIRTUAL column promotion to STORED justified when pg_stat_statements shows repeated computation cost exceeding disk price.

## Closing notes

Review generated column expressions in migration PR for immutability and volatility — legal-age flags using current_date belong in triggers; normalization expressions belong in STORED generated columns indexed for lookup.

## Additional guidance

When migrating from application-computed column to STORED generated, deploy expand-contract: stop writing app column, backfill generated, switch reads, drop old column. Zero-downtime requires dual-write phase only if generated cannot attach online — measure table size before choosing maintenance window versus pg_repack online rewrite strategy for ten-million-row tables common in user profile normalization migrations.

Extended case study: marketplace normalizes seller slug for URL uniqueness using GENERATED ALWAYS AS (lower(regexp_replace(slug_raw, '[^a-z0-9-]', '', 'g'))) STORED with unique index. Migration added column using ADD COLUMN then UPDATE backfill in ten-million-row batches over weekend because PG version predated fast ADD GENERATED on huge table. Post-migration query plans show index scan on slug_normalized replacing sequential scan on lower(slug_raw) functional index dropped after cutover. Application removed duplicate normalization helpers in three services — single source in database prevented divergent slug rules causing SEO duplicate content when mobile app used different strip regex than web backend before generated column centralized logic.

Operational monitoring: pg_stat_user_tables n_tup_upd increase on seller row edit reflects generated column rewrite cost — acceptable for low-frequency seller profile updates; would reject generated approach for per-second metric counter updates where expression index or plain column maintained by trigger batching preferred.

## Resources

- [PostgreSQL documentation](https://www.postgresql.org/docs/)
- [Microservices patterns](https://microservices.io/patterns/)
- [OpenTelemetry docs](https://opentelemetry.io/docs/)
- [12-Factor App](https://12factor.net/)
