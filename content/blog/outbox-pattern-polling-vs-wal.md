---
title: "Outbox Pattern Polling vs WAL"
slug: "outbox-pattern-polling-vs-wal"
description: "Compare polling the outbox table against Postgres logical replication and WAL-based CDC for reliable event publishing."
datePublished: "2026-02-23"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Architecture"
keywords: "transactional outbox, polling vs wal, logical replication, debezium, change data capture"
faq:
  - q: "When is polling the outbox table good enough?"
    a: "Polling works well below roughly 500 events per second, when sub-second publish latency is acceptable, and when you want the simplest operational model — a background worker SELECT-ing unpublished rows. Add FOR UPDATE SKIP LOCKED, batch sizes tuned to your commit rate, and exponential backoff on empty polls."
  - q: "What latency advantage does WAL-based CDC provide over polling?"
    a: "WAL tailing delivers events within milliseconds of commit because the replication slot streams changes as they hit the write-ahead log. Polling introduces at least one poll interval of delay — often 100ms to 1s — plus query overhead. For user-facing read-your-writes across services, WAL CDC closes that gap."
  - q: "Does WAL-based outbox publishing still require an outbox table?"
    a: "Yes. The outbox table enforces atomic write-and-publish intent within the business transaction. WAL CDC replaces the polling relay — it watches the outbox table itself via logical replication rather than the application polling it. You still INSERT into outbox inside the same transaction as your domain write."
---

The transactional outbox pattern guarantees that domain state changes and event publication intent commit atomically. The remaining design question — how unpublished events reach your message broker — splits teams into two camps: **poll the outbox table** or **tail the WAL** via logical replication. Both work. They differ in latency, operational complexity, failure modes, and how they behave under load.

This article compares both approaches with enough implementation detail to choose confidently for your throughput and latency requirements.

## The outbox contract

Regardless of relay mechanism, the outbox contract is identical:

```sql
BEGIN;
  UPDATE orders SET status = 'shipped' WHERE id = $1;
  INSERT INTO outbox (aggregate_id, event_type, payload, created_at)
  VALUES ($1, 'OrderShipped', '{"orderId": ...}', now());
COMMIT;
```

Either both statements persist or neither does. The relay mechanism — polling or WAL — is a separate process that reads committed outbox rows and publishes to Kafka, SNS, or RabbitMQ.

## Polling relay architecture

A background worker loop:

```sql
SELECT id, event_type, payload
FROM outbox
WHERE published_at IS NULL
ORDER BY id
LIMIT 100
FOR UPDATE SKIP LOCKED;
```

For each row: publish to broker, then mark published:

```sql
UPDATE outbox SET published_at = now() WHERE id = $1;
```

Or delete after publish for append-only outbox tables with archival elsewhere.

Worker pseudocode:

```python
while True:
    rows = db.fetch_unpublished(limit=100)
    if not rows:
        time.sleep(POLL_INTERVAL)  # 100ms - 1s typical
        continue
    for row in rows:
        broker.publish(row.event_type, row.payload)
        db.mark_published(row.id)
```

### Polling strengths

- **Simplicity**: One table, one worker, no replication slots
- **Debuggability**: `SELECT * FROM outbox WHERE published_at IS NULL` shows backlog instantly
- **Portability**: Works on any Postgres version without logical replication enabled
- **Backpressure control**: Batch size and poll interval throttle publish rate naturally

### Polling weaknesses

- **Latency floor**: Events wait at least one poll interval after commit
- **Database load**: Empty polls still hit the database; high-frequency polling wastes connections
- **Duplicate publish risk**: Worker crashes after broker publish but before mark_published — requires idempotent consumers or transactional outbox cleanup patterns
- **Ordering**: Multiple workers with SKIP LOCKED may publish events for the same aggregate out of order

### Polling optimizations

**Adaptive poll interval**: Sleep 100ms when rows found, backoff to 1s when empty.

**Partial index** for unpublished rows:

```sql
CREATE INDEX outbox_unpublished_idx ON outbox (id)
WHERE published_at IS NULL;
```

**Batch publish**: Publish entire batch to broker in one produce call, then batch UPDATE.

**Separate mark step in same transaction as publish** using the transactional producer pattern (see companion article on Kafka) — or accept at-least-once and rely on consumer idempotency.

## WAL-based CDC relay architecture

Postgres logical replication streams row-level changes from the WAL to a consumer. Debezium (or pgoutput-native consumers) watches the outbox table:

```
Business TX → INSERT outbox row → WAL record
                                      ↓
                              Logical replication slot
                                      ↓
                              Debezium connector
                                      ↓
                              Kafka topic
```

Debezium configuration snippet:

```json
{
  "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
  "database.server.name": "orders-db",
  "table.include.list": "public.outbox",
  "plugin.name": "pgoutput",
  "publication.name": "outbox_pub",
  "transforms": "outbox",
  "transforms.outbox.type": "io.debezium.transforms.outbox.EventRouter"
}
```

The Outbox Event Router transform maps table columns to Kafka message key, topic, and payload automatically.

Setup on Postgres:

```sql
-- Requires wal_level = logical
CREATE PUBLICATION outbox_pub FOR TABLE outbox;

-- Replication slot created by Debezium on first connect
-- SELECT slot_name, confirmed_flush_lsn FROM pg_replication_slots;
```

