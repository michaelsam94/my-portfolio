---
title: "AI Agents: Full Refresh Vs Incremental"
slug: "agent-full-refresh-vs-incremental"
description: "When agent pipelines should full-refresh versus incrementally sync state — CDC vs batch rebuild, vector index strategies, watermarking, and operational tradeoffs for RAG and tool caches."
datePublished: "2025-02-21"
dateModified: "2025-02-21"
tags: ["AI", "Agent", "Full"]
keywords: "full refresh, incremental sync, agent state, vector index rebuild, CDC, watermark, RAG pipeline, materialized view, idempotent upsert"
faq:
  - q: "When should an agent knowledge base use full refresh instead of incremental sync?"
    a: "Full refresh is appropriate after schema-breaking changes, embedding model upgrades, corrupted index state, or when incremental lag exceeds your freshness SLO and catch-up would take longer than a clean rebuild. It is also the right default for small corpora under a few hundred thousand chunks where rebuild cost is negligible compared to operational complexity."
  - q: "How do you prevent incremental sync from missing deletes or out-of-order updates?"
    a: "Emit tombstone events for deletes, carry monotonic sequence numbers or LSNs from the source, and make consumers idempotent with upsert-by-primary-key semantics. Reconcile periodically with a checksum or row-count diff against the source of truth; incremental alone without reconciliation drifts silently."
  - q: "What is the safest way to swap a vector index during full refresh?"
    a: "Build the new index in a shadow namespace or alias (e.g., index_v2), validate recall on a golden query set, then atomically flip an alias pointer. Keep the old index for rollback until error rates and latency stabilize. Never mutate the live index in place during a full rebuild."
  - q: "How do embedding model changes affect the refresh strategy?"
    a: "A new embedding model invalidates all stored vectors — incremental row sync is insufficient because the vector space changed. Plan a full re-embed with versioned embedding metadata, dual-read during migration if needed, and feature flags to route queries to the correct index version until cutover completes."
---
The argument between full refresh and incremental sync shows up the moment your agent stops being a demo and starts serving real tenants. A nightly batch job that re-indexes everything worked fine at ten documents; at ten million chunks with live deletes, permission changes, and embedding model upgrades, it becomes an outage waiting to happen. Incremental sync feels elegant until a missed tombstone leaves deleted PII in retrieval results. Full refresh feels safe until a six-hour rebuild blocks every deploy. The engineering question is not which pattern wins globally — it is which pattern matches your freshness SLO, corpus size, change rate, and failure modes.

Agent platforms accumulate derived state everywhere: vector indexes, tool-result caches, conversation summaries, permission denormalizations, and feature-store snapshots. The OLTP database remains authoritative; everything else is a projection. **Full refresh** rebuilds the projection from scratch. **Incremental sync** applies deltas — inserts, updates, deletes — as they occur or on a short schedule. Production systems almost always need both, selected per projection with explicit cutover rules.

## When full refresh is the correct default

Full refresh wins when the cost of rebuilding is predictable and lower than the cost of incremental correctness. Concrete scenarios:

| Scenario | Why full refresh |
|----------|------------------|
| Embedding model upgrade | Vectors are incompatible; every document must be re-embedded |
| Index corruption or unknown drift | Incremental cannot prove completeness |
| Schema migration on chunk layout | Old incremental events lack new fields |
| Small corpus (< 100k chunks) | Rebuild completes in minutes; CDC overhead not worth it |
| Greenfield index after bad deploy | Faster to rebuild than debug poisoned segments |

The operational shape is a **batch pipeline**: export source rows, transform, embed, bulk-load into a shadow index, validate, flip alias. Latency from source change to searchable is bounded by batch duration, not milliseconds.

```python
# Full refresh orchestrator — shadow index + alias swap
async def full_refresh_index(
    source: DocumentSource,
    embedder: Embedder,
    index: VectorIndex,
    alias: str = "agent_kb_live",
) -> RefreshResult:
    shadow = f"{alias}_shadow_{int(time.time())}"
    cursor = source.scan_all(batch_size=500)
    total = 0
    async for batch in cursor:
        vectors = await embedder.embed_batch([d.text for d in batch])
        await index.upsert_batch(shadow, zip(batch, vectors))
        total += len(batch)

    recall = await index.evaluate_recall(shadow, golden_queries=GOLDEN_SET)
    if recall < RECALL_FLOOR:
        await index.drop(shadow)
        raise RefreshFailed(f"recall {recall:.3f} below floor {RECALL_FLOOR}")

    await index.swap_alias(alias, shadow)
    await index.drop_old_aliases(alias, keep=1)
    return RefreshResult(chunks=total, recall=recall, shadow=shadow)
```

Never serve queries from a half-built index. Shadow builds isolate users from partial state. Golden-query recall gates prevent shipping a broken index because an embedder endpoint flaked mid-run.

## When incremental sync earns its complexity

Incremental sync is mandatory when freshness SLOs are measured in seconds or minutes, when corpus size makes full rebuild prohibitively expensive, or when source change volume is low relative to total corpus size. A document deleted by a user must disappear from retrieval before the next query — batch refresh with a six-hour window fails compliance and trust.

Incremental paths consume **change events** from CDC (Debezium, logical replication), message queues (outbox pattern), or application-emitted webhooks. Each event carries enough metadata to apply idempotent upserts and tombstone deletes.

