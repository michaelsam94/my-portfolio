---
title: "AI Agents: Incremental Sync Cursors"
slug: "agent-incremental-sync-cursors"
description: "Cursor-based incremental sync for agent knowledge pipelines — watermark design, idempotent upserts, backfill safety, and recovery when connectors stall or replay."
datePublished: "2025-02-18"
dateModified: "2025-02-18"
tags: ["AI", "Agent", "Incremental"]
keywords: "incremental sync, cursor, watermark, CDC, agent knowledge base, idempotent upsert, backfill, change data capture, RAG pipeline"
faq:
  - q: "What makes a good sync cursor for agent knowledge bases?"
    a: "A production cursor must be monotonic, durable, and tied to a stable ordering key — updated_at plus id, sequence number, or LSN for CDC. It should survive worker restarts, be checkpointed after successful downstream writes (not before), and encode enough metadata to detect gaps or replays without full rescans."
  - q: "Should agent sync use timestamp cursors or change-data-capture?"
    a: "Timestamp watermarks work for low-volume SaaS APIs with reliable updated_at fields. CDC (Debezium, logical replication) is better when you need row-level deletes, sub-second freshness, or cannot trust client-side timestamps. Many agent stacks start with API polling cursors and migrate hot tables to CDC once volume or delete semantics demand it."
  - q: "How do I prevent duplicate embeddings when a sync job retries?"
    a: "Treat sync as at-least-once delivery: upsert source documents by stable external_id, hash content before embedding, and skip vector writes when the hash is unchanged. Store cursor position only after the document row and embedding job are committed in the same transaction or outbox event."
  - q: "What happens when a cursor falls behind or skips records?"
    a: "Alert on lag (now minus cursor watermark) and on zero-progress windows. Run periodic reconciliation jobs that compare source counts or checksums against your index. Keep a bounded lookback window (e.g., re-fetch last 15 minutes by updated_at) to heal clock skew and missed pages without full backfill."
---
A nightly full reindex of your agent's knowledge base worked fine at ten thousand documents. At four million — with Salesforce, Confluence, and Zendesk all pushing updates — the pipeline could not finish before the next run started, embeddings cost more than inference, and users saw stale answers for tickets closed six hours ago. The fix was not a bigger GPU cluster. It was incremental sync with durable cursors that checkpoint only after downstream work succeeds.

Incremental sync cursors are the contract between messy upstream systems and your agent's retrieval layer. Get the cursor semantics wrong and you either miss deletes, double-embed unchanged pages, or replay six hours of history after every deploy. Get them right and your RAG index stays fresh at the cost of changed rows, not total corpus size.

## Why full sync breaks agent pipelines first

Agent knowledge pipelines have three properties that punish naive batch jobs.

**Write amplification.** Every unchanged document re-fetched triggers chunking, embedding API calls, and vector upserts. A full sync of a million-row table where 0.3% changed daily still pays for a million embeddings.

**Latency to user-visible freshness.** Agents are judged on whether they know about the ticket you just closed or the policy page edited ten minutes ago. Hourly batch windows create predictable "the bot is wrong" reports.

**Operational fragility.** Long-running full sync jobs hit API rate limits, hold database connections, and fail halfway through — leaving indexes in unknown partial states unless you built idempotent merge logic anyway.

Incremental sync narrows each run to "everything after cursor X," but the cursor itself becomes load-bearing infrastructure.

## Cursor types and when to use each

| Cursor type | Ordering key | Best for | Failure modes |
|-------------|--------------|----------|---------------|
| Timestamp watermark | `updated_at` | REST APIs, SaaS exports | Clock skew, equal timestamps, missed soft deletes |
| Keyset / seek pagination | `(updated_at, id)` | Large SQL tables | Requires composite index; stable sort |
| Sequence / offset | Auto-increment id | Simple append-only logs | Gaps on deletes; not viable for updates |
| CDC log position | LSN, binlog offset | Postgres, MySQL replication | Operational complexity; schema migrations |
| Change token | Graph API `@odata.deltaLink` | Microsoft, Google delta APIs | Token expiry; must persist opaque tokens |

For most agent integrations, **keyset pagination on `(updated_at, id)`** is the sweet spot: monotonic, index-friendly, and resilient to rows sharing the same timestamp.

