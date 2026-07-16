---
title: "Downsampling and Retention Policies"
slug: "timeseries-downsampling-retention"
description: "Design downsampling and retention policies for time-series data: tiered rollups, continuous aggregates, storage math, and query patterns that keep historical telemetry fast and cheap."
datePublished: "2026-02-01"
dateModified: "2026-02-01"
tags: ["Data", "Databases", "Time Series", "Architecture"]
keywords: "downsampling, retention policy, time series, continuous aggregates, TimescaleDB, Prometheus, telemetry storage"
faq:
  - q: "What is downsampling in a time-series database?"
    a: "Downsampling is the process of replacing high-resolution raw measurements with coarser aggregates — hourly averages, daily maxima, or percentile summaries — while discarding the original points you no longer need. It reduces storage cost and keeps long-range queries fast because the database scans fewer rows. The trade-off is that you lose per-second detail for old data, which is usually acceptable for operational dashboards and trend analysis."
  - q: "How do I choose retention windows for different resolutions?"
    a: "Start from how your users actually query: if nobody looks at per-second data older than two weeks, keep raw at 14 days. Hourly rollups are useful for six months to a year of operational history. Daily aggregates can live for years at negligible cost. The pattern is tiered retention — raw for the hot window, progressively coarser resolutions for colder tiers — and each tier's window should match a real query pattern, not an arbitrary calendar date."
  - q: "Should downsampling happen at ingest or after the fact?"
    a: "Almost always after the fact, via continuous aggregates or scheduled rollups that read from a raw table and write to a coarser one. Ingest-time downsampling loses information you cannot recover and makes debugging recent incidents harder. Post-ingest rollups let you keep full resolution for a defined window, then compress on a schedule. The exception is edge devices with severe bandwidth limits, where pre-aggregation on the device itself is justified."
---

A monitoring stack I inherited was storing 15-second resolution metrics at full fidelity for three years. Disk was growing 40 GB a month, queries over a month of data timed out, and nobody on the team had ever asked for sub-minute granularity older than a week. The fix wasn't a bigger server — it was defining what resolution we actually needed at each age tier and automating the transition between them. Downsampling and retention policies are where time-series economics are won or lost, and most teams configure them too late.

The core idea is simple: raw high-resolution data is expensive and rarely queried at full resolution forever. You ingest at full fidelity for a hot window, roll up into coarser aggregates on a schedule, and drop what you no longer need. Done well, you keep 95% of analytical value at 10% of the storage cost.

## Tiered retention: the pattern that works

The scheme I default to for application metrics:

| Tier | Resolution | Retention | Use case |
|---|---|---|---|
| Raw | 15s–1m | 7–30 days | Incident debugging, live dashboards |
| Hourly | avg/max/min | 6–12 months | Capacity planning, SLO review |
| Daily | avg/max/min | 3–5 years | Long-term trends, compliance |

Each tier answers a different question. Raw data answers "what happened at 14:32:07 during the outage?" Hourly data answers "was CPU elevated all of last Tuesday?" Daily data answers "how did Q1 compare to Q2?" If a tier doesn't map to a real query pattern, cut it.

## Continuous aggregates in TimescaleDB

TimescaleDB makes this straightforward with continuous aggregates — materialized views that refresh incrementally as new raw data arrives:

```sql
CREATE MATERIALIZED VIEW cpu_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', ts) AS bucket,
    host,
    avg(cpu_pct)              AS avg_cpu,
    max(cpu_pct)              AS max_cpu,
    percentile_cont(0.99)
        WITHIN GROUP (ORDER BY cpu_pct) AS p99_cpu
FROM cpu_raw
GROUP BY bucket, host;

-- Refresh policy: roll up every hour, lag 1 hour behind now
SELECT add_continuous_aggregate_policy('cpu_hourly',
    start_offset => INTERVAL '3 hours',
    end_offset   => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');

-- Drop raw data older than 30 days
SELECT add_retention_policy('cpu_raw', INTERVAL '30 days');
```

The continuous aggregate refreshes on a schedule, processing only the new raw data since the last refresh. Queries against `cpu_hourly` scan orders of magnitude fewer rows than the raw table. Retention policies drop old chunks automatically — no cron job, no manual `DELETE`.

## Prometheus: recording rules and remote storage retention

Prometheus handles downsampling differently. Recording rules pre-compute aggregates at scrape time:

```yaml
groups:
  - name: hourly_rollups
    interval: 1h
    rules:
      - record: instance:cpu_usage:avg1h
        expr: avg_over_time(cpu_usage[1h])
```

The local TSDB keeps data for a configured retention period (default 15 days). For longer history, remote write sends samples to a long-term store — Thanos, Cortex, Mimir, or VictoriaMetrics — where compaction and downsampling run as background jobs. The operational split is: Prometheus for recent, high-resolution alerting; remote storage for historical queries at coarser resolution.

## Storage math that justifies the effort

Rough numbers for a metric with 10 labels at moderate cardinality, scraped every 15 seconds:

- Raw, 30 days: ~175,000 samples per series
- Hourly rollup, 1 year: ~8,760 samples per series
- Daily rollup, 5 years: ~1,825 samples per series

At 8 bytes per sample plus index overhead, raw data for 10,000 active series over 30 days is roughly 15–20 GB. The same series at hourly resolution for a year is under 1 GB. The compression ratio between tiers is what makes multi-year retention affordable.

## Query routing: which tier to hit

Application code or Grafana should route queries to the right tier automatically. A query for "last 6 hours" hits raw. "Last 90 days" hits hourly. "Year over year" hits daily. Getting this wrong — querying raw for a year of data — is the most common performance regression after downsampling is configured but query routing isn't updated.

In Grafana, use different data sources or recording rules aliased to the right resolution. In application code, parameterize the query window and select the table or metric name accordingly:

```typescript
function metricTable(rangeHours: number): string {
  if (rangeHours <= 48)  return 'cpu_raw';
  if (rangeHours <= 720) return 'cpu_hourly';
  return 'cpu_daily';
}
```

## Pitfalls I've hit

**Downsampling before you understand the data.** Rolling up too aggressively on day one means you cannot recompute finer aggregates later. Keep raw longer than you think you need, then tighten retention once query patterns are clear.

**Aggregating non-additive metrics incorrectly.** You can sum counters and average gauges, but percentiles don't average cleanly. Use `histogram_quantile` or store pre-computed percentiles, not averages of p99 values.

**Retention policies without monitoring.** Set an alert on storage growth rate. If raw retention is misconfigured, disk fills silently until queries fail.

**Forgetting cardinality in rollups.** A continuous aggregate grouped by `host` is fine. Grouped by `request_id` recreates the cardinality problem at every tier.

## Common production mistakes

Teams get timeseries downsampling retention wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of timeseries downsampling retention fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [TimescaleDB continuous aggregates](https://docs.timescale.com/use-timescale/latest/continuous-aggregates/)
- [TimescaleDB data retention](https://docs.timescale.com/use-timescale/latest/data-retention/)
- [Prometheus recording rules](https://prometheus.io/docs/prometheus/latest/configuration/recording_rules/)
- [Thanos downsampling](https://thanos.io/tip/components/compact.md/#downsampling)
- [Grafana time-series query performance](https://grafana.com/docs/grafana/latest/datasources/prometheus/#query-performance)
