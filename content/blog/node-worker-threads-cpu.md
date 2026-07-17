---
title: "Worker Threads for CPU Work"
slug: "node-worker-threads-cpu"
description: "Offload CPU-intensive work from the Node.js event loop with worker threads: image processing, parsing, cryptography, and pool patterns."
datePublished: "2025-09-12"
dateModified: "2026-07-17"
tags:
keywords: "Node.js worker threads, worker_threads module, CPU intensive Node.js, event loop blocking, Piscina worker pool, offloading computation Node.js"
faq:
  - q: "When should I use worker threads vs child processes?"
    a: "Use worker threads for CPU-bound tasks that need shared memory or frequent communication—image resizing, JSON parsing of large payloads, bcrypt hashing. Use child processes for isolation (crash one without killing the server), running non-Node code, or when memory leaks in untrusted code are a concern."
  - q: "How many worker threads should I create?"
    a: "Match CPU core count for CPU-bound work—creating more threads than cores adds context-switching overhead without throughput gain. For mixed I/O and CPU workloads, cores minus one (leaving one for the main event loop) is a reasonable starting point."
  - q: "Can worker threads access the same variables as the main thread?"
    a: "Not directly—they have separate V8 isolates. Share data via message passing (postMessage), SharedArrayBuffer for typed arrays, or transfer ArrayBuffers with zero-copy. Treat workers like separate programs that exchange messages."
---
A password hashing endpoint uses bcrypt with cost factor 12. Under load, response times spike from 50 ms to 8 seconds—not because bcrypt got slower, but because each hash blocks the event loop for 200 ms and queues pile up. Worker threads run JavaScript on separate V8 isolates with their own event loops, keeping the main thread free for incoming HTTP connections. They are not parallel threads in the C++ sense, but they achieve real parallelism for CPU-bound JavaScript.

## Identifying event loop blocking

```javascript
import { monitorEventLoopDelay } from "node:perf_hooks";

const h = monitorEventLoopDelay({ resolution: 10 });
h.enable();

setInterval(() => {
  const p99 = h.percentile(99) / 1e6;
  if (p99 > 50) console.warn(`Event loop p99: ${p99.toFixed(1)}ms`);
}, 5000);
```

If p99 exceeds 50 ms during CPU work, offload it.

## Basic worker thread

**worker.js:**

```javascript
import { parentPort, workerData } from "node:worker_threads";
import bcrypt from "bcrypt";

const { password, saltRounds } = workerData;
const hash = bcrypt.hashSync(password, saltRounds);
parentPort.postMessage({ hash });
```

**main.js:**

```javascript
import { Worker } from "node:worker_threads";

function hashPassword(password) {
  return new Promise((resolve, reject) => {
    const worker = new Worker("./worker.js", {
      workerData: { password, saltRounds: 12 },
    });
    worker.on("message", resolve);
    worker.on("error", reject);
    worker.on("exit", (code) => {
      if (code !== 0) reject(new Error(`Worker exited with ${code}`));
    });
  });
}
```

## Worker pool with Piscina

Spawning a new Worker per request adds 30–50 ms startup overhead. Pools reuse workers:

```javascript
import Piscina from "piscina";
import { fileURLToPath } from "node:url";

const pool = new Piscina({
  filename: fileURLToPath(new URL("./hash-worker.js", import.meta.url)),
  minThreads: 2,
  maxThreads: require("node:os").cpus().length,
});

app.post("/register", async (req, res) => {
  const hash = await pool.run({
    password: req.body.password,
    saltRounds: 12,
  });
  await db.createUser({ email: req.body.email, hash });
  res.status(201).json({ ok: true });
});
```

## Transferring large buffers

Pass ArrayBuffers without copying:

```javascript
// main thread
const imageBuffer = fs.readFileSync("photo.jpg");
const result = await pool.run(imageBuffer, { transferList: [imageBuffer.buffer] });

// worker
export default function processImage(buffer) {
  // buffer is now owned by this worker — main thread cannot use it
  return resize(buffer, 800, 600);
}
```

`transferList` moves ownership. The main thread's buffer becomes detached.

## SharedArrayBuffer for counters

```javascript
import { Worker } from "node:worker_threads";

const sharedBuffer = new SharedArrayBuffer(4);
const counter = new Int32Array(sharedBuffer);

const workers = Array.from({ length: 4 }, () =>
  new Worker("./counter-worker.js", { workerData: { sharedBuffer } })
);

// counter-worker.js
const counter = new Int32Array(workerData.sharedBuffer);
for (let i = 0; i < 1_000_000; i++) {
  Atomics.add(counter, 0, 1);
}
```

Use `Atomics` for thread-safe operations on shared memory.

## Image processing example

