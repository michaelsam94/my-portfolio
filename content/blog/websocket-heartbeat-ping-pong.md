---
title: "WebSocket Heartbeats and Health"
slug: "websocket-heartbeat-ping-pong"
description: "Detect dead WebSocket connections with protocol pings and app heartbeats: idle timeouts, proxy quirks, and half-open TCP realities."
datePublished: "2026-05-26"
dateModified: "2026-07-17"
tags: ["Web", "IoT", "Networking"]
keywords: "WebSocket ping pong, websocket heartbeat, keepalive websocket, half-open connection, idle timeout load balancer"
faq:
  - q: "What's the difference between WebSocket protocol ping and app heartbeats?"
    a: "Protocol-level Ping/Pong frames are handled by the WebSocket stack and may not be visible to your app code in browsers. App-level heartbeats (JSON `{type:'ping'}`) are visible, work everywhere, and can carry health metadata — but you must implement timeout logic yourself."
  - q: "Why does my connection die after 60 seconds of silence?"
    a: "Many load balancers and NATs close idle TCP connections. Send traffic (pings) more frequently than the idle timeout — commonly every 15–30s — and configure the LB timeout to match your design."
  - q: "Who should ping, client or server?"
    a: "Either works; pick one side as authoritative for timeout. Often the server pings and closes silent clients to protect resources; mobile clients also ping to refresh NAT bindings."
---
TCP won't tell you quickly that a laptop lid closed on a cellular network. Half-open connections linger until something times out. Heartbeats make liveness explicit so you can reconnect ([with backoff](https://blog.michaelsam94.com/websocket-reconnection-backoff/)) instead of waiting on a zombie socket.

## App-level heartbeat

```typescript
const INTERVAL = 20_000;
const TIMEOUT = 10_000;

setInterval(() => {
  const id = crypto.randomUUID();
  socket.send(JSON.stringify({ type: "ping", id }));
  const t = setTimeout(() => socket.close(), TIMEOUT);
  // clear t on matching pong
}, INTERVAL);
```

## Infra alignment

Document and set:

- LB idle timeout > heartbeat interval
- Server read timeouts
- Client visibility API — pause heartbeats when tab hidden if you don't need background sockets

## Metrics

Track ping RTT, missed pongs, forced closes. Spikes after deploys often mean timeout misconfiguration, not app bugs.

Heartbeats are cheap insurance. Silence isn't health.

## Mobile and background tabs

Browsers throttle timers in background tabs — heartbeat intervals may fire less frequently. Use shorter timeouts (2x interval instead of 3x) for mobile clients. Listen for `document.visibilitychange` to ping immediately when the tab becomes visible again.

## Load balancer sticky sessions

When using WebSocket with multiple server instances, ensure sticky sessions or shared pub/sub (Redis) so messages reach the correct connection. Heartbeats should be handled by the instance holding the connection, not broadcast to all nodes.

## Debugging checklist

When something doesn't work as documented, verify browser support with Can I use before assuming a polyfill bug. Check the Network tab for failed resource loads, incorrect MIME types, and missing CORS headers. Use the Console for CSP violations and Trusted Types errors that silently block operations.

Compare behavior in incognito mode to rule out extension interference. Test with cache disabled during development but validate with realistic caching in staging. Read the specification for edge cases the tutorial skipped — MDN examples cover happy paths, not every boundary condition.

If performance regresses after deployment, roll back first and investigate second. Keep a changelog of performance-related changes linked to metric dashboards. Future you will need to know why that preload tag exists before removing it during a refactor.

## Integration with your stack

Every technique in this guide adapts to your framework and hosting environment. Next.js, Nuxt, Rails, and Django each have conventions for where static assets live, how SSR works, and where to inject resource hints. Map the concepts here to your stack's documentation rather than copying snippets verbatim.

Staging environments should mirror production CDN configuration, HTTP/2 settings, and compression. A fix validated locally over HTTP/1.1 without compression may behave differently behind Cloudflare or Fastly. Deploy performance changes to a canary percentage before full rollout when your platform supports it.

