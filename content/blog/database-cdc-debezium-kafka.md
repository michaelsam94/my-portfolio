---
title: "Change Data Capture with Debezium"
slug: "database-cdc-debezium-kafka"
description: "Debezium streams database row changes to Kafka from transaction logs. Setup patterns, schema evolution, ordering guarantees, and operational gotchas."
datePublished: "2025-08-22"
dateModified: "2025-08-22"
tags: ["Backend", "Databases", "Architecture"]
keywords: "Debezium, change data capture, CDC, Kafka Connect, PostgreSQL logical replication, MySQL binlog"
faq:
  - q: "What is Debezium?"
    a: "Debezium is an open-source CDC platform built on Kafka Connect. It reads database transaction logs — PostgreSQL WAL, MySQL binlog, SQL Server CDC — and publishes row-level change events (insert, update, delete) to Kafka topics with before/after payloads and schema metadata."
  - q: "Why use CDC instead of timestamp-based polling?"
    a: "Polling misses deletes, adds query load on source databases, and struggles with backfills. CDC captures every committed change in order with low latency and minimal impact on OLTP workloads when configured correctly."
  - q: "How do I handle schema changes with Debezium?"
    a: "Register schemas in Schema Registry; Debezium emits schema change events. Use backward-compatible Avro evolution. Consumers must handle optional new fields. For breaking changes, coordinate expand-contract migrations and snapshot reloads."
---

Polling `WHERE updated_at > ?` every five minutes was our integration strategy until a product manager asked why deleted users still received emails. Deletes don't bump `updated_at`. Change Data Capture from the transaction log captures the truth — inserts, updates, **and** deletes — without hammering the primary with full-table scans.

## How Debezium fits

```
PostgreSQL ──WAL──▶ Debezium Connector ──▶ Kafka ──▶ Flink/dbt/Snowflake
```

Debezium runs as a **Kafka Connect** connector (or Debezium Server for non-Kafka sinks). It reads the database's replication stream, not application queries.

## PostgreSQL setup sketch

Enable logical replication:

```sql
ALTER SYSTEM SET wal_level = logical;
-- restart required

CREATE PUBLICATION dbz_publication FOR TABLE public.orders, public.customers;

CREATE ROLE debezium REPLICATION LOGIN PASSWORD '...';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO debezium;
```

Connector config:

```json
{
  "name": "postgres-orders",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "postgres-primary",
    "database.port": "5432",
    "database.user": "debezium",
    "database.password": "${secrets}",
    "database.dbname": "app",
    "topic.prefix": "prod",
    "table.include.list": "public.orders,public.customers",
    "plugin.name": "pgoutput",
    "publication.name": "dbz_publication",
    "slot.name": "debezium_orders",
    "transforms": "unwrap",
    "transforms.unwrap.type": "io.debezium.transforms.ExtractNewRecordState",
    "transforms.unwrap.drop.tombstones": "false"
  }
}
```

`ExtractNewRecordState` simplifies payloads for downstream consumers.

## Event shape

Typical change record:

```json
{
  "op": "u",
  "before": { "id": 1, "status": "pending", "total": 100 },
  "after":  { "id": 1, "status": "paid", "total": 100 },
  "source": { "table": "orders", "lsn": 12345678 },
  "ts_ms": 1724000000000
}
```

`op`: `c` create, `u` update, `d` delete, `r` snapshot read. Tombstones on delete keys for Kafka log compaction.

## Initial snapshot + streaming

First connector start optionally **snapshots** existing table data, then switches to streaming. `snapshot.mode` options:

- `initial` — snapshot then stream (default)
- `never` — stream only
- `when_needed` — incremental snapshot features in newer versions

Large tables: parallel snapshot, filter predicates, or pre-load warehouse then start streaming from LSN.

## Ordering and partitioning

Kafka partition by primary key hash preserves **per-key ordering**, not global table order. Design consumers idempotently — same key may redeliver on failure.

Cross-table transactions appear as separate events — no atomic multi-table message. Sagas or outbox pattern for coordinated publishes.

## Schema evolution

Debezium publishes to Schema Registry (Avro/JSON Schema/Protobuf). Add nullable columns safely; renaming columns appears as drop+add — treat as breaking in consumers.

Enable `include.schema.changes` topic for audit; automate consumer compatibility tests in CI.

## Operational concerns

