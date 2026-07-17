---
title: "RAG: Exactly Once Delivery Claims"
slug: "rag-exactly-once-delivery-claims"
description: "Debunking exactly-once delivery in RAG pipelines — idempotent consumers, transactional outbox, and what Kafka EOS actually guarantees."
datePublished: "2024-11-17"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Exactly"]
keywords: "rag, exactly, once, delivery, ai, production, engineering, architecture"
faq:
  - q: "Is exactly-once delivery achievable in RAG ingestion pipelines?"
    a: "End-to-end exactly-once is not achievable in distributed systems with external side effects. Embedding APIs and vector upserts are side effects—you can achieve effectively-once processing via idempotent consumer design, deduplication keys, and transactional outbox patterns so duplicates do not create duplicate vectors or double-charged API calls."
  - q: "What does Kafka exactly-once semantics actually mean?"
    a: "EOS means exactly-once processing within Kafka streams when using transactions between consume-transform-produce on Kafka topics—it does not extend to side effects writing to Pinecone or OpenAI. Treat broker EOS as eliminating duplicate Kafka messages, not duplicate embeddings in your index."
  - q: "How should RAG workers deduplicate document processing?"
    a: "Use deterministic IDs: hash(source_uri + content_hash + chunk_index) for vectors, store processed document version in a dedup table with unique constraint, and pass idempotency keys to embedding APIs where supported. Replays become safe no-ops instead of duplicate chunks."
---
Marketing claimed "exactly-once document indexing." Finance counted embedding API calls and found 2.3× expected volume during backlog replays. The Kafka cluster had `enable.idempotence=true` and transactional producers; workers still double-upserted vectors because consumption committed before Pinecone acknowledged—and retries after crash re-embedded identical chunks. Exactly-once **delivery** became exactly-twice **billing** while search returned duplicate hits with different internal IDs.

**Exactly-once delivery** is the most misunderstood promise in streaming systems. Vendors and blog posts imply end-to-end guarantees; distributed systems textbooks say otherwise. RAG pipelines with costly embedding side effects must design for **at-least-once delivery with idempotent effects**—honest engineering beats marketing claims.

## The impossibility result (practical version)

Consider:

1. Worker consumes message M
2. Worker calls embedding API (side effect)
3. Worker upserts vectors (side effect)
4. Worker commits offset

Crash between any steps yields duplicate or missed processing unless external systems participate in a distributed transaction—which embedding APIs do not offer.

**Exactly-once** in the wild means one of:

- Exactly-once within broker boundary (Kafka transactions)
- Effectively-once via idempotency (same outcome if processed 1 or N times)
- Deduped visibility (user sees one result; duplicates suppressed at read)

RAG needs **effectively-once indexing**.

## Kafka exactly-once: scope and limits

Kafka EOS (0.11+):

- Idempotent producer (`enable.idempotence=true`) dedupes producer retries
- Transactions atomicity: consume from input topic + produce to output topic

Works for **Kafka → Kafka** stream processing. Stops at:

```python
# NOT covered by Kafka EOS
embedding = openai.embed(text)      # external API
pinecone.upsert(embedding)          # external DB
```

Document this in architecture reviews when someone enables transactions expecting magic.

## Idempotent consumer pattern for RAG

### Deterministic vector IDs

```python
def chunk_vector_id(doc_uri: str, content_hash: str, chunk_index: int) -> str:
    raw = f"{doc_uri}|{content_hash}|{chunk_index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]

def upsert_chunks(chunks):
    for c in chunks:
        vid = chunk_vector_id(c.uri, c.content_hash, c.index)
        index.upsert(id=vid, values=c.embedding, metadata=c.meta)  # overwrite = idempotent
```

Replay same document → same IDs → replace not duplicate.

### Processed document ledger

```sql
CREATE TABLE ingest_dedup (
  corpus_id TEXT,
  document_id TEXT,
  content_hash TEXT,
  processed_at TIMESTAMPTZ,
  PRIMARY KEY (corpus_id, document_id, content_hash)
);
```

Consumer checks ledger in same transaction as marking complete—or use INSERT ON CONFLICT DO NOTHING and skip if no row inserted.

### Idempotency keys for embedding APIs

OpenAI and others accept `Idempotency-Key` header—reuse key derived from `content_hash + model_version` so network retries do not double-charge.

## Transactional outbox pattern

Problem: DB commit and message publish are not atomic.

**Outbox**: write event to `outbox` table in same DB transaction as business state; separate relay publishes to queue.

```
BEGIN;
  INSERT INTO documents ...;
  INSERT INTO outbox (payload) VALUES (...);
COMMIT;
-- relay reads outbox → Kafka → workers
```

Worker idempotency handles relay duplicates. No lost messages if crash after COMMIT.

For RAG: sync job records document metadata + outbox `IndexDocument` command; projectors consume reliably.

## Ordering and partition keys

Per-document ordering: partition Kafka by `document_id`. Parallelism across documents; single consumer sequence per doc prevents chunk B before chunk A races.

Global order unnecessary for most corpora—do not single-partition entire topic for "ordering" unless required.

