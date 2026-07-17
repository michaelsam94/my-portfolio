---
title: "RAG: Event Sourcing Cqrs Basics"
slug: "rag-event-sourcing-cqrs-basics"
description: "Event sourcing and CQRS for RAG platforms — audit trails for corpus changes, read models for retrieval, and replay-safe ingestion pipelines."
datePublished: "2024-11-03"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Event"]
keywords: "rag, event, sourcing, cqrs, ai, production, engineering, architecture"
faq:
  - q: "Why would a RAG platform use event sourcing?"
    a: "Every corpus change—document added, chunk deleted, embedding model upgraded, ACL updated—becomes an immutable event. You gain complete audit history for compliance, ability to rebuild vector indexes by replaying events, and debugging of 'why was this chunk retrieved yesterday but not today' by projecting state at any timestamp."
  - q: "What goes in the write model versus read model for CQRS in RAG?"
    a: "Write model: append-only event log of corpus commands (UpsertDocument, RevokeAccess, ReindexStarted). Read models: materialized views optimized for retrieval—vector index, BM25 index, permission cache, document metadata table—built asynchronously by projectors consuming events."
  - q: "Does event sourcing replace the vector database?"
    a: "No. The event store is the system of record for changes; vector indexes are disposable projections rebuilt from events. You still query vectors for similarity search—the event log answers provenance and enables rebuild, not sub-second semantic search alone."
---
Support escalations asked why Tuesday's answer cited a contract clause removed Monday. The vector index had updated; the audit log had a row in `documents_updated_at` but no history of chunk-level deletes, no record of which sync job removed text, and no way to reconstruct index state as of Monday night for legal review. Replay meant full reindex from S3 snapshots that might not match what production served.

**Event sourcing** stores state as a sequence of immutable **events** rather than overwriting rows. **CQRS** (Command Query Responsibility Segregation) separates write paths (commands → events) from read paths (optimized projections). For RAG platforms managing corpus lifecycle under compliance pressure, the combination provides auditability, reproducible index rebuilds, and clear boundaries between ingestion commands and retrieval queries.

## Core concepts mapped to RAG

| Concept | RAG interpretation |
|---------|-------------------|
| Command | `IndexDocument`, `DeleteDocument`, `UpdateACL`, `StartReindex` |
| Event | `DocumentIndexed`, `ChunkRemoved`, `AccessDenied`, `ReindexCompleted` |
| Aggregate | `Corpus` or per-`Document` stream |
| Projection | Vector index, search metadata DB, permissions cache |
| Read model | What retrieval API queries |

User query "What is refund policy?" hits **read models** only—never appends events.

## Event store design

Append-only log per aggregate or partitioned by `corpus_id`:

```json
{
  "event_id": "evt_01J8Y...",
  "aggregate_id": "corpus:legal-us",
  "sequence": 1847291,
  "type": "DocumentIndexed",
  "occurred_at": "2026-07-16T14:22:01Z",
  "payload": {
    "document_id": "doc_4412",
    "source_uri": "s3://legal/nda-v4.pdf",
    "content_hash": "sha256:9f3c...",
    "chunk_count": 847,
    "embedding_store_version": "legal-us-v3"
  },
  "metadata": {
    "actor": "sync-job:nightly",
    "correlation_id": "sync-20260716"
  }
}
```

Technologies: EventStoreDB, Kafka with compacted topics, PostgreSQL event tables with optimistic concurrency on `sequence`.

**Never** mutate or delete events—compliance depends on immutability. Corrections append compensating events (`DocumentIndexRevoked`).

## Write path: commands to events

```python
def handle_index_document(cmd: IndexDocument, stream: EventStore):
    existing = stream.load(cmd.corpus_id)
    if existing.has_document(cmd.document_id):
        if existing.content_hash(cmd.document_id) == cmd.content_hash:
            return  # idempotent no-op
        events = [DocumentReplaced(...)]
    else:
        events = [DocumentIndexed(...)]
    stream.append(cmd.corpus_id, events, expected_version=existing.version)
```

Commands validate business rules before append. Duplicate sync deliveries become idempotent via content hash checks on aggregate state rebuilt from events.

## Projections: building read models

Async consumers project events into retrieval infrastructure:

```
DocumentIndexed → [Chunker projector] → ChunkCreated events
ChunkCreated → [Embed projector] → vectors upserted to Pinecone
DocumentIndexed → [Metadata projector] → Postgres doc table
AccessChanged → [ACL projector] → Redis permission set
```

Projectors track **checkpoint** position per consumer group. Lag metrics drive alerting—retrieval stale if projector behind.

Rebuild vector index from scratch:

1. Deploy empty namespace `legal-us-v4`
2. Reset projector checkpoint to 0 (or snapshot + delta)
3. Replay all `ChunkEmbedded` events or re-derive from `DocumentIndexed`
4. Swap alias when caught up

Hours-long replays acceptable offline—production queries continue on old projection until cutover.

## CQRS query side for RAG retrieval

Retrieval service reads:

- Vector index (similarity)
- Metadata filter DB (ACL, locale, corpus_version)
- Optional BM25 index (hybrid)

