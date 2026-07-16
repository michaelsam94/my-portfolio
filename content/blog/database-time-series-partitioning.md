---
title: "Time-Series Partitioning Patterns"
slug: "database-time-series-partitioning"
description: "Time-series data overwhelms single tables without partitioning. Native Postgres partitioning, TimescaleDB hypertables, retention, and compression strategies."
datePublished: "2025-09-15"
dateModified: "2025-09-15"
tags: ["Backend", "Databases", "Architecture"]
keywords: "time series partitioning, TimescaleDB, PostgreSQL partition, retention policy, hypertable, IoT metrics storage"
faq:
  - q: "Why partition time-series data by time?"
    a: "Time-series workloads append mostly recent data and query narrow time windows. Partitioning by day or month enables partition pruning on scans, cheap retention via DROP PARTITION, and parallel maintenance. Without partitioning, indexes and vacuum on monolithic tables degrade as history grows."
  - q: "What is the best partition interval for metrics data?"
    a: "Match interval to ingest volume and query patterns — hourly for high-cardinality IoT bursts, daily for application metrics, monthly for low-volume logs. Target partition sizes roughly 100MB–1GB. Too granular creates small-file overhead; too coarse slows drops and compactions."
  - q: "How does TimescaleDB differ from native PostgreSQL partitioning?"
    a: "TimescaleDB builds hypertables atop Postgres with automatic chunk management, compression policies, continuous aggregates, and retention jobs. Native Postgres declarative partitioning achieves similar goals with more manual DDL. Timescale adds time-series ergonomics; vanilla Postgres suffices for moderate scale."
---

Metrics tables grow forever unless you plan for the day `SELECT` over last hour requires scanning eight years of indexes. Time-series partitioning isn't optional at scale — it's how you keep drops and queries bounded.

## Declarative partitioning in PostgreSQL

```sql
CREATE TABLE metrics (
  device_id   INT NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  value       DOUBLE PRECISION,
  PRIMARY KEY (device_id, recorded_at)
) PARTITION BY RANGE (recorded_at);

CREATE TABLE metrics_2025_07 PARTITION OF metrics
  FOR VALUES FROM ('2025-07-01') TO ('2025-08-01');

CREATE TABLE metrics_2025_08 PARTITION OF metrics
  FOR VALUES FROM ('2025-08-01') TO ('2025-09-01');
```

Queries with time bounds prune old partitions:

```sql
SELECT avg(value) FROM metrics
WHERE recorded_at >= '2025-07-15' AND recorded_at < '2025-07-16';
```

Automate partition creation with pg_partman or cron DDL.

## Retention via drop

Hard delete on billion-row tables is painful. Partition drop is O(metadata):

```sql
DROP TABLE metrics_2024_01;  -- instant retention
```

Align retention policy to compliance — 90 days hot, 1 year warm archive, then drop or export to S3 Parquet.

## Composite partition keys

High device count + time — sub-partition or hash(device_id) within time chunk:

```sql
-- TimescaleDB space partition by device_id
SELECT create_hypertable('metrics', 'recorded_at',
  partitioning_column => 'device_id',
  number_partitions => 4);
```

Prevents single daily partition from becoming terabyte monster.

## TimescaleDB hypertables

```sql
CREATE TABLE metrics (
  time        TIMESTAMPTZ NOT NULL,
  device_id   INT,
  temperature DOUBLE PRECISION
);
SELECT create_hypertable('metrics', 'time');

SELECT add_compression_policy('metrics', INTERVAL '7 days');
SELECT add_retention_policy('metrics', INTERVAL '90 days');
```

Compression columnstore-style on cold chunks — 90%+ storage savings typical for repetitive metrics.

**Continuous aggregates** precompute rollups:

```sql
CREATE MATERIALIZED VIEW metrics_hourly
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 hour', time) AS bucket,
       device_id,
       avg(temperature) AS avg_temp
FROM metrics
GROUP BY bucket, device_id;
```

## Index strategy

Index `(device_id, recorded_at DESC)` for "latest N readings per device." Avoid indexing only `recorded_at` on high-cardinality multi-tenant data.

BRIN indexes on `recorded_at` for append-only low-selectivity scans — tiny index size.

## Ingest patterns

Batch inserts per partition window — COPY beats row-by-row. Buffer recent writes in memory queue flush every N seconds.

Out-of-order timestamps crossing partition boundaries need tolerant routing — Timescale handles; native Postgres requires correct partition or default partition catch-all.

## Query anti-patterns

`SELECT * FROM metrics WHERE device_id = 1` without time filter — scans all partitions. Enforce max time range in API layer.

