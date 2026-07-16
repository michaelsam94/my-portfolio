---
title: "GraphQL Subscriptions at Scale"
slug: "graphql-subscriptions-realtime"
description: "Run GraphQL subscriptions in production: WebSocket transport, pub/sub backends, authorization, connection scaling, and when subscriptions beat polling."
datePublished: "2025-06-16"
dateModified: "2025-06-16"
tags: ["Backend", "GraphQL", "API", "Architecture"]
keywords: "GraphQL subscriptions, WebSocket GraphQL, real-time GraphQL, Redis pubsub GraphQL, subscription scaling, graphql-ws"
faq:
  - q: "When should I use GraphQL subscriptions instead of polling?"
    a: "Use subscriptions when clients need near-real-time updates for events they can't predict the timing of — chat messages, live order status, notification feeds. Polling is simpler and cheaper when update frequency is low or predictable (every 30 seconds is fine). Subscriptions add persistent connection overhead."
  - q: "What transport do GraphQL subscriptions use?"
    a: "WebSocket is the standard transport. The graphql-ws protocol (not the deprecated subscriptions-transport-ws) handles connection init, authentication, keep-alive pings, and subscription lifecycle over a single persistent WebSocket connection per client."
  - q: "How do I scale GraphQL subscriptions horizontally?"
    a: "Use a pub/sub broker (Redis, Kafka, NATS) between your event sources and GraphQL server instances. When an event occurs, publish to the broker; each server instance subscribed to the topic pushes to its connected WebSocket clients. No single server needs to know about all connections."
---

Subscriptions are the part of GraphQL everyone wants in the demo and nobody wants to run in production. Persistent WebSocket connections, pub/sub wiring, auth on every subscribe, reconnect storms after deploys — it's real infrastructure. But when you need live updates (order tracking, collaborative editing, alert feeds), subscriptions beat polling hard. Here's how to run them without the connection count eating your server alive.

## Subscriptions vs polling vs SSE

| Approach | Latency | Server load | Complexity |
|----------|---------|-------------|------------|
| Polling | Seconds | High (repeated queries) | Low |
| SSE | Sub-second | Medium (one HTTP stream) | Medium |
| WebSocket subscriptions | Sub-second | High (persistent connections) | High |

GraphQL subscriptions use WebSocket because the client initiates typed subscription operations with variables and receives typed payloads — SSE can't carry GraphQL subscription semantics cleanly.

## Basic subscription schema

```graphql
type Subscription {
  orderStatusChanged(orderId: ID!): OrderStatusEvent!
  messageReceived(roomId: ID!): Message!
}

type OrderStatusEvent {
  orderId: ID!
  status: OrderStatus!
  updatedAt: DateTime!
}
```

Client:

```javascript
import { createClient } from 'graphql-ws';
import { WebSocket } from 'ws';

const client = createClient({
  url: 'wss://api.example.com/graphql',
  connectionParams: { authorization: `Bearer ${token}` },
});

client.subscribe(
  { query: `subscription($id: ID!) { orderStatusChanged(orderId: $id) { status } }`, variables: { id: '123' } },
  { next: (data) => console.log(data), error: (err) => console.error(err), complete: () => {} }
);
```

Use `graphql-ws` — the maintained protocol. Do not use the deprecated `subscriptions-transport-ws`.

## Server setup with Redis pub/sub

A single server instance can manage subscriptions in memory. Multiple instances need a shared pub/sub layer:

```javascript
import { WebSocketServer } from 'ws';
import { useServer } from 'graphql-ws/lib/use/ws';
import { Redis } from 'ioredis';

const pub = new Redis(process.env.REDIS_URL);
const sub = new Redis(process.env.REDIS_URL);

const resolvers = {
  Subscription: {
    orderStatusChanged: {
      subscribe: (_, { orderId }) => {
        const channel = `order:${orderId}:status`;
        return {
          [Symbol.asyncIterator]: () => {
            const queue = [];
            let resolve;
            sub.subscribe(channel);
            sub.on('message', (ch, msg) => {
              if (ch === channel) {
                if (resolve) { resolve({ value: JSON.parse(msg), done: false }); resolve = null; }
                else queue.push(JSON.parse(msg));
              }
            });
            return {
              next: () => new Promise(r => {
                if (queue.length) r({ value: queue.shift(), done: false });
                else resolve = r;
              }),
              return: () => { sub.unsubscribe(channel); return Promise.resolve({ done: true }); },
            };
          },
        };
      },
    },
  },
};

// When order status changes elsewhere in your app:
await pub.publish(`order:${orderId}:status`, JSON.stringify({ orderStatusChanged: event }));
```

For production, use a library like `graphql-redis-subscriptions` instead of rolling your own iterator.

## Authorization on subscribe

Auth must happen at subscription time, not just connection time:

```javascript
orderStatusChanged: {
  subscribe: async (_, { orderId }, { user }) => {
    const order = await db.orders.findById(orderId);
    if (!order || order.userId !== user.id) {
      throw new ForbiddenError('Not your order');
    }
    return pubsub.asyncIterator(`order:${orderId}:status`);
  },
},
```

A user who authenticated at WebSocket connect shouldn't be able to subscribe to every order ID by guessing. Validate ownership on each subscribe call.

## Connection scaling

Each WebSocket is a persistent TCP connection. At 100K concurrent users, that's 100K open sockets per server instance behind your load balancer.

Practical limits:
- **Sticky sessions** — required if using in-memory pub/sub (same client → same server)
- **Redis pub/sub** — removes sticky session requirement; any server can push to any client
- **Connection limits per instance** — 10K–50K depending on memory; scale horizontally
- **Keep-alive** — graphql-ws sends ping/pong; configure idle timeout on load balancer (AWS ALB default 60s is too aggressive; set 300s+)

For very high fan-out (millions of subscribers to the same event), consider whether GraphQL subscriptions are the right tool. A dedicated push service or CDN-based live updates may fit better.

## Reconnection handling

Clients disconnect constantly (mobile backgrounding, network switches, deploys). Handle gracefully:

```javascript
const client = createClient({
  url: 'wss://api.example.com/graphql',
  retryAttempts: Infinity,
  retryWait: (retries) => Math.min(1000 * 2 ** retries, 30000),
  shouldRetry: () => true,
  on: {
    connected: () => console.log('connected'),
    closed: () => console.log('disconnected — retrying'),
  },
});
```

Server-side: don't replay missed events through the subscription itself. Clients should refetch current state on reconnect, then re-subscribe for new events.

## When not to use subscriptions

- **Dashboard metrics refreshing every 30s** — poll with a cache TTL
- **Webhook delivery confirmation** — use webhooks, not subscriptions
- **File upload progress** — HTTP streaming or SSE is simpler
- **Cross-user broadcast to millions** — dedicated message bus (Kafka → push gateway)

Subscriptions excel at low-to-medium fan-out, user-scoped, typed real-time events.

## Common production mistakes

Teams get subscriptions realtime wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

GraphQL APIs for subscriptions realtime melt down under nested queries without depth limits, N+1 resolvers hit the database per field, and schema deprecation has no usage telemetry.

## Debugging and triage workflow

When subscriptions realtime misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [graphql-ws GitHub](https://github.com/enisdenjo/graphql-ws) — the WebSocket protocol implementation for GraphQL
- [graphql-redis-subscriptions](https://github.com/davidyaha/graphql-redis-subscriptions) — Redis-backed PubSub engine for GraphQL
- [Apollo Subscriptions documentation](https://www.apollographql.com/docs/react/data/subscriptions/) — client and server setup guides
- [The State of GraphQL Subscriptions (Hasura)](https://hasura.io/blog/the-state-of-graphql-subscriptions/) — protocol comparison and scaling patterns