**Replication slots** on Postgres consume WAL — monitor lag; orphaned slots fill disks.

**Binlog retention** on MySQL — debezium heartbeat must keep pace.

**High-volume tables** — filter columns, separate connectors, or event flattening to reduce payload size.

**Secrets rotation** — connector restarts; use Kafka Connect secret providers.

Monitor: `MilliSecondsSinceLastEvent`, snapshot progress, connector FAILED state.

## Downstream patterns

- **Flink** — upsert Kafka changelog into Iceberg
- **Snowflake** — Kafka connector + MERGE
- **dbt** — staging models from raw CDC JSON, Type 1/2 on merge keys
- **Cache invalidation** — stream deletes to Redis

Pick primary key carefully — composite keys need composite Kafka keys.

## Debezium Server without Kafka

Not every team runs Kafka. Debezium Server pushes changes directly to sinks:

```yaml
# application.properties
debezium.sink.type=pubsub
debezium.sink.pubsub.project.id=my-project
debezium.source.connector.class=io.debezium.connector.postgresql.PostgresConnector
debezium.source.database.hostname=postgres-primary
debezium.source.table.include.list=public.orders
```

Supported sinks: Amazon Kinesis, Google Pub/Sub, Amazon SQS, Redis, Apache Pulsar, NATS JetStream. Simpler ops for teams without Kafka expertise — tradeoff is losing Kafka's replay and multi-consumer fan-out.

## Monitoring replication health

Critical metrics for Debezium operations:

| Metric | Alert threshold | Action |
|---|---|---|
| `MilliSecondsSinceLastEvent` | >300000 (5 min) | Check connector status, DB connectivity |
| Replication slot lag (bytes) | >1GB | Investigate slow consumer or connector pause |
| Snapshot progress | Stalled >1 hour | Check table size, parallel snapshot config |
| Connector state | FAILED | Auto-restart with backoff; check error logs |
| Schema change events | Any breaking change | Notify consumers, run compatibility tests |

Postgres replication slot monitoring is critical — orphaned slots prevent WAL cleanup and fill disk:

```sql
SELECT slot_name, pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS lag
FROM pg_replication_slots;
```

Alert when any slot lag exceeds 10GB.

## Outbox pattern integration

Debezium's outbox event router transform converts transactional outbox rows to clean domain events:

```sql
-- Application writes to outbox in same transaction as business data
INSERT INTO outbox (aggregate_id, event_type, payload)
VALUES ('order-123', 'OrderCreated', '{"orderId": "order-123", "total": 5000}');
```

```json
// Debezium outbox transform config
"transforms": "outbox",
"transforms.outbox.type": "io.debezium.transforms.outbox.EventRouter",
"transforms.outbox.route.topic.replacement": "events.${routedByValue}"
```

Debezium reads outbox table changes and routes to Kafka topics by event type — no separate relay process needed. See [outbox pattern guide](https://blog.michaelsam94.com/backend-outbox-inbox-messaging/).

## Failure modes

- **Orphaned replication slot** — WAL disk fills; monitor slot lag and connector health
- **Schema change breaks consumers** — column rename appears as drop+add; coordinate expand-contract
- **Initial snapshot on huge table** — hours of snapshot before streaming; use parallel snapshot or predicate filter
- **Delete events missed** — consumer ignores tombstones; stale data in downstream systems
- **High-volume table overwhelms Kafka** — filter columns, separate connector, or partition by key

## Production checklist

- Replication slot lag monitored and alerted
- Schema Registry configured for Avro/Protobuf evolution
- Initial snapshot strategy defined (parallel, predicate, or pre-load)
- Delete tombstones handled by all consumers
- Outbox pattern for reliable event publishing considered
- Connector auto-restart configured with backoff
- High-volume tables have dedicated connector or column filtering

Monitor replication slot lag as a paging alert, not a dashboard tile — WAL bloat from stalled CDC takes down the primary database.

## Resources

- [Debezium documentation](https://debezium.io/documentation/)
- [PostgreSQL logical replication](https://www.postgresql.org/docs/current/logical-replication.html)
- [Kafka Connect guide](https://kafka.apache.org/documentation/#connect)
- [Confluent — CDC with Debezium](https://docs.confluent.io/kafka-connectors/debezium-postgres-source/current/overview.html)
- [Debezium unwrap SMT](https://debezium.io/documentation/reference/stable/transformations/event-flattening.html)
