---
title: "Vector Databases in Production: pgvector and Beyond"
slug: "vector-databases-in-production"
description: "A production guide to vector databases: when pgvector is enough, HNSW vs IVFFlat indexing, filtering, scaling limits, and choosing a dedicated store like Qdrant."
datePublished: "2026-01-29"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "vector database, pgvector, embeddings storage, similarity search, vector search production, HNSW"
faq:
  - q: "What is the main production risk with vector databases in production?"
    a: "Teams ship without field measurement—vector databases in production failures appear as silent UX regressions, cost drift, or audit findings rather than clear errors."
  - q: "When should we prioritize vector databases in production?"
    a: "Prioritize when user research, CrUX, support tickets, or compliance requirements show pain on critical paths—not when a checklist mentions it abstractly."
  - q: "How do we validate vector databases in production changes?"
    a: "Baseline RUM before changes, compare p75 after deploy, and keep rollback via feature flags or cache purge documented in the PR."
---

title: "Vector Databases in Production: pgvector and Beyond"
slug: "vector-databases-in-production"
description: "A production guide to vector databases: when pgvector is enough, HNSW vs IVFFlat indexing, filtering, scaling limits, and choosing a dedicated store like Qdrant."
datePublished: "2026-01-29"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "vector database, pgvector, embeddings storage, similarity search, vector search production, HNSW"
faq:
  - q: "What is the main production risk with vector databases in production?"
    a: "Teams ship without field measurement—vector databases in production failures appear as silent UX regressions, cost drift, or audit findings rather than clear errors."
  - q: "When should we prioritize vector databases in production?"
    a: "Prioritize when user research, CrUX, support tickets, or compliance requirements show pain on critical paths—not when a checklist mentions it abstractly."
  - q: "How do we validate vector databases in production changes?"
    a: "Baseline RUM before changes, compare p75 after deploy, and keep rollback via feature flags or cache purge documented in the PR."
---
---

title: "vector-databases-in-production"
slug: "vector-databases-in-production"
description: ""
datePublished: "2026-07-17"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "vector-databases-in-production"
faq:
  - q: "What is the main production risk with vector databases in production?"
    a: "Teams ship without field measurement—vector databases in production failures appear as silent UX regressions, cost drift, or audit findings rather than clear errors."
  - q: "When should we prioritize vector databases in production?"
    a: "Prioritize when user research, CrUX, support tickets, or compliance requirements show pain on critical paths—not when a checklist mentions it abstractly."
  - q: "How do we validate vector databases in production changes?"
    a: "Baseline RUM before changes, compare p75 after deploy, and keep rollback via feature flags or cache purge documented in the PR."
---
---

title: "vector-databases-in-production"
slug: "vector-databases-in-production"
description: ""
datePublished: "2026-07-17"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "vector-databases-in-production"
faq:
  - q: "What is the main production risk with vector databases in production?"
    a: "Teams ship without field measurement—vector databases in production failures appear as silent UX regressions, cost drift, or audit findings rather than clear errors."
  - q: "When should we prioritize vector databases in production?"
    a: "Prioritize when user research, CrUX, support tickets, or compliance requirements show pain on critical paths—not when a checklist mentions it abstractly."
  - q: "How do we validate vector databases in production changes?"
    a: "Baseline RUM before changes, compare p75 after deploy, and keep rollback via feature flags or cache purge documented in the PR."
---
---

title: "vector-databases-in-production"
slug: "vector-databases-in-production"
description: ""
datePublished: "2026-07-17"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "vector-databases-in-production"
faq:
  - q: "What is the main production risk with vector databases in production?"
    a: "Teams ship without field measurement—vector databases in production failures appear as silent UX regressions, cost drift, or audit findings rather than clear errors."
  - q: "When should we prioritize vector databases in production?"
    a: "Prioritize when user research, CrUX, support tickets, or compliance requirements show pain on critical paths—not when a checklist mentions it abstractly."
  - q: "How do we validate vector databases in production changes?"
    a: "Baseline RUM before changes, compare p75 after deploy, and keep rollback via feature flags or cache purge documented in the PR."
---
---

title: "vector-databases-in-production"
slug: "vector-databases-in-production"
description: ""
datePublished: "2026-07-17"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "vector-databases-in-production"
faq:
  - q: "What is the main production risk with vector databases in production?"
    a: "Teams ship without field measurement—vector databases in production failures appear as silent UX regressions, cost drift, or audit findings rather than clear errors."
  - q: "When should we prioritize vector databases in production?"
    a: "Prioritize when user research, CrUX, support tickets, or compliance requirements show pain on critical paths—not when a checklist mentions it abstractly."
  - q: "How do we validate vector databases in production changes?"
    a: "Baseline RUM before changes, compare p75 after deploy, and keep rollback via feature flags or cache purge documented in the PR."
---
---

