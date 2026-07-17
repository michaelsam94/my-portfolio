---
title: "Vector Search in Postgres with pgvector"
slug: "vector-db-pgvector-postgres"
description: "Add vector search to Postgres with pgvector: installation, index types, similarity operators, hybrid queries, and when pgvector replaces a dedicated vector database."
datePublished: "2026-02-27"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "pgvector, Postgres vector search, HNSW, IVFFlat, embedding, similarity search, hybrid search"
faq:
  - q: "What is the main production risk with vector db pgvector postgres?"
    a: "Teams ship without field measurement—vector db pgvector postgres failures appear as silent UX regressions, cost drift, or audit findings rather than clear errors."
  - q: "When should we prioritize vector db pgvector postgres?"
    a: "Prioritize when user research, CrUX, support tickets, or compliance requirements show pain on critical paths—not when a checklist mentions it abstractly."
  - q: "How do we validate vector db pgvector postgres changes?"
    a: "Baseline RUM before changes, compare p75 after deploy, and keep rollback via feature flags or cache purge documented in the PR."
---

title: "Vector Search in Postgres with pgvector"
slug: "vector-db-pgvector-postgres"
description: "Add vector search to Postgres with pgvector: installation, index types, similarity operators, hybrid queries, and when pgvector replaces a dedicated vector database."
datePublished: "2026-02-27"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "pgvector, Postgres vector search, HNSW, IVFFlat, embedding, similarity search, hybrid search"
faq:
  - q: "What is the main production risk with vector db pgvector postgres?"
    a: "Teams ship without field measurement—vector db pgvector postgres failures appear as silent UX regressions, cost drift, or audit findings rather than clear errors."
  - q: "When should we prioritize vector db pgvector postgres?"
    a: "Prioritize when user research, CrUX, support tickets, or compliance requirements show pain on critical paths—not when a checklist mentions it abstractly."
  - q: "How do we validate vector db pgvector postgres changes?"
    a: "Baseline RUM before changes, compare p75 after deploy, and keep rollback via feature flags or cache purge documented in the PR."
---
---

title: "vector-db-pgvector-postgres"
slug: "vector-db-pgvector-postgres"
description: ""
datePublished: "2026-07-17"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "vector-db-pgvector-postgres"
faq:
  - q: "What is the main production risk with vector db pgvector postgres?"
    a: "Teams ship without field measurement—vector db pgvector postgres failures appear as silent UX regressions, cost drift, or audit findings rather than clear errors."
  - q: "When should we prioritize vector db pgvector postgres?"
    a: "Prioritize when user research, CrUX, support tickets, or compliance requirements show pain on critical paths—not when a checklist mentions it abstractly."
  - q: "How do we validate vector db pgvector postgres changes?"
    a: "Baseline RUM before changes, compare p75 after deploy, and keep rollback via feature flags or cache purge documented in the PR."
---
---

title: "vector-db-pgvector-postgres"
slug: "vector-db-pgvector-postgres"
description: ""
datePublished: "2026-07-17"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "vector-db-pgvector-postgres"
faq:
  - q: "What is the main production risk with vector db pgvector postgres?"
    a: "Teams ship without field measurement—vector db pgvector postgres failures appear as silent UX regressions, cost drift, or audit findings rather than clear errors."
  - q: "When should we prioritize vector db pgvector postgres?"
    a: "Prioritize when user research, CrUX, support tickets, or compliance requirements show pain on critical paths—not when a checklist mentions it abstractly."
  - q: "How do we validate vector db pgvector postgres changes?"
    a: "Baseline RUM before changes, compare p75 after deploy, and keep rollback via feature flags or cache purge documented in the PR."
---
---

title: "vector-db-pgvector-postgres"
slug: "vector-db-pgvector-postgres"
description: ""
datePublished: "2026-07-17"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "vector-db-pgvector-postgres"
faq:
  - q: "What is the main production risk with vector db pgvector postgres?"
    a: "Teams ship without field measurement—vector db pgvector postgres failures appear as silent UX regressions, cost drift, or audit findings rather than clear errors."
  - q: "When should we prioritize vector db pgvector postgres?"
    a: "Prioritize when user research, CrUX, support tickets, or compliance requirements show pain on critical paths—not when a checklist mentions it abstractly."
  - q: "How do we validate vector db pgvector postgres changes?"
    a: "Baseline RUM before changes, compare p75 after deploy, and keep rollback via feature flags or cache purge documented in the PR."
---
---

