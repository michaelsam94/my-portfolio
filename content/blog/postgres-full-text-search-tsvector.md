---
title: "Full-Text Search in Postgres"
slug: "postgres-full-text-search-tsvector"
description: "Build full-text search with PostgreSQL tsvector and tsquery: GIN indexes, ranking, phrase search, and when FTS beats Elasticsearch for your workload."
datePublished: "2026-03-13"
dateModified: "2026-03-13"
tags: ["PostgreSQL", "Backend", "Search", "Database"]
keywords: "PostgreSQL full text search, tsvector tsquery, GIN index Postgres, pg_trgm search, Postgres FTS ranking"
faq:
  - q: "When is Postgres full-text search enough instead of Elasticsearch?"
    a: "When you search under 10–50 million documents, need ACID consistency with your data, want simple deployment, and can accept basic relevance tuning. Postgres FTS handles product catalogs, support ticket search, and admin panels well. Elasticsearch wins on complex aggregations, fuzzy scale, and advanced analyzers."
  - q: "What is the difference between tsvector and tsquery?"
    a: "tsvector is the indexed document — normalized lexemes with optional weights. tsquery is the search expression with operators (AND, OR, NOT, phrase). You match with tsvector @@ tsquery and rank with ts_rank or ts_rank_cd."
  - q: "Should I use GIN or GiST indexes for FTS?"
    a: "GIN is the default choice — faster lookups, slower updates. GiST suits frequently updated tsvectors with moderate read volume. Most apps use GIN on a generated tsvector column."
---

We almost spun up Elasticsearch for ticket search — 200k rows, three text fields, "find tickets mentioning refund and shipping." Postgres already held the data. `tsvector`, a GIN index, and `ts_rank` shipped in two days. Elasticsearch would have been a third system to secure, backup, and keep in sync. Postgres FTS isn't Google — it's good enough for a lot of internal and mid-scale product search.

## Core types: tsvector and tsquery

```sql
SELECT to_tsvector('english', 'The quick brown fox jumps over the lazy dog');
-- 'brown':3 'dog':9 'fox':4 'jump':5 'lazi':8 'quick':2

SELECT to_tsquery('english', 'refund & ship');
-- 'refund' & 'ship'

SELECT to_tsvector('english', 'Customer wants refund on shipping') @@ to_tsquery('english', 'refund & ship');
-- true (ship matches shipping stem)
```

`english` config stems words (`shipping` → `ship`). Choose config per column language or use `simple` for codes/SKUs without stemming.

## Schema pattern

```sql
ALTER TABLE articles ADD COLUMN search_vector tsvector
  GENERATED ALWAYS AS (
    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(body, '')), 'B')
  ) STORED;

CREATE INDEX articles_search_idx ON articles USING GIN (search_vector);
```

Generated column keeps tsvector synced on write — no trigger maintenance.

Weights: A (title) ranks higher than B (body) in `ts_rank`.

## Querying with ranking

```sql
SELECT id, title,
       ts_rank_cd(search_vector, query) AS rank
FROM articles, plainto_tsquery('english', 'postgresql indexing') query
WHERE search_vector @@ query
ORDER BY rank DESC
LIMIT 20;
```

`plainto_tsquery` converts user input to AND query — safer than raw `to_tsquery` (handles user punctuation).

Phrase search:

```sql
SELECT * FROM articles
WHERE search_vector @@ phraseto_tsquery('english', 'connection pooling');
```

Highlighting snippets:

```sql
SELECT ts_headline('english', body, query) AS snippet
FROM articles, plainto_tsquery('english', 'advisory lock') query
WHERE search_vector @@ query;
```

## Prefix and autocomplete

`to_tsquery('english', 'conn:*')` matches lexemes starting with `conn`. Combine with `pg_trgm` for fuzzy SKU search:

```sql
CREATE EXTENSION pg_trgm;
CREATE INDEX products_name_trgm ON products USING GIN (name gin_trgm_ops);

SELECT * FROM products WHERE name % 'iphnoe' ORDER BY similarity(name, 'iphnoe') DESC;
-- typo-tolerant; separate from FTS
```

Use FTS for word relevance; trigrams for fuzzy string match.

## Performance at scale

- **GIN index** on tsvector — mandatory above 100k rows
- **`LIMIT` early** — don't rank full table; filter `@@` first (index used)
- **Partition large tables** by date if searching recent data primarily
- **Vacuum** — GIN indexes bloat on heavy updates; monitor `pg_stat_user_indexes`

Benchmark: 2M rows, GIN index, typical query 5–20ms on db.r6g.large. Beyond 50M or sub-10ms at high QPS, evaluate OpenSearch.

## Sync with application search APIs

```python
def search_articles(q: str, limit: int = 20) -> list[Article]:
    return db.execute(
        """
        SELECT id, title, ts_rank_cd(search_vector, query) AS rank
        FROM articles, plainto_tsquery('english', %s) query
        WHERE search_vector @@ query
        ORDER BY rank DESC LIMIT %s
        """,
        (q, limit),
    ).fetchall()
```

Sanitize input length; cap query complexity. `plainto_tsquery` rejects malformed input gracefully.

## When to migrate to Elasticsearch

- Faceted navigation with 20+ aggregations per query
- Sub-second search across 100M+ documents
- Complex analyzers (CJK tokenization, phonetic)
- Decoupled search team scaling independently

Hybrid works: Postgres FTS for admin/internal; Elasticsearch for customer-facing catalog sync via CDC.

## Multi-language search

Use `simple` config for SKU codes mixed with English prose — stemming can mangle part numbers. For true multilingual content, consider `to_tsvector` with language detection per row or separate tsvector columns per language with query routing.

## Operational notes

Refresh tsvector generated columns after bulk imports with `UPDATE articles SET title = title` trick or explicit recompute — generated columns update on row rewrite; verify index reflects imported content before opening search to users.

Benchmark search relevance with human-labeled query set before launch — ts_rank tuning without relevance judgments optimizes the wrong metric.

Combine FTS with pagination using keyset on ranked ID — OFFSET through search results degrades as page number increases because rank must be computed for skipped rows first.

Expose search syntax help in UI — power users benefit from phrase quotes and minus operators; casual users need plain language search box without tsquery syntax exposure.

Reindex GIN indexes after major bulk loads if search recall drops — bloat in GIN posting trees affects result completeness before autovacuum catches up on very large tables.

## Common production mistakes

Teams get full text search tsvector wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Postgres work on full text search tsvector causes outages when migrations run without `lock_timeout`, connection pools are sized for app servers not PgBouncer modes, and `EXPLAIN` plans from staging are assumed to match production statistics.

## Debugging and triage workflow

When full text search tsvector misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [PostgreSQL full text search documentation](https://www.postgresql.org/docs/current/textsearch.html)
- [PostgreSQL GIN indexes](https://www.postgresql.org/docs/current/gin.html)
- [pg_trgm extension](https://www.postgresql.org/docs/current/pgtrgm.html)
- [Postgres FTS tutorial (Crunchy Data)](https://www.crunchydata.com/blog/postgres-full-text-search-a-search-engine-in-your-database)
- [Elasticsearch vs Postgres FTS comparison (ParadeDB)](https://www.paradedb.com/blog/postgres-vs-elasticsearch)
