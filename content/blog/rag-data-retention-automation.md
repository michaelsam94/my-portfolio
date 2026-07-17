---
title: "Automating Data Retention Policies"
slug: "rag-data-retention-automation"
description: "Automated retention for agent conversation logs, vector indexes, eval artifacts, and observability—legal holds, tenant policies, cascading deletes, and provable erasure for GDPR/CCPA."
datePublished: "2025-01-15"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Data"]
keywords: "data retention, gdpr erasure, agent logs, conversation deletion, ttl automation, legal hold, vector index cleanup, compliance"
faq:
  - q: "What data stores need retention policies in an agent platform?"
    a: "At minimum: conversation messages, tool I/O logs, embedding indexes and source chunks, session metadata, eval/export buckets, observability traces, and vendor-side copies (LLM API logs if retained). Each store may have different legal retention periods—automate per class, not one global TTL."
  - q: "How do you delete vectors when a user requests erasure?"
    a: "Map user/session identifiers to chunk IDs and vector primary keys at ingest time. Erasure job deletes rows in OLTP, objects in blob storage, vectors in the index, and emits deletion proofs. Re-embedding remaining docs without the user’s content may still be required if chunks mixed multiple tenants."
  - q: "What is a legal hold and how does it interact with TTL jobs?"
    a: "Legal hold pauses automated deletion for affected records when litigation or investigation requires preservation. Hold flags override TTL; release hold resumes normal schedules. Agent systems need hold at session or tenant granularity, auditable who set it and when."
---
Storage costs were flat, but the compliance review was not. Conversation logs stretched back four years across Postgres, S3, Pinecone, and a Datadog archive nobody had configured to expire. A GDPR erasure request took eleven engineer-days because **user_id** was not indexed in the vector metadata—teams grep’d JSON in cold storage. Retention had been "we'll delete someday." Automation turns policy into scheduled, auditable execution.

Agent platforms generate durable data faster than traditional SaaS: every turn, tool call, retrieved chunk, trace span, and eval run leaves copies in multiple systems. Manual cleanup does not scale. This post covers retention policy modeling, automated deletion workflows, legal holds, and cross-store erasure that survives audit.

## Retention policy as code

Define policies declaratively—not in wiki tables:

```yaml
# retention/policies.yaml
policies:
  conversation_messages:
    default_ttl_days: 90
    tenant_overrides:
      enterprise_acme: 365
    legal_hold_exempt: false

  tool_io_logs:
    default_ttl_days: 30
    redact_before_delete: true

  vector_chunks:
    default_ttl_days: 180
    cascade_from: source_document

  eval_export_artifacts:
    default_ttl_days: 14
    prefix: s3://agent-eval/staging/

  observability_traces:
    default_ttl_days: 30
    store: datadog
    external_api: true
```

Load policies into a **retention controller** service; version in git; require approval for default TTL decreases (may destroy evidence) and increases (may violate minimization).

## Identity graph: what to delete when user U leaves

Build a **deletion graph** at write time:

```
User → Sessions → Messages → ToolCalls
                    ↓
              ChunkReferences → VectorIds
                    ↓
              S3Objects (attachments, trace blobs)
```

```sql
-- deletion_graph tables (simplified)
CREATE TABLE retention_entities (
  entity_type TEXT NOT NULL,  -- user, session, message, vector
  entity_id TEXT NOT NULL,
  parent_type TEXT,
  parent_id TEXT,
  tenant_id TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  retain_until TIMESTAMPTZ,
  legal_hold BOOLEAN DEFAULT FALSE,
  PRIMARY KEY (entity_type, entity_id)
);

CREATE INDEX idx_retention_retain_until
  ON retention_entities (retain_until)
  WHERE legal_hold = FALSE AND retain_until IS NOT NULL;
```

Every ingest path registers entities and computes `retain_until` from policy + tenant override.

## TTL sweeper job

```python
# jobs/retention_sweeper.py
from datetime import datetime, timezone

BATCH_SIZE = 500

def sweep_due_entities(store, deleters: dict):
    now = datetime.now(timezone.utc)
    cursor = None
    while True:
        batch = store.fetch_due_for_deletion(
            before=now,
            limit=BATCH_SIZE,
            cursor=cursor,
            legal_hold=False,
        )
        if not batch:
            break

        for entity in batch:
            deleter = deleters[entity.entity_type]
            try:
                deleter.delete(entity)
                ledger.record_deletion(entity, job_run_id=RUN_ID)
            except Exception as e:
                ledger.record_failure(entity, error=str(e))
                metrics.increment("retention.delete.failure")

        cursor = batch.next_cursor
```

