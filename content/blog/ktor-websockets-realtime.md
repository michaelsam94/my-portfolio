---
title: "Real-Time Ktor with WebSockets"
slug: "ktor-websockets-realtime"
description: "Build real-time features with Ktor WebSockets: sessions, broadcast channels, heartbeat, backpressure, and scaling horizontally with sticky sessions or pub/sub."
datePublished: "2026-01-16"
dateModified: "2026-01-16"
tags: ["Backend", "Ktor"]
keywords: "Ktor WebSocket, real-time, session, broadcast, heartbeat, Channels, horizontal scaling"
faq:
  - q: "How do Ktor WebSockets relate to HTTP routing?"
    a: "WebSocket routes use the webSocket { } builder inside routing. The client upgrades an HTTP connection via Upgrade header; after handshake, bidirectional FrameChannel communication replaces request/response cycles. Same Application pipeline applies for plugins installed before routing."
  - q: "How do I scale WebSockets across multiple Ktor instances?"
    a: "WebSocket state is local to the instance holding the connection. Scale with sticky sessions at the load balancer, or broadcast events through Redis Pub/Sub, Kafka, or similar so each node forwards messages to its connected clients."
  - q: "Should I use application-level heartbeat over WebSockets?"
    a: "Yes for mobile and browser clients behind NATs and proxies that drop idle connections. Send periodic ping frames or JSON ping messages; close sessions that miss pongs within timeout. Ktor supports Frame.Ping and Frame.Pong."
---

Live order tracking broke whenever we deployed—every WebSocket dropped, and clients did not reconnect for thirty seconds. The server side was a `ConcurrentHashMap` of sessions on one JVM. Moving to **Ktor WebSockets** with explicit heartbeat, structured session handling, and Redis pub/sub for cross-node broadcast fixed deploy blips and let us run three replicas behind the load balancer.

Ktor's WebSocket support is first-class in the routing DSL: suspend handlers, Frame types, and integration with coroutine channels for fan-out.

## Basic WebSocket route

```kotlin
fun Application.module() {
    install(WebSockets) {
        pingPeriod = Duration.ofSeconds(15)
        timeout = Duration.ofSeconds(30)
        maxFrameSize = Long.MAX_VALUE
        masking = false
    }

    routing {
        webSocket("/ws/orders/{orderId}") {
            val orderId = call.parameters["orderId"]!!
            val session = call.receiveSession(orderId)
            session.incoming.collect { frame ->
                when (frame) {
                    is Frame.Text -> handleCommand(frame.readText(), session)
                    is Frame.Close -> return@collect
                    else -> Unit
                }
            }
        }
    }
}
```

`install(WebSockets)` configures ping/pong at engine level.

## Session registry

```kotlin
class OrderSessionHub {
    private val sessions = ConcurrentHashMap<String, MutableSet<OrderSession>>()

    fun join(orderId: String, session: OrderSession) {
        sessions.computeIfAbsent(orderId) { ConcurrentHashMap.newKeySet() }.add(session)
    }

    suspend fun broadcast(orderId: String, message: String) {
        sessions[orderId]?.forEach { session ->
            session.send(message)
        }
    }

    fun leave(orderId: String, session: OrderSession) {
        sessions[orderId]?.remove(session)
    }
}
```

Wrap outgoing send with try/catch—broken pipes throw on send.

## Outgoing channel pattern

Decouple producers from WebSocket writes:

```kotlin
class OrderSession(private val outgoing: SendChannel<Frame>) {
    suspend fun send(text: String) = outgoing.send(Frame.Text(text))
}

webSocket("/ws/orders/{orderId}") {
    val channel = Channel<Frame>(Channel.BUFFERED)
    val writer = launch {
        for (frame in channel) outgoing.send(frame)
    }
    val session = OrderSession(channel)
    hub.join(orderId, session)
    try {
        incoming.collect { /* handle */ }
    } finally {
        hub.leave(orderId, session)
        channel.close()
        writer.cancel()
    }
}
```

Buffered channel absorbs brief send spikes; apply backpressure policy when buffer fills.

## Authentication

Validate JWT from query param or first message before joining hub:

```kotlin
webSocket("/ws") {
    val token = call.request.queryParameters["token"]
    val user = verifyToken(token) ?: run {
        close(CloseReason(CloseReason.Codes.VIOLATED_POLICY, "Unauthorized"))
        return@webSocket
    }
    // ...
}
```

Never accept tokens in logs.

## Horizontal scaling with Redis

```kotlin
// Each instance subscribes to Redis channel "order-events"
redis.subscribe("order-events") { message ->
    val event = json.decodeFromString<OrderEvent>(message)
    hub.broadcast(event.orderId, message)
}

// Business logic publishes once
redis.publish("order-events", json.encodeToString(event))
```

All nodes receive; each forwards only to local sessions. Sticky sessions optional but reduce cross-talk for connection-oriented debugging.

## Client reconnection contract

Document client behavior:

1. Exponential backoff reconnect
2. Resync state via REST after connect (`GET /orders/{id}`)
3. Include `Last-Event-Id` for missed messages if you log history

Server-side session IDs help deduplicate reconnects.

## Load and limits

- Cap connections per IP at reverse proxy
- Set `maxFrameSize` to prevent memory bombs
- Monitor open file descriptors per pod
- Graceful shutdown: broadcast going-away, drain on SIGTERM

## Backpressure on slow clients

If a client cannot read fast enough, outgoing channel buffer fills—drop, disconnect, or sample events. Document policy: trading apps disconnect; chat apps may drop typing indicators only.

## Sticky sessions vs pub/sub

ALB sticky sessions simplify debugging but uneven load during reconnect storms. Prefer pub/sub for broadcast with stateless app servers.


## What to measure after rollout

Track error rates, tail latency, and resource utilization for two weeks after changes land—most regressions appear under real traffic mixes, not in staging smoke tests. Keep a rollback path documented: feature flags, Helm revision, or Git revert with known good digest. Review on-call pages tied to the topic quarterly; delete alerts that never fire and add thresholds that would have caught your last incident.

Run a short blameless postmortem if production surprised you, even for minor issues. The goal is updating this runbook section with one concrete lesson per quarter so the next engineer inherits context, not just configuration snippets.


## Documentation your team should maintain

Maintain a one-page runbook link from your main service README: prerequisites, owner rotation, last drill date, and known sharp edges. Link to vendor docs in the Resources section below but capture org-specific decisions (CIDR ranges, cluster names, approval gates) in internal docs that stay current. New hires should deploy a safe canary within a week using only that runbook—if they cannot, the doc is incomplete.


## Pre-production checklist

Before promoting to production, walk through this list with someone who was not the primary author—fresh eyes catch assumptions.

- **Staging parity**: The staging environment exercises the same code paths as production, including failure modes you expect to handle (timeouts, retries, partial outages).
- **Observability**: Dashboards and alerts exist for the metrics and log patterns discussed above; on-call knows where to look first.
- **Rollback**: You can revert to the previous known-good state in one documented step without improvising.
- **Access control**: Only the principals that need access have it; audit logs are enabled where the topic touches secrets or infrastructure APIs.
- **Load test**: You have evidence—not intuition—about behavior at expected peak plus headroom.

If any item is "we will do that later," treat it as a release blocker for tier-1 services.


## Common questions from reviewers

Reviewers and auditors often ask whether this approach scales with team growth and whether it fails safely. Answer explicitly in your design doc: what happens when dependencies are down, when credentials expire, and when traffic doubles overnight. Prefer defaults that deny or degrade gracefully over defaults that fail open. Document known limits (throughput ceilings, supported versions, regions) in the same place operators look during incidents—avoid scattering critical constraints across Slack threads.


## Resources

- [Ktor WebSockets documentation](https://ktor.io/docs/server-websockets.html) — configuration and API
- [RFC 6455 WebSocket protocol](https://datatracker.ietf.org/doc/html/rfc6455) — frame types and close codes
- [Redis Pub/Sub guide](https://redis.io/docs/interact/pubsub/) — cross-node fan-out pattern
- [Ktor WebSocket sample](https://github.com/ktorio/ktor-samples/tree/main/websocket-chat) — chat reference app
