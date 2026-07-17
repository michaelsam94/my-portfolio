---
title: "RAG: Embedding Store Versioning"
slug: "rag-embedding-store-versioning"
description: "Versioning embedding stores in RAG — model upgrades, dual-write migrations, namespace aliasing, and eval gates before cutover."
datePublished: "2025-04-06"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Embedding"]
keywords: "rag, embedding, store, versioning, ai, production, engineering, architecture"
faq:
  - q: "What must be versioned when upgrading embedding models in RAG?"
    a: "Version the embedding model ID and revision, vector dimension, distance metric, chunking parameters, and index namespace. Queries encoded with model A are not comparable to index B—treat model changes as incompatible schema migrations requiring re-embed or parallel indexes."
  - q: "How do you migrate production traffic to a new embedding store without downtime?"
    a: "Build new index namespace in shadow, dual-write new documents to both during transition, run eval comparing retrieval quality on golden queries, flip read alias atomically, keep old namespace read-only for rollback window, then decommission after TTL."
  - q: "Should embedding version live in vector metadata or only in index config?"
    a: "Both. Index-level config documents default model for queries; per-vector metadata fields embedding_model_version and corpus_version enable debugging mixed indexes during migration and filtering stale vectors if rollback partial."
---
Search quality jumped 12% in offline eval when the team swapped embedding models—then dropped in production because half the index still used old vectors and the query encoder silently upgraded. Hybrid results paired 1536-dim chunks with 3072-dim query embeddings after a partial reindex timed out. Rollback took a weekend because nobody had named namespaces per model version or an alias pointing traffic at a coherent store generation.

**Embedding store versioning** treats vector indexes like database schemas: incompatible changes get new versions, migrations are planned, and traffic cuts over via aliases—not hope that Sunday's cron finishes before Monday traffic.

## Dimensions of an embedding store version

A **store version** is a tuple, not just a model name:

```
{
  "store_version": "legal-us-2026q2-v3",
  "embedding_model": "text-embedding-3-large@2024-01",
  "dimensions": 3072,
  "metric": "cosine",
  "chunk_spec": "512tok/64overlap-heading-aware",
  "corpus_snapshot": "sha256:b7e4...",
  "created_at": "2026-06-01T00:00:00Z"
}
```

Query path must use **matching** embedding config. Mismatch is not degraded quality—it is meaningless geometry.

Store in a **version registry** (Postgres, DynamoDB, git YAML)—not tribal knowledge in runbooks.

## Namespace and alias pattern

Physical index namespaces are immutable generations; aliases point live traffic:

```
legal-us-prod          → ALIAS (read/write)
legal-us-prod-v2       → building (reindex target)
legal-us-prod-v1       → previous (rollback)
```

Pinecone, OpenSearch k-NN, pgvector with schema-per-version, Weaviate collections—naming convention consistent across backends.

**Atomic cutover**: update alias in one API call after validation gates pass. Apps never hardcode `v2` in config—resolve alias at startup with cache TTL.

## Migration workflow

### Phase 1: Shadow build

- Freeze chunk spec or document chunk spec in new version tuple
- Full reindex into `legal-us-prod-v3` from source corpus snapshot
- No production reads

### Phase 2: Dual-write (optional for incremental corpora)

New documents embed to **both** v2 and v3 during catch-up. Incremental sync jobs tag writes:

```python
for ns in ["legal-us-prod-v2", "legal-us-prod-v3"]:
    index.upsert(chunks, namespace=ns, metadata={"embedding_model_version": MODEL_V3})
```

Skip dual-write if full rebuild completes in maintenance window—simpler, less write amplification.

### Phase 3: Eval gate

Compare v2 vs v3 on golden query set (500+ labeled relevance judgments):

| Metric | Threshold |
|--------|-----------|
| nDCG@10 | v3 ≥ v2 - 0.01 |
| Recall@50 | v3 ≥ v2 |
| p95 query latency | v3 ≤ v2 * 1.15 |
| Zero-result rate | v3 ≤ v2 |

Fail gate → fix chunking or model choice, not silent cutover.

### Phase 4: Canary read

Route 5% query traffic to v3 via feature flag reading alternate namespace. Monitor feedback thumbs, latency, support tickets 48h.

### Phase 5: Alias flip + rollback window

`legal-us-prod` → v3. Keep v2 read-only 14 days. Rollback = alias flip back, no re-embed emergency.

### Phase 6: Decommission

Delete v1 vectors after retention policy. Archive version registry entry.

## Metadata on every vector

```json
{
  "id": "doc_4412_chunk_17",
  "values": [...],
  "metadata": {
    "corpus_version": "2025-06-01",
    "embedding_model_version": "text-embedding-3-large@2024-01",
    "chunk_spec_hash": "a1b2c3",
    "source_uri": "s3://..."
  }
}
```

