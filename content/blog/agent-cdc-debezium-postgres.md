---
title: "AI Agents: Cdc Debezium Postgres"
slug: "agent-cdc-debezium-postgres"
description: "Change Data Capture with Debezium and PostgreSQL for agent systems — logical replication slots, outbox patterns, schema evolution, and exactly-once semantics for RAG index sync."
datePublished: "2025-02-16"
dateModified: "2025-02-16"
tags: ["AI", "Agent", "Cdc"]
keywords: "Debezium PostgreSQL CDC, logical replication, agent event sync, outbox pattern, WAL, Kafka Connect, RAG index updates, change data capture"
faq:
  - q: "Why use Debezium CDC instead of polling Postgres for agent state sync?"
    a: "Polling adds latency proportional to your interval and loads the database with repeated full-table or indexed scans. Debezium reads the WAL via logical replication, capturing row-level changes in near real time with minimal read amplification. For agent session stores and knowledge-base tables, CDC keeps downstream vector indexes and analytics pipelines within seconds of OLTP truth."
  - q: "What PostgreSQL settings are required for Debezium logical replication?"
    a: "Set wal_level=logical, max_replication_slots and max_wal_senders high enough for your connectors (typically 4–10 each), and ensure the Debezium user has REPLICATION privilege plus SELECT on captured tables. On managed RDS/Aurora/Cloud SQL, enable logical replication at the parameter group level and restart if required."
  - q: "How do you handle schema migrations without breaking CDC consumers?"
    a: "Prefer additive changes: new nullable columns, new tables. Debezium emits schema-change events when configured with a schema history topic. For breaking changes (column rename, type change), use expand-contract: add new column, dual-write, migrate consumers, drop old column. Never ALTER TYPE on a hot table without a consumer compatibility plan."
  - q: "Can Debezium guarantee exactly-once delivery to a vector index?"
    a: "Debezium delivers at-least-once from Postgres to Kafka. Exactly-once end-to-end requires idempotent consumers: upsert by primary key, tombstone deletes, and deduplication by LSN or event sequence. Vector pipelines should treat CDC events as upsert/delete operations keyed on document_id, not blind re-embed of every change."
---
The first time I wired an agent's knowledge base to PostgreSQL CDC, the demo worked in ten minutes and production broke in ten days. A schema migration added a `NOT NULL` column, the replication slot fell behind, WAL segments piled up until disk filled, and the search index served stale chunks for six hours before anyone noticed the lag alert was misconfigured. CDC with Debezium and Postgres is not a Kafka tutorial — it is an operational contract between your OLTP database, your event bus, and every downstream system that assumes the agent's world matches what's in the row store.

Agent platforms accumulate state in Postgres: conversation threads, tool invocation logs, tenant-scoped document metadata, feature-flag overrides, and approval queues. Batch ETL nightly is too slow when a user deletes a document and expects it gone from retrieval immediately. Polling `updated_at` columns works until you miss soft deletes, lose concurrent update ordering, or hammer the primary with index scans. **Change Data Capture** through logical replication gives you ordered, row-level events without rewriting application queries.

## How logical replication feeds Debezium

PostgreSQL writes every change to the Write-Ahead Log (WAL). With `wal_level=logical`, the server can decode WAL records into logical change events — inserts, updates, deletes — for subscribed tables. Debezium's PostgreSQL connector acts as a logical replication client: it creates a replication slot, streams decoded changes, and publishes them to Kafka (or other sinks) with envelope metadata.

The envelope matters for agents. A raw row snapshot is not enough; you need `op` (c, u, d, r for create/update/delete/read), `before` and `after` payloads, `source` metadata (LSN, transaction id, timestamp), and schema identifiers. Downstream indexers use LSN ordering to detect gaps and replays.

```
┌─────────────┐     WAL / logical slot      ┌──────────────┐     Kafka topics     ┌─────────────────┐
│  Postgres   │ ──────────────────────────► │   Debezium   │ ───────────────────► │ Agent indexers  │
│ (agent DB)  │                             │  Connector   │                      │ analytics, audit│
└─────────────┘                             └──────────────┘                      └─────────────────┘
```

Replication slots are the sharp edge. Postgres retains WAL until the slot consumer confirms progress. If Debezium stops or cannot keep pace, **WAL bloat** consumes disk and can halt writes to the primary. Monitor `pg_replication_slots` for `active`, `restart_lsn`, and lag bytes. Alert on lag, not just connector health.

## Table selection and publication design

Do not replicate every table. Agent CDC scope should mirror **downstream consumers**:

