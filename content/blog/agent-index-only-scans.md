---
title: "AI Agents: Index Only Scans"
slug: "agent-index-only-scans"
description: "PostgreSQL index-only scans for agent retrieval workloads — covering indexes, visibility map tuning, EXPLAIN analysis, and schema choices that keep RAG metadata queries off the heap."
datePublished: "2024-11-29"
dateModified: "2024-11-29"
tags: ["AI", "Agent", "Index"]
keywords: "index-only scan, PostgreSQL, covering index, visibility map, RAG metadata, agent retrieval, query optimization, INCLUDE index"
faq:
  - q: "When does PostgreSQL choose an index-only scan?"
    a: "The planner picks Index Only Scan when all columns in the query are present in the index leaf pages and the visibility map confirms heap pages are all-visible — meaning PostgreSQL can answer the query from the index alone without checking row versions on the heap. Partial coverage or stale visibility maps force Index Scan with heap fetches."
  - q: "Why do index-only scans matter for agent RAG pipelines?"
    a: "Agent systems run high-volume metadata filters — tenant_id, document status, embedding model version, chunk timestamps — before vector search or reranking. Index-only scans cut I/O on these narrow lookups, freeing buffer cache for pgvector HNSW traversals and keeping ingestion workers from contending on heap pages."
  - q: "How do I design a covering index for agent document tables?"
    a: "Lead with equality filters (tenant_id, status), then range columns (updated_at), and INCLUDE columns you SELECT but do not filter on (id, content_hash, source_uri). Match column order to your most common WHERE clauses. Avoid over-wide indexes that slow writes during sync ingestion."
  - q: "Why does EXPLAIN show 'Heap Fetches' on an index-only scan?"
    a: "Heap Fetches means some index entries pointed at heap pages not marked all-visible in the visibility map — usually after recent UPDATEs/DELETEs before VACUUM runs. Increase autovacuum aggressiveness on hot agent tables or accept occasional heap fetches until vacuum catches up."
---
The agent retrieval service logged p95 metadata latency at 180 ms — odd, because the query was a simple tenant filter returning document IDs before a vector lookup. `EXPLAIN (ANALYZE, BUFFERS)` showed an Index Scan reading every matching heap page for a table with forty million chunk rows. The fix was not more RAM. It was a covering index that let PostgreSQL serve the filter as an Index Only Scan, dropping p95 to 12 ms and freeing shared buffers for the pgvector leg of the pipeline.

Index-only scans are one of the highest-leverage PostgreSQL optimizations for agent stacks, yet they rarely appear in RAG architecture diagrams. Teams obsess over embedding models and HNSW parameters while metadata queries — tenant scoping, freshness filters, soft-delete tombstones, model-version gates — quietly dominate buffer cache and connection time.

## What an index-only scan actually does

A standard Index Scan walks the B-tree, finds matching entries, then **fetches each heap tuple** to read columns not in the index and to verify the row is visible to your transaction (MVCC).

An Index Only Scan still walks the B-tree, but if **every required column lives in the index** and the **visibility map** says the heap page is all-visible, PostgreSQL skips the heap fetch entirely. The index leaf pages become a covering store for that query shape.

```
Query: SELECT id, content_hash FROM documents
       WHERE tenant_id = $1 AND status = 'active'
       AND updated_at > $2
       ORDER BY updated_at DESC LIMIT 100;

Without covering index:
  Index Scan → heap fetch per row → filter → sort

With covering index on (tenant_id, status, updated_at DESC)
  INCLUDE (id, content_hash):
  Index Only Scan → results (no heap)
```

The visibility map is a bitmap per heap page marking whether all tuples on the page are visible to all transactions. After bulk ingestion or heavy updates, pages are not all-visible until autovacuum runs — you get Index Only Scan in the plan but non-zero **Heap Fetches** in `EXPLAIN ANALYZE`.

## Agent workloads that benefit most

Agent pipelines hit PostgreSQL differently from OLTP checkout flows.

**Pre-filter before vector search.** You resolve candidate document IDs by tenant, ACL tags, and freshness before calling pgvector or an external ANN service. These filters are repetitive, narrow, and often cover a small column set — ideal for covering indexes.

**Sync ingestion lookups.** Incremental sync upserts by `(tenant_id, external_id)` and checks `content_hash`. Unique indexes with included columns support index-only existence checks.

