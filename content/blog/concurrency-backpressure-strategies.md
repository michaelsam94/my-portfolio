---
title: "Backpressure Strategies"
slug: "concurrency-backpressure-strategies"
description: "Handle producer-consumer speed mismatches with bounded buffers, drop policies, reactive streams backpressure, and flow control in async systems."
datePublished: "2025-04-24"
dateModified: "2025-04-24"
tags: ["Career", "Engineering"]
keywords: "backpressure, flow control, bounded buffer, reactive streams, producer consumer, overload handling"
faq:
  - q: "What is backpressure in software systems?"
    a: "Backpressure is a mechanism where a slow consumer signals a fast producer to slow down or stop sending data temporarily. Without backpressure, unbounded queues grow until memory exhaustion or latency becomes unusable. It converts uncontrolled overload into explicit flow control between pipeline stages."
  - q: "What are common backpressure strategies?"
    a: "Block the producer until buffer space opens, drop newest or oldest items, sample or batch events, spill to disk, or return errors to clients (HTTP 429). Choice depends on data criticality—financial events block or persist; metrics can drop; user-facing APIs should reject with retry-after."
  - q: "Does Kotlin Flow support backpressure?"
    a: "Cold Flow suspends emit when collectors are slow—natural backpressure via coroutine suspension. Shared hot flows using SharedFlow or Channel need explicit buffer capacity and BufferOverflow strategy (SUSPEND, DROP_OLDEST, DROP_LATEST) because multiple collectors or unbounded emitters bypass automatic pacing."
---

Every queue in your system is a lie you tell yourself about capacity. Producer posts events at 50k/sec; consumer handles 5k/sec; the broker buffer grows; GC pauses spike; someone pages at 3 AM. Backpressure is the honest conversation between stages: "I cannot keep up—stop or slow down." Systems that implement it explicitly survive load spikes; systems that buffer infinitely fail catastrophically.

## The problem without flow control

```
Producer ──► [ unbounded queue ] ──► Consumer
   50k/s              RAM ↑↑↑           5k/s
```

Latency = queue_depth / processing_rate. Users see stale data long before the process crashes.

## Strategy 1: Block (pressure upstream)

Producer waits when buffer is full—natural in synchronous call chains and coroutine channels with rendezvous:

```kotlin
val channel = Channel<Event>(capacity = 64)  // suspends send when full

suspend fun produce(event: Event) {
    channel.send(event)  // suspends until space
}
```

Pros: no data loss. Cons: blocked producers tie up threads or coroutines—cascading stalls if upstream holds locks.

## Strategy 2: Drop

When buffer full, discard items:

```kotlin
val flow = MutableSharedFlow<Event>(
    extraBufferCapacity = 100,
    onBufferOverflow = BufferOverflow.DROP_OLDEST,
)
```

| Policy | Behavior | Use case |
|--------|----------|----------|
| DROP_OLDEST | Remove oldest, accept new | Live metrics, sensor readings |
| DROP_LATEST | Reject incoming | Keep stable snapshot |
| SUSPEND | Block emitter | Must-not-lose events |

Document drop behavior in SLAs—"metrics may lose up to 1% under peak."

## Strategy 3: Sample and debounce

Reduce volume instead of dropping arbitrarily:

```kotlin
sensorReadings
    .sample(100.milliseconds)
    .collect { display(it) }
```

Or debounce user keystrokes. Acceptable when consumers need approximate recent state, not every event.

## Strategy 4: Spill to disk

Message brokers (Kafka with retention, persistent queues) absorb bursts by writing to disk. Consumer lag becomes operational metric—scale consumers until lag stabilizes.

Not infinite—disk fills. Monitor consumer lag alerts:

```
kafka.consumer.lag > threshold → scale consumers or throttle producers
```

## Strategy 5: Reject at the edge

HTTP APIs return `429 Too Many Requests` with `Retry-After`. gRPC returns `RESOURCE_EXHAUSTED`. Clients implement exponential backoff with jitter.

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 2
Content-Type: application/json

