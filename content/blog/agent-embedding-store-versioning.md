---
title: "AI Agents: Embedding Store Versioning"
slug: "agent-embedding-store-versioning"
description: "Version embedding indexes for RAG agents—blue/green vector collections, model migration, query routing, and rollback when recall drops after re-embedding."
datePublished: "2025-04-07"
dateModified: "2025-04-07"
tags: ["AI", "Agent", "Embedding"]
keywords: "embedding versioning, vector index migration, RAG index version, blue green embeddings, Pinecone namespace, pgvector migration, embedding model upgrade, recall regression"
faq:
  - q: "When should I create a new embedding store version instead of overwriting?"
    a: "Create a new version when the embedding model changes (dimensions or geometry), chunking strategy changes, or preprocessing (OCR, language detection) changes. In-place overwrites are acceptable only for idempotent metadata fixes that do not alter vectors. Treat version bumps like database schema migrations with explicit cutover and rollback."
  - q: "How do I query during a long re-embedding job?"
    a: "Run dual-read or weighted routing: production traffic reads the current version while the new version builds in shadow. Compare recall@k on golden queries; cut over when new version meets or beats baseline. Keep the old version hot for 7–14 days for instant rollback."
  - q: "What metadata belongs in an embedding version record?"
    a: "Store model_id, model_revision, dimensions, chunk_size, chunk_overlap, tokenizer, source corpus snapshot id, created_at, document_count, and status (building, validating, active, deprecated). Propagate index_version on every retrieval request and agent session so mismatches fail loudly."
  - q: "How do I detect a bad embedding migration before users complain?"
    a: "Run automated eval: fixed set of 200–500 golden queries with expected doc IDs, measure recall@5 and MRR before/after. Alert if recall drops >3% absolute or latency p95 regresses >20%. Sample production queries into shadow retrieval against the candidate version."
---
Search quality collapsed the morning after a "routine" embedding upgrade. The team swapped `text-embedding-3-small` for a larger model, re-indexed overnight, and flipped the Pinecone namespace pointer at 06:00. By 09:00 support tickets spiked: correct answers existed in the corpus but ranked on page three. Chunk boundaries had changed; overlap settings differed; nobody had versioned the **store**—only the model name in a config file. Rollback meant re-pointing to `index_v17`, which still existed because ops had learned from a previous fire drill.

Embedding store versioning is how RAG agents survive model upgrades, document pipeline changes, and multi-tenant custom indexes without silent recall regression. Vectors are not fungible—768 dimensions from model A live in a different geometry than 1536 from model B. Mixing versions in one query guarantees wrong answers. This post covers version identifiers, dual-write migration, routing, and eval gates that block bad cutovers.

## What constitutes an embedding version

An embedding **version** is a immutable snapshot defined by everything that affects vector bytes:

- Embedding model (`model_id`, API revision, local weights hash)
- Vector dimension and distance metric (cosine vs dot vs L2)
- Chunking: size, overlap, splitter (markdown vs sentence)
- Preprocessing: OCR engine, language filter, PII redaction pass
- Source corpus: git SHA or snapshot ID of indexed documents

```typescript
// index/version.ts
export interface EmbeddingVersion {
  id: string; // e.g. "ev-2026-04-07-a3-large-ch512-o64"
  modelId: string;
  dimensions: number;
  metric: "cosine" | "dotproduct" | "euclidean";
  chunkSize: number;
  chunkOverlap: number;
  corpusSnapshot: string;
  status: "building" | "validating" | "active" | "deprecated";
  createdAt: string;
  documentCount: number;
}

export const ACTIVE_VERSION: EmbeddingVersion = {
  id: "ev-2026-04-07-a3-large-ch512-o64",
  modelId: "text-embedding-3-large",
  dimensions: 3072,
  metric: "cosine",
  chunkSize: 512,
  chunkOverlap: 64,
  corpusSnapshot: "corpus@8f2a1c9",
  status: "active",
  createdAt: "2026-04-07T04:00:00Z",
  documentCount: 1_842_000,
};
```

If any field changes, mint a new `id`. Never mutate vectors under an existing id.

## Physical storage layouts

Map logical versions to physical isolation:

| Backend | Pattern |
|---------|---------|
| Pinecone | Separate namespace or index per version |
| pgvector | Table per version `embeddings_v17` or partition key |
| Weaviate | Collection class `Document_ev17` |
| Qdrant | Named collection with version suffix |

```python
# storage/collection_name.py
def collection_for(version_id: str, tenant_id: str) -> str:
    # tenant isolation + version isolation
    safe = version_id.replace(".", "-").lower()
    return f"t_{tenant_id}__{safe}"

def upsert_batch(store, version: EmbeddingVersion, vectors: list[dict]):
    coll = collection_for(version.id, vectors[0]["tenant_id"])
    store.ensure_collection(
        coll,
        dim=version.dimensions,
        metric=version.metric,
    )
    store.upsert(coll, vectors)
```

Query code must accept explicit `index_version`; defaulting to "latest" hides cutover bugs.

## Blue/green indexing pipeline

Pipeline stages:

1. **Snapshot corpus** at `corpusSnapshot` hash—reproducible inputs.
2. **Build** new version in `building` status; embed in batches with checkpointing.
3. **Validate** recall on golden set; status → `validating`.
4. **Cutover** config to `active`; previous → `deprecated`.
5. **Retire** old physical collection after retention window.

```python
# pipeline/build_version.py
async def build_version(version: EmbeddingVersion, docs: AsyncIterator[Document]):
    batch, done = [], 0
    async for doc in docs:
        chunks = chunk(doc, version.chunkSize, version.chunkOverlap)
        vectors = await embed_batch(chunks, version.modelId)
        batch.extend(vectors)
        if len(batch) >= 500:
            upsert_batch(store, version, batch)
            batch, done = [], done + 500
            await update_progress(version.id, done)
    if batch:
        upsert_batch(store, version, batch)
    await set_status(version.id, "validating")
```

Embed jobs must be resumable—track last processed `doc_id` in a sidecar table.

## Query routing and agent session pins

When a user starts a session, pin `index_version` in session state. All turns in that conversation read the same version—even if cutover happens mid-chat—unless you explicitly migrate sessions.

```typescript
export async function retrieve(
  query: string,
  session: { indexVersion: string; tenantId: string },
): Promise<Chunk[]> {
  const version = await registry.get(session.indexVersion);
  if (version.status === "deprecated") {
    metrics.increment("retrieval_deprecated_version");
  }
  const vector = await embed(query, version.modelId);
  return vectorStore.search(
    collectionFor(version.id, session.tenantId),
    vector,
    { topK: 8, metric: version.metric },
  );
}
```

For global cutover, run two-phase:

- **Phase A:** New sessions get new version; old sessions drain on old version.
- **Phase B:** Force-refresh remaining sessions or accept one-turn quality blip.

Edge caches (KV, CDN) must include `index_version` in keys—see companion patterns on edge KV for agents.

## Evaluation gates before cutover

Golden query set stored in git:

```json
[
  {
    "query": "How do I reset MFA?",
    "expected_doc_ids": ["doc-security-mfa-001", "doc-security-mfa-002"]
  }
]
```

```python
def recall_at_k(results, expected_ids, k=5) -> float:
    top = [r.doc_id for r in results[:k]]
    hits = len(set(top) & set(expected_ids))
    return hits / len(expected_ids)

async def gate_cutover(candidate: EmbeddingVersion, baseline: EmbeddingVersion) -> bool:
    scores_new, scores_old = [], []
    for g in golden_queries:
        q_vec = await embed(g["query"], candidate.modelId)
        res_new = search(candidate, q_vec)
        res_old = search(baseline, q_vec)
        scores_new.append(recall_at_k(res_new, g["expected_doc_ids"]))
        scores_old.append(recall_at_k(res_old, g["expected_doc_ids"]))
    mean_new, mean_old = sum(scores_new) / len(scores_new), sum(scores_old) / len(scores_old)
    if mean_new < mean_old - 0.03:
        raise CutoverBlocked(f"recall regression: {mean_new:.3f} vs {mean_old:.3f}")
    return True
```

Add latency checks and spot human review for subjective answer quality on 20 sampled queries.