Schedule sweeper hourly for hot stores, daily for cold archives. Idempotent deletes—safe to retry.

## Store-specific deleters

**Postgres messages** — Hard delete or crypto-shred depending on policy:

```python
def delete_message(entity):
    db.execute(
        "DELETE FROM messages WHERE id = %s AND retain_until <= NOW()",
        (entity.entity_id,),
    )
```

**S3** — Lifecycle rules for prefix TTL plus explicit delete for erasure:

```python
def delete_s3_object(entity):
    s3.delete_object(Bucket=BUCKET, Key=entity.metadata["s3_key"])
    # Verify with head_object → 404
```

**Vector index** — Delete by metadata filter or primary ID:

```python
def delete_vectors(entity):
    index.delete(ids=[entity.entity_id])
    # Or: index.delete(filter={"session_id": entity.parent_id})
```

**Observability** — Call vendor retention API or submission deletion endpoints; do not assume default TTL exists.

Register deleters in a map; integration tests use LocalStack/minio and ephemeral vector index.

## GDPR/CCPA erasure workflow

Subject access requests differ from scheduled TTL. Erasure is **targeted and immediate** (within statutory window):

```python
def process_erasure_request(user_id: str, tenant_id: str):
    hold_check = legal_hold.active_for_user(user_id)
    if hold_check:
        return ErasureResult(status="blocked", reason="legal_hold")

    entities = graph.expand_user(user_id, tenant_id)
    run_id = ledger.start_erasure(user_id, entity_count=len(entities))

    for entity in entities:
        deleters[entity.entity_type].delete(entity)
        ledger.record_deletion(entity, run_id=run_id)

    reconciliation.verify_user_absent(user_id, tenant_id)
    ledger.complete_erasure(run_id)
    notify_dpo(run_id)
```

SLA timer starts at request verification—not when an engineer picks up the ticket. Automate verification emails and identity proof per policy.

## Legal hold automation

```python
def apply_legal_hold(scope: LegalHoldScope, actor: str, matter_id: str):
    affected = graph.query(scope)  # user_ids, tenant_id, date range
    db.execute(
        """
        UPDATE retention_entities
        SET legal_hold = TRUE, hold_matter_id = %s, hold_set_at = NOW(), hold_set_by = %s
        WHERE entity_id = ANY(%s)
        """,
        (matter_id, actor, [e.entity_id for e in affected]),
    )
    audit.log("legal_hold.set", scope=scope, matter_id=matter_id, actor=actor)

def release_legal_hold(matter_id: str, actor: str):
    db.execute(
        """
        UPDATE retention_entities
        SET legal_hold = FALSE, hold_matter_id = NULL
        WHERE hold_matter_id = %s
        """,
        (matter_id,),
    )
    # Recompute retain_until; sweeper picks up on next run
```

Hold UI in admin console must be CSRF-protected and role-restricted; every hold change pages legal team.

## Cascading deletes and mixed chunks

RAG chunks derived from multi-tenant documents are painful. Mitigations:

1. **Avoid mixed chunks** — partition corpus by tenant at source.
2. **Chunk-level provenance** — store `source_user_ids[]`; erasure removes or rewrites chunks listing that user.
3. **Re-index job** — after erasure, rebuild affected document shards without deleted segments.

```python
def erase_user_from_chunk(chunk_id: str, user_id: str):
    chunk = store.get_chunk(chunk_id)
    if chunk.tenant_id != infer_tenant(user_id):
        raise PermissionError()
    if user_id in chunk.contributor_ids:
        if len(chunk.contributor_ids) == 1:
            vector_index.delete(ids=[chunk_id])
            store.delete_chunk(chunk_id)
        else:
            redacted = redact_user_references(chunk.text, user_id)
            store.update_chunk(chunk_id, redacted)
            vector_index.upsert(chunk_id, embed(redacted))
```

Document re-index cost in erasure SLA for shared corpora.

## Vendor and third-party retention

