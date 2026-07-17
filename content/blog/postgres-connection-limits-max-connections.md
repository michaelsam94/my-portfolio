---
title: "Postgres Connection Limits max_connections"
slug: "postgres-connection-limits-max-connections"
description: "Size max_connections, understand memory per connection, and use poolers to avoid connection exhaustion."
datePublished: "2026-02-23"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
keywords: "max_connections, postgres connection pool, pgbouncer, connection exhaustion, superuser_reserved_connections"
faq:
  - q: "What happens when Postgres hits max_connections?"
    a: "New connection attempts receive FATAL: sorry, too many clients already. Existing connections continue working. Application connection pools retry and queue, causing request latency spikes. Monitoring connections near the limit and using a pooler prevents this."
  - q: "How much memory does each Postgres connection consume?"
    a: "Budget roughly 5–10 MB per connection for work_mem-dependent workloads, plus shared memory allocated once. A rough formula: total RAM reserved for connections = max_connections × (work_mem peak usage + connection overhead). Setting max_connections=500 on a 16 GB instance often leaves insufficient memory for shared_buffers and query execution."
  - q: "Should I increase max_connections or add PgBouncer?"
    a: "Add PgBouncer (or RDS Proxy) in almost all cases. Postgres connections are heavyweight OS processes. PgBouncer multiplexes hundreds of application connections onto tens of database connections. Increase max_connections only when active backend count genuinely requires it — not because application instance count grew."
---

`FATAL: sorry, too many clients already` is Postgres telling you that every allowed connection slot is occupied — and your application is about to cascade-fail as connection pools block, health checks fail, and deploys cannot establish new sessions. The `max_connections` parameter looks like a simple integer to raise, but each connection consumes memory, file descriptors, and CPU for process management. Understanding the math behind connection limits — and why poolers exist — separates stable production databases from ones that page at 2 AM during a traffic spike.

## How Postgres connections work

Each client connection spawns a dedicated backend process:

```
Client → postmaster → fork backend process → query execution
```

These are OS processes, not lightweight threads. At 500 connections, you have 500 processes competing for memory and CPU scheduling. Postgres was designed for moderate connection counts with pooling in front — not for one connection per serverless function invocation.

Check current settings and usage:

```sql
SHOW max_connections;
-- typically 100 default

SELECT count(*) AS total,
       count(*) FILTER (WHERE state = 'active') AS active,
       count(*) FILTER (WHERE state = 'idle') AS idle,
       count(*) FILTER (WHERE state = 'idle in transaction') AS idle_in_tx
FROM pg_stat_activity
WHERE backend_type = 'client backend';
```

## Memory math

Each connection allocates:

- **Base overhead**: ~2–5 MB per backend (depends on PG version and platform)
- **work_mem**: Allocated per sort/hash operation, per query, per connection — not per database
- **temp_buffers**: Per-session temporary buffer space
- **Maintenance**: autovacuum workers, replication connections — also count toward limits

Conservative sizing:

```
Available for connections = Total RAM
  - shared_buffers (25% RAM typical)
  - OS cache and kernel
  - autovacuum and maintenance workers
  - replication slots

Safe max_connections ≈ Available / 10MB
```

On a 32 GB machine with 8 GB shared_buffers:

```
(32 - 8 - 4) GB / 10 MB ≈ 2000 theoretical max
Practical max_connections: 200–400 with headroom for query memory spikes
```

Raising `max_connections` to 1000 without reducing per-connection memory settings guarantees OOM kills under load.

## Key related parameters

```sql
-- Reserve slots for superuser emergency access
SHOW superuser_reserved_connections;  -- default 3

-- Connection limits per role
ALTER ROLE app_user CONNECTION LIMIT 150;

-- Timeout idle connections
ALTER SYSTEM SET idle_in_transaction_session_timeout = '60s';
ALTER SYSTEM SET idle_session_timeout = '300s';  -- PG14+
```

**superuser_reserved_connections**: When at max_connections, only superusers can still connect. Always leave 3+ reserved for emergency `psql` access during incidents.

**Role connection limits**: Cap a runaway application's connection consumption without affecting other services sharing the database.

**Idle timeouts**: Idle-in-transaction connections hold slots indefinitely after a forgotten `BEGIN`. Aggressive timeout prevents slot hoarding from application bugs.

## Connection exhaustion symptoms

| Symptom | Likely cause |
| --- | --- |
| Intermittent "too many clients" | Traffic spike + no pooler |
| Connections climb, never drop | Connection leak — pools not releasing |
| idle in transaction grows | Missing transaction cleanup in app code |
| Spikes during deploy | Old + new instances both connecting simultaneously |
| Connection count = app instances × pool size | No pooler multiplexing |

Diagnose idle-in-transaction leaks:

```sql
SELECT pid, usename, application_name, state,
       now() - xact_start AS xact_age,
       left(query, 80) AS query
FROM pg_stat_activity
WHERE state = 'idle in transaction'
ORDER BY xact_start;
```

Terminate runaway sessions (after confirming safety):

```sql
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND now() - xact_start > interval '5 minutes'
  AND usename = 'app_user';
```

## PgBouncer: the standard solution

PgBouncer sits between applications and Postgres, multiplexing many client connections onto fewer server connections.

```
100 app instances × 20 pool size = 2000 client connections
                                    ↓
                              PgBouncer (pool_mode=transaction)
                                    ↓
                              50 Postgres connections
```

Configuration (`pgbouncer.ini`):

