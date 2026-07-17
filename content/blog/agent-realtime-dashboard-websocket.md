---
title: "AI Agents: Realtime Dashboard Websocket"
slug: "agent-realtime-dashboard-websocket"
description: "Ship a WebSocket-backed operations dashboard for agent fleets: channel design, snapshot-plus-delta protocol, horizontal scale with pub/sub backplanes, and backpressure when trace volume exceeds browser capacity."
datePublished: "2025-03-22"
dateModified: "2025-03-22"
tags: ["AI", "Agent", "Realtime"]
keywords: "WebSocket agent dashboard, realtime ops telemetry, Redis pubsub agent traces, snapshot delta protocol, agent monitoring UI"
faq:
  - q: "WebSocket or SSE for an agent ops dashboard?"
    a: "WebSocket when you need bidirectional control: cancel run, ack alert, subscribe to tenant filters. SSE is simpler for read-only metric streams. Agent ops consoles almost always grow bidirectional — start with WebSocket or wrap SSE behind an upgrade path."
  - q: "How do you prevent one tenant's trace flood from lagging everyone else's dashboard?"
    a: "Per-tenant topics on the pub/sub backplane, per-connection outbound queues with drop-oldest for low-priority spans, and hard caps on events/sec per subscription. Never multiplex all tenants through one firehose channel."
  - q: "What should the first message after connect contain?"
    a: "A snapshot: active runs, recent failures, aggregate counters, and schema version. Then deltas only. Clients that miss deltas use sequence numbers to detect gaps and request resync — do not replay unbounded history over the socket."
  - q: "How do you authenticate WebSocket connections for internal dashboards?"
    a: "Short-lived JWT in Sec-WebSocket-Protocol or query param exchanged during HTTP upgrade, validated before accept. Re-auth on token expiry with 4401 close code. Bind subscriptions server-side to claims — never trust client-sent tenant_id without verification."
---

The incident started when someone opened the agent ops dashboard during a load test. Three hundred engineers didn't — three hundred **browser tabs** did, each holding a WebSocket that expected every tool span from every run. The pub/sub cluster melted, Redis output buffers ballooned, and the dashboard itself became the outage it was meant to diagnose.

Realtime agent dashboards are not CRUD apps with fancy polling. They are **streaming systems** with browsers on one end and firehoses of trace data on the other.

## What the UI actually needs

Operators watch different signals than end users:

- Run lifecycle: `queued → running → tool_call → completed | failed`
- Token burn rate and cost accumulation per tenant
- Error spikes by tool name and model version
- Active concurrency vs rate limit headroom
- Deploy markers overlaid on latency charts

Polling `/api/runs` every two seconds collapses at 500 concurrent runs. Push is mandatory; the design choice is **what to push** and **what to aggregate server-side**.

## Topology

```
 Agent workers ──► Kafka (trace topic)
                         │
                         ▼
                 Stream aggregator
                 (windowed counters)
                         │
            ┌────────────┼────────────┐
            ▼            ▼            ▼
        Redis       Postgres     Alerting
        pub/sub     (snapshots)
            │
            ▼
    WebSocket gateway (stateless, N replicas)
            │
            ▼
       Browser dashboard
```

Workers emit structured events. Aggregators compute rollups — do not forward raw spans to every browser. The WebSocket tier is stateless; session state lives in the pub/sub subscription set plus an in-memory outbound queue per connection.

## Wire protocol: snapshot, delta, resync

Version your messages from day one:

```typescript
type WireMessage =
  | { type: "snapshot"; seq: number; schema: 2; data: DashboardSnapshot }
  | { type: "delta"; seq: number; ops: DeltaOp[] }
  | { type: "gap"; fromSeq: number; toSeq: number }
  | { type: "ping"; ts: number }
  | { type: "pong"; ts: number };

interface DashboardSnapshot {
  activeRuns: RunSummary[];
  counters: {
    runsStarted: number;
    runsFailed: number;
    tokensUsed: number;
  };
  recentErrors: ErrorEvent[];
  serverTime: string;
}
```

On connect:

1. Authenticate upgrade
2. Send `snapshot` with `seq=1000`
3. Stream `delta` messages `1001, 1002, …`
4. Client tracks `lastSeq`; if gap detected, HTTP `GET /dashboard/resync?since=994`

Delta ops keep payloads small:

```json
{
  "type": "delta",
  "seq": 1001,
  "ops": [
    { "op": "inc", "path": "counters.tokensUsed", "value": 842 },
    { "op": "set", "path": "activeRuns.run_9.status", "value": "failed" },
    { "op": "append", "path": "recentErrors", "value": { "run_id": "run_9", "tool": "search" }, "max": 50 }
  ]
}
```

## Server-side subscription routing

```typescript
import { WebSocketServer, WebSocket } from "ws";

const wss = new WebSocketServer({ noServer: true });

interface ClientContext {
  ws: WebSocket;
  tenantIds: string[];
  lastSeq: number;
  outbound: AsyncQueue<string>;
}

wss.on("connection", (ws, req, ctx: ClientContext) => {
  const channels = ctx.tenantIds.map((t) => `agent:dashboard:${t}`);

  const sub = redis.duplicate();
  sub.subscribe(...channels);

  sub.on("message", (_channel, payload) => {
    const msg = enrichAndFilter(JSON.parse(payload), ctx);
    if (!msg) return;
    if (!ctx.outbound.tryEnqueue(JSON.stringify(msg))) {
      metrics.increment("dashboard_backpressure_drop");
    }
  });

  ws.on("close", () => {
    sub.unsubscribe();
    sub.quit();
    ctx.outbound.close();
  });

  pumpOutbound(ctx); // async loop: queue → ws.send
});
```

