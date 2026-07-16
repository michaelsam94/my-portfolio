---
title: "Partitioning and Bucketing Strategies"
slug: "data-partitioning-bucketing"
description: "Partition pruning cuts scan cost; bucketing spreads hot keys. How to choose partition columns, avoid the small-file problem, and combine both in Spark and warehouses."
datePublished: "2025-08-01"
dateModified: "2025-08-01"
tags: ["Data Engineering", "Analytics"]
keywords: "data partitioning, bucketing, Hive partitioning, partition pruning, small files, Spark bucketing"
faq:
  - q: "What is the difference between partitioning and bucketing?"
    a: "Partitioning splits data into directory-like segments by column values — often date — so queries filter to relevant subsets. Bucketing hashes rows into fixed buckets within a partition to colocate keys for efficient joins and aggregations. Partitioning helps scan pruning; bucketing helps join locality."
  - q: "How do I choose a partition column?"
    a: "Pick columns frequently used in WHERE clauses with reasonable cardinality — event_date for logs, not user_id. Aim for partitions between roughly 100MB and 1GB of data each. High-cardinality partitions create small files and metadata bloat."
  - q: "What is the small file problem?"
    a: "Too many tiny files — often from over-partitioning or streaming micro-batches — slows listing, increases metadata overhead, and hurts query planners. Fix with compaction jobs, larger batch windows, or partition coarsening (daily instead of hourly until volume warrants)."
---

Partitioning is free until it isn't. I've seen `PARTITION BY user_id` on a billion-row table turn a simple count into a forty-minute metadata crawl. Bucketing helps different problems — skewed joins — but won't save a bad partition key. The design work is matching physical layout to query patterns.

## Partitioning for prune, not organize

**Goal:** queries read only relevant files.

```sql
-- BigQuery: partition by ingestion date
CREATE TABLE analytics.events
PARTITION BY DATE(occurred_at)
AS SELECT * FROM raw.events;

-- Query prunes to one day of storage
SELECT count(*) FROM analytics.events
WHERE occurred_at >= '2025-07-01' AND occurred_at < '2025-07-02';
```

Warehouse engines push partition filters to storage layers. Missing the partition column in predicates triggers full scans — educate analysts or use require_partition_filter.

### Cardinality rules of thumb

| Column | Verdict |
|---|---|
| `event_date` (daily) | Strong default for event logs |
| `country_code` (~200 values) | OK for regional aggregates |
| `user_id` (millions) | Avoid as top-level partition |
| `status` (3 values) | Too low alone; combine with date |

**Hourly partitions** make sense at high ingest volume; at low volume they manufacture small files.

## Bucketing for join and skew

Bucketing distributes rows by hash into N fixed files per partition:

```sql
CREATE TABLE analytics.user_sessions
USING parquet
CLUSTER BY (user_id)  -- BigQuery clustering; similar intent to bucketing
AS SELECT * FROM staging.sessions;
```

Spark explicit bucketing:

```python
df.write \
  .bucketBy(64, "user_id") \
  .sortBy("user_id") \
  .saveAsTable("analytics.user_events")
```

Joins on `user_id` become bucket-to-bucket without shuffle — when both sides bucket count matches and keys align.

## Combining partition + bucket

Common pattern for clickstreams:

- **Partition** by `event_date` — daily prune
- **Bucket** by `user_id` within day — session joins

```
s3://warehouse/events/event_date=2025-07-01/
  part-00000-bucket-00.parquet
  part-00001-bucket-01.parquet
  ...
```

Iceberg and Delta hide physical layout with **hidden partitioning** and automatic file sizing — prefer them over manual Hive paths for new pipelines.

## Small files and compaction

Streaming sinks writing 128MB/hour across 24 hourly partitions → 24 tiny files/day/partition. Symptoms: slow `LIST`, planner timeouts, high $LIST costs on S3.

Mitigations:

1. **Coalesce** micro-batches before write
2. **Compaction** jobs (Iceberg rewrite, Delta optimize, `OPTIMIZE` in Databricks)
3. **Wider partitions** — daily until median file > 256MB
4. **Target file size** configs in Spark (`spark.sql.files.maxRecordsPerFile`)