| Table class | Replicate? | Typical consumer |
|-------------|------------|------------------|
| `documents`, `chunks`, `embeddings_meta` | Yes | Vector index sync |
| `agent_sessions`, `messages` | Yes | Analytics, compliance archive |
| `users`, `tenants` | Often | Cache invalidation, entitlements |
| `job_queue`, `idempotency_keys` | Rarely | Ephemeral; high churn noise |
| Materialized views | No | Not in publications |

Use Postgres publications to limit scope:

```sql
-- Minimal publication for RAG document sync
CREATE PUBLICATION agent_doc_cdc FOR TABLE
  documents,
  document_chunks
  WITH (publish = 'insert, update, delete');

-- Debezium user (run as superuser or rds_superuser)
CREATE ROLE debezium_replication WITH REPLICATION LOGIN PASSWORD '...';
GRANT SELECT ON documents, document_chunks TO debezium_replication;
GRANT USAGE ON SCHEMA public TO debezium_replication;
```

For row-level filtering (multi-tenant isolation on shared topics), prefer **downstream filtering** by `tenant_id` in consumers rather than complex publication predicates — unless compliance mandates topic-level separation per tenant.

## Debezium connector configuration that survives production

A connector config tuned for agent workloads balances snapshot behavior, heartbeat, and slot management:

```json
{
  "name": "agent-postgres-cdc",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "pg-primary.internal",
    "database.port": "5432",
    "database.user": "debezium_replication",
    "database.password": "${secrets:debezium/db_password}",
    "database.dbname": "agent_platform",
    "topic.prefix": "agent",
    "table.include.list": "public.documents,public.document_chunks",
    "plugin.name": "pgoutput",
    "publication.name": "agent_doc_cdc",
    "slot.name": "debezium_agent_doc",
    "snapshot.mode": "initial",
    "heartbeat.interval.ms": "10000",
    "heartbeat.action.query": "INSERT INTO debezium_heartbeat (ts) VALUES (NOW());",
    "tombstones.on.delete": "true",
    "decimal.handling.mode": "string",
    "time.precision.mode": "adaptive_time_microseconds"
  }
}
```

Key decisions:

- **`pgoutput`** — native Postgres plugin; prefer over `decoderbufs` on supported versions.
- **Heartbeat table** — advances LSN during idle periods so slots don't stall when no agent writes occur overnight.
- **`tombstones.on.delete`** — emits Kafka tombstones on DELETE so compacted topics and vector indexers remove stale vectors.
- **`snapshot.mode=initial`** — full consistent snapshot on first start; use `no_data` for append-only tables where history is irrelevant.

After connector start, verify slot lag:

```sql
SELECT slot_name, active, pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS lag
FROM pg_replication_slots
WHERE slot_name = 'debezium_agent_doc';
```

## The outbox pattern for agent side effects

Application code that writes Postgres **and** publishes to Kafka in one request creates dual-write races: DB commits, message never sends, or message sends, DB rolls back. For agent tool calls that persist state and notify indexers, use the **transactional outbox**.

```sql
CREATE TABLE outbox_events (
  id            BIGSERIAL PRIMARY KEY,
  aggregate_id  UUID NOT NULL,
  event_type    TEXT NOT NULL,
  payload       JSONB NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Inside same transaction as business write
INSERT INTO documents (id, tenant_id, title, body) VALUES (...);
INSERT INTO outbox_events (aggregate_id, event_type, payload)
VALUES ($doc_id, 'DocumentCreated', jsonb_build_object('tenant_id', $tid, 'title', $title));
```

Debezium captures `outbox_events`; a separate router (or Debezium Outbox Event Router SMT) maps rows to domain topics. Consumers see one ordered stream per aggregate — critical when agent session updates must not arrive out of order.

## Consumer design for vector and cache pipelines

Index sync consumers should be **idempotent** and **keyed**:

```python
# kafka_consumer/embeddings_sync.py
from dataclasses import dataclass

@dataclass
class DocChange:
    op: str          # "c" | "u" | "d"
    doc_id: str
    tenant_id: str
    lsn: int

def handle_event(envelope: dict, indexer: "VectorIndexer") -> None:
    change = parse_debezium(envelope)
    dedupe_key = f"{change.tenant_id}:{change.doc_id}:{change.lsn}"

    if dedupe_store.seen(dedupe_key):
        return  # at-least-once replay

    if change.op == "d":
        indexer.delete(tenant_id=change.tenant_id, doc_id=change.doc_id)
    else:
        doc = fetch_document(change.doc_id)  # or use envelope.after
        chunks = chunk_document(doc)
        indexer.upsert(tenant_id=change.tenant_id, doc_id=change.doc_id, chunks=chunks)

    dedupe_store.mark(dedupe_key)
```