```ini
[databases]
mydb = host=postgres.internal port=5432 dbname=mydb

[pgbouncer]
pool_mode = transaction
max_client_conn = 2000
default_pool_size = 50
reserve_pool_size = 10
reserve_pool_timeout = 3
server_idle_timeout = 60
```

**pool_mode=transaction**: Server connection returned to pool after each transaction. Best for web request workloads. Cannot use prepared statements that span transactions (unless PgBouncer 1.21+ with prepared statement tracking).

**pool_mode=session**: One server connection per client for session lifetime. Use when you need session-level features (LISTEN/NOTIFY, temp tables, SET parameters persisting across queries).

**default_pool_size**: Actual Postgres connections PgBouncer opens. Set based on CPU cores and memory — typically 20–100 for OLTP.

Application connection string points to PgBouncer, not Postgres directly:

```
postgresql://app_user:pass@pgbouncer.internal:6432/mydb
```

## Managed cloud limits

| Provider | Default max_connections | Notes |
| --- | --- | --- |
| RDS Postgres | Formula based on instance RAM | Cannot exceed without instance upgrade on some tiers |
| Cloud SQL | Tier-dependent | Use Cloud SQL Auth Proxy + pooler |
| Aurora | Higher limits | Still pool at application/PgBouncer layer |
| Supabase | Pooler on port 6543 | Direct port 5432 limited |

Cloud provider formulas (RDS example):

```
max_connections = LEAST({DBInstanceClassMemory/9531392}, 5000)
```

Check your instance class before assuming you can set arbitrary values.

## Application pool sizing

Without PgBouncer, size application pools conservatively:

```
Total app connections = instances × pool_max_size
Must be < max_connections - reserved - admin - replication
```

Rule of thumb for direct connections:

```
pool_max_size = (max_connections - 20) / number_of_app_instances
```

With PgBouncer:

```
pool_max_size = 20-50 per instance (client-side, cheap)
PgBouncer default_pool_size = based on Postgres capacity
```

Common mistake: setting application `pool_max_size=100` across 50 Kubernetes pods = 5000 connections attempted against `max_connections=200`.

## Serverless and connection storms

Serverless functions (Lambda, Cloud Functions) that open a new Postgres connection per invocation multiply connections by concurrency:

```
1000 concurrent Lambda invocations = 1000 connections
```

Solutions:

1. **RDS Proxy / PgBouncer / Supavisor** — mandatory for serverless
2. **HTTP-based database APIs** (PostgREST, custom) — connection pooling at API layer
3. **Neon / PlanetScale serverless drivers** — WebSocket multiplexing

Never connect directly from short-lived serverless workers without a pooler.

## Monitoring and alerting

Prometheus/Grafana queries via `pg_stat_activity` or postgres_exporter:

```
pg_stat_activity_count{state="active"} / pg_settings_max_connections > 0.8
```

Alert at 80% utilization. Alert separately on `idle in transaction` count > 10.

PgBouncer metrics:

```
SHOW POOLS;   -- cl_active, cl_waiting, sv_active, sv_idle
SHOW STATS;   -- total requests, avg wait time
```

`cl_waiting > 0` sustained means clients queue for server connections — increase `default_pool_size` or optimize query duration.

## Tuning workflow

1. Measure peak `count(*)` from `pg_stat_activity` over 7 days
2. Count idle-in-transaction as waste, fix application leaks
3. Deploy PgBouncer if app connections > 2× CPU cores
4. Set `max_connections` = PgBouncer pool size + admin headroom (replication, monitoring)
5. Set application pool sizes to match PgBouncer `max_client_conn`
6. Enable idle timeouts
7. Re-measure after deploy

## Emergency runbook

During "too many clients" incident:

1. Connect as superuser (uses reserved slot)
2. Identify top consumers: `SELECT usename, application_name, count(*) FROM pg_stat_activity GROUP BY 1,2 ORDER BY 3 DESC`
3. Terminate idle-in-transaction sessions older than threshold
4. Temporarily reduce application pool sizes via config reload
5. Scale PgBouncer pool if Postgres CPU/memory allows
6. Post-incident: deploy pooler if not present, fix connection leaks

## Connection budgeting worksheet

Use this template during capacity planning:

```
max_connections (Postgres)           = ___
superuser_reserved_connections     = 3
replication slots (physical)       = ___
monitoring / admin connections     = 5
available for application          = ___ - 3 - replication - 5

PgBouncer default_pool_size        = available × 0.8
PgBouncer max_client_conn          = app_instances × pool_max_size

Per-instance pool_max_size         = max_client_conn / app_instances
```

Revisit quarterly or after autoscaling policy changes. Serverless concurrency limits belong in this calculation — each concurrent invocation is a potential connection unless pooled through a proxy.

Document the worksheet in your infrastructure runbook so on-call engineers know whether "raise max_connections" or "fix pooler config" is the correct incident response.

## Summary

Postgres connections are expensive processes, not free handles. Default `max_connections=100` is a ceiling, not a target — size based on memory math, not application instance count. PgBouncer (or managed equivalents) multiplexes client connections onto a small pool of server backends, which is the standard architecture for any multi-instance application. Monitor utilization, kill idle-in-transaction leaks, reserve superuser slots, and treat connection exhaustion as an architecture signal rather than a knob to turn indefinitely.


Alert at 70% connection utilization and graph idle-in-transaction counts; exhaustion is more often a leak than an undersized max_connections.
