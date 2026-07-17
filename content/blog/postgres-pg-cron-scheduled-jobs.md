---
title: "Postgres pg_cron Scheduled Jobs"
slug: "postgres-pg-cron-scheduled-jobs"
description: "Schedule vacuum, partition maintenance, and materialized view refresh with pg_cron inside Postgres."
datePublished: "2026-02-23"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
keywords: "pg_cron, postgres scheduled jobs, cron extension, partition maintenance, materialized view refresh"
faq:
  - q: "How is pg_cron different from system cron calling psql?"
    a: "pg_cron runs inside the Postgres server as a background worker — jobs execute in-database without shell access, SSH keys, or connection overhead from external cron. Job definitions live in pg_cron.job table, visible in SQL, and survive in backups. System cron requires credential management and spawns new connections per invocation."
  - q: "Can pg_cron jobs run in any database?"
    a: "pg_cron installs in the postgres database (or a dedicated admin database) but can schedule jobs targeting any database on the same instance via cron.schedule's database parameter. Each job runs as the pg_cron extension owner — configure job commands with appropriate SET ROLE or SECURITY DEFINER functions for least privilege."
  - q: "What happens if a pg_cron job overlaps with itself?"
    a: "pg_cron does not prevent overlapping runs by default — a slow job still running when the next schedule fires starts a second instance. Use pg_advisory_lock in job SQL, schedule with sufficient interval, or check pg_cron.job_run_details for run duration before tightening schedules."
---

Database maintenance tasks — partition creation, materialized view refresh, stale row cleanup, statistics updates — need reliable scheduling. External cron calling `psql -c "..."` works but scatters credentials, opens new connections per run, and hides job definitions outside the database. **pg_cron** runs scheduled jobs as a Postgres background worker, storing schedules in SQL-accessible tables and executing within the database engine.

This article covers installation, job definition, common maintenance patterns, monitoring, and the pitfalls that cause duplicate runs or silent failures.

## Installation and setup

pg_cron is available on RDS, Cloud SQL (selected tiers), and self-managed Postgres via package or compile:

```sql
-- postgresql.conf
shared_preload_libraries = 'pg_cron'
cron.database_name = 'postgres'  -- database where pg_cron metadata lives

-- Restart required for shared_preload_libraries
CREATE EXTENSION pg_cron;
```

Verify:

```sql
SELECT cron.schedule('0 * * * *', 'SELECT 1');
SELECT * FROM cron.job;
```

Jobs are stored in `cron.job`; execution history in `cron.job_run_details`.

## Scheduling syntax

Standard cron expressions (minute, hour, day of month, month, day of week):

```sql
SELECT cron.schedule(
  'nightly-vacuum',           -- job name (optional, PG 12+)
  '0 3 * * *',                -- 03:00 daily
  'VACUUM ANALYZE orders'
);
```

Returns job ID. Five-field cron format:

```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 7, 0 and 7 = Sunday)
│ │ │ │ │
* * * * *
```

Examples:

```sql
-- Every 15 minutes
SELECT cron.schedule('*/15 * * * *', 'REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_sales');

-- Weekdays at 6 AM
SELECT cron.schedule('0 6 * * 1-5', 'CALL refresh_reporting_tables()');

-- First day of month at midnight
SELECT cron.schedule('0 0 1 * *', 'SELECT create_next_month_partitions()');
```

Target a specific database:

```sql
SELECT cron.schedule_in_database(
  'app-db-cleanup',
  '0 4 * * *',
  'DELETE FROM sessions WHERE expires_at < now()',
  'application_db'
);
```

## Common maintenance jobs

### Materialized view refresh

```sql
SELECT cron.schedule(
  'refresh-sales-mv',
  '0 * * * *',
  $$REFRESH MATERIALIZED VIEW CONCURRENTLY mv_hourly_sales$$
);
```

CONCURRENTLY requires unique index on materialized view — avoids blocking reads during refresh.

### Partition management