Filter **server-side** by tenant claims. Client-sent `subscribe: { tenant: "*" }` is a security bug.

## Backpressure and slow consumers

Browsers choke before servers do. Per-connection:

- Bounded outbound queue (e.g. 256 messages)
- Drop policy: coalesce counter increments, drop debug spans first, never drop run terminal states
- Heartbeat every 30s; close with 4408 if client stops ponging

```typescript
class CoalescingQueue {
  private pendingDeltas = new Map<string, DeltaOp>();
  private queue: string[] = [];
  private maxSize: number;

  pushDelta(op: DeltaOp) {
    const key = `${op.op}:${op.path}`;
    const existing = this.pendingDeltas.get(key);
    if (existing?.op === "inc" && op.op === "inc") {
      existing.value += op.value;
    } else {
      this.pendingDeltas.set(key, { ...op });
    }
    this.flushCoalesced();
  }

  private flushCoalesced() {
    if (this.queue.length >= this.maxSize) {
      this.queue.shift(); // drop oldest
    }
    const ops = Array.from(this.pendingDeltas.values());
    this.pendingDeltas.clear();
    this.queue.push(JSON.stringify({ type: "delta", ops }));
  }
}
```

When drops exceed threshold, send `gap` so the client resyncs via HTTP — partial state beats wedged sockets.

## Bidirectional control plane

Ops dashboards need actions:

```json
{ "type": "command", "action": "cancel_run", "run_id": "run_9", "request_id": "cmd_1" }
```

Validate commands against RBAC, enqueue to a command topic, ack with `{ "type": "command_ack", "request_id": "cmd_1", "status": "accepted" }`. Never execute synchronously inside the WebSocket handler — slow commands block the event loop and stall broadcasts.

## Horizontal scale

WebSocket gateways don't share memory. Scale with:

- Sticky sessions at load balancer **or** Redis pub/sub where every gateway subscribes to all channels (works to ~ moderate scale)
- For large deployments: shard channels by `hash(tenant_id) % N` with gateway affinity

Kubernetes: terminate TLS at ingress, enable WebSocket upgrade, set idle timeout above heartbeat interval. Liveness probe HTTP only — TCP probes lie about WS health.

## Frontend integration sketch

```typescript
function connectDashboard(token: string): DashboardClient {
  const ws = new WebSocket(`wss://ops.example.com/ws`, [`auth.${token}`]);
  let lastSeq = 0;
  let state: DashboardSnapshot | null = null;

  ws.onmessage = (ev) => {
    const msg: WireMessage = JSON.parse(ev.data);

    if (msg.type === "snapshot") {
      state = msg.data;
      lastSeq = msg.seq;
      render(state);
      return;
    }

    if (msg.type === "delta") {
      if (msg.seq !== lastSeq + 1) {
        resync(lastSeq);
        return;
      }
      state = applyOps(state!, msg.ops);
      lastSeq = msg.seq;
      render(state);
    }

    if (msg.type === "gap") {
      resync(msg.fromSeq);
    }
  };

  return { ws, getState: () => state };
}
```

Use React external store or canvas charts for high-frequency counters — do not `setState` on every token increment.

## Security checklist

- TLS everywhere; `wss` only in production
- Short-lived tokens; reconnect loop re-auths
- Rate limit upgrade attempts per IP
- Sanitize run metadata before push — prompts may contain PII
- Audit log every command action with actor and run_id

## Testing

- Property test: applying snapshot then deltas equals batch snapshot at seq N
- Load test: 1k connections, 10k events/sec aggregate, measure p99 delivery latency
- Chaos: kill one gateway pod, verify clients reconnect and resync
- Browser test: throttle CPU 6x, confirm backpressure drops without freezing tab

A realtime agent dashboard should feel instant and fail quietly — degrading to HTTP resync under load, not taking down the observability path when traces spike.

## Deploy markers and comparative overlays

Ops teams need to correlate agent behavior with releases. Emit deploy events into the same trace stream:

```json
{
  "event_type": "deploy_marker",
  "service": "agent-gateway",
  "version": "2.14.0",
  "git_sha": "a1b2c3d",
  "timestamp": "2025-03-22T18:04:00Z",
  "tenant_scope": "all"
}
```

The dashboard renders vertical markers on latency and error charts. WebSocket deltas include `{ "op": "marker", "version": "2.14.0", "ts": "..." }` so live viewers see deploys without refresh.

When comparing model versions (`gpt-4o` vs `gpt-4o-mini`), pre-aggregate metrics server-side into `{ model: { p50_ms, error_rate, tokens_per_run } }` — do not stream per-run comparisons for every client. Comparison mode is a separate HTTP fetch triggered by UI toggle; default stream stays lightweight.

## Historical replay without melting the socket

Investigating yesterday's incident shouldn't require replaying six million spans over WebSocket. Pattern:

- Live socket: last 15 minutes, high resolution
- HTTP `/runs?from=&to=`: paginated historical runs
- On-demand **replay channel**: client sends `{ "type": "replay_request", "run_id": "run_9" }`, server streams that run's spans at controlled rate (50/sec max), then closes replay sub-channel

Replay uses a different Redis channel (`agent:replay:${run_id}`) so it doesn't pollute tenant broadcast topics. Rate-limit replay requests per user — forensics is important, but one engineer downloading an entire tenant's history via WebSocket is exfiltration wearing a debugger costume.

## Resources

- [RFC 6455 — The WebSocket Protocol](https://datatracker.ietf.org/doc/html/rfc6455)
- [ws library (Node.js WebSocket)](https://github.com/websockets/ws)
- [Redis Pub/Sub documentation](https://redis.io/docs/interact/pubsub/)
- [OpenTelemetry trace model](https://opentelemetry.io/docs/concepts/signals/traces/)
- [MDN WebSocket API](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
