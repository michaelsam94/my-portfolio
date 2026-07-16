---
title: "Node.js Streams and Backpressure"
slug: "node-streams-backpressure"
description: "Handle large data flows in Node.js with streams: readable, writable, transform pipes, backpressure signals, and memory-safe file processing."
datePublished: "2025-09-09"
dateModified: "2025-09-09"
tags: ["Backend", "Node.js", "Performance", "Architecture"]
keywords: "Node.js streams, backpressure Node.js, stream pipe, transform stream, readable writable stream, large file processing Node.js"
faq:
  - q: "When should I use streams instead of reading a file into a buffer?"
    a: "Use streams when data size is unknown or exceeds available memory—a 2 GB log file, HTTP response body, or database cursor. Buffering loads everything into RAM. Streams process chunks incrementally, keeping memory usage flat regardless of file size."
  - q: "What happens if I ignore backpressure?"
    a: "The producer outruns the consumer. Chunks accumulate in internal buffers, memory grows until the process crashes with OOM. Symptoms include rising heap usage during file uploads and event loop lag. Always pipe streams or handle drain events."
  - q: "Are Node.js streams still relevant with async/await?"
    a: "Yes. Async/await simplifies control flow but does not replace streaming I/O. Use stream/promises helpers (pipeline, finished) to combine streams with async error handling. For HTTP proxying and ETL, streams remain the correct abstraction."
---

A CSV import endpoint reads the entire 800 MB upload into a Buffer, parses it, and inserts rows. It works in staging with test files. In production, three concurrent uploads exhaust server memory and the process restarts. Node.js streams process data chunk by chunk—typically 64 KB at a time—keeping memory flat whether the file is 1 MB or 10 GB. Backpressure is the mechanism that prevents the fast producer from overwhelming the slow consumer.

## Stream types

| Type | Direction | Example |
|------|-----------|---------|
| Readable | Source → app | `fs.createReadStream`, HTTP response body |
| Writable | App → destination | `fs.createWriteStream`, HTTP response |
| Transform | Modify in transit | `zlib.createGzip`, CSV parser |
| Duplex | Both directions | TCP socket, WebSocket |

## Basic pipe

```javascript
import { createReadStream, createWriteStream } from "node:fs";
import { pipeline } from "node:stream/promises";
import { createGzip } from "node:zlib";

await pipeline(
  createReadStream("access.log"),
  createGzip(),
  createWriteStream("access.log.gz"),
);
console.log("Compression complete");
```

`pipeline` (not `pipe`) forwards errors and destroys all streams on failure.

## Backpressure explained

When a writable stream's internal buffer fills, `write()` returns `false`:

```javascript
const readable = getDataSource();
const writable = getSlowDestination();

readable.on("data", (chunk) => {
  const ok = writable.write(chunk);
  if (!ok) {
    readable.pause();                    // stop producing
    writable.once("drain", () => {
      readable.resume();                 // resume when buffer empties
    });
  }
});
```

`pipe()` and `pipeline()` handle this automatically. Manual `data` event handlers do not—this is the most common streams bug.

## Transform stream for CSV parsing

```javascript
import { Transform } from "node:stream";
import { pipeline } from "node:stream/promises";
import { createReadStream } from "node:fs";

let leftover = "";

const csvParser = new Transform({
  objectMode: true,
  transform(chunk, encoding, callback) {
    const lines = (leftover + chunk.toString()).split("\n");
    leftover = lines.pop() ?? "";
    for (const line of lines) {
      if (line.trim()) {
        const [id, name, email] = line.split(",");
        this.push({ id, name, email });
      }
    }
    callback();
  },
  flush(callback) {
    if (leftover.trim()) {
      const [id, name, email] = leftover.split(",");
      this.push({ id, name, email });
    }
    callback();
  },
});

for await (const row of createReadStream("users.csv").pipe(csvParser)) {
  await db.insert(row);
}
```

`objectMode: true` passes JavaScript objects instead of Buffers between chunks.

## HTTP streaming response

```javascript
import { Readable } from "node:stream";

app.get("/export", async (req, res) => {
  res.setHeader("Content-Type", "application/json");
  res.write("[\n");

  const cursor = db.query("SELECT * FROM orders").stream();
  let first = true;

  for await (const row of cursor) {
    if (!first) res.write(",\n");
    res.write(JSON.stringify(row));
    first = false;
  }

  res.end("\n]");
});
```

