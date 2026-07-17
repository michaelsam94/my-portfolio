---
title: "Postgres pgvector Hybrid Search"
slug: "postgres-pgvector-hybrid-search"
description: "Combine pgvector semantic search with full-text ranking using reciprocal rank fusion, weighted scores, and indexes that stay maintainable."
datePublished: "2026-02-27"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
  - "Search"
keywords: "pgvector, hybrid search, reciprocal rank fusion, full text search, semantic search postgres"
faq:
  - q: "Why combine vector search with full-text search instead of vectors alone?"
    a: "Embeddings excel at semantic similarity but miss exact tokens, SKUs, legal citations, and rare proper nouns. Full-text search handles lexical matches, prefixes, and weighted fields. Hybrid merges both rank lists so users get recall from semantics and precision from keywords."
  - q: "What is reciprocal rank fusion (RRF) and why use it over weighted score addition?"
    a: "RRF combines ranked lists by summing 1/(k + rank) per document across retrievers, with k typically 60. It avoids normalizing incompatible scores—cosine distance vs ts_rank_cd—which weighted addition gets wrong when score distributions differ by query."
  - q: "Which indexes do I need for hybrid search at scale?"
    a: "HNSW or IVFFlat on the embedding column for approximate nearest neighbor; GIN on tsvector for lexical search. Keep embedding dimension fixed per model; rebuild HNSW after bulk loads. Partial indexes help when filtering by tenant_id or published=true."
  - q: "Does hybrid search work inside a single SQL query?"
    a: "Yes. Common pattern: two CTEs (vector top-K and FTS top-K), FULL OUTER JOIN on primary key, compute RRF, ORDER BY fused score LIMIT K. For very large corpora, retrieve candidates separately in application code then fuse—same math, easier caching."
---

Search that only embeds user queries feels magical until someone searches `CVE-2024-1234` and gets semantically related blog posts instead of the advisory. Pure full-text search fails the opposite way: "how do I reduce cloud spend" returns nothing when docs say "FinOps cost optimization."

Hybrid search in Postgres—**pgvector for semantics**, **`tsvector` for lexemes**, **fusion for ranking**—keeps one database, one transaction boundary, and one replication stream. You do not need Elasticsearch for every product catalog if you understand how to merge rank lists without naive score addition.

## Schema foundation

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
  id           bigserial PRIMARY KEY,
  tenant_id    int NOT NULL,
  title        text NOT NULL,
  body         text NOT NULL,
  embedding    vector(1536),
  search_vector tsvector GENERATED ALWAYS AS (
    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(body, '')), 'B')
  ) STORED,
  published    boolean NOT NULL DEFAULT true
);

CREATE INDEX documents_embedding_hnsw ON documents
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

