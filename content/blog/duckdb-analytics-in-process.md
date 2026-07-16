---
title: "In-Process Analytics with DuckDB"
slug: "duckdb-analytics-in-process"
description: "Run fast analytical SQL inside your app with DuckDB: embedded OLAP, Parquet and CSV ingestion, Python and Node bindings, and when to skip a separate warehouse."
datePublished: "2025-11-13"
dateModified: "2025-11-13"
tags: ["Data Engineering", "Analytics", "SQL", "DuckDB"]
keywords: "DuckDB in-process analytics, embedded OLAP, DuckDB Python, query Parquet DuckDB, DuckDB vs SQLite analytics, local data warehouse, DuckDB Arrow"
faq:
  - q: "When should I use DuckDB instead of PostgreSQL or a cloud warehouse?"
    a: "Use DuckDB for analytical workloads on local or object-store files (Parquet, CSV) where you want columnar speed without standing up a server. Use PostgreSQL for transactional OLTP and a cloud warehouse when you need multi-user concurrency, petabyte scale, and managed ops. DuckDB excels as an embedded engine inside notebooks, CLIs, and data pipelines."
  - q: "Can DuckDB query S3 Parquet files directly?"
    a: "Yes. Install and load the httpfs extension, configure credentials, and run SELECT * FROM read_parquet('s3://bucket/path/*.parquet'). DuckDB pushes down filters and projection when possible. For production pipelines, consider caching hot partitions locally."
  - q: "How does DuckDB compare to Polars or pandas for analytics?"
    a: "DuckDB speaks SQL and integrates with both — you can run SQL on DataFrames via the Python API. Polars and pandas are DataFrame libraries; DuckDB is a query engine. Many teams use Polars for transforms and DuckDB for ad hoc SQL and joins across files without loading everything into memory."
---

Your notebook has twelve gigabytes of Parquet on disk and a question that needs a grouped aggregation across three directories. Spinning up Spark feels like bringing a forklift to carry a grocery bag; loading everything into pandas will swap your laptop to death. DuckDB is an in-process analytical database — no server daemon, no JDBC cluster — that runs columnar SQL directly on files and Arrow buffers. It has become the default answer for "I need warehouse-style queries locally or inside my pipeline" without the warehouse bill.

## Embedded OLAP architecture

DuckDB compiles SQL to vectorized execution over columnar storage. The entire engine runs inside your process:

```python
import duckdb

con = duckdb.connect()  # in-memory; or duckdb.connect("analytics.duckdb") for persistent

con.execute("""
    CREATE TABLE events AS
    SELECT * FROM read_parquet('data/events/year=2025/month=11/*.parquet')
""")

result = con.execute("""
    SELECT user_id, count(*) AS sessions, sum(revenue) AS total
    FROM events
    WHERE event_date >= '2025-11-01'
    GROUP BY user_id
    HAVING total > 100
    ORDER BY total DESC
    LIMIT 100
""").df()
```

No ETL into a remote system for exploratory work. Point DuckDB at files; it handles projection and filter pushdown into Parquet readers.

## File formats and remote storage

DuckDB reads Parquet, CSV, JSON, and Iceberg (with extensions) natively:

```python
duckdb.sql("""
    SELECT region, avg(latency_ms)
    FROM read_csv_auto('logs/*.csv', header=true)
    GROUP BY region
""")
```

For S3:

```python
con.execute("INSTALL httpfs; LOAD httpfs;")
con.execute("SET s3_region='us-east-1';")
con.execute("""
    SELECT count(*) FROM read_parquet(
        's3://my-bucket/analytics/daily/*.parquet'
    )
""")
```

Use IAM roles or explicit keys via `SET s3_access_key_id` in controlled environments — prefer instance roles in production pipelines.

## Python, Node, and CLI workflows

The Python API integrates with pandas, Polars, and PyArrow:

```python
import polars as pl

df = pl.scan_parquet("data/*.parquet")
duckdb.sql("SELECT * FROM df WHERE amount > 500").pl()  # returns Polars
```

For Node.js services that need lightweight reporting:

```javascript
const duckdb = require('duckdb');
const db = new duckdb.Database(':memory:');

db.all(`
  SELECT product_id, sum(qty) AS units
  FROM read_parquet('reports/sales.parquet')
  GROUP BY 1
`, (err, rows) => { /* ... */ });
```

The CLI (`duckdb`) is underrated for shell pipelines:

```bash
duckdb -c "COPY (SELECT * FROM 'raw/*.parquet' WHERE valid) TO 'clean/out.parquet'"
```