## Claiming EOS in SLAs and docs

Honest language for stakeholders:

| Claim | Accurate statement |
|-------|-------------------|
| "Exactly-once indexing" | "Idempotent indexing; duplicates suppressed" |
| "No duplicate vectors" | "Deterministic IDs with upsert semantics" |
| "Kafka EOS enabled" | "No duplicate Kafka messages between internal topics" |

Sales and legal appreciate precision after billing disputes.

## Testing duplicate delivery

Chaos tests:

- Kill worker after embed, before upsert—verify replay single vector
- Kill after upsert, before offset commit—verify ledger skip or idempotent upsert
- Publish duplicate messages manually—verify one index entry

Measure embedding API call count vs documents processed—ratio should approach 1.0 steady state, spike only during intentional reindex.

## DLQ interaction

Permanent failures go to DLQ after retries—separate from duplicate concern. Ledger records `failed_permanent` to prevent infinite retry loops on poison docs.

Replay from DLQ uses same idempotency keys—safe by design.

## Cost attribution

Track:

- `embedding_calls_total`
- `documents_processed_unique` (ledger inserts)
- `duplicate_suppressed_total`

Dashboard ratio exposes broken idempotency before finance does.

Exactly-once delivery claims collapse under RAG's external side effects unless you engineer idempotency explicitly. Kafka transactions help internal streaming; deterministic vector IDs, dedup ledgers, outbox publishing, and embedding idempotency keys deliver what users actually need—each document indexed once in effect, replays that do not multiply cost, and search results free of duplicate chunks from retry artifacts.

## Sagas and compensating transactions

When embedding succeeds but vector upsert fails persistently, **saga orchestrator** emits compensating `EmbeddingAttemptRevoked` event and marks ledger `failed`—support manual retry from DLQ without assuming clean state. Long-running ingest benefits from explicit saga state machine vs implicit retry loops.

Document which steps are compensable (delete orphan vectors by ID) vs require human intervention (embedding billed non-refundably).

## Observability for delivery semantics

Dashboard panels: `at_least_once_deliveries`, `idempotent_skips`, `effectively_once_rate = unique_docs_processed / messages_consumed`. Target effectively-once rate > 0.999 during steady state. Alert when idempotent skip rate drops suddenly—may indicate broken dedup table rather than improved reliability.

## Financial reconciliation with embedding vendors

Monthly invoice reconciliation: embedding API bill vs `embedding_calls_unique` ledger count. Discrepancy >0.5% triggers finance ticket—investigate duplicate calls from broken idempotency vs vendor billing error.

Idempotency key retention matches vendor dedup window (often 24h)—document alignment so retries after window do not double-charge while still safe at vector layer via deterministic IDs.

## Cross-team vocabulary training

Engineering, product, and sales must share vocabulary slide: **at-least-once delivery**, **idempotent processing**, **effectively-once outcomes**. Quarterly onboarding quiz for new PMs prevents roadmap promises of "guaranteed no duplicate indexing" in customer RFPs.

Legal reviews customer contracts for exactly-once language—replace with SLA on duplicate rate measurable via ledger metrics (`duplicate_vector_rate < 0.001%`) achieving same buyer confidence with honest metrics.

## Platform standards document

Publish internal **messaging semantics standard** mandating idempotency keys on all consumer handlers touching billable or user-visible state. Code review checklist item: "Does this handler safe under redelivery?" New RAG pipeline services scaffold with dedup table migration and deterministic ID helper—same way APIs scaffold OpenAPI validation. Standards beat post-hoc audits finding duplicate vectors after launch.

Platform guild maintains reference implementation in Java and Python copied into new services—reduces subtle bugs in hand-rolled dedup logic that tests miss because test harness delivers exactly-once unlike production Kafka.

Platform onboarding for new RAG ingest services includes 30-minute lab: deliberately crash consumer mid-batch, observe duplicate message delivery, verify index unchanged and embedding call count stable. Hands-on beats architecture slide for teaching idempotency expectations inherited from Kafka marketing.

Finance and engineering should share one dashboard for duplicate suppression rate and embedding spend—aligned incentives prevent teams hiding redelivery problems to avoid acknowledging wasted API budget after claiming exactly-once delivery in roadmap documents.

Idempotency is a property of the whole pipeline, not a Kafka checkbox. Document delivery semantics at service boundaries in OpenAPI and AsyncAPI specs so integrators know which guarantees extend across HTTP callbacks versus message consumers versus webhook retries from embedding vendors.

Run duplicate-delivery chaos tests in staging after every Kafka cluster upgrade or consumer framework major bump—regressions in offset commit semantics have shipped from upstream libraries without headline release notes, and RAG ingest pipelines are expensive places to discover them. Treat those tests as release gates, not optional hygiene.

## Integration notes for exactly once delivery claims

This rarely lives alone. Map upstream dependencies (auth, data stores, queues) and downstream consumers before you harden the happy path. Sequence the rollout: observability first, then flags, then the risky behavior change. That order turns rollback into a flag flip instead of a reverse migration under pressure. Keep the integration diagram in the same repo as the code so it cannot rot in a slide deck.
