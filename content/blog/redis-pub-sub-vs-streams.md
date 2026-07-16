---
title: "Redis Pub/Sub vs Streams"
slug: "redis-pub-sub-vs-streams"
description: "Redis Pub/Sub and Streams compared: delivery guarantees, persistence, consumer groups, fan-out patterns, and choosing the right messaging primitive."
datePublished: "2026-01-18"
dateModified: "2026-01-18"
tags: ["Backend", "Redis", "Messaging", "Architecture"]
keywords: "Redis Pub/Sub vs Streams, Redis messaging, consumer groups, fire and forget, at-least-once delivery, XADD SUBSCRIBE"
faq:
  - q: "What is the main difference between Redis Pub/Sub and Streams?"
    a: "Pub/Sub delivers messages only to subscribers connected at publish time — no persistence, no replay, no acknowledgment. Streams append messages to a durable log with IDs, support consumer groups for load-balanced processing, and allow replay from any point. Pub/Sub is a broadcast channel; Streams are an event log."
  - q: "When should I use Redis Pub/Sub?"
    a: "Use Pub/Sub for ephemeral notifications where loss is acceptable: live UI updates, cache invalidation broadcasts, presence fan-out, or triggering WebSocket pushes. It is low-latency and simple. If a subscriber is offline, it misses the message — by design."
  - q: "Can Redis Streams replace Kafka?"
    a: "For moderate throughput (thousands to low tens of thousands of events per second), short-to-medium retention, and teams already running Redis, Streams can replace Kafka for many internal event pipelines. Kafka wins on very high throughput, long retention, partition ordering at scale, and ecosystem connectors."
---

Redis offers two messaging primitives that look interchangeable from a distance and behave nothing alike up close. Pub/Sub is a megaphone: shout and whoever is listening hears it; everyone else misses it forever. Streams are a ledger: every message gets a permanent slot until you trim it, and consumer groups coordinate who processed what.

I have debugged production incidents where a team used Pub/Sub for order fulfillment because the API felt familiar. Workers restarted, messages vanished, orders stuck. The fix was not "retry harder" — it was switching to Streams with consumer groups and explicit acknowledgment.

## Pub/Sub — fire-and-forget broadcast

```redis
# Subscriber (blocking connection)
SUBSCRIBE notifications:room-42

# Publisher
PUBLISH notifications:room-42 "{\"type\":\"message\",\"text\":\"hello\"}"
```

Characteristics:

- **At-most-once** — no connected subscriber = message gone
- **No history** — late joiners see nothing from before
- **Fan-out** — all subscribers on the channel receive every message
- **Pattern subscribe** — `PSUBSCRIBE notifications:*` for wildcard channels

Perfect for WebSocket relay: when a user sends a chat message, publish to the room channel; each WS server subscribed forwards to local connections. If a server was down for two seconds, it does not need the messages from that window — clients reconnect and fetch history from Postgres anyway.

## Streams — durable log with consumer groups

```redis
XADD orders * type "created" orderId "ord-991" amount "49.99"

XREADGROUP GROUP fulfillers consumer-1 COUNT 10 BLOCK 5000 STREAMS orders >

XACK orders fulfillers 1680000000000-0
```

Characteristics:

- **Persistent** — messages survive until trimmed
- **Consumer groups** — each message delivered to one consumer in group
- **Pending list** — track in-flight; reclaim on crash with XCLAIM
- **Replay** — read from any ID or time range

Perfect for order processing, audit trails, and any workflow where "message lost on restart" is unacceptable.

## Side-by-side comparison

| | Pub/Sub | Streams |
| --- | --- | --- |
| Persistence | None | Yes (until trimmed) |
| Delivery | All live subscribers | One per consumer group |
| Replay | No | Yes |
| Acknowledgment | No | XACK |
| Backpressure | Drop (slow client buffers) | Consumer pulls at own pace |
| Latency | Lower | Slightly higher |

## Hybrid architecture (common in practice)

Most apps I see use both:

```
Order created → XADD orders (durable processing)
             → PUBLISH dashboard:metrics (live counter tick)

Cache invalidation → PUBLISH cache:invalidate product:42
Presence update → PUBLISH presence:room-7
Background job → XADD jobs + consumer group
```

Pub/Sub for **signals**; Streams for **work**.

## Pub/Sub gotchas

**Subscriber connection is dedicated.** A connection in SUBSCRIBE mode cannot run other commands except unsubscribe variants. Use a separate connection pool for Pub/Sub listeners vs regular commands.

**No backpressure semantics.** Slow subscriber buffers grow until disconnect. Do not put heavy processing in the subscribe loop — enqueue locally and process async.

**Cluster caveat.** Pub/Sub in Redis Cluster only delivers to subscribers on the same node unless using sharded pub/sub (Redis 7+). Plan channel-to-slot mapping or use centralized relay.

## Streams gotchas

**Memory growth.** Unbounded XADD without `MAXLEN ~` trimming fills RAM. Set approximate max length or trim on schedule.

**Idempotent consumers.** XACK after process means redelivery on crash — handlers must tolerate duplicates.

**Not a full event bus.** No schema registry, no cross-datacenter replication story built in. Know your limits.

## Migration path: Pub/Sub to Streams

When you outgrow Pub/Sub:

1. Identify messages that must not be lost (jobs, payments, emails).
2. Replace `PUBLISH` with `XADD` on a stream per domain.
3. Add consumer group workers with XREADGROUP loop.
4. Keep Pub/Sub for UI fan-out if needed — dual-write during transition.
5. Monitor pending list length (XPENDING) for stuck consumers.

## Monitoring both primitives

For Pub/Sub, track subscriber count and message publish rate — sudden drops in subscribers may indicate connection leaks. For Streams, alert on stream length growth, consumer group lag (messages not yet delivered to any consumer), and pending entries list size (messages delivered but not acked). Grafana dashboards combining Redis INFO and XPENDING output catch stuck consumers before backlog spans hours.

## Choosing pub/sub vs streams

Use **Pub/Sub** when: fire-and-forget notifications, subscribers online, message loss OK.
Use **Streams** when: consumer groups, at-least-once, replay needed, audit trail.

Never use Pub/Sub for payment events — disconnected consumer loses messages permanently.

## Common production mistakes

Teams get pub sub vs streams wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Redis usage for pub sub vs streams loses data when persistence mode is misunderstood, hot keys saturate single shards, and TTL strategy is applied after memory pressure already triggered evictions.

## Debugging and triage workflow

When pub sub vs streams misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Redis Pub/Sub documentation](https://redis.io/docs/latest/develop/interact/pubsub/)
- [Redis Streams introduction](https://redis.io/docs/latest/develop/data-types/streams/)
- [XREADGROUP command](https://redis.io/docs/latest/commands/xreadgroup/)
- [Sharded Pub/Sub (Redis 7)](https://redis.io/docs/latest/develop/interact/pubsub/#sharded-pubsub)
- [Event Processing with Redis Streams](https://redis.io/docs/latest/develop/data-types/streams-tutorial/)
