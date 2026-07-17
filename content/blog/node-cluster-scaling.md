---
title: "Scaling Node.js with Cluster"
slug: "node-cluster-scaling"
description: "Scale Node.js across CPU cores with the cluster module: worker forking, zero-downtime restarts, load distribution, and when to prefer PM2 or containers."
datePublished: "2025-09-06"
dateModified: "2026-07-17"
tags:
keywords: "Node.js cluster module, scale Node.js, multi-core Node.js, PM2 cluster mode, zero downtime restart Node.js, worker processes"
faq:
  - q: "Does the cluster module make a single Node.js request faster?"
    a: "No. Cluster spreads concurrent requests across CPU cores—each worker still handles one request at a time on its event loop. A single CPU-bound request on one worker is not faster. Throughput scales with core count for I/O-bound workloads."
  - q: "When should I use cluster vs running multiple containers?"
    a: "Use cluster for single-server deployments where you want to utilize all cores without orchestration overhead. Use multiple containers (Kubernetes, Docker Compose) when you need horizontal scaling across machines, independent deploys, or isolation between instances."
  - q: "How do I share sessions across cluster workers?"
    a: "In-memory sessions break with cluster—each worker has its own heap. Store sessions in Redis, Memcached, or a database. The same applies to in-memory caches and rate limit counters."
---
Your Node.js API saturates one CPU core at 100% while five others sit idle. The event loop handles thousands of concurrent I/O requests, but a single process cannot use more than one core. The `cluster` module forks worker processes that share the same server port, distributing connections across cores. It is built into Node.js—no dependencies—and remains relevant for bare-metal and VPS deployments even as containers dominate cloud architecture.

## How cluster works

```
                    ┌─ Worker 1 (PID 101)
Primary (PID 100) ──┼─ Worker 2 (PID 102)
                    ├─ Worker 3 (PID 103)
                    └─ Worker 4 (PID 104)
         ↑ all listen on port 3000
```

The primary process forks workers. The OS distributes incoming TCP connections. Default scheduling is round-robin (except on Windows).

## Basic implementation

```javascript
import cluster from "node:cluster";
import os from "node:os";
import process from "node:process";

if (cluster.isPrimary) {
  const numCPUs = os.cpus().length;
  console.log(`Primary ${process.pid} forking ${numCPUs} workers`);

  for (let i = 0; i < numCPUs; i++) {
    cluster.fork();
  }

  cluster.on("exit", (worker, code, signal) => {
    console.log(`Worker ${worker.process.pid} died (${signal || code})`);
    cluster.fork(); // replace dead worker
  });
} else {
  const { startServer } = await import("./server.js");
  startServer();
  console.log(`Worker ${process.pid} started`);
}
```

Each worker imports and starts the HTTP server independently.

## Zero-downtime restart

```javascript
if (cluster.isPrimary) {
  let nextWorkerId = 0;
  const workers = new Map();

  function forkWorker() {
    const worker = cluster.fork();
    workers.set(++nextWorkerId, worker);
    return worker;
  }

  for (let i = 0; i < os.cpus().length; i++) forkWorker();

  process.on("SIGUSR2", () => {
    console.log("Rolling restart initiated");
    const workerIds = [...workers.keys()];
    let i = 0;

    function restartNext() {
      if (i >= workerIds.length) return;
      const old = workers.get(workerIds[i]);
      const replacement = forkWorker();

      replacement.on("listening", () => {
        old.disconnect();
        old.on("exit", () => {
          workers.delete(workerIds[i]);
          i++;
          restartNext();
        });
      });
    }
    restartNext();
  });
}
```

Send `kill -SIGUSR2 <primary_pid>` to roll workers one at a time.

## Sharing state

Workers do not share memory. Patterns that break:

```javascript
// BROKEN with cluster — each worker has its own counter
let requestCount = 0;
app.use((req, res, next) => {
  requestCount++;
  next();
});
```

Fix with external state:

```javascript
import Redis from "ioredis";
const redis = new Redis(process.env.REDIS_URL);

app.use(async (req, res, next) => {
  await redis.incr("request_count");
  next();
});
```

## PM2 alternative

PM2 wraps cluster with process management, logging, and monitoring:

```bash
pm2 start server.js -i max    # fork workers = CPU count
pm2 reload server             # zero-downtime restart
pm2 monit                     # live dashboard
```

```javascript
// ecosystem.config.js
module.exports = {
  apps: [{
    name: "api",
    script: "./server.js",
    instances: "max",
    exec_mode: "cluster",
    env: { NODE_ENV: "production" },
  }],
};
```

PM2 adds 30 MB overhead per worker for its daemon. Worth it for the operational tooling on single-server deployments.

## When cluster is not enough

| Symptom | Cluster helps? | Better solution |
|---------|-------------|-----------------|
| One core at 100%, others idle | Yes | — |
| All cores at 100% on one machine | No | Horizontal scaling (more machines) |
| CPU-bound computation per request | Partially | Worker threads or job queue |
| Memory leak | No (restarts help temporarily) | Fix the leak |
| 10,000+ req/s | No | Load balancer + multiple instances |

