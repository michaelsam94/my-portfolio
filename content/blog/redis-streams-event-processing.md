---
title: "Event Processing with Redis Streams"
slug: "redis-streams-event-processing"
description: "Redis Streams for event processing: consumer groups, at-least-once delivery, the pending list, and when it beats Kafka — and when it doesn't."
datePublished: "2026-03-10"
dateModified: "2026-03-10"
tags: ["Backend", "Databases", "Messaging", "Architecture"]
keywords: "Redis Streams, consumer groups, event processing, stream processing, XADD XREADGROUP, at-least-once"
faq:
  - q: "What are Redis Streams?"
    a: "Redis Streams are an append-only log data structure built into Redis, where each entry has an auto-generated, time-ordered ID and a set of field-value pairs. Producers append events with XADD and consumers read them with XREAD or, for coordinated processing, XREADGROUP. Unlike Redis Pub/Sub, streams persist entries and support consumer groups, acknowledgments, and replay, which makes them suitable for durable event processing rather than fire-and-forget messaging."
  - q: "How do consumer groups provide at-least-once delivery?"
    a: "A consumer group tracks a last-delivered ID and maintains a pending entries list (PEL) of messages delivered but not yet acknowledged. When a consumer reads with XREADGROUP, entries move into the PEL; the consumer must call XACK after successfully processing. If a consumer crashes before acking, the entry stays pending and can be reclaimed by another consumer with XCLAIM, so no message is silently lost — at the cost of possible redelivery."
  - q: "When should I use Redis Streams instead of Kafka?"
    a: "Reach for Redis Streams when you already run Redis, throughput is moderate (thousands to low tens of thousands of events per second), and you want durable consumer-group semantics without operating a separate Kafka cluster. Choose Kafka when you need very high throughput, long-term retention measured in weeks, strong partition-level ordering guarantees at scale, or a broad connector ecosystem. Streams trade some of Kafka's scale and tooling for radical operational simplicity."
---

Redis Streams give you a durable, ordered event log with consumer groups — Kafka-style semantics — without running Kafka. If you already have Redis in your stack, you can build a genuinely reliable event-processing pipeline with a handful of commands: `XADD` to append, `XREADGROUP` to consume as a coordinated group, and `XACK` to confirm work is done. That combination buys you at-least-once delivery, horizontal consumer scaling, and crash recovery, all from a data structure most teams already have deployed.

I've used Redis Streams as the backbone for background job processing and internal event fan-out on systems doing a few thousand events a second, and the appeal is honest: it's *boring* in the best way. No new cluster, no ZooKeeper-era ceremony, one dependency you already operate. Let me show what it actually looks like and where the sharp edges are.

## Streams vs the alternatives inside Redis

Redis has offered messaging primitives for years, and it's worth being precise about why Streams are different from what came before:

- **Pub/Sub** is fire-and-forget. If no subscriber is listening when a message is published, it's gone. No persistence, no replay, no delivery guarantee.
- **Lists** (`LPUSH`/`BRPOP`) give you a simple durable queue, but no consumer groups, no acknowledgment, and once an element is popped it's off the list — a crash mid-processing loses the work.
- **Streams** persist entries in an append-only log with time-ordered IDs, and consumer groups add the last-delivered cursor, a pending list, and acknowledgment. This is the first Redis primitive designed for reliable event *processing* rather than transport.

That progression is the whole reason Streams exist: they close the durability and delivery-guarantee gap that made people bolt Kafka onto Redis-based stacks.

## The core commands, end to end

The producer side is trivial. Each `XADD` appends an entry and returns its ID (a millisecond timestamp plus a sequence number):

```bash
# Append an event; * means "assign an ID automatically"
XADD orders '*' type created order_id 4821 total 2999

# Create a consumer group starting from new messages
XGROUP CREATE orders fulfillment '$' MKSTREAM
```

The consumer side is where the reliability lives. A worker reads as a named consumer within a group, processes, then acknowledges:

```bash
# Read up to 10 new entries as consumer "worker-1" in group "fulfillment"
XREADGROUP GROUP fulfillment worker-1 COUNT 10 BLOCK 5000 STREAMS orders '>'

# After successfully processing an entry, acknowledge it
XACK orders fulfillment 1710000000000-0
```