```typescript
type ChangeEvent =
  | { op: "upsert"; id: string; tenantId: string; text: string; seq: bigint }
  | { op: "delete"; id: string; tenantId: string; seq: bigint };

async function applyIncremental(
  event: ChangeEvent,
  index: VectorIndex,
  embedder: Embedder,
): Promise<void> {
  const lastSeq = await index.getWatermark(event.tenantId, event.id);
  if (lastSeq !== null && event.seq <= lastSeq) {
    return; // stale or duplicate — idempotent no-op
  }

  if (event.op === "delete") {
    await index.delete(event.tenantId, event.id);
  } else {
    const vector = await embedder.embed(event.text);
    await index.upsert(event.tenantId, event.id, vector, { seq: event.seq });
  }
  await index.setWatermark(event.tenantId, event.id, event.seq);
}
```

Watermarks per `(tenant_id, document_id)` prevent out-of-order replay from regressing state. At-least-once delivery from Kafka or SQS is assumed; exactly-once end-to-end requires this idempotency layer at the consumer.

## Hybrid architectures most teams actually ship

Mature agent stacks rarely pick one mode globally. A practical split:

- **Incremental** for document CRUD, permission changes, and metadata updates on the hot path.
- **Scheduled full refresh** (weekly or on-demand) as reconciliation — compare source row counts to index counts, run checksum samples, rebuild if drift exceeds threshold.
- **Full refresh on trigger** for embedding version bumps, configured via feature flag or config change detection.

```
                    ┌─────────────────┐
  OLTP (Postgres)   │  change events  │
        │           └────────┬────────┘
        │                    │ incremental consumer
        ▼                    ▼
   batch export ──────►  vector index (alias: live)
        │                    ▲
        └──── full refresh ──┘ (scheduled + on model change)
```

The reconciliation job catches what incremental misses: bugs in delete propagation, consumer downtime longer than retention, manual DBA edits bypassing CDC. Run it off-peak; alert on drift percentage, not just job success.

## Cost and latency tradeoffs

Full refresh cost scales with **corpus size × embed price × index write throughput**. A 5M-chunk corpus at $0.0001 per 1k tokens for embedding can exceed thousands of dollars per rebuild. Incremental cost scales with **daily change rate**, but adds standing infrastructure: Kafka, Debezium slots, consumer fleets, dead-letter handling.

| Dimension | Full refresh | Incremental |
|-----------|--------------|-------------|
| Freshness | Batch interval (hours) | Seconds to minutes |
| Compute spike | High during rebuild | Steady low |
| Correctness proof | Strong after validation | Requires reconciliation |
| Operational complexity | Lower | Higher (lag, ordering, DLQ) |
| Rollback | Keep previous index alias | Replay from offset or rebuild |

For agent **tool caches** (API responses, computed summaries), incremental often means TTL-based invalidation plus selective refresh — not every cache layer needs CDC. Full refresh of a tool cache on deploy is acceptable when cache warm time is seconds and stale tools fail closed.

## Failure modes that decide the argument

**Incremental lag** during traffic spikes leaves retrieval serving outdated permissions — a security issue, not just staleness. Monitor consumer lag, replication slot WAL retention, and p95 time-from-write-to-indexed. If lag exceeds SLO, pause writes to the index consumer and fall back to read-from-primary for critical paths, or trigger partial full refresh for affected tenants.

**Partial full refresh** without alias swap exposes users to incomplete indexes. Always build shadow, always gate on eval metrics.

**Embedding model change mid-incremental** produces a mixed vector space if some chunks re-embed and others do not. Version-tag every vector with `embedding_model_id`; query routing must filter or rebuild consistently per version.

**Delete propagation failure** is the silent killer. Integration tests must assert: insert → searchable → delete → not searchable, within SLO window. Property: for any document id, index state eventually matches source or alerts fire.

## Testing and rollout discipline

Contract tests between source schema and consumer mapping catch breaking migrations before production. Golden-path integration tests with real Postgres + Kafka (Testcontainers) validate ordering and tombstones.

Roll out incremental consumers with **dual-write shadow**: apply events to shadow index, diff sample queries against live, promote when diff rate is zero for 24 hours. Full refresh rollouts use canary tenants first — rebuild shadow for tenant cohort A, compare recall, expand.

Feature flags should control query routing (`index_version`, `embedding_model_id`) independently of build pipelines so you can rollback query path without re-running a six-hour embed job.

## Observability essentials

Dashboards need four panels per projection: **lag** (seconds from source commit to indexed), **throughput** (events/sec), **error rate** (DLQ depth), and **freshness SLO burn**. Log structured fields: `document_id`, `tenant_id`, `seq`, `op`, `index_alias`, `embedding_model_id`.

Alerts on lag alone are insufficient — a stalled consumer with zero throughput also triggers. Combine lag > threshold AND consumer heartbeat age.

## Closing

Full refresh versus incremental is a per-projection decision tied to freshness, cost, and correctness requirements — not an architectural religion. Ship incremental for hot document paths with watermarks, tombstones, and scheduled reconciliation. Full refresh remains your escape hatch for model changes, corruption, and proof-of-correctness. The teams that get burned treat incremental as "set and forget" or run full refresh in place without shadow indexes. Document the cutover runbook before you need it at 3 a.m.

## Resources

- [Debezium PostgreSQL Connector Documentation](https://debezium.io/documentation/reference/stable/connectors/postgresql.html)
- [Elasticsearch Reindex API and Index Aliases](https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-reindex.html)
- [Pinecone: Understanding Hybrid Search and Metadata Filtering](https://docs.pinecone.io/guides/data/understanding-hybrid-search)
- [dbt: Incremental Models](https://docs.getdbt.com/docs/build/incremental-models)
- [AWS: Lambda Powertools Idempotency](https://docs.powertools.aws.dev/lambda/python/latest/utilities/idempotency/)
