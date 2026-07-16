---
title: "Streaming CDC to the Warehouse"
slug: "cdc-streaming-to-warehouse"
description: "Change Data Capture streams database mutations to your data warehouse in near-real-time. Set up Debezium, Kafka, and Snowflake/BigQuery ingestion for analytics without batch ETL lag."
datePublished: "2025-01-18"
dateModified: "2025-01-18"
tags: ["Data Engineering", "Analytics", "CDC", "Kafka"]
keywords: "CDC streaming warehouse, Debezium Kafka, change data capture analytics, Snowflake streaming ingestion, database replication warehouse"
faq:
  - q: "What is CDC and why stream it to a warehouse?"
    a: "Change Data Capture reads database transaction logs (WAL/binlog) and emits insert, update, and delete events. Streaming CDC to a warehouse gives analytics tables that lag seconds behind production instead of hours with nightly batch ETL. Dashboards, ML features, and operational analytics stay current."
  - q: "Debezium vs batch ETL — when to use each?"
    a: "Use CDC streaming when you need near-real-time data, want to capture deletes and updates (not just snapshots), or have high-change tables where full extracts are expensive. Batch ETL remains fine for low-change reference data, third-party sources without CDC, and historical backfills."
  - q: "How do I handle schema changes in CDC pipelines?"
    a: "Debezium emits schema change events when columns are added or types change. Use a schema registry (Confluent Schema Registry or AWS Glue) to version Avro/Protobuf schemas. Downstream consumers and warehouse loaders must handle additive schema changes gracefully — never drop columns without a migration plan."
---

The nightly ETL job finishes at 6 AM with yesterday's data. By 10 AM, product asks for today's conversion metrics. By noon, you're manually querying production (bad) or telling them to wait until tomorrow (worse). Change Data Capture streaming pushes every insert, update, and delete from your operational database to the warehouse in seconds — analytics that reflect reality, not yesterday's snapshot.

## CDC pipeline architecture

```
Postgres WAL → Debezium → Kafka → Stream processor → Warehouse
                                     ↓
                              Schema Registry
```

Each component has a distinct job:
- **Debezium:** Reads DB transaction log, produces change events
- **Kafka:** Durable buffer, decouples source from sink
- **Stream processor:** Transforms, deduplicates, routes (Flink, ksqlDB, or custom)
- **Warehouse loader:** Snowpipe, BigQuery streaming, or MERGE jobs

## Debezium Postgres connector

```json
{
  "name": "orders-connector",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "postgres.prod.internal",
    "database.port": "5432",
    "database.user": "debezium",
    "database.password": "${secrets:debezium_password}",
    "database.dbname": "app",
    "topic.prefix": "cdc",
    "table.include.list": "public.orders,public.order_items",
    "plugin.name": "pgoutput",
    "publication.name": "debezium_pub",
    "slot.name": "debezium_slot",
    "snapshot.mode": "initial"
  }
}
```

Postgres setup:

```sql
CREATE PUBLICATION debezium_pub FOR TABLE orders, order_items;

CREATE USER debezium WITH REPLICATION PASSWORD '...' LOGIN;
GRANT SELECT ON orders, order_items TO debezium;
```

Debezium creates a replication slot — monitor slot lag; a stalled consumer causes WAL accumulation and disk fill.

## Event format

Debezium emits change events:

```json
{
  "op": "c",
  "before": null,
  "after": {
    "id": "ord_123",
    "customer_id": "cust_456",
    "total_cents": 9999,
    "status": "pending",
    "updated_at": 1704067200000
  },
  "source": {
    "table": "orders",
    "lsn": 12345678
  }
}
```

`op`: c=create, u=update, d=delete, r=read (snapshot).

## Loading into Snowflake

Snowpipe with Kafka connector, or MERGE from staging:

```sql
MERGE INTO analytics.orders AS target
USING staging.orders_cdc AS source
ON target.id = source.id
WHEN MATCHED AND source.op = 'd' THEN DELETE
WHEN MATCHED AND source.op = 'u' THEN UPDATE SET
    customer_id = source.customer_id,
    total_cents = source.total_cents,
    status = source.status,
    updated_at = source.updated_at
WHEN NOT MATCHED AND source.op = 'c' THEN INSERT
    (id, customer_id, total_cents, status, updated_at)
    VALUES (source.id, source.customer_id, source.total_cents,
            source.status, source.updated_at);
```

Handle deletes explicitly — batch ETL often misses them.

## BigQuery streaming alternative

