---
title: "WebSocket Heartbeats and Health"
slug: "websocket-heartbeat-ping-pong"
description: "Detect dead WebSocket connections with protocol pings and app heartbeats: idle timeouts, proxy quirks, and half-open TCP realities."
datePublished: "2026-05-26"
dateModified: "2026-05-26"
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

## Measuring success in production

Deploy changes behind feature flags when possible so you can compare metrics between control and treatment groups. Use Real User Monitoring to capture performance data from actual devices and network conditions — lab tools alone miss the long tail of user experiences. Set up alerts for regressions: a 10% LCP increase week-over-week warrants investigation before it hits CrUX.

Document your baseline metrics before making changes. Performance work without measurement is guesswork. Share results with the team — concrete numbers ("LCP improved 800ms on mobile") build support for continued investment in web performance and reliability.

Review changes quarterly. Browser updates, new API support, and traffic pattern shifts can obsolete previous optimizations or create new opportunities. What worked in 2024 may not be the best approach in 2026.

## Additional production considerations

Teams often underestimate the maintenance cost of performance optimizations. Automate what you can: CI bundle budgets, Lighthouse CI on PRs, and RUM dashboards that alert on regressions. Manual audits don't scale past a handful of pages.

Security and performance intersect more than teams expect. Third-party scripts that hurt INP also expand your attack surface. Self-hosting fonts and critical assets reduces both latency and supply-chain risk. Review every external dependency quarterly — remove what you no longer need.

Accessibility and performance share goals: semantic HTML helps screen readers and gives the browser better rendering hints. Native elements like dialog, popover, and details reduce JavaScript while improving accessibility. Prefer platform features over custom implementations when they meet your requirements.

Mobile users dominate traffic for most sites. Test on real mid-tier Android hardware, not just desktop Chrome. Simulated throttling in DevTools approximates network conditions but not CPU constraints. A fix that helps desktop may be invisible on mobile if the bottleneck is JavaScript execution, not network.

Collaborate with backend teams on TTFB and API response times. Frontend optimizations can't fix a 2-second server response. Set SLAs for API endpoints that feed critical pages and measure them in the same RUM pipeline as Core Web Vitals.

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

## Resources

- [RFC 6455 — Ping/Pong](https://datatracker.ietf.org/doc/html/rfc6455#section-5.5.2)
- [MDN — WebSocket](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
---