The `>` symbol means "give me messages never delivered to this group." When you pass an explicit ID instead, you read from this consumer's **pending entries list** — messages it was handed but hasn't acked. That's the recovery mechanism: on restart, a worker first drains its own pending list before asking for new work, so nothing in flight is dropped.

## Consumer groups and the pending entries list

The pending entries list (PEL) is the concept that makes or breaks a correct implementation. When a consumer reads with `>`, each entry moves into the PEL, tagged with which consumer holds it and when. It stays there until `XACK`. If the consumer crashes between read and ack, the entry doesn't vanish and it doesn't get auto-redelivered to someone else — it just sits pending, owned by a dead consumer.

Recovering it is deliberate, using `XAUTOCLAIM` (or the older `XCLAIM`):

```bash
# Reassign entries idle for >30s from any consumer to worker-2
XAUTOCLAIM orders fulfillment worker-2 30000 0
```

This is the machinery behind at-least-once delivery, and the design tradeoff is explicit: you get "no message lost," and in exchange you must handle "some messages processed twice." A reclaimed entry may have actually been processed before the original consumer died mid-ack. Every consumer therefore needs to be **idempotent** — key your side effects on the event ID or a business key so a duplicate is a no-op. This is the same discipline that makes the [event-driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/) safe, and it's non-negotiable in any at-least-once system.

## Keeping the stream from growing forever

An append-only log grows without bound unless you trim it. Redis gives you capped streams:

```bash
# Keep roughly the most recent 1,000,000 entries (approximate is cheaper)
XADD orders MAXLEN '~' 1000000 '*' type created order_id 4821
```

The `~` makes trimming approximate, which lets Redis remove whole macro-nodes efficiently instead of trimming to an exact count on every write. For most workloads that's the right call. But watch a subtle failure: trimming by length can **delete entries that some slow consumer group hasn't read yet**. Redis will happily trim past an unacked entry. If you can't tolerate that, size `MAXLEN` generously relative to your slowest consumer's lag, or trim by time/ID only after confirming all groups have advanced. Monitoring per-group lag is essential — an unbounded PEL or a group that's fallen far behind is your early warning.

## Backpressure and throughput realities

Streams naturally support backpressure because consumers pull at their own pace, and `BLOCK` lets idle workers wait cheaply instead of hot-looping. But Redis is single-threaded for command execution, so a firehose producer can outrun consumers and the stream (and memory) balloons. The correct response is to shape the flow rather than let it collapse — the strategies I lay out in [rate limiting and backpressure](https://blog.michaelsam94.com/rate-limiting-backpressure/) apply directly: bound producer rate, scale consumers horizontally within the group, and shed or queue-to-disk when you're structurally behind.

On scale: I'd comfortably run Redis Streams into the low tens of thousands of events per second on a decent instance. Past that, or when you need retention measured in weeks and partition-level ordering across many machines, the honest answer is Kafka. Here's the decision I actually make:

| Factor | Redis Streams | Kafka |
| --- | --- | --- |
| Ops burden | You already run Redis | Separate cluster |
| Throughput ceiling | Low tens of thousands/s | Millions/s |
| Retention | Hours to days (memory-bound) | Weeks+ (disk) |
| Ordering | Per-stream | Per-partition |
| Ecosystem | Minimal | Connectors, tooling |

## The verdict from production

Redis Streams hit a sweet spot that a lot of teams overshoot with Kafka. If your event volume is moderate, you value operational simplicity, and you already run Redis, you can have durable, replayable, group-consumed events today with commands you can memorize. The two things you must get right are **idempotent consumers** and **stream trimming with lag awareness** — get those wrong and at-least-once becomes at-least-once-and-sometimes-lost. Get them right and it's one of the most cost-effective pieces of event infrastructure available.

I don't reach for it when I need Kafka's scale or its connector ecosystem. But for the large middle of real-world systems, Redis Streams is the pragmatic default I keep coming back to.

## Resources

- [Redis Streams introduction](https://redis.io/docs/latest/develop/data-types/streams/)
- [XREADGROUP command reference](https://redis.io/docs/latest/commands/xreadgroup/)
- [XAUTOCLAIM command reference](https://redis.io/docs/latest/commands/xautoclaim/)
- [XADD command reference](https://redis.io/docs/latest/commands/xadd/)
- [Redis Streams tutorial (redis.io)](https://redis.io/docs/latest/develop/data-types/streams-tutorial/)
- [Apache Kafka documentation](https://kafka.apache.org/documentation/)