```sql
CREATE OR REPLACE FUNCTION create_weekly_partitions()
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
  start_date date := date_trunc('week', now() + interval '2 weeks');
BEGIN
  EXECUTE format(
    'CREATE TABLE IF NOT EXISTS events_%s PARTITION OF events
     FOR VALUES FROM (%L) TO (%L)',
    to_char(start_date, 'IYYY_IW'),
    start_date,
    start_date + interval '1 week'
  );
END;
$$;

SELECT cron.schedule('0 2 * * 0', 'SELECT create_weekly_partitions()');
```

Weekly Sunday 2 AM — creates partition two weeks ahead.

### Stale data cleanup

```sql
SELECT cron.schedule(
  '0 5 * * *',
  $$DELETE FROM audit_log WHERE created_at < now() - interval '90 days'$$
);
```

Batch large deletes to avoid long locks:

```sql
CREATE OR REPLACE FUNCTION batch_delete_audit()
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  LOOP
    DELETE FROM audit_log
    WHERE id IN (
      SELECT id FROM audit_log
      WHERE created_at < now() - interval '90 days'
      LIMIT 10000
    );
    EXIT WHEN NOT FOUND;
    COMMIT;
  END LOOP;
END;
$$;
```

### Statistics and vacuum

```sql
SELECT cron.schedule('0 3 * * *', 'VACUUM ANALYZE');
SELECT cron.schedule('30 3 * * 0', 'VACUUM FULL pg_catalog.pg_statistic');  -- rarely needed
```

Prefer autovacuum tuning over scheduled VACUUM FULL — VACUUM FULL takes AccessExclusiveLock.

### Reindex CONCURRENTLY

```sql
SELECT cron.schedule(
  '0 1 * * 6',
  'REINDEX INDEX CONCURRENTLY idx_orders_created_at'
);
```

## Preventing overlapping runs

pg_cron does not skip if previous run still active:

```sql
CREATE OR REPLACE FUNCTION refresh_with_lock()
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  IF NOT pg_try_advisory_lock(hashtext('refresh_mv_daily')) THEN
    RAISE NOTICE 'Previous refresh still running, skipping';
    RETURN;
  END IF;
  BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily;
  finally
    PERFORM pg_advisory_unlock(hashtext('refresh_mv_daily'));
  END;
END;
$$;

SELECT cron.schedule('*/30 * * * *', 'SELECT refresh_with_lock()');
```

Check run duration before tightening schedule:

```sql
SELECT jobid, runid, status, start_time, end_time,
       end_time - start_time AS duration, return_message
FROM cron.job_run_details
WHERE jobid = 1
ORDER BY start_time DESC
LIMIT 20;
```

## Security and privileges

pg_cron runs jobs as the user that owns the extension (usually superuser or dedicated admin):

```sql
-- Least privilege: SECURITY DEFINER function owned by privileged role
CREATE OR REPLACE FUNCTION cleanup_sessions()
RETURNS void
SECURITY DEFINER
SET search_path = public
LANGUAGE sql AS $$
  DELETE FROM sessions WHERE expires_at < now();
$$;

REVOKE ALL ON FUNCTION cleanup_sessions() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION cleanup_sessions() TO cron_runner;

SELECT cron.schedule('0 * * * *', 'SELECT cleanup_sessions()');
```

Never schedule jobs containing credentials or unsanitized dynamic SQL from external input.

## Monitoring job execution

Recent runs:

```sql
SELECT j.jobname, d.status, d.start_time, d.end_time,
       d.end_time - d.start_time AS duration,
       d.return_message
FROM cron.job_run_details d
JOIN cron.job j ON j.jobid = d.jobid
ORDER BY d.start_time DESC
LIMIT 50;
```

Failed jobs:

```sql
SELECT * FROM cron.job_run_details
WHERE status = 'failed'
ORDER BY start_time DESC;
```

Alert on failed status or duration exceeding threshold. Integrate with Prometheus via custom query exporter or pg_cron log scraping.