## Container note

In Kubernetes, run one Node.js process per container and scale with pod replicas. Running cluster inside a container fights the orchestrator's scaling model—each pod already gets allocated CPU. Set `instances: 1` in PM2 or skip cluster entirely when deploying to K8s.

## Shared state problems in cluster mode

Cluster workers don't share memory — design accordingly:

```javascript
// ❌ In-memory cache breaks across workers
const cache = new Map();  // each worker has separate cache

// ✅ Use external store for shared state
const redis = new Redis(process.env.REDIS_URL);
async function getCached(key) {
  return redis.get(key);
}

// ❌ In-memory rate limiter — each worker counts separately
// ✅ Redis-backed rate limiter shared across workers
```

Session affinity (sticky sessions) is a workaround, not a solution — prefer external state store.

## Worker lifecycle and graceful shutdown

Handle SIGTERM for zero-downtime deploys:

```javascript
const cluster = require('cluster');
const http = require('http');

if (cluster.isPrimary) {
  for (let i = 0; i < os.cpus().length; i++) {
    cluster.fork();
  }
  cluster.on('exit', (worker) => {
    console.log(`Worker ${worker.process.pid} died, restarting`);
    cluster.fork();
  });
} else {
  const server = http.createServer(app);
  server.listen(PORT);

  process.on('SIGTERM', () => {
    server.close(() => process.exit(0));  // finish in-flight requests
    setTimeout(() => process.exit(1), 10000);  // force kill after 10s
  });
}
```

Primary respawns dead workers automatically. Workers drain connections on SIGTERM before exiting.

## When to use worker threads instead

CPU-bound work inside request handlers blocks the event loop for all cluster workers:

```javascript
const { Worker } = require('worker_threads');

app.post('/process-image', async (req, res) => {
  const result = await new Promise((resolve, reject) => {
    const worker = new Worker('./image-processor.js', {
      workerData: req.body.imageBuffer
    });
    worker.on('message', resolve);
    worker.on('error', reject);
  });
  res.json(result);
});
```

Cluster scales I/O-bound concurrency. Worker threads handle CPU-bound tasks within a process without blocking the event loop.

## Failure modes

- **In-memory state in cluster** — cache/rate limiter inconsistent across workers
- **No graceful shutdown** — in-flight requests killed on deploy
- **Cluster inside Kubernetes pod** — double scaling fights orchestrator
- **CPU-bound work on main thread** — blocks all requests in that worker
- **No worker restart on crash** — primary must respawn dead workers

## Production checklist

- Shared state in Redis/external store, not in-memory Map
- SIGTERM handler drains connections before exit (10s timeout)
- Primary process respawns dead workers automatically
- One Node.js process per K8s pod — scale with pod replicas
- CPU-bound tasks offloaded to worker threads
- PM2 or cluster primary monitors worker health

## Resources

- [Node.js cluster documentation](https://nodejs.org/api/cluster.html) — official API reference
- [PM2 cluster mode guide](https://pm2.keymetrics.io/docs/usage/cluster-mode/) — production process management
- [Node.js os.cpus()](https://nodejs.org/api/os.html#oscpus) — detecting available cores
- [Zero-downtime reload patterns](https://nodejs.org/api/cluster.html#clusterforkenv) — worker replacement
- [The Node.js Event Loop](https://nodejs.org/en/docs/guides/event-loop-timers-and-nexttick) — why one process uses one core


## Production validation (1)

Ship changes behind feature flags when behavior crosses route or service boundaries. Canary deploy with automatic rollback when error rate or p95 latency regresses beyond SLO budget. Document which metrics prove success—user-visible latency, error ratio, conversion—not only CPU graphs.

When operating **node cluster scaling** (`node-cluster-scaling`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.

## Failure modes (2)

Recurring incidents: missing idempotency on retried paths, connection pool exhaustion masquerading as slow queries, retry storms amplifying partial outages. Design explicit timeouts on every outbound call.

When operating **node cluster scaling** (`node-cluster-scaling`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.

## Observability (3)

Structured logs include trace_id and tenant_id on every error path. Metrics: request rate, error ratio, duration histogram, queue depth or pool wait. Traces: one span per dependency.

When operating **node cluster scaling** (`node-cluster-scaling`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.

## Security review (4)

Least-privilege credentials, no PII in logs, fail-closed auth defaults. Secrets rotate without redeploy where possible. Never log raw tokens or authorization headers.

When operating **node cluster scaling** (`node-cluster-scaling`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.

## Testing strategy (5)

Integration tests against real Postgres/Redis in CI with Testcontainers. Load test at 2× peak with production-like payloads. Chaos: inject dependency latency and verify degradation matches runbooks.

When operating **node cluster scaling** (`node-cluster-scaling`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.
