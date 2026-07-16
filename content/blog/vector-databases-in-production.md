---
title: "Vector Databases in Production: pgvector and Beyond"
slug: "vector-databases-in-production"
description: "A production guide to vector databases: when pgvector is enough, HNSW vs IVFFlat indexing, filtering, scaling limits, and choosing a dedicated store like Qdrant."
datePublished: "2026-01-29"
dateModified: "2026-01-29"
tags: ["Vector Database", "pgvector", "Postgres", "RAG"]
keywords: "vector database, pgvector, embeddings storage, similarity search, vector search production, HNSW"
faq:
  - q: "Is pgvector good enough for production?"
    a: "For most applications, yes. pgvector turns Postgres into a capable vector store, handling millions of vectors with HNSW indexing while letting you keep vectors, metadata, and relational data in one transactional database. Consider a dedicated vector database when you reach hundreds of millions of vectors or need advanced features it lacks."
  - q: "What is the difference between HNSW and IVFFlat?"
    a: "HNSW builds a graph for fast, high-recall approximate search with higher memory use and slower index builds. IVFFlat clusters vectors into lists and is cheaper to build with lower memory but generally lower recall. HNSW is the default choice for query-heavy production workloads."
  - q: "Do I need a dedicated vector database?"
    a: "Not usually to start. If you already run Postgres, pgvector avoids adding infrastructure and keeps everything in one place. Move to a dedicated store like Qdrant, Milvus, or Pinecone when scale, filtering performance, or specialized indexing outgrows what pgvector comfortably handles."
---

The most common over-engineering I see in RAG projects is standing up a dedicated vector database on day one. For the overwhelming majority of applications, [pgvector](https://github.com/pgvector/pgvector) — the vector extension for Postgres — is the right answer, and it stays the right answer well past the scale most teams ever reach. You get similarity search, your metadata, and your relational data in one transactional database you already know how to operate.

That said, "pgvector until it hurts" is a strategy, not a religion. There's a point where a purpose-built store earns its keep. This post covers when pgvector is enough, how to index it properly, the filtering trap that silently wrecks recall, and the signals that mean it's time to look at Qdrant, Milvus, or a managed option.

## Why start with pgvector

If Postgres is already in your stack, adding vector search is one extension away:

```sql
CREATE EXTENSION vector;

CREATE TABLE documents (
  id         bigserial PRIMARY KEY,
  content    text,
  category   text,
  embedding  vector(1536)
);

-- cosine distance nearest neighbours
SELECT id, content
FROM documents
ORDER BY embedding <=> $1
LIMIT 8;
```

The advantages compound. Your embeddings live next to the source rows, so there's no sync problem between a vector store and a system of record — a class of bug that eats weeks. You get transactions, backups, replication, and access control you already run. And you can combine vector search with ordinary SQL `WHERE` clauses and joins in a single query. For a [RAG pipeline](https://blog.michaelsam94.com/rag-in-production-chunking-reranking-evals/) serving up to tens of millions of chunks, this is genuinely all you need.

## Indexing: HNSW is the default now

An unindexed vector column does a full scan on every query — fine for a demo, fatal in production. pgvector offers two index types, and the choice matters:

| Index | Build cost | Memory | Recall | Best for |
| --- | --- | --- | --- | --- |
| HNSW | High | Higher | High | Query-heavy production |
| IVFFlat | Low | Lower | Moderate | Fast builds, tighter memory |

**HNSW** (Hierarchical Navigable Small World) builds a navigable graph and delivers high recall with fast queries — at the cost of slower builds and more memory. **IVFFlat** partitions vectors into lists and probes a subset; cheaper to build, lighter on memory, but lower recall. For most production workloads, build HNSW:

```sql
CREATE INDEX ON documents
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

Then tune `ef_search` at query time to trade recall for latency — higher `ef_search` means better recall and slower queries. Match the operator class to your distance metric (`vector_cosine_ops` for cosine, the standard for text embeddings), and make sure your queries use the same metric you indexed with, or the index won't be used at all.

## The filtering trap

Here's the mistake that bites teams in production: combining a metadata filter with vector search and getting terrible recall. You want "the nearest vectors *where category = 'legal'*," but the approximate index searches by vector similarity first and *then* filters — so if few of the nearest neighbors match your filter, you get back far fewer results than you asked for, or slow queries as the engine over-fetches.

The fixes, in order of preference:

- **Partition or use partial indexes** by your high-cardinality filter dimensions so each search space is pre-narrowed.
- **Increase `ef_search`** so the candidate pool is large enough to survive filtering — at a latency cost.
- **Consider a store with native filtered search** if filtering is central to your workload; this is one of the clearest reasons to outgrow pgvector.

Always test recall *with your real filters applied*, not on unfiltered queries. Unfiltered benchmarks look great and hide the problem you'll actually have. This is exactly the kind of regression a [retrieval eval](https://blog.michaelsam94.com/evaluating-retrieval-metrics-rag/) catches before users do.

## When to reach for a dedicated store

Move off pgvector when you hit real, measured limits — not hypothetical ones:

- **Scale.** Hundreds of millions to billions of vectors, where HNSW index memory and build times strain a single Postgres instance.
- **Filtering-first workloads.** Heavy metadata filtering where you need native filtered ANN search that stays fast and accurate.
- **Specialized features.** Built-in hybrid (dense + sparse) search, multi-tenancy isolation, quantization for memory savings, or distributed sharding out of the box.
- **Operational separation.** You want vector search to scale independently of your transactional database.

The main contenders: **Qdrant** (Rust, excellent filtered search, easy to self-host), **Milvus** (built for massive scale and distribution), **Weaviate** (integrated hybrid search and modules), and managed **Pinecone** (no ops, pay for it). Each is a real system to operate, monitor, and keep in sync with your source of truth — which is precisely the cost pgvector lets you avoid until you truly need it.

## Operational realities

Whichever you run, a few things separate a vector store that works in a demo from one that works at 2 a.m.:

- **Re-embedding is a migration.** Changing your [embeddings model](https://blog.michaelsam94.com/choosing-an-embeddings-model/) means recomputing every vector. Plan it like a [zero-downtime database migration](https://blog.michaelsam94.com/zero-downtime-database-migrations/) — dual-write, backfill, cut over.
- **Dimensions are fixed at the column.** Different models emit different dimensions; you can't mix them in one index.
- **Monitor recall, not just latency.** A fast index returning wrong neighbors is worse than a slow correct one. Track recall against a labeled set continuously.
- **Memory is the real cost.** HNSW keeps the graph in memory; size your instance for the index, not just the data.

My default recommendation stands: **start with pgvector.** It's less infrastructure, no sync problem, and enough for most of what people build. Reach for a dedicated vector database when you can name the specific limit you've hit — scale, filtering, or a feature you genuinely need. Choosing based on a benchmark blog post instead of your own measured constraints is how teams end up operating a distributed system they didn't need.

## Resources

- [pgvector — GitHub](https://github.com/pgvector/pgvector)
- [Qdrant — documentation](https://qdrant.tech/documentation/)
- [Milvus — documentation](https://milvus.io/docs)
- [Weaviate — documentation](https://weaviate.io/developers/weaviate)
- [Pinecone — Learn: vector search](https://www.pinecone.io/learn/vector-database/)
- [HNSW algorithm paper (arXiv)](https://arxiv.org/abs/1603.09320)
