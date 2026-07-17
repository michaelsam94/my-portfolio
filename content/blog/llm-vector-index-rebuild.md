---
title: "Vector Index Rebuild Strategies for Agent RAG"
slug: "llm-vector-index-rebuild"
description: "Blue-green vector index rebuilds when embeddings change: dual-write, alias cutover, HNSW vs IVF rebuild times, and validation gates before agent retrieval switches for teams running LLM features in production."
datePublished: "2025-05-01"
dateModified: "2026-07-17"
tags:
  - "AI"
  - "LLM"
keywords: "vector index rebuild agent, embedding migration RAG, blue green vector index, HNSW rebuild pgvector"
faq:
  - q: "When is a full vector index rebuild mandatory vs incremental update?"
    a: "Full rebuild when embedding model dimension or distance metric changes, HNSW parameter `m`/`ef_construction` changes, or corruption is suspected. Incremental upsert suffices for new/changed documents with stable model version — but schedule periodic full rebuilds to compact graph drift."
  - q: "How long do HNSW rebuilds take at agent scale?"
    a: "Rule of thumb: 1–4 hours per 10M 768-dim vectors on a single pgvector node with SSD — highly hardware-dependent. IVF rebuilds faster but recall drops unless `nlist`/`nprobe` retuned. Always benchmark on a snapshot, not spreadsheets."
  - q: "Can agents query two indexes during migration?"
    a: "Yes — dual-read fusion during shadow validation: query v1 and v2, log recall differences, serve v1 until v2 passes gates. Avoid dual-write to two index types long-term; pick cutover window."
  - q: "What validation gates block alias cutover?"
    a: "Recall@10 ≥ champion on golden query set, p95 latency within SLO, zero tenant isolation test failures, and embedding version tag matches config. Rollback alias flip must complete in under 5 minutes."
---
Embedding model upgrades are exciting until production agent retrieval returns wrong chunks because half your index was built with `text-embedding-ada-002` and half with `v3-large`. **Vector index rebuilds** are blue-green deployments for approximate nearest neighbor graphs — not `DROP INDEX` Friday afternoon. Agent platforms need alias cutover, shadow validation, and rollback paths as rigorous as API gateway migrations.

## Triggers for rebuild

| Event | Incremental upsert OK? | Full rebuild required? |
|-------|------------------------|------------------------|
| New documents ingested | Yes | No |
| Document text updated | Yes (re-embed chunk) | No |
| Embedding model version bump | No | Yes |
| Vector dimension change | No | Yes |
| HNSW `m` / `ef_construction` change | No | Yes |
| Index corruption / recall cliff | Maybe | Usually yes |

Track `embedding_model_version` and `index_build_id` in every retrieval log line.

## Blue-green index topology

```
                    ┌─────────────┐
  Agent retrieval ─►│ alias: prod │──► index_green (active)
                    └─────────────┘
                           │
              cutover      │ shadow queries
                           ▼
                    index_blue (building)
```

Implementation patterns:

- **pgvector:** separate tables `embeddings_green`, `embeddings_blue` + view alias swap.
- **Qdrant:** collection alias `prod` → physical collection name.
- **OpenSearch k-NN:** index alias pattern identical to text search.

## Dual-write embedding pipeline

During migration window, embed every new/changed chunk to **both** model versions:

```python
async def embed_and_store(chunk: Chunk, migration: MigrationState):
    if migration.phase in ("dual_write", "shadow"):
        vec_old = await embed(chunk.text, model=migration.from_model)
        vec_new = await embed(chunk.text, model=migration.to_model)
        store(migration.old_table, chunk.id, vec_old)
        store(migration.new_table, chunk.id, vec_new)
    elif migration.phase == "cutover":
        vec_new = await embed(chunk.text, model=migration.to_model)
        store(migration.new_table, chunk.id, vec_new)
```

Backfill historical chunks via batch job with rate limits on embedding API — throttle to avoid starving live agent traffic.

## HNSW vs IVF rebuild tradeoffs