## When in-process beats a warehouse

| Scenario | DuckDB fit |
|----------|------------|
| Local EDA on Parquet exports | Excellent |
| CI test fixtures aggregating sample data | Excellent |
| Single-user CLI analytics tool | Excellent |
| Multi-tenant SaaS dashboard backend | Poor — use a server database |
| Real-time streaming ingestion | Poor — batch-oriented |

DuckDB supports concurrent reads within a process and limited multi-writer scenarios with persistent databases, but it is not a replacement for Postgres connection pooling across hundreds of app servers.

## Performance habits

- **Filter early** — predicates in `WHERE` push into Parquet row group skipping.
- **Avoid SELECT *** — columnar engines reward explicit column lists.
- **Use EXPLAIN** — verify whether filters hit statistics.
- **Persistent vs in-memory** — `:memory:` for ephemeral; file-backed for repeatable local datasets.
- **ATTACH multiple databases** — join across DuckDB files or attach Postgres with the postgres extension for federated queries.

```sql
ATTACH 'postgres://user:pass@localhost/oltp' AS pg (TYPE POSTGRES);
SELECT o.id, a.total
FROM pg.orders o
JOIN read_parquet('warehouse/aggregates.parquet') a ON o.id = a.order_id;
```

## DuckDB in Python data pipelines

Replace pandas for aggregations on large datasets:

```python
import duckdb

# Query Parquet directly without loading into memory
result = duckdb.sql("""
    SELECT
        date_trunc('month', order_date) AS month,
        product_category,
        SUM(revenue) AS total_revenue,
        COUNT(DISTINCT customer_id) AS unique_customers
    FROM read_parquet('data/orders/*.parquet')
    WHERE order_date >= '2024-01-01'
    GROUP BY 1, 2
    ORDER BY total_revenue DESC
""").df()  # returns pandas DataFrame
```

DuckDB handles 100GB Parquet on a laptop — pandas loads everything into RAM first. Use DuckDB for aggregation, pandas for small result manipulation.

## MotherDuck for team collaboration

MotherDuck adds cloud sharing to local DuckDB:

```python
import duckdb

# Connect to shared cloud database
con = duckdb.connect("md:my_database")
con.sql("CREATE TABLE shared_metrics AS SELECT * FROM read_parquet('s3://bucket/metrics.parquet')")

# Teammate queries same database
con2 = duckdb.connect("md:my_database")
con2.sql("SELECT * FROM shared_metrics WHERE date = '2024-12-27'").show()
```

Local DuckDB performance with cloud persistence and sharing — useful for analytics teams without warehouse budget.

## DuckDB extensions ecosystem

```sql
INSTALL httpfs; LOAD httpfs;       -- S3, GCS, HTTP Parquet
INSTALL postgres; LOAD postgres;   -- query Postgres tables
INSTALL json; LOAD json;           -- JSON file ingestion
INSTALL icu; LOAD icu;             -- locale-aware date/string ops
INSTALL spatial; LOAD spatial;     -- geospatial queries
```

Extensions load on demand — keep base install small. `httpfs` is essential for cloud Parquet; `postgres` enables federated OLTP + analytics queries without ETL.

## Failure modes

- **Loading full Parquet into pandas first** — OOM on large files; query Parquet directly
- **SELECT *** on wide Parquet files — scans all columns; specify needed columns
- **In-memory database for persistent workflows** — data lost on restart; use file-backed
- **Multi-writer concurrent access** — DuckDB not designed for hundreds of concurrent writers
- **Using DuckDB as app backend** — no connection pooling; use Postgres for multi-tenant SaaS

## Production checklist

- Parquet queried directly via `read_parquet()` (not loaded into pandas first)
- Explicit column lists in SELECT (columnar engine optimization)
- File-backed database for persistent local datasets
- httpfs extension for S3/GCS Parquet access
- EXPLAIN used to verify filter pushdown into Parquet row groups
- DuckDB used for analytics/EDA; Postgres/warehouse for production app backend

Cap DuckDB memory with `SET memory_limit` in shared services — in-process analytics without limits OOMs the host application.

## Resources

- [DuckDB documentation](https://duckdb.org/docs/)
- [DuckDB Python API](https://duckdb.org/docs/api/python/overview)
- [Reading and writing Parquet files](https://duckdb.org/docs/data/parquet/overview)
- [httpfs extension for S3 and HTTP](https://duckdb.org/docs/extensions/httpfs/s3api)
- [DuckDB vs SQLite — official comparison](https://duckdb.org/docs/guides/database_integration/sqlite)
