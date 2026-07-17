---
title: "Full-Text Search in Postgres"
slug: "postgres-full-text-search-tsvector"
description: "Build full-text search with PostgreSQL tsvector and tsquery: GIN indexes, ranking, phrase search, and when FTS beats Elasticsearch for your workload."
datePublished: "2026-03-13"
dateModified: "2026-07-17"
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


## tsvector column vs generated

Maintained tsvector updated by trigger vs GENERATED ALWAYS AS to_tsvector STORED. Generated simplifies schema; triggers allow custom weighting per field (title weight A, body weight D).

## Ranking with ts_rank_cd

ts_rank_cd covers density — prefer over ts_rank for longer documents. Combine with published_at DESC for recency boost in hybrid score.

## GIN index maintenance

GIN indexes bloat with heavy updates — monitor pg_stat_user_indexes. Autovacuum must keep pace; bulk reindex CONCURRENTLY if search latency drifts.

## Language configuration

Multilingual content needs per-row regconfig or separate columns per language. Single english config stemmes French poorly — detect language at ingest.

## Highlighting search results

ts_headline generates snippet with match markers for UI:

```sql
SELECT id, ts_headline('english', body, query) AS snippet
FROM articles, plainto_tsquery('english', $1) query
WHERE search_vector @@ query;
```

Configure MaxWords and MinWords to control snippet length in mobile results list.

## Synonym dictionaries

Install custom thesaurus for product names ("laptop" ↔ "notebook") via CREATE TEXT SEARCH CONFIGURATION — reduces zero-result searches without OR-exploding query manually in application code.

## Updating tsvector on row change

Trigger maintains search_vector on INSERT/UPDATE:

```sql
CREATE TRIGGER tsvector_update BEFORE INSERT OR UPDATE ON articles
FOR EACH ROW EXECUTE FUNCTION
  tsvector_update_trigger(search_vector, 'pg_catalog.english', title, body);
```

Generated STORED column alternative in PG12+ reduces trigger boilerplate — choose based on team familiarity.

## phraseto_tsquery vs plainto_tsquery

User quoted phrase search uses phraseto_tsquery for proximity — "machine learning" as phrase not OR of tokens. plainto_tsquery ANDs words — better for single-word and casual search box. Expose mode in API query param; wrong choice frustrates power users.

## Weighing title over body

Setweight on tsvector components: setweight(to_tsvector(title), 'A') || setweight(to_tsvector(body), 'D') — rank boosts title matches. Maintain in trigger or generated expression; document weight scheme for relevance tuning QA.

## Limiting search result explosion

SET pg_trgm similarity threshold or ts_rank cutoff in query HAVING ts_rank > 0.05 — prevents low-relevance flood on common terms. Pagination with stable ORDER BY rank, id tiebreaker avoids duplicate/missing pages when rows updated during user scroll.

## Accent-insensitive search

unaccent extension paired with tsvector — GENERATED column to_tsvector('unaccent', lower(title)) STORED for user-facing search expecting café matching cafe. Extension install in all envs including CI; missing unaccent fails search deploy on staging only classic bug.

## Closing notes

Search analytics log zero-result queries weekly — add synonym or adjust weighting when product terms mismatch document vocabulary; tsvector tuning driven by real failed searches not engineer guesswork.

## Additional guidance

Combine tsvector with trigram index on title for typo tolerance when product requires fuzzy brand search — two indexes maintained on write, query uses OR of tsvector match and similarity threshold with rank merge in application layer documented in search architecture note.

Reindex search GIN CONCURRENTLY after bulk catalog import before marketing launch — pending gin entries slow search below SLO during peak traffic when import finished hours before campaign start; runbook step often missed because functional tests pass on small staging catalog.

Schedule REINDEX CONCURRENTLY on search GIN before large marketing catalog push — pending-list latency otherwise violates search SLO opening day.

Log zero-result searches to analytics weekly — product adds synonyms when brand names mismatch document vocabulary causing empty SERP on internal catalog search.

## Resources

- [PostgreSQL full text search documentation](https://www.postgresql.org/docs/current/textsearch.html)
- [PostgreSQL GIN indexes](https://www.postgresql.org/docs/current/gin.html)
- [pg_trgm extension](https://www.postgresql.org/docs/current/pgtrgm.html)
- [Postgres FTS tutorial (Crunchy Data)](https://www.crunchydata.com/blog/postgres-full-text-search-a-search-engine-in-your-database)
- [Elasticsearch vs Postgres FTS comparison (ParadeDB)](https://www.paradedb.com/blog/postgres-vs-elasticsearch)