## Designing a durable cursor store

Cursors belong in a small, strongly consistent table — not in Redis alone, not in a worker's memory, not in a config file.

```sql
CREATE TABLE sync_cursors (
  connector_id     TEXT PRIMARY KEY,
  cursor_kind      TEXT NOT NULL CHECK (cursor_kind IN ('keyset', 'cdc_lsn', 'delta_token')),
  watermark_ts     TIMESTAMPTZ,
  watermark_id     TEXT,
  cdc_lsn          TEXT,
  opaque_token     TEXT,
  last_success_at  TIMESTAMPTZ NOT NULL,
  records_synced   BIGINT NOT NULL DEFAULT 0,
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX sync_cursors_stale_idx
  ON sync_cursors (last_success_at);
```

Rules that survive production:

**Checkpoint after commit, not before.** Advance the cursor only when the document upsert and embedding enqueue (or outbox row) are durable. If you checkpoint first and crash mid-batch, you lose data silently.

**One cursor per connector per tenant.** Sharing cursors across tenants creates cross-tenant gaps when one tenant's API errors.

**Version cursor schema.** When you change pagination logic, bump `cursor_kind` or add a `cursor_version` column so old checkpoints are not misinterpreted.

## Keyset pagination implementation

```python
# sync/keyset_pull.py
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import AsyncIterator

@dataclass(frozen=True)
class KeysetCursor:
    updated_at: datetime
    record_id: str

async def pull_changes(
    client,
    cursor: KeysetCursor | None,
    page_size: int = 500,
) -> AsyncIterator[tuple[dict, KeysetCursor]]:
    """Fetch records strictly after cursor using (updated_at, id) ordering."""
    params = {"limit": page_size, "order": "updated_at,id"}
    if cursor:
        params["after_updated_at"] = cursor.updated_at.isoformat()
        params["after_id"] = cursor.record_id

    while True:
        page = await client.list_records(**params)
        if not page.items:
            break

        for item in page.items:
            new_cursor = KeysetCursor(
                updated_at=item["updated_at"],
                record_id=item["id"],
            )
            yield item, new_cursor

        if not page.has_more:
            break
        last = page.items[-1]
        params["after_updated_at"] = last["updated_at"]
        params["after_id"] = last["id"]
```

On the SQL side, the equivalent query must use a composite index and avoid `OFFSET`:

```sql
SELECT id, title, body, updated_at, content_hash
FROM knowledge_documents
WHERE (updated_at, id) > ($1::timestamptz, $2::text)
ORDER BY updated_at ASC, id ASC
LIMIT 500;
```

Without `(updated_at, id)` indexed, incremental sync devolves into sequential scans that compete with your agent's online retrieval queries.

## Idempotent downstream writes

Sync is at-least-once. Retries, pod restarts, and Kafka redelivery will re-process rows. Downstream logic must be idempotent.

```typescript
// pipeline/upsertDocument.ts
import { createHash } from "crypto";

export async function upsertFromSync(
  db: Db,
  embedQueue: Queue,
  record: SourceRecord,
): Promise<"skipped" | "enqueued" | "inserted"> {
  const contentHash = createHash("sha256")
    .update(record.body)
    .digest("hex");

  const existing = await db.documents.findByExternalId(record.externalId);

  if (existing?.contentHash === contentHash && existing.deletedAt === null) {
    return "skipped"; // No embedding work needed
  }

  await db.transaction(async (tx) => {
    await tx.documents.upsert({
      externalId: record.externalId,
      title: record.title,
      body: record.body,
      contentHash,
      sourceUpdatedAt: record.updatedAt,
      deletedAt: record.isDeleted ? new Date() : null,
    });

    if (!record.isDeleted) {
      await tx.outbox.insert({
        type: "EMBED_DOCUMENT",
        payload: { externalId: record.externalId, contentHash },
      });
    } else {
      await tx.outbox.insert({
        type: "DELETE_VECTORS",
        payload: { externalId: record.externalId },
      });
    }
  });

  return existing ? "enqueued" : "inserted";
}
```

Skipping unchanged hashes is the single largest cost saver in agent sync pipelines. Teams that re-embed on every sync often discover 95% of rows are identical — they were paying for deterministic work.

## Handling deletes, tombstones, and soft deletes