```javascript
// resize-worker.js
import { parentPort } from "node:worker_threads";
import sharp from "sharp";

parentPort.on("message", async ({ buffer, width, height }) => {
  try {
    const resized = await sharp(buffer)
      .resize(width, height)
      .jpeg({ quality: 80 })
      .toBuffer();
    parentPort.postMessage({ ok: true, buffer: resized });
  } catch (err) {
    parentPort.postMessage({ ok: false, error: err.message });
  }
});
```

Sharp in a worker thread processes images without blocking HTTP handlers.

## What not to offload

- **Database queries** — already async I/O, workers add overhead.
- **HTTP fetch calls** — same reason.
- **Small computations** (<5 ms) — worker startup costs more than inline execution.
- **Frequent tiny tasks** — message passing overhead dominates.

## Error handling and timeouts

```javascript
function runWithTimeout(pool, data, ms = 5000) {
  return Promise.race([
    pool.run(data),
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error("Worker timeout")), ms)
    ),
  ]);
}
```

Workers that hang (infinite loop) do not crash the main process. Set timeouts and kill stuck workers:

```javascript
const worker = new Worker("./task.js");
const timer = setTimeout(() => worker.terminate(), 10_000);
worker.on("exit", () => clearTimeout(timer));
```

## Worker pool sizing

Size pools against CPU cores and workload type:

```javascript
import os from "node:os";
import Piscina from "piscina";

const pool = new Piscina({
  filename: "./worker.js",
  maxThreads: os.availableParallelism(),  // not cpus().length on containers
  minThreads: 2,
  idleTimeout: 30_000,
});
```

CPU-bound tasks: `maxThreads = cores`. Mixed I/O + CPU: `maxThreads = cores * 1.5`. More threads than cores on CPU-bound work increases context switching without throughput gain.

Monitor queue depth — sustained backlog means scale workers or optimize task size.

## Structured cloning costs

`worker.postMessage()` uses structured clone — large objects copy memory:

```javascript
// BAD: sends 50 MB buffer every task
pool.run({ buffer: hugeArrayBuffer });

// GOOD: transfer ownership (zero-copy)
pool.run({ buffer: hugeArrayBuffer }, { transferList: [hugeArrayBuffer] });
```

SharedArrayBuffer enables true sharing but requires cross-origin isolation headers in browsers — fine in Node, rare in web workers.

## When to use child processes instead

| Need | worker_threads | child_process |
|------|----------------|---------------|
| Shared memory | Yes (limited) | No |
| Crash isolation | Whole process affected | Child crash isolated |
| Different V8 isolate | Yes | Yes |
| Run non-Node code | No | Yes (Python, etc.) |

Use `child_process.fork` for untrusted user code — a segfault in native addon shouldn't kill the HTTP server.

Pair with [Node streams backpressure](https://blog.michaelsam94.com/node-streams-backpressure/) when piping large data through worker pipelines.

## Production validation (1)

Ship changes behind feature flags when behavior crosses route or service boundaries. Canary deploy with automatic rollback when error rate or p95 latency regresses beyond SLO budget. Document which metrics prove success—user-visible latency, error ratio, conversion—not only CPU graphs.

When operating **node worker threads cpu** (`node-worker-threads-cpu`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.

## Failure modes (2)

Recurring incidents: missing idempotency on retried paths, connection pool exhaustion masquerading as slow queries, retry storms amplifying partial outages. Design explicit timeouts on every outbound call.

When operating **node worker threads cpu** (`node-worker-threads-cpu`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.

## Observability (3)

Structured logs include trace_id and tenant_id on every error path. Metrics: request rate, error ratio, duration histogram, queue depth or pool wait. Traces: one span per dependency.

When operating **node worker threads cpu** (`node-worker-threads-cpu`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.

## Security review (4)

Least-privilege credentials, no PII in logs, fail-closed auth defaults. Secrets rotate without redeploy where possible. Never log raw tokens or authorization headers.

When operating **node worker threads cpu** (`node-worker-threads-cpu`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.

## Testing strategy (5)

Integration tests against real Postgres/Redis in CI with Testcontainers. Load test at 2× peak with production-like payloads. Chaos: inject dependency latency and verify degradation matches runbooks.

When operating **node worker threads cpu** (`node-worker-threads-cpu`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.

## Rollout checklist (6)

Staging mirrors production topology for cache, pools, and timeouts. Rollback path tested quarterly. On-call runbook fits one page: symptom, dashboard, mitigation, rollback.

When operating **node worker threads cpu** (`node-worker-threads-cpu`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.

## Performance tuning (7)

Measure p50/p95 before optimizing. Change one variable at a time—pool size, batch size, TTL, timeout. Profile CPU for JSON serialization and regex; profile IO for N+1 and pool wait.

When operating **node worker threads cpu** (`node-worker-threads-cpu`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.

## On-call triage (8)

Confirm scope: one tenant, region, or deploy stage? Check deploys and migrations in last 24h. Compare golden signals to baseline. Rollback first during incident if faster than root cause.

When operating **node worker threads cpu** (`node-worker-threads-cpu`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.
