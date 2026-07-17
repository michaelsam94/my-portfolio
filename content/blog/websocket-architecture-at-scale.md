---
title: "WebSocket Architecture at Scale"
slug: "websocket-architecture-at-scale"
description: "How to design WebSocket architecture that survives real traffic: connection management, horizontal scaling with pub/sub, backpressure, and the failure modes that bite."
datePublished: "2026-06-14"
dateModified: "2026-07-17"
tags: ["WebSockets", "Real-Time", "Backend", "Scalability"]
keywords: "WebSocket, real-time architecture, WebSocket scaling, pub sub, connection management, horizontal scaling, backpressure"
faq:
  - q: "How many WebSocket connections can one server handle?"
    a: "A single well-tuned Linux box can hold hundreds of thousands of idle WebSocket connections — the limit is memory per connection and file descriptors, not CPU. The real ceiling is message throughput and fan-out, not raw connection count, so benchmark with your actual message rate rather than trusting a headline number."
  - q: "How do you scale WebSockets across multiple servers?"
    a: "Put a pub/sub layer (Redis, NATS, or Kafka) between your WebSocket nodes so a message published on one node reaches clients connected to any other node. Each node subscribes to the channels its connected clients care about, and connections are sticky to a node for their lifetime."
  - q: "What breaks first when WebSocket traffic grows?"
    a: "Fan-out and backpressure. A slow or dead client that never drains its socket causes memory to balloon on the server; a broadcast to millions of clients saturates the pub/sub bus. Both need explicit buffering limits and slow-consumer eviction long before you hit connection limits."
faqAnswers:
  - question: "When is websocket architecture at scale the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for websocket architecture at scale?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back websocket architecture at scale safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
The first time I ran a real-time system at scale — live match analytics pushing player and ball positions to tens of thousands of viewers — the connection count was never the thing that broke. What broke was one phone on a bad train connection that stopped reading its socket, and a fan-out loop that happily buffered megabytes of position updates for it until the node ran out of memory. That's the lesson that reframes WebSocket architecture at scale: holding connections is easy, and moving messages through them under pressure is where the engineering actually lives.

This post is about the parts that matter once you're past a single server: connection management, horizontal scaling with pub/sub, backpressure, and the failure modes that only show up at load.

## Connections are cheap, fan-out is not

A modern Linux server can hold a very large number of idle WebSocket connections. Each connection costs you a file descriptor and some kernel and application memory for buffers — on the order of tens of kilobytes if you're careful. Tune `ulimit -n`, `net.ipv4.tcp_mem`, and your runtime's per-connection buffer sizes and a single node comfortably parks 100k+ sleeping sockets.

The number that actually determines your architecture is **messages per second times recipients**. Pushing one update per second to 50,000 clients is 50,000 sends per second from one logical event. Pushing 20 position updates per second to the same audience is a million sends per second. CPU, serialization cost, and socket writes are your budget, and they're spent on fan-out, not on the connections sitting there.

So the first design decision is: minimize the work per broadcast. Serialize the payload once, not once per client. Batch high-frequency updates into a single frame at a fixed tick (say 10 Hz) instead of forwarding every upstream event. Use a compact binary format — I've reached for MessagePack and, for hot paths, hand-rolled binary — rather than re-encoding JSON per recipient.

## Scaling horizontally: the pub/sub backbone

One node isn't enough, and the moment you have two, you have a routing problem: a client connected to node A sends a message that a client on node B needs to receive. WebSocket connections are stateful and long-lived, so you can't just round-robin requests. The standard answer is a message bus between nodes.

```
        ┌──────────┐        ┌──────────┐
client──│  Node A  │        │  Node B  │──client
        └────┬─────┘        └────┬─────┘
             │   publish/subscribe   │
             └──────►  Redis / NATS  ◄┘
```

Each node subscribes to the channels relevant to its currently-connected clients. When node A receives a message for room `match:42`, it publishes to that channel; every node with a subscriber for `match:42` — including A itself — delivers to its local sockets. This keeps nodes stateless about *each other*: they only know their own connections plus the bus.

Choosing the bus matters:

| Bus | Best for | Watch out for |
|---|---|---|
| Redis pub/sub | Simple broadcast, low ops overhead | No persistence; a disconnected node misses messages |
| NATS | High throughput, subject wildcards, clustering | At-most-once by default; use JetStream for durability |
| Kafka | Durable, replayable event streams | Higher latency, heavier ops, overkill for pure fan-out |