title: "vector-databases-in-production"
slug: "vector-databases-in-production"
description: ""
datePublished: "2026-07-17"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "vector-databases-in-production"
faq:
  - q: "What is the main production risk with vector databases in production?"
    a: "Teams ship without field measurement—vector databases in production failures appear as silent UX regressions, cost drift, or audit findings rather than clear errors."
  - q: "When should we prioritize vector databases in production?"
    a: "Prioritize when user research, CrUX, support tickets, or compliance requirements show pain on critical paths—not when a checklist mentions it abstractly."
  - q: "How do we validate vector databases in production changes?"
    a: "Baseline RUM before changes, compare p75 after deploy, and keep rollback via feature flags or cache purge documented in the PR."
---
---

title: "Vector Databases in Production: pgvector and Beyond"
slug: "vector-databases-in-production"
description: "A production guide to vector databases: when pgvector is enough, HNSW vs IVFFlat indexing, filtering, scaling limits, and choosing a dedicated store like Qdrant."
datePublished: "2026-01-29"
dateModified: "2026-07-17"
tags:
  - "Vector Database"
  - "pgvector"
  - "Postgres"
  - "RAG"
keywords: "vector database, pgvector, embeddings storage, similarity search, vector search production, HNSW"
faq:
  - q: "What is the main production risk with vector databases in production?"
    a: "Teams ship without field measurement—vector databases in production failures appear as silent UX regressions, cost drift, or audit findings rather than clear errors."
  - q: "When should we prioritize vector databases in production?"
    a: "Prioritize when user research, CrUX, support tickets, or compliance requirements show pain on critical paths—not when a checklist mentions it abstractly."
  - q: "How do we validate vector databases in production changes?"
    a: "Baseline RUM before changes, compare p75 after deploy, and keep rollback via feature flags or cache purge documented in the PR."
---
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

## pgvector before dedicated vector DB

Hybrid filters (`WHERE tenant_id = $1 ORDER BY embedding <=> $2`) are trivial in Postgres; awkward in some dedicated engines. Start HNSW index on pgvector; measure recall@10 on production query log sample. Billion-vector scale or sub-10ms at huge QPS — then evaluate Pinecone/Weaviate with same eval set, not blog benchmarks.

## pgvector before dedicated vector DB

Hybrid filters (`WHERE tenant_id = $1 ORDER BY embedding <=> $2`) are trivial in Postgres; awkward in some dedicated engines. Start HNSW index on pgvector; measure recall@10 on production query log sample. Billion-vector scale or sub-10ms at huge QPS — then evaluate Pinecone/Weaviate with same eval set, not blog benchmarks.

## Field metrics and rollback

Capture baseline p75 error rate and latency on tier-1 routes before merge. Compare seven days post-deploy sliced by mobile and region. Document rollback in PR and runbook.

## Resources

- [pgvector — GitHub](https://github.com/pgvector/pgvector)
- [Qdrant — documentation](https://qdrant.tech/documentation/)
- [Milvus — documentation](https://milvus.io/docs)
- [Weaviate — documentation](https://weaviate.io/developers/weaviate)
- [Pinecone — Learn: vector search](https://www.pinecone.io/learn/vector-database/)
- [HNSW algorithm paper (arXiv)](https://arxiv.org/abs/1603.09320)

## Trade-offs I keep revisiting for vector databases in production

AI systems around vector databases in production fail on evaluation blindness and cost cliffs. Define golden sets and latency/cost budgets before tuning ANN parameters or prompt length.

For vector databases in production:
- Separate embedding model version from index generation — rebuilds are migrations
- Filter/metadata strategy matters as much as HNSW params
- Cache semantic results carefully; stale answers look like model regressions
- Log prompts/outputs with PII redaction and retention limits

Ship a thin eval harness in CI for critical intents so prompt changes cannot silent-break production.

| Signal | Target | Alarm |
|--------|--------|-------|
| Coverage % | Team-defined SLO | Page on burn rate |
| Mean time to detect | Baseline − noise | Ticket if sustained |
| Escapes to prod | Budget cap | Weekly review |

## What reviewers should challenge in vector databases in production PRs

Reviewers should challenge assumptions encoded in vector databases in production: defaults copied from tutorials, timeouts that exceed upstream SLAs, and authz checks applied only on the primary UI path. Require a short threat or failure note in the PR when the change touches a trust boundary.

Concrete probes:
1. Scenario C for vector databases in production: traffic 3× baseline — prove autoscaling or shedding keeps the golden journey healthy.
2. Scenario A for vector databases in production: partial dependency outage — prove clients degrade gracefully and retries do not amplify load.
3. Scenario B for vector databases in production: bad config shipped — prove rollback within the declared RTO without data corruption.

## Capacity planning with vector databases in production in mind

Roll out vector databases in production behind a flag or weighted route when possible. Start with internal users or a low-risk geography. Watch the signals in the table for at least one full business cycle before calling the migration done. Keep the previous path warm until error budgets stabilize.

Document the owner, the dashboard, and the single command that reverts the change. If that sentence is hard to write, the design is not ready for production traffic.

## Multi-tenant concerns in vector databases in production

Detail 1 (634): for vector databases in production, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When multi-tenant concerns in vector databases in production becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break vector databases in production, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about vector databases in production: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Compliance evidence for vector databases in production

Detail 2 (708): for vector databases in production, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When compliance evidence for vector databases in production becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break vector databases in production, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about vector databases in production: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.