Global aggregates across all history — pre-aggregate to hourly/daily tables; don't scan raw seconds granularity.

## Tiered storage

Hot SSD partitions recent week; detach old partitions to cheaper tablespaces or export:

```sql
ALTER TABLE metrics_2024_06 SET TABLESPACE slow_storage;
```

Or ETL to warehouse for long-term analytics; OLTP retention stays short.

## When not to partition

Sub-million row tables — operational overhead exceeds benefit. Single-tenant apps with modest log volume — simple indexed table + periodic archive job.

Partition when vacuum time, index size, or retention drops hurt ops metrics.

## Partition management automation

Manual partition creation doesn't scale. Automate with pg_partman or scheduled DDL:

```sql
-- pg_partman setup
SELECT partman.create_parent(
  p_parent_table => 'public.metrics',
  p_control => 'recorded_at',
  p_type => 'native',
  p_interval => 'daily',
  p_premake => 7  -- create 7 days ahead
);

-- Retention: drop partitions older than 90 days
UPDATE partman.part_config
SET retention = '90 days', retention_keep_table = false
WHERE parent_table = 'public.metrics';
```

For native Postgres without pg_partman, cron job:

```sql
-- Run daily: create tomorrow's partition
CREATE TABLE IF NOT EXISTS metrics_2025_07_17 PARTITION OF metrics
  FOR VALUES FROM ('2025-07-17') TO ('2025-07-18');
```

Miss a day and inserts fail with "no partition found" — monitor partition existence as an alert.

## Monitoring partition health

Metrics worth tracking:

| Metric | Alert threshold | Why |
|---|---|---|
| Partition count | >365 daily partitions without retention | Retention policy not running |
| Largest partition size | >10GB for daily | Consider sub-partitioning |
| Insert rate per partition | Sudden 10× spike | Hot device or attack |
| Query scan count | Full partition scan without time filter | Missing WHERE on recorded_at |
| Vacuum duration | Increasing trend | Partition too large or bloat |

```sql
-- Find queries scanning all partitions
SELECT query, calls, mean_exec_time
FROM pg_stat_statements
WHERE query LIKE '%metrics%' AND query NOT LIKE '%recorded_at%'
ORDER BY mean_exec_time DESC;
```

## IoT and high-cardinality patterns

IoT metrics often have millions of devices × multiple sensors:

```sql
-- Composite: time partition + hash sub-partition on device_id
CREATE TABLE sensor_readings (
  device_id INT NOT NULL,
  sensor_type TEXT NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  value DOUBLE PRECISION
) PARTITION BY RANGE (recorded_at);

-- Daily time partitions, each sub-partitioned by device_id hash
CREATE TABLE sensor_readings_2025_07_17 PARTITION OF sensor_readings
  FOR VALUES FROM ('2025-07-17') TO ('2025-07-18')
  PARTITION BY HASH (device_id);
```

Prevents a single daily partition from becoming terabytes when device count scales.

## Default partition catch-all

Out-of-order timestamps or timezone bugs send data to wrong partition:

```sql
CREATE TABLE metrics_default PARTITION OF metrics DEFAULT;
```

Monitor default partition row count — growing default partition means partition routing is broken. Alert on `SELECT count(*) FROM metrics_default > 0`.

## Failure modes

- **Missing partition for tomorrow** — insert failures at midnight UTC; automate premake
- **Queries without time filter** — full table scan across all partitions; enforce in API layer
- **Retention job fails silently** — disk fills over months; alert on partition count
- **Wrong partition interval** — daily partitions with 10GB/day each; switch to hourly
- **Out-of-order ingest** — IoT devices with clock drift send data to wrong partition; use default partition + reorder job

## Production checklist

- Partition interval matched to ingest volume (target 100MB–1GB per partition)
- Automated partition creation (pg_partman or cron DDL)
- Retention policy configured and monitored
- Default partition monitored for routing failures
- Queries enforce time range filter at API layer
- BRIN index on recorded_at for append-only scans
- Compression enabled on cold partitions (TimescaleDB or manual)

## Resources

- [PostgreSQL — Table Partitioning](https://www.postgresql.org/docs/current/ddl-partitioning.html)
- [TimescaleDB documentation](https://docs.timescale.com/)
- [pg_partman extension](https://github.com/pgpartman/pg_partman)
- [AWS — Time-series best practices for Timestream](https://docs.aws.amazon.com/timestream/latest/developerguide/best-practices.html)
- [InfluxDB — Time series data layout](https://docs.influxdata.com/influxdb/v2/reference/internals/storage-engine/)