The client starts receiving data immediately instead of waiting for the full result set.

## Monitoring backpressure

```javascript
const { monitorEventLoopDelay } = require("node:perf_hooks");
const h = monitorEventLoopDelay({ resolution: 20 });
h.enable();

const writable = fs.createWriteStream("output.dat");
console.log("Buffer level:", writable.writableLength);
console.log("High water mark:", writable.writableHighWaterMark);

setInterval(() => {
  console.log(`Event loop p99 delay: ${h.percentile(99) / 1e6}ms`);
}, 5000);
```

Rising `writableLength` and event loop delay together indicate backpressure not being respected.

## Async generators as readable streams

```javascript
import { Readable } from "node:stream";

async function* generateRows() {
  const cursor = db.query("SELECT * FROM events").stream();
  for await (const row of cursor) {
    yield JSON.stringify(row) + "\n";
  }
}

const readable = Readable.from(generateRows());
await pipeline(readable, createWriteStream("events.ndjson"));
```

`Readable.from` bridges async iterables into the streams API.

## Common mistakes

1. **Using `data` events without pause/resume** — memory leak under load.
2. **Not destroying streams on error** — file descriptors leak.
3. **Mixing pipe() without error handlers** — silent failures.
4. **Buffering stream output** — `const buf = await streamToBuffer(s)` defeats the purpose.

Always prefer `pipeline` from `node:stream/promises`.

## Transform streams in production

`Transform` streams are where business logic lives — parsing, filtering, batching:

```javascript
import { Transform } from "node:stream";
import { pipeline } from "node:stream/promises";

const batchJson = new Transform({
  objectMode: true,
  transform(row, enc, cb) {
    batch.push(row);
    if (batch.length >= 100) {
      this.push(JSON.stringify(batch) + "\n");
      batch.length = 0;
    }
    cb();
  },
  flush(cb) {
    if (batch.length) this.push(JSON.stringify(batch) + "\n");
    cb();
  },
});
let batch = [];

await pipeline(dbCursor, batchJson, createWriteStream("out.ndjson"));
```

Batching reduces write syscalls but increases latency — tune batch size against memory (1000-row batches at 2 KB each = 2 MB in flight).

## HTTP response streaming

Express/Fastify handlers can stream responses without buffering entire payloads:

```javascript
app.get("/export", async (req, res) => {
  res.setHeader("Content-Type", "application/x-ndjson");
  res.setHeader("Transfer-Encoding", "chunked");
  await pipeline(generateRows(req.query), res);
});
```

If the client disconnects mid-stream, `pipeline` destroys upstream sources — handle `ECONNRESET` gracefully and abort expensive DB cursors.

## Worker threads vs streams

CPU-heavy transforms (compression, encryption) block the event loop if done synchronously in a Transform. Offload to `worker_threads` or use `@napi-rs/canvas`-style native addons. Rule of thumb: if transform takes > 5ms per chunk, move off main thread.

Monitor with `monitorEventLoopDelay` — p99 above 50ms under load means streams aren't enough; you need worker pools.

Pair with [concurrency backpressure strategies](https://blog.michaelsam94.com/concurrency-backpressure-strategies/) for cross-service flow control beyond Node internals.

## Production checklist

- [ ] `pipeline()` used instead of raw `pipe()` everywhere
- [ ] Transform streams batch to reduce write syscalls
- [ ] Client disconnect aborts upstream DB cursors
- [ ] CPU-heavy transforms offloaded to worker threads
- [ ] Event loop delay monitored under stream load

## Common production mistakes

Teams get node streams backpressure wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of node streams backpressure fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [Node.js Stream API](https://nodejs.org/api/stream.html) — official documentation
- [stream/promises pipeline](https://nodejs.org/api/stream.html#streampipelinesource-transforms-destination-options) — error-safe piping
- [Backpressure explanation (Node.js docs)](https://nodejs.org/en/docs/guides/backpressuring-in-streams) — official guide
- [Node.js fs.createReadStream](https://nodejs.org/api/fs.html#fscreatereadstreampath-options) — file streaming
- [Web Streams API (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/Streams_API) — browser equivalent
