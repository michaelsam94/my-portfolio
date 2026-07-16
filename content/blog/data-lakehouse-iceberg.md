---
title: "The Lakehouse with Apache Iceberg"
slug: "data-lakehouse-iceberg"
description: "Apache Iceberg brings ACID transactions and time travel to object storage. Table format internals, compaction, hidden partitioning, and when it beats Hive tables."
datePublished: "2025-07-17"
dateModified: "2025-07-17"
tags: ["Data Engineering", "Analytics"]
keywords: "Apache Iceberg, lakehouse, data lake, ACID, time travel, Spark, Trino, table format"
faq:
  - q: "What problem does Apache Iceberg solve?"
    a: "Iceberg adds relational table semantics — ACID commits, schema evolution, hidden partitioning, and snapshot isolation — on top of cheap object storage like S3. It replaces fragile Hive-style directory tables where concurrent writers corrupt data and renames require full rewrites."
  - q: "How is Iceberg different from Delta Lake or Hudi?"
    a: "All three are open table formats with similar goals. Iceberg emphasizes vendor-neutral spec, hidden partitioning, and metadata tree design that avoids listing entire directories. Engine support spans Spark, Flink, Trino, Snowflake external tables, and more. Choice often depends on existing stack and engine maturity in your environment."
  - q: "When should I migrate existing Parquet datasets to Iceberg?"
    a: "Migrate when you need concurrent writers, row-level deletes/updates, time travel for audits, or safe schema changes without rewriting terabytes. Batch-only append pipelines on static Parquet may not justify migration cost until operational pain — failed partitions, manual compaction, inconsistent reads — accumulates."
---

Object storage is cheap; treating it like a database without a table format is expensive. I've debugged too many "the job succeeded but half the partition is missing" incidents caused by non-atomic directory writes on S3. Apache Iceberg is the layer that makes a data lake behave like a warehouse — without giving up Parquet files and open engines.

## Lake vs lakehouse in one sentence

A **data lake** stores files. A **lakehouse** stores **tables** — versioned, queryable units with metadata that engines agree on. Iceberg is the metadata and commit protocol; Parquet (or ORC) remains the row storage.

## Table layout under the hood

Iceberg separates **data files** from **metadata files**:

```
warehouse/events/
  metadata/
    v1.metadata.json
    v2.metadata.json
    snap-123.avro
  data/
    year=2025/month=07/part-00001.parquet
```

Each commit writes a new metadata pointer atomically. Readers always see a consistent snapshot — never a half-written partition. The catalog (Glue, REST, Hive Metastore, Nessie) stores the current metadata location.

```sql
-- Spark: create and query
CREATE TABLE prod.events (
  event_id STRING,
  occurred_at TIMESTAMP,
  payload STRING
) USING iceberg
PARTITIONED BY (days(occurred_at));

SELECT * FROM prod.events FOR SYSTEM_TIME AS OF TIMESTAMP '2025-07-01 00:00:00';
```

Time travel reads historical snapshots without maintaining duplicate tables.

## Hidden partitioning

Hive forced partition columns into query predicates (`WHERE year=2025 AND month=7`). Iceberg **hidden partitioning** transforms values at write time — `days(occurred_at)` — and tracks transforms in metadata. Analysts filter on `occurred_at` directly; the optimizer prunes files automatically.

Change partition spec without rewriting all data — add a new transform, migrate gradually. That alone saves weeks on evolving event pipelines.

## Writes, merges, and compaction

Iceberg supports row-level **MERGE INTO**, **DELETE**, and **UPDATE** on open engines. Small files accumulate from streaming ingest; schedule **compaction** jobs that rewrite data files into optimal sizes:

```sql
CALL prod.system.rewrite_data_files(
  table => 'prod.events',
  options => map('min-input-files', '50')
);
```

**Expire snapshots** to reclaim storage after retention windows. **Remove orphan files** after failed writes. Operational maturity means automating these — not running them manually when queries slow down.

## Engine ecosystem

| Engine | Typical role |
|---|---|
| Spark | Batch ETL, compaction, MERGE |
| Flink | Streaming upserts into Iceberg |
| Trino / Presto | Interactive analytics |
| DuckDB | Local inspection and tests |
| Snowflake / BigQuery | External / managed Iceberg reads |

