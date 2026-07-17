---
title: "PgBouncer as a PostgreSQL Connection Proxy"
slug: "rag-connection-proxy-pgbouncer"
description: "Deploy PgBouncer in front of Postgres for agent platforms: choose transaction vs session pooling, configure auth and TLS, handle prepared statements, and monitor multiplexing without breaking tool loops."
datePublished: "2024-12-18"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Connection"]
keywords: "PgBouncer agent workloads, transaction pooling Postgres, connection multiplexing agents, PgBouncer prepared statements, agent database proxy"
faq:
  - q: "Should agent services use PgBouncer transaction or session pooling?"
    a: "Transaction pooling for stateless tool queries and short reads — it multiplexes best. Session pooling when you rely on prepared statements, temp tables, LISTEN/NOTIFY, or SET parameters that must persist across queries in one agent turn. Many agent stacks use transaction mode for retrieval and a separate session-mode pool for analytics workloads."
  - q: "How many client connections can PgBouncer handle for an agent fleet?"
    a: "PgBouncer handles thousands of client connections with hundreds of server connections — that is the point. Set default_pool_size per database/user based on Postgres capacity, not client count. Agent pods scaling to 50 replicas × 20 pool slots = 1000 clients multiplexed into 80 server connections is normal and healthy."
  - q: "Why do agent apps break with prepared statement errors through PgBouncer?"
    a: "In transaction mode, each transaction may run on a different backend session — server-side prepared plans vanish. Fix by disabling prepared statements in the driver, using PgBouncer 1.21+ with max_prepared_statements, or switching affected workloads to session mode."
---

Fifty API pods autoscale on GPU queue depth. Each pod opens a Hikari pool of twenty connections. The math is quick: **1000 client connections** hitting a Postgres instance with `max_connections=200`. The database did not run out of CPU — it ran out of connection slots, and new tool calls failed with `FATAL: sorry, too many clients already`.

PgBouncer sits between agent services and Postgres as a **connection multiplexer**. Thousands of short-lived client connections fold into a bounded set of server connections. For agent platforms where connection count scales with pod count × tool parallelism, PgBouncer is not optional infrastructure — it is the difference between horizontal scaling and a hard ceiling.

## Architecture overview

```
┌─────────────┐  ┌─────────────┐       ┌───────────┐       ┌──────────┐
│ agent-api   │  │ agent-api   │  ...  │ PgBouncer │ ────► │ Postgres │
│ pod (×50)   │  │ pod (×50)   │       │ (×2 HA)   │       │ primary  │
└─────────────┘  └─────────────┘       └───────────┘       └──────────┘
   20 conn each     20 conn each         ~80 server conn      max_conn=200
   = 1000 clients                      multiplexed
```

Agent services connect to PgBouncer hostname, not Postgres directly. PgBouncer maintains a warm pool of backend connections per `(database, user)` pair and assigns them for the duration of a transaction (transaction mode) or client session (session mode).

## Pool mode selection

| Mode | Multiplexing | Agent use case | Caveats |
|------|--------------|----------------|---------|
| Transaction | Best | RAG retrieval, session reads, audit inserts | No prepared stmts*, no temp tables across queries |
| Session | Moderate | Migrations, LISTEN/NOTIFY, advisory locks | One backend per client — defeats multiplexing |
| Statement | Aggressive (rare) | Autocommit single-statement only | Breaks multi-statement transactions |

*PgBouncer 1.21+ supports `max_prepared_statements` in transaction mode — verify your version.

Default recommendation: **transaction mode** for the API read/write path. If a specific tool needs session semantics, route it through a separate PgBouncer database entry in session mode with a small `pool_size`.

## PgBouncer configuration

Production `pgbouncer.ini` baseline for data-intensive workloads:

```ini
[databases]
agents = host=postgres-primary.internal port=5432 dbname=agents pool_size=60
agents_session = host=postgres-primary.internal port=5432 dbname=agents pool_mode=session pool_size=10

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = scram-sha-256
auth_file = /etc/pgbouncer/userlist.txt

pool_mode = transaction
max_client_conn = 2000
default_pool_size = 60
min_pool_size = 10
reserve_pool_size = 10
reserve_pool_timeout = 3

server_reset_query = DISCARD ALL
server_idle_timeout = 600
server_lifetime = 3600
query_timeout = 30
client_idle_timeout = 300

log_connections = 0
log_disconnections = 0
stats_period = 60

admin_users = pgbouncer_admin
```

Key knobs:

- **`max_client_conn`**: upper bound on agent pod connections — set above expected fleet size
- **`default_pool_size`**: actual Postgres connections per user/db — sized from Postgres budget
- **`reserve_pool`**: burst buffer when the main pool is exhausted — 3-second timeout prevents indefinite queue
- **`server_reset_query = DISCARD ALL`**: cleans session state between transaction-mode clients — critical for production apps that accidentally `SET` parameters

## Kubernetes deployment pattern

Shared pooler Deployment (preferred over per-pod sidecars):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pgbouncer
  namespace: data
spec:
  replicas: 2
  selector:
    matchLabels:
      app: pgbouncer
  template:
    spec:
      containers:
        - name: pgbouncer
          image: edoburu/pgbouncer:1.22.0
          ports:
            - containerPort: 6432
          volumeMounts:
            - name: config
              mountPath: /etc/pgbouncer
          livenessProbe:
            tcpSocket:
              port: 6432
          readinessProbe:
            exec:
              command: ["psql", "-h", "127.0.0.1", "-p", "6432", "-U", "pgbouncer_admin", "-c", "SHOW POOLS;"]
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              memory: 256Mi
```

Agent API pods point at the ClusterIP service:

```yaml
env:
  - name: PGHOST
    value: pgbouncer.data.svc.cluster.local
  - name: PGPORT
    value: "6432"
```

Use a **PodDisruptionBudget** `minAvailable: 1` so pooler maintenance does not drop all multiplexing during node drains.

## Auth: SCRAM through the proxy

PgBouncer terminates client auth and authenticates to Postgres separately:

```ini
# userlist.txt
"agent_api" "SCRAM-SHA-256$4096:..."
"pgbouncer_admin" "SCRAM-SHA-256$4096:..."
```

For Kubernetes, mount userlist from ExternalSecrets. Rotate credentials by updating both Postgres role and PgBouncer userlist in one change window.

TLS options:

- **Client → PgBouncer**: enable `client_tls_sslmode = require` when traffic crosses nodes
- **PgBouncer → Postgres**: `server_tls_sslmode = verify-full` with CA mounted in the pooler pod

Agent platforms often skip TLS on client→pooler inside the mesh (mTLS via Istio/Linkerd) while enforcing TLS on pooler→Postgres.

## Driver configuration for transaction mode

Disable prepared statements when using classic transaction pooling:

```typescript
// node-pg
const pool = new Pool({
  host: "pgbouncer.data.svc.cluster.local",
  port: 6432,
  max: 20,
  // Disable extended query protocol prepared statements
  // Option: use pg-native or set via connection param
});