```sql
-- Streaming insert from Dataflow/Datastream
INSERT INTO analytics.orders
SELECT * FROM EXTERNAL_QUERY(...)

-- Or use BigQuery CDC preview with Datastream
```

Google Datastream is managed CDC for Postgres/MySQL → BigQuery.

## Schema evolution

Register schemas with Confluent Schema Registry:

```json
{
  "type": "record",
  "name": "Order",
  "fields": [
    { "name": "id", "type": "string" },
    { "name": "total_cents", "type": "long" },
    { "name": "discount_code", "type": ["null", "string"], "default": null }
  ]
}
```

When adding `discount_code`:
1. Deploy DB migration (add nullable column)
2. Debezium emits schema change event
3. Registry registers new schema version
4. Warehouse adds column (nullable)
5. Deploy consumer that reads new field

Never rename or drop columns without a multi-phase migration.

## Monitoring

| Metric | Alert |
|--------|-------|
| Replication slot lag (bytes) | > 1 GB |
| Kafka consumer lag | > 10,000 messages |
| Event processing latency p95 | > 60 seconds |
| Schema registry compatibility failures | Any |
| Warehouse load errors | Any |

## Operational gotchas

- **Replication slot bloat:** Stopped consumer → WAL grows → disk full → production down. Monitor aggressively.
- **Snapshot on large tables:** Initial snapshot locks or slows production. Use `snapshot.mode=never` with a separate backfill for existing data.
- **TOAST columns in Postgres:** Large text/jsonb values may appear as unavailable in WAL — configure `column.truncate.to` or use logical decoding options.
- **Ordering:** Events for the same row key should land in the same Kafka partition (key by primary key).

Pair with [Postgres logical replication fundamentals](https://blog.michaelsam94.com/postgres-logical-replication-cdc/) for the database-side setup.

## Backfill vs streaming coordination

Initial CDC snapshots and ongoing streaming must converge without duplicates or gaps:

1. **Snapshot phase** — Debezium exports table state at `SCN` or LSN `L0`
2. **Streaming phase** — events after `L0` flow continuously
3. **Validation** — row counts and checksums match between source and warehouse at cutover

For large tables, avoid blocking snapshots during business hours. Run `snapshot.mode=initial_only` on a replica, or use incremental snapshot (Debezium 2.x) that chunks by primary key without long locks.

```sql
-- Warehouse reconciliation query (run nightly)
SELECT s.id, s.updated_at AS source_ts, w.updated_at AS warehouse_ts
FROM source.orders s
LEFT JOIN warehouse.orders w ON s.id = w.id
WHERE w.id IS NULL OR s.updated_at > w.updated_at + interval '5 minutes';
```

Discrepancies usually mean consumer lag, poison messages, or a schema change that failed silently.

## Exactly-once semantics in practice

True exactly-once end-to-end is rare. Aim for **effectively-once**:

- Kafka: idempotent producer + transactional writes
- Warehouse: merge by primary key (`MERGE INTO` in Snowflake, `INSERT ... ON CONFLICT` in Postgres)
- Deletes: tombstone events or explicit `op=delete` with full row key

Track `source_lsn` or `source_ts_ms` on every warehouse row. Reprocessing the same event twice should produce identical state, not double counts.

## Cost and latency tradeoffs

| Pattern | Latency | Cost | Best for |
|---------|---------|------|----------|
| Kafka → stream processor → warehouse | Seconds | Medium | Real-time dashboards |
| Kafka → Snowpipe streaming | 1–5 min | Low per row | Analytics |
| Batch ETL nightly | Hours | Lowest | Historical reporting |
| Materialized views on replica | Minutes | DB load | Small teams, < 1 TB |

Micro-batching (100–500 events) reduces warehouse load costs dramatically compared to per-row inserts. Tune batch size against freshness SLO — finance often accepts 5-minute lag; fraud detection may not.

## Production checklist

- [ ] Replication slot lag alert at 1 GB WAL
- [ ] Merge/upsert idempotency on warehouse loads
- [ ] Schema registry compatibility checked in CI
- [ ] Nightly reconciliation query between source and warehouse
- [ ] Initial snapshot scheduled off-peak or on replica

## Resources

- [Debezium documentation](https://debezium.io/documentation/reference/stable/)
- [PostgreSQL logical replication](https://www.postgresql.org/docs/current/logical-replication.html)
- [Snowflake Snowpipe streaming](https://docs.snowflake.com/en/user-guide/data-load-snowpipe-streaming)
- [Google Datastream for BigQuery](https://cloud.google.com/datastream/docs)
- [Confluent Schema Registry](https://docs.confluent.io/platform/current/schema-registry/index.html)
