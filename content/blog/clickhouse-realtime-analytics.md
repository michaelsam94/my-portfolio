---
title: "Real-Time Analytics with ClickHouse"
slug: "clickhouse-realtime-analytics"
description: "Build sub-second analytics dashboards with ClickHouse: MergeTree tables, materialized views, and ingestion patterns for high-volume event streams."
datePublished: "2025-03-10"
dateModified: "2025-03-10"
tags: ["Data Engineering"]
keywords: "ClickHouse analytics, real-time dashboards, MergeTree, materialized views, event ingestion, OLAP"
faq:
  - q: "Why use ClickHouse for real-time analytics?"
    a: "ClickHouse is a column-oriented OLAP database optimized for aggregations over billions of rows with millisecond-to-second query latency. Unlike row-oriented Postgres tuned for transactional workloads, ClickHouse scans only the columns you SELECT and compresses data aggressively. It handles append-heavy event streams natively through MergeTree engine tables with time-based partitioning."
  - q: "What is the minimum viable ClickHouse schema for events?"
    a: "Start with a MergeTree table partitioned by day on an event timestamp, ordered by (tenant_id, event_type, timestamp). Include low-cardinality dimensions as Enum or LowCardinality(String) columns. Pre-aggregate hot metrics in materialized views that write to SummingMergeTree or AggregatingMergeTree target tables for dashboard queries."
  - q: "How do I ingest events without blocking writes?"
    a: "Batch inserts of 10,000–100,000 rows via Kafka engine tables, ClickHouse Cloud ingest, or application-side buffering. Avoid single-row inserts—they create too many parts and trigger expensive merges. Use async_insert settings for small batches from web servers when you cannot buffer client-side."
---

Product teams ask for "real-time dashboards" and backend engineers reach for Postgres materialized views refreshed every five minutes. That works until event volume hits a few million rows per day and the refresh job locks tables or the query planner gives up. ClickHouse is built for exactly this shape: append-only events, time-range filters, group-by aggregations, and queries that must return in under a second.

## Schema design for event streams

The default choice is `MergeTree` with a partition key on date and an order key that matches your filter patterns:

```sql
CREATE TABLE events (
    event_time DateTime64(3),
    tenant_id LowCardinality(String),
    event_type LowCardinality(String),
    user_id UUID,
    properties String  -- JSON as String; or use JSON type in 24.3+
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(event_time)
ORDER BY (tenant_id, event_type, event_time)
TTL event_time + INTERVAL 90 DAY;
```

`ORDER BY` determines data layout on disk. Queries filtering `tenant_id` and `event_type` with a time range read contiguous granules and skip everything else. Putting high-cardinality `user_id` first in the order key helps user-level queries but hurts tenant-wide rollups—pick based on your dashboard filters.

`LowCardinality(String)` stores a dictionary for columns with fewer than ~10,000 distinct values. Event names and plan tiers compress well; free-form URLs do not.

## Ingestion: Kafka engine to MergeTree

For streaming ingestion, the Kafka table engine reads from a topic and a materialized view inserts into the durable table:

```sql
CREATE TABLE events_kafka (
    event_time DateTime64(3),
    tenant_id String,
    event_type String,
    user_id UUID,
    properties String
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'broker:9092',
    kafka_topic_list = 'events',
    kafka_group_name = 'clickhouse_consumer',
    kafka_format = 'JSONEachRow';

CREATE MATERIALIZED VIEW events_mv TO events AS
SELECT * FROM events_kafka;
```

The materialized view runs on insert into the Kafka engine—events flow from topic to queryable table without a separate ETL job. Monitor `system.tables` for Kafka consumer lag.

For application-direct inserts, batch in the client:

```python
client.insert(
    "events",
    rows,
    column_names=["event_time", "tenant_id", "event_type", "user_id", "properties"],
    settings={"async_insert": 1, "wait_for_async_insert": 0},
)
```

## Pre-aggregation with materialized views

Dashboard queries that `COUNT(*)` and `GROUP BY` minute over raw events will scan millions of rows. Push aggregation into ingest:

```sql
CREATE TABLE events_hourly (
    hour DateTime,
    tenant_id LowCardinality(String),
    event_type LowCardinality(String),
    event_count UInt64
)
ENGINE = SummingMergeTree()
ORDER BY (tenant_id, event_type, hour);

CREATE MATERIALIZED VIEW events_hourly_mv TO events_hourly AS
SELECT
    toStartOfHour(event_time) AS hour,
    tenant_id,
    event_type,
    count() AS event_count
FROM events
GROUP BY hour, tenant_id, event_type;
```

Dashboard queries hit `events_hourly`—thousands of rows instead of billions. `SummingMergeTree` merges partial counts on background merge; use `sum(event_count)` in queries or `FINAL` sparingly.

For quantiles and uniq counts, use `AggregatingMergeTree` with `-State` combinators:

```sql
CREATE TABLE events_daily_state (
    day Date,
    tenant_id LowCardinality(String),
    uv AggregateFunction(uniq, UUID)
)
ENGINE = AggregatingMergeTree()
ORDER BY (tenant_id, day);
```

## Query patterns that stay fast

Always filter on partition key (`event_time` / date). ClickHouse prunes entire partitions when the WHERE clause includes the partition expression.

Avoid `SELECT *` on wide tables. Project only columns you need—columnar storage makes this a massive win.

Use `PREWHERE` for high-selectivity filters when the primary filter column is not first in ORDER BY:

```sql
SELECT event_type, count()
FROM events
PREWHERE tenant_id = 'acme'
WHERE event_time >= now() - INTERVAL 1 HOUR
GROUP BY event_type;
```

Set `max_execution_time` on dashboard connections so runaway queries fail fast instead of starving ingestion.

## Operational concerns

**Too many parts.** Small frequent inserts create parts faster than background merges combine them. Symptoms: slow queries, `Too many parts` errors. Fix: larger batches, `async_insert`, or tune `parts_to_throw_insert`.

**Replication.** Production runs `ReplicatedMergeTree` on ZooKeeper or ClickHouse Keeper. Ingest to one shard per partition key if you need ordering guarantees per tenant.

**Backfills.** Inserting historical data into past partitions triggers merges across old and new data. Schedule backfills off-peak and use `max_partitions_per_insert_block` to avoid hitting partition limits.

## When not to use ClickHouse

Transactional updates, foreign keys, and row-level locking belong in Postgres. ClickHouse `ALTER UPDATE` and `DELETE` are mutations—expensive and asynchronous. Use ClickHouse for analytics reads; keep operational state elsewhere and sync events via CDC or application dual-write.

## MergeTree engine selection

```sql
CREATE TABLE events (
  ts DateTime,
  user_id UUID,
  event String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(ts)
ORDER BY (user_id, ts);
```

ORDER BY determines primary index — queries filtering user_id + time range are fast; random access by event alone is not.

## Common production mistakes

Teams get realtime analytics wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of realtime analytics fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When realtime analytics misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [ClickHouse MergeTree engine reference](https://clickhouse.com/docs/en/engines/table-engines/mergetree-family/mergetree)
- [Materialized views guide](https://clickhouse.com/docs/en/guides/developer/cascading-materialized-views)
- [Kafka engine table](https://clickhouse.com/docs/en/engines/table-engines/integrations/kafka)
- [ClickHouse async insert](https://clickhouse.com/docs/en/optimize/asynchronous-inserts)
