---
title: "Postgres pg_stat_statements for Query Tuning"
slug: "postgres-pg-stat-statements-tuning"
description: "Enable pg_stat_statements, interpret total_time vs mean_time, find regressions after deploys, and reset safely in production."
datePublished: "2026-02-25"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
  - "Observability"
keywords: "pg_stat_statements, query performance Postgres, top queries by total time, shared_blks_read"
faq:
  - q: "total_time or mean_time for prioritization?"
    a: "Rank by total_time (or total_exec_time) to find queries consuming the most cluster capacity. mean_time finds slow individual executions; a fast query run millions of times dominates total_time."
  - q: "How do I reset pg_stat_statements in prod?"
    a: "Use `pg_stat_statements_reset()` for specific queryids after fixing a query, or snapshot to a metrics table before reset. Avoid global reset during incidents — you lose comparison baseline."
  - q: "Does pg_stat_statements show prepared statement text?"
    a: "It normalizes parameters to `$1`, `$2`. Use `queryid` to track the same logical query across ORM versions that change whitespace."
---

## Finding the real CPU hogs


```sql
SELECT queryid,
       calls,
       round(total_exec_time::numeric, 2) AS total_ms,
       round(mean_exec_time::numeric, 2) AS mean_ms,
       rows,
       shared_blks_read
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;
```

## Regression detection workflow

Export top 50 queryids nightly to Prometheus or ClickHouse. Alert when mean_exec_time doubles for a stable queryid. Pair with deploy markers — ORM upgrades change query text but often preserve queryid.

## IO vs CPU bound queries

High `shared_blks_read` relative to calls indicates cache misses — index missing or working set exceeds shared_buffers. High mean time with low blocks suggests CPU-heavy sorts or JSON parsing in SQL.


## Enabling and permissions

CREATE EXTENSION pg_stat_statements; set track=all and max=10000. Requires shared_preload_libraries restart. Grant pg_read_all_stats to observability role.

## Normalized query text pitfalls

ORMs emit different whitespace — same queryid still groups. Dynamic SQL with literal IN lists creates thousands of queryids — fix app to use arrays.

## pg_stat_statements_reset discipline

Reset single queryid after verified fix. Global reset before load test baseline; never during incident triage when you need comparison.

## Correlating with pg_stat_io (PG16+)

Join top total_exec_time queries with read_bytes — distinguishes CPU-heavy from IO-heavy optimization paths.

## Dashboard queries for weekly review

Top 10 by total_exec_time, top 10 by mean_exec_time over 100ms, top 10 by shared_blks_read per call. Review in weekly DB guild — assign owner per queryid. Stale queries after feature removal still consuming CPU show up here before users complain.

## pg_stat_statements vs auto_explain

pg_stat_statements aggregates; auto_explain logs individual slow plans. Use statements for capacity planning, auto_explain for debugging specific regression after deploy. Enable auto_explain only on canary replica to avoid log volume explosion.

## Export pipeline to warehouse

Nightly COPY (SELECT * FROM pg_stat_statements) to S3 → Snowflake. Join queryid history with deploy table on timestamp — regression analysis survives pg_stat_statements_reset in prod. Retention 90 days for trend charts in DB guild reviews.

## wal_bytes and temp_blks_written columns

PG13+ tracks WAL generation per query — bulk UPDATE showing high wal_bytes suggests batched update opportunity. temp_blks_written flags sorts/hash aggregates spilling to disk — add work_mem cautiously or rewrite query with LIMIT subquery.

## Role separation

Application role should not have pg_stat_statements_reset — only DBA automation role. Developers read views masking query text containing literal secrets — normalize or redact in export ETL if apps embed PII in dynamic SQL (anti-pattern but happens).

## Example weekly report query

```sql
SELECT queryid,
       left(query, 80) AS q,
       calls,
       round(total_exec_time/1000, 1) AS total_sec,
       round(100.0 * total_exec_time / sum(total_exec_time) OVER (), 2) AS pct_cluster
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 15;
```

pct_cluster column focuses optimization on queries consuming >5% cluster time — diminishing returns below 1% unless tail latency SLO breach tied to specific queryid.

## pg_stat_statements in managed RDS

RDS Parameter group: shared_preload_libraries includes pg_stat_statements, track=all. reboot instance once — plan maintenance window. Performance Insights overlays top waits with statements — correlate wait event IO:DataFileRead with shared_blks_read from pg_stat_statements same queryid.

## Identifying plan regression after ANALYZE

mean_exec_time jump without call increase after autovacuum — check if generic plan replaced custom plan. pg_stat_statements plans extension PG14+ stores sample plans per queryid — compare plan_id histogram before and after stats change.