**Admin and eval queries.** Offline eval jobs scan "all active documents for tenant X updated since Y" — batch reads that amplify heap I/O without covering indexes.

**Chunk metadata joins.** Multi-table joins between `documents` and `chunks` on `(document_id, chunk_index)` explode buffer reads when only the index could serve the driving filter.

Vector indexes solve similarity. Index-only scans solve **everything around similarity** — and that surrounding work often sets your end-to-end retrieval ceiling.

## Designing covering indexes for agent schemas

Start from real query text in logs, not hypothetical ORM output. For each hot query, list:

1. Equality filters (most selective first)
2. Range filters
3. Columns in SELECT / JOIN keys not used in WHERE
4. ORDER BY columns

Example agent document table:

```sql
CREATE TABLE agent_documents (
  id              UUID PRIMARY KEY,
  tenant_id       UUID NOT NULL,
  external_id     TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'active',
  content_hash    TEXT NOT NULL,
  embedding_model TEXT NOT NULL DEFAULT 'text-embedding-3-small',
  updated_at      TIMESTAMPTZ NOT NULL,
  deleted_at      TIMESTAMPTZ
);

-- Hot path: tenant-scoped active docs by freshness
CREATE INDEX agent_docs_tenant_fresh_idx
  ON agent_documents (tenant_id, status, updated_at DESC)
  INCLUDE (id, content_hash, embedding_model)
  WHERE deleted_at IS NULL;

-- Hot path: sync upsert lookup
CREATE UNIQUE INDEX agent_docs_tenant_external_uidx
  ON agent_documents (tenant_id, external_id)
  INCLUDE (content_hash, status, updated_at);
```

Partial indexes (`WHERE deleted_at IS NULL`) shrink index size and improve cache hit rate when soft deletes are common in knowledge bases.

Avoid indexing every column "just in case." Each index slows ingestion — and agent sync workers are write-heavy during business hours.

## Reading EXPLAIN output like an agent SRE

```sql
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT id, content_hash, embedding_model
FROM agent_documents
WHERE tenant_id = '11111111-1111-1111-1111-111111111111'
  AND status = 'active'
  AND updated_at > now() - interval '24 hours'
ORDER BY updated_at DESC
LIMIT 200;
```

What to look for:

| Signal | Healthy | Investigate |
|--------|---------|-------------|
| Node type | `Index Only Scan` | `Seq Scan` on large tables |
| Heap Fetches | 0 or low vs rows | Heap Fetches ≈ rows returned |
| Buffers: shared hit | High hit ratio | Mostly reads — cache too small |
| Actual rows vs Estimate | Within ~2× | Bad stats — run ANALYZE |
| Sort node present | Avoid on large sets | Index column order mismatch |

Enable `track_io_timing` and log queries exceeding retrieval SLO. Correlate with `pg_stat_user_indexes` to find indexes that exist but never scan — dead weight during ingestion.

## Visibility map and vacuum strategy

Index-only scans degrade after bulk updates — exactly what sync pipelines do.

```sql
-- Check heap fetch pressure
SELECT relname, idx_scan, idx_tup_fetch, idx_tup_read
FROM pg_stat_user_indexes
WHERE schemaname = 'public' AND relname LIKE 'agent_%';

-- Per-table vacuum stats
SELECT relname, n_live_tup, n_dead_tup, last_autovacuum, last_autoanalyze
FROM pg_stat_user_tables
WHERE relname = 'agent_documents';
```

Tuning for hot agent tables:

```sql
ALTER TABLE agent_documents SET (
  autovacuum_vacuum_scale_factor = 0.02,
  autovacuum_analyze_scale_factor = 0.01,
  fillfactor = 90
);
```

Lower scale factors trigger vacuum sooner after ingestion bursts, restoring all-visible bits faster. `fillfactor = 90` leaves headroom for HOT updates on metadata columns without new heap pages — though content_hash changes from sync will still create new row versions.

For massive one-time backfills, consider loading into a staging table, building indexes once, then swapping — rather than polluting the visibility map on the live table during peak agent traffic.

## Interaction with pgvector and connection pooling

Agent retrieval often runs two queries in sequence: metadata filter in PostgreSQL, then vector query via `<=>` operator on `chunks.embedding`.

