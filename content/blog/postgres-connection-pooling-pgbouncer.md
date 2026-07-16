---
title: "Connection Pooling with PgBouncer"
slug: "postgres-connection-pooling-pgbouncer"
description: "Scale Postgres connections with PgBouncer: pool modes, sizing math, prepared statements, RDS integration, and common misconfigurations that exhaust connections."
datePublished: "2026-03-09"
dateModified: "2026-03-09"
tags: ["PostgreSQL", "Backend", "Database", "Performance"]
keywords: "PgBouncer connection pooling, Postgres max connections, pool mode transaction session, RDS PgBouncer, connection pool sizing"
faq:
  - q: "Why does Postgres need an external pooler like PgBouncer?"
    a: "Each Postgres connection spawns a backend process consuming 2–10 MB RAM. A few hundred connections is fine; ten thousand Node.js microservice pods each opening five connections exhausts memory and CPU on context switching. PgBouncer multiplexes many client connections onto fewer server connections."
  - q: "Which PgBouncer pool mode should I use?"
    a: "Transaction mode for most web apps — server connection returned to pool after each transaction. Session mode if you need prepared statements, temp tables, or advisory session locks across queries. Statement mode is rarely compatible with modern ORMs."
  - q: "How many server connections should PgBouncer use?"
    a: "Start with (CPU cores × 2) + effective_spindle_count for OLTP, often 50–200 for typical RDS instances. Client connections can be thousands. Never set Postgres max_connections to match total microservice pods — that's what the pooler is for."
---

RDS alarm: `too many connections.` The culprit wasn't traffic — it was 400 Kubernetes pods each configured with `pool_size=20` hitting Postgres directly. Eight thousand connection attempts, instance limit 500. PgBouncer in transaction mode cut server connections to 80 while serving 2000 clients. Same database, same queries — different architecture.

## Connection economics

Postgres `max_connections` default 100. Each connection:
- Dedicated backend process
- Memory for buffers and catalog cache
- Lock table entries

Rule of thumb: **connections ≠ concurrency**. Postgres throughput often peaks well below connection count due to lock contention.

```
App pods (2000 conn) ──► PgBouncer ──► Postgres (80 conn)
```

## Pool modes explained

| Mode | Server conn held | Compatible with |
|------|------------------|-----------------|
| Session | Entire client session | Temp tables, session GUCs, session locks |
| Transaction | Single transaction | Most ORMs, web request cycle |
| Statement | Single statement | Simple autocommit only — breaks most apps |

**Transaction mode** — default recommendation:

```ini
; pgbouncer.ini
[databases]
appdb = host=postgres.internal port=5432 dbname=appdb

[pgbouncer]
pool_mode = transaction
max_client_conn = 2000
default_pool_size = 50
reserve_pool_size = 10
reserve_pool_timeout = 3
```

Client connects to PgBouncer port 6432; PgBouncer opens ≤50 connections to Postgres per user/database pair.

## Sizing

```ini
default_pool_size = 50        # per db+user pool to Postgres
max_client_conn = 2000        # total incoming clients
```

Postgres side:
```sql
ALTER SYSTEM SET max_connections = 120;  # pool_size × pools + admin headroom
```

For RDS db.r6g.large (2 vCPU): start `default_pool_size` 25–50. Load test and watch `pg_stat_activity` wait events — `Lock` and `IO` saturation mean too many concurrent queries, not necessarily too few connections.

## Prepared statements and ORMs

Transaction pooling **breaks** unnamed prepared statements that outlive a transaction — common with PgBouncer + Prisma/JDBC defaults.

Fixes:
- PgBouncer 1.21+ `max_prepared_statements` with prepared statement tracking
- Disable prepared statements in client: `?prepareThreshold=0` (JDBC), Prisma `pgbouncer=true`
- Use session mode (reduces pooling benefit)

We standardize on PgBouncer 1.21+ and Prisma's pgbouncer compatibility flag.

## Authentication

```ini
auth_type = scram-sha-256
auth_file = /etc/pgbouncer/userlist.txt
```

Or `auth_query` against Postgres `pg_shadow` for centralized user management:

```ini
auth_query = SELECT usename, passwd FROM pg_shadow WHERE usename=$1
auth_user = pgbouncer_auth
```

RDS: use IAM auth at app layer, static creds at PgBouncer, or RDS Proxy as managed alternative.