{"error": "rate_limit_exceeded", "limit": 1000}
```

Edge rejection protects internal queues from untrusted traffic.

## Reactive Streams contract

Java `Flow.Publisher` / Project Reactor / RxJava use explicit request:

```java
subscriber.onSubscribe(subscription);
subscription.request(16);  // pull next 16 items
```

Downstream `request(n)` is backpressure signal upstream. Kotlin Flow's suspension model achieves similar for cold streams without the ceremony.

## Actor mailbox bounds

Erlang and Akka mailboxes can grow unbounded by default—configure bounded mailboxes or monitor queue depth:

```scala
// Akka: stash or drop with custom mailbox
```

Supervision restarts actors with mailbox backlog cleared—data loss by design on crash.

## Choosing a strategy

Ask three questions:

1. **Can we lose this data?** No → block, persist, or scale consumers
2. **Is stale data harmful?** Yes → drop oldest, not newest
3. **Who controls the producer?** External → reject at edge; internal → channel bounds

Mix strategies per pipeline stage—edge 429, internal bounded channel, metrics drop.

## Observability

Instrument:

- Queue depth / channel size
- Drop counters by policy
- Block time histogram for producers
- Consumer lag

Alert on trend, not just absolute—gradual lag increase predicts incident hours before OOM.

## Backpressure in HTTP APIs

Return 429 Too Many Requests when overloaded — don't accept work you can't process:

```python
from fastapi import FastAPI, HTTPException
import asyncio

app = FastAPI()
semaphore = asyncio.Semaphore(100)  # max 100 concurrent requests

@app.middleware("http")
async def backpressure_middleware(request, call_next):
    if semaphore.locked() and semaphore._value == 0:
        raise HTTPException(429, "Server overloaded", headers={"Retry-After": "5"})
    async with semaphore:
        return await call_next(request)
```

Include `Retry-After` header so clients back off predictably. Pair with queue depth metric — if depth trending up for 5 minutes, scale consumers or alert.

## Kafka consumer backpressure

Kafka consumers control ingestion rate via poll frequency and processing parallelism:

```python
consumer = KafkaConsumer(
    'events',
    max_poll_records=50,           # limit batch size
    max_poll_interval_ms=300000,   # rebalance if processing too slow
)

for message in consumer:
    if processing_queue.qsize() > 1000:
        time.sleep(0.1)  # back off polling when downstream saturated
    processing_queue.put(message)
```

If `max_poll_interval_ms` exceeded, consumer is kicked from group — tune batch size and processing speed together. Prefer smaller batches with faster processing over large batches that risk rebalance.

## Reactive Streams (Project Reactor / RxJava)

Standardized backpressure protocol for async streams:

```java
Flux.range(1, 1_000_000)
    .onBackpressureBuffer(1000, BufferOverflowStrategy.DROP_OLDEST)
    .publishOn(Schedulers.boundedElastic(), 100)  // prefetch = 100
    .subscribe(item -> process(item));
```

`onBackpressureBuffer` with overflow strategy, `publishOn` with prefetch limit, and `limitRate(n)` for explicit demand signaling. Producers never outpace consumer capacity.

## Failure modes

- **Unbounded queue** — memory grows until OOM; always set max capacity
- **Drop newest instead of oldest** — loses fresh data; usually wrong policy
- **No 429 at API edge** — requests accepted but never processed; client timeout
- **Kafka max_poll_interval exceeded** — consumer rebalanced; duplicate processing
- **Backpressure not propagated upstream** — downstream saturated but producers unaware

## Production checklist

- Bounded queues/channels with explicit overflow policy
- 429 with Retry-After at API edge when saturated
- Queue depth and consumer lag monitored with trend alerts
- Kafka max_poll_records tuned to processing speed
- Drop policy documented per pipeline (oldest vs newest)
- Backpressure propagated end-to-end, not just at one layer

## Common production mistakes

Teams get backpressure strategies wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of backpressure strategies fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [Reactive Streams specification](https://www.reactive-streams.org/)
- [Kotlin Flow buffer operator](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines.flow/buffer.html)
- [Akka mailboxes and backpressure](https://doc.akka.io/docs/akka/current/mailboxes.html)
- [gRPC flow control](https://grpc.io/docs/guides/performance/)
