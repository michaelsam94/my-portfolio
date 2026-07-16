---
title: "System Design: Chat System"
slug: "system-design-chat-messaging"
description: "Design a real-time chat system handling one-to-one and group messaging, presence, read receipts, and message history at scale. Architecture patterns for WhatsApp-scale messaging."
datePublished: "2025-10-09"
dateModified: "2025-10-09"
tags: ["System Design", "Architecture", "Messaging", "Backend"]
keywords: "chat system design, real-time messaging architecture, WebSocket scaling, message queue chat, group chat system design, presence system"
faq:
  - q: "Should a chat system use WebSockets or long polling?"
    a: "WebSockets for production chat — they provide full-duplex, low-latency communication ideal for real-time message delivery and typing indicators. Long polling works as a fallback for restrictive corporate networks but adds latency and server load. Use WebSockets with a fallback transport (SSE or long poll) for clients that can't maintain persistent connections."
  - q: "How do you store message history for billions of messages?"
    a: "Partition messages by conversation ID (chat_id) across a distributed database like Cassandra or ScyllaDB. Hot conversations get dedicated partitions; cold history moves to cheaper storage tiers. Index recent messages in Redis for fast retrieval; paginate older messages from the database with cursor-based queries. Never store all messages in a single SQL table without sharding."
  - q: "How does message delivery work when a user is offline?"
    a: "The message service persists the message, publishes a push notification event, and stores the message in the recipient's inbox queue. When the user reconnects, the client syncs missed messages from the inbox using a last-seen sequence number. Push notifications (APNs/FCM) alert the user on mobile; the full message loads on app open."
---

Designing a chat system sounds simple until you account for group messages fanning out to 500 members, a user with three devices that all need the same message, and the requirement that messages arrive in order even when sent from Tokyo and read in New York. WhatsApp handles over 100 billion messages daily. The architecture that supports that scale separates message ingestion from delivery, uses sequence numbers for ordering, and treats presence as a best-effort overlay — not a blocking dependency.

## High-level architecture

```
Client ←→ WebSocket Gateway ←→ Chat Service ←→ Message Store (Cassandra)
                ↓                    ↓
           Connection Map       Message Queue (Kafka)
                ↓                    ↓
           Presence Service     Push Notification Service
                                     ↓
                               APNs / FCM
```

Clients connect to WebSocket gateways via load balancers. Gateways maintain connection state in a distributed map (Redis). The chat service handles message validation, persistence, and fan-out. Kafka decouples write path from delivery path.

## Message flow: sending a message

1. Client sends message via WebSocket: `{ chat_id, content, client_msg_id }`.
2. Gateway routes to a chat service instance (partitioned by `chat_id`).
3. Chat service assigns a server-side sequence number (monotonic per chat).
4. Message persisted to Cassandra: `INSERT INTO messages (chat_id, seq, sender, content, timestamp)`.
5. Chat service publishes delivery events to Kafka topic partitioned by `chat_id`.
6. Delivery workers consume events and push to connected recipients via their gateway instances.
7. Sender receives ACK with server `seq` — client marks message as delivered.

```python
# Simplified message send handler
async def send_message(chat_id: str, sender_id: str, content: str, client_msg_id: str):
    seq = await redis.incr(f"chat:{chat_id}:seq")
    message = Message(
        chat_id=chat_id, seq=seq, sender_id=sender_id,
        content=content, timestamp=now(), client_msg_id=client_msg_id
    )
    await cassandra.execute(
        "INSERT INTO messages (chat_id, seq, ...) VALUES (?, ?, ...)",
        (chat_id, seq, ...)
    )
    await kafka.publish("message-events", key=chat_id, value=message)
    return {"seq": seq, "status": "sent"}
```

The `client_msg_id` enables idempotency — if the client retries a send, the server deduplicates by `(chat_id, client_msg_id)`.

## Group chat fan-out

For a group with N members, fan-out multiates delivery work. Strategies:

**Write fan-out:** Store one copy of the message, deliver to N recipients at read time. Efficient storage, expensive delivery for large groups.

**Read fan-out:** Write N copies (one per recipient inbox) at send time. Fast delivery, expensive storage.

**Hybrid:** Write fan-out for groups under 100 members. For larger channels (broadcast groups, announcement channels), store once and deliver to online members only; offline members sync on reconnect.

WhatsApp uses write fan-out with per-recipient delivery queues for groups up to a few hundred members.

## WebSocket gateway scaling

Each gateway instance holds thousands of WebSocket connections. Scaling challenges:

- **Connection routing:** Sticky sessions via load balancer, or a connection registry in Redis mapping `user_id → gateway_instance`.
- **Cross-gateway delivery:** When user A on gateway-1 sends to user B on gateway-3, the delivery event routes through Kafka to gateway-3, which pushes to B's WebSocket.
- **Heartbeat and reconnection:** Clients send pings every 30 seconds. Missed heartbeats trigger disconnect cleanup. Clients reconnect with exponential backoff and sync missed messages.

```javascript
// Client reconnection with sync
ws.onopen = () => {
  ws.send(JSON.stringify({
    type: "sync",
    last_seq: localStore.getLastSeq(chatId)
  }));
};
```

## Message ordering and consistency

Messages within a chat must appear in sequence order. Across chats, ordering doesn't matter. Per-chat sequence numbers (stored in Redis, incremented atomically) guarantee ordering without global coordination.

For "sent" → "delivered" → "read" status progression, use a state machine per message per recipient:

```
sent → delivered → read
```

Each transition is an event stored alongside the message. Clients update UI optimistically and reconcile with server state on sync.

## Presence system

Track online/offline/last-seen status separately from messaging — presence is best-effort:

- Gateway sets `user:online` in Redis with TTL on connect.
- TTL refreshes on heartbeat; expiry means offline.
- Last-seen updated on disconnect.
- Presence changes published to subscribed contacts via lightweight events.

Don't block message delivery on presence checks. Deliver to connected devices; queue for offline users regardless.

## Data model

```sql
-- Cassandra tables (partition key → clustering key)
CREATE TABLE messages (
    chat_id UUID,
    seq BIGINT,
    sender_id UUID,
    content TEXT,
    timestamp TIMESTAMP,
    client_msg_id TEXT,
    PRIMARY KEY (chat_id, seq)
) WITH CLUSTERING ORDER BY (seq DESC);

CREATE TABLE user_chats (
    user_id UUID,
    chat_id UUID,
    last_seq BIGINT,
    unread_count INT,
    PRIMARY KEY (user_id, chat_id)
);
```

Recent messages load from the `messages` table by `chat_id`. User's chat list loads from `user_chats` with unread counts maintained by counters.

## Common production mistakes

Teams get chat messaging wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

System design for chat messaging breaks at scale when hot keys, thundering herds, and cache stampedes are discovered during launch week instead of load test week.

## Debugging and triage workflow

When chat messaging misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [WhatsApp architecture (Meta engineering blog)](https://engineering.fb.com/)
- [Discord's real-time infrastructure](https://discord.com/blog/how-discord-stores-trillions-of-messages)
- [WebSocket scaling patterns](https://ably.com/topic/websocket-architecture)
- [Apache Cassandra data modeling for messaging](https://cassandra.apache.org/doc/latest/cassandra/developing/data-modeling/)
- [System Design Interview — Alex Xu, Chapter on Chat Systems](https://www.amazon.com/System-Design-Interview-insiders-Second/dp/B08CMF2CQF)