Incremental APIs often omit deletes. Your agent will confidently cite removed policies unless you handle removal explicitly.

**Hard deletes via CDC.** Debezium `DELETE` events carry the primary key; enqueue vector deletion immediately.

**Soft deletes via flag.** Sync the row with `is_deleted=true` and tombstone the index entry.

**Reconciliation sweep.** Nightly, compare source ID sets (or use trash APIs) against your document table. Orphaned rows get tombstoned.

Never infer deletes from "row disappeared from this page" unless the API guarantees completeness.

## Backfill without clobbering incremental cursors

Initial load and incremental sync should share code paths but not cursors. Run backfill with a separate `connector_id` suffix (`zendesk:backfill`) or a `mode` flag. When backfill completes, seed the incremental cursor from the max `(updated_at, id)` observed, then disable backfill.

Parallel backfill plus incremental is possible with a high-water mark rule: incremental runs only fetch rows newer than backfill's trailing edge, coordinated via a shared status table. Most teams serialize backfill before enabling incremental to reduce race complexity.

## Overlap windows and clock skew

Pure timestamp cursors miss rows when the source clock jumps backward or when two rows share identical `updated_at` values and your pagination breaks ties incorrectly.

Mitigations:

- Always tie-break with primary key in sort order.
- Re-fetch an overlap window (5–15 minutes) each run and rely on idempotent upserts to absorb duplicates.
- For CDC, prefer log sequence numbers over wall-clock timestamps.

## Observability and alerting

Dashboards should answer: "Is sync keeping up, and is the index trustworthy?"

Metrics worth tracking:

- `sync_lag_seconds` — now minus cursor watermark timestamp
- `sync_records_processed_total` by connector and result (`skipped`, `enqueued`, `error`)
- `sync_api_errors_total` by HTTP status
- `embedding_queue_depth` correlated with sync spikes
- `index_freshness_p95` — agent query time minus newest `source_updated_at` in retrieved chunks

Alert when lag exceeds SLO (e.g., 15 minutes for ticket data), when `last_success_at` is stale despite scheduled runs, or when skip ratio drops suddenly (often signals hash logic broke).

Runbook outline:

1. Check upstream API status and rate-limit headers.
2. Inspect last cursor row — did watermark advance?
3. Sample failed records; fix schema mapping before rewinding cursor.
4. If poison message, quarantine record ID and advance cursor past it with manual audit entry.
5. Trigger overlap re-fetch for the last hour if gap suspected.

## Testing sync before production traffic

Unit tests cover cursor comparison and hash skip logic. Integration tests need a real database and a fake upstream with controlled clocks.

Scenarios to automate:

- Restart mid-batch: cursor must not advance; retry must not duplicate embeddings.
- Duplicate `updated_at`: keyset pagination returns all rows exactly once.
- Delete event removes vectors within freshness SLO.
- Clock skew overlap: same row fetched twice resolves to one index entry.

Property-based tests on `(updated_at, id)` ordering catch off-by-one pagination bugs that manual tests miss.

## Security and tenancy boundaries

Sync connectors hold broad read credentials to source systems. Scope OAuth tokens to read-only, partition credentials per tenant, and never mix tenant rows in a shared cursor. Audit cursor advances — they prove what data entered your agent's retrieval boundary and when.

For regulated content, tag synced rows with classification metadata at ingest so retrieval filters can enforce policy without rescans.

## Closing

Incremental sync cursors turn agent knowledge pipelines from fragile batch jobs into steady-state systems. The implementation details — keyset pagination, post-commit checkpoints, content-hash skip, explicit delete handling — are unglamorous but directly determine whether users trust agent answers. Design the cursor as durable infrastructure, measure lag like you measure inference latency, and treat every retry as proof your upserts are idempotent.

## Resources

- [Change Data Capture with Debezium](https://debezium.io/documentation/reference/stable/)
- [Microsoft Graph delta query documentation](https://learn.microsoft.com/en-us/graph/delta-query-overview)
- [Stripe pagination: cursor vs offset guidance](https://stripe.com/docs/api/pagination)
- [PostgreSQL: Avoid OFFSET for large datasets](https://www.postgresql.org/docs/current/queries-limit.html)
- [Transactional outbox pattern (microservices.io)](https://microservices.io/patterns/data/transactional-outbox.html)
