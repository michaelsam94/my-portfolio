---
title: "Vector Search in Postgres with pgvector"
slug: "vector-db-pgvector-postgres"
description: "Add vector search to Postgres with pgvector: installation, index types, similarity operators, hybrid queries, and when pgvector replaces a dedicated vector database."
datePublished: "2026-02-27"
dateModified: "2026-02-27"
tags: ["AI", "Postgres", "Vector Database", "RAG"]
keywords: "pgvector, Postgres vector search, HNSW, IVFFlat, embedding, similarity search, hybrid search"
faq:
  - q: "What is pgvector and how does it work?"
    a: "pgvector is a Postgres extension that adds a vector data type and similarity search operators to standard PostgreSQL. You store embeddings in a vector column, create an approximate nearest neighbor index (HNSW or IVFFlat), and query with distance operators like <=> for cosine distance. It runs inside your existing Postgres instance, so vector search joins with relational data in a single SQL query without a separate vector database."
  - q: "When should I use pgvector instead of a dedicated vector database?"
    a: "Use pgvector when you already run Postgres, your dataset is under roughly 10 million vectors, you need SQL joins between embeddings and relational data, and your team wants one database to operate. Switch to a dedicated vector database when you need horizontal sharding beyond a single Postgres instance, sub-10ms latency at hundreds of millions of vectors, or specialized features like multi-tenancy namespaces and built-in hybrid search pipelines."
  - q: "Which pgvector index type should I use: HNSW or IVFFlat?"
    a: "HNSW is the better default for most workloads in 2026. It offers higher recall at the same latency, supports concurrent inserts without major degradation, and does not require a training step. IVFFlat is faster to build and uses less memory, but needs a training pass on existing data to cluster centroids and its recall drops as data grows beyond the training set. Use IVFFlat only if memory is severely constrained or you need the fastest possible index build time."
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

## Common production mistakes

Teams get vector db pgvector postgres wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of vector db pgvector postgres fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [pgvector GitHub repository](https://github.com/pgvector/pgvector)
- [pgvector HNSW indexing](https://github.com/pgvector/pgvector#hnsw)
- [pgvector Python client](https://github.com/pgvector/pgvector-python)
- [Supabase vector guide](https://supabase.com/docs/guides/ai/vector-columns)
- [Neon pgvector documentation](https://neon.tech/docs/extensions/pgvector)
