---
title: "OLAP vs OLTP Workloads"
slug: "olap-vs-oltp-workloads"
description: "OLAP vs OLTP explained for engineers: workload characteristics, schema design, database choices, and why mixing analytical queries with transactional paths kills production."
datePublished: "2025-08-14"
dateModified: "2026-07-17"
tags: ["Data", "Database", "Analytics", "Architecture"]
keywords: "OLAP vs OLTP, analytical vs transactional database, data warehouse, star schema, workload isolation"
faq:
  - q: "Can one database handle both OLAP and OLTP?"
    a: "Small scale yes — PostgreSQL with read replicas or materialized views works for moderate analytics. At production scale, mixed workloads cause lock contention, unpredictable latency on writes, and expensive vertical scaling. Separate transactional stores from analytical pipelines via CDC or ETL."
  - q: "What is the main schema difference between OLTP and OLAP?"
    a: "OLTP uses normalized schemas (3NF) to minimize redundancy and preserve write integrity. OLAP uses denormalized star or snowflake schemas optimized for aggregate scans across dimensions — fact tables plus dimension tables."
  - q: "When should data move from OLTP to OLAP?"
    a: "When reporting queries scan millions of rows, require historical snapshots, or need complex joins that slow transactional traffic. Typical pattern: CDC from OLTP to warehouse within minutes (near-real-time) or nightly batch for non-urgent dashboards."
---

The checkout API p99 jumped from 80ms to 2.4 seconds after BI connected Metabase directly to production Postgres and ran `SELECT date_trunc('day', created_at), sum(total) FROM orders GROUP BY 1` during Black Friday. Same database, same tables — completely different workload shapes. OLTP optimizes for short, indexed reads and writes; OLAP optimizes for scanning millions of rows and aggregating. Treating them as interchangeable is how transactional systems die quietly under dashboard load.

## Defining the two workload types

| Dimension | OLTP (Online Transaction Processing) | OLAP (Online Analytical Processing) |
|-----------|----------------------------------------|-------------------------------------|
| Primary ops | INSERT, UPDATE, DELETE, point SELECT | SELECT aggregates, scans, joins |
| Query pattern | Short, indexed, high QPS | Long-running, batch, low QPS |
| Data freshness | Current state, milliseconds | Historical, often delayed |
| Consistency | ACID required | Eventual OK for reports |
| Users | Applications, APIs | Analysts, dashboards, ML |
| Schema | Normalized (3NF) | Denormalized (star/snowflake) |

OLTP answers: *"What's order #847291's status right now?"*
OLAP answers: *"What was revenue by region and product category for the last 36 months?"*

## OLTP design characteristics

Normalized schema reduces update anomalies:

```sql
-- OLTP: orders + order_items (3NF)
CREATE TABLE orders (
  id          BIGINT PRIMARY KEY,
  user_id     BIGINT NOT NULL REFERENCES users(id),
  status      TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE order_items (
  order_id    BIGINT REFERENCES orders(id),
  product_id  BIGINT REFERENCES products(id),
  quantity    INT NOT NULL,
  unit_price  NUMERIC(12,2) NOT NULL,
  PRIMARY KEY (order_id, product_id)
);

CREATE INDEX idx_orders_user_created ON orders(user_id, created_at DESC);
```

Properties:
- **Narrow indexes** for lookup paths
- **Row-level locking** — many concurrent writers
- **Foreign keys** enforce integrity at write time
- **Connection pooling** — thousands of short transactions

Typical engines: PostgreSQL, MySQL, CockroachDB, DynamoDB (key-value OLTP patterns).

## OLAP design characteristics

Star schema denormalizes for scan speed:

```sql
-- OLAP: fact_sales + dimensions
CREATE TABLE fact_sales (
  sale_date_key    INT,      -- FK to dim_date
  product_key      INT,      -- FK to dim_product
  store_key        INT,      -- FK to dim_store
  customer_key     INT,
  quantity         INT,
  revenue          NUMERIC(14,2),
  cost             NUMERIC(14,2)
) ENGINE = columnar;  -- BigQuery, Snowflake, ClickHouse, etc.

CREATE TABLE dim_product (
  product_key      INT PRIMARY KEY,
  sku              TEXT,
  category         TEXT,
  brand            TEXT
);
```

Analytical query:

```sql
SELECT d.year, p.category, SUM(f.revenue)
FROM fact_sales f
JOIN dim_date d ON f.sale_date_key = d.date_key
JOIN dim_product p ON f.product_key = p.product_key
WHERE d.year BETWEEN 2022 AND 2025
GROUP BY 1, 2;
```

Columnar storage reads only `revenue`, `product_key`, `sale_date_key` — not full rows. Aggregations vectorize across billions of rows.

Typical engines: Snowflake, BigQuery, Redshift, ClickHouse, DuckDB, Apache Druid.

## Why mixing workloads fails

Running OLAP on OLTP causes:

1. **Lock contention** — long SELECTs hold snapshots or block vacuum (Postgres MVCC bloat)
2. **Buffer pool pollution** — analytical scans evict hot OLTP pages from cache
3. **Unpredictable p99** — checkout latency spikes when analyst runs wide join
4. **Index mismatch** — OLTP indexes don't help aggregations; analytical indexes hurt write speed

Metabase-on-prod is the classic failure mode. Fix: read replica for BI (still imperfect at scale) or proper pipeline to warehouse.

## The modern split architecture

```
┌─────────────┐    CDC/ETL     ┌──────────────┐    SQL    ┌────────────┐
│  OLTP       │ ─────────────► │  Staging /   │ ────────► │  OLAP      │
│  Postgres   │   Debezium,    │  dbt models  │           │  Snowflake │
│             │   Fivetran     │              │           │            │
└─────────────┘                └──────────────┘           └────────────┘
      ▲                                                          │
      │ short queries                                            ▼
   Application                                              Dashboards
```

**Change Data Capture (CDC)** streams inserts/updates/deletes to warehouse without batch windows. Debezium + Kafka → Snowpipe pattern gives near-real-time OLAP without touching OLTP query paths.

**dbt** transforms raw CDC tables into star schema marts — `fact_orders`, `dim_customers` — versioned in Git.



**HTAP: when one system tries both.**

Hybrid Transaction/Analytical Processing (TiDB, SingleStore, Apache Pinot with upserts) blurs the line. Useful when:
- Team lacks pipeline ops capacity
- Data volume fits single cluster (< few TB active)
- Analytics need sub-minute freshness on narrow queries

Trade-offs: jack of both trades, expert in neither; licensing cost; harder tuning than pure-play split.

We use Postgres OLTP + ClickHouse OLAP via PeerDB sync — HTAP products weren't worth the lock-in premium at our scale.



**Choosing storage.**

| Signal | Lean OLTP | Add OLAP |
|--------|-----------|----------|
| Query scans >1M rows regularly | — | Yes |
| Dashboards hit production DB | — | Yes |
| Need point-in-time historical snapshots | — | Yes |
| All queries indexed, <100ms | Yes | — |
| ML feature store from raw events | — | Yes |
| <100GB total data, few analysts | Postgres replica maybe enough | Maybe later |



**Operational differences.**

| Concern | OLTP | OLAP |
|---------|------|------|
| Backup | Frequent, point-in-time recovery | Snapshot + incremental |
| Scaling | Vertical + read replicas + sharding | Horizontal, separate compute/storage |
| Cost driver | IOPS, connection count | Scanned bytes, warehouse uptime |
| Testing | Transaction integration tests | dbt tests, row count reconciliation |
| SLA | 99.99% availability | Best-effort refresh by 6am |

Reconcile OLTP and OLAP counts nightly — `SUM(orders.total)` in warehouse vs OLTP snapshot catches pipeline bugs before executives see wrong numbers.

