---
title: "Keeping RAG Indexes Fresh"
slug: "rag-freshness-incremental-indexing"
description: "Keep RAG indexes fresh with incremental indexing: change detection, partial re-embedding, versioned corpora, and staleness policies for production knowledge bases."
datePublished: "2024-12-11"
dateModified: "2024-12-11"
tags: ["AI", "RAG", "Indexing", "Data Pipeline"]
keywords: "incremental indexing RAG, index freshness, vector database updates, change detection, stale documents, RAG pipeline"
faq:
  - q: "How often should I re-index my RAG corpus?"
    a: "Re-index frequency should match how often your source documents change and how costly stale answers are. Documentation that updates daily needs incremental indexing on every publish event. Stable policy documents might re-index weekly with a full rebuild monthly as a safety net. The right cadence is whatever keeps your p95 answer freshness within acceptable bounds for your users."
  - q: "What is the difference between incremental and full re-indexing?"
    a: "Full re-indexing rebuilds every chunk and embedding from scratch — simple but slow and expensive on large corpora. Incremental indexing detects changed, added, and deleted documents and updates only affected chunks. Most production systems use incremental updates for daily changes and scheduled full rebuilds to catch drift from failed incremental runs."
  - q: "How do I handle deleted documents in the vector index?"
    a: "Treat deletions as first-class events. When a source document is removed or archived, delete its chunks from the vector index by document ID metadata filter. Leaving orphaned chunks is how RAG systems cite policies that were revoked two years ago. Log deletions and verify chunk counts match source corpus counts after each sync."
---

Your RAG bot quoted the 2023 pricing page for three weeks after the February rate change because the indexing pipeline ran on a weekly cron and nobody wired it to the CMS publish webhook. The document was updated in the source system within minutes; the vector index lagged by days. Freshness is not a nice-to-have for knowledge bases that drive customer-facing answers — it is a correctness requirement.

## Sources of staleness

Staleness creeps in through multiple paths:

- **Batch-only indexing** — cron jobs that miss intra-week changes.
- **Append-only updates** — new versions indexed without deleting old chunks.
- **Failed incremental runs** — silent failures leave the index behind with no alert.
- **Cached embeddings** — reusing embeddings for edited text without re-embedding.
- **Downstream lag** — CMS updated but ETL to the search index has its own delay.

Map your document lifecycle from author edit to indexed chunk. Every hop is potential lag.

## Change detection strategies

**Webhook-driven:** CMS, Confluence, Git, or Notion publish events trigger indexing for the changed document only. Lowest latency, best for customer-facing docs.

**Hash-based polling:** Store a content hash per document. Poll the source on a schedule; re-index when hash differs.

```python
def needs_reindex(doc_id: str, source_content: str) -> bool:
    current_hash = sha256(source_content.encode()).hexdigest()
    stored_hash = metadata_store.get_hash(doc_id)
    return current_hash != stored_hash
```

**Version metadata:** If sources expose `last_modified` or `version` fields, compare against indexed metadata before downloading full content.

**Git-based:** For docs-as-code repos, index on push to main. Diff commits to determine which files changed.

## Incremental indexing workflow

```python
def sync_document(doc_id: str, content: str, metadata: dict):
    # 1. Delete existing chunks for this document
    vector_store.delete(filter={"doc_id": doc_id})

    # 2. Chunk and contextualize
    chunks = chunk_document(content, metadata)

    # 3. Embed only new chunks
    embeddings = embed_batch([c.text for c in chunks])

    # 4. Upsert with metadata
    vector_store.upsert(
        ids=[f"{doc_id}:{i}" for i in range(len(chunks))],
        embeddings=embeddings,
        documents=[c.text for c in chunks],
        metadatas=[{**metadata, "doc_id": doc_id, "chunk_index": i} for i in range(len(chunks))],
    )
```

Delete-then-upsert per document prevents duplicate chunks from partial updates. Use document-level IDs in metadata so deletion is a single filter operation.

## Versioned corpora for zero-downtime updates

