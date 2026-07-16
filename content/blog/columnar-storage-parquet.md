---
title: "Columnar Storage with Parquet"
slug: "columnar-storage-parquet"
description: "How Parquet columnar layout speeds analytics queries: row groups, compression codecs, schema evolution, and read patterns in Spark and DuckDB."
datePublished: "2025-03-19"
dateModified: "2025-03-19"
tags: ["Data Engineering"]
keywords: "Apache Parquet, columnar storage, row groups, Snappy compression, schema evolution, data lake"
faq:
  - q: "Why is Parquet faster than CSV for analytics?"
    a: "Parquet stores data column-by-column with type metadata and statistics per row group. A query selecting three columns from a table with fifty columns reads only those three columns from disk—often 10–50x less I/O than CSV row scans. Built-in compression (Snappy, ZSTD, dictionary encoding) further reduces size and decode cost."
  - q: "What row group size should I use?"
    a: "Target 128 MB to 512 MB uncompressed row groups for object storage workloads. Smaller groups increase metadata overhead and reduce compression efficiency; larger groups hurt predicate pushdown granularity and memory use during reads. Spark's default 128 MB is a reasonable starting point; tune with your typical query selectivity."
  - q: "How does Parquet handle schema changes?"
    a: "Parquet supports schema evolution: add columns with defaults, widen types in some engines, and rename via field aliases in Spark. Removed columns remain readable in old files. Writers must not change column order or types incompatibly without a migration job rewriting files."
---

CSV on S3 is the gateway drug of data lakes—easy to write, painful to query at scale. The first `SELECT avg(price) FROM sales` that scans 500 GB of text files convinces teams to adopt Parquet. Columnar layout is not magic; it is a bet that analytics workloads read subsets of columns across many rows, and that bet pays off almost every time for warehouse-style queries.

## How Parquet lays out data

A Parquet file is a footer-driven columnar format:

1. **Row groups** — horizontal partitions of rows (typically 128 MB each)
2. **Column chunks** — one per column per row group, compressed independently
3. **Pages** — subdivisions within column chunks with their own encodings
4. **Footer metadata** — schema, row group locations, column statistics (min, max, null count)

```
File
├── Row Group 0
│   ├── Column: user_id   (RLE + dictionary encoded)
│   ├── Column: event_time (DELTA_BINARY_PACKED)
│   └── Column: amount     (PLAIN)
├── Row Group 1
│   └── ...
└── Footer (schema + statistics)
```

Readers load the footer first, apply predicate pushdown using column statistics, and skip row groups or pages that cannot match the WHERE clause.

## Writing Parquet well

**Pick encodings the data supports.** Low-cardinality strings (country codes, status enums) compress dramatically with dictionary encoding. High-cardinality UUIDs do not—use plain encoding and ZSTD.

**Sort before write when possible.** Sorting by a common filter column (`event_date`, `tenant_id`) co-locates similar values, improving dictionary efficiency and min/max statistics for pruning.

Spark example with sensible defaults:

```python
df.write \
  .option("compression", "zstd") \
  .option("parquet.block.size", 134217728) \
  .partitionBy("event_date") \
  .mode("overwrite") \
  .parquet("s3://lake/events/")
```

Hive-style partitioning (`event_date=2025-03-01/`) prunes at the directory level before opening files. Combine partition keys with in-file row group statistics for two-level pruning.

## Reading efficiently

**Project only needed columns.** In Spark, `select("user_id", "amount")` before heavy joins. In DuckDB, column pruning is automatic:

```sql
SELECT user_id, sum(amount)
FROM read_parquet('s3://lake/events/**/*.parquet')
WHERE event_date >= '2025-03-01'
GROUP BY user_id;
```

**Avoid small files.** Thousands of 1 MB Parquet files destroy listing performance and prevent efficient vectorized reads. Compact with `OPTIMIZE` (Delta/Iceberg) or a scheduled `coalesce` job targeting 256 MB files.

**Use appropriate split sizing.** Spark's `spark.sql.files.maxPartitionBytes` controls parallelism vs overhead per file.

## Schema evolution in practice

Adding a nullable column is safe—new files include it, old files return NULL:

```python
# New pipeline version adds `device_type`
df.withColumn("device_type", lit(None).cast("string")) \
  .write.parquet(path, mode="append")
```

