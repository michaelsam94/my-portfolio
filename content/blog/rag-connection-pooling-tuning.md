---
title: "Database Connection Pool Tuning Under Real Load"
slug: "rag-connection-pooling-tuning"
description: "Tune database connection pools for agent workloads: size pools against tool-loop concurrency, set idle and lifetime limits, handle prepared statements, and measure wait time instead of guessing."
datePublished: "2024-11-23"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Connection"]
keywords: "connection pool tuning agents, PostgreSQL pool size, HikariCP agent workloads, pool exhaustion agent loops, database connection wait time"
faq:
  - q: "How big should a connection pool be for an agent API service?"
    a: "Start with (expected concurrent agent runs × average DB-using tools per run) + 10% headroom — then cap by Postgres max_connections divided by replica count and service instances. A single agent turn firing four parallel retrieval tools can hold four connections simultaneously; request-level pooling math that assumes one query per HTTP request will exhaust the pool."
  - q: "What is the most common pool misconfiguration in agent stacks?"
    a: "maxPoolSize set to the framework default (often 10) while horizontal pod autoscaling adds replicas — each replica opens its own pool, and aggregate connections exceed Postgres limits. The second most common: idleTimeout too high, keeping connections open during long LLM waits and starving active tool calls."
  - q: "Should agent services use prepared statements with connection pooling?"
    a: "With transaction-level poolers like PgBouncer in transaction mode, disable prepared statement caching in the driver or use statement names carefully — prepared plans are tied to backend sessions. With session pooling or direct connections, prepared statements are fine and help repeated retrieval queries."
---

The incident page said "database timeout." The Postgres dashboard showed CPU at 30% and disk I/O flat. What spiked was **connection wait time** — 200 sessions each running a three-processing loop had opened 600 concurrent transactions, and the pool max of 20 per pod meant most tool calls sat in queue for eight seconds while the upstream service happily streamed tokens.

Connection pooling for data-intensive workloads breaks the assumptions baked into typical web-app defaults. A REST API might hold a connection for 50 ms per request. An request holds a connection **only during tool execution** but may acquire and release multiple times per turn, burst parallel acquisitions during fan-out retrieval, and idle between model inference calls long enough for stale connections to die quietly.

Tuning pools is arithmetic constrained by Postgres physics — not a magic number from a tutorial.

## The connection lifecycle under load

Map one user message through the system:

```
HTTP request arrives
  → load session (acquire conn, query, release)
  → call LLM (NO conn held — 2–30 seconds)
  → tool: vector search (acquire, query, release)
  → tool: SQL analytics (acquire, query, release)
  → tool: write audit log (acquire, insert, release)
  → call LLM again
  → persist turn (acquire, transaction, release)
```

The anti-pattern: wrapping the entire request in `@Transactional` or holding a connection in request-scoped context while awaiting the model. That ties up pool slots during the most expensive non-DB phase of the pipeline.

Rule one: **connections span database work only**, never LLM or HTTP tool calls to external APIs.

Rule two: **parallel tools mean parallel acquisitions**. If your runtime executes tools concurrently, peak demand is the sum of concurrent DB tools, not one.

## Sizing formula

For each service instance:

```
pool_max = min(
  (concurrent_agent_runs × db_tools_per_run × parallel_factor),
  (postgres_max_connections - superuser_reserve) / (num_app_instances × num_services)
)
```

Example: Postgres `max_connections=200`, reserve 20 for admin, 5 API pods, 2 services sharing the DB (API + embedding worker):

```
per_service_budget = (200 - 20) / (5 × 2) = 18 connections per pod per service
```

If your processing loop needs 8 concurrent connections at peak, `maxPoolSize=18` works with headroom. If you need 25, you do not raise the pool — you add PgBouncer, reduce parallel tool fan-out, or scale Postgres connections with realistic cost analysis.

Add **10–15% headroom** for admin queries, health checks, and migration jobs — not 2× "just to be safe."

## HikariCP configuration for Node/Java agent services

Java example (Spring runtime):

```yaml
spring:
  datasource:
    hikari:
      maximum-pool-size: 18
      minimum-idle: 4
      connection-timeout: 5000      # fail fast — don't queue forever
      idle-timeout: 300000          # 5 min — release during idle sessions
      max-lifetime: 1800000         # 30 min — rotate before LB/firewall drops
      keepalive-time: 120000        # 2 min — probe idle connections
      leak-detection-threshold: 60000
      pool-name: agent-api
```

Node (`pg` pool):

```typescript
import { Pool } from "pg";

export const pool = new Pool({
  host: process.env.PGHOST,
  database: process.env.PGDATABASE,
  max: 18,
  min: 4,
  connectionTimeoutMillis: 5000,
  idleTimeoutMillis: 300_000,
  maxLifetimeSeconds: 1800,
  allowExitOnIdle: true,
});

// Always release — especially in tool error paths
export async function withConnection<T>(
  fn: (client: PoolClient) => Promise<T>
): Promise<T> {
  const client = await pool.connect();
  const start = Date.now();
  try {
    return await fn(client);
  } finally {
    client.release();
    poolMetrics.acquireDuration.observe(Date.now() - start);
  }
}
```

`connectionTimeoutMillis` is your user-visible latency ceiling when the pool is saturated. Five seconds is long for a web CRUD app; for tool calls it is acceptable if you surface a retry — but investigate immediately if p95 acquire time exceeds 500 ms.

## Do not pool across the LLM await

The bug pattern in async agent frameworks:

```typescript
// BAD: connection held during entire turn
async function handleTurn(sessionId: string, message: string) {
  const client = await pool.connect();
  try {
    const history = await loadHistory(client, sessionId);
    const llmResponse = await callLLM(history, message); // 20s — conn idle in pool slot
    await saveTurn(client, sessionId, llmResponse);
  } finally {
    client.release();
  }
}

// GOOD: narrow scopes
async function handleTurn(sessionId: string, message: string) {
  const history = await withConnection(c => loadHistory(c, sessionId));
  const llmResponse = await callLLM(history, message);
  await withConnection(c => saveTurn(c, sessionId, llmResponse));
}
```

Some ORMs make narrow scoping verbose. The refactor pays for itself the first time concurrent sessions exceed pool capacity during a demo.

## Parallel tool fan-out

When the agent invokes three retrieval tools in parallel:

```typescript
async function runRetrievalTools(queries: string[]) {
  return Promise.all(
    queries.map(q =>
      withConnection(async client => {
        return vectorSearch(client, q);
      })
    )
  );
}
```

Peak connections = `queries.length`. Cap parallelism:

```typescript
import pLimit from "p-limit";

const dbLimit = pLimit(3); // matches pool budget per turn

async function runRetrievalTools(queries: string[]) {
  return Promise.all(
    queries.map(q =>
      dbLimit(() => withConnection(client => vectorSearch(client, q)))
    )
  );
}
```

Match `dbLimit` to your per-turn connection budget. Uncapped `Promise.all` against a pool of 18 is a load test you did not intend to run.

## Prepared statements and poolers

If PgBouncer sits in **transaction mode** (common at scale), server-side prepared statements break — the backend session changes between transactions. Driver settings:

```
# JDBC
spring.datasource.hikari.data-source-properties.prepareThreshold=0

# node-pg — disable prepared statements or use simple query protocol
```

With **session mode** PgBouncer or direct Postgres, enable prepared statements for hot retrieval queries — measurable win on repeated `SELECT ... WHERE embedding <=> $1` patterns.

Know your pooler mode before tuning the driver. Misalignment manifests as cryptic `prepared statement "S_1" does not exist` errors under load.

## Read replicas and routing

Agent read-heavy tools (RAG retrieval, conversation history) should target read replicas. Separate pools:

```typescript
const writePool = new Pool({ host: process.env.PG_PRIMARY, max: 8 });
const readPool = new Pool({ host: process.env.PG_REPLICA, max: 24 });
```

Read pool can be larger — replicas tolerate more connections than the primary tolerates write load. Route analytics and long-running reporting tools to a dedicated replica pool so ad-hoc SQL from an tool does not compete with latency-sensitive retrieval.

Track **replication lag**. Stale reads on conversation history confuse users; enforce max lag routing:

```typescript
async function getReadPool(): Promise<Pool> {
  const lagMs = await checkReplicationLag();
  if (lagMs > 5000) return writePool; // fallback to primary
  return readPool;
}
```

## Metrics that matter

Export from the pool and the driver:

| Metric | What it tells you |
|--------|-------------------|
| `pool.connections.active` | Current in-use |
| `pool.connections.idle` | Available |
| `pool.connections.pending` | Tasks waiting — **alert if > 0 sustained** |
| `pool.acquire.duration.p95` | Undersized pool or slow queries |
| `pool.connections.timeouts` | Hard exhaustion — user-visible failures |
| Postgres `pg_stat_activity.count` | Ground truth vs pool metrics |

Alert: `pending > 5 for 2 minutes` OR `acquire.duration.p95 > 1s`. Do not alert on active/max ratio alone — a healthy pool runs hot.

Log **connection leak warnings** from HikariCP (`leak-detection-threshold`). Agent code paths with early returns and forgotten `release()` accumulate slowly until sudden exhaustion.

## Load testing agent-shaped traffic

Uniform QPS misses agent burst patterns. Script load tests that:

1. Spawn N concurrent sessions
2. Each session: read history → idle 2s (LLM) → 3 parallel DB tools → idle 5s → write turn
3. Ramp N until `pool.connections.pending` sustains above zero

Compare against production traces. Your load test should reproduce the **acquire wait spike**, not just query latency.

## Failure modes and mitigation

- **Thundering herd after deploy**: cold pools on new pods + traffic shift → stagger rollouts, use `minimum-idle`, pre-warm connections on startup
- **Long transactions from migration scripts**: run migrations outside the app pool with a dedicated admin connection — never share the app Hikari pool
- **Connection storms on retry**: tool retry loops that re-acquire on every attempt — add backoff and cap retries; consider circuit breaking the DB path
- **IPv6/DNS flapping**: `maxLifetime` shorter than your network middlebox TCP timeout causes mysterious disconnects — align lifetime with infra docs (often 30 min or less)

When saturation occurs, the fix order is: stop holding connections across LLM awaits → cap parallel DB tools → add read replica capacity → add PgBouncer → increase Postgres `max_connections`. Skipping straight to max_connections invites OOM on the database.

## The takeaway

Data-intensive workloads turn connection pools into a concurrency problem dressed as a database problem. Size pools from tool parallelism and session concurrency, not HTTP QPS. Keep connections scoped to query execution, measure acquire wait time, and align driver settings with your pooler mode. A pool that looks "big enough" on average will still catch fire at the p99 agent burst — tune for that burst, or queue gracefully with a timeout users can understand.

## Resources

- [HikariCP pool sizing wiki](https://github.com/brettwooldridge/HikariCP/wiki/About-Pool-Sizing)
- [PostgreSQL connection management](https://www.postgresql.org/docs/current/runtime-config-connection.html)
- [node-postgres pool documentation](https://node-postgres.com/apis/pool)
- [PgBouncer features and pool modes](https://www.pgbouncer.org/features.html)
- [AWS RDS connection max recommendations](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Limits.html)