| Index type | Build time | Query latency | Recall tuning |
|------------|------------|---------------|---------------|
| HNSW | Slow, memory-heavy | Low p95 | `ef_search` at query time |
| IVF-Flat | Faster bulk build | Medium | `nprobe` |
| IVF-PQ | Fastest, compressed | Higher variance | Quantization loss |

Agent RAG with <5M chunks and tight latency SLO: HNSW on pgvector or Qdrant. 100M+ chunks: IVF-PQ with aggressive re-rank on top-50.

pgvector HNSW build:

```sql
-- New table for blue index
CREATE TABLE embeddings_v3 (
  chunk_id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  embedding vector(3072) NOT NULL,
  model_version text NOT NULL DEFAULT 'text-embedding-3-large'
);

CREATE INDEX embeddings_v3_hnsw ON embeddings_v3
USING hnsw (embedding vector_cosine_ops)
WITH (m = 24, ef_construction = 128);

-- Partial index per tenant if multi-tenant isolation at index level
CREATE INDEX embeddings_v3_tenant ON embeddings_v3 (tenant_id);
```

Build during off-peak; monitor `pg_stat_progress_create_index`.

## Shadow validation gate

Before alias flip, run automated eval:

```python
def validation_gate(golden: list[Query], old_idx, new_idx) -> bool:
    recalls_old, recalls_new = [], []
    lat_old, lat_new = [], []
    for q in golden:
        r_old, t_old = search(old_idx, q.text, k=10)
        r_new, t_new = search(new_idx, q.text, k=10)
        recalls_old.append(hit_at_k(r_old, q.relevant_ids, k=10))
        recalls_new.append(hit_at_k(r_new, q.relevant_ids, k=10))
        lat_old.append(t_old)
        lat_new.append(t_new)

    mean_recall_new = sum(recalls_new) / len(recalls_new)
    mean_recall_old = sum(recalls_old) / len(recalls_old)
    p95_new = percentile(lat_new, 95)

    return (
        mean_recall_new >= mean_recall_old - 0.02
        and p95_new <= SLO_P95_MS
        and tenant_isolation_test(new_idx)
    )
```

Golden set must include tenant-scoped queries — recall globally means nothing if tenant A sees tenant B docs.

## Cutover and rollback

```sql
-- Atomic alias swap (PostgreSQL view pattern)
CREATE OR REPLACE VIEW retrieval_embeddings AS
  SELECT * FROM embeddings_v3;  -- was v2
```

Or Qdrant:

```bash
curl -X POST "http://qdrant:6333/collections/aliases" \
  -d '{"actions":[{"add_alias":{"alias_name":"prod","collection_name":"chunks_v3"}}]}'
```

Rollback: reverse alias to previous collection — keep old index hot for 7 days minimum.

## Agent-facing behavior during migration

- Feature flag `retrieval_index_version` in config — agents don't hardcode collection names.
- Elevated retrieval latency during rebuild is OK; wrong chunks are not.
- Communicate maintenance window if dual-read is disabled and cutover causes brief search unavailability.

## Operational checklist

1. Snapshot current index metadata and recall baseline.
2. Start backfill job; monitor embedding API spend cap.
3. Build ANN index on blue; verify disk headroom (HNSW ≈ 1.5× raw vector size overhead).
4. Shadow query 10% production traffic for 48h.
5. Flip alias; watch `retrieval_miss_rate`, agent task success, p95 latency.
6. Decommission green after rollback window.

## Resources

- [pgvector — HNSW indexing](https://github.com/pgvector/pgvector#hnsw)
- [Qdrant — Collection aliases](https://qdrant.tech/documentation/concepts/collections/#collection-aliases)
- [OpenSearch k-NN — index rebuild guidance](https://opensearch.org/docs/latest/search-plugins/knn/index/)
- [Pinecone — pod-based vs serverless migration notes](https://docs.pinecone.io/guides/indexes/pods/convert-a-pod-based-index-to-serverless)

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.