### WAL CDC strengths

- **Sub-second latency**: Events stream within milliseconds of commit
- **No poll load**: Database does not serve repeated SELECT queries from relay workers
- **Change ordering**: Replication slot preserves WAL order per table
- **Decoupled scaling**: Kafka Connect cluster scales independently of application workers

### WAL CDC weaknesses

- **Operational complexity**: Replication slots, Connect cluster, schema history topics, connector restarts
- **Slot lag danger**: If the consumer stops, the replication slot retains WAL — disk fills up
- **Schema evolution**: Column additions require connector config updates and careful rollout
- **Requires logical replication**: Not available on all managed Postgres tiers; read replicas cannot host slots on some providers
- **Published row cleanup**: Still need a strategy to DELETE or archive published outbox rows

### WAL slot monitoring — non-negotiable

```sql
SELECT slot_name,
       pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn)) AS retained_wal
FROM pg_replication_slots
WHERE slot_type = 'logical';
```

Alert when retained WAL exceeds 1GB. A stalled Debezium connector with an active slot can fill your disk and crash Postgres.

## Side-by-side comparison

| Dimension | Polling | WAL CDC |
| --- | --- | --- |
| Publish latency | Poll interval (100ms–1s+) | ~10–100ms |
| DB read load | Repeated SELECT queries | WAL stream (minimal query load) |
| Setup complexity | Low | High |
| Failure: worker down | Backlog grows, no WAL retention | Slot retains WAL — disk risk |
| Exactly-once to broker | Hard (needs transactional producer) | Hard (same — at-least-once typical) |
| Multi-table outbox | Single worker can batch across tables | One connector per table or route transforms |
| Local dev experience | Trivial (run worker process) | Needs Connect + Kafka stack |

## Hybrid approaches

Teams often start with polling and migrate to WAL CDC when latency requirements tighten:

1. **Phase 1**: Polling worker, idempotent consumers, partial index
2. **Phase 2**: Add Debezium in shadow mode — compare events without consuming downstream
3. **Phase 3**: Cut over consumers to CDC-sourced topics, retire polling worker
4. **Phase 4**: DELETE published rows via scheduled job (both approaches need this)

Some architectures run both: polling as fallback when the replication slot lag exceeds a threshold. The polling worker picks up anything the CDC stream missed during connector downtime. Duplicate events are handled by consumer idempotency keys.

## Choosing for your workload

**Choose polling when**:

- Event volume under ~500/sec sustained
- 1-second publish latency acceptable
- Small team, minimal infrastructure
- Managed Postgres without logical replication support

**Choose WAL CDC when**:

- Sub-200ms publish latency required
- Event volume exceeds 1,000/sec
- Already operating Kafka Connect or Debezium for other tables
- Database team can monitor replication slot health

**Choose hybrid when**:

- Latency matters but CDC downtime cannot mean event loss
- Migrating from polling to CDC with zero-downtime requirement

## Outbox table design for both approaches

Design the table to serve either relay:

```sql
CREATE TABLE outbox (
  id            bigserial PRIMARY KEY,
  aggregate_type text NOT NULL,
  aggregate_id   text NOT NULL,
  event_type     text NOT NULL,
  payload        jsonb NOT NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  published_at   timestamptz
);

CREATE INDEX outbox_unpublished_idx ON outbox (id)
WHERE published_at IS NULL;
```

For Debezium Outbox Event Router, add routing columns:

```sql
ALTER TABLE outbox ADD COLUMN topic text NOT NULL DEFAULT 'domain-events';
ALTER TABLE outbox ADD COLUMN partition_key text;
```

Polling workers use `published_at IS NULL`. Debezium reads all INSERTs regardless — use a separate `published_at` update from a downstream consumer acknowledgment, or DELETE rows after Kafka ack via a compaction consumer.

## Idempotency regardless of relay choice

Both polling and WAL CDC deliver **at-least-once** to the broker. Design consumers with idempotency keys:

```sql
CREATE TABLE processed_events (
  idempotency_key text PRIMARY KEY,
  processed_at    timestamptz NOT NULL DEFAULT now()
);
```

Key on `outbox.id` or a business idempotency key in the payload. The relay mechanism does not change consumer requirements.

## Cleanup and table bloat

Published outbox rows accumulate in both models. Without cleanup:

- Index bloat on partial index (polling model checks unpublished filter)
- Sequential scans slow as table grows
- Debezium replays historical rows on snapshot (initial sync only, but table size affects snapshot duration)

Cleanup job:

```sql
DELETE FROM outbox
WHERE published_at IS NOT NULL
  AND published_at < now() - interval '7 days';
```

Run during low-traffic windows with `LIMIT` batches to avoid long locks.

## Summary

Polling the outbox table is the right default for most applications — simple, debuggable, and sufficient until latency or throughput demands push you elsewhere. WAL-based CDC via logical replication eliminates poll latency and database read overhead at the cost of replication slot monitoring, infrastructure complexity, and disk retention risk during consumer outages. The outbox table and atomic write pattern stay the same either way; only the relay changes. Start simple, measure publish lag against your SLO, and migrate to WAL CDC when the numbers justify the operational burden.