## Security: redacting query text

Some apps embed secrets in dynamic SQL — export view replaces literals with $1 before warehouse load. Better fix: ban dynamic secret embedding; interim redaction prevents Snowflake leak.

## Capacity planning query

Sum total_exec_time across all queries ≈ single-core busy time if one CPU — rough sanity check. If sum exceeds wall-clock interval × cores, queries parallelized or I/O overlapped — use with system CPU metrics not alone.

## shared_preload_libraries ordering

pg_stat_statements must appear in shared_preload_libraries before restart — RDS parameter group change requires maintenance reboot. Staging must mirror prod parameter group class — "works in dev docker" without shared_preload fails silently (extension CREATE succeeds but no stats accumulate).

## Query id join to pg_stat_activity

Active long-running query matched to pg_stat_statements queryid via pg_stat_activity.query_id PG14+ — kill session with context of total historical time spent in same query shape. Incident: one runaway report query identified among hundreds of similar SELECTs.

## min/max_exec_time columns

PG13+ min_exec_time and max_exec_time expose tail spread — high max with low mean indicates occasional catastrophic plan or lock wait embedded in same queryid bucket. Investigate max before mean when p99 SLO fails but mean looks fine.

## stddev_exec_time for noisy queries

High standard deviation suggests plan instability or data skew — candidate for prepare custom plan or statistics target increase on leading column.

## Export to Grafana

postgres_exporter pg_stat_statements custom query top-N by total_time as gauge — dashboard panel refreshes 1m; links to runbook queryid lookup table maintained by DB guild.

## pg_stat_statements in read replica

Track statements on replica separately — reporting queries dominate replica stats not seen on primary pg_stat_statements. Export replica stats to separate dashboard; optimize read path without confusing primary OLTP tuning session.

## Limit pg_stat_statements.max

Cap at 10000; evicted queryids lost history — archive nightly top 500 to warehouse before eviction matters for quarterly trending. Increase max only if memory headroom verified on shared_buffers plus stats overhead.

## Tie to query plan cache

pg_stat_statements plans table join queryid to sample plans — when mean time spikes, diff sample plans for same queryid detecting index drop regression vs data volume growth using same plan shape.

## Role of pg_buffercache

For top shared_blks_read query, check if pages in buffer cache — cold cache after restart explains post-deploy spike not bad plan. correlate pg_stat_statements reset time with RDS reboot events in incident timeline.

## Example alert rules

Alert when any queryid mean_exec_time > 500ms for 15m AND calls > 100/min — excludes one-off reports. Alert when total_exec_time share > 10% for single queryid after deploy marker — automatic rollback discussion in incident channel without blaming deploy author individually.

## Closing notes

Weekly DB guild agenda: review top five queryids by total_exec_time delta week-over-week; assign owner before next meeting; close loop when metric returns below threshold or documented as acceptable trade-off.

## Additional guidance

Rotate pg_stat_statements history into data warehouse before major version upgrade — upgrade wipes stats otherwise. Compare pre/post upgrade top queryid mean_exec_time to detect planner regression from PG major jump not caught in staging due to smaller dataset lacking production skew on tenant_id leading column statistics.

Deep dive: pairing pg_stat_statements with pg_stat_io for PG16 shows read_bytes dominated by sequential scan node id visible in auto_explain sample — optimizer chose seq scan because reltuples stale after COPY import; ANALYZE single table fixes mean_exec_time drop forty percent without query rewrite proving stats maintenance before index addition avoids unnecessary CREATE INDEX CONCURRENTLY week-long project.

Automated weekly Slack bot posts top three queryids by total_exec_time delta with links to Grafana dashboard filtered queryid — visibility sustains tuning culture without manual guild scheduling conflict when DBAs travel or on vacation incident week.

Archive pg_stat_statements nightly before RDS maintenance reboot — post-reboot comparison to prior week identifies planner regressions after minor version upgrade.

Join deploy webhook timestamp with queryid mean_exec_time chart — five-minute spike after release visible before customer tickets arrive when regression isolated to single new query shape.

Create read-only Grafana dashboard per service team filtered by application_name connection setting — teams tune their queries without access to cluster-wide pg_stat_statements export containing other tenants SQL text in shared database hosting model.

Reset single queryid after verified fix to measure improvement — global reset during incident destroys before-and-after comparison needed for postmortem timeline reconstruction.

## Resources

- [PostgreSQL documentation](https://www.postgresql.org/docs/)
- [Microservices patterns](https://microservices.io/patterns/)
- [OpenTelemetry docs](https://opentelemetry.io/docs/)
- [12-Factor App](https://12factor.net/)