title: "Vector Search in Postgres with pgvector"
slug: "vector-db-pgvector-postgres"
description: "Add vector search to Postgres with pgvector: installation, index types, similarity operators, hybrid queries, and when pgvector replaces a dedicated vector database."
datePublished: "2026-02-27"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "pgvector, Postgres vector search, HNSW, IVFFlat, embedding, similarity search, hybrid search"
faq:
  - q: "What is the main production risk with vector db pgvector postgres?"
    a: "Teams ship without field measurement—vector db pgvector postgres failures appear as silent UX regressions, cost drift, or audit findings rather than clear errors."
  - q: "When should we prioritize vector db pgvector postgres?"
    a: "Prioritize when user research, CrUX, support tickets, or compliance requirements show pain on critical paths—not when a checklist mentions it abstractly."
  - q: "How do we validate vector db pgvector postgres changes?"
    a: "Baseline RUM before changes, compare p75 after deploy, and keep rollback via feature flags or cache purge documented in the PR."
---
---

The team wanted vector search for a RAG feature and evaluated Pinecone, Weaviate, and Qdrant. Then someone asked: "Can we just use our Postgres?" We had 800,000 document chunks, already ran Postgres 16 with replication, and every query needed to join embeddings with document metadata, user permissions, and audit timestamps. Adding pgvector took an afternoon. Operating a second database would have taken a quarter. For our scale and query patterns, pgvector wasn't a compromise — it was the right tool.

## Setup

```sql
CREATE EXTENSION vector;

CREATE TABLE documents (
    id         BIGSERIAL PRIMARY KEY,
    content    TEXT NOT NULL,
    embedding  vector(1536),  -- OpenAI text-embedding-3-small dimension
    tenant_id  TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

The `vector(n)` type stores a fixed-dimension float array. pgvector validates dimension on insert.

## Inserting embeddings

```python
import psycopg2
from pgvector.psycopg2 import register_vector

conn = psycopg2.connect(DATABASE_URL)
register_vector(conn)

embedding = openai.embeddings.create(
    input="document text", model="text-embedding-3-small"
).data[0].embedding

with conn.cursor() as cur:
    cur.execute(
        "INSERT INTO documents (content, embedding, tenant_id) VALUES (%s, %v, %s)",
        ("document text", embedding, "acme")
    )
```

The `pgvector` Python package registers the vector type adapter for psycopg2, asyncpg, and SQLAlchemy.

## Similarity search

pgvector supports three distance operators:

| Operator | Distance | Use for |
|---|---|---|
| `<->` | L2 (Euclidean) | General similarity |
| `<#>` | Negative inner product | Normalized vectors |
| `<=>` | Cosine distance | Text embeddings (most common) |

```sql
SELECT id, content, embedding <=> $1 AS distance
FROM documents
WHERE tenant_id = 'acme'
ORDER BY embedding <=> $1
LIMIT 10;
```

Cosine distance (`<=>`) is the standard choice for text embeddings. Pass the query embedding as `$1`.

## Indexing for performance

Without an index, every query is a sequential scan — fine for thousands of rows, unusable for millions.

### HNSW (recommended)

```sql
CREATE INDEX ON documents
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

HNSW builds a multi-layer graph for approximate nearest neighbor search. Key parameters:
- `m` — connections per node (16 is a good default, higher = better recall, more memory)
- `ef_construction` — build-time search depth (64 default, higher = better index quality, slower build)

Set search-time recall with `ef_search`:

```sql
SET hnsw.ef_search = 100;  -- default 40, higher = better recall
```

### IVFFlat (memory-constrained alternative)

```sql
CREATE INDEX ON documents
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Must run after sufficient data exists
-- lists = sqrt(row_count) is a common starting point
```

IVFFlat partitions vectors into clusters. Queries search only the nearest clusters. Requires enough data at index creation time for meaningful clusters.

## Hybrid queries: the pgvector advantage

The killer feature is SQL — vector similarity plus relational filters in one query:

```sql
SELECT d.id, d.content, d.embedding <=> $1 AS distance
FROM documents d
JOIN users u ON d.author_id = u.id
WHERE d.tenant_id = $2
  AND d.created_at > now() - INTERVAL '30 days'
  AND u.role IN ('editor', 'admin')
  AND d.embedding <=> $1 < 0.3
ORDER BY distance
LIMIT 10;
```

Try doing this in Pinecone. You'd retrieve vectors, then make a second query to Postgres for permissions, then merge in application code. With pgvector, it's one query, one round trip, and the planner optimizes both the btree filters and the vector index scan.

## Full-text + vector hybrid search

Combine `tsvector` with vector search for keyword + semantic retrieval:

```sql
WITH vector_results AS (
    SELECT id, content, embedding <=> $1 AS vscore
    FROM documents
    WHERE tenant_id = $2
    ORDER BY vscore LIMIT 50
),
text_results AS (
    SELECT id, content, ts_rank(search_vector, plainto_tsquery('english', $3)) AS tscore
    FROM documents
    WHERE tenant_id = $2
      AND search_vector @@ plainto_tsquery('english', $3)
    ORDER BY tscore DESC LIMIT 50
)
SELECT COALESCE(v.id, t.id) AS id,
       COALESCE(v.content, t.content) AS content,
       COALESCE(1 - v.vscore, 0) AS vector_score,
       COALESCE(t.tscore, 0) AS text_score