For large indexes, rebuild a new version in the background and swap an alias when complete:

1. Index into `corpus-v2024-12-11` collection.
2. Run validation — chunk count, sample retrieval checks.
3. Point the production alias from `corpus-v2024-12-04` to `corpus-v2024-12-11`.
4. Delete the old collection after a grace period.

This avoids serving half-updated state during long full rebuilds.

## Staleness policies and retrieval filtering

Add temporal metadata and filter at query time:

```python
results = vector_store.search(
    query_embedding,
    filter={
        "status": "current",
        "effective_date": {"$lte": today.isoformat()},
    },
    top_k=10,
)
```

For documents with explicit expiry — promotional content, time-limited policies — store `expires_at` and exclude expired chunks automatically. Combine with a `version` field and prefer highest version when duplicates exist.

## Monitoring freshness in production

Track and alert on:

- **Index lag** — time between source `last_modified` and chunk `indexed_at`. Alert if p95 exceeds your SLA.
- **Sync failure rate** — failed webhook or cron runs.
- **Corpus count drift** — source document count vs indexed document count.
- **Stale citation reports** — user flags on answers referencing old versions.

Dashboard the age distribution of indexed chunks. A healthy index has most chunks indexed within your target window.

## Full rebuilds as a safety net

Schedule full rebuilds weekly or monthly even with incremental sync. They catch:

- Chunks orphaned by buggy delete logic.
- Embedding model upgrades requiring re-embedding everything.
- Metadata schema migrations.

Full rebuilds during low-traffic windows with versioned swap avoid serving incomplete indexes mid-build. Schedule them during maintenance windows and alert the on-call if rebuild duration exceeds historical p95 — a suddenly slow rebuild often means corpus size crossed an infrastructure threshold.

Track index staleness per document source — users trust RAG answers less when retrieved chunks are months older than source-of-truth updates.

## Webhook-driven incremental sync

```python
@app.post("/webhooks/cms")
async def cms_webhook(event: CMSEvent):
    if event.action == "published":
        await index_document(event.document_id, force=True)
    elif event.action == "deleted":
        await vector_store.delete(filter={"document_id": event.document_id})
    elif event.action == "unpublished":
        await vector_store.update_metadata(
            filter={"document_id": event.document_id},
            metadata={"status": "draft"},
        )
```

Debounce rapid edits — five saves in 30 seconds should produce one re-index, not five embedding calls.

## Versioned index swaps

Blue-green for vector indexes:

1. Build `index_v2` with updated embeddings
2. Validate recall on holdout query set
3. Atomically swap alias `production` → `index_v2`
4. Delete `index_v1` after 24h rollback window

Partial rebuilds mid-alias swap serve inconsistent retrieval — use dual-write or read-only mode during swap.

## Staleness in answers

Surface freshness to users when content is time-sensitive:

```python
def format_citation(chunk):
    age_days = (datetime.now() - chunk.indexed_at).days
    if age_days > 30:
        return f"{chunk.source} (indexed {age_days} days ago — may be outdated)"
    return chunk.source
```

Pair with [RAG metadata filtering hybrid](https://blog.michaelsam94.com/rag-metadata-filtering-hybrid/) for temporal filters at query time.

## Common production mistakes

Teams get freshness incremental indexing wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

RAG pipelines for freshness incremental indexing degrade when chunk boundaries split tables, embeddings go stale after doc updates, and retrieval metrics are measured offline only. Re-index incrementally and monitor answer faithfulness on live traffic samples.

## Resources

- [Pinecone — upsert and metadata filtering](https://docs.pinecone.io/guides/data/upsert-data)
- [Weaviate — incremental imports](https://weaviate.io/developers/weaviate/manage-data/create-objects)
- [LlamaIndex ingestion pipeline](https://docs.llamaindex.ai/en/stable/module_guides/indexing/ingestion_pipeline/)
- [Qdrant — payload-based filtering](https://qdrant.tech/documentation/concepts/filtering/)
- [Airflow — scheduling document sync DAGs](https://airflow.apache.org/docs/)