Index-only scans on the metadata leg reduce:

- Time holding pooled connections (PgBouncer transaction mode timeouts)
- Shared buffer eviction before the vector leg runs
- CPU spent on heap visibility checks competing with HNSW graph traversal

If the metadata query returns ten thousand IDs that feed a vector query, you have a design problem no index type fixes — push more filtering into SQL or precompute allowed document sets. Index-only scans optimize **when the filtered set is small relative to corpus size**.

## Common mistakes in agent PostgreSQL schemas

**Leading column mismatch.** Index on `(status, tenant_id)` but every query filters `tenant_id` first — planner may skip the index or scan inefficiently.

**Over-wide INCLUDE lists.** Including `body` or large JSON blobs in indexes bloats pages and defeats cache efficiency. Keep covering columns narrow; fetch heavy payloads by primary key only for the final result set.

**Ignoring statistics on skewed tenants.** One enterprise tenant with 80% of rows makes global statistics lie. Use extended statistics or partition by `tenant_id` for mega-tenants.

**UUID v4 primary keys in clustered order.** Random UUID inserts fragment indexes. For append-heavy chunk tables, consider `bigint` sequences or time-ordered IDs for better sequential scan locality — index-only scans still help, but ingestion becomes cheaper overall.

## Partitioning and index-only scans at scale

When agent document counts exceed comfortable single-table vacuum windows, declarative partitioning by `tenant_id` hash or `created_at` month keeps visibility maps manageable.

Each partition carries its own indexes. A query with `tenant_id` equality prunes partitions before index-only scans run — compounding the benefit.

Tradeoff: cross-partition admin queries get harder. Agent retrieval almost always scopes by tenant, so pruning aligns with product access patterns.

## Testing index changes safely

Never build production indexes blindly during peak hours.

```sql
-- Production-safe concurrent build
CREATE INDEX CONCURRENTLY agent_docs_tenant_fresh_idx_v2
  ON agent_documents (tenant_id, status, updated_at DESC)
  INCLUDE (id, content_hash, embedding_model)
  WHERE deleted_at IS NULL;
```

Workflow:

1. Capture baseline `EXPLAIN ANALYZE` and p95 from staging with production-shaped row counts.
2. Build index concurrently on staging; re-run explain — confirm Index Only Scan, measure Heap Fetches after simulated sync burst + vacuum.
3. Deploy during low traffic; use `pg_stat_statements` to verify plan flip.
4. Drop superseded indexes only after a week of metrics — ingestion write latency should be monitored.

Load tests should include concurrent sync workers updating `content_hash` while retrieval runs — this is when Heap Fetches spike if vacuum lag is ignored.

## Operational runbook

Symptoms: metadata filter latency regression after deploy or sync spike.

1. Run `EXPLAIN ANALYZE` on top queries from `pg_stat_statements`.
2. If Index Only Scan with high Heap Fetches → check `n_dead_tup`, force `VACUUM (ANALYZE)` if justified.
3. If Index Scan or Seq Scan → missing or mismatched index; verify partial index predicates match query filters (`deleted_at IS NULL`).
4. If estimates wildly off → `ANALYZE` or increase `default_statistics_target` on skewed columns.
5. Post-incident: add ingestion/vacuum dashboard panel alongside retrieval SLO.

## Closing

Index-only scans are not an exotic DBA feature — they are the difference between metadata filters that disappear in the background and filters that starve your agent retrieval path of I/O budget. For PostgreSQL-backed agent systems, design covering indexes from logged query shapes, keep visibility maps healthy with autovacuum tuned for sync write patterns, and verify plans with `EXPLAIN ANALYZE` under load — not just on empty staging tables.

## Resources

- [PostgreSQL documentation: Index-Only Scans and Covering Indexes](https://www.postgresql.org/docs/current/indexes-index-only-scans.html)
- [PostgreSQL: Visibility Map and VACUUM](https://www.postgresql.org/docs/current/routine-vacuuming.html)
- [pgvector: Indexing and performance notes](https://github.com/pgvector/pgvector#indexing)
- [Use The Index, Luke! — Covering indexes explained](https://use-the-index-luke.com/sql/partial-index/covering-index)
- [pg_stat_statements and query planning workflow](https://www.postgresql.org/docs/current/pgstatstatements.html)