Monitor files-per-partition metric; alert when median file size drops below threshold.

## Warehouse-specific notes

**Snowflake** — micro-partitions are automatic; clustering keys (`CLUSTER BY`) guide co-location. Don't overthink manual partitions.

**BigQuery** — partition + cluster is the standard combo; partition expiration for TTL.

**Redshift** — distribution keys (all nodes get rows) vs sort keys (range order within node). DISTKEY on join columns; SORTKEY on filter columns.

One-size-fits-all advice fails — read your engine's docs.

## Anti-patterns

Partitioning on nullable columns (orphan `__HIVE_DEFAULT_PARTITION__`). Partitioning cold historical data the same as hot recent data — use tiered storage or archive unpartitioned backups. Bucketing both sides with different bucket counts. Re-partitioning entire history for a query pattern one dashboard uses.

Validate with `EXPLAIN` / query profile: bytes scanned should match expectation.

## Partition evolution without full rewrite

Iceberg and Delta Lake support partition spec evolution — add or change partition columns without rewriting existing data:

```sql
-- Iceberg: add year partition to existing daily-partitioned table
ALTER TABLE events SET PARTITION SPEC (year, day);
```

Old files keep daily partitions; new writes use year+day. Queries spanning both layouts still work via metadata. Avoid rewriting terabytes when query patterns shift.

For Hive-style tables without evolution support, use **partition projection** (Athena, Trino) to synthesize partition paths without physical directories:

```sql
-- Athena partition projection — no MSCK REPAIR needed
TBLPROPERTIES (
  'projection.enabled' = 'true',
  'projection.dt.type' = 'date',
  'projection.dt.range' = '2020-01-01,NOW',
  'projection.dt.format' = 'yyyy-MM-dd'
)
```

## Cost impact of wrong partitioning

| Mistake | Cost impact |
|---|---|
| Daily partitions, query scans 365 days | 365× partition metadata overhead |
| High-cardinality partition (user_id) | Millions of tiny files, metastore bloat |
| No partition on time-filtered queries | Full table scan every query |
| Bucket count mismatch on join | Full shuffle instead of bucket join |

Run monthly partition audit: list partitions with file count and total size. Alert on partitions with >10k files or <1MB total size.

## Real-world migration path

When query patterns change (daily → hourly for recent data):

1. **Add new partition spec** for future writes (Iceberg evolution)
2. **Dual-write** to old and new layout during transition
3. **Backfill hot range** (last 90 days) to new layout in background
4. **Switch queries** to new layout with fallback to old
5. **Archive or drop** old layout after validation period

Don't rewrite entire history unless analytics team confirms need — cold data rarely queried.

## Failure modes

- **Partition column nullable** — orphan default partition catches all nulls; skews queries
- **MSCK REPAIR on large Hive table** — hours of metastore churn; use partition projection instead
- **Bucketing both sides with different counts** — bucket join fails; full shuffle
- **Over-partitioning cold data** — same granularity as hot data wastes metastore entries
- **No file compaction** — thousands of tiny files per partition; slow reads

## Production checklist

- Partition column matches primary filter in 80%+ of queries
- Low-cardinality partitions (date, region) not high-cardinality (user_id)
- File compaction scheduled (Delta OPTIMIZE, Iceberg rewrite_data_files)
- Partition evolution plan for layout changes without full rewrite
- Monthly audit: file count and size per partition
- EXPLAIN validated: bytes scanned matches expectation

Rebalance partitions before individual buckets exceed 100 GB — query planners degrade and compaction jobs miss SLA on skewed keys.

## Resources

- [Apache Spark — Bucketing](https://spark.apache.org/docs/latest/sql-data-sources-bucketing.html)
- [Google BigQuery — Partitioned tables](https://cloud.google.com/bigquery/docs/partitioned-tables)
- [Apache Iceberg — Partitioning spec evolution](https://iceberg.apache.org/docs/latest/partitioning/)
- [Snowflake — Clustering keys and micro-partitions](https://docs.snowflake.com/en/user-guide/tables-clustering-keys)
- [Databricks — Optimize writes and auto compaction](https://docs.databricks.com/en/delta/optimize.html)