The format spec is engine-neutral — avoid lock-in to a single vendor's table implementation while still using their compute.

## Migration path from raw Parquet

1. Register existing files as an Iceberg table via `migrate` or snapshot procedures
2. Enable double-write: legacy path + Iceberg for one release cycle
3. Point downstream Spark/Trino jobs at Iceberg catalog
4. Retire Hive partition layout after validation

Validate row counts and checksums per snapshot. Iceberg's audit log (`history`, `snapshots` metadata tables) helps prove parity.

## When Iceberg isn't worth it yet

Tiny datasets, single-writer batch dumps, teams with no Spark/Flink ops — the operational surface (catalog HA, compaction, snapshot retention) has cost. Managed offerings (Tabular, AWS S3 Tables, Databricks UniForm) offload ops if you accept vendor coupling.

## Catalog selection and HA

The catalog is the source of truth for table metadata — if it fails, reads and writes stop:

| Catalog | HA approach | Best for |
|---|---|---|
| REST (Tabular, Polaris) | Managed service | Production without self-hosting |
| Hive Metastore | Single point of failure unless HA pair | Legacy Hadoop shops |
| AWS Glue | Managed, regional | AWS-native stacks |
| Nessie | Git-like branching for tables | CI/CD for data, dev/prod isolation |

```sql
-- Nessie: create dev branch, test schema change, merge to main
CALL nessie.createBranch('dev-feature', 'main');
-- writers target dev-feature branch
-- after validation: merge dev-feature → main
```

For production, use managed catalog (Tabular, Glue) or Nessie with HA deployment — not a single Hive Metastore instance.

## Compaction and file layout maintenance

Iceberg tables accumulate small files from streaming writes. Schedule regular compaction:

```sql
-- Spark: rewrite small files into optimal size
CALL catalog.system.rewrite_data_files(
    table => 'db.events',
    options => map('target-file-size-bytes', '134217728')  -- 128MB
);

-- Remove orphan files after failed writes
CALL catalog.system.remove_orphan_files(table => 'db.events', older_than => TIMESTAMP '2024-01-01');
```

Monitor `files_count` and `total_size` per table via Iceberg metadata tables. Alert when average file size drops below 10MB — compaction overdue.

## Time travel and audit queries

Every write creates a snapshot — query historical state without backups:

```sql
-- Query table as it existed yesterday
SELECT * FROM db.events FOR SYSTEM_TIME AS OF TIMESTAMP '2024-12-26 00:00:00';

-- List all snapshots
SELECT * FROM db.events.snapshots ORDER BY committed_at DESC;

-- Rollback to previous snapshot (metadata operation, instant)
CALL catalog.system.rollback_to_snapshot('db.events', 1234567890);
```

Useful for debugging data pipeline regressions — compare row counts between snapshots without restoring from backup.

## Failure modes

- **Catalog single point of failure** — all reads/writes blocked; use HA catalog
- **No compaction scheduled** — thousands of tiny files; query performance degrades
- **Snapshot retention unbounded** — storage cost grows; set retention policy
- **Schema evolution without compatibility check** — breaking change breaks downstream jobs
- **Concurrent writers without conflict handling** — optimistic concurrency failures

## Production checklist

- HA catalog (managed or Nessie cluster)
- Compaction scheduled (daily for streaming tables)
- Orphan file cleanup scheduled weekly
- Snapshot retention policy configured (e.g., keep 30 days)
- Row count validation after migration from raw Parquet
- Time travel tested for audit/debug workflows

Schedule compaction during low-traffic windows and monitor file count per table — query planners degrade sharply above 10,000 small files per partition even with metadata caching enabled.

## Resources

- [Apache Iceberg documentation](https://iceberg.apache.org/docs/latest/)
- [Iceberg spec — Table metadata and snapshots](https://iceberg.apache.org/spec/)
- [Tabular — Iceberg maintenance guide](https://docs.tabular.io/)
- [Trino — Iceberg connector](https://trino.io/docs/current/connector/iceberg.html)
- [Netflix tech blog — Apache Iceberg at Netflix](https://netflixtechblog.com/)