## Managing jobs

List scheduled jobs:

```sql
SELECT jobid, jobname, schedule, command, nodename, nodeport, database, username, active
FROM cron.job;
```

Unschedule:

```sql
SELECT cron.unschedule('nightly-vacuum');
-- or by job ID
SELECT cron.unschedule(42);
```

Alter schedule (unschedule and recreate — pg_cron lacks native alter in older versions):

```sql
SELECT cron.unschedule('refresh-sales-mv');
SELECT cron.schedule('refresh-sales-mv', '0 */2 * * *', 'REFRESH MATERIALIZED VIEW CONCURRENTLY mv_hourly_sales');
```

Deactivate without removing:

```sql
UPDATE cron.job SET active = false WHERE jobname = 'nightly-vacuum';
```

## pg_cron vs external schedulers

| Aspect | pg_cron | System cron + psql | Application scheduler (Sidekiq, Celery) |
| --- | --- | --- | --- |
| Credentials | In-database | File/env required | App config |
| Connection overhead | None (in-process) | New connection each run | App pool |
| Visibility | SQL tables | Crontab file | UI/dashboard |
| Cross-database | Same instance only | Any reachable | Any reachable |
| Heavy compute | Blocks worker — keep jobs SQL-light | External process | External workers |

Use pg_cron for SQL-native maintenance. Use external schedulers for jobs requiring application logic, external API calls, or cross-service orchestration.

## RDS and managed Postgres notes

**Amazon RDS**: pg_cron available via `shared_preload_libraries` parameter group. Runs as master user. Some SQL restricted.

**Cloud SQL**: pg_cron on selected versions — check extension list.

**Supabase**: pg_cron pre-enabled with dashboard for job management.

Always verify extension availability and privilege model on managed platforms before designing around pg_cron.

## Resource impact

pg_cron uses one background worker from `max_worker_processes`. Long-running jobs block that worker's job queue — keep individual jobs short or split into batched functions.

Heavy jobs during peak hours compete for I/O and CPU with OLTP:

```sql
-- Schedule maintenance during off-peak
SELECT cron.schedule('0 3 * * *', ...);  -- 3 AM, not 3 PM
```

Set statement_timeout within job functions:

```sql
CREATE OR REPLACE FUNCTION safe_maintenance()
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  SET LOCAL statement_timeout = '3600s';
  SET LOCAL lock_timeout = '5s';
  -- maintenance SQL
END;
$$;
```

## Troubleshooting

**Job not running**:

- Check `active = true` in cron.job
- Verify pg_cron worker in `pg_stat_activity` (backend_type)
- Check cron.database_name matches where extension is installed
- Review pg_log for pg_cron errors

**Job fails silently**:

- Query cron.job_run_details for return_message
- Test command manually: `psql -c "..."`
- Permission errors — job runs as extension owner, not application user

**Jobs run twice after failover**:

- pg_cron on primary only — standby does not run jobs
- After failover, verify jobs exist on new primary (replicated if cron.job in replication stream — it is, as user table)

**Timezone confusion**:

- pg_cron uses UTC by default
- Server timezone affects `now()` in job SQL but not cron schedule interpretation
- Document schedules in UTC; convert explicitly if needed: `cron.schedule('0 3 * * *', ...)` is 03:00 UTC

## Summary

pg_cron embeds cron scheduling inside Postgres — ideal for VACUUM, partition creation, materialized view refresh, and data retention jobs defined in SQL. Install via shared_preload_libraries, schedule with standard cron syntax, prevent overlapping runs with advisory locks, and monitor cron.job_run_details for failures and duration. Keep jobs SQL-focused, run heavy maintenance off-peak, and use SECURITY DEFINER functions for least-privilege execution. For application logic or cross-service work, external schedulers remain appropriate — pg_cron owns database-native maintenance.


Log ROW_COUNT from retention jobs and alert when deletes stay at zero while table size still grows — green cron status can hide a wrong column predicate.