Train the team on these patterns during code review. Performance regressions usually arrive as small PRs — one unoptimized image, one synchronous script, one missing width attribute. Reviewers who recognize LCP and CLS anti-patterns catch issues before they reach production.

## Key takeaways

Start with measurement, ship the smallest fix that addresses the root cause, and validate in field data. Performance and security work is never finished — it evolves with your product, traffic, and the browser platform. Return to these patterns when onboarding new team members or auditing legacy code paths.

Document your configuration choices in runbooks so on-call engineers know which timeouts, intervals, and policies are intentional rather than defaults.
Set pong timeout to 2× ping interval — mobile networks suspend TCP without closing socket; heartbeat detects zombie connections.

## Load balancer idle timeouts

AWS ALB default idle 60s — without ping, connection appears open while LB closed. Align client ping to 20-30s interval.

## Resources

- [RFC 6455 — Ping/Pong](https://datatracker.ietf.org/doc/html/rfc6455#section-5.5.2)
- [MDN — WebSocket](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
---

## Operational checklist (1)

Before promoting Websocket Heartbeat Ping Pong changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (2)

Re-baseline Websocket Heartbeat Ping Pong after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (3)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Websocket Heartbeat Ping Pong touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (4)

Before promoting Websocket Heartbeat Ping Pong changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (5)

Re-baseline Websocket Heartbeat Ping Pong after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (6)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Websocket Heartbeat Ping Pong touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (7)

Before promoting Websocket Heartbeat Ping Pong changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (8)

Re-baseline Websocket Heartbeat Ping Pong after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Incident patterns around websocket heartbeat ping pong

Most incidents involving websocket heartbeat ping pong start as a silent drift: a secondary path skips the control, a retry amplifies load, or a config default from a tutorial ships to production. Write the failure story before the happy path.

| Check | Expected for websocket heartbeat ping pong |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 1: inject the failure mode you fear for websocket heartbeat ping pong in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Invariants to enforce for websocket heartbeat ping pong

Name three invariants that must hold after every deploy of websocket heartbeat ping pong. Encode at least one in an automated test that fails when the invariant is disabled. Reviewers should reject PRs that only cover the primary UI path.

Concrete probe 2: inject the failure mode you fear for websocket heartbeat ping pong in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Telemetry and ownership for websocket heartbeat ping pong

Pair a leading operational signal with a lagging user or risk outcome. Page on burn related to websocket heartbeat ping pong, not vanity counters. Keep a named owner and a dashboard link in the service catalog entry.

| Check | Expected for websocket heartbeat ping pong |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 3: inject the failure mode you fear for websocket heartbeat ping pong in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Rollout sequence for websocket heartbeat ping pong

Prefer flags, weighted routes, or dual-running configs. Rehearse rollback once in staging. The on-call note for websocket heartbeat ping pong should include the revert command and the expected user-visible effect within five minutes.

Concrete probe 4: inject the failure mode you fear for websocket heartbeat ping pong in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Cross-team contracts for websocket heartbeat ping pong

Document producers, consumers, timeouts, and idempotency keys. Silent schema or policy changes are how websocket heartbeat ping pong breaks without a clear owner in the incident channel.

| Check | Expected for websocket heartbeat ping pong |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 5: inject the failure mode you fear for websocket heartbeat ping pong in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Capacity and cost notes for websocket heartbeat ping pong

Estimate QPS, payload size, cardinality, and downstream saturation. Functionally correct websocket heartbeat ping pong changes still cause outages through pool exhaustion, crawl waste, or CPU amplification.

Concrete probe 6: inject the failure mode you fear for websocket heartbeat ping pong in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Reviewer checklist for websocket heartbeat ping pong

Ask what happens when the dependency is slow, when authz is skipped on batch jobs, and when clients retry. Those three questions catch most websocket heartbeat ping pong regressions before production.

| Check | Expected for websocket heartbeat ping pong |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 7: inject the failure mode you fear for websocket heartbeat ping pong in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.