Define SLAs separately: OLTP p99 latency SLOs should exclude analytical query paths entirely. When BI teams request "just one more direct query," redirect to the warehouse or a dedicated read replica with statement_timeout enforced (`SET statement_timeout = '30s'`). Reconciliation jobs comparing row counts and sum totals between OLTP snapshots and OLAP marts catch pipeline bugs before executives see them in board decks. For early-stage teams, Postgres plus nightly pg_dump to DuckDB or BigQuery may suffice — but set a growth trigger (e.g., analytical queries exceed 5% of CPU for three days) to fund proper CDC. FinOps should tag warehouse compute by team; unconstrained OLAP spend often exceeds OLTP RDS cost once analysts adopt self-serve SQL.

Never run `SELECT *` analytics against the production OLTP primary without `statement_timeout` — one analyst's cartesian join becomes everyone's checkout outage.

## Slowly changing dimensions in the warehouse

OLTP stores current customer addresses; OLAP needs history for "sales by region as-of order date." Model **SCD Type 2** in dbt:

```sql
-- dim_customer with effective dating
SELECT customer_id, region, valid_from, valid_to,
       valid_to = '9999-12-31' AS is_current
FROM dim_customer
```

Join facts on `order_date BETWEEN valid_from AND valid_to`. Getting SCD wrong inflates revenue in regions users moved away from — executives notice before engineers do.

## Query federation without killing OLTP

BI tools love "live connections." Enforce guardrails:

- Read replica with `hot_standby_feedback = on` and `max_standby_streaming_delay`
- Role `bi_readonly` with `statement_timeout = '60s'` and `idle_in_transaction_session_timeout`
- Block `pg_cancel_backend` escalation path documented for on-call

Postgres **logical replication** to a dedicated analytics instance beats letting Metabase hit the primary — slot lag becomes the metric that matters.

## Cost-aware warehouse design

Snowflake/BigQuery bills on scanned bytes. Partition fact tables by `order_date`, cluster on high-cardinality filter columns, and materialize only marts analysts query weekly. Raw CDC JSON blobs are cheap to land; letting analysts `SELECT *` on them daily is not.

## Materialized view trap on Postgres

Materialized views on OLTP DB feel like free OLAP — refresh locks or heavy IO still hurt. Use `REFRESH MATERIALIZED VIEW CONCURRENTLY` only with unique index; schedule refresh off-peak. Beyond 100GB fact data, migrate to warehouse — MV maintenance becomes ops burden.

## Analyst sandbox isolation

Give analysts read-only warehouse role, not production replica — accidental `UPDATE` via BI tool GUI happens. Snowflake `QUERY_TAG` or BigQuery labels attribute cost per team for chargeback conversations.

## Real-time analytics anti-pattern

ClickHouse materialized views fed by Kafka mimic OLAP freshness — still not OLTP. Don't route inventory holds through ClickHouse — eventual consistency sells oversold SKUs.

## CDC lag SLO

Define business SLO: dashboard data max 15 minutes behind OLTP. Alert when replication lag exceeds — executives make decisions on stale warehouse during incident if lag unnoticed.
## Reverse ETL loop guard

Hightouch/Census syncing warehouse segments back to OLTP for marketing — rate limit and validate; bad SQL in audience builder overwrites production `email_opt_in`.

## Resources

- [Ralph Kimball — The Data Warehouse Toolkit](https://www.kimballgroup.com/data-warehouse-toolkit-books/)
- [Debezium change data capture](https://debezium.io/documentation/)
- [dbt documentation — staging and marts](https://docs.getdbt.com/best-practices/how-we-structure/1-guide-overview)
- [ClickHouse vs OLTP databases](https://clickhouse.com/docs/en/intro/concepts/olap)
- [AWS — OLTP vs OLAP overview](https://aws.amazon.com/compare/the-difference-between-olap-and-oltp/)
