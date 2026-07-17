---
title: "Time-Series Databases for IoT Telemetry"
slug: "time-series-databases-iot"
description: "Choosing a time-series database for IoT telemetry: TimescaleDB vs InfluxDB, high ingest, downsampling, retention policies, cardinality traps, and real query patterns."
datePublished: "2026-01-28"
dateModified: "2026-07-17"
tags: ["IoT", "Databases", "Data", "Architecture"]
keywords: "time series database, TimescaleDB, InfluxDB, IoT telemetry, downsampling, retention policy, high ingest"
faq:
  - q: "What is a time-series database and why use one for IoT?"
    a: "A time-series database is a store optimized for data points indexed by time — measurements, events, and metrics that arrive continuously and are queried by time ranges. For IoT telemetry it beats a general-purpose database because it handles very high write rates, compresses timestamped data efficiently, and provides built-in tooling for downsampling, retention, and time-window aggregation that you would otherwise build by hand."
  - q: "Should I use TimescaleDB or InfluxDB for IoT?"
    a: "Use TimescaleDB when you want full SQL, joins with relational data, and the maturity of the Postgres ecosystem — it is Postgres with time-series superpowers. Use InfluxDB when you want a purpose-built time-series engine with a lighter operational footprint and its own query language optimized purely for metrics. The choice usually comes down to whether SQL and relational joins matter to your team."
  - q: "What is cardinality and why does it break time-series databases?"
    a: "Cardinality is the number of unique series, roughly the product of all distinct tag/label value combinations. High cardinality — for example tagging every reading with a unique request ID or raw GPS coordinate — explodes the index and memory usage, degrading both ingest and query performance. Controlling cardinality by keeping tags low-variety is the single most important tuning decision in a time-series database."
faqAnswers:
  - question: "When is time series databases iot the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for time series databases iot?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back time series databases iot safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
A fleet of a few thousand sensors reporting every few seconds will generate hundreds of millions of rows a month, all timestamped, mostly written once and queried in ranges. Throw that at a general-purpose relational database and you'll spend your life fighting index bloat and slow window queries. A time-series database is purpose-built for this shape of data: continuous, append-heavy, time-indexed telemetry that you aggregate over windows rather than look up by primary key. Picking and configuring one correctly is one of the highest-leverage decisions in an IoT backend, and it's easy to get subtly wrong in ways that only surface at scale.

I've run IoT telemetry pipelines where the database was the bottleneck and where it wasn't, and the difference was rarely raw horsepower — it was data modeling, retention discipline, and respecting cardinality. Let me walk through what actually matters.

## Why not just Postgres?

You can absolutely start with plain Postgres, and for a small deployment you should. The problems appear at scale: a single ever-growing table makes time-range queries scan too much, autovacuum struggles with the churn, and inserts contend on a giant index. Time-series databases solve this primarily through **partitioning by time** — automatically splitting data into chunks by time interval so a query for "last 24 hours" touches one small chunk, and dropping old data is a partition drop rather than a mass delete.

TimescaleDB is the honest middle path here: it *is* Postgres, extended with hypertables that do this chunking transparently. You keep SQL, joins, and every Postgres tool you know, and gain time-series performance. That's why it's my default recommendation for teams that already speak SQL and have relational data (devices, customers, sites) to join against telemetry.

## TimescaleDB vs InfluxDB, honestly

The two most common choices pull in different directions:

| Dimension | TimescaleDB | InfluxDB |
|---|---|---|
| Query language | Full SQL | Flux / InfluxQL |
| Foundation | Postgres extension | Purpose-built engine |
| Joins with relational data | Native, easy | Awkward |
| Ecosystem | Entire Postgres world | Metrics-focused tooling |
| Operational model | Run Postgres | Lighter, single-purpose |

There's no universal winner. I lean TimescaleDB when telemetry needs to join device metadata, when the team's muscle memory is SQL, and when I want one database technology instead of two. I'd consider InfluxDB when the workload is purely metrics, the team wants a dedicated metrics store, and relational joins aren't in the picture. What I'd caution against is choosing on benchmark blog posts — both are fast enough when modeled well and both fall over when modeled badly. The modeling matters more than the engine.

## The cardinality trap

The mistake that kills time-series performance isn't write volume — it's cardinality. A "series" is a unique combination of measurement plus tag values, and the database keeps an index entry per series. Tag your readings with sensible low-variety labels (`device_id`, `sensor_type`, `site`) and you have manageable cardinality. Tag them with something unbounded — a raw GPS coordinate, a per-message UUID, a full user-agent string — and cardinality explodes into the millions, index memory blows up, and everything slows down.

The rule I enforce in reviews: **tags/labels are for filtering and grouping and must be low-variety; high-variety data goes in fields/values, not tags.** A device ID is a tag. Its temperature reading is a field. Its precise latitude to seven decimals is *not* a tag — bucket it or store it as a field. Getting this one distinction right prevents the majority of "why is our time-series DB melting" incidents.

## Downsampling and retention are the point

Raw high-resolution telemetry is expensive to keep and rarely needed at full resolution forever. Nobody queries per-second data from eight months ago; they query hourly averages. So the two features you configure on day one are downsampling and retention:

```sql
-- TimescaleDB: continuous aggregate rolling raw readings into hourly stats
CREATE MATERIALIZED VIEW readings_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', ts)      AS bucket,
    device_id,
    avg(value)                     AS avg_value,
    max(value)                     AS max_value,
    min(value)                     AS min_value
FROM readings
GROUP BY bucket, device_id;

-- Keep raw data 30 days, then let it drop automatically
SELECT add_retention_policy('readings', INTERVAL '30 days');
```