Debug queries: "show chunks where embedding_model_version != expected"—should return zero before cutover.

## Query-side version enforcement

```python
def search(query: str, store_alias: str):
    cfg = version_registry.resolve(store_alias)
    query_vector = embed(query, model=cfg.embedding_model, dims=cfg.dimensions)
    return index.query(
        vector=query_vector,
        namespace=cfg.physical_namespace,
        metric=cfg.metric,
    )
```

Reject search if registry marks store `status=building`.

## Handling model deprecation from vendors

Vendors retire models on schedules. Alert 90 days before:

- Identify affected store versions
- Schedule reindex into new model tuple
- Budget embedding cost upfront

Never auto-upgrade model string in config without new namespace— that's how dimension mismatches ship.

## Cost and storage management

Old namespaces cost money. Policy:

- One previous generation online for rollback
- Older → export metadata + delete vectors, or move to cold storage if vendor supports

Track **$/million vectors** per version for finance.

## Observability

Metrics:

- `embedding_store_version` label on search latency, nDCG proxy metrics
- Reindex progress `% chunks embedded`
- Mixed-version vector count (should be zero post-cutover)

Traces include `store_version`, `model`, `namespace` on retrieval spans.

Embedding store versioning is the discipline that keeps query vectors and document vectors in the same mathematical space. Name namespaces per generation, register version tuples, gate cutover with eval, flip aliases atomically, and tag every vector with model metadata so partial migrations surface in dashboards—not in confused users wondering why search got worse after an "innocuous" model upgrade.

## Partial failure recovery during reindex

When reindex aborts at 73% complete, **resume checkpoints** store last processed document ID and embedding batch offset—do not restart from zero unless chunk spec changed. Checkpoint table keyed by target namespace version prevents paying twice for embeddings already computed.

Validate partial namespace before alias flip: random sample queries must hit only new-version vectors—grep metadata for stale `embedding_model_version` counts zero.

## Communicating version changes to customers

External API changelog entries when store version bumps affect recall characteristics—"search may surface different ordering after 2026-07-20 index refresh." Transparency reduces support tickets blaming "broken search" when quality actually improved but familiar top results moved.

Include `X-Embedding-Store-Version` response header for debugging client integrations without exposing internal namespace names.

## FinOps and embedding cost attribution

Reindex jobs tag cloud cost allocation labels with `store_version`—finance reports cost per version migration. Compare v2→v3 reindex spend against projected retrieval quality lift; kill migrations that exceed budget without eval gate pass.

Schedule large reindexes off-peak when embedding API tier pricing drops or reserved capacity available—cost optimization pairs with version registry scheduling API.

## Disaster recovery across store versions

Backup strategy includes **export vectors** for current alias target nightly—even if vendor manages infra, logical export to object storage enables rebuild on vendor outage. Export job tags `store_version`; restore validates dimension and model metadata before alias flip.

DR drill semi-annually: restore vN-1 namespace from backup into isolated environment, run golden query eval, document minutes to readable index. Finance approves storage cost for backups vs cost of search outage during reindex from raw documents only.

## Collaboration between ML and platform teams

Store version migrations require joint ownership: ML picks model and chunk spec; platform executes reindex and alias flip; product communicates user-visible search changes. RACI matrix in runbook prevents "I thought you reindexed" gaps. Weekly standup during active migration tracks embedding cost burn rate, eval gate status, and canary feedback—abort criteria pre-written before start, not debated under pressure at 2 a.m. when canary thumbs-down spikes.

Treat store versions like database migrations in change advisory board: major version bumps need scheduled maintenance window communication even when zero downtime technically achievable—users notice ordering changes without warning.

Store version registry entries should link to eval reports, cost estimates, and rollback runbooks in one URL per version—on-call during migration opens single bookmark instead of searching three systems. Include business owner sign-off timestamp field required before alias flip cron executes in automated pipeline.

Hybrid search compounds versioning complexity: BM25 index and vector index must share generation ID in registry tuple so partial upgrades cannot serve lexical results from v2 with vectors from v3. Single cutover ceremony flips both aliases or neither—documented in runbook with explicit abort if either backend lagging.

Version registry diffs should appear in deploy Slack notifications the same way application diffs do—operators notice namespace alias changes when the message is unavoidable, not when search quality shifts mysteriously after overnight cron.

## Field checklist for embedding store versioning

Before calling this done in production, confirm you can measure success and failure independently: a positive metric (throughput, conversion, recall) and a negative one (abuse rate, false accepts, lag). Add one alert that pages on the negative metric and one dashboard panel for the positive. Run a staging drill that forces the failure mode — timeout, poison input, or partial outage — and capture the exact commands in the runbook next to the config. If the drill takes longer than fifteen minutes to execute, simplify the recovery path before you need it at 2am.
