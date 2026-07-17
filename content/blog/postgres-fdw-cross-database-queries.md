---
title: "Postgres FDW Cross Database Queries"
slug: "postgres-fdw-cross-database-queries"
description: "Query remote Postgres and other databases with postgres_fdw — setup, pushdown, performance tuning, and security boundaries."
datePublished: "2026-02-23"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
keywords: "postgres_fdw, foreign data wrapper, cross database query, remote postgres, sharding"
faq:
  - q: "Does postgres_fdw support writes to remote tables?"
    a: "Yes. INSERT, UPDATE, DELETE, and COPY work on foreign tables when created without read-only restrictions. Writes execute as single-row operations on the remote server unless batch insert pushdown is available in your PG version. Transaction semantics span both servers only with two-phase commit in supported configurations — default is independent commits per server."
  - q: "How does query pushdown affect performance?"
    a: "Postgres pushes WHERE filters, JOIN clauses, and aggregates to the remote server when possible, reducing rows transferred over the network. Without pushdown, postgres_fdw fetches all rows and filters locally — catastrophic on large remote tables. Check EXPLAIN output for 'Remote SQL' to verify pushdown."
  - q: "Should I use FDW for production cross-database joins or migrate schemas instead?"
    a: "FDW suits reporting, gradual migration, and occasional cross-database lookups. For high-volume OLTP joins across databases, network latency and lack of true distributed transactions make FDW a poor fit — consolidate schemas, use application-level aggregation, or adopt a purpose-built distributed query engine instead."
---

Postgres databases are isolated by design — one cluster, one database, no cross-database queries within a single connection. Yet production systems accumulate separate databases for legacy migrations, multi-tenant isolation, or bounded context boundaries. When a report needs orders from `billing_db` joined with users from `identity_db`, **Foreign Data Wrappers (FDW)** bridge the gap without ETL pipelines or application-level fan-out.

**postgres_fdw** is the built-in wrapper for remote Postgres servers. This article covers setup, query pushdown mechanics, performance tuning, and the sharp edges that turn an convenient shortcut into a production bottleneck.

## Basic setup

On the local (coordinator) database:

```sql
CREATE EXTENSION postgres_fdw;

CREATE SERVER identity_server
  FOREIGN DATA WRAPPER postgres_fdw
  OPTIONS (host 'identity-db.internal', port '5432', dbname 'identity');

CREATE USER MAPPING FOR app_reader
  SERVER identity_server
  OPTIONS (user 'fdw_reader', password 'secret');

CREATE FOREIGN TABLE remote_users (
  id         uuid,
  email      text,
  created_at timestamptz
)
SERVER identity_server
OPTIONS (schema_name 'public', table_name 'users');

-- Query as if local
SELECT * FROM remote_users WHERE email = 'alice@example.com';
```

postgres_fdw connects to the remote server, executes SQL, and returns rows to the local planner.

## Query pushdown

The local planner decomposes queries into **remote SQL** sent to the foreign server and **local processing** for operations that cannot be pushed.

Pushed operations (when supported):

- `WHERE` clause filters on remote columns
- `JOIN` between foreign tables on the same server
- `ORDER BY` on remote columns (with limit pushdown)
- Aggregate pushdown (PG 10+ for simple cases)
- `FOR UPDATE` (PG 14+ with limitations)

Check pushdown with EXPLAIN:

```sql
EXPLAIN (VERBOSE, COSTS OFF)
SELECT email FROM remote_users WHERE created_at > '2026-01-01';

-- Look for:
-- Foreign Scan on remote_users
--   Remote SQL: SELECT email, created_at FROM public.users
--               WHERE (created_at > '2026-01-01'::timestamptz)
```

Bad — no filter pushdown:

```sql
EXPLAIN SELECT email FROM remote_users WHERE lower(email) = 'alice@example.com';
-- Filter applied locally after fetching all rows
```

Fix: create a functional index on the remote server and match the expression, or add an immutable wrapper function marked for pushdown.

## Joining local and foreign tables

```sql
SELECT o.id, o.total, u.email
FROM local_orders o
JOIN remote_users u ON u.id = o.user_id
WHERE o.status = 'pending';
```

The planner may:

1. Fetch all pending orders locally, then nested loop to remote for each user (slow)
2. Push the join to remote if both tables are on the same foreign server
3. Hash join locally after fetching both sides (memory-intensive)

Force better plans with statistics:

```sql
IMPORT FOREIGN SCHEMA public
  LIMIT TO (users)
  FROM SERVER identity_server
  INTO fdw_identity;

ANALYZE fdw_identity.users;  -- PG 14+ auto-analyze foreign tables
```

Set remote estimate options:

```sql
ALTER FOREIGN TABLE remote_users
  OPTIONS (ADD use_remote_estimate 'true');
```

`use_remote_estimate` asks the remote server for row counts — more accurate plans, extra round trip during planning.

## Performance tuning options

```sql
ALTER SERVER identity_server OPTIONS (
  SET fetch_size '10000',        -- rows per fetch (default 100)
  SET batch_size '1000',         -- INSERT batch size
  SET application_name 'fdw_coordinator'
);

ALTER FOREIGN TABLE remote_users OPTIONS (
  ADD async_capable 'true'       -- PG 14+ async append
);
```

**fetch_size**: Increase for large scans to reduce round trips. Memory cost scales with row width × fetch_size.

**Connection pooling**: Each local backend opens a connection to the remote server. With 100 local connections, you get 100 remote connections. Use PgBouncer on the remote side or limit `max_connections` impact.

**Materialized foreign tables**: For read-heavy reporting, materialize locally:

```sql
CREATE MATERIALIZED VIEW local_user_cache AS
SELECT * FROM remote_users;

REFRESH MATERIALIZED VIEW CONCURRENTLY local_user_cache;
```

Refresh on schedule via pg_cron instead of live FDW queries.

## Write operations

Writable foreign tables:

```sql
CREATE FOREIGN TABLE remote_audit_log (...)
SERVER identity_server
OPTIONS (schema_name 'public', table_name 'audit_log');

INSERT INTO remote_audit_log (event, payload) VALUES ('login', '{"user": "alice"}');
```

Each INSERT is typically a remote round trip. Bulk insert:

```sql
INSERT INTO remote_audit_log
SELECT event, payload FROM local_staging_events;
-- May batch depending on PG version and batch_size setting
```

Updates and deletes push WHERE clauses when possible:

```sql
UPDATE remote_users SET email = 'new@example.com' WHERE id = '...';
-- Remote SQL: UPDATE public.users SET email = $1 WHERE id = $2
```

## Transaction behavior

Default: local and remote transactions are **independent**. Local COMMIT succeeds even if remote write fails afterward in multi-statement transactions — unless using prepared transactions with two-phase commit.

```sql
BEGIN;
  INSERT INTO local_orders VALUES (...);
  INSERT INTO remote_audit_log VALUES (...);
COMMIT;
-- Not atomic across servers by default
```

For cross-server atomicity, configure two-phase commit (complex, rarely used in practice). Application-level outbox or saga patterns handle cross-database consistency more reliably.

## Security model

**User mapping**: Maps local roles to remote credentials. Use least-privilege remote users:

```sql
-- On remote server
CREATE ROLE fdw_reader WITH LOGIN PASSWORD '...';
GRANT SELECT ON users TO fdw_reader;
-- Not SUPERUSER, not write access unless needed
```

**Credential storage**: Passwords in user mappings are visible to superusers:

```sql
SELECT * FROM pg_user_mappings;
```

Use vault integration or certificate auth for remote connections where supported.

**Network**: FDW traffic is standard Postgres protocol — encrypt with `sslmode=require` in server options:

```sql
ALTER SERVER identity_server OPTIONS (ADD sslmode 'require');
```

**Row-level security**: Remote RLS policies apply on the remote server using the mapped remote user — not the local user.

## Sharding pattern with FDW

Postgres native sharding (PG 15+ improvements, Citus extension) often uses FDW under the hood. Manual sharding:

```sql
-- Shard by tenant on separate databases
CREATE FOREIGN TABLE tenant_a_orders (...) SERVER tenant_a_server ...;
CREATE FOREIGN TABLE tenant_b_orders (...) SERVER tenant_b_server ...;

CREATE VIEW all_orders AS
  SELECT 'a' AS tenant, * FROM tenant_a_orders
  UNION ALL
  SELECT 'b' AS tenant, * FROM tenant_b_orders;
```

Query routing in application code beats UNION ALL across many shards for OLTP.

## Alternatives comparison

| Approach | Latency | Consistency | Complexity |
| --- | --- | --- | --- |
| postgres_fdw | Network per query | Independent TX | Low |
| Application fan-out | Network per service | Application-managed | Medium |
| ETL to warehouse | Minutes-hours | Eventual | Medium |
| Schema consolidation | Local | Full ACID | High (migration) |
| Citus/distributed PG | Low (co-located) | Distributed TX | High |

## Monitoring

Track FDW activity:

```sql
-- Remote query duration in pg_stat_statements on coordinator
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
WHERE query LIKE '%postgres_fdw%' OR query LIKE '%remote_%'
ORDER BY mean_exec_time DESC;
```

On remote server, monitor connections from FDW coordinator IP — they appear as regular client connections in `pg_stat_activity`.

## Common mistakes

**Selecting * from large foreign table without filter**: Fetches entire remote table across network.

**Ignoring statistics**: Planner assumes 1000 rows default without `use_remote_estimate` — chooses nested loop when hash join is correct.

**Write-heavy FDW for OLTP**: Each row is a network round trip. Use local tables with async replication instead.

**Same server, different database**: FDW works but `dblink` or schema consolidation may be simpler for same-cluster cross-database access.

## Cost-based planner tuning for FDW

Foreign table statistics dramatically affect plan quality. After bulk loads on the remote server, refresh:

```sql
-- On remote server
ANALYZE remote_schema.users;

-- On coordinator — import updated stats
IMPORT FOREIGN SCHEMA remote_schema LIMIT TO (users)
  FROM SERVER identity_server INTO fdw_identity;
```

Adjust cost settings when network latency dominates:

```sql
ALTER SERVER identity_server OPTIONS (
  SET use_remote_estimate 'true',
  SET fdw_startup_cost '100',
  SET fdw_tuple_cost '0.05'
);
```

Higher `fdw_startup_cost` discourages the planner from choosing FDW when a local materialized cache would be cheaper. Benchmark with EXPLAIN ANALYZE comparing direct FDW query vs materialized view refresh cycle — the crossover point depends on refresh frequency and data change rate.

## Summary

postgres_fdw makes remote Postgres tables queryable from local SQL with filter and join pushdown reducing network transfer. Configure fetch_size, remote statistics, and materialized caches for reporting workloads. Treat FDW as a migration bridge and analytics tool — not as a distributed OLTP join engine. Secure user mappings with least privilege, encrypt connections, and understand that cross-server transactions are not atomic by default.


If EXPLAIN VERBOSE shows a remote SELECT without your WHERE clause, fix pushdown before tuning fetch_size — you are shipping the table across the network.