Renaming columns without rewriting files requires metadata aliases in Spark 3+:

```python
spark.read.option("mergeSchema", "true") \
  .parquet(path) \
  .withColumnRenamed("old_name", "new_name")
```

Changing `Int32` to `String` or reordering columns breaks readers—plan migrations that rewrite affected partitions.

## Parquet vs ORC vs Avro

| Format | Strength | Weak spot |
|--------|----------|-----------|
| Parquet | Broad ecosystem, nested types, stats | Write-heavy small updates |
| ORC | Hive integration, similar columnar wins | Less adoption outside Hadoop |
| Avro | Row-oriented, schema in every file | Analytics scans read all columns |

Parquet won the lake format war for cold analytics storage. Avro still fits Kafka → lake ingestion before compaction to Parquet.

## Common production mistakes

**Storing nested JSON as a single string column.** You lose column pruning on inner fields. Use Parquet nested types (`struct`, `list`, `map`) or flatten to top-level columns.

**No statistics on filtered columns.** If `amount` has incorrect min/max because of write bugs, predicate pushdown skips valid row groups. Validate stats after pipeline changes.

**Uniform compression everywhere.** ZSTD level 9 on already-small dimension tables adds CPU at read time for marginal size gain. Snappy or ZSTD level 1–3 for interactive workloads.

## Tooling checklist

- **DuckDB** — local and S3 Parquet queries without a cluster
- **PyArrow** — read/write with fine-grained encoding control
- **parquet-tools** — inspect schema, row groups, footers from CLI

```bash
parquet-tools meta file.parquet
parquet-tools dump --column amount file.parquet
```

Choose row group size 128MB for analytics workloads — smaller groups increase metadata overhead, larger groups hurt predicate pushdown granularity.

## Partitioning and file layout

Organize Parquet files for query patterns:

```
s3://lake/orders/year=2026/month=01/day=15/part-00000.parquet
```

Hive-style partitioning enables partition pruning — query with `WHERE year=2026 AND month=01` reads only January files. Target 128–512 MB per file; smaller files increase metadata overhead, larger files reduce parallelism.

## Compression codec selection

| Codec | Ratio | CPU | Best for |
|-------|-------|-----|----------|
| Snappy | Moderate | Low | Interactive queries |
| ZSTD | High | Medium | Cold storage, archival |
| GZIP | High | High | Legacy compatibility |

Benchmark on your data — text-heavy columns compress 5–10×, already-compressed JSON inside strings barely compresses.

## Schema evolution in production

```python
# PyArrow safe column add
table = pq.read_table("old.parquet")
new_table = table.append_column("discount_code", pa.array([None] * len(table)))
pq.write_table(new_table, "new.parquet")
```

Never remove or rename columns without dual-write migration — downstream Spark jobs break on missing columns mid-pipeline.

Pair with [data lakehouse Iceberg](https://blog.michaelsam94.com/data-lakehouse-iceberg/) when you need ACID transactions over Parquet tables.

## Compaction and incremental pipelines

Micro-batch writers (Kafka → Flink, Kinesis → Lambda) produce **small-file churn** unless you schedule compaction. A nightly job that reads the last 24 hours of partitions, `repartition(N)` to target file size, and overwrites atomically (via Iceberg/Delta commit or S3 swap prefix) keeps listing latency flat as data volume grows.

For incremental ETL, track **watermarks** in a side table: last processed `event_time`, file paths touched, row counts. After compaction, update the watermark only when the new files pass row-count reconciliation against source. Skipping this step causes silent double-counting when a failed job retries mid-partition.

Register Parquet datasets in a catalog (Glue, Unity Catalog, Hive Metastore) so engines share schema and partition discovery. Raw S3 paths without catalog metadata force every query engine to list prefixes independently — that becomes your bottleneck before CPU.

## Resources

- [Apache Parquet format specification](https://parquet.apache.org/docs/)
- [Parquet encoding documentation](https://parquet.apache.org/docs/file-format/data-pages/encodings/)
- [DuckDB Parquet reading guide](https://duckdb.org/docs/data/parquet/overview)
- [Spark Parquet configuration](https://spark.apache.org/docs/latest/sql-data-sources-parquet.html)