The pattern is: ingest raw, continuously roll up into coarser aggregates (hourly, daily), keep raw data only as long as you truly need it, and query the aggregates for anything historical. This keeps the hot dataset small and fast while preserving the long-term trends people actually ask for. A tiered scheme — raw for 30 days, hourly for a year, daily forever — cuts storage dramatically without losing analytical value.

## Where it sits in the pipeline

The time-series database is the sink, not the whole system. Upstream, telemetry usually flows through a broker before it lands — devices publish, a broker buffers and fans out, and a consumer batches writes into the database. That decoupling is essential because databases prefer batched writes and devices produce bursty, unbatched streams; the reasoning is the same as in [MQTT for IoT at scale](https://blog.michaelsam94.com/mqtt-iot-at-scale/), where the broker absorbs the impedance mismatch between flaky field links and backend consumers. Batch your inserts — writing 5,000 rows in one transaction is orders of magnitude cheaper than 5,000 single inserts.

If your telemetry also needs to feed other systems or a relational store of record, change-data-capture becomes relevant, and I've written about that flow in [Postgres logical replication and CDC](https://blog.michaelsam94.com/postgres-logical-replication-cdc/) — with TimescaleDB being Postgres, the same CDC tooling applies directly, which is another quiet argument in its favor.

## Practical tuning that pays off

A few things I always do:

- **Batch writes** from the ingest consumer; never single-row insert telemetry.
- **Compress older chunks.** Both engines compress historical data heavily — timestamped numeric data compresses beautifully, often 90%+.
- **Query the right resolution.** Point dashboards at continuous aggregates, not raw tables.
- **Set retention before you need it.** It's much harder to reclaim space after a table is huge.
- **Watch cardinality as a first-class metric.** Alert on series count growth; a sudden spike usually means someone tagged something they shouldn't have.

A time-series database makes IoT telemetry tractable, but it rewards discipline more than it rewards spending. Model your tags to keep cardinality bounded, downsample and expire aggressively, batch your writes, and choose the engine that fits your team's query habits rather than a benchmark. Do those, and a firehose of sensor data becomes a fast, cheap, queryable asset instead of an operational liability.

## Cardinality guardrails

`device_id` tag good; `firmware_patch_version` on every series killed TSDB — bucket to major.minor label only. Retention: raw 7d, 1m agg 90d, 1h forever — alert queries define minimum resolution needed, not infinite raw hoarding.

## Cardinality guardrails

`device_id` tag good; `firmware_patch_version` on every series killed TSDB — bucket to major.minor label only. Retention: raw 7d, 1m agg 90d, 1h forever — alert queries define minimum resolution needed, not infinite raw hoarding.

## Resources

- [TimescaleDB documentation](https://docs.timescale.com/)
- [InfluxDB documentation](https://docs.influxdata.com/)
- [PostgreSQL partitioning documentation](https://www.postgresql.org/docs/current/ddl-partitioning.html)
- [Prometheus — time-series monitoring system](https://prometheus.io/docs/introduction/overview/)
- [Apache IoTDB — time-series database for IoT](https://iotdb.apache.org/)
- [Time Series Benchmark Suite (TSBS)](https://github.com/timescale/tsbs)

## Architecture decisions around time series databases iot

Time-series platforms for time series databases iot need retention, downsampling, and cardinality control. High-cardinality labels are the classic outage.

For time series databases iot:
- Bound label keys; reject user-controlled label explosion at ingest
- Tiered retention: raw → 5m → 1h aggregates
- Remote write buffers and shard awareness under burst
- Alert on ingest lag and compaction debt, not only query latency

Review recording rules quarterly; unused metrics are paying rent forever.

| Signal | Target | Alarm |
|--------|--------|-------|
| Plan apply time | Team-defined SLO | Page on burn rate |
| Drift open count | Baseline − noise | Ticket if sustained |
| Failed policy checks | Budget cap | Weekly review |

## Load and chaos experiments for time series databases iot

Reviewers should challenge assumptions encoded in time series databases iot: defaults copied from tutorials, timeouts that exceed upstream SLAs, and authz checks applied only on the primary UI path. Require a short threat or failure note in the PR when the change touches a trust boundary.

Concrete probes:
1. Scenario C for time series databases iot: traffic 3× baseline — prove autoscaling or shedding keeps the golden journey healthy.
2. Scenario A for time series databases iot: partial dependency outage — prove clients degrade gracefully and retries do not amplify load.
3. Scenario B for time series databases iot: bad config shipped — prove rollback within the declared RTO without data corruption.

## Post-incident changes after time series databases iot failures

Roll out time series databases iot behind a flag or weighted route when possible. Start with internal users or a low-risk geography. Watch the signals in the table for at least one full business cycle before calling the migration done. Keep the previous path warm until error budgets stabilize.

Document the owner, the dashboard, and the single command that reverts the change. If that sentence is hard to write, the design is not ready for production traffic.

## Observability cardinality around time series databases iot

Detail 1 (837): for time series databases iot, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When observability cardinality around time series databases iot becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break time series databases iot, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about time series databases iot: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Caching interactions with time series databases iot

Detail 2 (220): for time series databases iot, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When caching interactions with time series databases iot becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break time series databases iot, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about time series databases iot: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.