None write events during query. **Read-your-writes** consistency optional: after admin deletes document, UI polls until projector removes chunks— or synchronous projector for admin path only (pragmatic CQRS violation with clear scope).

## Snapshots for long aggregate streams

Corpus with millions of document events slows replay. Periodic **snapshots** store aggregate state at sequence N; projectors restart from latest snapshot + events since.

```json
{
  "aggregate_id": "corpus:legal-us",
  "sequence": 1800000,
  "state": { "documents": { "doc_4412": { "hash": "...", "chunk_ids": [...] } } }
}
```

Snapshot frequency tradeoff: storage vs rebuild time.

## Temporal queries for audits

Legal asks: "What chunks for doc_4412 were searchable on 2026-07-15?" Replay events until timestamp into in-memory state—or query **temporal read model** storing `(chunk_id, valid_from, valid_to)` intervals derived from events.

More honest than guessing from current index minus delete log.

## Integration with existing RAG pipelines

Incremental adoption:

1. **Dual-write**: sync job appends events AND updates index directly (transition)
2. **Projector owns index**: stop direct index writes from sync
3. **Event store authoritative**: rebuild test proves parity

Start with high-value corpora under regulatory scrutiny—not every hackathon index.

## Failure handling

- **Duplicate events**: idempotent projectors keyed by `event_id`
- **Out-of-order**: partition by aggregate; single writer per partition
- **Projector crash mid-batch**: at-least-once delivery + idempotent upserts
- **Poison event**: quarantine stream segment; append `ProcessingFailed` with manual fix

## When not to event-source

Low-stakes internal search prototype with no audit requirements—CRUD + index is fine. Event sourcing adds operational complexity (projector lag, schema evolution, snapshot management).

CQRS without full event sourcing still helps: separate ingestion write API from retrieval read API with different scaling profiles.

Event sourcing plus CQRS gives RAG platforms a time-travelable audit log of every corpus mutation and disposable vector indexes rebuilt from truth. Commands append facts; projectors materialize search; compliance officers get Tuesday-vs-Monday answers from replay—not from hoping S3 backup timestamps align with what users actually saw.

## Event schema evolution

Events live for years—use **upcasting** when payload shapes change: store version in event metadata, upcaster transforms v1→v2 on read before projectors consume. Never rewrite historical events in place.

```python
UPCASTERS = {
    ("DocumentIndexed", 1): lambda e: {**e, "organization_id": e.pop("tenant_id"), "_v": 2},
}
```

Projectors declare minimum event version supported; deploy upcasters before projectors requiring new shape.

## Snapshots and cold storage

Archive events older than retention policy to S3 Glacier with manifest—legal hold may require 7-year retention even if hot store keeps 90 days. Rebuild from archive slower but possible for litigation timelines.

Snapshot frequency tradeoff dashboard: replay lag vs snapshot storage cost vs recovery time objective (RTO) for full index rebuild.

## Projector scaling and ordering guarantees

High-volume corpora shard projectors by `corpus_id` partition—parallel embed projectors consume independent Kafka partitions preserving per-document order. Global ordering across corpus unnecessary; cross-document race acceptable if document IDs deterministic.

Monitor **projector lag** as SLO: retrieval read model no more than 5 minutes behind write stream for admin UI; 60 minutes acceptable for analytics projections. Alert separate thresholds per projection criticality.

## Choosing aggregates boundaries

Poor aggregate boundaries cause contention—`corpus:global` single stream serializes all document events worldwide. Prefer **document-level** or **source-connector-level** streams with corpus_id in event payload for filtering. Tradeoff: cross-document invariants harder to enforce—use saga orchestrating document events when bulk delete corpus requires atomic visibility.

Event store sizing: plan storage growth—legal corpus 100M events/year at 2KB average is hundreds of GB; tiered storage and snapshot policy prevent bill shock. Compress event payloads omitting redundant chunk text stored in object storage referenced by URI.

## When the audit trail becomes product feature

Some RAG customers pay for **provable citation history**—event sourcing enables "show what corpus state existed when answer generated" as premium compliance feature. Productize temporal replay API for legal customers instead of one-off engineering scripts during escalations. Monetization funds event store storage costs that otherwise face finance scrutiny as pure overhead.

Document replay API rate limits—full corpus replay is expensive; offer point-in-time query for single document aggregate stream by default, bulk replay only via async job with cost estimate approval.

Start event sourcing on one high-value corpus before mandating platform-wide—teams learn projector lag and schema evolution operational cost on bounded blast radius. Success criteria for expansion: zero audit escalations requiring unavailable historical state for six months on pilot corpus, and rebuild drill completed under RTO target without heroics.

Event store backup restore test quarterly—same discipline as database restores. Teams assume append-only log is safe until regional outage proves replay from backup is only recovery path when projectors corrupt read models catastrophically.

## Acceptance criteria for event sourcing cqrs basics

Ship only when staging demonstrates the failure modes you claim to handle. Record the evidence — load test output, chaos result, or screenshot of the alert firing — in the PR. Revisit the settings after the first real incident; production will teach you which timeout or retention value was optimistic. Prefer boring, documented tradeoffs over clever defaults that only exist in one engineer's head.