## Incremental updates within a version

Document adds/deletes within the **same** version should not require full rebuild:

- **Upsert** changed docs by `doc_id` (deterministic chunk IDs from content hash)
- **Delete** vectors for removed `doc_id`
- **Track** `indexed_content_hash` per doc; skip unchanged

If chunking parameters change, that is a **new version**, not an incremental patch.

## Multi-tenant version matrices

Enterprise tenants may lag on older versions during validation:

```yaml
# config/tenant_index_routing.yaml
tenants:
  acme:
    active_version: ev-2026-04-07-a3-large-ch512-o64
  beta-corp:
    active_version: ev-2026-03-01-a3-small-ch256-o32  # pinned until legal review
default_version: ev-2026-04-07-a3-large-ch512-o64
```

Registry service resolves `(tenant_id) → version`. Orchestrator never hardcodes "latest."

## Observability and rollback

Metrics:

- `embedding_version_active{version_id, tenant}`
- `retrieval_recall_shadow_diff` (candidate vs active on sampled queries)
- `index_build_lag_documents` during backfill
- `retrieval_latency_ms` by version

Rollback procedure (one page):

1. Set registry `active_version` back to last `deprecated` entry.
2. Invalidate edge caches keyed by new version prefix.
3. New sessions pick old version immediately; alert on-call for session pin review.
4. Postmortem: why eval gate missed regression?

Keep deprecated physical indexes for 14 days minimum—storage is cheaper than downtime.

## Handling embedding model deprecation

Providers retire models on notice. When `text-embedding-ada-002` or a self-hosted checkpoint reaches EOL:

1. Register final version with frozen corpus snapshot—no new docs on deprecated geometry.
2. Build successor version in parallel; extend validation window to 30 days for large corpora.
3. Communicate cutover date to tenants with API `Deprecation` headers on retrieval endpoints.
4. Block **new** index builds on deprecated models in CI.

```python
DEPRECATED_MODELS = {"text-embedding-ada-002": "2026-09-01"}

def assert_model_allowed(model_id: str):
    sunset = DEPRECATED_MODELS.get(model_id)
    if sunset and date.today() >= date.fromisoformat(sunset):
        raise ValueError(f"model {model_id} retired; bump embedding version")
```

Agents that allow customer-uploaded documents should queue re-embed jobs automatically when their pinned version enters `deprecated` status—proactive outreach beats silent quality decay.

## Cross-region replication of versioned indexes

Multi-region agent deployments replicate **active** versions only. Deprecated versions stay in primary region for rollback until retention expires. Replication lag means EU PoPs might query `ev-17` while US already serves `ev-18` during cutover—avoid split-brain by:

- Global config service with watch notifications (Consul, etcd, or managed feature store)
- Read-your-region-active-version with max 60 s staleness SLA
- Session pins that override regional defaults for conversation continuity

Never replicate half-built `building` versions to production regions; validation happens in one place, then promote artifacts.

## Cost and storage tradeoffs

Full re-embed of 2M chunks × 3072 dims is not cheap. Strategies:

- Compress with PQ/SQ only within a version family (document precision loss)
- Tier old versions to cold storage if rollback window closes
- Share corpus snapshots across tenants with identical pipelines to avoid duplicate embed jobs

Do not delete old versions the day after cutover—the rollback window exists because regressions surface slowly.

## Closing

Embedding store versioning treats vectors like schema migrations: immutable versions, explicit physical isolation, eval-gated cutover, and session pins that prevent mixed geometry in one query. Teams that bump `index_version` on every pipeline change roll back in minutes when recall dips; teams that overwrite in place debug mysterious quality cliffs for weeks. Version everything that touches the bytes—not just the model name in a comment.

## Resources

- [Pinecone namespace and metadata filtering](https://docs.pinecone.io/guides/indexes/manage-indexes)
- [pgvector indexing and performance](https://github.com/pgvector/pgvector)
- [OpenAI embedding model changelog](https://platform.openai.com/docs/guides/embeddings)
- [BEIR benchmark for retrieval evaluation](https://github.com/beir-cellar/beir)
- [LangChain index versioning patterns](https://python.langchain.com/docs/how_to/indexing/)