For pure real-time fan-out where a dropped frame is fine (live positions, presence, cursors), Redis or core NATS is the right weight. When a client must not miss a message (chat history, order updates), you need durability and per-client cursors, which pushes you toward JetStream or Kafka plus a catch-up read from a store on reconnect.

## Sticky connections and where state lives

A WebSocket connection lives on exactly one node for its whole life, so your load balancer needs connection-level stickiness — which you get for free since the TCP connection stays open. What you *don't* get for free is where you keep per-connection state: subscriptions, auth context, presence.

Keep the authoritative connection state on the node that owns the connection, and mirror only what other nodes need (presence, room membership) into a shared store with a TTL. I lean on Redis with short TTLs and heartbeat refresh so that when a node dies, its presence entries expire on their own rather than requiring a cleanup crawl. Don't try to make connection state globally consistent — it's inherently local and ephemeral.

## Backpressure: the failure mode everyone forgets

Here's the one that took down my early system. A WebSocket send is not instantaneous — it writes to a per-connection buffer that drains at the client's network speed. A healthy client drains fast. A dead or throttled client doesn't drain at all, and if your code keeps calling `send()`, that buffer grows without bound until the process OOMs.

You must treat every slow consumer as a liability and enforce limits:

```go
// Per-connection send with a bounded queue; drop the client if it can't keep up.
select {
case conn.sendCh <- payload:
    // queued
default:
    // buffer full: client is too slow, evict it
    metrics.slowConsumerDrops.Inc()
    conn.closeWithReason(websocket.CloseTryAgainLater, "slow consumer")
}
```

The policy — drop vs. drop-oldest vs. disconnect — depends on your data. For live position streams, dropping the *oldest* queued frame is correct: a stale position is worthless, the latest is all that matters. For chat, you can't silently drop; you disconnect and let the client reconnect and fetch missed history. The one thing you can never do is buffer unbounded. Set a max queue depth per connection and a max total, and shed load deliberately.

## Heartbeats, reconnection, and mobile reality

Networks lie about being connected. A phone that walks into a tunnel keeps a TCP connection that looks alive for minutes. Ping/pong heartbeats at the protocol level are how you detect this: send a ping every 20–30 seconds, and if you don't get a pong within a timeout, close the connection and reclaim its resources. Without this, dead connections accumulate and eat your capacity.

On the client, reconnection needs exponential backoff with jitter, or a server restart triggers a thundering herd where every client reconnects in the same second. This is the same discipline I write about in [handling flaky networks in mobile apps](https://blog.michaelsam94.com/handling-flaky-networks-mobile/) — the connection dropping is the normal case, not the exception, so design the resume path first. On reconnect, the client sends its last-seen sequence number and the server replays anything missed from a durable log, if your semantics require it.

## Load shedding and graceful degradation

At the top of the traffic curve — a goal in a World Cup match, a product launch — you will exceed capacity for short bursts. Decide in advance how you degrade. Options I've used: drop the tick rate (10 Hz to 2 Hz) under load, coalesce updates more aggressively, reject new connections with a `503`-equivalent close code while protecting existing ones, and cap fan-out group sizes. Deciding this under fire is how you get an outage; deciding it in a design doc is how you get a bad ten minutes instead.

Rate limiting inbound messages matters too — a single misbehaving client shouldn't be able to publish thousands of messages a second into a room. The [rate limiting and backpressure](https://blog.michaelsam94.com/rate-limiting-backpressure/) tactics from HTTP apply directly to WebSocket ingress.

## Putting it together

A WebSocket system that scales looks like: stateless nodes each holding a slice of connections, a pub/sub bus routing messages between them, presence and room state in a shared store with TTLs, strict per-connection backpressure with slow-consumer eviction, heartbeats to reap dead sockets, and a pre-planned degradation ladder for peak load. None of that is exotic. The discipline is refusing to let any single slow client, dead connection, or traffic spike take down the whole fleet — because at scale, one of those is always happening.

If you're building real-time features into a mobile client, it's worth pairing this with a look at [WebSocket-heavy mobile networking](https://blog.michaelsam94.com/handling-flaky-networks-mobile/) so the client half is as resilient as the server half.

## Resources

- [MDN: The WebSocket API](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)
- [RFC 6455 — The WebSocket Protocol](https://datatracker.ietf.org/doc/html/rfc6455)
- [Redis Pub/Sub documentation](https://redis.io/docs/latest/develop/interact/pubsub/)
- [NATS — JetStream](https://docs.nats.io/nats-concepts/jetstream)
- [Cloudflare: WebSockets](https://developers.cloudflare.com/workers/runtime-apis/websockets/)
- [The C10K problem](http://www.kegel.com/c10k.html)