// Prisma
// datasource url: "...?pgbouncer=true&connection_limit=20"
```

```yaml
# Spring Boot + Hikari through PgBouncer transaction mode
spring.datasource.url: jdbc:postgresql://pgbouncer:6432/agents?prepareThreshold=0
spring.datasource.hikari.maximum-pool-size: 20
```

With PgBouncer 1.21+ and `max_prepared_statements = 100`, you can re-enable prepared statements for hot queries — benchmark before rolling out; memory per prepared plan adds up across 60 server connections.

## Agent-specific pitfalls

**Long transactions block multiplexing.** A tool that opens a transaction and then calls an external API before committing holds a backend connection for the entire duration — same anti-pattern as holding app-pool connections across LLM awaits. PgBouncer cannot fix application-level hold time; it only multiplexes between transactions.

**Advisory locks and session state.** Agent job schedulers using `pg_advisory_lock` need session mode on a dedicated pool entry. Mixing advisory locks in transaction mode causes locks to release at transaction end — sometimes intended, often not.

**LISTEN for realtime agent updates.** If your agent dashboard uses Postgres NOTIFY, that connection must be session-pooled or direct to Postgres — transaction mode drops channel subscriptions.

**Multi-statement migrations.** Flyway/Liquibase through transaction-mode PgBouncer works for simple migrations; complex DDL with temp tables needs a direct admin connection bypassing the pooler.

## Monitoring PgBouncer

Admin console queries:

```sql
-- Connect: psql -h pgbouncer -p 6432 -U pgbouncer_admin pgbouncer
SHOW POOLS;
SHOW STATS;
SHOW CLIENTS;
SHOW SERVERS;
```

Critical columns in `SHOW POOLS`:

- `cl_active` / `cl_waiting`: clients executing / queued — **cl_waiting > 0 sustained is an alert**
- `sv_active` / `sv_idle`: server connections in use / available
- `maxwait`: longest wait time for a server connection

Export via Prometheus pgbouncer_exporter or parse `SHOW STATS` in a sidecar:

```
pgbouncer_pools_client_waiting{database="agents"} > 0
pgbouncer_pools_server_active / pgbouncer_pools_server_total > 0.9
```

Correlate with agent metrics: `agent_tool_db_duration_ms` and `pool.acquire.duration`. If PgBouncer wait rises but Postgres CPU is low, you need more `pool_size` or fewer long transactions — not a bigger RDS instance.

## HA and failover

Run two PgBouncer replicas behind a Service. They are stateless — scaling is horizontal. On Postgres failover:

1. Update `[databases]` host to new primary (or use a DNS name that follows failover)
2. `RELOAD` PgBouncer: `psql -c "RELOAD;"` on admin console
3. Agent pods reconnect automatically if `connectionTimeout` and retry logic are configured

For managed Postgres (RDS, Cloud SQL), pair with their recommended proxy (RDS Proxy, Auth Proxy) when you want automatic failover handling — PgBouncer alone does not redirect on primary change unless DNS or config updates.

Connection storm after failover: agent pods retry simultaneously. Use **jittered backoff** in the driver and cap `reserve_pool_size` to prevent thundering herd against a recovering primary.

## Sizing worked example

Postgres `max_connections=250`, reserve 30 for replication and admin.

Budget for API through PgBouncer: 180 server connections.

```
default_pool_size = 180 / num_pgbouncer_replicas
                  = 180 / 2 = 90 per pooler instance
```

Agent fleet: 40 pods × 20 client connections = 800 clients → 800:180 multiplex ratio.

If `SHOW POOLS` shows `cl_waiting` during peak traffic, increase `default_pool_size` until waiting clears or Postgres CPU becomes the bottleneck — whichever comes first.

## When PgBouncer is not enough

- **Query volume** exceeds Postgres capacity even with multiplexing → read replicas, caching, or archive cold conversation data
- **Session affinity requirements** dominate (most connections need session mode) → multiplexing benefit collapses; reconsider architecture
- **Global low-latency requirements** with cross-region agents → regional Postgres + regional PgBouncer, not one global pooler

PgBouncer solves **connection count**, not **query cost**. An agent that runs unindexed vector scans will still melt CPU with fifty server connections.

## The takeaway

Agent platforms scale pods faster than Postgres scales connection slots. PgBouncer multiplexes the connection storm into a bounded server pool, but only when agent services use short transactions and drivers configured for transaction mode. Deploy a shared HA pooler, monitor `cl_waiting`, disable prepared statements unless your PgBouncer version supports them, and keep session-mode escape hatches for the tools that genuinely need backend stickiness.

## Resources

- [PgBouncer official documentation](https://www.pgbouncer.org/usage.html)
- [PgBouncer config reference](https://www.pgbouncer.org/config.html)
- [PgBouncer 1.21 prepared statement support](https://www.pgbouncer.org/changelog.html)
- [PostgreSQL connection limits](https://www.postgresql.org/docs/current/runtime-config-connection.html)
- [Crunchy Data PgBouncer Kubernetes guide](https://www.crunchydata.com/blog/pgbouncer-in-kubernetes)
