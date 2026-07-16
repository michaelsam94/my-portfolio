---
title: "Connection Pooling for Serverless Databases"
slug: "connection-pooling-serverless-databases"
description: "Why serverless functions exhaust database connections, and how connection pooling with PgBouncer and data proxies keeps Postgres from falling over."
datePublished: "2026-01-16"
dateModified: "2026-01-16"
tags: ["Backend", "Databases", "Serverless"]
keywords: "connection pooling, serverless database, pgbouncer, connection limits, data proxy, edge database pooling"
faq:
  - q: "Why do serverless functions exhaust database connections?"
    a: "Each concurrent function invocation tends to open its own database connection, and serverless platforms can scale to hundreds or thousands of instances almost instantly. Postgres allocates a backend process per connection and has a hard max_connections limit, so a traffic spike opens more connections than the database can serve, causing timeouts and 'too many clients' errors. Connection pooling breaks that one-to-one mapping between invocations and database connections."
  - q: "What's the difference between transaction and session pooling in PgBouncer?"
    a: "In session pooling, a client holds a server connection for the entire client session, which limits reuse. In transaction pooling, a server connection is assigned only for the duration of a transaction and then returned to the pool, so far more clients can share a small number of real connections. Transaction pooling is the right mode for serverless, but it disallows session-level features like prepared statements and LISTEN/NOTIFY unless handled carefully."
  - q: "Do I need a pooler if I use a serverless database like Neon or PlanetScale?"
    a: "Those platforms usually build pooling in — Neon offers a PgBouncer-backed pooled endpoint, and PlanetScale multiplexes connections at its edge. You still choose between the pooled and direct endpoints depending on whether you need session features, and you still size concurrency so you don't overwhelm the pooler itself. Managed pooling reduces the work but doesn't remove the design decision."
---

The first time a serverless app takes real traffic, the database is usually what breaks — not the functions. You'll see `FATAL: sorry, too many clients already` in the logs while your function count looks healthy, and the reason is a mismatch baked into the architecture. Connection pooling for serverless databases is the fix: a layer that decouples the number of function invocations from the number of actual database connections, so a thousand concurrent Lambdas don't try to open a thousand Postgres backends.

I've debugged this exact failure at 2 a.m. more than once, and the trap is that everything works perfectly in testing and dev, then collapses under the first real spike. Here's why it happens and how to actually solve it.

## The impedance mismatch at the core

Traditional databases were built for a world of long-lived, relatively few connections. Postgres in particular forks a **backend process per connection** — each one costs memory and scheduling overhead — and it enforces a hard `max_connections`, commonly 100 on a modest instance. A classic app server keeps a small warm pool (say 10–20 connections) and reuses them across thousands of requests. That model is efficient precisely because connections are expensive to create and are shared.

Serverless inverts every assumption. Each invocation is stateless and, by default, opens its own connection. The platform scales instances horizontally with no coordination, so 500 concurrent requests can mean 500 connection attempts within a second. Even if your database could handle the query load, it can't handle the *connection* load — the processes alone will exhaust memory or blow past `max_connections`. This is one of the sharper edges of the [serverless model in 2026](https://blog.michaelsam94.com/serverless-2026/): compute scales instantly, but stateful backends behind it do not.

## PgBouncer and transaction pooling