FROM vector_results v
FULL OUTER JOIN text_results t ON v.id = t.id
ORDER BY (COALESCE(1 - v.vscore, 0) * 0.7 + COALESCE(t.tscore, 0) * 0.3) DESC
LIMIT 10;
```

## Scaling limits

pgvector on a single Postgres instance handles:
- **< 1M vectors** — excellent performance with HNSW
- **1-10M vectors** — good with tuning, adequate hardware (32GB+ RAM)
- **> 10M vectors** — consider partitioning, read replicas for query offload, or a dedicated vector DB

Insert throughput on HNSW indexes is lower than dedicated vector databases because each insert updates the graph. Batch inserts help. For write-heavy workloads (>10k vectors/second), a dedicated store with async ingestion may be better.

## When to graduate to a dedicated vector DB

- Dataset exceeds 10-50M vectors on a single node
- Sub-10ms p99 latency is a hard requirement at scale
- You need built-in multi-tenancy, namespaces, or collection isolation
- Write throughput exceeds what Postgres HNSW can sustain
- Ops team doesn't want vector search load on the primary database

Until then, pgvector in the Postgres you already run is simpler, cheaper, and more flexible.

## Connection pooling with pgvector workloads

PgBouncer in transaction mode works for short vector queries but breaks prepared statements unless configured. Session mode preserves prepared statements at cost of pool efficiency. For high QPS vector search:

- Keep embedding generation **outside** the database connection—compute vector in app, pass as parameter
- Use prepared statements for repeated query shape: `ORDER BY embedding <=> $1 LIMIT 10`
- Set `statement_timeout` on search role to prevent runaway sequential scans
- Separate read replica for search if writes cause replication lag affecting freshness SLAs

Neon's serverless Postgres and similar platforms support pgvector—verify HNSW index persistence and autoscaling behavior under index build load.

## Vacuum, bloat, and index health

Heavy UPDATE on embedding columns bloats HNSW indexes. Schedule `VACUUM (ANALYZE)` on tables after bulk re-embed jobs. Monitor `pg_stat_user_tables.n_dead_tup`. For major model migrations, sometimes faster to `CREATE TABLE chunks_v2`, bulk load, swap names in transaction, drop old table—than UPDATE-in-place on millions of rows.

```sql
SELECT schemaname, relname, n_live_tup, n_dead_tup, last_autovacuum
FROM pg_stat_user_tables
WHERE relname = 'chunks';
```

Reindex after bulk delete if query planner chooses sequential scan—check with `EXPLAIN (ANALYZE, BUFFERS)`.

## Hybrid search with Postgres full text

Combine vector and keyword without leaving Postgres:

```sql
SELECT id, content,
  ts_rank_cd(search_vector, plainto_tsquery('english', $2)) AS text_rank,
  embedding <=> $1 AS vector_dist
FROM documents
WHERE tenant_id = $3
  AND search_vector @@ plainto_tsquery('english', $2)
ORDER BY (0.3 * ts_rank_cd(search_vector, plainto_tsquery('english', $2))
         - 0.7 * (embedding <=> $1))
LIMIT 10;
```

Tune weights from click logs. GIN index on `tsvector` column; HNSW on embedding—both must be maintained. For production hybrid at scale, consider dedicated engines—but pgvector hybrid suffices for many SaaS MVPs.

## Row-level security with vectors

Multi-tenant RAG on shared pgvector tables needs RLS policies matching application auth:

```sql
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON chunks
  USING (tenant_id = current_setting('app.tenant_id')::uuid);
```

Set `app.tenant_id` per connection from JWT middleware. ANN indexes scan before RLS filter on some Postgres versions — verify `EXPLAIN` plan includes filter early; otherwise partition by tenant.

## Practical follow-through (1)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Resources

- [pgvector GitHub repository](https://github.com/pgvector/pgvector)
- [pgvector HNSW indexing](https://github.com/pgvector/pgvector#hnsw)
- [pgvector Python client](https://github.com/pgvector/pgvector-python)
- [Supabase vector guide](https://supabase.com/docs/guides/ai/vector-columns)
- [Neon pgvector documentation](https://neon.tech/docs/extensions/pgvector)
