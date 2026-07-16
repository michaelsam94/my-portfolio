---
title: "SSE vs WebSockets for Real-Time"
slug: "realtime-protocols-sse-vs-websocket"
description: "Choosing between Server-Sent Events and WebSockets: one-way vs bidirectional, HTTP/2 behavior, reconnection, proxies, and decision criteria for real-time apps."
datePublished: "2026-01-10"
dateModified: "2026-01-10"
tags: ["Real-Time", "Web", "Backend", "Architecture"]
keywords: "SSE vs WebSocket, Server-Sent Events, real-time protocol, EventSource, long polling, bidirectional communication"
faq:
  - q: "When should I use SSE instead of WebSockets?"
    a: "Use SSE when the server pushes data to the client and the client rarely needs to send messages back over the same channel (or can use regular HTTP POST for upstream). SSE works over standard HTTP, auto-reconnects, and passes through most corporate proxies. WebSockets fit when you need low-latency bidirectional messaging — chat, multiplayer games, collaborative cursors."
  - q: "Does SSE work with HTTP/2?"
    a: "Yes. SSE runs as a long-lived HTTP GET request. Under HTTP/2, it shares the connection with other requests via multiplexing, though a slow SSE stream can still consume flow-control window if not managed. HTTP/1.1 limits concurrent connections per host (typically six), which historically made SSE expensive — HTTP/2 largely removes that penalty."
  - q: "How does SSE handle reconnection?"
    a: "The browser EventSource API automatically reconnects on disconnect and sends the Last-Event-ID header so the server can replay missed events. You must design the server to buffer recent events keyed by ID or accept gaps after long outages. WebSockets require custom reconnection and replay logic — nothing is built into the protocol."
---

Every real-time feature starts with the same question: WebSockets or something simpler? Teams reach for WebSockets by default because they feel like the "real" real-time protocol. Half the time SSE would have shipped in a day, worked through the corporate proxy without incident, and covered the actual requirement — server pushes updates, client sends commands via normal REST.

I learned this rebuilding a notification feed. WebSockets worked in dev; in production, an intermediary stripped upgrade headers for certain enterprise customers. SSE over HTTPS sailed through unchanged.

## Protocol comparison at a glance

| | SSE | WebSocket |
| --- | --- | --- |
| Direction | Server → client | Bidirectional |
| Transport | HTTP (text/event-stream) | WS upgrade, framed messages |
| Browser API | EventSource (native) | WebSocket (native) |
| Auto-reconnect | Built-in | Roll your own |
| Binary data | No (UTF-8 text) | Yes |
| Proxy/firewall | Usually fine | Sometimes blocked |

Neither is universally better. Match the protocol to traffic shape.

## Server-Sent Events in practice

SSE is a long-lived HTTP response with `Content-Type: text/event-stream`:

```
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive

id: 42
event: price-update
data: {"symbol":"AAPL","price":189.50}

id: 43
data: {"symbol":"MSFT","price":420.10}

```

Client:

```javascript
const source = new EventSource("/api/stream/prices", {
  withCredentials: true,
});

source.addEventListener("price-update", (e) => {
  const tick = JSON.parse(e.data);
  updateChart(tick);
});

source.onerror = () => {
  // EventSource reconnects automatically; show stale indicator in UI
  markFeedStale();
};
```

Server (Node/Express sketch):

```javascript
app.get("/api/stream/prices", (req, res) => {
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.flushHeaders();

  const lastId = req.headers["last-event-id"];
  replayMissedEvents(res, lastId);

  const subscription = priceBus.subscribe(tick => {
    res.write(`id: ${tick.id}\nevent: price-update\ndata: ${JSON.stringify(tick)}\n\n`);
  });

  req.on("close", () => subscription.unsubscribe());
});
```

Upstream client actions (acknowledge alert, change filter) go through regular `fetch` POST — no need for a back channel on the same socket.

## WebSockets when bidirectional matters

Chat, collaborative editing sync, and multiplayer game state need client-to-server messages at high frequency without HTTP overhead per message. WebSockets excel here:

```javascript
const ws = new WebSocket("wss://api.example.com/ws/room-7");

ws.onopen = () => ws.send(JSON.stringify({ type: "join", userId }));
ws.onmessage = (e) => handleMessage(JSON.parse(e.data));

// Reconnection — not automatic
ws.onclose = () => scheduleReconnect(exponentialBackoff);
```

You own heartbeat, auth refresh, backpressure, and replay. Libraries like Socket.IO add these layers; raw WebSockets do not.

## The hidden costs people miss

**SSE connection limits on HTTP/1.1.** Six connections per host meant six SSE streams max unless you shard domains or upgrade to HTTP/2. Still relevant for legacy clients.

**WebSocket sticky sessions.** Stateful servers need session affinity or a shared pub/sub backplane (Redis) so any node can serve any connection.

**SSE text-only.** Send binary (protobuf, compressed frames) → WebSocket or fetch streaming.

**Load balancer idle timeouts.** Both protocols hit LB timeouts (often 60s). Configure TCP keep-alive and application heartbeats (SSE comment lines `: ping\n\n` every 30s).

## Hybrid pattern that works

Many production apps combine both:

- **SSE** for server push: notifications, log tail, build status, stock ticks.
- **HTTP POST/PUT** for client commands: mark read, submit form, run query.
- **WebSocket** only for features that truly need duplex low-latency sync.

This reduces WebSocket connection count (expensive on some hosts) and simplifies auth — SSE reuses cookie sessions; WebSockets often need token-in-query or post-connect auth messages.

## Decision checklist

Choose **SSE** if:

- Flow is primarily server → client
- You want automatic reconnect with event IDs
- You must traverse restrictive proxies
- Team prefers standard HTTP tooling (CDN, WAF, logging)

Choose **WebSockets** if:

- Both directions send frequently
- Latency below ~50ms matters per message
- You need binary frames
- You already run a WS-aware infra stack

If you are unsure, prototype with SSE first. Adding WebSocket later is a migration; downgrading from WebSocket to SSE after clients depend on bidirectional messaging is painful. Both protocols hit browser connection limits (six per domain on HTTP/1.1). HTTP/2 and HTTP/3 reduce this constraint — consolidate events into fewer streams with client-side filtering if you need many parallel feeds.

## Common production mistakes

Teams get protocols sse vs websocket wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of protocols sse vs websocket fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When protocols sse vs websocket misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [MDN EventSource documentation](https://developer.mozilla.org/en-US/docs/Web/API/EventSource)
- [HTML Living Standard — SSE](https://html.spec.whatwg.org/multipage/server-sent-events.html)
- [RFC 6455 — The WebSocket Protocol](https://datatracker.ietf.org/doc/html/rfc6455)
- [WebSocket API (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
- [What is SSE? (web.dev)](https://web.dev/articles/eventsource-basics)