The canonical answer for Postgres is [PgBouncer](https://www.pgbouncer.org/), a lightweight external pooler that sits between your app and the database. Clients connect to PgBouncer; PgBouncer maintains a small set of real connections to Postgres and multiplexes many clients over them.

The critical setting is pool mode. **Transaction pooling** is what makes serverless viable:

```ini
[databases]
appdb = host=127.0.0.1 port=5432 dbname=appdb

[pgbouncer]
pool_mode = transaction
max_client_conn = 5000
default_pool_size = 20
```

With `max_client_conn = 5000` and `default_pool_size = 20`, five thousand function instances can connect to PgBouncer while only twenty real connections ever touch Postgres. A server connection is borrowed for the length of a single transaction and immediately returned. The math is the whole point: client concurrency and database concurrency become independent numbers you can tune separately.

The cost of transaction pooling is that **session-scoped features stop working transparently** — server-side prepared statements, `LISTEN/NOTIFY`, session-level `SET`, and advisory locks that span statements. Most ORMs can be configured to disable prepared statements or use protocol-level ones. If your code relies on session state across queries, transaction pooling will bite you, and you need to know that before you flip it on.

## Where the pooler should live

Placement matters as much as configuration. You have three broad options, and each has a different failure profile:

| Pooler location | Latency added | Operational burden | Best for |
| --- | --- | --- | --- |
| In-database (built-in) | Lowest | Managed for you | Neon, Supabase, managed Postgres |
| Sidecar / same VPC | Low | You run PgBouncer | Self-hosted, VMs, ECS |
| Data proxy (HTTP) | Higher | Managed, HTTP-based | Edge functions, cold regions |

For AWS Lambda in a VPC, running PgBouncer on a small instance or using **RDS Proxy** keeps the hop cheap. For edge runtimes that can't hold a TCP connection at all — think Cloudflare Workers or Vercel Edge — you often need an **HTTP data proxy** (Neon's serverless driver, PlanetScale's HTTP API, Prisma Accelerate) that turns queries into stateless HTTP requests and pools on the far side. The tradeoff is real: HTTP proxies add latency per query but survive environments where a persistent connection is impossible.

## The application-side discipline

Pooling infrastructure only helps if the application cooperates. A few rules I enforce on every serverless codebase:

- **Reuse the client across invocations.** Declare the connection/client *outside* the handler so a warm instance reuses it instead of reconnecting on every call.
- **Cap the per-instance pool at 1–2.** Each warm instance should hold at most a connection or two; the platform's horizontal scaling is your concurrency, not a big local pool.
- **Set aggressive timeouts.** Connection acquisition and query timeouts should be short and explicit, so a stalled pool fails fast instead of piling up.
- **Close nothing eagerly.** Don't tear down the connection at the end of the handler — let it live with the warm instance.

```typescript
// Declared at module scope, reused across warm invocations
import { Pool } from "pg";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL, // the pooled endpoint
  max: 1,
  connectionTimeoutMillis: 3000,
  idleTimeoutMillis: 10000,
});

export async function handler(event) {
  const { rows } = await pool.query(
    "select id, email from users where id = $1",
    [event.userId]
  );
  return rows[0];
}
```

Point `DATABASE_URL` at the **pooled** endpoint for normal traffic and keep the direct endpoint only for migrations and admin tasks — the direct one bypasses the pooler and is what you want for schema changes, which is also relevant when you're doing [zero-downtime database migrations](https://blog.michaelsam94.com/zero-downtime-database-migrations/) where you need predictable session behavior.

## Sizing, and knowing when it's not enough

Sizing the pool is a capacity exercise: `default_pool_size` should be set so the total real connections across all poolers stays comfortably under `max_connections`, leaving headroom for admin sessions and replicas. A rule I use is to reserve ~20% of `max_connections` for non-app use and divide the rest across poolers.

And a senior-engineer caveat: pooling solves the *connection* problem, not the *load* problem. If your queries are slow, a pooler just means requests queue at the pooler instead of erroring at the database — you've moved the bottleneck, not removed it. When I see a pool saturated with 20 busy connections all running 500ms queries, the answer is query optimization and caching, not a bigger pool. Pooling buys you connection efficiency; it does not buy you a faster database.

Get the pooler in place, run transaction mode, reuse clients across warm instances, and size for headroom, and the "too many clients" pages stop. It's one of those unglamorous pieces of plumbing that, done right, you never think about again — which is exactly the goal.

## Resources

- [PgBouncer documentation](https://www.pgbouncer.org/config.html)
- [PostgreSQL connection settings reference](https://www.postgresql.org/docs/current/runtime-config-connection.html)
- [Amazon RDS Proxy documentation](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-proxy.html)
- [Neon connection pooling guide](https://neon.tech/docs/connect/connection-pooling)
- [Supabase connection pooling docs](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [PlanetScale connection strategy docs](https://planetscale.com/docs/concepts/connection-pooling)