Map subprocessors in a registry with `retention_days` and `deletion_api`:

| Vendor | Data class | Contract TTL | Automated delete |
|--------|------------|--------------|------------------|
| LLM API | Prompt/response | 30 days | Zero-retention flag + ticket |
| Labeling vendor | Exports | 14 days | SFTP purge script |
| Error tracker | Stack traces | 90 days | Project retention setting |

Erasure workflow must enqueue vendor deletes and **verify** responses—ledger status `pending_vendor` until confirmed.

## Monitoring and reconciliation

Metrics:

- `retention.entities_due` — backlog gauge
- `retention.delete.success/failure` — by store
- `retention.erasure_sla_hours` — histogram for DSAR
- `retention.orphan_scan.matches` — should trend to zero

Nightly reconciliation job:

```python
def reconcile():
    # Sample messages past retain_until still in DB
    orphans = db.query("""
        SELECT id FROM messages m
        JOIN retention_entities r ON r.entity_id = m.id
        WHERE r.retain_until < NOW() - INTERVAL '25 hours'
          AND r.legal_hold = FALSE
        LIMIT 100
    """)
    if orphans:
        page_oncall("retention_reconciliation_failed", count=len(orphans))
```

Quarterly drill: synthetic user erasure in staging, measure end-to-end time and orphan count.

## Backup and disaster recovery interaction

Backups extend retention beyond primary store TTL. Policy options:

- **Encrypted backups with same TTL metadata** — restore excludes expired entities (complex).
- **Shorter backup retention** than primary (common: 35-day backups, 90-day messages).
- **Crypto-shredding** — delete per-tenant DEK; backups become unreadable for that tenant.

Document in DPA which approach you use—"we restore backups" can undo GDPR erasure if not handled.

## Testing retention automation

```python
def test_sweeper_deletes_due_messages(db, fake_clock):
    msg = insert_message(created_days_ago=91)
    register_retention(msg, ttl_days=90)
    fake_clock.advance(days=1)
    run_sweeper()
    assert db.get_message(msg.id) is None
    assert ledger.has_deletion_record(msg.id)

def test_legal_hold_blocks_sweeper(db):
    msg = insert_message(retain_until=yesterday)
    apply_legal_hold(scope=UserScope(msg.user_id))
    run_sweeper()
    assert db.get_message(msg.id) is not None
```

Chaos: kill vector deleter mid-batch; verify idempotent retry does not double-charge or leave inconsistent graph.

## Tenant offboarding and contract termination

Enterprise churn triggers bulk retention changes distinct from per-user erasure. When a tenant contract ends, policy may require **immediate** purge of all tenant-scoped entities rather than waiting for individual TTLs:

```python
def offboard_tenant(tenant_id: str, actor: str):
    if legal_hold.active_for_tenant(tenant_id):
        raise OffboardBlocked("legal_hold")
    entities = graph.all_for_tenant(tenant_id)
    run_id = ledger.start_tenant_purge(tenant_id, len(entities))
    for entity in entities:
        deleters[entity.entity_type].delete(entity)
    reconciliation.verify_tenant_absent(tenant_id)
    ledger.complete_tenant_purge(run_id, actor=actor)
```

Run offboarding in staging with synthetic tenants before automating in production. Notify downstream billing and support systems only after reconciliation passes—partial offboards strand paid seats with no data.

## Closing

Data retention automation is how agent platforms keep minimization promises at scale: TTL sweeper jobs enforce policy code, deletion graphs make erasure tractable, legal holds integrate with audit, and reconciliation proves orphans do not linger. Treat conversation logs, vectors, and traces as **linked entities** from day one—not as silos cleaned up manually when storage bills or regulators arrive. The goal is predictable expiry, fast erasure, and evidence that both happened.

## Resources

- [GDPR Article 17: Right to erasure](https://gdpr-info.eu/art-17-gdpr/)
- [NIST SP 800-88: Media sanitization guidelines](https://csrc.nist.gov/publications/detail/sp/800-88/rev-1/final)
- [AWS S3 Lifecycle configuration](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html)
- [CNIL: Retention period guidelines](https://www.cnil.fr/en)
- [SOC 2 CC6.5 logical access and data retention mapping](https://www.aicpa.org/resources/landing/system-and-organization-controls)
