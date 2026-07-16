---
title: "Change Data Capture with Postgres Logical Replication"
slug: "postgres-logical-replication-cdc"
description: "A practical guide to change data capture with Postgres logical replication: how the WAL, replication slots, and Debezium turn changes into events."
datePublished: "2026-02-11"
dateModified: "2026-02-11"
tags: ["Backend", "Databases", "Data", "Architecture"]
keywords: "change data capture, CDC, Postgres logical replication, Debezium, WAL, replication slots, event streaming"
faq:
  - q: "What is change data capture (CDC)?"
    a: "Change data capture is a technique for detecting and streaming every insert, update, and delete on a database table as a sequence of events, without polling. In Postgres it works by reading the write-ahead log (WAL) through logical replication, so downstream systems receive an ordered, low-latency feed of row-level changes. CDC lets caches, search indexes, data warehouses, and other services stay in sync with the source database without the application explicitly publishing each change."
  - q: "How does Postgres logical replication differ from physical replication?"
    a: "Physical (streaming) replication copies the exact byte-level WAL to a standby, producing an identical binary replica used for high availability. Logical replication decodes the WAL into row-level change events described in terms of tables and columns, which can be consumed by any client and filtered per table. Logical replication is what makes CDC possible because it exposes changes as structured data rather than raw disk blocks."
  - q: "Why do replication slots matter for CDC?"
    a: "A replication slot is Postgres's bookmark that tracks how far a consumer has read in the WAL and prevents those WAL segments from being recycled until they're consumed. This guarantees no changes are lost if the consumer disconnects, but it also means an abandoned slot will hold WAL forever and can fill the disk. Monitoring slot lag and cleaning up unused slots is essential operational hygiene."
---

Change data capture turns your database into an event source. Instead of the application publishing "user updated" messages by hand — and inevitably forgetting some paths — you read Postgres's write-ahead log and get *every* insert, update, and delete as an ordered stream, automatically. That stream keeps search indexes fresh, feeds analytics warehouses, invalidates caches, and drives downstream services, all without touching the write path of your app.

I reach for CDC when a system has grown past the point where dual-writes are safe. If your code writes to Postgres and then tries to also update Elasticsearch or publish to Kafka, you have a distributed-transaction problem hiding in plain sight — one of the two writes will eventually fail and leave the systems inconsistent. CDC sidesteps that by making the database's own durable log the single source of truth.

## How Postgres logical replication actually works

Every change in Postgres is first written to the **write-ahead log (WAL)** for durability — that's how the database recovers after a crash. Physical replication ships those WAL bytes verbatim to a standby. Logical replication does something more useful for integration: it runs the WAL through a **logical decoding** plugin that reconstructs each change as a structured, row-level event — this table, this operation, these old and new column values.

Three pieces make it work:

- **`wal_level = logical`** — the server must be configured to write enough information to the WAL for logical decoding. This requires a restart, so plan for it.
- **A publication** — a named set of tables whose changes you want to stream: `CREATE PUBLICATION cdc_pub FOR TABLE orders, customers;`
- **A replication slot** — the consumer's durable bookmark into the WAL.

The slot is the part people underestimate. It guarantees that WAL segments aren't recycled until your consumer has acknowledged them, which is exactly what you want for at-least-once delivery. It's also a loaded gun: if a consumer dies and the slot is never advanced or dropped, Postgres retains WAL indefinitely and **will fill your disk**. I've seen a forgotten slot from a decommissioned pipeline take down a production primary. Monitor `pg_replication_slots` and alert on `restart_lsn` lag from day one.

## The decoding step, concretely

You can watch logical decoding directly without any external tool, which is the best way to build intuition. Using the built-in `pgoutput` or the `test_decoding` plugin:

```sql
-- One-time setup
ALTER SYSTEM SET wal_level = 'logical';  -- then restart
CREATE PUBLICATION cdc_pub FOR TABLE orders;
SELECT pg_create_logical_replication_slot('cdc_slot', 'pgoutput');

-- Peek at pending changes without consuming them
SELECT lsn, xid, data
FROM pg_logical_slot_peek_changes('cdc_slot', NULL, NULL);
```