## RDS Proxy vs self-hosted PgBouncer

| Feature | PgBouncer | RDS Proxy |
|---------|-----------|-----------|
| Cost | Self-managed | Per-hour + per-connection |
| IAM auth | Manual | Native |
| Failover | Reconnect logic needed | Faster failover handling |
| Control | Full ini tuning | Limited knobs |

RDS Proxy simplifies IAM and failover; PgBouncer gives control and runs anywhere (including outside AWS).

## Monitoring

PgBouncer `SHOW POOLS;`, `SHOW STATS;`, `SHOW CLIENTS;` via admin console.

Key metrics:
- `cl_waiting` — clients queued for server conn (increase pool or optimize queries)
- `sv_active` vs `sv_idle` — utilization
- `maxwait` — longest wait time

Prometheus pgbouncer_exporter for dashboards. Alert on sustained `cl_waiting > 0`.

## Common misconfigurations

**App connects to Postgres directly bypassing pooler** — enforce via security group: only PgBouncer SG reaches 5432.

**Session mode with 5000 clients** — defeats pooling; one server conn per client.

**Long transactions holding pool slots** — open transaction during external HTTP call blocks server connection. Keep transactions short.

**Missing `server_reset_query`** — leaked session state between clients:

```ini
server_reset_query = DISCARD ALL
```

## Observability integration

Export PgBouncer stats to Prometheus and dashboard: waiting clients, query time, pool utilization per database. Alert when any pool spends more than 30 seconds with waiting clients — indicates need for query optimization or pool size bump, not just "add connections."

## Operational notes

When using RDS Proxy plus PgBouncer, avoid double pooling unless you understand connection math — often pick one layer. Double pooling obscures which layer queues requests and complicates timeout tuning.

Document application connection string pointing at PgBouncer in golden path template — new services connecting directly to Postgres bypass pooler silently until connection exhaustion incident.

Set `server_idle_timeout` on PgBouncer below RDS idle timeout to prevent server-side connection kills leaving stale client pool entries that fail on next query with confusing errors.

Size PgBouncer pool to `(core_count * 2) + spindle_count` on DB server, not per-app-instance connections summed — connection storms exhaust Postgres max_connections.

## Transaction mode pitfalls

```ini
; pool_mode = transaction  — safest default for web apps
; pool_mode = session      — needed for prepared statements, LISTEN/NOTIFY, temp tables
; pool_mode = statement    — rarely used, breaks transactions
```

Prisma, Django, and Rails work with transaction mode + `DISCARD ALL`. JDBC prepared statement caching may need session mode — doubles connection count, plan accordingly.

## RDS and managed Postgres specifics

| Service | Recommendation |
|---------|----------------|
| RDS Postgres | PgBouncer on EC2/ECS, or RDS Proxy |
| Aurora | RDS Proxy often sufficient |
| Supabase | Supavisor (built-in pooler) |
| Neon | Built-in connection pooling |

Don't stack RDS Proxy → PgBouncer → app without calculating: `apps × pool_size` must stay below Postgres `max_connections`.

## Connection storm on deploy

Rolling deploy of 50 pods × 20 connections = 1000 connections if all connect simultaneously:

```python
# SQLAlchemy — limit pool per instance
engine = create_engine(url, pool_size=5, max_overflow=2)
```

Use connection pool per process, not per request. Stagger pod startup with `maxSurge: 1` during deploys.

Pair with [Postgres query planning EXPLAIN ANALYZE](https://blog.michaelsam94.com/postgres-query-planning-explain-analyze/) when pool waits indicate slow queries, not pool undersizing.

## Common production mistakes

Teams get connection pooling pgbouncer wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Postgres work on connection pooling pgbouncer causes outages when migrations run without `lock_timeout`, connection pools are sized for app servers not PgBouncer modes, and `EXPLAIN` plans from staging are assumed to match production statistics.

## Resources

- [PgBouncer documentation](https://www.pgbouncer.org/usage.html)
- [PostgreSQL connection pooling wiki](https://wiki.postgresql.org/wiki/Connection_pooling)
- [AWS RDS Proxy documentation](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-proxy.html)
- [Prisma PgBouncer configure guide](https://www.prisma.io/docs/guides/performance-and-optimization/connection-management/configure-pg-bouncer)
- [PgBouncer config reference](https://www.pgbouncer.org/config.html)