Avoid re-embedding on every `UPDATE` to a `view_count` column. Use **column include lists** in Debezium or filter in consumer: only react when content-bearing columns change. Debezium 2.x supports `column.include.list` per table to reduce noise.

For read-your-writes consistency in the agent UI, CDC lag is user-visible. Track **end-to-end latency** from commit timestamp to index searchable. SLO example: p95 under 30 seconds. If lag spikes, prefer throttling ingest over serving wrong answers.

## Schema evolution and operational failure modes

Common production failures:

1. **Long-running migration locks** — `ALTER TABLE` blocks replication decoding; plan migrations in maintenance windows or use online schema tools.
2. **Connector offset corruption** — restoring Kafka without schema history topic breaks deserialization; backup `schema-changes.agent` topic with retention aligned to recovery needs.
3. **Slot duplication** — never run two connectors against the same slot name; second connector stalls or duplicates events.
4. **TOAST columns** — large JSONB in agent transcripts may appear as partial updates; consumers must handle `toast` placeholders and refetch when needed.

Expand-contract rename example: add `content_v2`, backfill, switch writers, replicate both columns briefly, update consumer, drop `content_v1`.

## Security, compliance, and PII

CDC streams are a **data exfiltration surface**. Kafka ACLs must restrict topic read to indexer and audit services. Mask PII at source or via Debezium SMTs (`ReplaceField`, custom transforms) before events leave the compliance zone. Agent message tables often contain user prompts — classify topics accordingly and encrypt at rest.

Retention policies differ: OLTP may purge messages after 90 days while Kafka retains 7 days for replay. Document the gap for GDPR erasure requests — deleting a row emits a delete event, but compacted topics and index replicas need explicit tombstone propagation.

## Testing CDC paths before launch

Integration tests with Testcontainers (Postgres + Kafka + Debezium) validate:

- Insert → event → consumer upsert round trip
- Delete → tombstone → index removal
- Connector restart resumes from LSN without full snapshot
- Simulated lag recovery after consumer pause

Load test with production-shaped write rates. Agent bulk imports (ingesting 100k documents) spike WAL generation — ensure indexers scale horizontally and slot lag alerts fire early.

## Multi-region and failover considerations

Agent platforms running Postgres with cross-region read replicas must decide whether CDC attaches to the **primary only** or follows a promoted standby after failover. Debezium should always consume the write leader — logical replication slots do not automatically migrate on Patroni/etcd failover unless you automate slot recreation or use managed services that preserve slots.

During planned switchover:

1. Pause Debezium connector gracefully (commit final offsets)
2. Promote replica or fail over managed primary
3. Verify replication slot exists on new primary (recreate from `pg_replication_slots` backup metadata if needed)
4. Resume connector; expect a brief burst of catch-up events

For globally distributed agents, consider **region-scoped publications** — EU tenant data in `eu-west` Postgres should not stream to US indexers without compliance review. Row filters in consumers or separate connectors per region keep data residency boundaries enforceable.

Kafka topic partitioning strategy affects ordering: partition by `tenant_id` or `document_id` so all changes for one aggregate land in one partition. Agent session updates keyed only by random UUID lose per-session ordering if spread across partitions.

## Observability dashboard essentials

Wire these metrics before declaring CDC production-ready:

| Metric | Source | Alert threshold |
|--------|--------|-----------------|
| `debezium_postgres_connector_metrics_millisecondsbehindsource` | JMX / Prometheus | > 60s for 5 min |
| `pg_replication_slots_confirmed_flush_lsn` lag bytes | Postgres exporter | > 1 GB |
| Consumer lag per partition | Kafka | > 10k messages |
| End-to-end index freshness | Custom (commit ts → searchable) | p95 > 30s |
| Outbox table depth | Postgres | > 1000 rows for 10 min |

Correlate spikes with agent bulk import jobs — schedule imports with backpressure or temporarily scale consumers. A dashboard that only shows "connector RUNNING" green hides the six-hour index drift that triggers user trust incidents.

## Closing

Debezium on Postgres turns your agent database into the system of record **and** the event source, but only if you treat replication slots, schema migrations, and idempotent consumers as first-class concerns. Start with a narrow publication, heartbeat-enabled connector, outbox for dual writes, and end-to-end lag metrics. Expand table coverage as consumers prove stable — not before.

## Resources

- [Debezium PostgreSQL Connector Documentation](https://debezium.io/documentation/reference/stable/connectors/postgresql.html)
- [PostgreSQL Logical Replication](https://www.postgresql.org/docs/current/logical-replication.html)
- [Debezium Outbox Event Router](https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html)
- [Kafka Connect Production Deployment Guide](https://docs.confluent.io/platform/current/connect/index.html)
- [pgvector + CDC patterns for RAG](https://github.com/pgvector/pgvector)