Each row you see is a change event carrying the log sequence number (LSN), the transaction id, and the decoded data. That LSN is the ordering key for the entire stream — it's monotonic, so downstream consumers can use it to dedupe and to reason about "have I already applied this change?"

## Debezium: the production-grade consumer

Rolling your own logical decoding consumer is educational but rarely wise. [Debezium](https://debezium.io/) is the mature answer — a connector, usually run on Kafka Connect, that reads the slot and emits well-structured change events to a topic per table. A typical connector config looks like this:

```yaml
name: orders-cdc
config:
  connector.class: io.debezium.connector.postgresql.PostgresConnector
  database.hostname: pg-primary
  database.dbname: appdb
  plugin.name: pgoutput
  publication.name: cdc_pub
  slot.name: cdc_slot
  topic.prefix: appdb
  table.include.list: public.orders,public.customers
  snapshot.mode: initial
```

`snapshot.mode: initial` matters more than it looks. When a connector first starts, the WAL only contains *recent* changes — it can't replay history that's already been recycled. So Debezium takes a consistent snapshot of the existing table rows first, then switches to streaming from the slot. That snapshot-then-stream handoff is how downstream consumers get a complete picture rather than only changes that happened after the pipeline was turned on.

## Where CDC fits — and where the outbox beats it

CDC and the transactional outbox pattern overlap, and choosing between them is a real design decision. Straight CDC streams *every* column change, which is powerful but leaky — your internal schema becomes your event contract, and a column rename ripples out to every consumer. The [event-driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/) instead has the application write purpose-built domain events into an `outbox` table inside the same transaction as the business change, and CDC streams *only that table*. You get the atomicity of CDC with events you actually designed.

My rule: use raw table-level CDC for **data integration** (warehouse loads, search indexing, cache invalidation) where mirroring the schema is fine, and use the outbox-over-CDC combination for **inter-service domain events** where you want a stable, intentional contract. From either source, the events usually land in a stream processor — Kafka, or something lighter like [Redis Streams for event processing](https://blog.michaelsam94.com/redis-streams-event-processing/) when you don't need the full Kafka footprint.

## Operational realities I've learned the hard way

A short list of things that separate a demo from production CDC:

| Concern | What to do |
| --- | --- |
| Slot disk growth | Alert on WAL retained by slots; drop dead slots |
| Consumer downtime | Fine short-term (slot holds WAL); dangerous long-term |
| Schema changes | Test DDL against your decoder; some changes need care |
| Ordering | Per-table order is preserved by LSN; cross-table isn't |
| Exactly-once | It's at-least-once — consumers must be idempotent |
| Large transactions | Huge txns delay decoding; watch memory on the connector |

The two that bite hardest are slot growth and idempotency. Treat every downstream consumer as if it *will* see duplicate events, because on restart it will, and design the apply logic to be idempotent — upserts keyed by primary key plus LSN comparison rather than blind inserts.

Done carefully, CDC becomes one of the most leveraged pieces of infrastructure you can run: a single, durable, ordered feed of everything that changes in your database, from which any number of downstream systems can be built without ever touching the application's write path again. That decoupling is worth the operational diligence it demands.

## Resources

- [PostgreSQL logical replication documentation](https://www.postgresql.org/docs/current/logical-replication.html)
- [PostgreSQL logical decoding concepts](https://www.postgresql.org/docs/current/logicaldecoding.html)
- [Debezium PostgreSQL connector docs](https://debezium.io/documentation/reference/stable/connectors/postgresql.html)
- [pg_replication_slots system view](https://www.postgresql.org/docs/current/view-pg-replication-slots.html)
- [Debezium project site](https://debezium.io/)
- [Kafka Connect documentation](https://kafka.apache.org/documentation/#connect)