CREATE INDEX documents_search_gin ON documents USING gin (search_vector);
```

**Model choice locks dimension:** migration means re-embed everything. Store `embedding_model` column if you anticipate upgrades.

**HNSW vs IVFFlat:** HNSW defaults in pgvector 0.5+ for better recall/latency tradeoff.

## Two retrievers, one query

```sql
WITH vector_hits AS (
  SELECT id,
         ROW_NUMBER() OVER (ORDER BY embedding <=> $1) AS v_rank
  FROM documents
  WHERE tenant_id = $2 AND published
  ORDER BY embedding <=> $1
  LIMIT 50
),
text_hits AS (
  SELECT id,
         ROW_NUMBER() OVER (
           ORDER BY ts_rank_cd(search_vector, websearch_to_tsquery('english', $3)) DESC
         ) AS t_rank
  FROM documents
  WHERE tenant_id = $2 AND published
    AND search_vector @@ websearch_to_tsquery('english', $3)
  LIMIT 50
),
fused AS (
  SELECT COALESCE(v.id, t.id) AS id,
         COALESCE(1.0 / (60 + v.v_rank), 0) +
         COALESCE(1.0 / (60 + t.t_rank), 0) AS rrf_score
  FROM vector_hits v
  FULL OUTER JOIN text_hits t ON v.id = t.id
)
SELECT d.id, d.title, f.rrf_score
FROM fused f
JOIN documents d ON d.id = f.id
ORDER BY f.rrf_score DESC
LIMIT 20;
```

**Why RRF:** Vector scores and `ts_rank_cd` are incompatible for weighted addition. RRF only needs ranks—robust across retrievers.

Tune **k** (often 60): higher k dampens rank differences. A/B test click-through, not offline cosine alone.

## Weighted fusion and field boosts

Product sometimes demands boosting title matches—handle via FTS weights (`setweight` A/B/C) before fusion, not double-counted in vector leg.

If you must combine normalized scores within one query, normalize within the candidate set (top 50 each)—still fragile across queries; prefer RRF.

## Candidate pool sizing and HNSW tuning

Fetching top 50 from each leg then fusing to 20 is standard. Too small pools lose hybrid benefit; too large adds latency.

```sql
SET hnsw.ef_search = 100;  -- default 40; higher = better recall, slower
```

Benchmark with `EXPLAIN (ANALYZE, BUFFERS)` on production-sized data.

## Filters and multi-tenant isolation

Apply **same predicates** in both CTEs: `tenant_id`, `published`, date ranges. Asymmetric filters cause fusion to rank documents that fail business rules.

For RLS-heavy schemas, run hybrid query as security invoker so both legs respect policies.

## Embedding pipeline and staleness

On insert/update, queue embed job. Write `embedding` when API returns; FTS updates synchronously via generated column. Search returns rows with NULL embedding from text leg only until embed completes.

Bulk re-embed on model change: background job with shadow column, rebuild HNSW during maintenance window.

## Evaluation methodology

Offline: labeled query set, nDCG@10, MRR, recall@50 per leg and hybrid. Slice by query type: SKU lookup, conceptual question, name search.

Online: click-through rate, zero-result rate. Log which leg contributed winning documents.

## Performance pitfalls

| Issue | Symptom | Fix |
| --- | --- | --- |
| Sequential scan on embedding | Slow ANN | Verify HNSW index used |
| GIN index ignored | FTS slow | Stale statistics; ANALYZE |
| Over-fetch columns | High IO | SELECT id only in CTEs |
| Cold cache | First query slow | Warm cache or accept |

## Caching and query plan stability

Pin statistics on `search_vector` and embedding column after baseline ANALYZE. Application-level caching of fused top-20 by query hash with short TTL cuts repeated embed API costs.

## Security: embedding injection

Sanitize length limits before `websearch_to_tsquery`. Treat embed API keys as secrets; never log raw query vectors.

## When hybrid in Postgres is enough

Stay on Postgres when corpus fits one node with acceptable HNSW memory and P95 latency target met with proper indexes. Move out when you need distributed sharding across many nodes or sub-millisecond at millions QPS with heavy faceting.



## Score normalization pitfalls in production

Teams often try **`0.7 * (1 - distance) + 0.3 * ts_rank`** because product asked for "70% semantic." The weights interact with query length, document length, and idf in **`ts_rank_cd`**—a query that works in staging fails in production when stopword distribution shifts. If product insists on weights, build a calibration set of 200 real queries with human relevance labels, grid-search weights offline, and still keep RRF as fallback when normalized scores disagree with click data.

## Multilingual and stemming interactions

Hybrid search on mixed-language corpora needs consistent **`regconfig`** per row or per tenant. Embedding models may be multilingual while **`to_tsvector('english', ...)`** strips diacritics differently than the embedder. Store **`content_language`** and choose **`regconfig`** in generated column expression. Hybrid fusion runs per language bucket when tenant locales diverge—never fuse ranks across incompatible FTS configs.

## Refresh strategies after bulk document import

Bulk import without embedding blocks vector leg until embed queue drains—text leg still works. Schedule **`ANALYZE`** after import; HNSW quality depends on representative build data. For IVFFlat, **`lists`** parameter ties to **`sqrt(rowcount)`** rule of thumb; rebuild index after import completes rather than incremental insert into empty index during load. Monitor **`pg_stat_progress_create_index`** during HNSW builds—multi-hour builds on production need maintenance windows or build on replica then swap.

## Degradation modes under embed API outage

When embed API fails, fall back to FTS-only query path with explicit **`degraded: true`** flag in API response so UI can badge results. Cache query embeddings briefly (15s) for repeat pagination requests—do not cache across tenants. Circuit-break embed calls after error rate threshold; Postgres FTS leg unaffected.



## Production rollout checklist for hybrid search

Ship hybrid search only after you validate embedding model version in config matches stored vectors, run EXPLAIN on both CTE legs under tenant filter load, and load-test fused query at 2x expected QPS. Add metrics for vector-leg-only hits, text-leg-only hits, and both-leg hits per query id—skew indicates tuning opportunity. Roll out behind feature flag per tenant; compare zero-result rate week over week before global enable.

## Replica lag and search freshness

Hybrid queries on read replicas see stale embeddings if replication lag exceeds embed pipeline latency—text leg may reference updated title while vector leg still old body embedding. Route search to primary when lag > SLA or accept brief inconsistency documented in product. Logical decoding embed workers on primary avoid replica staleness for index population at cost of primary CPU.


## Vector index rebuild communication

Communicate multi-hour HNSW rebuild windows to product—search quality may fluctuate during build. Use CONCURRENTLY where supported for indexes; vectors may require maintenance mode. Snapshot embed model version in index comment for on-call debugging.



## Hybrid ranking observability

Emit structured logs per search: query_hash, vector_pool_size, text_pool_size, fused_count, top_id, vector_rank_of_top, text_rank_of_top. Dashboards slice zero-result rate by tenant and query class. Alert when vector_leg_empty_rate spikes—embed pipeline outage or index invalid.

## pgvector version upgrades

Major pgvector upgrades occasionally change distance operator behavior or index build defaults—re-run offline nDCG suite after extension upgrade before promoting. Pin extension version in migration comments alongside embed model version.

## Resources

- [pgvector documentation](https://github.com/pgvector/pgvector)
- [PostgreSQL full text search](https://www.postgresql.org/docs/current/textsearch.html)
- [Reciprocal rank fusion (Cormack et al.)](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf)
